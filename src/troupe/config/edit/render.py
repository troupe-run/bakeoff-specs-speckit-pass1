"""How values are spelled in YAML: scalar styles, escaping, literal blocks, new collections.

Each style's "can it represent this value?" rule lives here (research R-8).
"""

import math

from troupe.config.scalars import NewNode, NewScalar, Scalar, resolve_plain

PLAIN: str | None = None
SINGLE = "'"
DOUBLE = '"'
LITERAL = "|"
FOLDED = ">"
INLINE_STYLES: tuple[str | None, ...] = (PLAIN, SINGLE, DOUBLE)

_INDICATORS = set("-?:,[]{}#&*!|>'\"%@`")
_FLOW_INDICATORS = set(",[]{}")
# Characters some YAML readers treat as line breaks or byte-order marks; never written bare
# outside double quotes.
_UNSAFE = "\ufeff\u2028\u2029"

# Escapes YAML defines for control characters (FR-028: only `\\`, `\"` and control characters
# are escaped; every other character is written literally).
_NAMED_ESCAPES = {
    "\0": "\\0",
    "\a": "\\a",
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\v": "\\v",
    "\f": "\\f",
    "\r": "\\r",
    "\x1b": "\\e",
    "\x85": "\\N",
    "\\": "\\\\",
    '"': '\\"',
}


def is_control(char: str) -> bool:
    code = ord(char)
    return code < 0x20 or code == 0x7F or 0x80 <= code <= 0x9F


def is_multiline(value: Scalar) -> bool:
    return isinstance(value, str) and "\n" in value


def can_plain(text: str, in_flow: bool) -> bool:
    """Whether a string can be written as a plain scalar and read back as the same string."""
    if not text or text != text.strip(" \t"):
        return False
    if any(is_control(char) or char in _UNSAFE for char in text):
        return False
    first = text[0]
    if first in _INDICATORS:
        follower = text[1:2]
        if first not in "-?:" or follower in ("", " ", "\t"):
            return False
        if in_flow and follower in _FLOW_INDICATORS:
            return False
    if ": " in text or ":\t" in text or " #" in text or "\t#" in text or text.endswith(":"):
        return False
    if in_flow and any(char in _FLOW_INDICATORS for char in text):
        return False
    if text in ("---", "...") or text.startswith(("--- ", "... ")):
        return False
    return resolve_plain(text) == text


def can_single(text: str) -> bool:
    return not any((is_control(char) and char != "\t") or char in _UNSAFE for char in text)


