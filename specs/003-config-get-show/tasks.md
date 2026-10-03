---

description: "Task list for troupe configuration — get for values, show for anything (Step 3)"
---

# Tasks: troupe configuration — `get` for values, `show` for anything (Step 3)

**Input**: Design documents from `specs/003-config-get-show/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: MANDATORY. Constitution Principle II overrides the template's "tests are optional". Every
behaviour gets a test that fails when it breaks. End-to-end tests run the real `troupe` CLI (the
`theatre` fixture in `tests/conftest.py`: `theatre.write(relpath, text)` writes under `.troupe/`,
`theatre.config(*args)` runs `troupe config … --theatre <root>` and returns `Result(code, out, err)`,
`theatre.snapshot()` gives every file's bytes, `assert_failed(result, code, mention)` checks a
non-zero exit with empty stdout and `mention` in stderr). Compare stdout byte-for-byte with the
expected text. Write each test task's tests first and see them fail. Once the implementation passes,
break the behaviour deliberately once to confirm the test catches it.

**Organization**: Grouped by user story (spec.md): US1 read one value with `get` (P1), US2 see a
section or the whole configuration as YAML with `show` (P1), US3 `show --sources` (P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3

## Path Conventions

Single project: `src/troupe/`, `tests/` at the repository root (plan.md → Project Structure).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the step 2 baseline is green before changing anything.

- [ ] T001 Run the gates on the unchanged tree and record the output: `uv sync`, `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`; if anything fails, stop and report it before step 3 work begins

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None needed. `get` reuses step 1's `show` code path, and `show` adds a new module. Both rely only on the existing `open_theatre`, `resolve`, `format_scalar` and `edit/render.py`. User stories start directly after Phase 1.

---

## Phase 3: User Story 1 - Read one value for a script (Priority: P1) 🎯 MVP

**Goal**: `troupe config get PATH` prints a scalar exactly as step 1's `show` did; a mapping or list → exit 5 with stderr mentioning `config show` (FR-200 – FR-204).

**Independent Test**: Run `config get` on scalars in the main file, nested YAML includes and text includes, and on a mapping and a list; compare stdout, stderr and the exit code (spec US1 scenarios 1–7).

### Tests for User Story 1

- [ ] T002 [P] [US1] Create `tests/e2e/test_get.py` by moving `tests/e2e/test_show.py`'s current content (`git mv`, then edit): rename the parametrised test to `test_get_prints_the_scalar` and every `config("show", …)` / `run("config", "show", …)` call to `get`; keep all cases (all scalar kinds, folded/literal/stripped, `tools.1`, nested include `agents.coder.skills.1`, text include with CRLF bytes exact, text include without final newline, empty text include → `\n`, non-ASCII, CRLF config file). Update the module docstring to "`get PATH` prints a scalar exactly as step 1's `show` did (spec FR-201, SC-201)"
- [ ] T003 [P] [US1] Create `tests/e2e/test_get_errors.py` by moving `tests/e2e/test_show_errors.py` (`git mv`): rename to `test_get_exits_5_naming_the_path`, call `get`; keep every path case and the snapshot check. Add `test_get_of_a_collection_mentions_config_show`, parametrised over `model` (mapping), `tools` (list) and `agents.coder` where `agents.coder` is a YAML include `file:c.yaml` containing `model: x` (mapping from an include): `assert_failed(result, 5, path)` and `"config show" in result.err` (FR-202). (Descending through a text include stays covered by the existing `prompt.x` case.)
- [ ] T004 [P] [US1] Create `tests/e2e/test_get_import.py` by moving `tests/e2e/test_show_import.py` (`git mv`) and switching both tests to `get` (first `get` imports; a failing `get` still imports). Add `test_get_reconciles_a_hand_edit_first` (FR-204, D-20): import with `config history`, write `a: 2` over `a: 1`, `config get a` prints `2\n`, and `theatre.history()[-1] == {"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}`
- [ ] T005 [US1] In `tests/e2e/test_usage.py` add usage cases for `get` (exit 2, stdout empty, nothing recorded): `("config", "get")` (no PATH), `("config", "get", "a", "extra")`, `("config", "get", "a", "--sources")` (D-26), `("config", "get", "a", "--bogus")`; change the existing case `("config", "show")` — which is now valid — to `("config", "get")` and keep `("config", "show", "a", "extra")` and `("config", "show", "a", "--bogus")`; switch the `--theatre`/cwd/`TROUPE_THEATRE` default tests to `get` (they test the default, not the subcommand). In `tests/e2e/test_error_messages.py` change the `("show", "l")` case (a list → 5) to `("get", "l")` and the `("show", "a..b")` usage case to `("get", "a..b")`; leave the other `show` scalar cases as they are (still valid)

### Implementation for User Story 1

- [ ] T006 [US1] In `src/troupe/config/commands.py` rename `show` to `get` (keep the body: `ConfigPath.parse`, `with theatre_lock(theatre): open_theatre(theatre, reconcile=True)`, `resolve`, `format_scalar`). Add a module-level function `use_show_hint(path: ConfigPath, node: Located) -> str` returning `f"{path}: is {node_kind(node)}, not a scalar; use `troupe config show {path}` to print it"` (the one place the FR-202 wording lives; comment cites spec FR-202) and raise `PathError(use_show_hint(path, node))` for a `LocatedMapping`/`LocatedSequence`. Update the module docstring to list `get, show, set, history, watch`
- [ ] T007 [US1] In `src/troupe/cli.py` add the `get` subparser: `add("get", "print a setting's value").add_argument("path", metavar="PATH")`; dispatch `if args.subcommand == "get": return commands.get(theatre, args.path)`. Temporarily keep `show` dispatching to `commands.get` until T013 replaces it, so the existing `show` scalar tests stay green. Update the module docstring to `troupe config get|show|set|history|watch`
- [ ] T008 [US1] Run T002 – T005 and the full suite to green; deliberately change the hint to omit `config show` and confirm T003's new test fails; make `get` call `open_theatre(reconcile=False)` and confirm T004's reconcile test fails; restore. Commit ("why": `get` takes over step 1's scalar printing so `show` can print sections)

**Checkpoint**: `get` is a drop-in for step 1's `show`.

---

## Phase 4: User Story 2 - See a section, or the whole configuration, as YAML (Priority: P1)

**Goal**: `show [PATH]` prints a scalar like `get`; a mapping or list (or the whole configuration) as block-style YAML with includes resolved and text includes as literal blocks (FR-210 – FR-225).

**Independent Test**: Run `config show [PATH]` on fixtures and compare stdout byte-for-byte with the expected YAML; parse the output back and compare with the configuration (spec US2 scenarios 1–7).

### Tests for User Story 2

- [ ] T009 [P] [US2] Unit tests in `tests/unit/test_view.py` for `view.render(node, theatre, sources=False)`, building nodes with the real loader (`load(theatre_root)` on files written under `tmp_path/.troupe/`, then `commands.resolve`) — exact strings:
  - flat mapping `a: 1\nb: x\n` → `"a: 1\nb: x\n"`;
  - nested mapping (flow in the file) `model: {temperature: 0.2, name: 'opus'}` → `"model:\n  temperature: 0.2\n  name: opus\n"` (FR-220, original quoting dropped FR-213);
  - list under key `tools: [git, shell]` → `"tools:\n  - git\n  - shell\n"`;
  - list at the root of the view (`resolve` to `tools`) → `"- git\n- shell\n"`;
  - list of mappings `steps: [{name: a, run: x}, {name: b}]` at `steps` → `"- name: a\n  run: x\n- name: b\n"` (compact form);
  - nested list `m: [[x, y], [z]]` at `m` → `"- - x\n  - y\n- - z\n"`;
  - empty collections `e: {}\nl: []\n` → `"e: {}\nl: []\n"`; empty main file → `"{}\n"` (FR-220, edge case);
  - quoting (FR-222): string values `"0.2"`, `"true"`, `"null"`, `""`, `"a: b"`, `"- x"`, `" lead"`, `"it's: x"` each render quoted and `YAML(typ="safe").load` of the output gives back the same string; plain `opus`, `yes`, `on` render unquoted; a key `"true"` (quoted in the file) renders quoted;
  - scalars (FR-224): `true`, `false`, `null`, `42`, `0x1F` → `31`, `1e3` → `1000.0`, `.inf` → `.inf`, `-.inf` → `-.inf`, `.nan` → `.nan`;
  - literal blocks (FR-223): a block-scalar value `notes: |\n  one\n  two\n` → `"notes: |\n  one\n  two\n"`; a double-quoted `"x\ny"` → `"k: |-\n  x\n  y\n"`; value with two trailing newlines → `|+` and reads back exactly; first line starting with a space → `|2` header and reads back exactly; a literal inside a list-of-mappings item (`- k: |` content indented 4) reads back exactly;
  - text include (FR-223, D-24): `p: file:p.md` with `p.md` = `Be terse.\n` → `"p: |\n  Be terse.\n"` (single-line still literal); `p.md` = `no newline` → `"p: |-\n  no newline\n"`; empty `p.md` → header `p: |-` and reads back as `""`; CRLF `p.md` = `a\r\nb\r\n` → `"p: |\n  a\n  b\n"`; a text whose content starts with `file:` is shown as text;
  - YAML include embedded in place (FR-213): `agents: {coder: "file:agents/coder.yaml"}` with a nested include two levels deep → the included keys appear under `coder` at the right indentation, in document order (FR-221); an empty YAML include → `key: null`
- [ ] T010 [P] [US2] Rewrite `tests/e2e/test_show.py` (it was moved to `test_get.py` in T002) for the new `show`: (1) `test_show_prints_a_scalar_like_get` — parametrised over `model.temperature`, `prompt` (text include, CRLF bytes exact), `model.stripped`, `agents.coder.model`: `config show P` stdout equals `config get P` stdout and both exit 0 (FR-211); (2) `test_show_of_the_whole_configuration` — the exact fixture and expected output of spec US2 scenario 2 (comment, flow mapping with `'opus'`, YAML include, text include `Be terse.\nNo jokes.\n`) byte-for-byte; (3) `test_show_of_a_section` — `agents.coder` → `"model: sonnet\ntools:\n  - git\n  - shell\n"` (US2 scenario 3); (4) `test_show_of_a_list` — `tools` → `"- git\n- shell\n"`; (5) `test_show_of_a_list_of_mappings` — US2 scenario 5; (6) `test_show_errors_exit_5_naming_the_path` — `missing`, `model.name.x`, `tools.9`, `model.0`, `prompt.x` → `assert_failed(..., 5, path)` (FR-212); (7) `test_show_writes_no_file` — `theatre.snapshot()` equal before/after `show` and `show --sources` (SC-204); (8) `test_show_reconciles_first` — hand edit `a: 1 → 2` after import, `config show` prints `a: 2\n` and history gains `set a 1 → 2` (FR-204); (9) `test_show_of_an_empty_configuration` — empty `troupe.yml` → `{}\n`; (10) `test_show_accepts_path_after_or_before_options` — `config show --theatre <root> tools` works (D-26)
- [ ] T011 [P] [US2] Create `tests/e2e/test_show_readback.py`: for a rich fixture (main file with flow and block collections, every scalar type including `.inf`/`.nan`, strings needing each quoting style, a multi-line block value, a `|+` value, a leading-space literal, a two-level YAML include, a text include without final newline, an include outside `.troupe/` via `file:../shared/s.yaml`), parse `config show` stdout and `config show --sources` stdout with `ruamel.yaml.YAML(typ="safe").load` and assert both equal the plain value tree built from the loaded configuration (walk `load(root).root` → dict/list/scalars, using `TextInclude.value`) with type-exact comparison via `troupe.config.scalars.scalars_equal` (FR-214, SC-202); also for `config show agents` (a section); a CRLF text include is checked separately: its read-back equals the text with `\r\n` → `\n` (D-24)

### Implementation for User Story 2

- [ ] T012 [US2] Create `src/troupe/config/view.py` (module docstring: "`show`'s YAML view of the located tree — spec FR-210 – FR-234, D-21; research G-2 explains why it does not reuse `render_block`"). Contents:
  - `STEP = 2` (the indentation step of `show`'s YAML, spec D-21);
  - `type Line = tuple[str, SourceFile | None]` — the text of a line and the file of the scalar it holds (None for lines holding no scalar: keys opening a collection, literal-block content lines, `{}`/`[]`);
  - `_spell(node: LocatedScalar | TextInclude, column: int) -> tuple[str, list[str], SourceFile]`: the inline text (or literal header) to put after `key: ` / `- ` / at the top level, the following content lines (already indented to `column`), and the source file. `TextInclude` → text `node.target.text.replace("\r\n", "\n")`; if `literal_representable(text)` → `render_literal(text, column, STEP)` else `render_inline(NewScalar(text), PLAIN, in_flow=False)` (double-quoted fallback, research G-3); source `node.target`. `LocatedScalar` with a `str` value containing `\n` and `literal_representable` → `render_literal(value, column, STEP)`; otherwise `render_inline(NewScalar(value), PLAIN, in_flow=False)`; source `node.file`;
  - `_mapping_lines(node: LocatedMapping, column: int) -> list[Line]` and `_sequence_lines(node: LocatedSequence, column: int) -> list[Line]` following research G-2's layout: keys spelled with `render_key(str(key.value), PLAIN, False)`; scalar values → `f"{pad}{key}: {inline}"` with the scalar's source, then literal content lines with None; empty collection → `f"{pad}{key}: {{}}"` / `[]` with None; non-empty collection → `f"{pad}{key}:"` with None then children at `column + STEP`; list items `f"{pad}- {inline}"`; a non-empty collection item → render its lines at `column + 2` and splice `- ` into the first line (compact form, `- k: v` / `- - x`), keeping the first line's source;
  - `_node_lines(node: Located, column: int) -> list[Line]` dispatching on node kind; an empty root mapping (`not node.entries`) → `[("{}", None)]`; a top-level scalar → `[(inline, source), *content lines]` with literal content at column `STEP`;
  - `source_label(theatre: Path, file: SourceFile) -> str` = `os.path.relpath(file.path, theatre.resolve()).replace(os.sep, "/")` (spec FR-233, D-22; research G-4);
  - `render(node: Located, theatre: Path, *, sources: bool) -> str` joining lines with `"\n"` after each, appending `f" # from {source_label(theatre, src)}"` to lines whose source is not None when `sources` (FR-230, D-25)
  Import `literal_representable`, `render_inline`, `render_key`, `render_literal`, `PLAIN` from `troupe.config.edit.render`; do not duplicate any scalar-spelling rule
- [ ] T013 [US2] In `src/troupe/config/commands.py` add `show(theatre: Path, path_text: str | None, *, sources: bool) -> str`: parse PATH if given (before the lock, so usage errors record nothing); `with theatre_lock(theatre): loaded, _ = open_theatre(theatre, reconcile=True)`; `node = loaded.root if path is None else resolve(loaded.root, path)`; if not `sources` and `node` is a `LocatedScalar` or `TextInclude` → `format_scalar(node.value)` (FR-211); else `view.render(node, theatre, sources=sources)`. In `src/troupe/cli.py` replace the `show` subparser with `show = add("show", "print a setting or a section as YAML")`, `show.add_argument("path", metavar="PATH", nargs="?")`, `show.add_argument("--sources", action="store_true", help="say which file each value comes from")`; dispatch `commands.show(theatre, args.path, sources=args.sources)`
- [ ] T014 [US2] Run T009 – T011 and the full suite (including the step 1/2 tests that still call `show` on scalars, e.g. `tests/e2e/test_reconcile.py`, `test_state.py`, `test_set_includes.py`, `test_load_errors.py`) to green; deliberately (a) make text includes use `render_inline` instead of a literal block and confirm T009/T010 fail, (b) drop the compact list-item form and confirm the list-of-mappings tests fail, (c) render `"0.2"` plain and confirm T011 fails; restore. Commit ("why": `show` prints whole sections with includes resolved)

**Checkpoint**: `show` prints any node; `get` and `show` agree on scalars.

---

## Phase 5: User Story 3 - Find out which file a value comes from (Priority: P2)

**Goal**: `show [PATH] --sources` annotates every scalar line with ` # from <file>` (FR-230 – FR-234).

**Independent Test**: Run `config show [PATH] --sources` on a theatre with values in the main file, nested YAML includes, a text include and an include outside `.troupe/`; compare stdout byte-for-byte (spec US3 scenarios 1–5).

### Tests for User Story 3

- [ ] T015 [P] [US3] Create `tests/e2e/test_show_sources.py`: (1) whole configuration — the exact fixture and output of spec US3 scenario 1 byte-for-byte (literal header `prompt: | # from .troupe/prompts/system.md`, content lines unannotated; `tools:` and `agents:`/`coder:` lines unannotated); (2) `show agents --sources` → only the `agents` section, annotated (US3 scenario 2); (3) include outside `.troupe/`: `shared: file:../common/shared.yaml` with `<root>/common/shared.yaml` = `k: v\n` → `"k: v # from common/shared.yaml\n"` for `show shared --sources` (FR-233, D-22); (4) two-level include (`troupe.yml` → `agents/coder.yaml` → `agents/limits.yaml`): leaves from `limits.yaml` say `# from .troupe/agents/limits.yaml` (FR-232); (5) scalar with `--sources`: `show model.temperature --sources` → `"0.2 # from .troupe/troupe.yml\n"`; a string `"0.2"` → `"'0.2' # from .troupe/troupe.yml\n"`; a text include `prompt` → `"| # from .troupe/prompts/system.md\n  Be terse.\n  No jokes.\n"` (FR-234, D-23); (6) empty collections and an empty configuration → no comment (`e: {}`, `{}\n`); (7) a list of mappings: `- name: a # from …` and `  run: x # from …` both annotated; (8) every line count: for the US3 fixture, the number of `# from` comments equals the number of scalar leaves (SC-203); (9) theatre passed through a symlinked directory (`os.symlink(root, tmp_path / "link")`, run with `--theatre <link>`) → labels are still `.troupe/...` (D-22); (10) `--sources` before PATH (`show --sources agents`) gives the same output (D-26)

### Implementation for User Story 3

- [ ] T016 [US3] Verify `view.render(..., sources=True)` and `source_label` from T012 satisfy T015; fix any gap in `src/troupe/config/view.py` (e.g. the compact list-item splice must keep the first inner line's source; a top-level literal's header carries the source). Add a comment at `source_label` citing spec D-22 (real paths, why)
- [ ] T017 [US3] Run T015 to green; deliberately (a) return `file.path` of the `TextInclude.include` scalar (the including file) instead of `target` and confirm T015 (1) fails, (b) drop `.resolve()` on the theatre and confirm T015 (9) fails, (c) annotate the `tools:` line and confirm T015 (1)/(8) fail; restore. Commit ("why": show where each value lives so users know which file to edit)

**Checkpoint**: all three stories work.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T018 [P] Update `README.md`: replace the `show PATH` line with `uv run troupe config get PATH [--theatre DIR]   # print a scalar setting` and `uv run troupe config show [PATH] [--sources] [--theatre DIR]   # print a setting or section as YAML (--sources: which file each value is in)`; add a short paragraph with a `show --sources` example; change the exit-5 row to "path not found, or the wrong kind of node for the command (e.g. `get` of a section)"; link `specs/003-config-get-show/`
- [ ] T019 [P] Mark step 1's `show PATH` as superseded: in `specs/001-config-load-show-set/spec.md` FR-015 append "*(Replaced by step 3: this behaviour is now `get PATH`; see `specs/003-config-get-show/spec.md`.)*"; in `specs/001-config-load-show-set/contracts/cli.md` add a one-line note at the top that `show PATH` is now `get PATH` (step 3); in `specs/002-config-file-sync/contracts/cli.md` add `get` to the side-effects table (imports: yes, reconciles: yes)
- [ ] T020 Walk through `specs/003-config-get-show/quickstart.md` by hand and confirm each expected output (including the read-back check)
- [ ] T021 Run the full gates and show output: `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`; report any failure with its output. Commit polish ("why": docs and earlier specs agree with the new commands, Principle VI)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → user stories (no foundational work).
- **US1 (Phase 3)**: independent; it frees the `show` name by moving step 1 tests and code to `get`.
- **US2 (Phase 4)** depends on US1 (T002 moves the old `test_show.py` before T010 rewrites it; T006 renames the function before T013 adds the new `show`).
- **US3 (Phase 5)** depends on US2 (T012's renderer carries the sources).
- **Polish (Phase 6)** after all stories.

### Within Each Story

Tests first (see them fail) → implementation → run to green → deliberate-break check → commit with a message saying why.

### Parallel Opportunities

- US1: T002 ∥ T003 ∥ T004 (different files); T005 after them (touches shared usage cases); T006 → T007.
- US2: T009 ∥ T010 ∥ T011; T012 → T013.
- US3: T015 alone, then T016.
- Polish: T018 ∥ T019.

## Parallel Example: User Story 2

```bash
# After US1 is committed:
Task: "Unit tests for view.render in tests/unit/test_view.py"         # T009
Task: "E2E tests for the new show in tests/e2e/test_show.py"          # T010
Task: "Read-back tests in tests/e2e/test_show_readback.py"            # T011
```

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1.
2. Phase 3 (US1): `get` exists and behaves exactly as step 1's `show`.
3. **Stop and validate** with T002 – T005 and the full suite.

### Incremental Delivery

1. US1 → commit.
2. US2 → commit.
3. US3 → commit.
4. Polish → commit.

## Notes

- Every commit message says why the change was made (Principle VI).
- Tests that call `show` on a scalar in step 1/2 files stay as they are: `show` still prints scalars exactly like `get` (FR-211), so they keep passing and also guard that rule.
- Text include content containing control characters other than tab/line breaks, non-UTF-8 text and non-string keys are out of contract (spec); do not test them.
