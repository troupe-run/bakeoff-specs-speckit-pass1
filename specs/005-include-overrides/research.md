# Research: troupe configuration — include overrides (Step 5)

Each entry gives the decision, why it was made, and what else was considered. Behaviour choices the
contract leaves open are in `spec.md` (D-40 … D-48). This file records the technical choices for step 5
(O-1 … O-9). Research from steps 1–4 (R-*, B-*, S-*, G-*, L-*) stays in force. No new library is
needed; `ruamel.yaml`'s composed nodes already give every span the planner needs.

## O-1 The loader merges; every other reader sees an ordinary tree

- **Decision**: The loader recognises a mapping-form include while building a `MappingNode` (a
  `$ref` entry whose resolved value is an include string, D-42) and returns the **merged** node:
  a `LocatedMapping` whose entries are the included content's entries, with overridden entries
  replaced by (or, mapping over mapping, recursively merged with) the override's entries, then the
  override-only entries (D-46). Every entry keeps its own `LocatedScalar` key and value, read from
  the file it is written in.
- **Rationale**: `leaves`, `to_value`, `get`, `show`, `show --sources`, reconcile, `watch` and the
  `set` walk all read entries and each scalar's `file`; if the merged tree looks like any other tree,
  they need no change (FR-405, FR-408, FR-440). `$ref` never appears in entries, so it is never a leaf
  or a path (FR-405). One place decides the merge (Principle IV).
- **Alternatives**: Keep base and overrides as separate trees and merge in each reader — five readers
  to keep consistent; merge plain values after loading — loses each scalar's file, which `--sources`
  and `set` need.

## O-2 Merged nodes remember where they were written

- **Decision**: `tree.py` gains two optional fields on located nodes:
  - `include_site: LocatedMapping | None` on an include root — the raw mapping-form mapping `M` in the
    including file (built without following its `$ref`, so its entries include the `$ref` scalar and
    the override values as written). `included_by` keeps pointing at the include string scalar (the
    `$ref` value in mapping form), so step 1's "whole value comes from an include" refusal (FR-024 /
    FR-432) works unchanged for both forms.
  - `overrides: LocatedMapping | None` on a merged mapping — the override mapping merged into it
    (`M` for an include root; the override's nested mapping below it). A mapping with
    `overrides is not None` is "merged".
  A helper `written_as(node)` returns `include_site`, else `included_by`, else `None`: the node that
  stands for the whole value in the including file. `content_end`, `_last_line`, `_style_of` and
  `written_value` use it where they used `included_by`, so a new sibling after a mapping-form include
  goes below the whole mapping, not below the `$ref` line.
- **Rationale**: The planner must find the override text in the including file (O-4) and the verifier
  must identify an include by where it is referenced (O-6). Two fields cover both.
- **Alternatives**: A separate `MergedMapping` class — every `isinstance(…, LocatedMapping)` in
  readers would need updating, for no behavioural gain.

## O-3 Loader validation

- **Decision**: In `_Loader.build` for a mapping with an include `$ref`:
  1. text target: no other keys → `TextInclude(include=$ref scalar, target, include_site=M)`; any
     other key → `LoadError("<including file>: $ref to non-YAML <target> cannot have overrides …")`
     (FR-403, exit 4).
  2. YAML target, no other keys → the embedded content, with `include_site=M` and, if it is a
     mapping, `overrides=M` (an empty overlay) so a new key under it is written into `M` (O-4).
  3. YAML target with other keys whose content is not a mapping (list, scalar, or empty file = null)
     → `LoadError` naming the including file (D-43).
  4. Cycle and missing-target checks are the scalar-form ones (`include()`), so messages and exit 4
     are identical (FR-407).
  Override values are built with the including file's chain, so includes inside overrides are
  followed (FR-404) and cycles through them are caught.
- **Rationale**: Reuses `include()` for path resolution, cycles and text/YAML choice; all new failure
  modes are `LoadError`, which already maps to exit 4 and names the file (FR-008).

## O-4 Where a new key goes: one walk, one decision function

- **Decision**: `plan_set`'s walk records, for each file, the **site** it was last entered through:
  stepping into an include root for target file F sets `site_of[F] = (root node, root path)`; stepping
  into a list item clears `site_of` (FR-424 — overrides cannot address list items; an item that is
  itself an include root then sets a fresh site, D-41). When the walk stops at the deepest existing
  mapping X, a new function `edit/override.py: place_new_key` decides:
  1. `own = overrides-file(X)` if X is merged (D-48), else `X.file`.
  2. If `own` is the main configuration file, or `own` has no site (it lies below a list): write in
     `own` — into X itself if X is plain, else into the innermost raw override mapping of X
     (following `overrides` until a plain mapping, which is in `own`). This is step 1's `_new_key`,
     unchanged.
  3. Else write an override at `site_of[own]`, with sub-path Q = segments from the site root to X plus
     the new segments: in mapping form (`include_site` M) walk Q through M's plain override mappings
     and call `_new_key` on the deepest one; in scalar form convert (O-5).
  Walking Q in M stops with `WriteRefused` (exit 3) if an existing step is not a plain mapping written
  in M's file (D-47).
- **Rationale**: Every rule of FR-420 – FR-424 and D-40/D-41/D-48 is in one function; step 1's
  `_new_key` remains the only code that lays out new keys, so quoting, comment and blank-line rules
  (FR-425, FR-427) carry over. Tracking the site per *file* (not "the last include passed") is what
  makes an ancestor written in `coder.yaml` go to `troupe.yml` even when the walk has since passed
  through `coder.yaml`'s own include of `model.yaml`.
- **Alternatives**: Decide from the ancestor alone — it does not know its include path; always the
  outermost include — rejected by D-40.

## O-5 Converting a scalar-form include

- **Decision**: In `edit/override.py`, given the include scalar S (in file G) and Q:
  - **Block mapping value** (`key: file:x  # c`): splice out from the end of the `:` to `S.end` (the
    space and the string), leaving whatever followed S — whitespace and comment — on the key line
    (FR-422); insert below the key line `$ref: <S's original bytes>` at `key column + step` and the
    nested override lines from `render.render_block({Q…: value})` at the same column. The contract
    example is a test fixture verbatim (SC-402).
  - **Block list item** (`- file:x  # c`, D-41): replace S's bytes with `$ref: <S bytes>` (compact
    form, comment stays at the end of that line), and insert the override lines at the column after
    `- `.
  - **Flow context**: replace S's bytes with `{$ref: <S bytes>, <render_flow entry>}` (FR-423).
  - `step` and line ending are G's (step 1 `indent_step`, D-6). One `EditPlan` for G (FR-426).
