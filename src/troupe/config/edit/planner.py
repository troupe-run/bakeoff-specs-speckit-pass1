"""Where a `set` is written and which bytes change (FR-020 to FR-036).

The planner turns `set PATH VALUE` into text splices on the one file that holds the value. It
never writes; `apply.py` verifies the result and writes it.
"""

from dataclasses import dataclass, field

from troupe.config.edit import folded, render
from troupe.config.edit.layout import (
    Lines,
    indent_of,
    indent_step,
    inline_replace,
    insertion_line,
    is_blank,
    last_content_line,
    scalar_spans,
)
from troupe.config.files import CRLF, LF, SourceFile
from troupe.config.loader import Loaded
from troupe.config.paths import ConfigPath, is_index
from troupe.config.scalars import NewNode, NewScalar, Value, plain_value, scalars_equal
from troupe.config.tree import (
    Located,
    LocatedMapping,
    LocatedScalar,
    LocatedSequence,
    TextInclude,
    is_alias,
    written_as,
)
from troupe.errors import PathError, WriteRefused

type Splice = tuple[int, int, str]


@dataclass
class EditPlan:
    """A change to one file. `anchor` is the deepest existing node the change is made at, reached
    by `anchor_path`; the changed value sits at `anchor_path` + `rest`."""

    file: SourceFile
    new_text: str
    anchor: Located
    anchor_path: ConfigPath | None
    rest: tuple[str, ...]
    expected: Value
    # Override writes are expected only where their include reference is, not wherever the
    # included file appears (research O-6).
    by_site: bool = False
    # The configuration the plan was made on, when not the one on disk: `--expand-alias` plans
    # the set on the expanded text (step 6).
    basis: Loaded | None = None


@dataclass
class _Owner:
    """What holds the target: a mapping entry (with its key) or a list item."""

    container: LocatedMapping | LocatedSequence
    key: LocatedScalar | None = None


MERGE_KEY = "<<"


def plan_set(
    loaded: Loaded,
    path: ConfigPath,
    value: NewNode,
    *,
    in_include: bool = False,
    expand_alias: bool = False,
) -> EditPlan | None:
    """Plan `set PATH VALUE`; None when the value is already what was asked (nothing to do)."""
    from troupe.config.edit.alias import through_alias
    from troupe.config.edit.override import Walk, place_new_key

    if MERGE_KEY in path.segments:
        raise WriteRefused(f"{path}: troupe never writes a merge key ({MERGE_KEY})")
    node: Located = loaded.root
    owner: _Owner | None = None
    walk = Walk()
    for depth, segment in enumerate(path.segments):
        here = ConfigPath(path.segments[: depth + 1])
        prefix = ConfigPath(path.segments[:depth]) if depth else None
        if isinstance(node, LocatedMapping):
            if is_index(segment):
                raise PathError(f"{here}: {segment!r} is a list index but its parent is a mapping")
            child = node.get(segment)
            if child is None:
                # Where a new key goes (spec FR-420 to FR-424): override.py decides.
                rest = path.segments[depth:]
                return place_new_key(
                    loaded, node, prefix, rest, value, path, walk, in_include=in_include
                )
            key = next(k for k, v in node.entries if v is child)
            owner = _Owner(node, key)
            node = child
        elif isinstance(node, LocatedSequence):
            if not is_index(segment):
                raise PathError(f"{here}: its parent is a list; {segment!r} is not an index")
            index = int(segment)
            if index == len(node.items) and depth == len(path.segments) - 1:
                return _append(loaded, node, prefix, value, path)
            if index >= len(node.items):
                raise PathError(f"{here}: index out of range (list has {len(node.items)} items)")
            owner = _Owner(node)
            node = node.items[index]
            walk.enter_item()
        else:
            raise PathError(f"{here}: its parent is a scalar, not a mapping or list")
        walk.enter(node, here)
        if is_alias(node) and depth < len(path.segments) - 1:
            # Below an alias is the anchored node, shared by every alias (step 6).
            return through_alias(
                loaded, node, owner, path, value, in_include=in_include, expand=expand_alias
            )
    assert owner is not None
    return _replace(loaded, node, owner, value, path)


# --- Shared context ------------------------------------------------------------------------


