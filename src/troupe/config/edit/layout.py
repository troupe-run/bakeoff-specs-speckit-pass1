"""Line geometry of a file's text: lines, columns, comments, indentation, insertion points.

Columns count Unicode code points (offsets into the decoded text), as the contract requires.
"""

import bisect
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode

COMMENT = "#"
DEFAULT_INDENT_STEP = 2


@dataclass(frozen=True)
class Line:
    start: int  # offset of the first character
    end: int  # offset just past the content, before the line ending
    next: int  # offset of the next line (just past the line ending)

    @property
    def eol(self) -> bool:
        return self.next > self.end


class Lines:
    def __init__(self, text: str) -> None:
        self.text = text
        self.lines: list[Line] = []
        start = 0
        while start < len(text):
            newline = text.find("\n", start)
            if newline < 0:
                self.lines.append(Line(start, len(text), len(text)))
                break
            end = newline - 1 if newline > start and text[newline - 1] == "\r" else newline
            self.lines.append(Line(start, end, newline + 1))
            start = newline + 1
        self._starts = [line.start for line in self.lines]

    def __len__(self) -> int:
        return len(self.lines)

    def __getitem__(self, index: int) -> Line:
        return self.lines[index]

    def index_of(self, offset: int) -> int:
        """Index of the line containing `offset` (the very end maps to the last line)."""
        return max(0, bisect.bisect_right(self._starts, offset) - 1)

    def content(self, index: int) -> str:
        line = self.lines[index]
        return self.text[line.start : line.end]

    def column(self, offset: int) -> int:
        return offset - self.lines[self.index_of(offset)].start

    def last_line_of(self, end: int) -> int:
        """Index of the line holding the character just before `end` (the last content line)."""
        return self.index_of(max(0, end - 1))


def indent_of(content: str) -> int:
    return len(content) - len(content.lstrip(" "))


def is_blank(content: str) -> bool:
    return content.strip(" \t") == ""


def is_comment(content: str) -> bool:
    return content.lstrip(" \t").startswith(COMMENT)


def scalar_spans(root: Any) -> list[tuple[int, int]]:
    """Spans of every scalar (keys included) in a composed file, sorted by start."""
    spans: list[tuple[int, int]] = []
    stack = [root] if root is not None else []
    while stack:
        node = stack.pop()
        if isinstance(node, ScalarNode):
            spans.append((node.start_mark.index, node.end_mark.index))
        elif isinstance(node, SequenceNode):
            stack.extend(node.value)
        elif isinstance(node, MappingNode):
            for key, value in node.value:
                stack.extend((key, value))
    spans.sort()
    return spans


def _inside(offset: int, spans: Iterable[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in spans)


def find_comment(lines: Lines, index: int, after: int, spans: list[tuple[int, int]]) -> int | None:
    """Offset of the end-of-line comment on line `index` at or after `after`, if any."""
    line = lines[index]
    text = lines.text
    for offset in range(max(after, line.start), line.end):
        if text[offset] != COMMENT:
            continue
        if offset > line.start and text[offset - 1] not in " \t":
            continue
        if not _inside(offset, spans):
            return offset
    return None


def inline_replace(
    lines: Lines, start: int, end: int, replacement: str, spans: list[tuple[int, int]]
) -> tuple[int, int, str]:
    """Splice replacing text[start:end] while keeping the line's end-of-line comment in place.

    FR-036: when the value's length changes, the comment returns to its previous column; if the
    new text reaches that column, exactly one space separates them. Nothing else changes.
    """
    text = lines.text
    if len(lines) == 0:
        return start, end, replacement
    index = lines.index_of(end)
    if end > lines[index].end:
        return start, end, replacement
    comment = find_comment(lines, index, end, spans)
    if comment is None:
        return start, end, replacement
    gap_start = comment
    while gap_start > end and text[gap_start - 1] in " \t":
        gap_start -= 1
    column = lines.column(comment)
    prefix = text[lines[lines.index_of(start)].start : start] + replacement + text[end:gap_start]
    reached = len(prefix.rsplit("\n", 1)[-1])
    padding = max(1, column - reached)
    return start, comment, replacement + text[end:gap_start] + " " * padding


def last_content_line(lines: Lines, end: int) -> int:
    """The last non-blank line at or before the line holding the character before `end`."""
    index = lines.last_line_of(end)
    while index > 0 and is_blank(lines.content(index)):
        index -= 1
    return index


def insertion_line(lines: Lines, last_entry_line: int, entry_column: int) -> int:
    """Index of the line after which a new entry of a block collection goes (FR-033).

    After the collection's last entry and below any comment lines that follow it, stopping at the
    next less-indented line; a comment indented less than the entries ends the collection. Blank
    lines directly above the stopping line stay below the new entry.
    """
    chosen = last_entry_line
    for index in range(last_entry_line + 1, len(lines)):
        content = lines.content(index)
        if is_blank(content):
            continue
        if is_comment(content) and indent_of(content) >= entry_column:
            chosen = index
            continue
        break
    return chosen


def indent_step(root: Any, lines: Lines) -> int:
    """The file's indentation step: smallest positive nesting indent in it (research R-10)."""
    steps: list[int] = []
    stack = [root] if root is not None else []
    while stack:
        node = stack.pop()
        if isinstance(node, MappingNode):
            for key, value in node.value:
                start, key_start = value.start_mark.index, key.start_mark.index
                nested = isinstance(value, (MappingNode, SequenceNode)) and not value.flow_style
                if nested and lines.index_of(start) != lines.index_of(key_start):
                    delta = lines.column(start) - lines.column(key_start)
                    if delta > 0:
                        steps.append(delta)
                stack.append(value)
        elif isinstance(node, SequenceNode):
            stack.extend(node.value)
    return min(steps) if steps else DEFAULT_INDENT_STEP
