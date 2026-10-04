---

description: "Task list for troupe configuration — lineage (Step 4)"
---

# Tasks: troupe configuration — lineage (Step 4)

**Input**: Design documents from `specs/004-config-lineage/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: MANDATORY. Constitution Principle II overrides the template's "tests are optional". Every
behaviour gets a test that fails when it breaks. End-to-end tests run the real `troupe` CLI (the
`theatre` fixture in `tests/conftest.py`: `theatre.write(relpath, text)` writes under `.troupe/`,
`theatre.config(*args)` runs `troupe config … --theatre <root>` and returns `Result(code, out, err)`,
`theatre.run(*args, env={...})` runs with extra environment variables, `theatre.snapshot()` gives every
file's bytes, `assert_failed(result, code, mention)` checks a non-zero exit with empty stdout and
`mention` in stderr, `set_ok(theatre, path, value)` runs a successful `set`, `start_watch()` starts
`config watch`, `wait_for_history(theatre, predicate, since)` polls the store). Write each test task's
tests first and see them fail. Once the implementation passes, break the behaviour deliberately once
to confirm the test catches it.

**Organization**: Grouped by user story (spec.md): US1 who and how — actor and via (P1), US2 what
changed together — change (P1), US3 when and why — at and `--reason` (P2), US4 survives restarts (P1).
US4 is ordered after US3 because it checks all five fields, but it does not need US3's `--reason` to
be meaningful (it can run with reasons omitted).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 / US4

## Path Conventions

Single project: `src/troupe/`, `tests/` at the repository root (plan.md → Project Structure).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the step 3 baseline is green, and make the test harness independent of the
developer's own `TROUPE_ACTOR` before any lineage behaviour exists.

- [X] T001 Run the gates on the unchanged tree and record the output: `uv sync`, `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`; if anything fails, stop and report it before step 4 work begins
- [X] T002 In `tests/conftest.py` add a module constant `INHERITED_ENV_DROPPED = ("TROUPE_THEATRE", "TROUPE_ACTOR")` and use it in both `Theatre.run` and `start_watch` instead of the literal `"TROUPE_THEATRE"` filter, so an actor exported in the developer's shell can never decide a test's outcome (plan: Constitution Check II). Also set `LOGNAME` to the fixed value `TEST_LOGIN = "troupe-tester"` in that base environment (callers' `env` still overrides it), so FR-321's login name is known in every test (research L-6: `getpass.getuser()` reads `LOGNAME` first). Run the suite: still green

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Lineage values, storage in the event, stamping at the three recording sites, and the
`history` output. Every story's tests read these fields, so this phase blocks all stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for the foundation

- [X] T003 [P] Create `tests/unit/test_lineage.py` (tests first; they fail until T005):
  - `test_actor_from_env_unset_is_human_with_login_name`: `actor_from_env({}, login=lambda: "dev") == Actor("human", "dev")` — see T005 for the injectable `login` parameter;
  - `test_actor_from_env_unset_with_unknown_login_has_null_id`: `login=lambda: None` → `Actor("human", None)` (FR-321, D-34);
  - `test_actor_from_env_accepts_human_and_agent`: parametrised `"human:alice"` → `Actor("human", "alice")`, `"agent:coder-7"` → `Actor("agent", "coder-7")`, `"agent:team:coder"` → id `"team:coder"`, `"human: spaced "` → id `" spaced "`, `"agent:café"` → id `"café"` (FR-320, D-33);
  - `test_actor_from_env_rejects_anything_else`: parametrised `""`, `"human"`, `"human:"`, `"agent:"`, `"Human:alice"`, `"AGENT:x"`, `"robot:x"`, `":x"`, `"unknown:x"` → raises `UsageError` (exit code 2) whose message contains `"TROUPE_ACTOR"` and the value's `repr` (FR-322, D-32);
  - `test_login_name_is_none_when_lookup_fails`: monkeypatch `getpass.getuser` to raise `OSError`, then `KeyError`, then return `""` → `login_name() is None` each time (research L-6);
  - `test_format_at_is_rfc3339_utc_with_z`: `format_at(datetime(2026, 10, 4, 9, 5, 7, 123, tzinfo=UTC)) == "2026-10-04T09:05:07.000123Z"`; a non-UTC aware datetime (`timezone(timedelta(hours=2))`) is converted to UTC before formatting (research L-4, spec edge case "non-UTC time zone");
  - `test_begin_gives_fresh_change_and_current_at`: two `Lineage.begin(UNKNOWN_ACTOR, "file")` calls → different `change`, both non-empty; `at` parses with `datetime.strptime(at, "%Y-%m-%dT%H:%M:%S.%fZ")` and lies between UTC times taken before and after the call (FR-303, FR-305, research L-3)
- [X] T004 [P] Extend `tests/unit/test_reconcile.py` (which builds a real theatre and `ConfigStore`): update its `import_leaves` / `reconcile` calls to the new signatures from T006/T007 and add `test_reconcile_stamps_one_file_lineage`: after an import and a hand edit changing two leaves, `reconcile(...)` records two events whose `HistoryRecord.lineage` are equal, have `via == "file"`, actor `UNKNOWN_ACTOR`, `reason is None`, and a `change` different from the import events' `change`; `test_empty_reconcile_records_nothing`: a second reconcile adds no record (spec edge case "records no events")

### Implementation for the foundation

- [X] T005 Create `src/troupe/config/lineage.py` (module docstring: "Who, how, when, why and with-what-else for every recorded event — spec FR-300 – FR-332, D-30 – D-38; research L-2 – L-6. Each decision below lives only here (Principle IV)."). Contents:
  - `ACTOR_ENV = "TROUPE_ACTOR"`; `type ActorKind = Literal["human", "agent", "unknown"]`; `type Via = Literal["import", "file", "cli"]`; `CLI_ACTOR_KINDS: tuple[ActorKind, ...] = ("human", "agent")`;
  - `@dataclass(frozen=True) class Actor: kind: ActorKind; id: str | None`; `UNKNOWN_ACTOR = Actor("unknown", None)` (FR-310: imports and file events);
  - `login_name() -> str | None`: `getpass.getuser()`, returning `None` on `OSError` or `KeyError` or an empty result (D-34, research L-6);
  - `actor_from_env(environ: Mapping[str, str], login: Callable[[], str | None] = login_name) -> Actor`: if `ACTOR_ENV not in environ` → `Actor("human", login())`; else `kind, sep, ident = value.partition(":")`; valid iff `sep and kind in CLI_ACTOR_KINDS and ident` → `Actor(kind, ident)` (id kept exactly, D-33); otherwise `raise UsageError(f"{ACTOR_ENV}: {value!r} is not human:<id> or agent:<id>")` ("anything else → exit 2", FR-322; the empty string is "anything else", D-32);
  - `format_at(moment: datetime) -> str`: `moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")` ("RFC 3339 UTC timestamp ending in `Z`", research L-4);
  - `new_change_id() -> str`: `str(uuid.uuid4())` (opaque, unique per unit, D-37, research L-3);
  - `@dataclass(frozen=True) class Lineage: actor: Actor; via: Via; at: str; reason: str | None; change: str` with `@classmethod begin(cls, actor: Actor, via: Via, reason: str | None = None) -> Lineage` that sets `at=format_at(datetime.now(UTC))`, `change=new_change_id()` — comment: "one Lineage per recorded unit (import, reconcile, or a set's own change): every event of the unit shares change and at (FR-303, FR-305, D-30)"
  Run T003 to green
