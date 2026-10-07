"""Scalar typing (YAML 1.2 core schema), scalar printing, and parsing of command-line VALUEs.

The core-schema rules live here and only here (research R-2): they type plain scalars read from
files and from the command line, and they decide whether a string could be written plain.
"""

import math
import re
from dataclasses import dataclass
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from troupe.config.includes import LITERAL_TAG
from troupe.errors import UsageError

type Scalar = str | int | float | bool | None
type Value = Scalar | list[Value] | dict[str, Value]

_NULL = re.compile(r"null|Null|NULL|~|")
_BOOL_TRUE = re.compile(r"true|True|TRUE")
_BOOL_FALSE = re.compile(r"false|False|FALSE")
_INT_DEC = re.compile(r"[-+]?[0-9]+")
_INT_OCT = re.compile(r"0o[0-7]+")
_INT_HEX = re.compile(r"0x[0-9a-fA-F]+")
_FLOAT = re.compile(r"[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?")
_INF = re.compile(r"[-+]?(\.inf|\.Inf|\.INF)")
_NAN = re.compile(r"\.nan|\.NaN|\.NAN")

_TAG_PREFIX = "tag:yaml.org,2002:"

# Set by the loader's composer on the stand-in node it returns for an alias (step 6).
ALIAS_NAME = "troupe_alias_name"  # the anchor's name
ALIAS_TARGET = "troupe_alias_target"  # the anchored node


def resolve_plain(text: str) -> Scalar:
    """Type a plain scalar's text by the YAML 1.2 core schema."""
    if _NULL.fullmatch(text):
        return None
    if _BOOL_TRUE.fullmatch(text):
        return True
    if _BOOL_FALSE.fullmatch(text):
        return False
    if _INT_DEC.fullmatch(text):
        return int(text, 10)
    if _INT_OCT.fullmatch(text):
        return int(text[2:], 8)
    if _INT_HEX.fullmatch(text):
        return int(text[2:], 16)
    if _FLOAT.fullmatch(text):
        return float(text)
    if _INF.fullmatch(text):
        return -math.inf if text.startswith("-") else math.inf
    if _NAN.fullmatch(text):
        return math.nan
    return text


def resolve_node(node: ScalarNode, source: str) -> Scalar:
    """Type a composed scalar node. `source` is the text the node was composed from."""
    # An alias is typed as the node it refers to (step 6).
    node = getattr(node, ALIAS_TARGET, node)
    text: str = node.value
    if node.tag == LITERAL_TAG:
        # `!literal` takes the text literally, as a string, whatever it looks like (step 7
        # FR-622, D-66).
        return text.replace("\a", "") if node.style == ">" else text
    if node.style == ">":
        # ruamel's round-trip composer marks fold points with BEL; a folded scalar cannot hold
        # a real BEL (it is not printable), so the markers are removed.
        text = text.replace("\a", "")
    explicit = source.startswith("!", content_start(source, node))
    if explicit and isinstance(node.tag, str) and node.tag.startswith(_TAG_PREFIX):
        kind = node.tag[len(_TAG_PREFIX) :]
        if kind == "str":
            return text
        typed = resolve_plain(text)
        expected: dict[str, tuple[type, ...]] = {
            "int": (int,),
            "float": (float, int),
            "bool": (bool,),
            "null": (type(None),),
        }
        if kind in expected and isinstance(typed, expected[kind]):
            return float(typed) if kind == "float" and typed is not None else typed
        return text
    if node.style is None:
        return resolve_plain(text)
    return text


