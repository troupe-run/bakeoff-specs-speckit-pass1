# Implementation Plan: troupe configuration — remote includes and a schema (Step 7)

**Branch**: `main` (spec dir `007-remote-includes-schema`) | **Date**: 2026-10-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-remote-includes-schema/spec.md`

## Summary

Treat `https://`/`http://` strings as includes fetched at load time, and make remote content
read-only. Add an optional JSON Schema at `.troupe/troupe.schema.json` that validates the loaded
configuration and marks `format: uri` strings as literals, alongside a `!literal` tag. Make `set`
tag include-like strings `!literal` unless `--include` is given.

How it is done:

- A source's location becomes `Path | str` (a URL for fetched content). Every write must go
  through `local_path`, and mypy enforces that, so writes into remote content are refused in one
  place (research U-2). The refusal message names the include line on PATH's route (U-7).
- The loader passes each node's subschema down as it builds, so a string is classified as include
  or literal before anything is fetched (U-5).
- Validation runs inside `load`. Every command gets exit 4 for an invalid configuration, and `set`'s
  existing re-check turns a would-be-invalid result into exit 3 (U-6).
- Include-like VALUE strings are tagged before planning and spelled by the renderer, so no
  placement code changes (U-8).

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`)

**Primary Dependencies**: `ruamel.yaml` and `eventsourcing` as before. New: `jsonschema` (≥4.23,
Draft 2020-12 validator, with `referencing`), which is the reference implementation (U-12). Fetching
uses the standard library's `urllib.request`, so there is no HTTP dependency.

**Storage**: the event store is unchanged. A new optional input file is
`.troupe/troupe.schema.json`. Remote documents are fetched per command and never stored.

**Testing**: pytest. The e2e tests drive the real CLI against real theatres and a local HTTP/HTTPS
fixture server (with an `openssl` self-signed certificate passed via `SSL_CERT_FILE`). They compare
the bytes of every file and count server requests. Unit tests cover the schema lookup, the include
classification and literal marking (U-11).

**Target Platform**: macOS and Linux

**Project Type**: CLI (single Python package, `src/` layout)

**Performance Goals**: none (constitution). There is one fetch per URL per command, with a 10 s
limit per fetch.

**Constraints**: nothing is ever written to remote content. Refusals change no file and record no
event. A URL at a `format: uri` path or tagged `!literal` is never fetched. `mypy --strict` and ruff
must be clean.

**Scale/Scope**:

- New modules: `includes.py`, `fetch.py`, `schema.py`, `remote.py` and `edit/literals.py`.
- Changed: `files.py`, `loader.py`, `scalars.py`, `edit/render.py`, `edit/planner.py`,
  `edit/apply.py`, `edit/alias.py`, `view.py`, `watch.py`, `commands.py` and `cli.py`.
- Also: tests, the README, the step 1 spec note and `pyproject.toml`.

No NEEDS CLARIFICATION remains. Every technical point is resolved in [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle / constraint | How the plan satisfies it | Status |
|---|---|---|
| I. User's files are sacred | Remote content is never written. The type system forces every write through `local_path` (U-2). A `!literal` tag is added only where the contract requires it, and an existing tag is kept for the smallest diff (D-67). Refusals (remote, schema, `--include` at a `format: uri` path) happen before any write, and writes stay atomic and re-checked. All error messages name the file, URL or path (FR-650). | PASS |
| II. Tests that prove behaviour | Every FR-600 – FR-650 and acceptance scenario maps to an e2e test against real HTTP(S) responses (U-11), with no stubbed fetch. "Nothing fetched" is proven by the server's request log, and file preservation by byte comparison. | PASS |
| III. Done means verified | The gates in [quickstart.md](quickstart.md) (pytest, `mypy --strict`, ruff) are run and their output shown. | PASS |
| IV. One decision, one place | Each decision has one home. **Include prefixes and the tag name:** `includes.py`. **Fetch rules and timeout:** `fetch.py`. **YAML-or-text:** `files.YAML_SUFFIXES` through `is_yaml_name`/`is_yaml_url`. **Schema location, lookup and validation:** `schema.py`. **Literal decision while loading:** `_Loader.is_include`. **Literal decision for `set`:** `literals.mark`. **Tag spelling:** `render`. **Remote refusal and message:** `remote.py`/`files.local_path`. | PASS |
| V. Deliver what was asked | Every contract bullet maps to FRs. Open choices are recorded (spec D-60 – D-70, research U-1 – U-12). Nothing outside the contract is added: no auth, caching, format assertion or schema editing. | PASS |
| VI. Traceability | The step 1 FR-010 note "extended by step 7" and the README section ship in the same change as the code. Code comments cite FR/D numbers at each decision site. | PASS |
| Tech constraints | Python 3.12+/uv; `uv run troupe config …`; `eventsourcing` store unchanged; config location unchanged; macOS/Linux; no performance work. Adding a dependency is permitted (the constraints fix the language, tool and event library, not an exhaustive list). | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/007-remote-includes-schema/
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
├── includes.py        # NEW: FILE_PREFIX, REMOTE_PREFIXES, LITERAL_TAG, REF_KEY, include_ref (U-1)
├── fetch.py           # NEW: fetch(url), FETCH_TIMEOUT; failures → LoadError (U-3)
├── schema.py          # NEW: SCHEMA_NAME, load_schema, Schema.child/validate, is_uri (U-5, U-6)
├── remote.py          # NEW: remote_site, refuse_remote (U-7)
├── files.py           # SourceFile.path: Path | str; is_yaml_url; local_path; RemoteSource (U-2, U-4)
├── loader.py          # sub-schema threaded through build; is_include; URL includes; D-61; validate;
│                      # Loaded.remote/schema; load/reload accept fetched documents (U-3 – U-6)
├── scalars.py         # LITERAL_TAG in resolve_node; content_start skips !literal; NewScalar.tag (U-8)
├── view.py            # source_label: URL for remote sources (U-10)
├── watch.py           # snapshot includes the schema file (U-6)
├── commands.py        # set_value(include=…) → literals.mark (U-8)
└── edit/
    ├── literals.py    # NEW: mark(value, path, schema, include) (U-8)
    ├── render.py      # tag prefix in render_inline / render_literal header (U-8)
    ├── planner.py     # _replace_scalar: keep or (with --include) remove an existing tag (U-8)
    ├── apply.py       # local_path at the write; RemoteSource → refuse_remote; reload with fetched (U-2, U-3, U-7)
    └── alias.py       # local_path before expansion; reload with fetched (U-2, U-3)
src/troupe/cli.py      # set --include (U-9)
tests/
├── conftest.py                       # web / web_tls fixtures; proxy variables dropped (U-11)
├── e2e/
│   ├── test_remote_read.py           # US1: YAML/text/query, --sources, overrides, nested, import
│   ├── test_remote_errors.py         # US1 sc.5, D-61, cycles, redirect, 10 s limit, TLS
│   ├── test_remote_readonly.py       # US2: each FR-610 case, message contents, overrides allowed
│   ├── test_literals.py              # US3: format uri via properties/additionalProperties/items, !literal
│   ├── test_schema_validation.py     # US4: invalid on load, invalid set, bad schema files
│   ├── test_set_literal.py           # US5: tagging matrix, --include, existing tag, collections
│   └── test_usage.py                 # --include on other subcommands → exit 2
└── unit/
    ├── test_schema_lookup.py         # Schema.child, is_uri, $ref/$schema checks
    └── test_includes.py              # include_ref, is_yaml_url, literals.mark
```

