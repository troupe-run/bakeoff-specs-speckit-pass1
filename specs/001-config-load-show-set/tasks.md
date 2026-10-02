---

description: "Task list for troupe configuration — load, show, set, history (Step 1)"
---

# Tasks: troupe configuration — load, show, set, history (Step 1)

**Input**: Design documents from `specs/001-config-load-show-set/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: MANDATORY. Constitution Principle II overrides the template's "tests are optional". Every
behaviour gets a test that fails when the behaviour breaks. End-to-end tests run the real `troupe`
CLI as a subprocess against real theatres in `tmp_path`, and file-preservation is checked by
comparing the exact bytes of every file under the theatre (research R-15). For each test task, write
the tests first and see them fail. After the implementation passes them, break the behaviour
deliberately once to confirm the test catches it.

**Organization**: Grouped by user story (spec.md): US1 read a setting (P1), US2 change a setting
byte-surgically (P1), US3 history (P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3

## Path Conventions

Single project: `src/troupe/`, `tests/` at the repository root (plan.md → Project Structure).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: A runnable, typed, linted, empty `troupe` package.

- [X] T001 Create `pyproject.toml` with uv: project `troupe`, `requires-python = ">=3.12"`, dependencies `eventsourcing>=9.5` and `ruamel.yaml>=0.18`, dependency group `dev` = `pytest`, `mypy`, `ruff`, `[project.scripts] troupe = "troupe.cli:main"`, `src/` layout build backend (`uv_build`, else `hatchling`); configure `[tool.mypy] strict = true` (files `src`, `tests`), `[tool.ruff]` (line-length 100, target py312, lint select `E,F,W,I,UP,B,SIM,RUF`), `[tool.pytest.ini_options] testpaths = ["tests"]`; add `.gitignore` entries for `.venv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`; run `uv sync` and commit `uv.lock`
- [X] T002 Create the package skeleton per plan.md: `src/troupe/__init__.py`, `src/troupe/__main__.py` (calls `cli.main()`), `src/troupe/config/__init__.py`, `src/troupe/config/edit/__init__.py`, `tests/__init__.py`, `tests/e2e/__init__.py`, `tests/unit/__init__.py`
- [X] T003 Verify the gates run on the skeleton: `uv run pytest` (no tests collected is OK), `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Errors, CLI shell, paths, scalar typing, file discovery and reading, loading with includes, leaves, and the event store with import-on-first-use. Every story needs these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational

