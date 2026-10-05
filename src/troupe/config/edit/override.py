"""Where a new key goes when includes are involved, and how a scalar-form include becomes mapping
form (spec FR-420 to FR-427, D-40, D-41, D-47, D-48; research O-4, O-5).

Included files are shared between projects (CR-A), so a new key whose deepest existing ancestor
comes from an included file is written as an override in the file holding the include reference.
`set --in-include` (step 5 CR-B) writes it into the included file instead. This module is the
one place that decides either.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from ruamel.yaml.nodes import MappingNode, Node, SequenceNode

from troupe.config.edit import render
from troupe.config.edit.planner import EditPlan, _context, _new_key
from troupe.config.loader import REF_KEY, Loaded
from troupe.config.paths import ConfigPath
from troupe.config.scalars import NewNode, plain_value
from troupe.config.tree import (
    Located,
    LocatedMapping,
    LocatedScalar,
    TextInclude,
    shared_part,
    written_as,
)
from troupe.errors import WriteRefused


@dataclass
class Walk:
    """What `plan_set`'s walk has seen on the way to the deepest existing node.

    `sites` maps each included file to the include root it was last entered through (and that
    root's path); entering a list item forgets them, since overrides cannot address list items
    (FR-424). `merged_root` is the last mapping-form include on the way, which anchors writes into
    its overrides.
    """

    sites: dict[Path, tuple[Located, ConfigPath]] = field(default_factory=dict)
    merged_root: tuple[LocatedMapping, ConfigPath] | None = None

    def enter_item(self) -> None:
        self.sites.clear()
        self.merged_root = None

    def enter(self, node: Located, path: ConfigPath) -> None:
        if isinstance(node, LocatedMapping) and node.include_site is not None:
            self.merged_root = (node, path)
        # A merged mapping stands for its base too: an include whose content an override merged
        # into is still the include through which the base's file is reached.
        current: Located | None = node
        while current is not None:
            if written_as(current) is not None:
                self.sites.setdefault(_target_file(current), (current, path))
            current = current.base if isinstance(current, LocatedMapping) else None


def _target_file(node: Located) -> Path:
    return node.target.path if isinstance(node, TextInclude) else node.file.path


def _innermost_override(mapping: LocatedMapping) -> LocatedMapping:
    assert mapping.overrides is not None
    inner = mapping.overrides
    while inner.overrides is not None:
        inner = inner.overrides
    return inner


def place_new_key(
    loaded: Loaded,
    ancestor: LocatedMapping,
    ancestor_path: ConfigPath | None,
    rest: tuple[str, ...],
    value: NewNode,
    path: ConfigPath,
    walk: Walk,
    *,
    in_include: bool = False,
) -> EditPlan:
    """Plan a new key below `ancestor`, the deepest existing mapping on PATH."""
    merged = ancestor.overrides is not None
    if in_include:
        # `set --in-include`: step 1's rule, into the file holding the ancestor; for a merged
        # mapping, its part in the included file (step 5 CR-B FR-461, FR-462, D-51).
        target = shared_part(ancestor) if merged else ancestor
        return _new_key(loaded, target, ancestor_path, rest, value, path)
    inner = _innermost_override(ancestor) if merged else ancestor
    if merged and written_as(inner) is not None:
        # The override at this position is itself an include (spec D-47).
        raise WriteRefused(
            f"{path}: the override for it in {inner.file.path} is an include, not a plain "
            "mapping; write the key by hand"
        )
    # A merged mapping comes from the file its override is written in (spec D-48).
    own = inner.file.path
    site = walk.sites.get(own)
    if own == loaded.root.file.path or site is None:
        if not merged:
            return _new_key(loaded, ancestor, ancestor_path, rest, value, path)
        assert walk.merged_root is not None
        plan = _new_key(loaded, inner, ancestor_path, rest, value, path)
        return _anchored(plan, *walk.merged_root, path)
    root, root_path = site
    tail = (*_segments(ancestor_path)[len(root_path.segments) :], *rest)
    if root.include_site is not None:
        plan = _into_mapping_form(loaded, root.include_site, tail, value, path)
    else:
        written = written_as(root)
        assert isinstance(written, LocatedScalar)
        plan = _convert(loaded, written, tail, value, path)
    return _anchored(plan, root, root_path, path)


def _segments(path: ConfigPath | None) -> tuple[str, ...]:
    return () if path is None else path.segments


def _anchored(plan: EditPlan, root: Located, root_path: ConfigPath, path: ConfigPath) -> EditPlan:
    """The plan anchored at the include root it overrides, identified by its reference, so the
    change is expected only where that reference is (research O-6)."""
    rest = path.segments[len(root_path.segments) :]
    return replace(plan, anchor=root, anchor_path=root_path, rest=rest, by_site=True)


def _into_mapping_form(
    loaded: Loaded, site: LocatedMapping, tail: tuple[str, ...], value: NewNode, path: ConfigPath
) -> EditPlan:
    """Write `tail` into a mapping-form include's overrides, reusing existing override mappings."""
    mapping = site
    for depth, segment in enumerate(tail):
        child = mapping.get(segment)
        if child is None:
            return _new_key(loaded, mapping, None, tail[depth:], value, path)
        plain = (
            isinstance(child, LocatedMapping)
            and child.file.path == site.file.path
            and written_as(child) is None
            and child.overrides is None
        )
        if not plain:
            raise WriteRefused(
                f"{path}: the override for it in {site.file.path} is not a plain mapping at "
                f"{segment!r}; write the key by hand"
            )
        assert isinstance(child, LocatedMapping)
        mapping = child
    raise AssertionError(f"{path}: the override already exists")


def _nested(tail: tuple[str, ...], value: NewNode) -> dict[str, NewNode]:
    nested: NewNode = value
    for segment in reversed(tail[1:]):
        nested = {segment: nested}
    return {tail[0]: nested}


def _convert(
    loaded: Loaded, include: LocatedScalar, tail: tuple[str, ...], value: NewNode, path: ConfigPath
) -> EditPlan:
    """Turn the scalar-form include `include` into mapping form carrying the override (FR-422,
    FR-423, D-41, D-45; research O-5). The include string keeps its bytes."""
    ctx = _context(loaded, include.file, path)
    original = ctx.text[include.start : include.end]
    overrides = _nested(tail, value)
    if include.in_flow:
        entries = render.render_flow(overrides)[1:-1]
        ctx.inline(include.start, include.end, f"{{{REF_KEY}: {original}, {entries}}}")
    else:
        line = ctx.lines.index_of(include.end)
        key = _key_of(loaded.composed.get(include.file.path), include.node)
        if key is None:
            # A list item: `- file:x` becomes `- $ref: file:x`, the overrides aligned below it.
            column = ctx.lines.column(include.start)
            ctx.splices.append((include.start, include.end, f"{REF_KEY}: {original}"))
        else:
            # `key: file:x  # c` becomes `key:  # c`: the value and the space before it go,
            # whatever followed it stays (the contract's example).
            column = ctx.lines.column(key.start_mark.index) + ctx.step
            colon = _colon_after(ctx.text, key.end_mark.index, path, include)
            ctx.splices.append((colon, include.end, ""))
        new_lines = [" " * column + f"{REF_KEY}: {original}"] if key is not None else []
        new_lines += render.render_block(overrides, column, ctx.step)
        ctx.insert_after_line(line, new_lines)
    return EditPlan(ctx.file, ctx.result(), include, None, tail, plain_value(value))


def _colon_after(text: str, offset: int, path: ConfigPath, include: LocatedScalar) -> int:
    while offset < len(text) and text[offset] in " \t":
        offset += 1
    if offset < len(text) and text[offset] == ":":
        return offset + 1
    raise WriteRefused(
        f"{path}: cannot locate the ':' before {include.value!r} in {include.file.path}"
    )


def _key_of(root: Any, target: Node) -> Node | None:
    """The key node whose value is `target` in a composed file, or None if `target` is a list
    item."""
    stack: list[Any] = [root] if root is not None else []
    while stack:
        node = stack.pop()
        if isinstance(node, MappingNode):
            for key, item in node.value:
                if item is target:
                    return key  # type: ignore[no-any-return]
                stack.append(item)
        elif isinstance(node, SequenceNode):
            if any(item is target for item in node.value):
                return None
            stack.extend(node.value)
    raise AssertionError("the include string is not in its file")
