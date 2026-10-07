"""`show`'s YAML view of the located tree (spec FR-210 to FR-234, D-21).

The view walks the tree the loader built, so every scalar still knows the file it was read from;
`--sources` appends that file to the scalar's line. Scalar spelling (quoting, literal blocks) is
`edit/render.py`'s; only the layout is decided here. It does not reuse `render_block`, which lays
out new values for `set` (research G-2).
"""

import os
from pathlib import Path

from troupe.config.edit.render import (
    PLAIN,
    literal_representable,
    render_inline,
    render_key,
    render_literal,
)
from troupe.config.files import SourceFile
from troupe.config.scalars import NewScalar
from troupe.config.tree import Located, LocatedMapping, LocatedScalar, LocatedSequence, TextInclude

STEP = 2  # indentation of `show`'s YAML (spec D-21)
SOURCE_COMMENT = " # from "  # one space before `#` (spec D-25)

type Line = tuple[str, SourceFile | None]
"""A line's text and the file of the scalar it holds; None when it holds no scalar."""


def source_label(theatre: Path, file: SourceFile) -> str:
    """`<file>` of `# from <file>`: relative to the theatre, `/` separators (spec FR-233).

    Loaded files are known by their real path, so the theatre is taken at its real path too
    (spec D-22): a theatre reached through a linked directory still gives `.troupe/...`.
    A fetched value is labelled with its URL as written (step 7 FR-604).
    """
    if isinstance(file.path, str):
        return file.path
    return os.path.relpath(file.path, theatre.resolve()).replace(os.sep, "/")


def _scalar(node: LocatedScalar | TextInclude, column: int) -> tuple[str, list[str], SourceFile]:
    """What follows `key: ` or `- ` (inline text or a literal header), the literal's content
    lines indented to `column`, and the file the value comes from."""
    if isinstance(node, TextInclude):
        # A literal block cannot hold CR; the text is shown as its lines (spec D-24).
        text = node.target.text.replace("\r\n", "\n")
        if literal_representable(text):
            header, lines = render_literal(text, column, STEP)
            return header, lines, node.target
        return render_inline(NewScalar(text), PLAIN, in_flow=False), [], node.target
    value = node.value
    if isinstance(value, str) and "\n" in value and literal_representable(value):
        header, lines = render_literal(value, column, STEP)
        return header, lines, node.file
    return render_inline(NewScalar(value), PLAIN, in_flow=False), [], node.file


def _is_empty(node: Located) -> bool:
    if isinstance(node, LocatedMapping):
        return not node.entries
    if isinstance(node, LocatedSequence):
        return not node.items
    return False


def _after(lead: str, node: Located, column: int) -> list[Line]:
    """Lines for `node` written after `lead` (`key:` or `-`) whose own entries go at `column`."""
    if isinstance(node, (LocatedScalar, TextInclude)):
        inline, content, source = _scalar(node, column)
        return [(f"{lead} {inline}", source), *((line, None) for line in content)]
    if _is_empty(node):
        return [(f"{lead} {{}}" if isinstance(node, LocatedMapping) else f"{lead} []", None)]
    return [(lead, None), *_collection(node, column)]


def _collection(node: LocatedMapping | LocatedSequence, column: int) -> list[Line]:
    pad = " " * column
    lines: list[Line] = []
    if isinstance(node, LocatedMapping):
        for key, value in node.entries:
            lead = f"{pad}{render_key(str(key.value), PLAIN, False)}:"
            lines.extend(_after(lead, value, column + STEP))
        return lines
    for item in node.items:
        if isinstance(item, (LocatedMapping, LocatedSequence)) and not _is_empty(item):
            # Compact form: the item's first entry shares the `- ` line (`- k: v`, `- - x`).
            nested = _collection(item, column + 2)
            (first, source), rest = nested[0], nested[1:]
            lines.append((f"{pad}- {first[column + 2 :]}", source))
            lines.extend(rest)
        else:
            lines.extend(_after(f"{pad}-", item, column + STEP))
    return lines


def _lines(node: Located) -> list[Line]:
    if isinstance(node, (LocatedScalar, TextInclude)):
        inline, content, source = _scalar(node, STEP)
        return [(inline, source), *((line, None) for line in content)]
    if _is_empty(node):
        return [("{}" if isinstance(node, LocatedMapping) else "[]", None)]
    return _collection(node, 0)


def render(node: Located, theatre: Path, *, sources: bool) -> str:
    """`node` as a YAML document; with `sources`, each scalar line names its file (FR-230)."""
    out = []
    for text, source in _lines(node):
        if sources and source is not None:
            text += SOURCE_COMMENT + source_label(theatre, source)
        out.append(text + "\n")
    return "".join(out)
