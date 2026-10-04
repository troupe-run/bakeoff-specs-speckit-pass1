# Implementation Plan: troupe configuration — lineage (Step 4)

**Branch**: `main` (spec dir `004-config-lineage`) | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-config-lineage/spec.md`

## Summary

Stamp every recorded event with lineage — actor, via, at, reason, change — and print it from
`history`. Lineage is stored as extra arguments of the existing `LeafChanged` event, so it is
persisted and replayed by `eventsourcing` with the event itself (research L-1). A new
`config/lineage.py` holds the `Actor`/`Lineage` values, `TROUPE_ACTOR` parsing, the login-name lookup
and the timestamp format (L-2 – L-6). Each `ConfigStore` call that saves a unit (import, reconcile,
`set`) takes one `Lineage`, so every event of a unit shares `change` and `at` by construction. The
CLI validates `TROUPE_ACTOR` for every subcommand before anything is loaded, and `set` gains
`--reason TEXT`.

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`)

**Primary Dependencies**: unchanged — `eventsourcing` 9.5 (SQLite), `ruamel.yaml`. Standard library
only for the new parts (`uuid`, `datetime`, `getpass`). No new dependency.

**Storage**: unchanged files (`<theatre>/.troupe/events.sqlite3`, lock file); the stored
`LeafChanged` event gains six fields.

**Testing**: pytest; end-to-end tests drive the real CLI on real theatres with controlled
`TROUPE_ACTOR` and `LOGNAME`, parse `history` JSON Lines and check lineage values, grouping and
timestamps (bounded by times taken before and after each command); unit tests for actor parsing,
login-name fallback and timestamp format.

**Target Platform**: macOS and Linux

**Project Type**: CLI (single Python package, `src/` layout)

**Performance Goals**: none (constitution).

**Constraints**: lineage immutable once recorded; invalid actor detected before any load or write;
`mypy --strict` and ruff clean.

**Scale/Scope**: one new module, changes to `store.py`, `sync.py`, `commands.py`, `cli.py`, test
fixtures; README.

No NEEDS CLARIFICATION remains: every technical point is resolved in [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle / constraint | How the plan satisfies it | Status |
|---|---|---|
| I. User's files are sacred | No change to loading or write-back. An invalid `TROUPE_ACTOR` or `--reason` misuse is rejected before loading, so no file is touched (tests compare theatre bytes before and after). The `TROUPE_ACTOR` error names the variable (and FR-008's "path or file" is about configuration; the actor has neither). | PASS |
| II. Tests that prove behaviour | Each FR-300 – FR-332 and each acceptance scenario maps to an e2e test on real theatres through the real CLI (actor per source, `via` per unit, grouping across import/reconcile/set in one invocation, reason scoping, `at` bounds and format, persistence across processes with a different actor, every invalid actor form on every subcommand). `conftest` removes any inherited `TROUPE_ACTOR` so tests cannot pass by accident of the developer's environment. | PASS |
| III. Done means verified | Gates in [quickstart.md](quickstart.md) — pytest, `mypy --strict`, ruff — run and shown. | PASS |
| IV. One decision, one place | `lineage.py`: env var name, actor grammar, unknown actor, login-name rule, `at` format, change-id rule. Which unit gets which `via`/actor: `open_theatre` (import, file) and `set_value` (cli). JSON field order: `history`. Pre-step-4 stores: no code (L-8). | PASS |
| V. Deliver what was asked | Every contract bullet maps to FRs; open choices recorded (spec D-30 – D-38, research L-1 – L-8). Nothing beyond the contract is added (no actor on reads, no lineage filters). | PASS |
| VI. Traceability | Spec supersedes step 2's "no source field" assumption explicitly; README gains `TROUPE_ACTOR`, `--reason` and the history fields in the same change as the code; code comments at `lineage.py` and the stamping sites cite the spec. | PASS |
| Tech constraints | Python 3.12+/uv; `uv run troupe config …`; history stays in the `eventsourcing` store; config location unchanged; macOS/Linux (`getpass` login name); no perf work. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/004-config-lineage/
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
├── cli.py                     # + `set --reason TEXT`; actor_from_env() before dispatch; actor → set_value
└── config/
    ├── lineage.py             # NEW: ACTOR_ENV, Actor, UNKNOWN_ACTOR, Lineage.begin, actor_from_env,
    │                          #      login_name, format_at, new_change_id (L-2 – L-6)
    ├── store.py               # LeafChanged + lineage args; HistoryRecord.lineage;
    │                          # import_leaves(leaves, lineage), record(events, lineage)
    ├── sync.py                # reconcile stamps Lineage.begin(UNKNOWN_ACTOR, "file")
    └── commands.py            # open_theatre: import lineage; set_value(actor, reason); history prints lineage
