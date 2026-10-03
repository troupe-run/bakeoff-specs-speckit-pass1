---

description: "Task list for troupe configuration — keep files and configuration in sync (Step 2)"
---

# Tasks: troupe configuration — keep files and configuration in sync (Step 2)

**Input**: Design documents from `specs/002-config-file-sync/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: MANDATORY. Constitution Principle II overrides the template's "tests are optional". Every
behaviour gets a test that fails when it breaks. End-to-end tests run the real `troupe` CLI against
real theatres in `tmp_path`; `watch` runs as a real subprocess and is stopped by real signals
(research S-9). Write each test task's tests first and see them fail. Once the implementation passes,
break the behaviour deliberately once to confirm the test catches it.

**Organization**: Grouped by user story (spec.md): US1 edits made while nothing ran are picked up
(P1), US2 live sync with `watch` (P1), US3 troupe's own write-backs are not recorded twice (P1).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3

## Path Conventions

Single project: `src/troupe/`, `tests/` at the repository root (plan.md → Project Structure).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the step 1 baseline is green before changing anything.

- [X] T001 Run the gates on the unchanged tree and record the output: `uv sync`, `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`; if anything fails, stop and report it before step 2 work begins

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The projection read, the reconcile function and the cross-process lock. Every story needs them.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational

- [X] T002 [P] Unit tests for `reconcile` in `tests/unit/test_reconcile.py`, using real theatres on disk (write files, `load()`, a real `ConfigStore` under `tmp_path`): after import, an unchanged configuration → `[]` and no new history record; a changed leaf `a: 1 → 2` → `[LeafEvent("set", "a", 1, 2)]`; a new leaf → `set` with `old` None; a missing leaf → `remove` with `new` None; type-only change `a: 1 → a: "1"` and `1 → 1.0` → one `set` each (FR-111); comment-only, re-indent, quoting-only (`x` → `"x"`), blank-line, key-reorder, CRLF line endings and block↔flow (`b: [x, y]` ↔ block list) edits → `[]` (FR-112); order: `set` events in file document order then `remove` events in projection order (FR-114) — e.g. projection `a, b, c` (import) plus `d` (set later), files drop `d` and `a` and change `c` → `set c`, `remove a`, `remove d`; a reconcile's events are persisted (re-open the store: `history()` contains them)
- [X] T003 [P] Unit tests for the lock in `tests/unit/test_lock.py`: `theatre_lock(theatre)` creates `<theatre>/.troupe/events.sqlite3.lock`; while held, a non-blocking `fcntl.flock(fd, LOCK_EX | LOCK_NB)` on a second descriptor of that file raises `BlockingIOError`; after the `with` exits it succeeds; a lock file that exists read-only (`chmod 0o444`) can still be locked; a `.troupe/` that does not exist → `LoadError` naming the lock file path

### Implementation for Foundational

- [X] T004 Add `ConfigStore.leaves() -> dict[str, Scalar]` to `src/troupe/config/store.py` returning a copy of the aggregate's `leaves` (empty dict if never imported); docstring: "the projection — what reconcile compares the files against (spec D-10)"
- [X] T005 [P] Create `src/troupe/config/lock.py`: constant `LOCK_FILENAME = STORE_FILENAME + ".lock"` (imported from `store.py`; the name groups it with the store's files), context manager `theatre_lock(theatre: Path) -> Iterator[None]` that opens `<theatre>/.troupe/LOCK_FILENAME` with `os.open(path, O_RDWR | O_CREAT, 0o644)`, falls back to `O_RDONLY` on `PermissionError`, raises `LoadError(f"{path}: cannot open the lock file: {strerror}")` on any other `OSError`, takes a blocking `fcntl.flock(fd, LOCK_EX)`, and unlocks/closes in `finally`; module docstring cites research S-3 and spec FR-130/FR-131 (why the lock spans load → write → record)
- [X] T006 Create `src/troupe/config/sync.py` with `reconcile(loaded: Loaded, store: ConfigStore) -> list[LeafEvent]`: `events = diff_events(store.leaves(), leaves(loaded.root))`; `store.record(events)` (one save → atomic, FR-115; empty list saves nothing, FR-116); return the events. Docstring cites spec FR-110 – FR-116 and research S-1 (remove order = projection order)
- [X] T007 Run T002 and T003 to green; then break `scalars_equal` use (e.g. compare with `==`) and confirm the type-only test fails; restore

**Checkpoint**: reconcile and the lock work in isolation.

---

## Phase 3: User Story 1 - Hand edits made while nothing was running are picked up (Priority: P1) 🎯 MVP

**Goal**: `show` and `set` reconcile before their own work; `history` never does.

**Independent Test**: In an imported theatre, edit files by hand between commands and compare `config history` JSON Lines exactly (spec US1 scenarios 1–8).

### Tests for User Story 1

- [X] T008 [P] [US1] E2E tests in `tests/e2e/test_reconcile.py` (use the `theatre` fixture; import first with `config history`): (1) `a: 1` → hand edit `a: 2` → `config show a` prints `2\n` and history's last line is exactly `{"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}` for a one-leaf theatre; (2) comment-only, re-indent, quoting-only and blank-line edits followed by `config show a` → history unchanged (compare full output before and after); (3) `b: [x, y]` → `b: [x]` then `show b.0` → `remove b.1` with `old` `"y"` and `new` null; (4) new key `c: 3` → `set c` null → 3; (5) hand-added `agents: {coder: "file:agents/coder.yaml"}` with `agents/coder.yaml` = `model: opus\ntools: [git]\n` → `set` events for `agents.coder.model` and `agents.coder.tools.0`, in that order (FR-113); (6) unreconciled hand edit `a: 1 → 2` then `config set b 5` → history gains `set a` then `set b`, in that order; (7) hand edit then `config history` → not listed (run `history` twice, identical output), then `config show a` → listed (FR-121); (8) reconcile then another `show` with no edit → nothing more recorded; (9) text-include target edited by hand → `set prompt` with old/new texts; (10) include target swapped `file:a.yaml` → `file:b.yaml` where only one leaf differs → exactly one `set`
- [X] T009 [US1] E2E tests for reconcile vs. failing commands in `tests/e2e/test_reconcile.py` (same file as T008, so after it): hand edit then `config show missing.path` → exit 5 and the reconcile event is in history (FR-122); hand edit then a refused set (`config set agents.coder '{a: 1}'` on a YAML include) → exit 3 and the reconcile event stands; hand edit then `config set a '[b'` (invalid VALUE) → exit 2 and nothing recorded; hand edit that makes the YAML invalid then `config show a` → exit 4 and nothing recorded; reconcile does not change any config/include file bytes (`theatre.snapshot()` before/after equal, FR-003/D-17)

### Implementation for User Story 1

- [X] T010 [US1] In `src/troupe/config/commands.py` change `open_theatre(theatre, *, reconcile: bool)`: load; `ConfigStore`; if not imported → `import_leaves`; elif `reconcile` → `sync.reconcile(loaded, store)`. Update its docstring (step 1 D-1 superseded by spec step 2; `history` passes `False` per FR-121; must be called with `theatre_lock` held)
- [X] T011 [US1] In `src/troupe/config/commands.py` wrap the bodies of `show`, `set_value` and `history` in `with theatre_lock(theatre):` *after* argument parsing (`ConfigPath.parse`, `parse_value` stay outside so usage errors record nothing, FR-122); `show` and `set_value` call `open_theatre(theatre, reconcile=True)`; `set_value` keeps `apply_set` and `store.record(events)` inside the lock; `history` calls `open_theatre(theatre, reconcile=False)`
- [X] T012 [US1] Run T008, T009 and the full step 1 suite to green; deliberately make `history` reconcile and confirm T008 (7) fails; remove the reconcile from `show` and confirm T008 (1) fails; restore

**Checkpoint**: commands pick up edits made while nothing was running — usable without `watch`.

---

## Phase 4: User Story 2 - Live sync while editing (Priority: P1)

**Goal**: `troupe config watch` prints `watching <dir>` once it can observe changes and reconciles within 2 s of every change until SIGINT/SIGTERM (exit 0).

**Independent Test**: Start `watch` as a subprocess, read its line, edit files, poll `config history` (which never reconciles) for ≤ 2 s, stop with a signal, check exit 0 and stdout (spec US2 scenarios 1–7).

### Tests for User Story 2

- [X] T013 [US2] Add a `watch` fixture to `tests/conftest.py`: `theatre.watch(*extra_args, theatre_arg=True, env=None)` starts `subprocess.Popen([*COMMAND, "config", "watch", "--theatre", str(root), *extra_args], stdout=PIPE, stderr=PIPE)` (env without `TROUPE_THEATRE` unless given), reads the first stdout line with a 10 s timeout (thread or `selectors`), and returns a `Watcher` with `.line`, `.stop(sig) -> (code, rest_of_stdout, stderr)`; a pytest finalizer kills any still-running watcher. Also add `wait_for_history(theatre, predicate, timeout=2.0)` that polls `theatre.history()` every 0.05 s and returns the history once `predicate` holds, failing with the last history if the deadline passes
- [X] T014 [P] [US2] E2E tests in `tests/e2e/test_watch.py`: (1) `line == f"watching {root}\n"` and the process is still running after 0.5 s; (2) main-file edit `a: 1 → 2` made immediately after the line (no sleep) → `set a` within 2 s (FR-102/FR-103); (3) edit inside a YAML include and (4) a text-include target → the matching `set` within 2 s; (5) comment-only and formatting-only edits → after 2.5 s history unchanged (FR-112); (6) save-by-rename (write a temp file in the same directory, `os.replace` over the config file) → recorded within 2 s; (7) hand-added include, then after it is recorded an edit to the newly included file → each recorded within 2 s of its edit (FR-104/FR-113); (8) include removed by hand → `remove` events for its leaves, then an edit to the formerly included file → nothing recorded after 2.5 s; (9) an include target outside `.troupe/` (`file:../shared.yaml`) edited → recorded; (10) never-imported theatre → after the line appears, `config history` shows exactly the `import` events and no `set` events (watch imported before announcing, FR-101)
- [X] T015 [P] [US2] E2E tests for the watch lifecycle in `tests/e2e/test_watch_lifecycle.py`: SIGINT → exit 0; SIGTERM → exit 0; in both cases stdout is exactly `watching <dir>\n` (FR-105, SC-105) and stderr empty; configuration unloadable at start (syntax error; no config file) → exit 4, stdout empty, stderr names the file, no `watching` line (FR-106); while watching, write invalid YAML → stderr gains exactly one `troupe: error:` line naming `troupe.yml` within 2 s and still only one after a further 1 s, nothing recorded, process alive; then fix the file to a new value → that change recorded within 2 s; create a missing include target named by a hand edit → recorded once the target appears; `config watch extra` → exit 2; `<dir>` display (D-11): run with `TROUPE_THEATRE=<root>` and no `--theatre` → `watching <root>`; run with `cwd=root`, no option, no env → `watching <absolute root>`; relative `--theatre theatre` from `cwd=tmp_path` → `watching theatre`

### Implementation for User Story 2

- [X] T016 [US2] Create `src/troupe/config/watch.py`: `POLL_INTERVAL = 0.2` (comment: well inside the contract's 2 s, research S-4); `type Snapshot = dict[Path, bytes | None]`; `snapshot_of(theatre, loaded) -> Snapshot` = `{path: source.text.encode("utf-8") for path, source in loaded.files.items()}` plus each `(theatre / TROUPE_DIR / name).resolve()` for `name in CONFIG_NAMES` not already present, mapped to its current bytes or `None`; `changed(snapshot) -> bool` re-reads each path (`None` on `FileNotFoundError`/`OSError`) and compares; `run_watch(theatre, announce, stop: threading.Event, report: Callable[[str], None]) -> None`: under `theatre_lock`, `loaded, _ = open_theatre(theatre, reconcile=True)` (TroupeError propagates → exit 4 at startup), snapshot, `announce()`; loop `while not stop.wait(POLL_INTERVAL)`: if `broken or changed(snapshot)`: under the lock `open_theatre(..., reconcile=True)`, rebuild snapshot, `broken=False`, `last_error=None`; on `TroupeError as e`: `broken=True`, call `report(e.message)` only if it differs from `last_error` (research S-5). Docstring cites FR-100 – FR-106 and why the snapshot is the parsed bytes (the "promise")
- [X] T017 [US2] Add `watch(theatre: Path, display: str, announce: Callable[[str], None], report: Callable[[str], None]) -> str` to `src/troupe/config/commands.py`: create `stop = threading.Event()`, install `signal.signal(SIGINT/SIGTERM, lambda *_: stop.set())` before anything else (research S-6), call `run_watch(theatre, lambda: announce(f"watching {display}\n"), stop, report)`, return `""`
- [X] T018 [US2] In `src/troupe/cli.py`: add `add("watch", "record hand edits to the configuration as they happen")` with no positionals; add `theatre_display(arg: Path | None, raw_arg: str | None) -> str` as the one place deciding `<dir>` (spec D-11: the `--theatre` string as given, else `$TROUPE_THEATRE` as given, else `str(Path.cwd())`) — keep the raw `--theatre` string (use `type=str` and convert to `Path` once) so the display is exactly what was typed; in `run()` dispatch `watch` with `announce` = write UTF-8 to `sys.stdout.buffer` and flush, `report` = `print(f"{PROG}: error: {message}", file=sys.stderr, flush=True)` (same format as `main()`; factor a shared `error_line(message)` so the format lives in one place)
- [X] T019 [US2] Run T014 and T015 to green; deliberately (a) build the snapshot from files read *after* the reconcile instead of `loaded.files` and run the immediate-edit test repeatedly (expect flakiness/failure), (b) drop the include re-snapshot and confirm T014 (7) fails, (c) let SIGINT raise `KeyboardInterrupt` and confirm exit code test fails; restore each. Outcome: (b) as written is not a break (a stale snapshot makes `watch` reconcile on every poll, which is still correct), so the real break — included files left out of the snapshot — was used and is caught by 4 tests; (a) cannot be hit reliably end to end (10/10 passes), so `tests/unit/test_watch_snapshot.py` proves the promise deterministically by editing between parse and snapshot, and fails under (a)

**Checkpoint**: `watch` records hand edits live.

---

## Phase 5: User Story 3 - troupe's own write-backs are not recorded twice (Priority: P1)

**Goal**: With `watch` running, a `set` records exactly its own events; every change is recorded exactly once (FR-130, FR-131).

**Independent Test**: Run a sequence of `set`s with and without `watch` and compare full histories (SC-103).

### Tests for User Story 3

- [X] T020 [P] [US3] E2E tests in `tests/e2e/test_watch_exactly_once.py`: (1) `watch` running, `config set a 2` → after 3 s exactly one new event `set a 1 → 2`; (2) `b: [x, y]`, `config set b '[z]'` → exactly `set b.0`, `remove b.1`, in that order; (3) text-include `prompt` set → exactly one `set prompt`; (4) a sequence of ≥10 `set`s (scalars, new keys, list append, collection replace, text include, a no-op `set`) run once in theatre A with `watch` and once in an identical theatre B without — after a final 3 s wait the two histories are equal (SC-103) and `seq` is contiguous from 1; (5) hand edit of `a` immediately followed by `config set c 1` → `set a` appears exactly once and `set c` exactly once, whichever process reconciled first (FR-131); (6) the lock is what prevents duplicates: the test process holds `theatre_lock(root)`, makes a hand edit, waits 1 s → history (read via the store directly, since `config history` would block on the lock) has no new event; releases → event recorded within 2 s, exactly once
- [X] T021 [P] [US3] Unit/integration test in `tests/unit/test_lock.py` (append after T003's tests): monkeypatch `ConfigStore.record` to assert, before delegating, that a non-blocking `flock` on a second descriptor of the lock file raises `BlockingIOError`; call `commands.set_value(theatre, "a", "2")` in-process on a real theatre and assert the patched `record` ran with the lock held (research S-3, S-9)

### Implementation for User Story 3

- [X] T022 [US3] Verify no further code is needed beyond T011 (lock spans `open_theatre` → `apply_set` → `store.record` in `set_value`) and T016 (watch reconciles only under the lock) in `src/troupe/config/commands.py` and `src/troupe/config/watch.py`; add a comment at the `with theatre_lock` in `set_value` citing FR-130 ("the write-back is recorded before watch can load it, so watch finds nothing to record")
- [X] T023 [US3] Run T020 and T021 to green; deliberately move `store.record(events)` in `set_value` outside the lock and confirm T021 fails (and T020 (4) fails or flakes when run in a shell loop of 20 runs); restore. Outcome: T021 fails; with the record also delayed 0.3 s (as a slow disk would) both T020 (1) and (4) fail 20/20 runs

**Checkpoint**: all three stories work; history is exactly-once with and without `watch`.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T024 [P] Update `README.md`: add `uv run troupe config watch [--theatre DIR]` to the command list with one line ("record hand edits as they happen; stop with Ctrl-C"); note that every command except `history` first records hand edits made since the last command; mention `events.sqlite3.lock` next to the event store; link `specs/002-config-file-sync/`
- [X] T025 [P] Mark step 1 spec D-1 as superseded in `specs/001-config-load-show-set/spec.md` with a one-line pointer to `specs/002-config-file-sync/spec.md` (Principle VI: spec and code agree)
- [X] T026 Walk through `specs/002-config-file-sync/quickstart.md` by hand and confirm each expected output
- [X] T027 Run the full gates and show output: `uv run pytest` (run the watch tests 5 times in a row to check for flakiness: `for i in 1 2 3 4 5; do uv run pytest tests/e2e/test_watch*.py -q || break; done`), `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`; report any failure with its output

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → user stories.
- **US1 (Phase 3)** depends on Phase 2 (reconcile, lock).
- **US2 (Phase 4)** depends on Phase 2 and on T010 (`open_theatre(reconcile=…)`) from US1.
- **US3 (Phase 5)** depends on US1 (T011, lock in `set_value`) and US2 (watch) — it tests their interplay.
- **Polish (Phase 6)** after all stories.

### Within Each Story

Tests first (see them fail) → implementation → run to green → deliberate-break check → commit with a message saying why.

### Parallel Opportunities

- Phase 2: T002 ∥ T003 (tests); T004 ∥ T005 (different files); T006 after T004.
- US1: T008 then T009 (same file).
- US2: T014 ∥ T015 after T013 (fixture); T016 → T017 → T018 (sequential: each uses the previous).
- US3: T020 ∥ T021.
- Polish: T024 ∥ T025.

## Parallel Example: User Story 2

```bash
# After T013 (watch fixture) is in place:
Task: "E2E tests for watch behaviour in tests/e2e/test_watch.py"            # T014
Task: "E2E tests for watch lifecycle in tests/e2e/test_watch_lifecycle.py"  # T015
```

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 + Phase 2.
2. Phase 3 (US1): every command picks up offline edits — useful on its own, no long-running process.
3. **Stop and validate** with T008/T009 and the step 1 suite.

### Incremental Delivery

1. US1 → commit ("why": edits made outside troupe were invisible to history).
2. US2 → commit ("why": record edits as they happen).
3. US3 → commit ("why": prove a `set` under `watch` is recorded once).
4. Polish → commit.

## Notes

- Every commit message says why the change was made (Principle VI).
- `config history` never reconciles, so tests use it to observe what other processes recorded.
- Concurrent `set`s and more than one `watch` are out of contract (spec D-16); do not test them.

## Phase 7: Convergence

- [ ] T028 CRITICAL: Add an e2e test in `tests/e2e/test_watch_lifecycle.py` that, while `watch` runs on `a: 1`, deletes `.troupe/troupe.yml` (expect one `troupe: error:` stderr line naming it within 2 s, nothing recorded, process alive), then recreates it as `a: 2` and expects `set a 1 → 2` within 2 s of the recreation per Constitution II / spec Edge Cases "File deleted and recreated" (partial)
- [ ] T029 CRITICAL: Add an e2e test in `tests/e2e/test_watch_exactly_once.py` that holds `theatre_lock(theatre.root)` in the test process, edits `a: 1 → 2`, waits 0.5 s, sends SIGTERM to `watch`, waits 0.5 s, then releases the lock; assert `watch` exits 0 with stdout exactly `watching <dir>\n`, and the store holds either exactly the one `set a 1 → 2` event or none, never part of a reconcile (with a single-leaf edit, check it is exactly one event) per Constitution II / spec Edge Cases "Signal during a reconcile", FR-105, FR-115 (partial)
- [ ] T030 CRITICAL: Add e2e tests in `tests/e2e/test_reconcile.py` for hand edits that change a node's kind: `m: plain` → `m: {k: 1, j: [x]}` followed by `config show m.k` records `set m.k` (null → 1) and `set m.j.0` (null → "x") then `remove m` ("plain" → null), in that order; and the reverse `m: {k: 1}` → `m: 3` records `set m` (null → 3) then `remove m.k` (1 → null) per Constitution II / spec Edge Cases "Scalar replaced by a collection by hand, or the reverse" (partial)
- [ ] T031 Add a `watch` e2e test in `tests/e2e/test_watch.py` with a two-level include (`troupe.yml` → `agents/coder.yaml` → `agents/limits.yaml`): editing `limits.yaml` records the matching `set` within 2 s per SC-101 (partial)
