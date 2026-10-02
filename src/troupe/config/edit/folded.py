"""Rewriting the content of a folded (`>`) block scalar (FR-032, research R-12).

Paragraphs whose text is unchanged keep their bytes; a changed paragraph is re-wrapped greedily
by word at the width of its old counterpart's longest content line; a paragraph with no
counterpart uses the width of the block's longest old content line.
"""

import difflib
from dataclasses import dataclass, field


class MoreIndented(Exception):
    """The new value would need a more-indented line, which a folded block cannot fold."""


@dataclass
class Paragraph:
    lines: list[str]  # original lines, indentation included, no line endings
    text: str


@dataclass
class OldBlock:
    leading: list[str] = field(default_factory=list)  # blank lines before the first paragraph
    paragraphs: list[Paragraph] = field(default_factory=list)
    separators: list[list[str]] = field(default_factory=list)  # blank lines between paragraphs


def parse_old(lines: list[str], column: int) -> OldBlock:
    """Split a folded block's content lines (trailing blank lines excluded) into paragraphs."""
    block = OldBlock()
    blanks: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.strip(" ") == "":
            if current:
                block.paragraphs.append(_paragraph(current, column))
                current = []
            blanks.append(line)
            continue
        if len(line) - len(line.lstrip(" ")) > column or line[column : column + 1] == "\t":
            raise MoreIndented
        if not current:
            if block.paragraphs:
                block.separators.append(blanks)
            else:
                block.leading = blanks
            blanks = []
        current.append(line)
    if current:
        block.paragraphs.append(_paragraph(current, column))
    return block


def _paragraph(lines: list[str], column: int) -> Paragraph:
    return Paragraph(lines, " ".join(line[column:] for line in lines))


def _width(paragraph: Paragraph, column: int) -> int:
    return max(len(line) - column for line in paragraph.lines)


def wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap on single spaces; a word wider than `width` takes a line of its own."""
    words = text.split(" ")
    lines = [words[0]]
    for word in words[1:]:
        if len(lines[-1]) + 1 + len(word) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    for line in lines:
        if line == "" or line[0] in " \t":
            raise MoreIndented
    return lines


def split_new(body: str) -> tuple[int, list[str], list[int]]:
    """Leading blank-line count, paragraph texts, and blank-line counts between paragraphs."""
    segments = body.split("\n")
    leading = 0
    while leading < len(segments) - 1 and segments[leading] == "":
        leading += 1
    paragraphs: list[str] = []
    gaps: list[int] = []
    blank = 0
    for segment in segments[leading:]:
        if segment == "":
            blank += 1
            continue
        if paragraphs:
            gaps.append(blank + 1)
        paragraphs.append(segment)
        blank = 0
    return leading, paragraphs, gaps


def rewrite(old_lines: list[str], column: int, body: str) -> list[str]:
    """New content lines (indented, no line endings) for a folded block whose value's text,
    without trailing newlines, is `body`. Raises MoreIndented when that cannot be written."""
    old = parse_old(old_lines, column)
    leading, texts, gaps = split_new(body)
    if any(text[0] in " \t" for text in texts):
        raise MoreIndented
    block_width = max((_width(p, column) for p in old.paragraphs), default=0)
    old_texts = [p.text for p in old.paragraphs]
    matcher = difflib.SequenceMatcher(None, old_texts, texts, autojunk=False)
    produced: list[tuple[list[str], int | None]] = []  # (lines, index of old paragraph kept)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            produced.extend((old.paragraphs[i].lines, i) for i in range(i1, i2))
            continue
        for k, j in enumerate(range(j1, j2)):
            width = _width(old.paragraphs[i1 + k], column) if i1 + k < i2 else block_width
            pad = " " * column
            produced.append(([pad + line for line in wrap(texts[j], width)], None))
    pad_blank = [""]
    result = old.leading if leading == len(old.leading) else pad_blank * leading
    result = list(result)
    for position, (lines, origin) in enumerate(produced):
        if position:
            gap = gaps[position - 1]
            previous = produced[position - 1][1]
            if (
                origin is not None
                and previous is not None
                and origin == previous + 1
                and len(old.separators[previous]) == gap
            ):
                result.extend(old.separators[previous])
            else:
                result.extend(pad_blank * gap)
        result.extend(lines)
    return result