- [X] T006 In `src/troupe/config/store.py`: (a) `HistoryRecord` gains `lineage: Lineage`; (b) `TheatreConfig.change` becomes `change(self, op, path, old, new, actor_kind: str, actor_id: str | None, via: str, at: str, reason: str | None, change: str)` — the `@event("LeafChanged")` arguments are what `eventsourcing` persists and replays, so lineage survives restarts with the event (FR-306, research L-1); its body rebuilds `Lineage(Actor(actor_kind, actor_id), via, at, reason, change)` (use `typing.cast` to the `Literal` types) and appends it to the `HistoryRecord`; no defaults for the new arguments (research L-8: pre-step-4 stores are out of contract); (c) add a private helper `_apply(aggregate, item: LeafEvent, lineage: Lineage)` passing the lineage's fields; (d) `import_leaves(self, leaves, lineage: Lineage)` and `record(self, events, lineage: Lineage)` stamp every event of the call with that one lineage; `record` keeps its early return on an empty list (an empty unit leaves no trace)
- [X] T007 Stamp the units at their recording sites: in `src/troupe/config/sync.py` `reconcile` calls `store.record(events, Lineage.begin(UNKNOWN_ACTOR, "file"))` (docstring: "file-originated events have the unknown actor and via `file` — FR-302, FR-310"); in `src/troupe/config/commands.py` `open_theatre` calls `store.import_leaves(leaves(loaded.root), Lineage.begin(UNKNOWN_ACTOR, "import"))`; `set_value(theatre, path_text, value_text, actor: Actor, reason: str | None)` records its events with `Lineage.begin(actor, "cli", reason)`, created after `open_theatre` returns so the `set`'s `change` and `at` are its own (D-30, FR-331); in `src/troupe/cli.py` pass `actor=actor_from_env(os.environ)` and `reason=None` for now (T013 and T019 complete the CLI). Run T004 to green
- [X] T008 In `src/troupe/config/commands.py` `history`: build each entry as `{"seq", "op", "path", "old", "new", "actor": {"kind": l.actor.kind, "id": l.actor.id}, "via": l.via, "at": l.at, "reason": l.reason, "change": l.change}` in exactly that key order (FR-300, D-38), keep `json.dumps(entry, ensure_ascii=False)`
- [X] T009 Keep the existing tests proving what they proved: in `tests/conftest.py` add `CORE_FIELDS = ("seq", "op", "path", "old", "new")`; `Theatre.history()` returns each line reduced to `CORE_FIELDS` (docstring: "step 1's fields only; lineage is checked by `Theatre.events()`"), and a new `Theatre.events(path: str | None = None) -> list[dict[str, Any]]` returns full lines with `env` passthrough (`events(path, env={...})` for running `history` under a given `TROUPE_ACTOR`); `recorded()` keeps building core-field dicts. In `tests/e2e/test_history.py` change `test_non_ascii_strings_are_written_literally` to check the raw line starts with `'{"seq": 1, "op": "import", "path": "name", "old": null, "new": "café 🎭", "actor": '` and still contains `café 🎭` literally. Add `test_history_line_keys_in_contract_order` in `tests/e2e/test_history.py`: after an import and a `set`, every parsed line's `list(keys)` equals `["seq", "op", "path", "old", "new", "actor", "via", "at", "reason", "change"]` and `list(line["actor"])` equals `["kind", "id"]` (FR-300, FR-301). Run the whole suite to green; deliberately swap `via` and `at` in T008 and confirm the key-order test fails; restore. Commit ("why": every event now carries its lineage, stored with the event itself)

