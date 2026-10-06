"""Verify a planned change by re-loading it, then write it (research R-7)."""

from collections.abc import Callable
from pathlib import Path

from troupe.config.edit.planner import EditPlan, plan_set
from troupe.config.files import atomic_write, check_writable
from troupe.config.leaves import LeafEvent, diff_events, leaves, to_value, written_value
from troupe.config.loader import Loaded, load
from troupe.config.paths import ConfigPath, dotted_is_within
from troupe.config.scalars import NewNode, Scalar, content_start, scalars_equal
from troupe.config.tree import (
    Located,
    LocatedMapping,
    LocatedSequence,
    TextInclude,
    alias_name,
    alias_target,
    written_as,
)
from troupe.errors import LoadError, TroupeError, WriteRefused


def apply_set(
    theatre: Path,
    loaded: Loaded,
    path: ConfigPath,
    value: NewNode,
    before_write: Callable[[], None] = lambda: None,
    *,
    in_include: bool = False,
    expand_alias: bool = False,
) -> list[LeafEvent]:
    """Plan, verify and write `set PATH VALUE`; returns the leaf events it caused.

    `before_write` runs just before the file is written; it raises to refuse the write.
    """
    plan = plan_set(loaded, path, value, in_include=in_include, expand_alias=expand_alias)
    if plan is None or plan.new_text == plan.file.text:
        return []
    before = leaves(loaded.root)
    after_loaded = _reload(theatre, plan, path)
    after = leaves(after_loaded.root)
    _verify(loaded, after_loaded, plan, path, before, after)
    check_writable(plan.file.path)
    before_write()
    atomic_write(plan.file.path, plan.new_text)
    return diff_events(before, after)


def _reload(theatre: Path, plan: EditPlan, path: ConfigPath) -> Loaded:
    try:
        return load(theatre, {plan.file.path: plan.new_text})
    except LoadError as error:
        raise WriteRefused(
            f"{path}: the change to {plan.file.path} would not load back ({error.message}); "
            "no file was changed"
        ) from None


def _refuse(plan: EditPlan, path: ConfigPath, why: str) -> WriteRefused:
    return WriteRefused(f"{path}: refusing to write {plan.file.path}: {why}; no file was changed")


def _verify(
    before_loaded: Loaded,
    after_loaded: Loaded,
    plan: EditPlan,
    path: ConfigPath,
    before: dict[str, Scalar],
    after: dict[str, Scalar],
) -> None:
    """The new text must give exactly the intended value at PATH (and at every other path that
    shows the same bytes, e.g. a file included twice) and leave every other leaf unchanged."""
    basis = plan.basis or before_loaded
    aliases = _aliases(basis.root, plan.anchor, by_site=plan.by_site)
    targets = [_join(alias, plan.rest) for alias in aliases]
    if not targets or alias_name(plan.anchor) is not None:
        # Replacing a YAML alias changes it alone, not its anchor (step 6).
        targets = [path.dotted]
    for target in targets:
        try:
            node = _resolve(after_loaded.root, target)
        except TroupeError:
            raise _refuse(plan, path, f"{target} would not exist afterwards") from None
        # A text-include write is checked by its loaded text; any other value by what is
        # written, so a `file:` string read back as the include it now names still matches.
        if not (
            scalars_equal(to_value(node), plan.expected)
            or scalars_equal(written_value(node), plan.expected)
        ):
            raise _refuse(plan, path, f"{target} would not read back as the requested value")
    for leaf in set(before) | set(after):
        if any(dotted_is_within(leaf, target) for target in targets):
            continue
        if leaf not in before or leaf not in after or not scalars_equal(before[leaf], after[leaf]):
            raise _refuse(plan, path, f"{leaf} would change too")


def _join(alias: str, rest: tuple[str, ...]) -> str:
    return ".".join(part for part in (alias, *rest) if part)


def _identity(node: Located) -> tuple[Path, str, int]:
    """A YAML alias has its anchor's identity: it shows the same bytes (step 6)."""
    if isinstance(node, TextInclude):
        return node.target.path, "text", 0
    if alias_name(node) is not None:
        return (
            node.file.path,
            type(node).__name__,
            content_start(node.file.text, alias_target(node)),
        )
    return node.file.path, type(node).__name__, node.start if node.node is not None else -1


def _site_identity(node: Located) -> tuple[Path, str, int]:
    """An include root identified by its reference in the including file (research O-6)."""
    written = written_as(node)
    return _identity(written if written is not None else node)


def _aliases(root: Located, anchor: Located, *, by_site: bool = False) -> list[str]:
    """Dotted paths of every node with the same source bytes as `anchor` (with `by_site`, the
    same include reference)."""
    identity = _site_identity if by_site else _identity
    wanted = identity(anchor)
    found: list[str] = []
    stack: list[tuple[str, Located]] = [("", root)]
    while stack:
        prefix, node = stack.pop()
        if identity(node) == wanted:
            found.append(prefix)
        if isinstance(node, LocatedMapping):
            for key, value in node.entries:
                stack.append((_join(prefix, (str(key.node.value),)), value))
        elif isinstance(node, LocatedSequence):
            for index, item in enumerate(node.items):
                stack.append((_join(prefix, (str(index),)), item))
    return sorted(found)


def _resolve(root: Located, dotted: str) -> Located:
    from troupe.config.commands import resolve

    if not dotted:
        return root
    return resolve(root, ConfigPath.parse(dotted))
