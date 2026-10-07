"""Load a theatre's configuration, following includes (`file:` and, from step 7, URLs)."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ruamel.yaml import YAML
from ruamel.yaml.composer import Composer
from ruamel.yaml.error import YAMLError
from ruamel.yaml.events import AliasEvent
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from troupe.config.fetch import FetchError, fetch
from troupe.config.files import SourceFile, find_config, is_yaml_name, is_yaml_url, read_source
from troupe.config.includes import LITERAL_TAG, REF_KEY, FileRef, UrlRef, include_ref
from troupe.config.leaves import to_value
from troupe.config.scalars import ALIAS_NAME, ALIAS_TARGET, resolve_node
from troupe.config.schema import Schema, SubSchema, is_uri, load_schema, schema_child
from troupe.config.tree import (
    Located,
    LocatedMapping,
    LocatedScalar,
    LocatedSequence,
    TextInclude,
    as_written,
)
from troupe.errors import LoadError

type Chain = tuple[Path | str, ...]
"""The sources on the way to a node: resolved paths, and URLs as written."""


@dataclass
class Loaded:
    root: LocatedMapping
    # Local files only: what `watch` reads back (step 7 D-65).
    files: dict[Path, SourceFile] = field(default_factory=dict)
    composed: dict[Path | str, Any] = field(default_factory=dict)
    # Fetched documents by URL, reused by a command's re-checks (spec D-62, research U-3).
    remote: dict[str, SourceFile] = field(default_factory=dict)
    schema: Schema | None = None


class _AliasComposer(Composer):
    """ruamel returns the anchored node itself for an alias; this returns a stand-in instead, a
    shallow copy spanning the `*name` token, so a value reached through an alias can be told from
    one reached through its anchor (step 6). The stand-in's children are the anchored node's."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if not self.parser.check_event(AliasEvent):
            return super().compose_node(parent, index)
        event = self.parser.peek_event()
        target = super().compose_node(parent, index)
        kind = _ALIAS_KINDS[type(target)]
        stand_in = kind.__new__(kind)
        for cls in type(target).__mro__:
            for slot in getattr(cls, "__slots__", ()):
                if hasattr(target, slot):
                    setattr(stand_in, slot, getattr(target, slot))
        stand_in.start_mark = event.start_mark
        stand_in.end_mark = event.end_mark
        stand_in.anchor = None
        setattr(stand_in, ALIAS_NAME, event.anchor)
        setattr(stand_in, ALIAS_TARGET, target)
        return stand_in


_STAND_IN_SLOTS = (ALIAS_NAME, ALIAS_TARGET)


class _AliasScalar(ScalarNode):
    __slots__ = _STAND_IN_SLOTS


class _AliasSequence(SequenceNode):
    __slots__ = _STAND_IN_SLOTS


class _AliasMapping(MappingNode):
    __slots__ = _STAND_IN_SLOTS


_ALIAS_KINDS: dict[type[Node], type[Node]] = {
    ScalarNode: _AliasScalar,
    SequenceNode: _AliasSequence,
    MappingNode: _AliasMapping,
}


def compose(source: SourceFile) -> Any:
    """Compose one file into ruamel nodes; positions are offsets into `source.text`."""
    yaml = YAML(typ="rt")
    yaml.Composer = _AliasComposer
    try:
        return yaml.compose(source.text)
    except YAMLError as error:
        raise LoadError(f"{source.path}: invalid YAML: {error}") from None


