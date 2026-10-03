# Implementation Plan: troupe configuration — keep files and configuration in sync (Step 2)

**Branch**: `main` (spec dir `002-config-file-sync`) | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-config-file-sync/spec.md`

## Summary

Add **reconcile**: compare the leaves loaded from the files with the leaves of the event-sourced
projection and record a `set`/`remove` event per difference, reusing step 1's `diff_events` (research
S-1). `show`, `set` and the new `watch` reconcile right after loading; `history` does not (S-2). Add
`troupe config watch`, which reconciles, snapshots the exact bytes of every file it parsed, prints
`watching <dir>`, then polls those bytes every 0.2 s and reconciles on any difference (S-4); it
survives broken files (S-5) and exits 0 on SIGINT/SIGTERM (S-6). One cross-process `flock` lock, held by
every command from loading until its events are recorded, makes every change recorded exactly once —
so a `set`'s own write-back is never recorded again by `watch` (S-3).

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`)

**Primary Dependencies**: unchanged — `eventsourcing` (SQLite), `ruamel.yaml`. Standard library only for
the new parts (`fcntl`, `signal`, `threading`). No new dependency (research S-4 rejects `watchdog`).

**Storage**: unchanged event store `<theatre>/.troupe/events.sqlite3`; new empty lock file
`<theatre>/.troupe/events.sqlite3.lock`.

**Testing**: pytest; end-to-end tests drive the real CLI, with `watch` run via `subprocess.Popen` and
stopped by real signals (research S-9).

**Target Platform**: macOS and Linux (`fcntl.flock`, POSIX signals)

**Project Type**: CLI (single Python package, `src/` layout)

**Performance Goals**: none beyond the contract's 2-second reconcile window (met by 0.2 s polling).

**Constraints**: watch writes no configuration file; exactly-once recording across processes; stdout of
`watch` is exactly one line; `mypy --strict` and ruff clean.

**Scale/Scope**: one new subcommand, one new behaviour on existing commands; small configurations.

No NEEDS CLARIFICATION remains: every technical point is resolved in [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle / constraint | How the plan satisfies it | Status |
|---|---|---|
| I. User's files are sacred | Reconcile and `watch` only read configuration files (D-17); `set`'s write path is unchanged. Conservative choices recorded: broken file while watching → report and keep going, record nothing (D-13); reconcile is atomic (FR-115). Every new error names its file (load errors, lock file). | PASS |
| II. Tests that prove behaviour | Each FR maps to e2e tests on real files and real processes/signals; exactly-once is proved by comparing full histories with and without `watch`; the lock is proved necessary by a test that holds it (S-9). | PASS |
| III. Done means verified | Gates in [quickstart.md](quickstart.md) — pytest, `mypy --strict`, ruff — run and shown. | PASS |
| IV. One decision, one place | "What differs" = existing `diff_events`; "who reconciles" = `open_theatre(reconcile=…)`; lock name/acquisition = `lock.py`; poll interval and snapshot = `watch.py`; `<dir>` display = one function in `cli.py`. No speculative abstraction (no pluggable watcher back-ends). | PASS |
| V. Deliver what was asked | Every contract bullet maps to FRs (FR-100 – FR-131); open choices recorded (spec D-10 – D-17, research S-1 – S-9); no history `source` field invented. | PASS |
| VI. Traceability | Step 1 D-1 marked superseded in this spec; spec FR-114 adjusted to the projection order the design uses; code comments at the lock and reconcile sites cite the spec. | PASS |
| Tech constraints | Python 3.12+/uv; `uv run troupe config watch`; `eventsourcing` remains the store (projection read, events appended through it); config location unchanged; macOS/Linux only (`fcntl`); no perf work. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/002-config-file-sync/
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
├── cli.py                     # + `watch` subparser; watching-line display (D-11); announce callback
└── config/
    ├── store.py               # + ConfigStore.leaves() (the projection)
    ├── lock.py                # NEW: theatre_lock(theatre), LOCK_FILENAME (S-3)
    ├── sync.py                # NEW: reconcile(loaded, store) -> list[LeafEvent] (S-1)
    ├── watch.py               # NEW: snapshot, poll loop, broken state, signal handling (S-4–S-6)
    └── commands.py            # open_theatre(reconcile=…); show/set/history under the lock; watch()
tests/
├── conftest.py                # + Watcher fixture: Popen, read first line with timeout, signal, kill on failure
├── e2e/
│   ├── test_reconcile.py      # edits between commands; format/comment-only; history never reconciles; failing commands
│   ├── test_watch.py          # line/promise, edits in main/include/text include, save-by-rename, new/removed include, broken file, signals
│   └── test_watch_exactly_once.py  # set under watch; hand edit + set; lock-held test
└── unit/
    ├── test_reconcile.py      # changed/added/removed/type-only/no-op/order
    └── test_lock.py           # lock is held when set records its events
```

**Structure Decision**: Keep the step 1 layout. Reconcile, lock and watch each get their own small
module under `config/` because each holds one decision (Principle IV); `commands.py` stays the place
that orchestrates what every command does before its own work.

## Design overview

1. **Lock** (`lock.py`): `with theatre_lock(theatre):` opens/creates the lock file and takes a blocking
   exclusive `flock`; released on exit (or process death).
2. **open_theatre(theatre, reconcile)**: load → `ConfigStore` → if not imported, import; elif
   `reconcile`, `store.record(reconcile(loaded, store))`. Must be called with the lock held.
3. **show**: parse PATH; `with theatre_lock`: `open_theatre(reconcile=True)`; resolve and format.
4. **set**: parse PATH and VALUE; `with theatre_lock`: `open_theatre(reconcile=True)`, `apply_set`,
   `store.record`. The `before` leaves equal the projection, so the recorded events are exactly the
   `set`'s own (FR-130).
5. **history**: `with theatre_lock`: `open_theatre(reconcile=False)`; print events.
6. **watch** (`watch.py`): install signal handlers → under the lock, `open_theatre(reconcile=True)` and
   build the snapshot from `Loaded.files` + config-name candidates (LoadError here → exit 4) → announce
   `watching <dir>` → loop until stopped: wait 0.2 s; if broken or any snapshot path's bytes differ,
   reconcile under the lock and rebuild the snapshot; on `TroupeError` enter broken state and report the
   message once (S-5).
7. **CLI**: `watch` subparser without positionals; `run()` passes `display` and an announce function
   that writes and flushes stdout; returns `""` → exit 0.

## Post-design Constitution Check

Re-evaluated after writing research.md, data-model.md, contracts/cli.md and quickstart.md: all rows
above remain PASS. The one new state file (`events.sqlite3.lock`) lives under `.troupe/` as step 1
FR-003 allows. The lock adds a small amount of mechanism, but it is the minimum that makes FR-130/FR-131
hold across processes (research S-3 lists the simpler alternatives and why they fail), so it is not a
violation. Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify.
