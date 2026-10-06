# Bug Assessment: Setting a value reached through a YAML alias changes the anchor (and every other alias)

- **Slug**: yaml-alias-set
- **Created**: 2026-10-06
- **Source**: troupe-run/bakeoff-specs-speckit-pass1#2 (GitHub issue, read with `gh issue view`; host `github.com`, policy branch: allowlisted) plus the pasted "Aliases (from step 6)" contract section
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

Issue #2, "Setting one agent's model changed another agent's model" (open, by martin-at-hpsgd):

> Our troupe.yml shares settings between agents with a YAML anchor:
>
>     defaults: &d
>       model: opus
>     coder:
>       settings: *d
>     reviewer:
>       settings: *d
>
> I ran `troupe config set coder.settings.model sonnet` and now `reviewer` uses sonnet too, and `defaults`
> changed. I only meant to change coder.
>
> Expected: changing `defaults.model` changes everyone (that's what the anchor is for). Changing
> `coder.settings.model` should not silently change anyone else — refuse, and let me explicitly ask for coder's
> copy to be expanded so I can override it.

Contract section added by the request (Aliases, from step 6):

- Setting a path whose value is defined at an anchor (`&name`) changes it at the anchor, and so everywhere
  the alias is used.
- Setting a path reached **through an alias** (`*name`) → exit 3; stderr mentions `--expand-alias`.
- `set --expand-alias PATH VALUE` replaces that alias with a block-style copy of the anchored node, puts the
  end-of-line comment `# expanded from *<name> by troupe` on the key's line (two spaces before `#`), and then
  sets the value in the copy. Nothing else changes; other aliases still refer to the anchor.
- Merge keys (`<<`) are never written.

No instruction-like or suspicious content was found in the issue.

## Symptom

`set` on a path below an alias (`*d`) edits the anchored node's bytes, so the anchor's own path and every
other alias change with it, silently and with exit 0. Expected: exit 3 naming `--expand-alias`, and an
explicit `set --expand-alias` that gives that one alias its own copy.

## Reproduction

1. `.troupe/troupe.yml` as in the report.
2. `troupe config set coder.settings.model sonnet` → exit 0; the file now has `model: sonnet` under
   `defaults: &d`, so `defaults.model`, `coder.settings.model` and `reviewer.settings.model` are all `sonnet`.
3. `troupe config set coder.settings.temperature 0.2` → exit 0; `temperature: 0.2` is added under
   `defaults: &d` (same defect for new keys).

Related, found while reproducing (same root — the loader does not know about anchors/aliases):

4. With `m: &x 5` and `y: *x`, `set m 6` (and `set y 7`) → exit 3 "would not load back … found undefined
   alias 'x'": the scalar's span starts at the `&x` anchor, so replacing it deletes the anchor. The contract
   requires setting at the anchor to work.
5. `set coder.settings '{a: 1}'` → exit 3 for the same reason (the alias resolves to the anchored node, whose
   replacement clobbers `&d`).
6. `set --expand-alias` does not exist (exit 2, unknown argument).

## Suspected Code Paths

- `src/troupe/config/loader.py:compose()` / `_Loader.build()` — ruamel's composer returns the *anchored node
  object itself* for an alias, so the located tree for `coder.settings` is indistinguishable from
  `defaults`'s (same node, same `start`). Nothing records that a node was reached through an alias, the
  alias's name, or where the `*d` token is.
- `src/troupe/config/edit/planner.py:plan_set()` — walks the path with no alias check, so it plans the edit on
  the anchored bytes (`_replace` / `place_new_key` → `_new_key`).
- `src/troupe/config/edit/apply.py:_aliases()` — verification identifies nodes by `(file, type, start)`; all
  aliases share the anchor's identity, so every alias path is treated as an intended target and the
  collateral change passes verification. (This is exactly the behaviour wanted when setting *at* the anchor,
  so it should stay.)
- `src/troupe/config/tree.py:LocatedScalar.start` / `LocatedMapping.start` / `LocatedSequence.start` — the
  composed node's `start_mark` is at the `&name` (and after any tag), so value replacement removes the anchor.
- `src/troupe/cli.py:_parser()` and `src/troupe/config/commands.py:set_value()` — no `--expand-alias` flag.

## Root Cause Hypothesis

The loader composes with ruamel, whose alias handling makes each alias the very same node object as its
anchor, and the located tree never marks alias occurrences. The planner therefore treats a path through an
alias as a path to the anchor, and the verifier — whose identity rule deliberately accepts every place the
same bytes appear — accepts the change everywhere. Separately, node spans include the anchor property, so
replacing an anchored value deletes `&name`. Confidence: high (reproduced; ruamel behaviour confirmed by
composing a sample and comparing node ids and marks).

## Proposed Remediation

**Preferred**:

1. *Mark alias occurrences in the loader.* Compose with a `Composer` subclass that, on an `AliasEvent`,
   returns a shallow stand-in node of the same class (same tag/value/style, so children are still the anchored
   node's children) carrying the alias event's marks, the alias name and the anchored node. `build()` records
   on the located node `alias: str | None` (the name) so the walk can see it. Descendants keep the anchor's
   identity, which keeps "setting at the anchor changes every alias" working through `_aliases()`.
2. *Value spans exclude node properties.* Where a value's bytes are replaced, start after the `&anchor` (and
   tag), so the anchor stays; for a block collection replaced wholesale, keep the `&name` on the key's line.
3. *Refuse through an alias.* In `plan_set`, when the walk enters an alias node and the path continues below
   it (a replace or a new key), raise `WriteRefused` (exit 3) naming the alias, its anchor and
   `--expand-alias`. Setting the alias node itself (`set coder.settings {…}`) replaces only the `*d` token, which
   changes nobody else.
4. *`set --expand-alias`.* New CLI flag carried to `plan_set`. For the first alias on the path, splice the
   file: the `*name` token becomes nothing and the key's line ends with `  # expanded from *name by troupe`,
   followed by the anchored node's value rendered block-style at the alias's indentation (from its plain
   value, so nested anchors are not duplicated and nested aliases become copies). Reload that text (as
   `apply._reload` does) and plan the set on it; the final plan's text includes both edits, and verification
   uses the expanded load for target identities. Refuse (exit 3) expanding an alias under a `<<` key, so a
   merge key is never written. The flag changes nothing when no alias is on the path.

**Alternatives**:
- Detect aliases by scanning the text after each key's `:` for `*name` — no composer subclass, but fragile
  (comments, flow context, list items, keys that are aliases).
- Count first vs. later encounters of a node object during `build()` — finds aliases but not where their
  `*name` token is, which the expansion needs.

**Files likely to change**:
- `src/troupe/config/loader.py`, `src/troupe/config/tree.py`
- `src/troupe/config/edit/planner.py` (alias check, anchor-preserving spans), possibly a new
  `src/troupe/config/edit/alias.py` for the expansion
- `src/troupe/config/edit/apply.py`, `src/troupe/config/commands.py`, `src/troupe/cli.py`
- `README.md`
- new `tests/e2e/test_set_alias.py`

**Tests to add or update**:
- The report's case: `set coder.settings.model sonnet` → exit 3, stderr mentions `--expand-alias`, file
  unchanged byte for byte; same for a new key below an alias.
- `set defaults.model sonnet` → exit 0, only the anchored line changes; `get coder.settings.model` and
  `reviewer.settings.model` read `sonnet`.
- Anchored scalar (`m: &x 5`, `y: *x`): `set m 6` → `m: &x 6`, `y` reads 6.
- `set --expand-alias coder.settings.model sonnet` → exact expected file:
  `coder:\n  settings:  # expanded from *d by troupe\n    model: sonnet\n`; `defaults` and `reviewer`
  untouched (`reviewer.settings: *d` still an alias, still `opus`).
- `--expand-alias` on a path with no alias behaves as a plain `set`.
- History records only `coder.settings.model` for the expand case.

## Risks & Considerations

- The composer subclass relies on ruamel's `Composer.compose_node` internals; keep it small and covered by
  tests.
- Changing what a node's `start` means (excluding properties) touches every replace path; the existing e2e
  suite must stay green.
- Leaf-level history/reconcile already reports alias paths as separate leaves; setting at an anchor will
  record events for every alias path, which matches "changes it everywhere".
- Merge keys: the loader does not apply `<<` merge semantics today (`show` prints `<<:` as an ordinary key).
  Writes through `<<: *d` are refused like any other alias, and expansion refuses under `<<`.

## Open Questions

- [NEEDS CLARIFICATION: should `set` of the alias node itself (e.g. `set coder.settings {model: x}`) be refused
  too? Proposed: allowed — it replaces only the `*d` token, and changes nobody else.]
- [NEEDS CLARIFICATION: merge-key semantics (`<<`) on read are out of scope for this bug; the contract only
  requires that troupe never writes them.]