**Checkpoint**: every event has lineage; `history` prints it; the step 1–3 suite is green.

---

## Phase 3: User Story 1 - Know who changed a setting, and how (Priority: P1) 🎯 MVP

**Goal**: Each event names its actor (human/agent/unknown and id) and `via` (import/cli/file);
`TROUPE_ACTOR` is honoured and an invalid value is refused by every command before anything happens
(FR-302, FR-310, FR-311, FR-320 – FR-323).

**Independent Test**: Import, `set` under unset / `human:alice` / `agent:coder-7`, hand edit then
`get`, a hand edit under `watch`; compare `actor` and `via` per line; invalid actors on every
subcommand exit 2 with nothing recorded (spec US1 scenarios 1–7).

### Tests for User Story 1

- [X] T010 [P] [US1] Create `tests/e2e/test_lineage_actor.py` (use `theatre.events()`):
  - `test_import_events_have_unknown_actor_via_import`: fresh theatre `a: 1\nb: [x, y]\n`, run with `env={"TROUPE_ACTOR": "agent:coder-7"}` `config history` → every line `actor == {"kind": "unknown", "id": None}`, `via == "import"` (US1-1, spec edge case "first command with TROUPE_ACTOR set");
  - `test_set_events_have_the_cli_actor`: parametrised `("agent:coder-7", {"kind": "agent", "id": "coder-7"})`, `("human:alice", {"kind": "human", "id": "alice"})`, `("agent:team:coder", {"kind": "agent", "id": "team:coder"})`, `("human:Zoë Q", {"kind": "human", "id": "Zoë Q"})`: import, then `theatre.run("config", "set", "a", "2", env={"TROUPE_ACTOR": value})` → the last line has that actor and `via == "cli"` (US1-2, US1-3, FR-320);
  - `test_set_without_troupe_actor_uses_the_login_name`: run `set a 2` with `TROUPE_ACTOR` absent and `env={"LOGNAME": "dev"}` → actor `{"kind": "human", "id": "dev"}` (US1-4, FR-321);
  - `test_set_without_any_login_name_has_null_id`: run with `LOGNAME`, `USER`, `LNAME`, `USERNAME` all removed from the environment (pass a base env built without them — add a `drop: tuple[str, ...]` parameter to `Theatre.run` in `tests/conftest.py` for this) only if `pwd.getpwuid(os.getuid())` raises `KeyError` in the test process, else `pytest.skip("uid has a passwd entry; covered by tests/unit/test_lineage.py")` — state in the docstring that the e2e path is environment-dependent (research L-6, D-34);
  - `test_hand_edit_reconciled_by_a_command_has_unknown_actor_via_file`: import, write `a: 5`, run `get a` with `TROUPE_ACTOR=agent:coder-7` → stdout `5\n`; last line `actor == {"kind": "unknown", "id": None}`, `via == "file"` (US1-5, FR-310, SC-306);
  - `test_reconcile_then_set_in_one_command_have_their_own_via`: import, hand edit `a`, then `set b 5` under `TROUPE_ACTOR=human:alice` → the `a` event is `file`/unknown and the `b` event is `cli`/alice (D-30)