- **Rationale**: Smallest diff that yields the contract's shape; S's bytes are copied, so quoting is
  kept (D-45). Block vs compact for list items: compact keeps the item on one line and the comment in
  place.
- **Alternatives**: Render `$ref` from S's value — would requote; put a list item's `$ref` on its own
  line below `-` — larger diff and an unusual layout.

## O-6 Verification identifies include roots by their reference

- **Decision**: An override write's `EditPlan` anchors at the include root with `anchor_path` = the
  root's path and `rest` = Q. `apply._identity` for a node with `written_as(node)` returns the
  identity of that reference (G, offset) instead of the target file's; `_aliases` therefore finds the
  root only where *this* reference is (or where G itself is included twice). The existing check —
  value at every alias reads back as requested, every other leaf unchanged — then proves that the
  shared file and other users of it are unaffected.
- **Rationale**: Without it, a file included at two keys would make `_verify` expect the override at
  both and refuse; with it, verification still guards against an override leaking anywhere else.
- **Alternatives**: Skip alias checks for overrides — would lose the "nothing else changed" guard.

## O-7 Existing values and whole-value replacement

- **Decision**: No new code for FR-430/FR-431: the merged tree holds the override's scalar where a
  value is overridden and the included file's scalar otherwise, and `_replace` writes in `target.file`.
  For a merged target mapping (FR-432/D-44): if any of its entries (recursively) comes from the
  included side, `WriteRefused`; otherwise (every key is the override's) replace the override mapping
  in its file. Mapping-form roots are refused by the existing `included_by` check. Appends to a list
  already go to `sequence.file`, the file holding the effective list (FR-424).
- **Rationale**: The merge already put the right node at each path; only the merged-mapping case
  needs a guard.

## O-8 Tests

- **Decision**: New e2e modules on real theatres through the real CLI, byte-comparing every file
  before and after (`assert_set` / `assert_refused` from `conftest`):
  `test_overrides_read.py` (US2, FR-400 – FR-408), `test_overrides_new_key.py` (US1, FR-420 – FR-427,
  D-40/D-41/D-45/D-47/D-48), `test_overrides_existing.py` (US3, FR-430 – FR-432, D-44),
  `test_overrides_lists.py` (US4, FR-424), `test_overrides_errors.py` (FR-403, D-43, FR-407, FR-450),
  and history/watch scenarios (FR-440, FR-441) in `test_overrides_history.py`. Unit tests for the merge
  in `tests/unit/test_merge.py`. `test_set_new_key.py::test_new_key_in_an_included_file` encodes the
  replaced FR-022 and is changed to expect the override (Principle VI).
- **Rationale**: Principle II — every behaviour has a test that fails when it breaks; Principle I —
  preservation is proven by bytes.

## O-9 Documentation

- **Decision**: README gains a short "Overrides" paragraph under includes and `set`; step 1's spec
  marks FR-022 as replaced by step 5 (and FR-020 refined), as step 3 marked FR-015; this feature's
  contract is linked.
- **Rationale**: Principle VI — spec, code, tests and docs change together.