def render_double(text: str) -> str:
    out = []
    for char in text:
        if char in _NAMED_ESCAPES:
            out.append(_NAMED_ESCAPES[char])
        elif is_control(char):
            out.append(f"\\x{ord(char):02x}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def render_single(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def canonical_plain(value: Scalar) -> str:
    """Plain spelling of a non-string scalar."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value):
            return ".nan"
        if math.isinf(value):
            return ".inf" if value > 0 else "-.inf"
        return repr(value)
    return str(value)


def can_style(value: Scalar, style: str | None, in_flow: bool) -> bool:
    if not isinstance(value, str):
        return style is PLAIN
    if style is PLAIN:
        return can_plain(value, in_flow)
    if style == SINGLE:
        return "\n" not in value and can_single(value)
    return style == DOUBLE


def tagged(scalar: NewScalar, text: str) -> str:
    """`text` — a scalar's spelling or a literal block's header — after the scalar's tag, if it
    has one. A tag is spelled here and only here (step 7 FR-640, research U-8)."""
    return f"{scalar.tag} {text}" if scalar.tag else text


def render_inline(scalar: NewScalar, preferred: str | None, in_flow: bool) -> str:
    """One-line spelling, after any tag: keep `preferred` if it can represent the value, else
    plain, single, double (FR-026/FR-027)."""
    return tagged(scalar, _spell_inline(scalar, preferred, in_flow))


def _spell_inline(scalar: NewScalar, preferred: str | None, in_flow: bool) -> str:
    value = scalar.value
    if not isinstance(value, str):
        return scalar.spelling if scalar.spelling is not None else canonical_plain(value)
    for style in (preferred, *INLINE_STYLES):
        if style in INLINE_STYLES and can_style(value, style, in_flow):
            if style is PLAIN:
                return value
            return render_single(value) if style == SINGLE else render_double(value)
    return render_double(value)  # unreachable: double can represent every string


# --- Block scalars -------------------------------------------------------------------------


def chomping_for(value: str, old: str) -> str:
    """Chomping indicator: keep `old` ("", "-" or "+") unless the value's trailing newlines
    require a different one (FR-030, research B-9)."""
    trailing = len(value) - len(value.rstrip("\n"))
    if trailing == 0:
        return "-"
    if old == "+" or trailing > 1 or value.strip("\n") == "":
        return "+"
    return ""


def literal_representable(value: str) -> bool:
    return not any((is_control(char) and char not in "\t\n") or char in _UNSAFE for char in value)


def block_content_lines(value: str, chomp: str) -> list[str]:
    """Content lines (without indentation) of a block scalar holding `value`."""
    body = value.rstrip("\n")
    trailing = len(value) - len(body)
    if not body:
        return [""] * trailing
    lines = body.split("\n")
    if chomp == "+" and trailing > 1:
        lines.extend([""] * (trailing - 1))
    return lines


def needs_indent_indicator(value: str) -> bool:
    """A literal block needs an explicit indentation indicator when its first non-blank line
    starts with a space, or when a spaces-only line comes before it: YAML takes the indentation
    from the first non-blank line and rejects a leading line indented further than that."""
    for line in value.split("\n"):
        if line.strip(" ") != "":
            return line.startswith(" ")
        if line:
            return True
    return False


def indent_lines(lines: list[str], column: int) -> list[str]:
    return [(" " * column + line) if line else "" for line in lines]


def render_literal(
    value: str, column: int, step: int, old_chomp: str = ""
) -> tuple[str, list[str]]:
    """Header and indented content lines of a literal block for `value` (research B-8)."""
    chomp = chomping_for(value, old_chomp)
    digit = str(step) if needs_indent_indicator(value) else ""
    return LITERAL + digit + chomp, indent_lines(block_content_lines(value, chomp), column)


# --- New collections -----------------------------------------------------------------------


def render_flow(node: NewNode, preferred: str | None = PLAIN) -> str:
    """Flow-style spelling (research B-6); multi-line strings become double-quoted."""
    if isinstance(node, NewScalar):
        return render_inline(node, preferred, in_flow=True)
    if isinstance(node, list):
        return "[" + ", ".join(render_flow(item) for item in node) + "]"
    return (
        "{"
        + ", ".join(
            f"{render_key(key, PLAIN, True)}: {render_flow(item)}" for key, item in node.items()
        )
        + "}"
    )


def render_key(key: str, preferred: str | None, in_flow: bool) -> str:
    return render_inline(NewScalar(key), preferred, in_flow)


def is_empty_collection(node: NewNode) -> bool:
    return isinstance(node, (list, dict)) and not node


def render_value_lines(
    node: NewNode, column: int, step: int, preferred: str | None = PLAIN
) -> tuple[str, list[str]]:
    """How a value follows its `key:` or `-` in block context.

    Returns the text to put on the same line (after one space, or "" for none) and the lines that
    follow, already indented. Collections are written in block style at `column`.
    """
    if isinstance(node, NewScalar):
        value = node.value
        if is_multiline(value) and isinstance(value, str) and literal_representable(value):
            header, lines = render_literal(value, column, step)
            return tagged(node, header), lines
        return render_inline(node, preferred, in_flow=False), []
    if is_empty_collection(node):
        return render_flow(node), []
    return "", render_block(node, column, step)


def render_block(node: NewNode, column: int, step: int) -> list[str]:
    """Block-style lines for a non-empty collection whose entries start at `column`."""
    pad = " " * column
    lines: list[str] = []
    if isinstance(node, dict):
        for key, item in node.items():
            inline, following = render_value_lines(item, column + step, step)
            head = f"{pad}{render_key(key, PLAIN, False)}:"
            lines.append(f"{head} {inline}" if inline else head)
            lines.extend(following)
    elif isinstance(node, list):
        for item in node:
            lines.extend(render_list_item(item, column, step))
    return lines


def render_list_item(
    item: NewNode, column: int, step: int, preferred: str | None = PLAIN
) -> list[str]:
    """Lines for one block-list item at `column`; collections use the compact form (`- k: v`)."""
    pad = " " * column
    if isinstance(item, (list, dict)) and item:
        nested = render_block(item, column + 2, step)
        return [pad + "- " + nested[0][column + 2 :], *nested[1:]]
    inline, following = render_value_lines(item, column + step, step, preferred)
    return [f"{pad}- {inline}" if inline else f"{pad}-", *following]
