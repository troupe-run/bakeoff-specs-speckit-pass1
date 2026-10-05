---

description: "Task list for troupe configuration — include overrides (Step 5, CR-A)"
---

# Tasks: troupe configuration — include overrides (Step 5, CR-A)

**Input**: Design documents from `specs/005-include-overrides/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: MANDATORY. Constitution Principle II overrides the template's "tests are optional". Every
behaviour gets a test that fails when it breaks. End-to-end tests run the real `troupe` CLI through
the `theatre` fixture in `tests/conftest.py`: `theatre.write(relpath, text)` writes under `.troupe/`,
`theatre.config(*args)` returns `Result(code, out, err)`, `theatre.snapshot()` gives every file's
bytes, `theatre.history()` parses `history`, `assert_set(theatre, files, path, value, expected)`
writes `files`, runs `set` and checks that exactly the `expected` files changed to exactly those bytes,
`assert_refused(theatre, files, path, value, code, mention)` checks a failing `set` changed nothing,
`assert_failed(result, code, mention)` checks exit code, empty stdout and `mention` in stderr. Write
each test task's tests first and see them fail. Once the implementation passes, break the behaviour
deliberately once to confirm the test catches it.

**Organization**: Grouped by user story (spec.md): US1 new key as an override (P1), US2 read overrides
(P1), US3 change existing values where they live (P2), US4 lists stay in their file (P2). Reading
(the loader's merge) is foundational: every story's fixtures contain mapping-form includes, and
US1's writes are verified by reloading them. US2 therefore comes first among the stories; it proves
the readers on top of the foundation.

**CR-B**: `specs/006-set-in-include/tasks.md` builds on this list (the `in_include` flag reaches
`place_new_key`, built in T013–T014). Implement CR-A first.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 / US4

## Path Conventions

Single project: `src/troupe/`, `tests/` at the repository root (plan.md → Project Structure).

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Run the gates on the unchanged tree and record the output: `uv sync`, `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`; if anything fails, stop and report it before step 5 work begins
- [X] T002 In `tests/conftest.py` let `set_ok(theatre, path, value, *options)` and `assert_set(..., options: tuple[str, ...] = ())` / `assert_refused(..., options: tuple[str, ...] = ())` pass extra `set` arguments through (needed by CR-B's `--in-include`; default keeps every existing call unchanged). Run the suite: still green

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The located tree remembers include sites and overrides; the loader recognises mapping
form, validates it and builds the merged tree. Blocks every story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for the foundation

- [X] T003 [P] Create `tests/unit/test_merge.py` (tests first; they fail until T006). Build trees with the real loader on small theatres in `tmp_path` (`load(theatre)`), and assert on `to_value(root)` and on each entry's `file.path`:
  - `test_override_scalar_replaces_and_keeps_the_included_position`: included `a: 1\nb: 2\n`, override `a: 9` → keys `["a", "b"]`, `a == 9` from the main file, `b == 2` from the included file (FR-401, D-46);
  - `test_override_only_keys_come_after_included_keys_in_written_order`: override `z: 1, y: 2` → order `a, b, z, y` (D-46);
  - `test_mappings_merge_recursively`: included `limits: {retries: 2, timeout: 10}`, override `limits: {timeout: 30}` → `{retries: 2, timeout: 30}`; `retries` from the included file, `timeout` from the main file (FR-401);
  - `test_override_list_replaces_included_list`: included `tools: [git, shell]`, override `tools: [lint]` → `[lint]` (FR-401);
  - `test_override_mapping_replaces_included_scalar` and `test_override_scalar_replaces_included_mapping` (FR-401 "anywhere else, the override's value replaces");
  - `test_ref_only_mapping_equals_scalar_form`: `{$ref: file:c.yaml}` and `file:c.yaml` give equal `to_value` for a YAML and for a text target (FR-402);
  - `test_ref_is_not_an_entry`: no entry key `$ref` anywhere in the merged tree (FR-405);
  - `test_merged_nodes_remember_site_and_overrides`: the root at `agents.coder` has `included_by` = the `$ref` value scalar, `include_site` = the raw mapping (whose entries include `$ref`), `overrides is include_site`; a nested merged mapping's `overrides` is the override's nested mapping (research O-2)

### Implementation for the foundation

- [X] T004 In `src/troupe/config/tree.py` add `include_site: "LocatedMapping | None" = None` to `LocatedScalar`, `LocatedMapping`, `LocatedSequence` and `TextInclude`, and `overrides: "LocatedMapping | None" = None` to `LocatedMapping` (comment: "the override mapping merged into this one; None = not merged — spec FR-401, research O-2"); add `def written_as(node: Located) -> Located | None` returning `node.include_site`, else `node.included_by`, else `None` (docstring: "the node that stands for the whole value in the including file")
- [X] T005 In `src/troupe/config/edit/planner.py` (`content_end`, `_last_line`, `_style_of`) and `src/troupe/config/leaves.py` (`written_value`) use `written_as(node)` wherever they used `node.included_by` as "the node written in the including file" (for `written_value`, a mapping-form root returns `written_value(include_site)`, i.e. `{"$ref": …, overrides…}`). Run the suite: still green (no mapping-form fixtures exist yet)
- [X] T006 In `src/troupe/config/loader.py` add `REF_KEY = "$ref"` beside `INCLUDE_PREFIX` and implement mapping form in `_Loader.build` (docstring cites FR-400 – FR-407, D-42, D-43, research O-1, O-3):
  1. build the mapping's entries as now, except that a `$ref` entry's value is kept as the plain `LocatedScalar` (not followed);
  2. if there is no `$ref` key, or its value is not an include string (`include_target(value) is None`), return the ordinary mapping (D-42);
  3. otherwise resolve the target with the existing `include()` (same cycle / missing-target `LoadError`s, FR-407);
  4. text target (`TextInclude`): any other key → `LoadError(f"{source.path}: {REF_KEY} {value!r} names a non-YAML file; it cannot have overrides")` (FR-403); else set `include_site` = raw mapping and return it;
  5. YAML target with other keys and non-mapping content (list, scalar, empty file) → `LoadError(f"{source.path}: {REF_KEY} {value!r} does not hold a mapping; overrides need one")` (D-43);
  6. otherwise return `merge(content, raw)` with `included_by` = the `$ref` scalar, `include_site` = raw, `overrides` = raw (also when there are no override keys, so a new key under it is written into `raw`, research O-3 step 2).
  `merge(base, over)` per data-model "Merge": copy `base` (same `file`, `node`, `in_flow`), entries in base order with overridden keys replaced by the override's `(key, value)` (both mappings → `(override key, merge(base value, override value))` with `overrides` = override value), then override-only entries in written order. Override values are built with the including file's `chain`. Run T003 to green

**Checkpoint**: mapping-form includes load; existing suite green.

---

## Phase 3: User Story 2 - Read configurations that use overrides (Priority: P1)

**Goal**: `get`, `show`, `show --sources`, history, reconcile and `watch` see the merged configuration.

**Independent Test**: Hand-written mapping-form fixtures; compare `get`/`show`/`--sources`/`history`
output and exit codes.

- [X] T007 [P] [US2] Create `tests/e2e/test_overrides_read.py` with spec US2 scenarios 1–4 and 6 verbatim (fixture `coder.yaml` = `model: opus\ntools: [git, shell]\nlimits: {retries: 2, timeout: 10}\n`): `get` of an overridden scalar, list replaced (`tools.1` → exit 5), recursive merge printed by `show agents.coder.limits` as exactly `retries: 2\ntimeout: 30\n`, `show agents.coder --sources` with each scalar line's exact `# from …` (overridden → `.troupe/troupe.yml`, others → `.troupe/agents/coder.yaml`) and no `$ref` line, `{$ref: file:prompts/system.md}` prints the text, `history` on a never-imported theatre lists one `import` event per merged leaf in D-46 order and none for `$ref`; plus `test_ref_segment_is_a_missing_path` (`get agents.coder.$ref` → exit 5, FR-405), `test_override_value_that_is_an_include_is_followed` (FR-404), `test_nested_mapping_form_in_an_override` (FR-404)
- [X] T008 [P] [US2] Create `tests/e2e/test_overrides_errors.py`: US2 scenario 5 (`{$ref: file:prompts/system.md, x: 1}` → every subcommand `get`/`show`/`set`/`history` exits 4, stderr names `troupe.yml`, no file changes, FR-403); `test_overrides_on_a_list_include_exit_4` and `…_on_an_empty_include_exit_4` (D-43); `test_ref_to_missing_file_exit_4` and `test_ref_cycle_exit_4` naming the file (FR-407); `test_ref_that_is_not_an_include_is_an_ordinary_mapping` (`a: {$ref: abc}` → `get a.$ref` prints `abc`, D-42)
- [X] T009 [P] [US2] Create `tests/e2e/test_overrides_history.py`: a hand edit adding an override (`coder: file:…` → mapping form with `model: x`) is reconciled by the next `get` as one `set` event for `agents.coder.model` (FR-440); removing the override records the included value back; `watch` records an edit to a file reached only through `$ref` within 2 seconds (FR-441, use `start_watch` / `wait_for_history`)
- [X] T010 [US2] Run T007–T009; fix any reader that does not yet see the merged tree (expected: none beyond Phase 2, research O-1). If `show --sources` mislabels an overridden value, the fix belongs in the merge (keys/values must come from the override), not in `view.py`