@dataclass
class _Context:
    path: ConfigPath
    file: SourceFile
    lines: Lines
    spans: list[tuple[int, int]]
    step: int
    splices: list[Splice] = field(default_factory=list)

    @property
    def text(self) -> str:
        return self.file.text

    @property
    def eol(self) -> str:
        return CRLF if self.file.newline == CRLF else LF

    def result(self) -> str:
        text = self.text
        for start, end, replacement in sorted(
            self.splices, key=lambda s: (s[0], s[1]), reverse=True
        ):
            text = text[:start] + replacement + text[end:]
        return text

    def inline(self, start: int, end: int, replacement: str) -> None:
        self.splices.append(inline_replace(self.lines, start, end, replacement, self.spans))

    def insert_after_line(self, index: int, new_lines: list[str]) -> None:
        """Insert whole lines after line `index` (or at the start of an empty file if -1)."""
        if not new_lines:
            return
        if index < 0:
            self.splices.append((0, 0, "".join(line + self.eol for line in new_lines)))
            return
        line = self.lines[index]
        if line.eol:
            self.splices.append((line.next, line.next, "".join(x + self.eol for x in new_lines)))
        else:
            self.splices.append((line.next, line.next, "".join(self.eol + x for x in new_lines)))

    def replace_lines(self, first: int, last: int, new_lines: list[str]) -> None:
        """Replace whole lines first..last (inclusive) with `new_lines`."""
        start = self.lines[first].start
        end_line = self.lines[last]
        if end_line.eol:
            text = "".join(line + self.eol for line in new_lines)
            self.splices.append((start, end_line.next, text))
        else:
            # Last line of a file without a final newline: keep it that way.
            text = self.eol.join(new_lines)
            end = end_line.end
            if not new_lines and first > 0:
                start = self.lines[first - 1].end
            self.splices.append((start, end, text))


def _context(loaded: Loaded, file: SourceFile, path: ConfigPath) -> _Context:
    lines = Lines(file.text)
    root = loaded.composed.get(file.path)
    return _Context(path, file, lines, scalar_spans(root), indent_step(root, lines))


# --- Block scalar geometry -----------------------------------------------------------------


@dataclass
class _BlockScalar:
    header_start: int
    header_end: int
    indicator: str  # "|" or ">"
    digit: str
    chomp: str  # "", "-" or "+"
    header_line: int
    content_column: int
    first: int  # first content line index (header_line + 1)
    last_text: int  # last non-blank content line index, or header_line if none
    last_block: int  # last line of the block including trailing blank lines


def _block_scalar(ctx: _Context, scalar: LocatedScalar, owner_column: int) -> _BlockScalar:
    text = ctx.text
    start = scalar.start
    end = start
    while end < len(text) and text[end] not in " \t\r\n#":
        end += 1
    header = text[start:end]
    indicator = header[0]
    digit = "".join(char for char in header if char.isdigit())
    chomp = "-" if "-" in header else "+" if "+" in header else ""
    header_line = ctx.lines.index_of(start)
    column = owner_column + int(digit) if digit else -1
    last_text = header_line
    last_block = header_line
    for index in range(header_line + 1, len(ctx.lines)):
        content = ctx.lines.content(index)
        if is_blank(content):
            last_block = index
            continue
        if column < 0:
            if indent_of(content) <= owner_column:
                break
            column = indent_of(content)
        if indent_of(content) < column:
            break
        last_text = last_block = index
    if column < 0:
        column = owner_column + ctx.step
    # Trailing blank lines belong to the block only up to the next content line.
    return _BlockScalar(
        start,
        end,
        indicator,
        digit,
        chomp,
        header_line,
        column,
        header_line + 1,
        last_text,
        last_block,
    )


def _owner_column(ctx: _Context, owner: _Owner) -> int:
    if owner.key is not None:
        return ctx.lines.column(owner.key.start)
    container = owner.container
    if not container.flow and isinstance(container, LocatedSequence):
        return ctx.lines.column(container.start)
    return 0


def _after_indicator(ctx: _Context, owner: _Owner, target_start: int) -> int:
    """Offset just after the `:` of the owning key, or after the `-` of the owning list item."""
    text = ctx.text
    if owner.key is not None:
        offset = owner.key.end
        while offset < len(text) and text[offset] in " \t":
            offset += 1
        if offset < len(text) and text[offset] == ":":
            return offset + 1
        key = owner.key.node.value
        raise WriteRefused(f"{ctx.path}: cannot locate the ':' after {key!r} in {ctx.file.path}")
    offset = target_start - 1
    while offset >= 0 and text[offset] in " \t\r\n":
        offset -= 1
    if offset >= 0 and text[offset] == "-":
        return offset + 1
    raise WriteRefused(
        f"{ctx.path}: cannot locate the list item in {ctx.file.path} at offset {target_start}"
    )


