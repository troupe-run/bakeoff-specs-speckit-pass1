# Bug Fix: Setting a value reached through a YAML alias changes the anchor (and every other alias)

- **Slug**: yaml-alias-set
- **Fixed**: 2026-10-06
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

The loader now marks alias occurrences, so `set` refuses (exit 3, naming `--expand-alias`) any path that
goes below an alias. The new `set --expand-alias` replaces that alias with a commented block-style copy
and sets the value in the copy. Anchored values keep their `&name` when they are replaced, so setting at
the anchor works and changes every alias. Merge keys (`<<`) are never written.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `src/troupe/config/loader.py` | modified | `_AliasComposer` returns a stand-in node (slotted subclass) for each alias, spanning `*name` and pointing at the anchored node; `reload()` helper |
| `src/troupe/config/scalars.py` | modified | `content_start()` (a node's bytes start after `&anchor`); `ALIAS_NAME`/`ALIAS_TARGET`; aliases typed as their target; an explicit tag after an anchor is now recognised |
| `src/troupe/config/tree.py` | modified | `.start` skips the anchor; `is_alias`, `alias_name`, `alias_target` |
| `src/troupe/config/edit/planner.py` | modified | refuse a path with a `<<` segment; hand off to `alias.py` when the walk goes below an alias; replace an alias token by itself; keep `&name` when an empty or block value is rewritten (`_after_properties`); `EditPlan.basis` |
| `src/troupe/config/edit/alias.py` | added | refusal message, and expansion (copy + `  # expanded from *name by troupe`), then plan the set on the expanded text |
| `src/troupe/config/edit/apply.py` | modified | an alias has its anchor's identity, so setting at an anchor is verified at every alias; replacing an alias token is verified only at PATH; verify against `plan.basis` |
| `src/troupe/config/commands.py`, `src/troupe/cli.py` | modified | `set --expand-alias` |
| `README.md` | modified | documents aliases and the flag |
| `tests/e2e/test_set_alias.py` | added test | 13 tests |
| `tests/unit/test_verify.py` | modified | the stand-in planner accepts `expand_alias` |

## Diff Highlights (optional)

```text
$ troupe config set coder.settings.model sonnet
troupe: error: coder.settings.model: goes through the alias *d in …/troupe.yml; changing it would change
&d and every alias of it. Use `set --expand-alias` to give it its own copy first        (exit 3)

$ troupe config set --expand-alias coder.settings.model sonnet
coder:
  settings:  # expanded from *d by troupe
    model: sonnet
reviewer:
  settings: *d
```

## Tests Added or Updated

- `tests/e2e/test_set_alias.py::test_setting_through_an_alias_is_refused`: the reported case gives exit 3,
  mentions `--expand-alias` and leaves every file unchanged.
- `…::test_a_new_key_through_an_alias_is_refused`
- `…::test_setting_at_the_anchor_changes_every_alias`
- `…::test_expand_alias_gives_the_alias_its_own_copy`: exact bytes, other aliases untouched, and one
  history event for the changed path.
- `…::test_expand_alias_adds_a_new_key_to_the_copy`, `…_in_a_list_item`, `…_without_an_alias_is_a_plain_set`
- `…::test_an_anchored_scalar_keeps_its_anchor`, `…::test_replacing_an_anchored_section_keeps_its_anchor`
- `…::test_replacing_the_alias_itself_changes_only_it`
- `…::test_merge_keys_are_never_written`, `…::test_an_alias_in_a_flow_collection_is_not_expanded`
- `…::test_refusal_without_the_flag_then_success_with_it`

## Local Verification

- `uv run pytest tests/e2e/test_set_alias.py` → 13 passed. With `src/` reverted to HEAD, 12 of the 13 fail
  (the plain-set case passes only because the flag fails to parse).
- `uv run pytest` (full suite) → 791 passed, 1 skipped and 4 failed in `tests/unit/test_verify.py`. Those
  4 failed because the stand-in planner had no `expand_alias` keyword. After that fix, `tests/unit` gives
  260 passed, and the full suite on the committed tree gives 795 passed, 1 skipped.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src tests` → clean.
- Manual checks: ran the issue's example through the CLI, plus anchored scalars, empty anchored scalars,
  aliases in lists, aliases with comments, flow aliases and `<<`.

## Deviations from Assessment

- Merge keys: the assessment proposed refusing only an expansion under `<<`. The fix refuses any `set`
  whose PATH has a `<<` segment, because `set coder.<< x` would otherwise write the merge key's value.
- An alias inside a flow collection cannot take a block-style copy, so `--expand-alias` refuses there
  (exit 3).
- An expansion whose final write would land in a different file (e.g. through an include inside the copy)
  is refused rather than split across two files.

## Follow-ups

- The loader still does not apply `<<` merge semantics on read (it shows `<<` as an ordinary key).
- When the alias line already has a comment, the expansion comment goes before it on the same line
  (`k:  # expanded from *d by troupe  # mine`).
- Recursive anchors (`a: &a [*a]`) would still loop in the loader; this was already the case before.
