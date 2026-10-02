"""Load a theatre's configuration, following `file:` includes."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from troupe.config.files import SourceFile, find_config, is_yaml_name, read_source
from troupe.config.scalars import resolve_node
from troupe.config.tree import Located, LocatedMapping, LocatedScalar, LocatedSequence, TextInclude
from troupe.errors import LoadError

INCLUDE_PREFIX = "file:"


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


def compose(source: SourceFile) -> Any:
    """Compose one file into ruamel nodes; positions are offsets into `source.text`."""
    try:
        return YAML(typ="rt").compose(source.text)
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
        self, node: Node, source: SourceFile, in_flow: bool, chain: tuple[Path, ...]
    ) -> Located:
        if isinstance(node, ScalarNode):
            scalar = LocatedScalar(resolve_node(node, source.text), source, node, in_flow)
            target = include_target(scalar.value)
            if target is None:
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
            for key_node, value_node in node.value:
                if not isinstance(key_node, ScalarNode):
                    raise LoadError(f"{source.path}: only scalar mapping keys are supported")
                key = LocatedScalar(resolve_node(key_node, source.text), source, key_node, flow)
                mapping.entries.append((key, self.build(value_node, source, flow, chain)))
            return mapping
        raise LoadError(f"{source.path}: unsupported YAML node")

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


class _Mark:
    def __init__(self, index: int) -> None:
        self.index = index


def load(theatre: Path, overrides: dict[Path, str] | None = None) -> Loaded:
    """Load the theatre's configuration. `overrides` substitutes file texts (by resolved path)."""
    return _Loader(overrides or {}).load(find_config(theatre))