class _Loader:
    def __init__(
        self, overrides: dict[Path, str], fetched: dict[str, SourceFile], schema: Schema | None
    ) -> None:
        self.overrides = overrides
        self.files: dict[Path, SourceFile] = {}
        self.composed: dict[Path | str, Any] = {}
        self.fetched = dict(fetched)
        # For each fetched URL, the include string in a local file it is reached through.
        self.local_sites: dict[str, LocatedScalar] = {}
        self.schema = schema

    def source(self, path: Path) -> SourceFile:
        key = path.resolve()
        if key not in self.files:
            if key in self.overrides:
                kind: Literal["yaml", "text"] = "yaml" if is_yaml_name(key) else "text"
                self.files[key] = SourceFile(key, self.overrides[key], kind)
            else:
                self.files[key] = read_source(key)
        return self.files[key]

    def remote_source(self, url: str, scalar: LocatedScalar) -> SourceFile:
        """The fetched document at `url`, included by `scalar`; fetched at most once per command
        (spec D-62)."""
        site = (
            scalar if isinstance(scalar.file.path, Path) else self.local_sites.get(scalar.file.path)
        )
        if site is not None:
            self.local_sites.setdefault(url, site)
        included_from = str(scalar.file.path)
        if site is not None and site is not scalar:
            # Nested remote includes: also name the local include line, the one the user can
            # change (spec FR-602, FR-611).
            included_from += (
                f" (included through {as_written(site)} at line "
                f"{int(site.node.start_mark.line) + 1} of {site.file.path})"
            )
        if url not in self.fetched:
            kind: Literal["yaml", "text"] = "yaml" if is_yaml_url(url) else "text"
            self.fetched[url] = SourceFile(url, fetch(url, included_from), kind)
        source = self.fetched[url]
        if source.kind == "yaml":
            try:
                self.composed_root(source)
            except LoadError as error:
                # Name the include's file too: the user can change only that (spec FR-602).
                raise FetchError(f"{included_from}: {error.message}") from None
        return source

    def composed_root(self, source: SourceFile) -> Any:
        if source.path not in self.composed:
            self.composed[source.path] = compose(source)
        return self.composed[source.path]

    def load(self, main: Path) -> Loaded:
        main = main.resolve()
        source = self.source(main)
        node = self.composed_root(source)
        if node is None:
            root = LocatedMapping(source, None, in_flow=False)
        elif isinstance(node, MappingNode):
            root_schema = None if self.schema is None else self.schema.document
            located = self.build(node, source, False, (main,), root_schema)
            assert isinstance(located, LocatedMapping)
            root = located
        else:
            raise LoadError(f"{source.path}: the top level must be a mapping")
        if self.schema is not None:
            # Every command loads through here, so an invalid configuration cannot be used, and
            # a `set` whose re-check fails here is refused (spec FR-631, FR-633; research U-6).
            self.schema.validate(to_value(root))
        return Loaded(root, self.files, self.composed, self.fetched, self.schema)

    def is_include(self, scalar: LocatedScalar, sub: SubSchema) -> FileRef | UrlRef | None:
        """What `scalar` includes, or None when it is not an include: not an include string, or
        a literal — tagged `!literal`, or `format: uri` in its subschema `sub` (spec FR-620)."""
        if scalar.node.tag == LITERAL_TAG or is_uri(sub):
            return None
        return include_ref(scalar.value)

    def build(
        self,
        node: Node,
        source: SourceFile,
        in_flow: bool,
        chain: Chain,
        sub: SubSchema,
        follow: bool = True,
    ) -> Located:
        """Build the located tree for `node`, whose subschema is `sub`; `follow=False` keeps an
        include string unfollowed (the value of `$ref`, which the enclosing mapping includes
        itself)."""
        if isinstance(node, ScalarNode):
            scalar = LocatedScalar(resolve_node(node, source.text), source, node, in_flow)
            included = self.is_include(scalar, sub)
            if included is None or not follow:
                return scalar
            return self.include(scalar, included, chain, sub)
        if node.tag == LITERAL_TAG:
            raise LoadError(
                f"{source.path}: line {node.start_mark.line + 1}: {LITERAL_TAG} applies to a "
                "single value, not a mapping or list"
            )
        if isinstance(node, SequenceNode):
            flow = in_flow or bool(node.flow_style)
            sequence = LocatedSequence(source, node, in_flow)
            sequence.items = [
                self.build(item, source, flow, chain, schema_child(sub, index))
                for index, item in enumerate(node.value)
            ]
            return sequence
        if isinstance(node, MappingNode):
            flow = in_flow or bool(node.flow_style)
            mapping = LocatedMapping(source, node, in_flow)
            ref: LocatedScalar | None = None
            for key_node, value_node in node.value:
                if not isinstance(key_node, ScalarNode):
                    raise LoadError(f"{source.path}: only scalar mapping keys are supported")
                key = LocatedScalar(resolve_node(key_node, source.text), source, key_node, flow)
                is_ref = key.value == REF_KEY
                # `$ref` is not part of the configuration, so it has no subschema.
                child = None if is_ref else schema_child(sub, str(key.node.value))
                value = self.build(value_node, source, flow, chain, child, follow=not is_ref)
                if (
                    is_ref
                    and isinstance(value, LocatedScalar)
                    and self.is_include(value, None) is not None
                ):
                    ref = value
                mapping.entries.append((key, value))
            if ref is None:
                return mapping  # no `$ref`, or one that is not an include string (spec D-42)
            return self.mapping_include(mapping, ref, chain, sub)
        raise LoadError(f"{source.path}: unsupported YAML node")

    def mapping_include(
        self, raw: LocatedMapping, ref: LocatedScalar, chain: Chain, sub: SubSchema
    ) -> Located:
        """A mapping-form include: the included content deep-merged with the overrides (spec
        FR-400 to FR-403, D-43; research O-3). `raw` is the mapping as written, `$ref` included;
        the content fills the mapping's place, so it has the mapping's subschema `sub`."""
        target = self.is_include(ref, None)
        assert target is not None
        content = self.include(ref, target, chain, sub)
        overrides = [(key, value) for key, value in raw.entries if value is not ref]
        if isinstance(content, TextInclude):
            if overrides:
                raise LoadError(
                    f"{raw.file.path}: {REF_KEY} {ref.value!r} names a non-YAML file; "
                    "it cannot have overrides"
                )
            content.include_site = raw
            return content
        if not isinstance(content, LocatedMapping):
            if overrides:
                raise LoadError(
                    f"{raw.file.path}: {REF_KEY} {ref.value!r} does not hold a mapping; "
                    "overrides need one"
                )
            content.include_site = raw
            return content
        merged = merge(content, overrides, raw)
        merged.included_by = ref
        merged.include_site = raw
        return merged

    def include(
        self, scalar: LocatedScalar, ref: FileRef | UrlRef, chain: Chain, sub: SubSchema
    ) -> Located:
        """The content `scalar` includes, at a place whose subschema is `sub`."""
        if isinstance(ref, UrlRef):
            # URLs are compared as written: a cycle is the same string met again (step 1 FR-012).
            if ref.url in chain:
                raise LoadError(f"{scalar.file.path}: include cycle through {ref.url}")
            source = self.remote_source(ref.url, scalar)
            return self.embed(scalar, source, (*chain, ref.url), sub)
        if isinstance(scalar.file.path, str):
            # Remote content may not reach into the user's disk (spec D-61).
            raise LoadError(
                f"{scalar.file.path}: the file: include {scalar.value!r} in remote content is "
                "not allowed"
            )
        path = (scalar.file.path.parent / ref.path).resolve()
        if path in chain:
            raise LoadError(f"{scalar.file.path}: include cycle through {path}")
        if not path.exists():
            raise LoadError(f"{scalar.file.path}: included file {path} not found")
        return self.embed(scalar, self.source(path), (*chain, path), sub)

    def embed(
        self, scalar: LocatedScalar, source: SourceFile, chain: Chain, sub: SubSchema
    ) -> Located:
        """`source`'s content in place of the include string `scalar`."""
        if source.kind == "text":
            return TextInclude(scalar, source)
        node = self.composed_root(source)
        if node is None:
            # An empty YAML file embeds as null; its span is the (empty) file itself.
            node = ScalarNode("tag:yaml.org,2002:null", "", _Mark(0), _Mark(0))
        embedded = self.build(node, source, False, chain, sub)
        embedded.included_by = scalar
        return embedded