**Checkpoint**: US2 fully functional — overrides written by hand read correctly everywhere.

---

## Phase 4: User Story 1 - Add a setting under an included section without touching the shared file (Priority: P1) 🎯 MVP

**Goal**: A new key whose deepest existing ancestor comes from an included file is written as an
override in the including file; shared files keep their bytes.

**Independent Test**: `assert_set` fixtures where only the including file is expected to change.

### Tests for User Story 1

- [ ] T011 [P] [US1] Create `tests/e2e/test_overrides_new_key.py` (tests first):
  - `test_contract_conversion_example` — `troupe.yml` `coder: file:agents/coder.yaml  # c\n`, `set coder.temperature 0.3` → exactly `coder:  # c\n  $ref: file:agents/coder.yaml\n  temperature: 0.3\n`, `coder.yaml` unchanged (SC-402, FR-422);
  - spec US1 scenario 1 (nested under `agents:` at indentation 2 → `$ref` at column 4), scenario 2 (existing mapping form: key added after the last override), scenario 3 (missing intermediate `limits.timeout` created in the override; `get …limits.retries` still `2`), scenario 4 (flow: `agents: {coder: file:agents/coder.yaml}` → `{coder: {$ref: file:agents/coder.yaml, temperature: 0.3}}`, FR-423), scenario 5 (one `set` event with `via` `cli`, none for `$ref`, FR-440);
  - `test_include_without_comment` (`coder: file:x.yaml` → `coder:` with no trailing space);
  - `test_quoted_include_string_keeps_its_quotes` (D-45);
  - `test_file_indentation_4` (`$ref` and the override at the file's step, FR-422);
  - `test_crlf_including_file_gets_crlf_lines` (step 1 D-6);
  - `test_existing_override_mapping_is_reused` (override `limits: {timeout: 30}`; `set …limits.backoff 2` adds to that mapping, FR-421);
  - `test_new_key_under_a_merged_mapping_goes_into_the_override` (spec edge case / D-48 with the main file);
  - `test_new_key_after_a_mapping_form_include_goes_below_the_whole_mapping` (sibling `agents.reviewer` after mapping-form `coder`, research O-2 `written_as`);
  - `test_nested_includes_write_in_the_nearest_including_file` (`troupe.yml` → `coder.yaml` → `model.yaml`; new key under `agents.coder.model` → override in `coder.yaml`; `troupe.yml` and `model.yaml` unchanged, D-40);
  - `test_ancestor_written_in_an_included_file_goes_one_level_out` (`coder.yaml` has `model: {$ref: file:model.yaml, a: {b: 1}}`; new key `agents.coder.model.a.d` → override in `troupe.yml`, D-48);
  - `test_list_item_include_converted_in_place` (`agents:\n  - file:a.yaml  # c\n` → `  - $ref: file:a.yaml  # c\n    temperature: 0.3\n`, D-41, research O-5);
  - `test_override_position_that_is_an_include_is_refused` (override `limits: file:l.yaml`, new key under `limits` → exit 3, no file changed, D-47);
  - `test_file_included_twice_gets_the_override_only_at_its_site` (`a: file:common.yaml\nb: file:common.yaml`; new key under `a` → override at `a` only; `get b.<key>` exits 5; research O-6);
  - `test_new_key_in_main_file_unchanged_behaviour` (ancestor in the main file → step 1 placement, FR-420)
- [ ] T012 [US1] Update `tests/e2e/test_set_new_key.py::test_new_key_in_an_included_file` to expect the override in `troupe.yml` (`agents:\n  coder:\n    $ref: file:agents/coder.yaml\n    retries: 3\n`) and `agents/coder.yaml` unchanged; rename it `test_new_key_under_an_include_becomes_an_override` (it encodes the replaced step 1 FR-022; Principle VI)

### Implementation for User Story 1

- [ ] T013 [US1] In `src/troupe/config/edit/planner.py` make `plan_set`'s walk track `site_of: dict[Path, tuple[Located, ConfigPath]]`: before stepping into a list item clear it; after stepping into a child with `written_as(child) is not None`, set `site_of[<target file of child>] = (child, here)` (target file: `child.target.path` for a `TextInclude`, else `child.file.path`). When a key is missing, call `override.place_new_key(loaded, node, prefix, path.segments[depth:], value, path, site_of)` instead of `_new_key` (comment: "spec FR-420 – FR-424; research O-4")
- [ ] T014 [US1] Create `src/troupe/config/edit/override.py` (module docstring: "Where a new key goes when includes are involved, and how a scalar-form include becomes mapping form — spec FR-420 – FR-427, D-40, D-41, D-47, D-48; research O-4, O-5. The one place these decisions live.") with `place_new_key(...) -> EditPlan` per data-model "New-key placement":
  - `own(X)`: follow `overrides` from X while the mapping is merged; the innermost plain override mapping's `file`, else `X.file` (D-48);
  - in place (`own` is the main file `loaded.root.file`, or `own.path not in site_of`): `planner._new_key` on X if not merged, else on the innermost plain override mapping;
  - otherwise site `(root, root_path) = site_of[own]`, `Q = path.segments[len(root_path.segments):]`; mapping form (`root.include_site` set): walk Q's segments (all but the new ones) through `include_site`'s entries while the child exists and is a plain `LocatedMapping` with `file` equal to the site's file, `included_by is None` and `overrides is None`; an existing child that is anything else → `WriteRefused(f"{path}: the override for it in {file} is not a plain mapping; write it by hand")` (D-47); then `planner._new_key` on the deepest one with the remaining segments; scalar form → T015;
  - override plans set `anchor=root`, `anchor_path=root_path`, `rest=Q`, and `by_site=True` (add `by_site: bool = False` to `EditPlan`)
- [ ] T015 [US1] In `src/troupe/config/edit/override.py` implement the conversion of a scalar-form include S (research O-5), using `planner._context` for the including file (its `step`, `eol`, `spans`):
  - block mapping value: splice `[after ':' , S.end)` → `""` (removes the space and the string; following whitespace and comment stay, FR-422); insert after the key's line `" " * (key column + step) + "$ref: " + S's original bytes` and `render.render_block(nested Q→value, key column + step, step)`;
  - block list item: replace S's bytes with `"$ref: " + S's bytes`; insert `render.render_block(…, dash column + 2, step)` after that line (D-41);
  - flow: replace S's bytes with `"{$ref: " + S's bytes + ", " + key + ": " + render.render_flow(…) + "}"` (FR-423);
  - one `EditPlan` for the including file (FR-426)
- [ ] T016 [US1] In `src/troupe/config/edit/apply.py` `_aliases(root, anchor, by_site)`: when `by_site`, compare `_identity(written_as(node) or node)` with `_identity(written_as(anchor))`; otherwise keep content identity (research O-6). Pass `plan.by_site` from `_verify`
- [ ] T017 [US1] Run T011–T012 to green; then run the whole suite. Break the conversion deliberately (e.g. keep the space before the comment) once to confirm `test_contract_conversion_example` fails

**Checkpoint**: MVP — CR-A's core promise holds.

---

## Phase 5: User Story 3 - Change an existing setting where it lives (Priority: P2)

**Goal**: Overridden values change in the override; others in the file they come from; ambiguous
whole-mapping replacements refuse.

- [ ] T018 [P] [US3] Create `tests/e2e/test_overrides_existing.py`: spec US3 scenarios 1–3 (override changed in `troupe.yml` only; non-overridden `effort` changed in `coder.yaml` only; no-op writes nothing and records nothing); `test_replacing_a_merged_mapping_is_refused` (`set agents.coder.limits '{a: 1}'` when `retries` comes from `coder.yaml` → exit 3, D-44); `test_replacing_an_override_only_mapping_writes_the_override` (all keys overridden → replaced in `troupe.yml`, research O-7); `test_replacing_a_mapping_form_include_is_refused` (`set agents.coder '{…}'` → exit 3, FR-432); `test_overridden_text_include_override_writes_its_target` (override `prompt: file:p.md` → `set agents.coder.prompt x` writes `p.md`)
- [ ] T019 [US3] In `src/troupe/config/edit/planner.py` `_replace`: if the target is a merged `LocatedMapping` (`overrides is not None`, not an include root) and any entry, recursively, has a `file` other than the override's file → `WriteRefused(f"{path}: its keys come from {base file} and from overrides in {override file}; an override cannot remove included keys")` (D-44); if every entry is the override's, replace the override mapping instead (research O-7). Run T018 to green

---

## Phase 6: User Story 4 - Lists stay in the file that holds them (Priority: P2)

- [ ] T020 [P] [US4] Create `tests/e2e/test_overrides_lists.py`: spec US4 scenarios 1–3 (append in `coder.yaml`; key inside a list item of `coder.yaml` written there; append to an override list in `troupe.yml`); `test_key_inside_an_item_of_an_override_list` (written in `troupe.yml`); each asserts every other file's bytes unchanged (FR-424)
- [ ] T021 [US4] Run T020; any failure is a `site_of` clearing bug in T013 — fix it there

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T022 [P] README: an "Overrides" paragraph under includes (mapping form, merge rules, where `set` writes a new key, that existing values change where they live, the exit-4/exit-3 cases) with the contract's conversion example; link `specs/005-include-overrides/`
- [ ] T023 [P] `specs/001-config-load-show-set/spec.md`: mark FR-022 "*(Replaced by step 5: see `specs/005-include-overrides/spec.md`, FR-420 – FR-427.)*" and FR-020 "*(Refined by step 5, FR-430 – FR-432.)*", as FR-015 was marked by step 3
- [ ] T024 Run the gates and show the output: `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`; walk through `quickstart.md`

---

## Dependencies & Execution Order

- Setup (T001–T002) → Foundational (T003–T006) → US2 (T007–T010) → US1 (T011–T017) → US3 (T018–T019) and US4 (T020–T021) in either order → Polish (T022–T024).
- US1 depends on the foundation only for reading; it is ordered after US2 so its reload verification runs on readers already proven.
- Within a story: tests first, see them fail, implement, see them pass.

## Parallel Opportunities

- T003 alongside T004 (different files); T007, T008, T009 together; T018 and T020 together; T022 and T023 together.

## Implementation Strategy

MVP = Phases 1–4 (reading plus new keys as overrides). Commit after each checkpoint with a message
that says why (Principle VI). CR-B (`specs/006-set-in-include/tasks.md`) follows.
