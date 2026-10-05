# Implementation Plan: troupe configuration — include overrides (Step 5)

**Branch**: `main` (spec dir `005-include-overrides`) | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-include-overrides/spec.md`

## Summary

Let an include be written in mapping form (`$ref` plus overrides) and make `set` write a new key under
included content as an override in the including file, so shared files stay unchanged. The loader
builds the **merged** tree directly — every entry keeps the scalar from the file it is written in —
so `get`, `show`, `--sources`, history, reconcile and `watch` work unchanged (research O-1). Merged
nodes remember their raw override mapping and include site (O-2). `plan_set`'s walk tracks, per file,
the include site it was entered through; a new `edit/override.py` decides where a new key goes and
converts a scalar-form include to mapping form (O-4, O-5). Verification identifies an include root by
its reference, so an override is proven to affect only its own site (O-6).

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`)

**Primary Dependencies**: unchanged — `ruamel.yaml` (compose only; spans from node marks),
`eventsourcing` 9.5. No new dependency.

**Storage**: unchanged (event store under `.troupe/`); configuration files gain mapping-form includes.

**Testing**: pytest; e2e tests on real theatres through the real CLI, comparing every file's bytes
before and after (`conftest.assert_set` / `assert_refused`); unit tests for the merge.

**Target Platform**: macOS and Linux

**Project Type**: CLI (single Python package, `src/` layout)

**Performance Goals**: none (constitution).

**Constraints**: included files byte-for-byte unchanged by new keys; smallest diff in the including
file; all refusals leave every file untouched; `mypy --strict` and ruff clean.

**Scale/Scope**: `tree.py`, `loader.py`, `edit/planner.py`, `edit/apply.py`, `leaves.py`
(`written_value`), new `edit/override.py`; tests; README and step 1 spec note.

No NEEDS CLARIFICATION remains: every technical point is resolved in [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle / constraint | How the plan satisfies it | Status |
|---|---|---|
| I. User's files are sacred | The CR's point: new keys no longer touch shared files (FR-421, FR-426), proven by byte comparison of every file. Conversion is a splice of the include line plus inserted lines (O-5), keeping the include string's bytes and the end-of-line comment. Ambiguous placements refuse (D-43, D-44, D-47) instead of guessing. Writes stay atomic and verified by reload (step 1 R-7, O-6). | PASS |
| II. Tests that prove behaviour | Every FR-400 – FR-450 and acceptance scenario maps to an e2e test (O-8); the contract example is a fixture verbatim. The existing test encoding the replaced FR-022 is updated, not deleted, so it now proves the new rule. | PASS |
| III. Done means verified | Gates in [quickstart.md](quickstart.md) — pytest, `mypy --strict`, ruff — run and shown. | PASS |
| IV. One decision, one place | `$ref` key name and mapping-form recognition: `loader` (next to `INCLUDE_PREFIX`). Merge rule and key order: `loader.merge`. Placement of a new key: `edit/override.place_new_key`. Conversion layout: `edit/override`. "Node standing for the whole value": `tree.written_as`. | PASS |
| V. Deliver what was asked | Every contract bullet maps to FRs; open choices recorded (spec D-40 – D-48, research O-1 – O-9). No extra features (no override removal, no list-item addressing). | PASS |
| VI. Traceability | Step 1 FR-022 marked replaced and FR-020 refined in the step 1 spec; README updated in the same change as the code; code comments cite FR/D numbers at the decision sites. | PASS |
| Tech constraints | Python 3.12+/uv; `uv run troupe config …`; event store unchanged; config location unchanged; macOS/Linux; no perf work. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/005-include-overrides/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/cli.md     # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/troupe/config/
├── tree.py                # + include_site, overrides fields; written_as()
├── loader.py              # REF_KEY = "$ref"; mapping-form recognition, validation, merge (O-1, O-3)
├── leaves.py              # written_value uses written_as (mapping form → its raw mapping)
└── edit/
    ├── planner.py         # walk tracks site_of (O-4); _new_key call goes through place_new_key;
    │                      # content_end/_last_line/_style_of use written_as; merged-mapping replace guard (O-7)
    ├── override.py        # NEW: place_new_key, override walk in M, scalar→mapping conversion (O-4, O-5)
    └── apply.py           # _identity of include roots by their reference (O-6)
tests/
├── e2e/
│   ├── test_overrides_read.py       # US2: get/show/--sources/merge/order/$ref not a path
│   ├── test_overrides_new_key.py    # US1: conversion (block/flow/list item/quoted), nested intermediates,
│   │                                #      existing overrides reused, nested includes (D-40), D-47, D-48
│   ├── test_overrides_existing.py   # US3: overridden vs not; no-op; D-44; whole include refused
│   ├── test_overrides_lists.py      # US4: append and key-in-item in the file holding the list
│   ├── test_overrides_errors.py     # FR-403, D-43, missing/cycle via $ref, D-42 ordinary mapping
│   ├── test_overrides_history.py    # import/set/reconcile events of merged leaves; watch follows $ref
│   └── test_set_new_key.py          # test_new_key_in_an_included_file → expects the override
└── unit/
    └── test_merge.py                # merge order, recursion, replacement kinds
```

**Structure Decision**: Keep the existing layout. Reading changes live in the loader; the one new
decision area (where a new key goes, and conversion) gets one new module beside the planner.

## Design overview

1. **Tree** (`tree.py`): add `include_site: LocatedMapping | None = None` to all located types and
   `overrides: LocatedMapping | None = None` to `LocatedMapping`; `written_as(node)`.
2. **Loader** (`loader.py`): `REF_KEY = "$ref"`. In `build` for a `MappingNode`, after building the
   key scalars, if an entry's key is `$ref` and its value resolves to an include string (D-42):
   build the raw mapping `M` (entries built normally, except the `$ref` value stays a `LocatedScalar`);
   resolve the target with the existing `include()` (cycles, missing, text/YAML); apply O-3
   validation; merge (data-model "Merge"); set `included_by` = `$ref` scalar, `include_site` = M,
   `overrides` = M. Override values are built with the including file's chain.
3. **Planner** (`planner.py`): in `plan_set`, keep `site_of: dict[Path, tuple[Located, ConfigPath]]`:
   on stepping into a child that has `written_as(child) is not None`, set
   `site_of[child_target_file] = (child, here)`; on stepping into a list item, clear it first. When a
   key is missing, call `override.place_new_key(loaded, node, prefix, rest, value, path, site_of)`.
   `_replace`: a merged target with any entry from the included side → `WriteRefused` (D-44); a merged
   target with only override entries → replace its override mapping. `content_end`, `_last_line`,
   `_style_of` use `written_as`.
4. **Override** (`edit/override.py`): `place_new_key` per data-model "New-key placement"; returns an
   `EditPlan` anchored at the include root (`anchor_path` = site path, `rest` = Q) for override writes,
   or delegates to `planner._new_key` for in-place writes. Conversion per research O-5, using
   `render.render_block`/`render_flow`/`render_list_item` and the including file's `indent_step` and
   line ending.
5. **Apply** (`apply.py`): `_identity(node)` uses `written_as(node)`'s file and offset when set.
6. **Docs**: README "Overrides" paragraph (mapping form, where `set` writes); step 1 spec FR-022
   "replaced by step 5", FR-020 "refined by step 5".

## Post-design Constitution Check

Re-evaluated after writing research.md, data-model.md, contracts/cli.md and quickstart.md: all rows
above remain PASS. The design adds no speculative abstraction: two optional fields and one module,
each holding a decision the contract makes this step. No violation; Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify.