- [X] T011 [P] [US1] Create `tests/e2e/test_lineage_errors.py`: `INVALID = ["", "human", "human:", "agent:", "Human:alice", "robot:x", ":x", "unknown:x"]`; `SUBCOMMANDS = [("get", "a"), ("show",), ("show", "a"), ("set", "a", "9"), ("history",)]`; `test_invalid_troupe_actor_exits_2_and_records_nothing` parametrised over both on (i) a never-imported theatre and (ii) an imported theatre with an unreconciled hand edit: `assert_failed(result, 2, "TROUPE_ACTOR")`, `theatre.snapshot()` unchanged, and the store is unchanged (`(theatre.root / ".troupe" / STORE_FILENAME).exists()` is False for (i); for (ii) `recorded(theatre)` equals what it was before) — run `history` for (ii)'s check without `TROUPE_ACTOR` (FR-322, FR-323, SC-303); `test_invalid_troupe_actor_stops_watch`: `start_watch(env={"TROUPE_ACTOR": "robot:x"})` → the process exits 2, stdout empty, stderr names `TROUPE_ACTOR`, no store created (D-31)
- [X] T012 [P] [US1] Create `tests/e2e/test_lineage_watch.py`: `test_watch_hand_edit_has_unknown_actor_via_file` — import, `start_watch(env={"TROUPE_ACTOR": "agent:w"})`, edit `a: 1` → `a: 2`, `wait_for_history` until the `set` appears, stop the watcher, then `theatre.events()[-1]` has actor unknown/null and `via == "file"` (US1-6); `test_set_under_watch_keeps_its_own_lineage` — with `watch` running, `theatre.run("config", "set", "a", "3", env={"TROUPE_ACTOR": "human:alice"})`, wait 3 s, stop → exactly one new event, `via == "cli"`, actor alice (spec edge case "set under watch"; step 2 FR-130)