def content_start(text: str, node: Node) -> int:
    """Where a node's own bytes start: after its `&anchor`, so a change to the value keeps the
    anchor, and after a `!literal` tag, so a change keeps the tag (step 7 FR-644). An anchored
    collection starts at its first entry; an empty anchored scalar just after the anchor."""
    offset = _after_literal_tag(text, int(node.start_mark.index))
    if not text.startswith("&", offset):
        return offset
    while offset < len(text) and text[offset] not in " \t\r\n,[]{}":
        offset += 1
    anchor_end = offset
    tag_end = literal_tag_end(text, _skip_blanks(text, offset))
    if tag_end is not None:
        anchor_end = offset = tag_end  # `&a !literal x`: the tag stays with the anchor
    while offset < len(text):
        if text[offset] in " \t":
            offset += 1
        elif isinstance(node, ScalarNode) and text[offset] in "\r\n#":
            return anchor_end if node.value == "" else offset
        elif text[offset] in "\r\n":
            offset += 1
        elif text[offset] == "#":
            while offset < len(text) and text[offset] not in "\r\n":
                offset += 1
        else:
            break
    return offset


def _skip_blanks(text: str, offset: int) -> int:
    while offset < len(text) and text[offset] in " \t":
        offset += 1
    return offset


def literal_tag_end(text: str, offset: int) -> int | None:
    """The end of a `!literal` tag and the blanks after it at `offset`, or None if there is
    none there."""
    end = offset + len(LITERAL_TAG)
    if not text.startswith(LITERAL_TAG, offset):
        return None
    if end < len(text) and text[end] not in " \t\r\n":
        return None  # a longer tag, e.g. `!literally`
    return _skip_blanks(text, end)


def _after_literal_tag(text: str, offset: int) -> int:
    end = literal_tag_end(text, offset)
    return offset if end is None else end


def scalars_equal(a: Value, b: Value) -> bool:
    """Type-exact equality: `1`, `1.0` and `true` are all different; NaN equals NaN."""
    if type(a) is not type(b):
        return False
    if isinstance(a, float) and isinstance(b, float):
        return a == b or (math.isnan(a) and math.isnan(b))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(scalars_equal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return list(a) == list(b) and all(scalars_equal(a[k], b[k]) for k in a)
    return a == b


def format_scalar(value: Scalar) -> str:
    """Printed form of a scalar (FR-006), including the trailing newline."""
    if isinstance(value, str):
        return value if value.endswith("\n") else value + "\n"
    if value is None:
        text = "null"
    elif isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = repr(value)
    return text + "\n"


# --- Command-line VALUE --------------------------------------------------------------------


@dataclass(frozen=True)
class NewScalar:
    """A scalar from the command line. `spelling` is its text when it was written plain; `tag`
    is written before it (`!literal`, step 7 FR-640) and is not part of the value."""

    value: Scalar
    spelling: str | None = None
    tag: str | None = None


type NewNode = NewScalar | list[NewNode] | dict[str, NewNode]


def plain_value(node: NewNode) -> Value:
    if isinstance(node, NewScalar):
        return node.value
    if isinstance(node, list):
        return [plain_value(item) for item in node]
    return {key: plain_value(item) for key, item in node.items()}


def _compose(text: str) -> Any:
    return YAML(typ="rt").compose(text)


def parse_value(text: str) -> NewNode:
    """Parse VALUE as one YAML 1.2 flow node (research R-3)."""
    try:
        node = _compose(text)
    except YAMLError as error:
        raise UsageError(f"invalid VALUE {text!r}: {error}") from None
    if node is None:
        raise UsageError(f"invalid VALUE {text!r}: expected a YAML flow node")
    return _new_node(node, text)


def _new_node(node: Node, source: str) -> NewNode:
    if isinstance(node, ScalarNode):
        if node.style in ("|", ">"):
            raise UsageError(f"invalid VALUE {source!r}: block scalars are not flow nodes")
        value = resolve_node(node, source)
        return NewScalar(value, node.value if node.style is None else None)
    if not getattr(node, "flow_style", False):
        raise UsageError(f"invalid VALUE {source!r}: block collections are not flow nodes")
    if isinstance(node, SequenceNode):
        return [_new_node(item, source) for item in node.value]
    if isinstance(node, MappingNode):
        result: dict[str, NewNode] = {}
        for key, item in node.value:
            result[str(key.value)] = _new_node(item, source)
        return result
    raise UsageError(f"invalid VALUE {source!r}")