def content_end(ctx: _Context, node: Located) -> int:
    """Offset just past the last character of `node` as written in the file that holds it."""
    written = written_as(node)
    if written is not None:
        return content_end(ctx, written)
    if isinstance(node, TextInclude):
        return node.include.end
    if isinstance(node, LocatedScalar):
        if node.style in (render.LITERAL, render.FOLDED):
            block = _block_scalar(ctx, node, _column_before(ctx, node.start))
            return ctx.lines[block.last_text].end
        return node.end
    if node.flow or (isinstance(node, LocatedMapping) and not node.entries):
        return node.end
    if isinstance(node, LocatedMapping):
        return content_end(ctx, node.entries[-1][1]) if node.entries else node.end
    return content_end(ctx, node.items[-1]) if node.items else node.end


def _last_line(ctx: _Context, node: Located) -> int:
    """Index of the last line `node` occupies in its file.

    Trailing blank lines are not part of an entry, except after a keep-chomped (`+`) block
    scalar, whose trailing blank lines belong to its value (research B-15).
    """
    tail = node
    while True:
        written = written_as(tail)
        if written is not None:
            # An include ends where its reference does in this file (research O-2).
            tail = written
        elif isinstance(tail, LocatedMapping) and tail.entries and not tail.flow:
            tail = tail.entries[-1][1]
        elif isinstance(tail, LocatedSequence) and tail.items and not tail.flow:
            tail = tail.items[-1]
        else:
            break
    if isinstance(tail, LocatedScalar) and tail.style in (render.LITERAL, render.FOLDED):
        block = _block_scalar(ctx, tail, _column_before(ctx, tail.start))
        if block.chomp == "+":
            return block.last_block
    return last_content_line(ctx.lines, content_end(ctx, node))


def _column_before(ctx: _Context, offset: int) -> int:
    """Indentation of the line holding `offset` (an approximation of a block scalar's parent)."""
    return indent_of(ctx.lines.content(ctx.lines.index_of(offset)))


def _style_of(node: Located | None) -> str | None:
    """The quoting style a new sibling copies (FR-027); plain when there is nothing to copy."""
    if node is None:
        return render.PLAIN
    written = written_as(node)
    if written is not None:
        node = written
    if isinstance(node, TextInclude):
        node = node.include
    if isinstance(node, LocatedScalar) and node.style in render.INLINE_STYLES:
        return node.style
    return render.PLAIN


# --- Replacing an existing value -----------------------------------------------------------


def _replace(
    loaded: Loaded, target: Located, owner: _Owner, value: NewNode, path: ConfigPath
) -> EditPlan | None:
    if (
        isinstance(target, LocatedMapping)
        and target.overrides is not None
        and target.included_by is None
    ):
        target = _override_to_replace(target, path)
    if target.included_by is not None:
        raise WriteRefused(
            f"{path}: its whole value comes from include {target.included_by.value!r} "
            f"in {target.included_by.file.path}; change the included file instead"
        )
    expected = plain_value(value)
    anchor_path = path
    if isinstance(target, TextInclude):
        return _replace_text_include(target, value, path, expected)
    if _same(target, expected):
        return None
    ctx = _context(loaded, target.file, path)
    if is_alias(target):
        # The alias itself is replaced: only its `*name` changes, the anchor stays (step 6).
        _replace_alias(ctx, target, owner, value)
    elif isinstance(target, LocatedScalar):
        _replace_scalar(ctx, target, owner, value)
    else:
        _replace_collection(ctx, target, owner, value)
    return EditPlan(ctx.file, ctx.result(), target, anchor_path, (), expected)


def _override_to_replace(target: LocatedMapping, path: ConfigPath) -> LocatedMapping:
    """A merged mapping can be replaced only through its override, and only when the included
    file contributes no key: an override cannot remove included keys (spec FR-432, D-44)."""
    assert target.base is not None and target.overrides is not None
    overridden = {str(key.value) for key, _ in target.overrides.entries}
    included = [
        str(key.value) for key, _ in target.base.entries if str(key.value) not in overridden
    ]
    if included:
        raise WriteRefused(
            f"{path}: {', '.join(included)} come from {target.base.file.path}; an override "
            f"in {target.overrides.file.path} cannot remove included keys"
        )
    return target.overrides