def merge(
    base: LocatedMapping,
    overrides: list[tuple[LocatedScalar, Located]],
    written: LocatedMapping,
) -> LocatedMapping:
    """`base` deep-merged with `overrides` (spec FR-401, D-46).

    Mappings merge key by key, recursively; any other override replaces. Overridden keys keep
    their place in `base`; override-only keys follow in written order. Overridden entries are the
    override's own key and value, so each still knows the file it is written in. `written` is the
    override mapping as written (the merged mapping's `overrides`).
    """
    pending = {str(key.node.value): (key, value) for key, value in overrides}
    merged = LocatedMapping(base.file, base.node, base.in_flow, overrides=written, base=base)
    for key, value in base.entries:
        override = pending.pop(str(key.node.value), None)
        if override is None:
            merged.entries.append((key, value))
            continue
        override_key, override_value = override
        if isinstance(value, LocatedMapping) and isinstance(override_value, LocatedMapping):
            nested = merge(value, override_value.entries, override_value)
            merged.entries.append((override_key, nested))
        else:
            merged.entries.append(override)
    merged.entries.extend(pending.values())
    return merged


class _Mark:
    def __init__(self, index: int) -> None:
        self.index = index


def reload(loaded: Loaded, overrides: dict[Path, str]) -> Loaded:
    """Load the same configuration again, with `overrides` substituting file texts and the
    documents `loaded` fetched reused (spec D-62)."""
    main = loaded.root.file.path
    assert isinstance(main, Path)
    return _Loader(overrides, loaded.remote, loaded.schema).load(main)


def load(
    theatre: Path,
    overrides: dict[Path, str] | None = None,
    fetched: dict[str, SourceFile] | None = None,
) -> Loaded:
    """Load the theatre's configuration. `overrides` substitutes file texts (by resolved path);
    `fetched` supplies documents already fetched by this command (by URL, spec D-62)."""
    main = find_config(theatre)
    return _Loader(overrides or {}, fetched or {}, load_schema(theatre)).load(main)
