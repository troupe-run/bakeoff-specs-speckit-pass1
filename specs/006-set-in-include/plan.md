# Implementation Plan: troupe configuration — `set --in-include` (Step 5, CR-B)

**Branch**: `main` (spec dir `006-set-in-include`) | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-set-in-include/spec.md`

## Summary

Add `--in-include` to `set`: a new key under included content is written into the included file by
the step 1 rule instead of as a CR-A override. The flag travels from the CLI to CR-A's single
placement function, `edit/override.place_new_key`, which is the only code that reads it (research
I-1); every other kind of write ignores it, giving D-50 by construction. For a merged ancestor the key
goes into the mapping's unmerged base, so merged mappings keep a `base` reference (I-2). In-include
writes keep step 1's content identity for verification, while CR-A's override writes match by include
reference (I-3, amending CR-A O-6).

This plan is implemented together with CR-A (`specs/005-include-overrides/plan.md`); it adds one flag,
one tree field and one branch to CR-A's design.

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`)

**Primary Dependencies**: unchanged — `argparse`, `ruamel.yaml`, `eventsourcing` 9.5.

**Storage**: unchanged.

**Testing**: pytest; e2e tests through the real CLI comparing every file's bytes, each flag scenario
paired with the same `set` without the flag; usage tests for the option's errors.

**Target Platform**: macOS and Linux

**Project Type**: CLI (single Python package, `src/` layout)

**Performance Goals**: none (constitution).

**Constraints**: the default behaviour (CR-A) is unchanged; option errors are detected before loading;
`mypy --strict` and ruff clean.

**Scale/Scope**: `cli.py`, `commands.set_value`, `edit/apply.apply_set`, `edit/planner.plan_set`,
`edit/override.place_new_key`, `tree.py` (`base`), `loader` merge (sets `base`); tests; README.

No NEEDS CLARIFICATION remains: every technical point is resolved in [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle / constraint | How the plan satisfies it | Status |
|---|---|---|
| I. User's files are sacred | The flag writes with step 1's layout code into the one included file; the including file is not converted or touched (byte-compared). Option misuse exits 2 before loading. | PASS |
| II. Tests that prove behaviour | Every FR-460 – FR-466 and acceptance scenario has an e2e test (I-5). D-50 tests pair the flag with the no-flag run and compare files and history, so they fail if the flag changes anything it should not. SC-462 re-runs the step 1 fixture CR-A changed. | PASS |
| III. Done means verified | Gates in [quickstart.md](quickstart.md) run and shown. | PASS |
| IV. One decision, one place | Option name and parsing: `cli.py`. Where a new key goes under each mode: `override.place_new_key` only. "Shared part of a merged mapping": `tree` (`base`, set in the loader's merge). Verification identity choice: the plan's `by_site` mark, set where the plan is made. | PASS |
| V. Deliver what was asked | The contract's single bullet maps to FR-461; open choices recorded (D-50 – D-52, I-1 – I-5). No extra options (no forced overrides for existing keys — out of contract). | PASS |
| VI. Traceability | CR-A's research O-6 amended in this change with a pointer to I-3; README documents the flag beside CR-A's override rules; code comment at the branch cites FR-461/D-51. | PASS |
| Tech constraints | Python 3.12+/uv; `uv run troupe config …`; event store unchanged; macOS/Linux. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/006-set-in-include/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/cli.md     # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/troupe/
├── cli.py                     # set: --in-include (store_true) → commands.set_value(in_include=…)
└── config/
    ├── commands.py            # set_value(…, in_include) → apply_set
    ├── tree.py                # LocatedMapping.base (merged mappings), shared_part()
    ├── loader.py              # merge() sets base on every merged mapping
    └── edit/
        ├── apply.py           # apply_set(…, in_include) → plan_set
        ├── planner.py         # plan_set(…, in_include) → place_new_key
        └── override.py        # place_new_key: in_include → _new_key(shared_part(X) or X)
tests/
└── e2e/
    ├── test_set_in_include.py # US1, US2, history, file included twice, SC-462
    └── test_usage.py          # option on other subcommands, with a value, positions, with --reason
```

**Structure Decision**: No new module; the flag reaches CR-A's placement function and branches there.

## Design overview

1. **CLI**: `set_parser.add_argument("--in-include", action="store_true", help="write a new key into
   the included file instead of as an override")`; `run` passes `in_include=args.in_include`.
2. **Plumbing**: `set_value`, `apply_set`, `plan_set` gain a keyword-only `in_include: bool = False`.
3. **Tree/loader**: CR-A's merge sets `merged.base = <included mapping>`; `shared_part(m)` follows
   `base` while it is set.
4. **Placement** (`place_new_key`): first branch —
   `if in_include: return _new_key(loaded, shared_part(X) if X.overrides is not None else X, …)`
   with step 1's anchor (content identity); otherwise CR-A's logic.
5. **Docs**: README `set` section: `--in-include` with a one-line example; link to this spec.

## Post-design Constitution Check

Re-evaluated after writing research.md, data-model.md, contracts/cli.md and quickstart.md: all rows
remain PASS. The amendment to CR-A's O-6 was found here and recorded in both features' research
(Principle VI). No violation; Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify.