tests/
├── conftest.py                # strip TROUPE_ACTOR from inherited env; set LOGNAME; history helper unchanged
├── e2e/
│   ├── test_lineage_actor.py      # US1: actor + via per source; TROUPE_ACTOR forms; login name
│   ├── test_lineage_change.py     # US2: grouping within units, distinct across units, PATH filter
│   ├── test_lineage_when_why.py   # US3: --reason scoping, "" reason, at format/bounds/shared per unit
│   ├── test_lineage_persist.py    # US4: lineage identical across processes and actors
│   ├── test_lineage_watch.py      # watch reconcile → file/unknown; set under watch keeps its lineage
│   ├── test_lineage_errors.py     # invalid TROUPE_ACTOR on every subcommand → 2, nothing recorded/written
│   ├── test_history.py            # existing exact-line assertions updated to include lineage keys
│   └── test_usage.py              # + --reason misuse
└── unit/
    └── test_lineage.py        # actor_from_env grammar; login_name fallback; format_at
```

Existing tests that compare whole history lines (`test_history.py`, `test_reconcile.py`,
`test_watch*.py`, `test_state.py`) are updated to compare the step 1 fields and check lineage
separately, so they keep proving what they proved.

**Structure Decision**: Keep the existing layout; lineage is one new decision area and gets one new
module.

## Design overview

1. **`lineage.py`**
   - `ACTOR_ENV = "TROUPE_ACTOR"`; `ActorKind = Literal["human", "agent", "unknown"]`;
     `Actor(kind, id)`; `UNKNOWN_ACTOR = Actor("unknown", None)`.
   - `actor_from_env(environ: Mapping[str, str]) -> Actor`: absent → `Actor("human", login_name())`;
     `kind, sep, ident = value.partition(":")`; valid iff `sep` and `kind in ("human", "agent")` and
     `ident`; else `UsageError(f"{ACTOR_ENV}: {value!r} is not human:<id> or agent:<id>")`.
   - `login_name()`: `getpass.getuser()` or `None` on `OSError`/`KeyError`/empty.
   - `format_at(moment)`: `%Y-%m-%dT%H:%M:%S.%fZ` of a UTC datetime.
   - `Lineage(actor, via, at, reason, change)`; `Lineage.begin(actor, via, reason=None)` sets
     `at = format_at(datetime.now(UTC))`, `change = str(uuid4())`.
2. **`store.py`**: `TheatreConfig.change(op, path, old, new, actor_kind, actor_id, via, at, reason,
   change)`; the applied body appends `HistoryRecord(seq, op, path, old, new, Lineage(...))`.
   `import_leaves(leaves, lineage)` and `record(events, lineage)` pass the lineage's fields for each
   event; `record` still returns early on an empty list.
3. **`sync.reconcile(loaded, store)`**: `store.record(events, Lineage.begin(UNKNOWN_ACTOR, "file"))`.
4. **`commands.py`**
   - `open_theatre`: `store.import_leaves(..., Lineage.begin(UNKNOWN_ACTOR, "import"))`.
   - `set_value(theatre, path_text, value_text, actor, reason)`: after `apply_set`,
     `store.record(events, Lineage.begin(actor, "cli", reason))` — begun after the reconcile, so its
     `change` and `at` are its own.
   - `history`: entry adds `actor: {"kind", "id"}`, `via`, `at`, `reason`, `change` after `new`.
5. **`cli.py`**: `set` gets `--reason` (`metavar="TEXT"`, default `None`); in `run`, after
   `parse_args`, `actor = actor_from_env(os.environ)` for every subcommand, then dispatch; only `set`
   uses it.
6. **Docs**: README — `TROUPE_ACTOR`, `set --reason`, history line example with lineage; link to
   `specs/004-config-lineage/`.

## Post-design Constitution Check

Re-evaluated after writing research.md, data-model.md, contracts/cli.md and quickstart.md: all rows
above remain PASS. The deliberate non-handling of pre-step-4 stores (L-8) follows Principle V and the
spec's "Out of contract" list rather than adding speculative migration code. No violation;
Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify.
