# Research: troupe configuration — `set --in-include` (Step 5, CR-B)

Each entry gives the decision, why it was made, and what else was considered. Behaviour choices the
contract leaves open are in `spec.md` (D-50 … D-52). This file records the technical choices for CR-B
(I-1 … I-5). CR-A's research (`specs/005-include-overrides/research.md`, O-1 … O-9) is the base this
builds on; I-3 amends O-6.

## I-1 The flag is a placement mode passed down to the one placement function

- **Decision**: `cli.py` adds `--in-include` to the `set` parser (`action="store_true"`). It is passed
  as `in_include: bool` through `commands.set_value` → `apply_set` → `plan_set` →
  `override.place_new_key`. `place_new_key` is the only code that reads it: with `in_include`, it
  skips CR-A's override branch and writes in place (I-2). Every other path of `plan_set` (replace,
  append, key inside a list item) ignores it, which is D-50 by construction.
- **Rationale**: CR-A put "where does a new key go" in one function (O-4); CR-B is a second answer to
  that same question, so it belongs there (Principle IV). `argparse` gives FR-460/FR-466 for free:
  any position, repeated flag accepted, `--in-include=x` → "ignored explicit argument" (exit 2), other
  subcommands → "unrecognized arguments" (exit 2), all before anything is loaded.
- **Alternatives**: A separate planner entry point for in-include writes — duplicates the walk;
  a global/setting — not what the contract asks.

## I-2 Where the step 1 rule writes, with merged mappings

- **Decision**: With `in_include`, the target mapping for the new key is:
  - X itself if X is not merged (plain mapping in the main file, an included file, or an override) —
    step 1's `_new_key(X)`, unchanged;
  - if X is merged, its **base**: the mapping as written in the included file, before overrides were
    merged in. If that base is itself merged (the included file overrides a deeper include), follow
    `base` again until a plain mapping (nested includes → the deepest file, spec US1 scenario 5).
  The merged mapping therefore keeps a reference to its unmerged base (`tree.LocatedMapping.base`,
  set by CR-A's merge). `_new_key` lays out the key after the base's own last entry, so placement,
  quoting and comment rules are exactly step 1's (FR-463).
- **Rationale**: A merged mapping's `entries` mix two files; laying out a new line needs the entries
  of the one file being written. The base is that file's mapping.
- **Alternatives**: Re-derive the base by re-reading the included file's composed node at the merged
  node's offset — the same information, found the hard way.

## I-3 Verification: content identity for in-include writes (amends CR-A O-6)

- **Decision**: An `--in-include` write is an ordinary step 1 write: its `EditPlan` anchors at the
  base mapping with step 1's content identity, so `_verify` expects the new key at every path that
  includes that file (spec edge case "included file used by several keys"). Only override writes
  (CR-A) are marked `by_site` and matched by their include reference. O-6 is amended accordingly.
- **Rationale**: Matching include roots by reference for *every* plan would make a write into a file
  included twice look like an unintended change at the second path and refuse it — breaking step 1's
  `test_file_included_twice…` and this CR alike.

## I-4 Events

- **Decision**: No change: `apply_set` diffs leaves before and after, so a key written into a file
  included at two paths yields a `set` event at each (FR-465), with `via` `cli`, the actor and reason.

## I-5 Tests

- **Decision**: `tests/e2e/test_set_in_include.py`: US1 scenarios (scalar form untouched, mapping form
  untouched, missing intermediates, merged ancestor → base, nested includes → deepest file, file
  included twice, flow mapping in the included file); US2 scenarios (existing overridden / not
  overridden, main-file ancestor, list append, key in list item — each compared with the same `set`
  without the flag); history fields. `tests/e2e/test_usage.py`: flag on `get`/`show`/`history`/
  `watch` → exit 2, `--in-include=yes` → exit 2, flag before PATH and after VALUE, with `--reason`.
  SC-462: the step 1 new-key-in-include fixture is run again with `--in-include` and expects step 1's
  original bytes.