def _same(target: Located, expected: Value) -> bool:
    from troupe.config.leaves import to_value

    return scalars_equal(to_value(target), expected)


def _replace_text_include(
    target: TextInclude, value: NewNode, path: ConfigPath, expected: Value
) -> EditPlan | None:
    if not isinstance(value, NewScalar) or not isinstance(value.value, str):
        raise WriteRefused(
            f"{path}: is a text include of {target.target.path}; its value must be a string"
        )
    text = value.value
    if target.target.newline == CRLF:
        text = text.replace(CRLF, LF).replace(LF, CRLF)
    if text == target.target.text:
        return None
    return EditPlan(target.target, text, target, path, (), text)


def _replace_alias(
    ctx: _Context,
    target: LocatedScalar | LocatedMapping | LocatedSequence,
    owner: _Owner,
    value: NewNode,
) -> None:
    if target.in_flow:
        ctx.inline(target.start, target.end, _flow_text(value, None))
        return
    line = ctx.lines.index_of(target.end)
    _write_value(ctx, owner, _owner_column(ctx, owner), target.start, target.end, line, "", value)


def _after_properties(ctx: _Context, offset: int) -> int:
    """`offset` (just after a `:` or `-`), moved past an `&anchor` that follows it on its line."""
    text = ctx.text
    probe = offset
    while probe < len(text) and text[probe] in " \t":
        probe += 1
    if not text.startswith("&", probe):
        return offset
    while probe < len(text) and text[probe] not in " \t\r\n":
        probe += 1
    return probe


def _replace_scalar(ctx: _Context, target: LocatedScalar, owner: _Owner, value: NewNode) -> None:
    owner_column = _owner_column(ctx, owner)
    if target.in_flow:
        ctx.inline(target.start, target.end, _flow_text(value, target.style))
        return
    if target.style in (render.LITERAL, render.FOLDED):
        _replace_block_scalar(ctx, target, owner, owner_column, value)
        return
    empty = target.style is None and target.node.value == ""
    # An empty value's end mark points at the next token; its real span is just after the
    # `:` or `-` (and the anchor, if any).
    start = (
        _after_properties(ctx, _after_indicator(ctx, owner, target.start))
        if empty
        else target.start
    )
    end = start if empty else target.end
    lead = " " if empty else ""
    line = ctx.lines.index_of(end)
    _write_value(ctx, owner, owner_column, start, end, line, lead, value, target.style)


def _write_value(
    ctx: _Context,
    owner: _Owner,
    owner_column: int,
    start: int,
    end: int,
    line: int,
    lead: str,
    value: NewNode,
    style: str | None = None,
) -> None:
    """Write `value` over the inline text start..end in block context."""
    if isinstance(value, NewScalar):
        text_value = value.value
        if (
            render.is_multiline(text_value)
            and isinstance(text_value, str)
            and render.literal_representable(text_value)
        ):
            header, lines = render.render_literal(text_value, owner_column + ctx.step, ctx.step)
            ctx.inline(start, end, lead + header)
            ctx.insert_after_line(line, lines)
            return
        ctx.inline(start, end, lead + render.render_inline(value, style, in_flow=False))
        return
    if render.is_empty_collection(value):
        ctx.inline(start, end, lead + render.render_flow(value))
        return
    _scalar_to_block_collection(ctx, owner, owner_column, start, end, line, value)


def _scalar_to_block_collection(
    ctx: _Context, owner: _Owner, owner_column: int, start: int, end: int, line: int, value: NewNode
) -> None:
    """FR-035 / research B-3: the key's line keeps its bytes up to its end-of-line comment."""
    if owner.key is not None:
        after_colon = _after_properties(ctx, _after_indicator(ctx, owner, start))
        ctx.inline(after_colon, end, "")
        ctx.insert_after_line(line, render.render_block(value, owner_column + ctx.step, ctx.step))
        return
    first, *following = render.render_list_item(value, owner_column, ctx.step)
    after_dash = _after_indicator(ctx, owner, start)
    ctx.inline(after_dash, end, " " + first[owner_column + 2 :])
    ctx.insert_after_line(line, following)


