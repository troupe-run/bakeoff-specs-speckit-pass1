"""Setting a path that goes through a YAML alias (step 6).

Below an alias (`*name`) is the anchored node (`&name`), shared by the anchor and every alias, so
`set` refuses to change it there. `set --expand-alias` first replaces the alias with a block-style
copy of the anchored node, then sets the value in the copy.
"""

from dataclasses import replace

from troupe.config.edit import render
from troupe.config.edit.planner import (
    MERGE_KEY,
    EditPlan,
    _after_indicator,
    _context,
    _Owner,
    _owner_column,
    plan_set,
)
from troupe.config.files import local_path
from troupe.config.includes import LITERAL_TAG
from troupe.config.leaves import written_value
from troupe.config.loader import Loaded, reload
from troupe.config.paths import ConfigPath
from troupe.config.scalars import NewNode, NewScalar, Value
from troupe.config.tree import (
    Located,
    LocatedMapping,
    LocatedScalar,
    LocatedSequence,
    TextInclude,
    alias_name,
    written_as,
)
from troupe.errors import LoadError, WriteRefused

type Alias = LocatedScalar | LocatedMapping | LocatedSequence

COMMENT = "# expanded from *{name} by troupe"


def through_alias(
    loaded: Loaded,
    alias: Alias,
    owner: _Owner | None,
    path: ConfigPath,
    value: NewNode,
    *,
    in_include: bool,
    expand: bool,
    include: bool = False,
) -> EditPlan | None:
    """Refuse a change below `alias`, or with `expand` plan it on a copy of the anchored node."""
    name = alias_name(alias)
    assert name is not None and owner is not None
    if not expand:
        raise WriteRefused(
            f"{path}: goes through the alias *{name} in {alias.file.path}; changing it would "
            f"change &{name} and every alias of it. Use `set --expand-alias` to give it its own "
            "copy first"
        )
    if alias.in_flow:
        raise WriteRefused(
            f"{path}: the alias *{name} in {alias.file.path} is inside a flow collection, "
            "where a block-style copy cannot go; expand it by hand"
        )
    copy = _copy(alias)
    if _has_merge_key(copy):
        raise WriteRefused(
            f"{path}: &{name} holds a merge key ({MERGE_KEY}); troupe never writes one"
        )
    target = local_path(alias.file)
    expanded = _expand(loaded, alias, owner, name, copy, path)
    try:
        basis = reload(loaded, {target: expanded})
    except LoadError as error:
        raise WriteRefused(
            f"{path}: expanding *{name} in {alias.file.path} would not load back "
            f"({error.message}); no file was changed"
        ) from None
    plan = plan_set(basis, path, value, in_include=in_include, expand_alias=True, include=include)
    if plan is None:
        return None
    if plan.file.path != alias.file.path:
        raise WriteRefused(
            f"{path}: after expanding *{name} the value is in {plan.file.path}, not in "
            f"{alias.file.path}; expand it by hand"
        )
    return replace(plan, basis=basis)


def _expand(
    loaded: Loaded, alias: Alias, owner: _Owner, name: str, copy: NewNode, path: ConfigPath
) -> str:
    """The file's text with `alias` replaced by `copy`, the comment on the key's (or dash's)
    line. A collection copy goes below that line."""
    ctx = _context(loaded, alias.file, path)
    owner_column = _owner_column(ctx, owner)
    column = owner_column + (ctx.step if owner.key is not None else 2)
    inline, following = render.render_value_lines(copy, column, ctx.step)
    after = _after_indicator(ctx, owner, alias.start)
    head = f" {inline}" if inline else ""
    ctx.splices.append((after, alias.end, f"{head}  {COMMENT.format(name=name)}"))
    ctx.insert_after_line(ctx.lines.index_of(alias.end), following)
    return ctx.result()


def _copy(node: Located) -> NewNode:
    """The anchored value as written, to be written again: includes as their include strings,
    and a `!literal` tag kept, so the copy reads back as the same value (step 7 FR-620)."""
    if written_as(node) is not None or isinstance(node, TextInclude):
        return _as_new(written_value(node))
    if isinstance(node, LocatedMapping):
        return {str(key.node.value): _copy(value) for key, value in node.entries}
    if isinstance(node, LocatedSequence):
        return [_copy(item) for item in node.items]
    return NewScalar(node.value, tag=LITERAL_TAG if node.node.tag == LITERAL_TAG else None)


def _as_new(value: Value) -> NewNode:
    if isinstance(value, list):
        return [_as_new(item) for item in value]
    if isinstance(value, dict):
        return {key: _as_new(item) for key, item in value.items()}
    return NewScalar(value)


def _has_merge_key(node: NewNode) -> bool:
    if isinstance(node, list):
        return any(_has_merge_key(item) for item in node)
    if isinstance(node, dict):
        return any(key == MERGE_KEY or _has_merge_key(item) for key, item in node.items())
    return False
