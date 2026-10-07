"""The loaded configuration: every node remembers the file and span its bytes come from.

A mapping-form include (`$ref` plus overrides) is loaded merged: its entries are the included
content's, with overridden entries taken from the including file (spec FR-401). Each entry still
remembers the file it is written in.
"""

from dataclasses import dataclass, field
from typing import Any, TypeGuard

from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode

from troupe.config.files import SourceFile
from troupe.config.scalars import ALIAS_NAME, ALIAS_TARGET, Scalar, content_start


@dataclass(eq=False)
class LocatedScalar:
    value: Scalar
    file: SourceFile
    node: ScalarNode
    in_flow: bool
    included_by: "LocatedScalar | None" = None
    include_site: "LocatedMapping | None" = None

    @property
    def start(self) -> int:
        return content_start(self.file.text, self.node)

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
    include_site: "LocatedMapping | None" = None
    # The override mapping merged into this one; None = not merged (spec FR-401, research O-2).
    overrides: "LocatedMapping | None" = None
    # A merged mapping's included part before the overrides were merged in; its entries are
    # only that file's (research O-4: the walk finds include sites through it; CR-B writes
    # `--in-include` keys into it).
    base: "LocatedMapping | None" = None

    @property
    def flow(self) -> bool:
        return self.node is not None and bool(self.node.flow_style)

    @property
    def start(self) -> int:
        return 0 if self.node is None else content_start(self.file.text, self.node)

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
    include_site: LocatedMapping | None = None

    @property
    def flow(self) -> bool:
        return bool(self.node.flow_style)

    @property
    def start(self) -> int:
        return content_start(self.file.text, self.node)

    @property
    def end(self) -> int:
        return int(self.node.end_mark.index)


@dataclass(eq=False)
class TextInclude:
    """A `file:` string whose target is not YAML: its value is the target's exact text."""

    include: LocatedScalar
    target: SourceFile
    included_by: LocatedScalar | None = None
    include_site: LocatedMapping | None = None

    @property
    def value(self) -> str:
        return self.target.text


type Located = LocatedScalar | LocatedMapping | LocatedSequence | TextInclude

_QUOTES = ('"', "'")


def as_written(scalar: LocatedScalar) -> str:
    """A scalar's text as written in its file, without quotes: how messages show an include
    string (step 7 D-70)."""
    text = scalar.file.text[scalar.start : scalar.end]
    if scalar.style in _QUOTES and len(text) >= 2:
        return text[1:-1]
    return text


def shared_part(mapping: LocatedMapping) -> LocatedMapping:
    """A merged mapping's part written in the included file, before any override (step 5 CR-B
    D-51): `base` followed through nested merges, so nested includes give the deepest file."""
    while mapping.base is not None:
        mapping = mapping.base
    return mapping


def written_as(node: Located) -> "Located | None":
    """The node that stands for the whole value in the including file: the mapping-form include
    as written (`$ref` and overrides), else the `file:` string; None when `node` is not an include
    root (research O-2)."""
    if node.include_site is not None:
        return node.include_site
    return node.included_by


# --- Anchors and aliases (step 6) ----------------------------------------------------------


def is_alias(node: Located) -> TypeGuard[LocatedScalar | LocatedMapping | LocatedSequence]:
    """Whether `node` is an alias (`*name`) as written."""
    return alias_name(node) is not None


def alias_name(node: Located) -> str | None:
    """The anchor name when `node` is an alias (`*name`) as written, else None."""
    name: str | None = getattr(getattr(node, "node", None), ALIAS_NAME, None)
    return name


def alias_target(node: Located) -> Any:
    """The anchored composed node an alias refers to (only when `alias_name(node)` is set)."""
    return getattr(node.node, ALIAS_TARGET) if not isinstance(node, TextInclude) else None