- [X] T004 [P] Write `tests/conftest.py`: a `Theatre` fixture (root `tmp_path`) with `write(relpath, text_or_bytes)` (relative to `.troupe/` by default), `snapshot() -> dict[str, bytes]` of every file under the theatre *excluding* the event-store files (`events.sqlite3*`), and `run(*args) -> CompletedProcess` that executes the venv's `troupe` console script (`shutil.which("troupe")`, falling back to `[sys.executable, "-m", "troupe"]`) with `--theatre <root>`, capturing stdout/stderr as text (`newline` untranslated); plus an `assert_failed(result, code, mention)` helper that checks the exit code, that stdout is empty, and that `mention` appears in stderr
- [X] T005 [P] Unit tests for the YAML 1.2 core-schema resolver in `tests/unit/test_scalars.py`: `null|Null|NULL|~|""(empty plain)` → None; `true|True|TRUE|false|False|FALSE` → bool; `yes`, `on`, `no` → str; `12`, `-3`, `0o17`, `0x1F` → int; `0.2`, `1e3`, `.5`, `-.inf`, `.NaN` → float; printing per FR-006 (`0.2` → `0.2`, `True` → `true`, `None` → `null`, string without trailing `\n` gets one, string ending in `\n` printed exactly)
- [X] T006 [P] Unit tests for VALUE parsing (research R-3) in `tests/unit/test_value_parse.py`: `0.2` float, `true` bool, `null` None, `abc` str, `"0.2"` str, `{a: 1}` dict, `[a, b]` list, `"line one\nline two\n"` multi-line str, `'[a'` / `''` / `a: b` / `- x` → `UsageError`
- [X] T007 [P] Unit tests for `ConfigPath` in `tests/unit/test_paths.py`: `a.b.0` → segments `("a","b","0")` with `0` an index; `""`, `a..b`, `.a`, `a.` → `UsageError`
- [X] T008 [P] E2E load-error tests in `tests/e2e/test_load_errors.py` (each asserts exit 4, empty stdout, stderr naming the file, and unchanged snapshot): no config file; both `troupe.yml` and `troupe.yaml`; YAML syntax error names that file; root that is a list (D-5); missing include target names the target; an include cycle `a.yaml → b.yaml → a.yaml` names a file in the cycle; a self-include; nonexistent `--theatre` directory. Also: an empty `troupe.yml` loads (any `show x` → exit 5, not 4)
- [X] T009 [P] E2E usage-error tests in `tests/e2e/test_usage.py`: no subcommand, unknown subcommand, `show` without PATH, `set` without VALUE, invalid VALUE `'[a'` → exit 2 with empty stdout and a stderr message; `--theatre` accepted before and after positionals; `--theatre` defaults to the current directory (run with `cwd=theatre root` and no `--theatre`)
- [X] T010 [P] E2E store-location test in `tests/e2e/test_state.py`: after any successful command, the only new files are under `<theatre>/.troupe/` and the config/include files' bytes are unchanged (FR-003); a smoke test that runs literally `uv run troupe config show a --theatre <dir>` from the repository root and gets the right output

### Implementation for Foundational

