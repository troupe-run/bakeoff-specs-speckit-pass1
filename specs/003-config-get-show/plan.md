# Implementation Plan: troupe configuration — `get` for values, `show` for anything (Step 3)

**Branch**: `main` (spec dir `003-config-get-show`) | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-config-get-show/spec.md`

## Summary

Rename step 1's `show` to `get`, with a hint to use `config show` when PATH is a mapping or list
(research G-1). Add a new `show [PATH] [--sources]` that prints scalars like `get` and collections
(or the whole configuration) as block-style YAML, written by a new `config/view.py` that walks the
located tree the loader already builds. Each scalar line carries its source file, which `--sources`
appends as ` # from <file>` (G-2, G-4). Scalar and literal-block spelling reuse `edit/render.py`
(G-3). Both commands import and reconcile first, like every command except `history`, and write no
configuration file.

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`)

**Primary Dependencies**: unchanged — `eventsourcing` (SQLite), `ruamel.yaml` (used for reading only;
`show`'s YAML is written by our own renderer, research G-2). No new dependency.

**Storage**: unchanged (`<theatre>/.troupe/events.sqlite3`, lock file).

**Testing**: pytest; end-to-end tests drive the real CLI on real theatres and compare stdout
byte-for-byte; read-back tests parse `show` output with ruamel (safe loader) and compare it with the
configuration; file snapshots prove nothing is written.

**Target Platform**: macOS and Linux

**Project Type**: CLI (single Python package, `src/` layout)

**Performance Goals**: none (constitution).

**Constraints**: byte-exact output layout (spec FR-220 – FR-234); `get` output identical to step 1
`show`; `mypy --strict` and ruff clean.

**Scale/Scope**: one new subcommand (`get`), one changed subcommand (`show`), one new module.

No NEEDS CLARIFICATION remains: every technical point is resolved in [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle / constraint | How the plan satisfies it | Status |
|---|---|---|
| I. User's files are sacred | `get` and `show` only read configuration files; tests compare the theatre's bytes before and after (SC-204). Errors name the path or file (existing `resolve`/load errors; the new `get` message names PATH). | PASS |
| II. Tests that prove behaviour | Every FR maps to an e2e test with exact expected stdout on real theatres (main file, nested YAML includes, text includes, outside-theatre include, CRLF, empty collections, quoting); read-back tests prove FR-214; existing step 1 `show` tests move to `get` so they keep proving SC-201. | PASS |
| III. Done means verified | Gates in [quickstart.md](quickstart.md) — pytest, `mypy --strict`, ruff — run and shown. | PASS |
| IV. One decision, one place | `show` layout and indentation step: `view.py`; scalar spelling, literal blocks: existing `render.py`; source label: `view.source_label`; "what every command does first": existing `open_theatre`; the `get` hint wording: one constant/function in `commands.py`. | PASS |
| V. Deliver what was asked | Every contract bullet maps to FRs (FR-200 – FR-240); open choices recorded (spec D-20 – D-26, research G-1 – G-7). D-22 was revised during planning (resolved paths) and the spec updated. | PASS |
| VI. Traceability | Spec states step 1 FR-015 is replaced; README and step 1 contract references to `show PATH` updated in the same change as the code; code comments at `view.py` and the `get` hint cite the spec. | PASS |
| Tech constraints | Python 3.12+/uv; `uv run troupe config get|show`; `eventsourcing` store unchanged; config location unchanged; macOS/Linux; no perf work. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/003-config-get-show/
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
├── cli.py                     # + `get PATH`; `show [PATH] [--sources]`
└── config/
    ├── view.py                # NEW: render(node, theatre, sources) -> str; source_label (G-2, G-4)
    └── commands.py            # show → get (+ `config show` hint); new show(); both via open_theatre(reconcile=True)
tests/
├── e2e/
│   ├── test_get.py            # moved from test_show.py: scalar printing, includes, CRLF text, non-ASCII
│   ├── test_get_errors.py     # moved from test_show_errors.py; + mapping/list → 5 with `config show`
│   ├── test_get_import.py     # moved from test_show_import.py (+ get reconciles)
│   ├── test_show.py           # NEW content: scalars like get; sections/whole config as exact YAML
│   ├── test_show_sources.py   # --sources: main/nested/text/outside-theatre includes, scalar, empty
│   ├── test_show_readback.py  # show output parses back to the configuration
│   └── test_usage.py          # + get/show usage errors
└── unit/
    └── test_view.py           # layout rules: quoting, literal chomping/indicator, compact items, {} []
```

**Structure Decision**: Keep the existing layout. The YAML view is a new decision (spec D-21) and
gets its own module; `render.py` stays the single place for scalar spelling.

## Design overview

1. **`commands.get(theatre, path_text)`**: exactly step 1 `show`, with the collection error
   `f"{path}: is {kind}, not a scalar; use `troupe config show {path}` to print it"` (FR-202).
2. **`commands.show(theatre, path_text | None, sources)`**: parse PATH if given; under `theatre_lock`,
   `open_theatre(reconcile=True)`; `node = resolve(root, path)` or `root`; if not `sources` and the
   node is a scalar/text include → `format_scalar(node.value)`; else
   `view.render(node, theatre, sources)`.
3. **`view.render`**: walk the tree producing `(text, source | None)` lines (data-model "View line"):
   - mapping: for each entry, key spelled by `render_key(key, PLAIN, False)`; scalar value → one line
     `key: spelled` with source; literal → `key: |…` header with source, content lines without;
     empty collection → `key: {}`/`key: []`; non-empty collection → `key:` then children at
     `column + STEP`.
   - list: items `- …` the same way; non-empty collection items in compact form.
   - top-level scalar (only with `--sources`): spelled alone; literal content at column 2.
   - empty root mapping → `{}`.
   Join with ` # from <label>` where sources are requested; each line + `\n`.
4. **CLI**: `get` subparser with required PATH; `show` with optional PATH and `--sources`.
5. **Docs**: README command table (`get`, `show [PATH] [--sources]`); note in step 1 contract that
   `show PATH` is superseded by step 3.

## Post-design Constitution Check

Re-evaluated after writing research.md, data-model.md, contracts/cli.md and quickstart.md: all rows
above remain PASS. `view.py` repeats the block layout shape that `render_block` uses for `set`, but
with different inputs (located nodes with sources) and a different decision behind it (spec D-21 vs
step 1 FR-029); research G-2 records why sharing it would couple the read-only view to the write
path. No violation; Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify.
