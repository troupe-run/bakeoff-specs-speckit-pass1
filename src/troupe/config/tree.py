"""The loaded configuration: every node remembers the file and span its bytes come from."""

from dataclasses import dataclass, field

from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode

from troupe.config.files import SourceFile
from troupe.config.scalars import Scalar


@dataclass(eq=False)
class LocatedScalar:
    value: Scalar
    file: SourceFile
    node: ScalarNode
    in_flow: bool
    included_by: "LocatedScalar | None" = None

    @property
    def start(self) -> int:
        return int(self.node.start_mark.index)

    @property
    def end(self) -> int:
        return int(self.node.end_mark.index)

    @property
    def style(self) -> str | None:
        style: str | None = self.node.style
        return style


@dataclass(eq=False)
class LocatedMapping:
    file: SourceFile
    node: MappingNode | None  # None for an empty main file (an empty mapping, spec D-5)
    in_flow: bool
    entries: list[tuple[LocatedScalar, "Located"]] = field(default_factory=list)
    included_by: LocatedScalar | None = None

    @property
    def flow(self) -> bool:
        return self.node is not None and bool(self.node.flow_style)

    @property
    def start(self) -> int:
        return 0 if self.node is None else int(self.node.start_mark.index)

    @property
    def end(self) -> int:
        return len(self.file.text) if self.node is None else int(self.node.end_mark.index)

    def get(self, key: str) -> "Located | None":
        for key_node, value in self.entries:
            if str(key_node.node.value) == key:
                return value
        return None


@dataclass(eq=False)
class LocatedSequence:
    file: SourceFile
    node: SequenceNode
    in_flow: bool
    items: list["Located"] = field(default_factory=list)
    included_by: LocatedScalar | None = None

    @property
    def flow(self) -> bool:
        return bool(self.node.flow_style)

    @property
    def start(self) -> int:
        return int(self.node.start_mark.index)

    @property
    def end(self) -> int:
        return int(self.node.end_mark.index)


@dataclass(eq=False)
class TextInclude:
    """A `file:` string whose target is not YAML: its value is the target's exact text."""

    include: LocatedScalar
    target: SourceFile
    included_by: LocatedScalar | None = None

    @property
    def value(self) -> str:
        return self.target.text


type Located = LocatedScalar | LocatedMapping | LocatedSequence | TextInclude