def _replace_block_scalar(
    ctx: _Context, target: LocatedScalar, owner: _Owner, owner_column: int, value: NewNode
) -> None:
    block = _block_scalar(ctx, target, owner_column)
    text_value = value.value if isinstance(value, NewScalar) else None
    if isinstance(text_value, str) and render.literal_representable(text_value):
        chomp = render.chomping_for(text_value, block.chomp)
        if block.indicator == render.FOLDED:
            old_lines = [ctx.lines.content(i) for i in range(block.first, block.last_text + 1)]
            try:
                body = folded.rewrite(old_lines, block.content_column, text_value.rstrip("\n"))
            except folded.MoreIndented:
                raise WriteRefused(
                    f"{ctx.path}: the new value would put a more-indented line into the "
                    f"folded value at line {block.header_line + 1} of {ctx.file.path}"
                ) from None
            trailing = len(text_value) - len(text_value.rstrip("\n"))
            new_lines = body + ([""] * (trailing - 1) if chomp == "+" and trailing > 1 else [])
        else:
            new_lines = render.indent_lines(
                render.block_content_lines(text_value, chomp), block.content_column
            )
        digit = block.digit
        if (
            not digit
            and render.needs_indent_indicator(text_value)
            and block.indicator == render.LITERAL
        ):
            digit = str(block.content_column - owner_column)
        header = block.indicator + digit + chomp
        if header != ctx.text[block.header_start : block.header_end]:
            ctx.inline(block.header_start, block.header_end, header)
        last = block.last_block if "+" in (block.chomp, chomp) else block.last_text
        _replace_content(ctx, block, last, new_lines)
        return
    # The value is no longer a block scalar: write it inline and drop the old content lines.
    _replace_content(ctx, block, block.last_text, [])
    if isinstance(value, NewScalar):
        ctx.inline(
            block.header_start, block.header_end, render.render_inline(value, None, in_flow=False)
        )
    elif render.is_empty_collection(value):
        ctx.inline(block.header_start, block.header_end, render.render_flow(value))
    elif owner.key is not None:
        after_colon = _after_properties(ctx, _after_indicator(ctx, owner, target.start))
        ctx.inline(after_colon, block.header_end, "")
        ctx.insert_after_line(
            block.header_line, render.render_block(value, owner_column + ctx.step, ctx.step)
        )
    else:
        first, *following = render.render_list_item(value, owner_column, ctx.step)
        ctx.inline(block.header_start, block.header_end, first[owner_column + 2 :])
        ctx.insert_after_line(block.header_line, following)


def _replace_content(ctx: _Context, block: _BlockScalar, last: int, new_lines: list[str]) -> None:
    if last >= block.first:
        old = [ctx.lines.content(i) for i in range(block.first, last + 1)]
        if old != new_lines:
            ctx.replace_lines(block.first, last, new_lines)
    else:
        ctx.insert_after_line(block.header_line, new_lines)


def _flow_text(value: NewNode, preferred: str | None) -> str:
    return render.render_flow(value, preferred)


def _replace_collection(
    ctx: _Context, target: LocatedMapping | LocatedSequence, owner: _Owner, value: NewNode
) -> None:
    owner_column = _owner_column(ctx, owner)
    if target.flow:
        if isinstance(value, NewScalar) and not target.in_flow:
            text_value = value.value
            if (
                render.is_multiline(text_value)
                and isinstance(text_value, str)
                and render.literal_representable(text_value)
            ):
                header, lines = render.render_literal(text_value, owner_column + ctx.step, ctx.step)
                ctx.inline(target.start, target.end, header)
                ctx.insert_after_line(ctx.lines.index_of(target.end), lines)
                return
            ctx.inline(target.start, target.end, render.render_inline(value, None, in_flow=False))
            return
        ctx.inline(target.start, target.end, render.render_flow(value))
        return
    # Block collection (research B-4 / B-5).
    first_line = ctx.lines.index_of(target.start)
    last_line = _last_line(ctx, target)
    line_start = ctx.lines[first_line].start
    compact = ctx.text[line_start : target.start].strip(" ") != ""
    column = ctx.lines.column(target.start)
    if isinstance(value, (list, dict)) and value:
        new_lines = render.render_block(value, column, ctx.step)
        if compact:
            joined = ctx.eol.join([new_lines[0][column:], *new_lines[1:]])
            ctx.splices.append((target.start, ctx.lines[last_line].end, joined))
        else:
            ctx.replace_lines(first_line, last_line, new_lines)
        return
    if isinstance(value, NewScalar):
        text_value = value.value
        if (
            render.is_multiline(text_value)
            and isinstance(text_value, str)
            and render.literal_representable(text_value)
        ):
            header, lines = render.render_literal(text_value, owner_column + ctx.step, ctx.step)
        else:
            header, lines = render.render_inline(value, None, in_flow=False), []
    else:
        header, lines = render.render_flow(value), []
    if compact:
        joined = ctx.eol.join([header, *lines])
        ctx.splices.append((target.start, ctx.lines[last_line].end, joined))
        return
    after = _after_properties(ctx, _after_indicator(ctx, owner, target.start))
    ctx.inline(after, after, " " + header)
    ctx.replace_lines(first_line, last_line, lines)


