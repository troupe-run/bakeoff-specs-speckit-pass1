---

description: "Task list for troupe configuration — set --in-include (Step 5, CR-B)"
---

# Tasks: troupe configuration — `set --in-include` (Step 5, CR-B)

**Input**: Design documents from `specs/006-set-in-include/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md;
CR-A implemented (`specs/005-include-overrides/tasks.md` complete — this list uses its
`place_new_key`, `merge`, `EditPlan.by_site` and the `options` parameter of `assert_set` /
`assert_refused` from its T002).

**Tests**: MANDATORY (Constitution Principle II). End-to-end tests run the real CLI through the
`theatre` fixture in `tests/conftest.py` (see CR-A's tasks.md header for the helpers);
`assert_set(theatre, files, path, value, expected, options=("--in-include",))` runs
`set --in-include` and checks that exactly the `expected` files changed to exactly those bytes. Write
each test task's tests first and see them fail; after the implementation passes, break the behaviour
deliberately once to confirm the test catches it.

**Organization**: US1 add a key to the shared file on purpose (P1), US2 the option is predictable
everywhere else (P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2

## Path Conventions

Single project: `src/troupe/`, `tests/` at the repository root.

---

## Phase 1: Setup

- [X] T001 Confirm CR-A is complete: every task in `specs/005-include-overrides/tasks.md` is checked and the gates are green (`uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`); record the output

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The option exists and reaches the placement function; merged mappings know their base.

- [X] T002 [P] Extend `tests/e2e/test_usage.py` (tests first): `test_in_include_on_other_subcommands_exits_2` parametrised over `("get", "a", "--in-include")`, `("show", "--in-include")`, `("history", "--in-include")`, `("watch", "--in-include")` → `assert_failed(result, 2, "--in-include")` and `theatre.snapshot()` unchanged (FR-466); `test_in_include_with_a_value_exits_2` (`set a 1 --in-include=yes` → exit 2 naming `--in-include`, FR-466); `test_in_include_in_any_position_and_repeated` (`set --in-include a 2`, `set a 2 --in-include`, `set a 2 --in-include --in-include` each exit 0, FR-460); `test_in_include_with_reason` (`set a 3 --in-include --reason why` → last history event `reason == "why"`, FR-460, FR-465)
- [X] T003 In `src/troupe/cli.py` add to `set_parser`: `add_argument("--in-include", action="store_true", help="write a new key into the included file instead of as an override")`; pass `in_include=args.in_include` to `commands.set_value`. Thread a keyword-only `in_include: bool = False` through `commands.set_value` (`src/troupe/config/commands.py`) → `apply_set` (`src/troupe/config/edit/apply.py`) → `plan_set` (`src/troupe/config/edit/planner.py`) → `override.place_new_key` (`src/troupe/config/edit/override.py`), not yet used there. Run T002 to green
- [X] T004 In `src/troupe/config/tree.py` add `base: "LocatedMapping | None" = None` to `LocatedMapping` (comment: "a merged mapping's included part before overrides — its entries are only that file's; CR-B D-51, research I-2") and `def shared_part(mapping: LocatedMapping) -> LocatedMapping` that follows `base` while it is set; in `src/troupe/config/loader.py` `merge` set `merged.base = base` on every merged mapping it creates. Extend `tests/unit/test_merge.py` with `test_merged_mapping_keeps_its_base` (a merged mapping's `base.entries` are exactly the included file's entries, in order) and `test_shared_part_follows_nested_bases` (`troupe.yml` → `coder.yaml` with `model: {$ref: file:model.yaml, a: 1}` + override in `troupe.yml` → `shared_part` of `agents.coder.model` is `model.yaml`'s mapping)

**Checkpoint**: the option parses everywhere correctly; no placement change yet.

---

## Phase 3: User Story 1 - Add a setting to the shared file on purpose (Priority: P1) 🎯 MVP

**Goal**: `set --in-include` writes a new key under included content into the included file by the
step 1 rule; the including file is untouched.

**Independent Test**: `assert_set(..., options=("--in-include",))` fixtures where only the included
file changes.

- [X] T005 [P] [US1] Create `tests/e2e/test_set_in_include.py` (tests first):
  - spec US1 scenario 1: `troupe.yml` `agents:\n  coder: file:agents/coder.yaml  # c\n`, `coder.yaml` `model: sonnet\n`; `set --in-include agents.coder.temperature 0.3` → `coder.yaml` exactly `model: sonnet\ntemperature: 0.3\n`, `troupe.yml` unchanged (FR-461);
  - scenario 2: missing intermediates `limits.retries` → `limits:\n  retries: 3\n` appended in `coder.yaml` (FR-461, FR-463);
  - scenario 3: merged ancestor (override `limits: {timeout: 30}` in `troupe.yml`, `coder.yaml` `limits:\n  retries: 2\n`) → `  backoff: 2` added under `limits` in `coder.yaml`, `troupe.yml` unchanged (FR-462, D-51);
  - scenario 4: the same command without the option writes the override in `troupe.yml` (CR-A default unaffected);
  - scenario 5: nested includes → written into `model.yaml` (`shared_part`, research I-2);
  - `test_mapping_form_without_overrides_writes_the_included_file` (spec edge case; `troupe.yml` keeps its mapping form bytes);
  - `test_ancestor_only_in_an_override_stays_in_that_file` (spec edge case, D-51);
  - `test_flow_mapping_in_the_included_file` (`coder.yaml` `{model: x}` → `{model: x, temperature: 0.3}`, step 1 FR-034);
  - `test_file_included_twice_gets_the_key_under_both_paths` (`a: file:common.yaml\nb: file:common.yaml`; `set --in-include a.y 2` → `common.yaml` gains `y: 2`; `get b.y` prints `2`; history has `set` events for `a.y` and `b.y`, FR-465, research I-3);
  - `test_step_1_fixture_passes_again_with_the_option` (SC-462: the fixture of CR-A's renamed `test_new_key_under_an_include_becomes_an_override`, run with `--in-include`, expects step 1's original result `agents/coder.yaml` → `model: sonnet\nretries: 3\n`)