- [X] T011 [P] Implement `src/troupe/errors.py`: `TroupeError(message)` with class attribute `exit_code`; subclasses `UsageError` (2), `WriteRefused` (3), `LoadError` (4), `PathError` (5). Docstring: this is the one place exit codes are decided (Principle IV)
- [X] T012 [P] Implement `src/troupe/config/paths.py`: frozen `ConfigPath(segments: tuple[str, ...])` with `parse(text)` (split on `.`; empty text or empty segment → `UsageError` naming the path), `is_index(segment)` (ASCII digits only), `dotted`, `child(segment)`, `parent`
- [X] T013 [P] Implement `src/troupe/config/scalars.py`: `Scalar` / `Value` type aliases; `resolve_plain(text) -> Scalar` using the YAML 1.2 core-schema regexes (research R-2); `resolve_node(node)` for ruamel `ScalarNode` honouring style (quoted/block → str) and explicit standard tags; `format_scalar(value) -> str` per FR-006 (floats via `repr()`, non-finite as Python repr); `scalars_equal(a, b)` type-exact equality; `parse_value(text) -> tuple[Value, Node]` per research R-3 (compose with ruamel, exactly one node, scalar or flow collection, recursively typed; otherwise `UsageError` naming the VALUE)
- [X] T014 Implement `src/troupe/config/files.py`: constants `CONFIG_NAMES = ("troupe.yml", "troupe.yaml")`, `TROUPE_DIR = ".troupe"`; `find_config(theatre) -> Path` (neither/both → `LoadError` naming the path(s); missing theatre dir → `LoadError`); `SourceFile` dataclass (`path`, `text` decoded UTF-8 with line endings preserved, `newline` = `"\r\n"` if the first line ending is CRLF else `"\n"` (spec D-6), `kind` = `yaml` if the name ends `.yml`/`.yaml` else `text`); `read_source(path)` (missing/not a regular file/undecodable → `LoadError` naming the file); `atomic_write(path, text)` (research R-6: temp file in the same directory, write UTF-8 bytes without newline translation, fsync, copy mode bits, `os.replace`, remove temp on failure; no-op if bytes are identical, spec D-7)
- [X] T015 Implement `src/troupe/config/tree.py`: dataclasses `LocatedScalar(value, file, start, end, style, in_flow, node)`, `LocatedMapping(entries: list[tuple[LocatedScalar, Located]], file, flow, start, end, node)`, `LocatedSequence(items, file, flow, start, end, node)`, `TextInclude(value: str, include: LocatedScalar, target: SourceFile)`; every node has an optional `included_by: LocatedScalar | None` (set on the root of a YAML-included file) per data-model.md
- [X] T016 Implement `src/troupe/config/loader.py`: `load(theatre) -> Loaded` (root tree + dict of `SourceFile` by path) and `load_with_override(theatre, path, new_text)` (same, but one file's text is replaced — used for verify-before-write, research R-7). Compose each YAML file with `YAML(typ="rt").compose(text)`; composer/scanner errors → `LoadError` naming the file; multi-document input is out of contract. Main root must be a mapping or empty (empty → empty mapping) else `LoadError` (spec D-5). A string scalar starting with `file:` is an include: resolve the rest relative to the containing file's directory; detect cycles with the stack of files on the current include chain (cycle → `LoadError` naming the file); `.yml`/`.yaml` targets embed the composed root with `included_by` set; other targets become `TextInclude`. Mapping keys are scalars (key strings via `resolve_node`)
- [X] T017 Implement `src/troupe/config/leaves.py`: `leaves(tree) -> dict[str, Scalar]` in document order with includes expanded in place, list items as `list.0`, text includes as string leaves, empty collections contributing nothing (research B-12); `to_value(node) -> Value`; `diff_events(before, after) -> list[LeafEvent]` exactly as data-model.md "Event derivation for `set`" (`set` events in `after` order, then `remove` events in `before` order, type-exact comparison)
- [X] T018 Implement `src/troupe/config/store.py`: `TheatreConfig` aggregate with id `uuid5(NAMESPACE_URL, "troupe:theatre-config")`, state `leaves: dict[str, Scalar]`, single event method `LeafChanged(op, path, old, new)` where op is one of `"import" | "set" | "remove"` (remove deletes the path, others set it); `ConfigStore(theatre)` wrapping an `eventsourcing` `Application` constructed with `env={"PERSISTENCE_MODULE": "eventsourcing.sqlite", "SQLITE_DBNAME": str(<theatre>/.troupe/events.sqlite3)}` (constant `STORE_FILENAME`, research R-4/R-5); methods `is_imported()`, `import_leaves(leaves)` (create + one `import` event per leaf, `old` None, one `save()`), `record(events)` (one `save()`, no-op for empty list), `history() -> list[HistoryRecord]` with `seq` = 1-based position among `LeafChanged` events
- [X] T019 Implement `src/troupe/config/commands.py` skeleton: `open_theatre(theatre) -> (Loaded, ConfigStore)` that loads and, if the store is not imported, imports (spec D-2: import stands even if the command later fails); `resolve(tree, path) -> Located` raising `PathError` naming the dotted path for: missing key, digit segment on a mapping, non-digit on a list, descending below a scalar or text include, index out of range (research B-1)
- [X] T020 Implement `src/troupe/cli.py`: argparse with `config` → subparsers `show PATH`, `set PATH VALUE`, `history [PATH]`, each with `--theatre DIR` (default `.`); usage errors exit 2 via argparse with nothing on stdout; `main()` runs the command, catches `TroupeError` and prints `troupe: error: <message>` to stderr and exits with its `exit_code`; stdout written only on success (buffer output, write at the end)

**Checkpoint**: T004–T010 pass (except tests that need show/set/history behaviour, which pass after their stories); mypy and ruff clean.

---

## Phase 3: User Story 1 — Read a setting (Priority: P1) 🎯 MVP

**Goal**: `troupe config show PATH` prints a scalar from the main file, YAML includes (nested) and text includes.

**Independent Test**: Write a theatre with includes; run `show` for paths in each file; compare stdout and exit codes (spec US1 scenarios 1–6).

### Tests for User Story 1

- [X] T021 [P] [US1] E2E tests in `tests/e2e/test_show.py`: `model.temperature` → `0.2\n`; string `opus` → `opus\n`; string already ending in `\n` (literal block) printed without an extra newline; `true`, `null`, `42`, `1e3` (→ `1000.0\n`), `yes` (→ `yes\n`, a string), `"0.2"` (→ `0.2\n`); list item `tools.1`; value in a YAML include (`agents.coder.model`); value two include levels deep, with the inner include path relative to the *including* file's directory; text include prints the target's exact text, including CRLF bytes; an empty text-include target prints `\n`
- [X] T022 [P] [US1] E2E error tests in `tests/e2e/test_show_errors.py` (exit 5, empty stdout, stderr names the dotted path): mapping at PATH; list at PATH; missing key; index out of range; digit segment on a mapping; key segment on a list; path below a scalar; path below a text include
- [X] T023 [P] [US1] E2E test in `tests/e2e/test_show_import.py`: the first `show` against a fresh theatre creates the event store under `.troupe/` (import happened, spec D-2), and a `show` that exits 5 still imports

### Implementation for User Story 1

- [X] T024 [US1] Implement `show(theatre, path)` in `src/troupe/config/commands.py`: open theatre (import if needed), resolve PATH, collections → `PathError("… is a mapping/list, not a scalar")` naming the path, scalar or text include → `format_scalar`; wire `show` in `src/troupe/cli.py`

**Checkpoint**: US1 tests pass; gates clean. The MVP is usable.

---

## Phase 4: User Story 2 — Change a setting without disturbing the file (Priority: P1)

**Goal**: `troupe config set PATH VALUE` writes byte-surgically into the file holding the value, per FR-020 – FR-036, refusing (exit 3) rather than risking a wrong write.

**Independent Test**: For each rule, a fixture theatre, `set`, then compare every file's bytes to the expected bytes (spec US2 scenarios 1–8).

All e2e tests in this phase assert on the **exact bytes of every file** after the command. Failing cases also assert exit code, empty stdout, stderr naming the path/file, and an unchanged snapshot.

### Tests for User Story 2

- [X] T025 [P] [US2] Unit tests for scalar rendering in `tests/unit/test_render.py`: plain representability (`abc` yes; `"0.2"`, `true`, `null`, `''`, ` a`, `a `, `a: b`, `a #b`, `#a`, `-`, `- a`, `[a`, `a,b` in flow context, `x:` → not plain; `a,b` in block context → plain); single-quoted (`it's` → `'it''s'`; multi-line → not representable); double-quoted escaping escapes only `\\`, `\"` and control characters (`"tab\there"`, `\n`, `\x07` → `\a`, `\x1b` → `\e`, U+0085 → `\N`, U+2028 → `\L`), leaving `é`, `日本`, `'` and emoji literal; non-string scalars rendered plain (`3`, `true`, `null`, `0.75`); style fallback order keep → plain → single → double
- [X] T026 [P] [US2] Unit tests for line geometry in `tests/unit/test_layout.py`: end-of-line comment column found only outside scalars (`a: "x # y"  # c` → column of the second `#`); comment column preserved when the value shrinks or grows, and exactly one space when the new value reaches the column; columns counted in code points (`name: 日本  # c`); file indentation step detection (2, 4, default 2 with no nesting; sequences counted by `-` column); insertion point after the last entry *below* trailing comment lines indented ≥ the entries, stopping at a less-indented comment line
- [X] T027 [P] [US2] Unit tests for folded re-wrapping in `tests/unit/test_folded.py`: unchanged paragraphs keep bytes; a changed paragraph re-wrapped greedily at the old paragraph's longest content-line width; a word longer than the width on its own line; a new paragraph with no counterpart wrapped at the block's longest old content-line width; removing a paragraph; leading-space paragraph → `WriteRefused`
- [X] T028 [P] [US2] E2E tests for scalar replacement in `tests/e2e/test_set_scalar.py`: plain → plain (`temperature: 0.2` → `0.75`); single-quoted kept (`'coder'` → `'reviewer'`); double-quoted kept; quoted style that cannot represent the value falls back (`'x'` set to `3` → plain `3`; plain `1` set to `"2"` → `'2'`; single-quoted set to a string containing a tab → double-quoted with `\t`); a plain scalar set to a string that would be ambiguous plain (`"true"`) → `'true'`; set that changes nothing → exit 0, every file byte-identical, no new history events; list item scalar (`tools.0`); scalar inside a flow mapping/sequence keeps the surrounding flow text; a multi-line plain scalar replaced wholly; a value in a CRLF file keeps CRLF on every line
- [X] T029 [P] [US2] E2E tests for end-of-line comments in `tests/e2e/test_set_comments.py`: shrink (`0.2000   # c` → `0.2` keeps `# c` column); grow past the column → exactly one space; grow without reaching it; multi-byte characters counted as one column; no other line changes; a value inside quotes containing `#` is not taken for a comment
- [X] T030 [P] [US2] E2E tests for block scalars and multi-line strings in `tests/e2e/test_set_block.py`: plain scalar ← `"line one\nline two\n"` → `|` literal block at parent indent + step, trailing comment on the key line kept; ← value without trailing newline → `|-`; ← value with two trailing newlines → `|+`; existing `|` block replaced keeps `|` and changes only content lines; existing `|-` gets a value ending in `\n` → becomes `|`; existing `|+` kept when it still yields the value; explicit indentation indicator added when the first line starts with a space; a multi-line string containing `\r` falls back to double-quoted
- [X] T031 [P] [US2] E2E tests for folded values in `tests/e2e/test_set_folded.py`: change one of three paragraphs → only that paragraph's lines change and are wrapped at that paragraph's old longest-line width; add a paragraph → wrapped at the block's longest old line; a word longer than the width on its own line; `>-` chomping kept; a value that would add a more-indented line → exit 3, files unchanged
- [X] T032 [P] [US2] E2E tests for new keys in `tests/e2e/test_set_new_key.py`: new key in a block mapping goes after the last entry and below trailing comments indented ≥ entries, but above a less-indented comment line; key quoting copies the preceding sibling key's style (`"a": 1` → new key `"b"`); new string value copies the preceding sibling value's style; with no sibling → plain or minimal quoting; missing intermediate mappings created (`model.limits.retries 3` → `  limits:\n    retries: 3`) at the file's detected indentation (fixture with 4-space indentation); new key with a mapping/list VALUE written in block style; new key with a multi-line string → literal block; new top-level key in a file without a trailing newline gets one newline inserted before it; new key in an empty `troupe.yml`; new key under a mapping that lives in an included YAML file is written into that file only; CRLF file → new lines use CRLF
- [X] T033 [P] [US2] E2E tests for flow collections in `tests/e2e/test_set_flow.py`: new key in `{a: 1}` → `{a: 1, b: 2}` on the last entry's line; append to `[git, shell]` with `tools.2 lint` → `[git, shell, lint]`; append to a multi-line flow sequence goes on the last entry's line; append to `[]` → `[lint]`; new key with a collection VALUE inside a flow parent written in flow style; new key with a multi-line string in a flow parent → double-quoted scalar with `\n`; trailing comment after the closing bracket is untouched
- [X] T034 [P] [US2] E2E tests for block-list append in `tests/e2e/test_set_append.py`: `tools.2` appends `- lint` after the last item and below an indented trailing comment; index > length → exit 5; appending a mapping VALUE → compact `- k: v` form (research B-7); appending to a list in an included file writes that file only
- [X] T035 [P] [US2] E2E tests for structural replacement in `tests/e2e/test_set_structure.py`: scalar → block mapping keeps the key line's bytes up to and including its end-of-line comment (research B-3); scalar → list; block collection → scalar (research B-4; comment lines after the last entry kept); list → list replaced at the same indentation (research B-5); flow collection → flow collection in place
- [X] T036 [P] [US2] E2E tests for includes in `tests/e2e/test_set_includes.py`: value in a YAML include changes only that file (rule 1); `set agents.coder '{model: x}'` where `agents.coder` is `file:agents/coder.yaml` → exit 3 (rule 4); text include ← `"New prompt\n"` → target file exactly `New prompt\n` and `troupe.yml` unchanged; CRLF text target ← `"a\nb\n"` → `a\r\nb\r\n`; text include ← `3` → exit 3, no file changed; the same file included twice (diamond) is changed once and both paths read the new value
- [X] T037 [P] [US2] E2E error tests in `tests/e2e/test_set_errors.py` (exit 5 unless stated, empty stdout, stderr naming the path, files unchanged): path through a scalar; path through a null scalar; digit segment on a mapping; key segment on a list; index > length; invalid VALUE → exit 2; and a forced verification failure (e.g. a VALUE whose rendering would change another leaf, if one can be constructed; otherwise a unit test of `apply.verify` with a hand-made splice) → exit 3 with files unchanged

### Implementation for User Story 2

- [X] T038 [P] [US2] Implement `src/troupe/config/edit/render.py` (research R-8): `Style` enum (`PLAIN`, `SINGLE`, `DOUBLE`, `LITERAL`, `FOLDED`); `can_plain(text, in_flow)`, `can_single(text)`, `render_plain/single/double(text)`; `render_scalar(value, preferred_style, in_flow, cli_spelling)` with fallback keep → plain → single → double; non-string scalars plain (floats use the VALUE's own plain spelling when given, else `repr()`; `.inf`/`-.inf`/`.nan` for non-finite); `render_literal(text, indent, newline, keep_plus)` returning header indicator (`|`, `|-`, `|+`, with explicit indentation digit when the first line starts with a space) and content lines, or `None` when a literal cannot hold the text (research B-8/B-9); `render_block_collection(value, indent, step, newline)` (block mappings/lists, compact `- k: v` for mappings in lists, research B-7) and `render_flow(value)` (`{k: v}` / `[a, b]` with `, `)
- [X] T039 [P] [US2] Implement `src/troupe/config/edit/layout.py` (research R-9–R-11): `Lines` view over a text with per-line start offsets and endings; `indent_of(line)`; `is_blank_or_comment(line)`; `eol_comment(text, line_no, scalar_spans)` → column/offset of `#` outside scalar spans; `reposition_comment(old_line, value_start_col, new_value)` implementing FR-036 (keep column; exactly one space if reached; code-point columns); `indent_step(tree_of_file)` (R-10, default 2); `insertion_offset(collection)` implementing FR-033 (after last entry, below trailing comments indented ≥ entries, stop at a less-indented line; blank lines directly above that stop line stay below the insertion)
- [X] T040 [P] [US2] Implement `src/troupe/config/edit/folded.py` (research R-12): split an old folded block's content into paragraphs with their original line bytes; split the new value into paragraphs; align with `difflib.SequenceMatcher`; keep equal paragraphs' bytes; re-wrap others greedily at the counterpart's longest content-line width or the block's longest old content-line width; raise `WriteRefused` naming the path when a line would start with whitespace (more-indented)
- [X] T041 [US2] Implement `src/troupe/config/edit/planner.py`: `plan_set(loaded, path, value, value_node) -> EditPlan | TextWrite` covering: B-1 resolution (deepest existing mapping, append index == len, `PathError` otherwise); rule 4 (`WriteRefused` when the target is the root of a YAML-included file, research B-2); rule 1 text include (non-string → `WriteRefused`; content = VALUE with `\n` → `\r\n` when the target's `newline` is CRLF); scalar → scalar (keep style if representable, FR-026; multi-line → literal, FR-030; block scalars keep indicator/chomping, FR-030; folded via `folded.py`, FR-032; end-of-line comment via `layout.reposition_comment`, FR-036); new key (FR-022/FR-027/FR-029/FR-031/FR-033; sibling key and value styles copied; missing intermediates as nested block mappings at `indent_step`; flow parent → flow entry on the last entry's line, FR-034); list append (block `- ` item or flow entry); scalar ↔ collection and collection → collection (research B-3–B-6, FR-035); every new line uses the file's `newline` (spec D-6) and a missing final newline is added before appended lines
- [X] T042 [US2] Implement `src/troupe/config/edit/apply.py` (research R-7): apply splices to the file text (non-overlapping, applied right-to-left); call `loader.load_with_override`; verify it loads, the value at PATH equals the intended value (type-exact, via `leaves.to_value`), and every leaf outside PATH is unchanged — else `WriteRefused` naming the path and file; return `(new_text, before_leaves, after_leaves)`; if the new text equals the old, signal no-op
- [X] T043 [US2] Implement `set_value(theatre, path, value_text)` in `src/troupe/config/commands.py` and wire `set` in `src/troupe/cli.py`: parse VALUE (`UsageError` on failure), open theatre (import if needed), plan, apply/verify, `files.atomic_write`, then `store.record(diff_events(before, after))` (spec D-8: events only after the file write succeeds); no-op → no write, no events

**Checkpoint**: US1 and US2 tests pass; quickstart steps 6–11 and 13 behave as documented; gates clean.

---

## Phase 5: User Story 3 — See what changed (Priority: P2)

**Goal**: `troupe config history [PATH]` prints the event stream as JSON Lines.

**Independent Test**: Fresh theatre → `history` → several `set`s → `history` and `history PATH`; compare JSON Lines (spec US3 scenarios 1–6).

### Tests for User Story 3

- [X] T044 [P] [US3] E2E tests in `tests/e2e/test_history.py`: first `history` on a fresh theatre imports — one `import` line per leaf in document order (includes expanded in place, list items `b.0`, `b.1`, text include as a string leaf), `seq` 1..n, `old` null; a second `history` prints the same lines (no re-import); `set a 2` adds `{"seq": n+1, "op": "set", "path": "a", "old": 1, "new": 2}`; `set b '[z]'` on `b: [x, y]` adds a `set` for `b.0` then a `remove` for `b.1` with `new` null (spec D-3); scalar → mapping emits `set` events for the new leaves; mapping → scalar emits `remove` events for vanished leaves; no-op `set` emits nothing; a failing `set` (exit 3/5) emits nothing; filter `history b` includes `b`, `b.0`, `b.1` but not `bb`; filter for a never-existing path prints nothing and exits 0; a hand edit between commands is not recorded (spec D-1, "importing is not reconciling"); events survive across separate processes; `seq` stays contiguous across 10 consecutive `set`s (SC-004); every line is valid JSON with keys `seq, op, path, old, new`; non-ASCII strings are emitted literally

### Implementation for User Story 3

- [X] T045 [US3] Implement `history(theatre, path_filter)` in `src/troupe/config/commands.py` (open theatre → import if needed; filter `p == PATH or p.startswith(PATH + ".")`, research B-10; each record as `json.dumps({"seq", "op", "path", "old", "new"}, ensure_ascii=False)`, research B-11) and wire `history` in `src/troupe/cli.py`

**Checkpoint**: All stories pass independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T046 [P] Add a short `README.md` at the repository root: what `troupe config` does, the three commands, exit codes table, and the quality-gate commands (link to `specs/001-config-load-show-set/`)
- [X] T047 Review every error message path: each `TroupeError` raised names the path or file (FR-008); add a parametrised e2e test in `tests/e2e/test_error_messages.py` that runs each failure fixture from T008/T009/T022/T037 and asserts the named path/file appears in stderr
- [X] T048 Ensure every decision lives in one place (Principle IV): grep for duplicated literals (`"troupe.yml"`, `"file:"`, `".troupe"`, exit-code integers, `"events.sqlite3"`) and fold any duplicate into its owning constant; add a one-line comment at each decision site citing its spec/research ID (D-n / R-n / B-n)
- [X] T049 Run the quickstart.md walk-through end to end and fix any deviation
- [X] T050 Run and show the full gates: `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`; report any failure with its output (Principle III)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001–T003)** → **Foundational (T004–T020)** → user stories.
- **US1 (T021–T024)** depends only on Foundational.
- **US2 (T025–T043)** depends on Foundational; it uses `commands.resolve` (T019) but not US1's `show`. Tests that read results back may use `show`, so finishing US1 first is recommended.
- **US3 (T044–T045)** depends on Foundational (store/import); its `set`-related assertions need US2.
- **Polish (T046–T050)** after all stories.

### Within Phases

- Tests are written first and fail before implementation.
- Foundational: T011–T013 in parallel → T014 → T015 → T016 → T017 → T018 → T019 → T020.
- US2: T038, T039, T040 in parallel → T041 → T042 → T043.

### Parallel Opportunities

- T004–T010 (different test files) in parallel; T011, T012, T013 in parallel.
- T021–T023 in parallel.
- T025–T037 (one test file each) in parallel; T038–T040 in parallel.
- US1 and US3 test-writing can proceed alongside US2 once Foundational is done.

## Parallel Example: User Story 2

```text
# Tests, all at once (separate files):
T028 test_set_scalar.py   T029 test_set_comments.py   T030 test_set_block.py
T031 test_set_folded.py   T032 test_set_new_key.py    T033 test_set_flow.py
T034 test_set_append.py   T035 test_set_structure.py  T036 test_set_includes.py

# Then the three independent writer modules:
T038 edit/render.py   T039 edit/layout.py   T040 edit/folded.py
```

## Implementation Strategy

### MVP First (User Story 1)

1. Phases 1–2, then Phase 3 (`show`). Stop and validate: show works across includes, errors correct, gates clean.

### Incremental Delivery

1. Add US2 in rule groups, committing after each group passes: scalar replacement + comments
   (T028/T029) → block/folded (T030/T031) → new keys/flow/append (T032–T034) → structure/includes
   (T035/T036) → errors (T037).
2. Add US3 (history).
3. Polish and run all gates. Each commit message says why (Principle VI). The work counts as done
   only once it is committed on `main`.

## Phase 7: Convergence

- [ ] T051 CRITICAL: Catch storage and file-write failures (e.g. `sqlite3.OperationalError` from an unwritable `.troupe/`, `OSError` from `atomic_write` in `src/troupe/config/files.py`) and turn them into `TroupeError`s with documented exit codes (write failures → `WriteRefused`, exit 3, no file changed; an unreadable/unwritable event store → `LoadError`, exit 4) whose messages name the file, so no command ever exits 1 with a traceback; add e2e tests in `tests/e2e/test_state.py` with a read-only `.troupe/` directory per Constitution I, FR-007, FR-008 (contradicts)
- [ ] T052 CRITICAL: Refuse `set` (exit 3, naming the file, nothing changed) when the file holding the value is not writable by the user, instead of letting `os.replace` in `src/troupe/config/files.py` replace a read-only file; add an e2e test in `tests/e2e/test_state.py` with a `0444` `troupe.yml` per Constitution I, FR-003 (contradicts)
- [ ] T053 Review the extra `--theatre` placement before the subcommand in `src/troupe/cli.py`: either record it as a decision in `specs/001-config-load-show-set/spec.md` (Decisions on open points) or remove it with its test in `tests/e2e/test_usage.py` per FR-001, Constitution V (unrequested)