### Implementation for User Story 1

- [X] T013 [US1] In `src/troupe/cli.py` `run`: right after `parse_args`, `actor = actor_from_env(os.environ)` for every subcommand, before the theatre path is used or any command dispatched (FR-323, D-31; comment citing research L-5); pass `actor` to `commands.set_value`. Confirm `UsageError` from `actor_from_env` reaches `main`'s handler (exit 2, `troupe: error: TROUPE_ACTOR: …` on stderr, empty stdout). Run T010 – T012 to green
- [X] T014 [US1] Deliberately (a) move the `actor_from_env` call into `set_value` only and confirm T011 fails for `get`/`show`/`history`/`watch`; (b) stamp reconcile events with the command's actor and confirm T010's `…_via_file` tests fail; (c) treat `""` as unset and confirm T011 fails; restore. Commit ("why": every change names who made it, and hand edits are never credited to the CLI user)

**Checkpoint**: who and how are answered for every event.

---

## Phase 4: User Story 2 - See which settings changed together (Priority: P1)

**Goal**: `change` is equal within each unit (import, reconcile, a `set`'s own change) and distinct
between units (FR-305, D-30, D-37).

**Independent Test**: Multi-event import, list-replacing `set`, two-key hand edit, reconcile + `set`
in one invocation, repeated `set`s, PATH-filtered history (spec US2 scenarios 1–6).

### Tests for User Story 2

- [X] T015 [P] [US2] Create `tests/e2e/test_lineage_change.py` (use `theatre.events()`):
  - `test_import_events_share_one_change`: `a: 1\nb: [x, y]\n` → the three import lines have one `change`, a non-empty string (US2-1);
  - `test_one_set_shares_one_change_across_set_and_remove`: `set b '[z]'` → `b.0` set and `b.1` remove share a `change` different from the import's (US2-2);
  - `test_one_hand_edit_reconcile_shares_one_change`: edit `a` and `b.0` by hand, `config show` → the two reconcile lines share a `change` (US2-3; step 2 D-14 coalescing);
  - `test_reconcile_and_set_in_one_invocation_are_separate_changes`: hand edit `a`, then `set c 1` → two distinct `change` values (US2-4, D-30);
  - `test_first_set_on_a_fresh_theatre_separates_import_and_set`: fresh theatre, `set a 2` as the first command → import lines share one `change`, the set line has another (D-30);
  - `test_changes_are_distinct_across_many_commands`: 10 `set`s alternating `a` between `1` and `2` (plus one `set b '[z, w, v]'` producing several events) → group lines by `change`: each group is exactly one command's events (verify by `seq` ranges recorded per command), and the number of distinct `change` values equals the number of units (US2-5, SC-302);
  - `test_filtered_history_keeps_change_values`: `config history b` lines are a subset (as whole dicts) of the unfiltered lines, so `change` is identical (US2-6);
  - `test_set_that_changes_nothing_leaves_no_change`: `set a 1` when `a` is already 1 → no new line, the set of `change` values is unchanged (spec edge case "records no events")

### Implementation for User Story 2

- [X] T016 [US2] Run T015; the foundation (T005 – T007) should already satisfy it. Fix any gap in `src/troupe/config/store.py` / `src/troupe/config/commands.py` (e.g. a `Lineage.begin` created before the reconcile and reused for the `set`). Deliberately (a) create one `Lineage` in `open_theatre` and reuse it for the `set`'s events and confirm `…separate_changes` fails; (b) call `Lineage.begin` per event in `store.record` and confirm `…shares_one_change` tests fail; restore. Commit ("why": a multi-value change can be reviewed as one unit)

**Checkpoint**: what-else-changed is answered for every event.

---

## Phase 5: User Story 3 - Know when and why (Priority: P2)

**Goal**: `at` is an RFC 3339 UTC time ending in `Z`, shared within a unit, inside the recording
command's run; `set --reason TEXT` is recorded on the `set`'s own events only (FR-303, FR-304,
FR-330 – FR-332, D-35, D-36).

**Independent Test**: Note UTC times around each command; `set` with and without `--reason`;
reason scoping when a reconcile happens in the same invocation; `--reason` misuse → exit 2 (spec US3
scenarios 1–6).

### Tests for User Story 3

- [X] T017 [P] [US3] Create `tests/e2e/test_lineage_when_why.py` (use `theatre.events()`):
  - `test_reason_is_recorded_on_the_sets_events`: `set a 2 --reason "raise for load test"` → `reason == "raise for load test"` (US3-1);
  - `test_reason_is_null_without_reason_and_on_import_and_file_events`: `set a 3` → `reason is None`; every `import` and `file` line in the history has `reason is None` (US3-2, FR-304);
  - `test_reason_applies_to_every_event_of_the_set`: `set b '[z]' --reason trim` replacing `[x, y]` → both lines `reason == "trim"` (US3-3);
  - `test_reason_does_not_apply_to_the_reconcile_in_the_same_command`: hand edit `a`, then `set c 1 --reason x` → the `a` line's reason is None, the `c` line's is `"x"` (US3-4, FR-331);
  - `test_reason_text_is_kept_exactly`: parametrised `""` (→ `""`, not None, D-36), `"line one\nline two"`, `'say "hi"'`, `"café 🎭"`, `"--looks-like-an-option"` (passed as `--reason=--looks-like-an-option`) → recorded exactly; the raw `history` line is valid JSON (spec edge case "reason text");
  - `test_at_is_rfc3339_utc_within_the_command`: for an import (`history`), a reconcile (`get` after a hand edit) and a `set`, take `datetime.now(UTC)` before and after each command; the event's `at` ends with `Z`, parses with `datetime.strptime(at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)`, and lies within `[before, after]` (US3-5, FR-303);
  - `test_at_is_shared_within_a_unit`: the two lines of `set b '[z]'` and the three import lines each have one `at` (FR-303, D-35);
  - `test_at_is_utc_whatever_the_time_zone`: run `set` with `env={"TZ": "America/New_York"}` → `at` still within the UTC bounds (spec edge case "non-UTC time zone")
- [X] T018 [P] [US3] In `tests/e2e/test_usage.py` add exit-2 cases that record nothing and change no file: `("config", "set", "a", "2", "--reason")` (no TEXT, FR-330), `("config", "get", "a", "--reason", "x")`, `("config", "show", "--reason", "x")`, `("config", "history", "--reason", "x")`, `("config", "watch", "--reason", "x")` (FR-332)

### Implementation for User Story 3

- [X] T019 [US3] In `src/troupe/cli.py` add `set_parser.add_argument("--reason", metavar="TEXT", default=None, help="why the change is made (recorded in history)")` and pass `reason=args.reason` to `commands.set_value` (replacing T007's `None`). Run T017 – T018 to green; deliberately (a) pass the reason to the reconcile lineage too and confirm `…reconcile_in_the_same_command` fails; (b) use `datetime.now()` (local time) in `Lineage.begin` and confirm the `TZ` test fails; (c) map `""` to `None` and confirm the `""` case fails; restore. Commit ("why": auditors can see when each change was made and the reason given for it)

**Checkpoint**: when and why are answered for every event.

---

## Phase 6: User Story 4 - The audit trail survives restarts (Priority: P1)

**Goal**: Lineage is persisted with the events and is printed identically by every later process,
whatever its `TROUPE_ACTOR` (FR-306, SC-304).

**Independent Test**: Record events with several actors and reasons, then list history from new
processes with `TROUPE_ACTOR` unset and set to a different actor; earlier lines are byte-identical
(spec US4 scenarios 1–2).

### Tests for User Story 4

- [X] T020 [P] [US4] Create `tests/e2e/test_lineage_persist.py`: build history with an import, a `set` under `agent:a` with `--reason r1`, a hand edit reconciled by `show`, and a `set` under `human:b`; capture `theatre.config("history").out` (raw text); then (a) run `history` again with `TROUPE_ACTOR` unset, (b) with `env={"TROUPE_ACTOR": "human:other", "LOGNAME": "someone-else"}`, (c) after one more `set` under `agent:c`: the earlier output is a byte-for-byte prefix of each later output (US4-1, US4-2, SC-304); also check, by reading the store through a fresh `ConfigStore(theatre.root).history()` in the test process, that each `HistoryRecord.lineage` equals the corresponding parsed line (lineage is in the store, not recomputed at print time — FR-306)

### Implementation for User Story 4

- [X] T021 [US4] Run T020; the foundation (T006) should already satisfy it. Deliberately make `history` print the *current* command's actor for `cli` events (instead of the stored one) and confirm T020 (b) fails; restore. Commit ("why": an audit trail that changes after the fact is not an audit trail)

**Checkpoint**: all four stories work.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T022 [P] Update `README.md`: add `[--reason TEXT]` to the `set` line; a short "Lineage" paragraph: each history line also has `actor`, `via`, `at`, `reason`, `change`; `TROUPE_ACTOR=human:<id>|agent:<id>` (unset → your login name; anything else → exit 2); hand edits and the first import are recorded with actor `unknown`; one example line from `specs/004-config-lineage/contracts/cli.md`; add `specs/004-config-lineage/` to the links
- [X] T023 [P] Traceability notes in earlier specs: in `specs/002-config-file-sync/spec.md` Assumptions, append to the "History needs no field…" bullet "*(Superseded by step 4: `via` tells hand edits from `set`; see `specs/004-config-lineage/spec.md`.)*"; in `specs/001-config-load-show-set/contracts/cli.md` add a one-line note that history lines gain lineage fields in step 4
- [X] T024 Walk through `specs/004-config-lineage/quickstart.md` by hand and confirm each expected output
- [X] T025 Run the full gates and show output: `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`; report any failure with its output. Commit polish ("why": docs and earlier specs agree with lineage, Principle VI)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — T001 then T002.
- **Foundational (Phase 2)**: after Setup; blocks every story. T003, T004 (tests) in parallel; T005 → T006 → T007 → T008 → T009.
- **US1 (Phase 3)**: after Phase 2. T010 – T012 in parallel, then T013 → T014.
- **US2 (Phase 4)**: after Phase 2; independent of US1 (its tests use `TROUPE_ACTOR` only incidentally). T015 → T016.
- **US3 (Phase 5)**: after Phase 2; T019 edits `src/troupe/cli.py`, so do it after T013 if both are in flight.
- **US4 (Phase 6)**: after Phase 2; its fixture uses `TROUPE_ACTOR` (US1) and `--reason` (US3) — run after T013 and T019, or drop `--reason r1` if done earlier.
- **Polish (Phase 7)**: after all stories.

### Within Each User Story

- Tests first and failing; implementation; green; deliberate break; commit.

### Parallel Opportunities

- T003 ∥ T004 (different test files).
- T010 ∥ T011 ∥ T012 (three new test files).
- After Phase 2: T015 (US2 tests) ∥ T017/T018 (US3 tests) ∥ US1 tests.
- T022 ∥ T023.

## Parallel Example: User Story 1

```text
Task: "T010 Create tests/e2e/test_lineage_actor.py"
Task: "T011 Create tests/e2e/test_lineage_errors.py"
Task: "T012 Create tests/e2e/test_lineage_watch.py"
```

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 (baseline, harness isolation) → Phase 2 (lineage stored and printed).
2. Phase 3: actor and via, `TROUPE_ACTOR` validation. **Stop and validate**: who/how answered.

### Incremental Delivery

1. Foundation → every line carries lineage (with `reason` always null until US3).
2. + US1 → who and how, invalid actors refused.
3. + US2 → grouping proven.
4. + US3 → `--reason`, timestamp guarantees.
5. + US4 → persistence proven.
6. Polish → docs, gates.

## Notes

- Commit after each phase with a message that says why (Principle VI).
- Never mark a task done without showing test, mypy and ruff output (Principle III).
- Pre-step-4 stores are out of contract (research L-8): add no migration or defaults.