**Structure Decision**: keep the existing layout. Each new decision area (fetching, the schema, the
remote refusal, literal marking) gets one small module. Existing modules change only where they
read sources or spell scalars.

## Design overview

1. **Includes** (`includes.py`): the prefixes, the tag name and `include_ref`. Callers that used
   `loader.INCLUDE_PREFIX`/`include_target` switch to these.
2. **Sources** (`files.py`): `SourceFile.path: Path | str`, `is_yaml_url`, `RemoteSource(WriteRefused)`
   and `local_path`. `atomic_write`/`check_writable` keep taking `Path`.
3. **Fetch** (`fetch.py`): urllib with a total deadline, 2xx only and strict UTF-8. Errors become
   `LoadError` naming the URL and the including file.
4. **Schema** (`schema.py`): load and check the schema file (dialect, validity, local `$ref`s only);
   `child` lookup; `is_uri`; `validate(value)` with no format checker.
5. **Loader**: `build(..., sub)` threads the subschema. `is_include` combines prefix, tag and
   schema. `include` dispatches `FileRef`/`UrlRef`; a `FileRef` from a remote source → `LoadError`.
   The chain holds `Path | str`. `!literal` on a collection → `LoadError`. After building,
   `schema.validate(to_value(root))`. `Loaded` gains `remote` and `schema`. `load`/`reload` accept
   `fetched`.
6. **`set`**: `commands.set_value` loads, then `literals.mark` (which may refuse, D-68), then
   `apply_set`. The renderer prefixes the tag. `_replace_scalar` keeps an existing tag, or removes
   it with `--include`. `apply` resolves `local_path(plan.file)` before re-checking and writing, and
   turns a `RemoteSource` into `refuse_remote(loaded, path, …)`. The re-check reloads with
   `fetched=loaded.remote`, so schema failures surface as exit 3 through the existing
   "would not load back".
7. **Views and watch**: `source_label` returns the URL for remote sources. `snapshot_of` adds the
   schema path.
8. **Docs**: a README section. The step 1 spec FR-010 gets "extended by step 7". `uv add jsonschema`.

## Post-design Constitution Check

Re-evaluated after writing research.md, data-model.md, contracts/cli.md and quickstart.md. All rows
above remain PASS. The one new dependency replaces what would otherwise be a hand-written validator
(Principle V: invent nothing). Each new module holds a decision the contract makes in this step. No
violation; Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify.