# --- Adding a new key ----------------------------------------------------------------------


def _new_key(
    loaded: Loaded,
    mapping: LocatedMapping,
    mapping_path: ConfigPath | None,
    rest: tuple[str, ...],
    value: NewNode,
    path: ConfigPath,
) -> EditPlan:
    """FR-022: write into the file holding the deepest existing mapping, creating the missing
    intermediate mappings there."""
    for depth, segment in enumerate(rest[1:], start=len(path.segments) - len(rest) + 1):
        if is_index(segment):
            raise PathError(f"{ConfigPath(path.segments[: depth + 1])}: path not found")
    nested: NewNode = value
    for segment in reversed(rest[1:]):
        nested = {segment: nested}
    ctx = _context(loaded, mapping.file, path)
    last_key = mapping.entries[-1][0] if mapping.entries else None
    last_value = mapping.entries[-1][1] if mapping.entries else None
    key_style = (
        last_key.style
        if last_key is not None and last_key.style in render.INLINE_STYLES
        else render.PLAIN
    )
    value_style = _style_of(last_value)
    if mapping.flow:
        key_text = render.render_key(rest[0], key_style, in_flow=True)
        entry = f"{key_text}: {render.render_flow(nested, value_style)}"
        if last_value is not None:
            end = content_end(ctx, last_value)
            ctx.inline(end, end, ", " + entry)
        else:
            ctx.inline(mapping.start + 1, mapping.start + 1, entry)
    else:
        key_text = render.render_key(rest[0], key_style, in_flow=False)
        if last_key is None:
            column = 0
            after = _last_line_index(ctx)
        else:
            column = ctx.lines.column(last_key.start)
            assert last_value is not None
            last = _last_line(ctx, last_value)
            after = insertion_line(ctx.lines, last, column)
        inline, following = render.render_value_lines(
            nested, column + ctx.step, ctx.step, value_style
        )
        head = " " * column + key_text + ":"
        ctx.insert_after_line(after, [f"{head} {inline}" if inline else head, *following])
    return EditPlan(ctx.file, ctx.result(), mapping, mapping_path, rest, plain_value(value))


def _last_line_index(ctx: _Context) -> int:
    return len(ctx.lines) - 1


# --- Appending to a list -------------------------------------------------------------------


def _append(
    loaded: Loaded,
    sequence: LocatedSequence,
    sequence_path: ConfigPath | None,
    value: NewNode,
    path: ConfigPath,
) -> EditPlan:
    """FR-023: PATH ending in the list's length appends to the list."""
    ctx = _context(loaded, sequence.file, path)
    last = sequence.items[-1] if sequence.items else None
    style = _style_of(last)
    if sequence.flow:
        text = render.render_flow(value, style)
        if last is not None:
            end = content_end(ctx, last)
            ctx.inline(end, end, ", " + text)
        else:
            ctx.inline(sequence.start + 1, sequence.start + 1, text)
    else:
        assert last is not None, "a block list always has an item"
        column = ctx.lines.column(sequence.start)
        last_line = _last_line(ctx, last)
        after = insertion_line(ctx.lines, last_line, column)
        ctx.insert_after_line(after, render.render_list_item(value, column, ctx.step, style))
    rest = (path.segments[-1],)
    return EditPlan(ctx.file, ctx.result(), sequence, sequence_path, rest, plain_value(value))