- [X] T006 [US1] In `src/troupe/config/edit/override.py` `place_new_key`, first branch: `if in_include:` return `planner._new_key(loaded, shared_part(X) if X.overrides is not None else X, …)` — a step 1 plan (`by_site=False`, content identity, research I-3), with the anchor path of X; comment "spec FR-461, FR-462, D-51: the step 1 rule, into the shared part of a merged mapping". Run T005 to green; break the branch once (e.g. drop `shared_part`) to confirm scenario 3 fails

**Checkpoint**: MVP — CR-B's promise holds.

---

## Phase 4: User Story 2 - The option is predictable everywhere else (Priority: P2)

**Goal**: The option changes nothing but new-key placement under included content (D-50).

- [ ] T007 [P] [US2] Add to `tests/e2e/test_set_in_include.py` a helper `same_with_and_without(theatre_factory, files, path, value)` that runs the `set` on two fresh theatres (`tmp_path / "plain"`, `tmp_path / "flag"`), one with `--in-include`, and asserts equal exit codes, equal snapshots (relative to each theatre) and equal history `(op, path, old, new, via, reason)` tuples. Use it for spec US2 scenarios 1–4: existing overridden value (override changes in `troupe.yml`), existing non-overridden value (changes in `coder.yaml`), new key with ancestor in the main file, list append in `coder.yaml`; plus key inside a list item of `coder.yaml`, a text-include target write, and a refused write (`set --in-include agents.coder '{a: 1}'` → exit 3 both ways) (FR-464, SC-461)
- [ ] T008 [US2] Run T007; any difference means the flag leaks outside `place_new_key` — fix by removing that use (Principle IV: the flag is read in one place)

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T009 [P] README `set` section: document `--in-include` beside CR-A's override rules, with a one-line example and the D-50 note ("existing values, list appends and keys inside list items are unaffected"); link `specs/006-set-in-include/`
- [ ] T010 Run the gates and show the output: `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`; walk through `quickstart.md`

---

## Dependencies & Execution Order

- CR-A complete → T001 → T002–T004 (T002 and T004 in parallel; T003 after T002) → US1 (T005–T006) → US2 (T007–T008) → Polish (T009–T010).
- US2 needs only Phase 2, but its tests pair results with the flag's US1 behaviour absent, so running it after US1 confirms the flag's effect is confined.

## Parallel Opportunities

- T002 with T004; T005 while T004 is finishing (different files); T007 with T009.

## Implementation Strategy

MVP = Phases 1–3. Commit after each checkpoint with a message that says why (Principle VI).
