# Implementation Plan: troupe configuration — load, show, set, history (Step 1)

**Branch**: `main` (spec dir `001-config-load-show-set`) | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-config-load-show-set/spec.md`

## Summary

Build the `troupe config` CLI (`show`, `set`, `history`) over a theatre's hand-edited YAML
configuration, with `file:` includes. Values are always read from the files (spec D-1). Each file
is parsed with `ruamel.yaml`'s composer only to get exact source spans, and values are typed by our
own YAML 1.2 core-schema resolver. `set` is computed as text splices on the one file that holds the
value, then checked by re-loading the edited configuration in memory, and only then written
atomically (research R-7). If the check fails, nothing is written and the command exits 3. Changes
are recorded per leaf as events of a single `eventsourcing` aggregate persisted in SQLite under
`.troupe/`; `history` prints them as JSON Lines.

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`)

**Primary Dependencies**: `eventsourcing` (≥9.5, mandated; SQLite persistence module), `ruamel.yaml`
(≥0.18; parsing and source positions only). Dev: `pytest`, `mypy`, `ruff`.

**Storage**: The configuration files themselves (source of truth for values); the event store is
`<theatre>/.troupe/events.sqlite3`.

**Testing**: pytest. End-to-end tests run the real `troupe` CLI as a subprocess against real
theatres in `tmp_path` and compare files byte for byte. Unit tests cover the pure modules.

**Target Platform**: macOS and Linux

**Project Type**: CLI (single Python package, `src/` layout)

**Performance Goals**: None (configurations are small; constitution)

**Constraints**: Byte-surgical write-back (FR-025); atomic file replacement; state only under
`.troupe/`; `mypy --strict` and ruff clean.

**Scale/Scope**: Three subcommands; a configuration of a few files and at most hundreds of leaves.

No NEEDS CLARIFICATION remains: every open technical point is resolved in [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle / constraint | How the plan satisfies it | Status |
|---|---|---|
| I. User's files are sacred | Edits are splices of only the bytes the rules require (R-7–R-12); verify-before-write refuses (exit 3) rather than risk corruption; atomic replace (R-6); no write on no-op (D-7); every error names its path/file (R-14). | PASS |
| II. Tests that prove behaviour | Each FR and each write rule gets an end-to-end test using real files and the real CLI, checked by exact bytes (R-15); tasks must include deliberately-break checks. | PASS |
| III. Done means verified | Quality gates in [quickstart.md](quickstart.md) — pytest, `mypy --strict`, ruff — run and shown before completion. | PASS |
| IV. One decision, one place | Exit codes in `errors.py`; file names/state path in `files.py`/`store.py` constants; typing in one resolver; style representability in `render.py`; line geometry in `layout.py`. No speculative abstractions for later steps. | PASS |
| V. Deliver what was asked | All contract sections in force are mapped to FRs; open choices recorded (spec D-1–D-9, research B-1–B-12). Nothing beyond the three subcommands. | PASS |
| VI. Traceability | Spec ↔ research ↔ code comments at the one place holding each decision; small commits with "why". | PASS |
| Tech constraints | Python 3.12+/uv, `uv run troupe config …`, `eventsourcing` used, config file location as given, macOS/Linux, no perf work. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/001-config-load-show-set/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/cli.md     # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
pyproject.toml                 # uv project; console script troupe = "troupe.cli:main"
src/troupe/
├── __init__.py
├── __main__.py                # python -m troupe
├── cli.py                     # argparse; maps TroupeError → stderr + exit code
├── errors.py                  # TroupeError, UsageError(2), WriteRefused(3), LoadError(4), PathError(5)
└── config/
    ├── __init__.py
    ├── paths.py               # ConfigPath parsing
    ├── scalars.py             # YAML 1.2 core-schema resolver; scalar printing; VALUE parsing
    ├── files.py               # config-file discovery; read (newline-preserving); atomic write
    ├── tree.py                # Located node types
    ├── loader.py              # compose files, follow includes, detect cycles → located tree
    ├── leaves.py              # flatten tree → ordered leaves; event diff
    ├── store.py               # eventsourcing aggregate + application (SQLite under .troupe/)
    ├── commands.py            # show / set / history orchestration (import-on-first-use)
    └── edit/
        ├── __init__.py
        ├── planner.py         # where a change goes (rules 1–4), chooses the operation
        ├── render.py          # scalar styles, double-quote escaping, block/flow collection text
        ├── layout.py          # lines, indentation, EOL comments/columns, insertion points
        ├── folded.py          # folded-scalar paragraph alignment and re-wrapping
        └── apply.py           # apply splices, re-load and verify, then write
tests/
├── conftest.py                # Theatre fixture: write files, snapshot bytes, run CLI
├── e2e/                       # subprocess CLI tests: show, set (one module per rule group), history, errors
└── unit/                      # scalars, render, layout, folded, paths
```

**Structure Decision**: Single package with a `config` subpackage, because Step 1 is only the
configuration subsystem; the `edit` subpackage isolates the byte-surgical writer, which is the part
most likely to change in later steps (e.g. step 5 changes rule 2 — a one-place change in
`planner.py`).

## Design overview

1. **Load** (`loader.py`): discover the config file (FR-002), compose it, walk nodes building
   located nodes; on a `file:` string, resolve relative to the containing file's directory, check
   for a cycle against the current include chain, and either embed the composed target (YAML) or
   make a text-include leaf. Errors → `LoadError` naming the file.
2. **Import** (`commands.py` + `store.py`): after a successful load, if the aggregate does not exist,
   create it and save one `import` event per leaf (D-2).
3. **show**: resolve PATH in the tree → scalar → print per FR-006; else `PathError`.
4. **set**: parse VALUE (R-3); `planner` resolves PATH (B-1), applies rules 1–4, and asks
   `render`/`layout`/`folded` for splices; `apply` re-loads with the new text, verifies (R-7),
   derives events, writes atomically, then saves events. No-op → nothing written or saved.
5. **history**: load (and import if needed), read events, filter by PATH prefix rule, print JSON
   Lines (B-11).

## Post-design Constitution Check

Re-evaluated after writing research.md, data-model.md, contracts/cli.md and quickstart.md: all rows
above remain PASS. The verify-before-write step (R-7) strengthens Principle I. The one temporary
file created during an atomic write (R-6) lives only for the duration of the write, so no extra
files remain afterwards (FR-003). No violations, so Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify.
