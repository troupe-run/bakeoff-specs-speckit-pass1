"""Load a theatre's configuration, following `file:` includes."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ruamel.yaml import YAML
from ruamel.yaml.composer import Composer
from ruamel.yaml.error import YAMLError
from ruamel.yaml.events import AliasEvent
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from troupe.config.files import SourceFile, find_config, is_yaml_name, read_source
from troupe.config.scalars import ALIAS_NAME, ALIAS_TARGET, resolve_node
from troupe.config.tree import (
    Located,
    LocatedMapping,
    LocatedScalar,
    LocatedSequence,
    TextInclude,
)
from troupe.errors import LoadError

INCLUDE_PREFIX = "file:"
REF_KEY = "$ref"  # the key of a mapping-form include (spec FR-400)


def include_target(value: object) -> str | None:
    """The include path named by a string value, or None if the value is not an include."""
    if isinstance(value, str) and value.startswith(INCLUDE_PREFIX):
        return value[len(INCLUDE_PREFIX) :]
    return None


@dataclass
class Loaded:
    root: LocatedMapping
    files: dict[Path, SourceFile] = field(default_factory=dict)
    composed: dict[Path, Any] = field(default_factory=dict)


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
    def __init__(self, overrides: dict[Path, str]) -> None:
        self.overrides = overrides
        self.loaded: Loaded | None = None
        self.files: dict[Path, SourceFile] = {}
        self.composed: dict[Path, Any] = {}

    def source(self, path: Path) -> SourceFile:
        key = path.resolve()
        if key not in self.files:
            if key in self.overrides:
                kind: Literal["yaml", "text"] = "yaml" if is_yaml_name(key) else "text"
                self.files[key] = SourceFile(key, self.overrides[key], kind)
            else:
                self.files[key] = read_source(key)
        return self.files[key]

    def composed_root(self, source: SourceFile) -> Any:
        if source.path not in self.composed:
            self.composed[source.path] = compose(source)
        return self.composed[source.path]

    def load(self, main: Path) -> Loaded:
        source = self.source(main)
        node = self.composed_root(source)
        if node is None:
            root = LocatedMapping(source, None, in_flow=False)
        elif isinstance(node, MappingNode):
            located = self.build(node, source, False, (source.path,))
            assert isinstance(located, LocatedMapping)
            root = located
        else:
            raise LoadError(f"{source.path}: the top level must be a mapping")
        return Loaded(root, self.files, self.composed)

    def build(
        self,
        node: Node,
        source: SourceFile,
        in_flow: bool,
        chain: tuple[Path, ...],
        follow: bool = True,
    ) -> Located:
        """Build the located tree for `node`; `follow=False` keeps a `file:` string unfollowed
        (the value of `$ref`, which the enclosing mapping includes itself)."""
        if isinstance(node, ScalarNode):
            scalar = LocatedScalar(resolve_node(node, source.text), source, node, in_flow)
            target = include_target(scalar.value)
            if target is None or not follow:
                return scalar
            return self.include(scalar, target, chain)
        if isinstance(node, SequenceNode):
            flow = in_flow or bool(node.flow_style)
            sequence = LocatedSequence(source, node, in_flow)
            sequence.items = [self.build(item, source, flow, chain) for item in node.value]
            return sequence
        if isinstance(node, MappingNode):
            flow = in_flow or bool(node.flow_style)
            mapping = LocatedMapping(source, node, in_flow)
            ref: LocatedScalar | None = None
            for key_node, value_node in node.value:
                if not isinstance(key_node, ScalarNode):
                    raise LoadError(f"{source.path}: only scalar mapping keys are supported")
                key = LocatedScalar(resolve_node(key_node, source.text), source, key_node, flow)
                value = self.build(value_node, source, flow, chain, follow=key.value != REF_KEY)
                if (
                    key.value == REF_KEY
                    and isinstance(value, LocatedScalar)
                    and include_target(value.value) is not None
                ):
                    ref = value
                mapping.entries.append((key, value))
            if ref is None:
                return mapping  # no `$ref`, or one that is not an include string (spec D-42)
            return self.mapping_include(mapping, ref, chain)
        raise LoadError(f"{source.path}: unsupported YAML node")

    def mapping_include(
        self, raw: LocatedMapping, ref: LocatedScalar, chain: tuple[Path, ...]
    ) -> Located:
        """A mapping-form include: the included content deep-merged with the overrides (spec
        FR-400 to FR-403, D-43; research O-3). `raw` is the mapping as written, `$ref` included."""
        target = include_target(ref.value)
        assert target is not None
        content = self.include(ref, target, chain)
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

    def include(self, scalar: LocatedScalar, target: str, chain: tuple[Path, ...]) -> Located:
        path = (scalar.file.path.parent / target).resolve()
        if path in chain:
            raise LoadError(f"{scalar.file.path}: include cycle through {path}")
        if not path.exists():
            raise LoadError(f"{scalar.file.path}: included file {path} not found")
        source = self.source(path)
        if source.kind == "text":
            return TextInclude(scalar, source)
        node = self.composed_root(source)
        if node is None:
            # An empty YAML file embeds as null; its span is the (empty) file itself.
            node = ScalarNode("tag:yaml.org,2002:null", "", _Mark(0), _Mark(0))
        embedded = self.build(node, source, False, (*chain, path))
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
    """Load the same configuration again, with `overrides` substituting file texts."""
    return _Loader(overrides).load(loaded.root.file.path)


def load(theatre: Path, overrides: dict[Path, str] | None = None) -> Loaded:
    """Load the theatre's configuration. `overrides` substitutes file texts (by resolved path)."""
    return _Loader(overrides or {}).load(find_config(theatre))
