---

description: "Task list for troupe configuration — remote includes and a schema (Step 7)"
---

# Tasks: troupe configuration — remote includes and a schema (Step 7)

**Input**: Design documents from `specs/007-remote-includes-schema/`

**Prerequisites**: plan.md, spec.md, research.md (U-1 … U-12), data-model.md, contracts/cli.md,
quickstart.md. Steps 1–6 implemented, including the step 6 alias fix in `.specify/bugs/yaml-alias-set/`.

**Tests**: MANDATORY (Constitution Principle II). End-to-end tests run the real CLI through the
`theatre` fixture in `tests/conftest.py`:

- `theatre.write(rel, text)` writes under `.troupe/`.
- `theatre.config(...)` runs `troupe config …`.
- `assert_set(theatre, files, path, value, expected, options=(...))` checks that exactly the
  `expected` files changed, to exactly those bytes.
- `assert_refused(theatre, files, path, value, code, mention, options=(...))` checks the exit code,
  empty stdout, that `mention` is in stderr, and that no file changed.
- `assert_failed(result, code, mention)` checks a failed result.

The new `web` fixture (T005) serves files over real HTTP; `web.url("agents.yaml")` gives the URL and
`web.requests` lists the paths requested. Write each test task's tests first and see them fail.
After the implementation passes, break the behaviour deliberately once to confirm the tests catch it.

**Organization**:

- US1: include shared team configuration from a URL (P1)
- US2: remote values are read-only (P1)
- US3: URL settings stay URLs (P1)
- US4: schema validation (P2)
- US5: `set` writes include-like strings as literals (P2)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 … US5

## Path Conventions

Single project: `src/troupe/`, `tests/` at the repository root.

---

## Phase 1: Setup

- [ ] T001 Confirm steps 1–6 are complete and the gates are green: `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`. Record the output.
- [ ] T002 Run `uv add "jsonschema>=4.23"` (updates `pyproject.toml` and `uv.lock`; research U-12). Check that `uv run python -c "import jsonschema; jsonschema.Draft202012Validator"` succeeds. Commit with the reason: "JSON Schema 2020-12 validation for step 7; the reference implementation instead of a hand-written validator".

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: one vocabulary for include strings; sources that may be URLs and can never be written;
a loader that carries the subschema; a real web server for tests. No behaviour changes yet: every
existing test stays green after each task.

- [ ] T003 [P] Create `src/troupe/config/includes.py` (research U-1):
  - Constants: `FILE_PREFIX = "file:"`, `REMOTE_PREFIXES = ("https://", "http://")`, `LITERAL_TAG = "!literal"`, `REF_KEY = "$ref"` (moved from `loader.py`).
  - Frozen dataclasses `FileRef(path: str)` and `UrlRef(url: str)`.
  - `include_ref(value: object) -> FileRef | UrlRef | None`: a `str` starting `file:` gives `FileRef(value[5:])`; a `str` starting one of `REMOTE_PREFIXES` gives `UrlRef(value)` (exact, case-sensitive, no stripping); anything else gives `None`.
  - Module docstring: "the one place that says which strings name includes (spec FR-600, step 1 FR-010)".
  - Replace `loader.INCLUDE_PREFIX`/`include_target` and every import of `REF_KEY` (`loader.py`, `edit/override.py`) with these.
  - Write `tests/unit/test_includes.py` first: `test_file_prefix`, `test_https_and_http_prefixes`, `test_prefix_is_case_sensitive_and_exact` (`HTTPS://x`, ` https://x`, `ftp://x` all give `None`), `test_non_strings_are_never_includes` (`5`, `None`, `True`).
- [ ] T004 [P] In `src/troupe/config/files.py` (research U-2, U-4):
  - Change `SourceFile.path` to `Path | str`. A `str` is a URL exactly as written.
  - Add `is_yaml_url(url: str) -> bool`, which returns `urlsplit(url).path.endswith(YAML_SUFFIXES)`.
  - Add `class RemoteSource(WriteRefused)` carrying `url: str`.
  - Add `local_path(source: SourceFile) -> Path`, which returns the path or raises `RemoteSource(source.path)` for a URL. Comment: "every write goes through here; remote content is read-only, spec FR-610".
  - Fix every mypy error the change causes. Write sites (`edit/apply.py` `check_writable`/`atomic_write`, `edit/alias.py` reload key) must call `local_path`. Reads and messages keep `.path`.
  - `Loaded.composed` and `_Loader.composed` become `dict[Path | str, Any]`. `override._target_file` returns `Path | str`.
  - Add unit tests to `tests/unit/test_includes.py`: `test_is_yaml_url_ignores_query_and_fragment` (`…/a.yaml?rev=3` → True, `…/a.yaml#x` → True, `…/a.md` → False, `…/a.YAML` → False) and `test_local_path_refuses_a_url`.
- [ ] T005 [P] In `tests/conftest.py` (research U-11):
  - Add `"http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"` to `INHERITED_ENV_DROPPED`.
  - Add a `Web` class and a `web` fixture: a `ThreadingHTTPServer` on `127.0.0.1:0` in a daemon thread, serving files from `tmp_path / "web"`, shut down at teardown.
    - `web.write(rel, text | bytes)` and `web.url(rel) -> str` (`http://127.0.0.1:<port>/<rel>`).
    - `web.requests: list[str]` records request paths (with query) in order.
    - Special paths: `/status/<code>` answers that status with an empty body; `/redirect/<rel>` answers 302 to `/<rel>`; `/stall` sleeps 15 s before answering; `/slow/<rel>` sends the file one byte per second.
  - Add a session fixture `tls_cert` that runs `openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=localhost -addext subjectAltName=IP:127.0.0.1` into a temp directory. Skip with a clear reason if `openssl` is missing.
  - Add a `web_tls` fixture: a `Web` whose socket is wrapped with that certificate, with `url()` giving `https://127.0.0.1:<port>/…`, and `web_tls.env = {"SSL_CERT_FILE": <cert path>}` to pass to `theatre.run(..., env=…)`.
  - Add `tests/unit/test_web_fixture.py`: `test_web_serves_and_records` and `test_status_path` (via `urllib.request`), so the fixture itself is proven.
- [ ] T006 In `src/troupe/config/loader.py` (research U-5; depends on T003, T004):
  - Thread a subschema through `_Loader.build(..., sub: dict[str, Any] | None)`. A mapping entry passes `schema_child(sub, key)`, a list item `schema_child(sub, "0")`. Included content (`include`) and mapping-form overrides (`mapping_include`) pass the `sub` of the position they fill.
  - Add the module-level `schema_child(sub, segment)` to a new `src/troupe/config/schema.py`, implemented per data-model "String classification": `properties[key]` if an object, else `additionalProperties` if an object; for a digit segment, `items` if an object; otherwise `None`.
  - Add `is_uri(sub) -> bool` (`isinstance(sub, dict) and sub.get("format") == "uri"`).
  - Add `_Loader.is_include(scalar, sub) -> FileRef | UrlRef | None`. For now it returns `include_ref(scalar.value)` for `FileRef` only, so URLs stay plain strings until US1; the root call passes `sub=None`.
  - Add `Loaded.remote: dict[str, SourceFile]` (empty for now) and `Loaded.schema` (`None` for now). `load(theatre, overrides=None, fetched=None)` and `reload(loaded, overrides)` pass `loaded.remote` as `fetched`.
  - Add `tests/unit/test_schema_lookup.py`: `test_child_by_properties`, `test_child_falls_back_to_additional_properties`, `test_additional_properties_false_gives_none`, `test_items_for_any_index`, `test_other_keywords_are_not_followed` (`$ref`, `allOf`, `patternProperties`, `prefixItems` give `None`; D-64), `test_is_uri`.
  - Run the full suite: it must stay green.

**Checkpoint**: refactor complete, behaviour unchanged, test web server available.

---

## Phase 3: User Story 1 - Include shared team configuration from a URL (Priority: P1) 🎯 MVP

**Goal**: `https://`/`http://` strings are includes, fetched on every load; failures exit 4.

**Independent Test**: serve fixtures with `web`; `get`/`show`/`--sources`/`history` give the
expected configuration; each failure kind exits 4.

- [ ] T007 [P] [US1] Create `tests/e2e/test_remote_read.py` (tests first):
  - **Scenario 1:** `web.write("agents.yaml", "coder:\n  model: opus\n")`; `troupe.yml` `agents: <url>\n`; `get agents.coder.model` → `opus\n` (FR-600, FR-601).
  - **Scenario 2:** text include, `system.md` = `Be brief.\n` → `get prompt` prints it exactly. Also `test_text_include_keeps_crlf` (`"a\r\nb\r\n"` read back unchanged via `show prompt`).
  - **Scenario 3:** `agents.yaml?rev=3` is read as YAML; `web.requests` contains `/agents.yaml?rev=3`.
  - **Scenario 4:** `show agents --sources` → `  model: opus # from <url>` (FR-604).
  - **Scenario 6:** `coder: {$ref: <url>/coder.yaml, model: sonnet}` → `get agents.coder.model` prints `sonnet`.
  - **Scenario 7:** on a fresh theatre, `history` has an `import` event for `agents.coder.model` with `new` `opus` (FR-605).
  - `test_quoted_url_is_an_include` (`agents: "<url>"`).
  - `test_nested_remote_include` (the remote `agents.yaml` contains `coder: <url>/coder.yaml`).
  - `test_same_url_twice_is_fetched_once` (`a: <url>/x.yaml\nb: <url>/x.yaml`; after `get a.k`, `web.requests.count("/x.yaml") == 1`; D-62).
  - `test_empty_yaml_body_is_null` (`show a` prints `null`).
  - `test_empty_text_body_is_empty_string`.
  - `test_redirect_is_followed` (`/redirect/agents.yaml`; D-63).
  - `test_https_include` (uses `web_tls`, passing `env=web_tls.env`).
  - `test_remote_change_is_reconciled_as_file` (load once, change the served file, run `get`; the last history event has `via` `file`, `op` `set`, and actor `{"kind": "unknown", "id": None}`; D-65).
- [ ] T008 [P] [US1] Create `tests/e2e/test_remote_errors.py` (tests first). Each test uses `assert_failed(result, 4, <url>)`, checks that stderr also names `.troupe/troupe.yml` (or the file holding the include), and that `theatre.snapshot()` is unchanged (FR-602, FR-650):
  - `test_connection_refused` (a URL on a closed port: bind then close a socket to get one).
  - `test_status_404`, `test_status_500`.
  - `test_non_utf8_body` (`web.write("a.md", b"\xff\xfe")`).
  - `test_invalid_yaml_body` (`a.yaml` = `"a: [\n"`).
  - `test_stall_exceeds_10_seconds` (`/stall`; the command must finish in under 14 s; mark the test with a comment on its duration).
  - `test_slow_trickle_exceeds_10_seconds` (`/slow/…` serving a 20-byte file).
  - `test_file_include_inside_remote_content` (the remote YAML has `x: file:local.yaml`, and `local.yaml` exists in the theatre; exit 4 naming the URL; D-61).
  - `test_url_include_cycle` (`a.yaml` includes `b.yaml`, which includes `a.yaml`).
  - `test_https_with_untrusted_certificate` (`web_tls` without `SSL_CERT_FILE` → exit 4).
  - Run every command (`get a`, `show`, `history`, `set a 1`) against one failing fixture: each exits 4.
- [ ] T009 [US1] Create `src/troupe/config/fetch.py` (research U-3):
  - `FETCH_TIMEOUT = 10.0` with the comment "spec D-63".
  - `fetch(url: str, included_from: str) -> str`: `urllib.request.urlopen(url, timeout=remaining)`, then read in 64 KiB chunks until EOF, raising if `time.monotonic()` passes the deadline. Require `200 <= status < 300`, then decode with `.decode("utf-8")` (strict).
  - Map `HTTPError` → `LoadError(f"{included_from}: cannot fetch {url}: HTTP {code}")`. Map `URLError`/`OSError`/`TimeoutError`/deadline/`UnicodeDecodeError` → `LoadError(f"{included_from}: cannot fetch {url}: {reason}")`.
  - Add the docstring "redirects followed, 2xx only, no cache, no retries (spec D-63); proxies from the environment".
- [ ] T010 [US1] In `src/troupe/config/loader.py` (research U-3, U-4):
  - `is_include` now also returns `UrlRef` (still no literal rules; those come in US3).
  - `include()` dispatches:
    - A `FileRef` from a source whose `path` is a `str`: `LoadError(f"{url}: file: include {value!r} in remote content is not allowed")` (D-61).
    - A `FileRef` from a local source: as before.
    - A `UrlRef`: cycle check against the chain (now `tuple[Path | str, ...]`, URLs compared as written; message as step 1). Then `self.remote_source(url, included_from=str(scalar.file.path))`. That uses `self.fetched` (seeded from `load(..., fetched=…)`), else `fetch()`, and stores `SourceFile(url, text, "yaml" if is_yaml_url(url) else "text")` in `self.fetched`. Then build exactly as a local file (text → `TextInclude`; YAML → compose and build; empty → null).
  - `Loaded.remote = self.fetched`. Fetched sources are not added to `Loaded.files`, so `watch` never reads URLs (D-65).
  - `apply._reload` passes `fetched=loaded.remote` (D-62).
  - Run T007/T008 to green.
- [ ] T011 [US1] In `src/troupe/config/view.py` `source_label`: `return file.path if isinstance(file.path, str) else <existing relpath>`, with the comment "a fetched value is labelled with its URL as written (spec FR-604)". Run T007 scenario 4 to green.

**Checkpoint**: MVP: URL includes load everywhere; failures are exit 4.

---

## Phase 4: User Story 2 - Remote values are read-only (Priority: P1)

**Goal**: any `set` that would write into remote content exits 3, naming the include line; new keys
become local overrides.

**Independent Test**: each FR-610 case with `assert_refused(…, 3, <url as written>)` plus checks on
stderr's file and line; the override cases with `assert_set`.

- [ ] T012 [P] [US2] Create `tests/e2e/test_remote_readonly.py` (tests first). The fixture `troupe.yml` is `# team config\nagents:\n  coder: "<url>/coder.yaml"  # team\n` and remote `coder.yaml` is `model: opus\ntools: [git]\nsteps:\n- name: build\n`.
  - **Scenario 1:** `set agents.coder.model sonnet` → `assert_refused(..., 3, "<url>/coder.yaml")`; stderr also contains `.troupe/troupe.yml` and `line 3` (FR-610, FR-611, D-70).
  - **Scenario 2:** `set agents.coder.temperature 0.3` → `assert_set` with `troupe.yml` exactly `# team config\nagents:\n  coder:  # team\n    $ref: "<url>/coder.yaml"\n    temperature: 0.3\n` (FR-612, step 5 FR-422, D-45).
  - **Scenario 3:** with that override present, `set agents.coder.temperature 0.5` changes only the override (FR-613).
  - **Scenario 4:** `set agents.coder.tools.1 lint` (append) and `set agents.coder.steps.0.retries 3` → exit 3 with the URL.
  - **Scenario 5:** a remote text include, `set prompt "New text"` → exit 3 with the URL.
  - **Scenario 6:** `troupe.yml` `agents: file:agents.yaml` and local `agents.yaml` line 2 holds `coder: <url>/coder.yaml` → stderr names `.troupe/agents.yaml` and `line 2`.
  - **Scenario 7:** `set --in-include agents.coder.temperature 0.3` → exit 3 with the URL.
  - `test_nested_remote_new_key_refused` (`troupe.yml` → `<url>/a.yaml` → `b: <url>/b.yaml`; a new key under `x.b` → exit 3 whose stderr contains `<url>/a.yaml`, the outermost include as written in the local file; D-60, FR-611).
  - `test_replace_whole_remote_include_refused` (`set agents.coder '{a: 1}'` → exit 3, step 1 FR-024).
  - `test_alias_in_remote_content_refused` (remote `d: &x {m: 1}\ne: *x`; `set --expand-alias agents.e.m 2` → exit 3 with the URL).
  - `test_same_url_two_sites_names_the_one_on_the_path` (`a: <url>/x.yaml` on line 1 and `b: <url>/x.yaml` on line 2; `set b.k 9` names `line 2`).
  - `test_no_event_recorded_on_refusal` (history is unchanged).
- [ ] T013 [US2] Create `src/troupe/config/remote.py` (research U-7):
  - `remote_site(loaded, path) -> LocatedScalar | None` walks `path.segments` from `loaded.root` through mappings and lists as far as they exist. At each node, `w = written_as(node)`; take its include scalar (`w` if it is a `LocatedScalar`, else the `$ref` scalar of the mapping `w`). If that scalar's `file.path` is a `Path` and the node's content source is a URL (`node.target.path` for a `TextInclude`, else `node.file.path`), remember it. Return the last one remembered.
  - `as_written(scalar)` returns the scalar's source text `file.text[start:end]` with its surrounding quotes removed when `style` is `'"'` or `"'"` (D-70).
  - `refuse_remote(loaded, path, theatre) -> WriteRefused` builds `f"{path}: comes from the remote include {as_written(s)} (line {s.node.start_mark.line + 1} of {source_label(theatre, s.file)}); remote content is read-only — change that include line instead; no file was changed"`.
- [ ] T014 [US2] Wire the refusal:
  - In `src/troupe/config/edit/apply.py` `apply_set`, compute `target = local_path(plan.file)` before `_reload`, in `try/except RemoteSource: raise refuse_remote(loaded, path, theatre) from None`, and use `target` for `check_writable`/`atomic_write`.
  - In `src/troupe/config/edit/alias.py`, call `local_path(alias.file)` before expanding, mapping `RemoteSource` the same way (thread `theatre` in, or raise `RemoteSource` and catch it in `apply_set`; choose one and keep it in one place).
  - Run T012 to green. Break the guard once (skip `local_path` in `apply_set`) and confirm that mypy fails, then restore it.

**Checkpoint**: remote content can be read but never written.

---

## Phase 5: User Story 3 - URL settings stay URLs (Priority: P1)

**Goal**: `format: uri` (via `properties`/`additionalProperties`/`items`) and `!literal` make a string
a literal; nothing is fetched or read for it.

**Independent Test**: fixtures with literals; `get` prints the string; `web.requests == []`; a
`file:` literal's file is never needed.

- [ ] T015 [P] [US3] Create `tests/e2e/test_literals.py` (tests first). Each fixture uses `web.url(...)` strings so any fetch would be visible:
  - **Scenario 1:** schema `{"properties": {"api": {"properties": {"endpoint": {"type": "string", "format": "uri"}}}}}` written to `.troupe/troupe.schema.json` → `get api.endpoint` prints the URL and `web.requests == []`.
  - **Scenario 2:** `items`.
  - **Scenario 3:** `additionalProperties`.
  - **Scenario 4:** `docs: !literal <url>/guide.yaml` with no schema; `notes: !literal file:missing.md` (the file does not exist) → `get notes` prints `file:missing.md`.
  - **Scenario 5:** history `import` events have the plain strings, no tag.
  - `test_literal_in_included_file` (`format: uri` applies to a string written in an included `file:` YAML at that path).
  - `test_literal_inside_override` (mapping-form override value at a `format: uri` path).
  - `test_ref_value_is_still_an_include_under_format_uri_parent` (schema marks `agents.coder` `format: uri` but `coder` is `{$ref: <url>, …}` → fetched).
  - `test_literal_tag_on_ref_value_makes_ordinary_mapping` (`{$ref: !literal file:x.yaml}` → `get c.$ref` prints `file:x.yaml`; step 5 D-42).
  - `test_literal_on_number_is_a_string` (`!literal 5` → history `new` is `"5"`; D-66).
  - `test_literal_on_mapping_exit_4` (`a: !literal {b: 1}` → exit 4 naming `troupe.yml`; D-66).
  - `test_pattern_properties_not_followed` (`patternProperties` `format: uri` → the string is still fetched; D-64).
  - `test_show_prints_literal_untagged` (`show` output has no `!literal`; D-67).
  - `test_schema_change_is_reconciled` (add the schema after the first `get`; the next `get` records the include's leaves removed and the string set).
  - `test_watch_sees_schema_file` (with `start_watch`: writing the schema file is recorded within 2 s).
- [ ] T016 [US3] Implement literals while loading (research U-5, U-8):
  - In `src/troupe/config/scalars.py`, `resolve_node` returns `text` first when `node.tag == LITERAL_TAG` (before alias and core-schema typing). `content_start` also skips a leading `!literal` tag token and the spaces after it (only that tag; other explicit tags unchanged). Docstring note "step 7, FR-644".
  - In `loader._Loader.is_include`, return `None` when `scalar.node.tag == LITERAL_TAG` or `is_uri(sub)`.
  - In `build`, a `SequenceNode`/`MappingNode` with `tag == LITERAL_TAG` raises `LoadError(f"{source.path}: line {n}: !literal applies to a single value, not a mapping or list")`.
  - Run the existing test suite to confirm that anchors and `!!str` behave as before.
- [ ] T017 [US3] In `src/troupe/config/schema.py` add `SCHEMA_NAME = "troupe.schema.json"`, `@dataclass Schema(path: Path, document: dict[str, Any])` and `load_schema(theatre) -> Schema | None` (research U-5):
  - A missing file gives `None`.
  - The file is read with `read_source`; invalid JSON → `LoadError(f"{path}: invalid JSON: …")`; a top level that is not an object → `LoadError`.
  - `$schema` must be absent or equal to `https://json-schema.org/draft/2020-12/schema`, else `LoadError(f"{path}: $schema must be JSON Schema 2020-12")`.
  - `Draft202012Validator.check_schema` failure → `LoadError(f"{path}: not a valid JSON Schema: {message}")`.
  - Any `$ref`/`$dynamicRef` string anywhere not starting with `#` → `LoadError(f"{path}: $ref {value!r} points outside the schema")` (FR-630).
  - In `loader.load`, call `load_schema(theatre)`, pass `schema.document` as the root `sub`, and set `Loaded.schema`.
  - In `src/troupe/config/watch.py` `snapshot_of`, add `(theatre / TROUPE_DIR / SCHEMA_NAME).resolve()` like the config names.
  - Run T015 to green.

**Checkpoint**: literals work with or without a schema.

---

## Phase 6: User Story 4 - The configuration is validated against the schema (Priority: P2)

**Goal**: an invalid configuration is exit 4 on load; a `set` that would invalidate it is exit 3.

**Independent Test**: schema with `type`/`enum` constraints; invalid fixtures exit 4; invalid `set`
exits 3 with no change.

- [ ] T018 [P] [US4] Create `tests/e2e/test_schema_validation.py` (tests first). The schema is `{"properties": {"temperature": {"type": "number"}, "agents": {"additionalProperties": {"properties": {"model": {"enum": ["opus", "sonnet"]}}}}}}`.
  - **Scenario 1:** `temperature: warm` → every command (`get temperature`, `show`, `history`, `set x 1`) gives `assert_failed(r, 4, "troupe.schema.json")`, and stderr contains `temperature` (FR-631).
  - **Scenario 2:** `assert_refused(..., "temperature", "warm", 3, "troupe.schema.json")`, stderr contains `temperature`, and history is unchanged (FR-633).
  - **Scenario 3:** `set temperature 0.5` succeeds.
  - **Scenario 4:** remote content `model: haiku` under `agents.coder` → exit 4.
  - **Scenario 5:** parametrised bad schema files: `{`, `[]`, `{"type": 5}`, `{"$schema": "http://json-schema.org/draft-07/schema#"}`, `{"$ref": "https://example.com/s.json"}` → exit 4 naming `troupe.schema.json` (FR-630).
  - **Scenario 6:** no schema → `temperature: warm` loads.
  - `test_format_is_not_asserted` (`{"properties": {"u": {"format": "uri"}}}` with `u: not a uri` loads; D-64).
  - `test_internal_ref_is_followed_for_validation` (`$defs` + `"$ref": "#/$defs/num"` on `temperature` with `temperature: warm` → exit 4).
  - `test_validation_sees_merged_overrides` (the override makes an invalid value valid → loads).
  - `test_text_include_validated_as_string`.
  - `test_watch_reports_invalid_then_recovers` (with `start_watch`: an invalid hand edit is reported on stderr, a valid edit is then recorded; step 2 D-13).
- [ ] T019 [US4] In `src/troupe/config/schema.py` add `Schema.validate(self, value: Value) -> None`. It uses `Draft202012Validator(self.document)` with no `format_checker`, takes `best_match(validator.iter_errors(value))`, and raises `LoadError(f"{self.path}: {dotted or 'the top level'}: {error.message}")`, where `dotted` is `".".join(str(p) for p in error.absolute_path)`. Comment: "format is an annotation only (spec D-64)".
  - In `loader.load`, after building, call `schema.validate(to_value(root))` when a schema exists (FR-631).
  - Confirm that `apply._reload` turns the failure into exit 3 whose message contains PATH and the schema file name (FR-633); if not, add the schema file to the `WriteRefused` text there.
  - Run T018 to green.

**Checkpoint**: invalid configuration cannot load and cannot be written.

---

## Phase 7: User Story 5 - `set` writes include-like strings as literals unless asked (Priority: P2)

**Goal**: FR-640 – FR-646.

**Independent Test**: `assert_set` byte comparisons over the tagging matrix (contracts/cli.md).

- [ ] T020 [P] [US5] Create `tests/e2e/test_set_literal.py` (tests first, using `assert_set` with exact bytes):
  - **Scenario 1:** `docs: old\n` + `set docs https://example.com/guide` → `docs: !literal https://example.com/guide\n`; `get docs` prints the URL (FR-640).
  - **Scenario 2:** schema marks `api.endpoint` → `  endpoint: https://api.example.com/v2\n`, untagged (FR-641).
  - **Scenario 3:** `set --include agents <web url>/agents.yaml` (new key) → `agents: <url>\n`, and `get agents.coder.model` works (FR-642).
  - **Scenario 4:** `--include` with a 404 URL, and with `file:missing.yaml` → exit 3, no change (FR-642).
  - **Scenario 5:** `set notes file:notes.md` → `notes: !literal file:notes.md\n`.
  - **Scenario 6:** `set name coder` → no tag.
  - `test_quoted_style_is_kept_after_the_tag` (`docs: "old"` → `docs: !literal "https://x"`; step 1 FR-026).
  - `test_new_key_is_tagged` and `test_flow_mapping_entry_is_tagged` (`a: {b: 1}` → `a: {b: 1, u: !literal https://x}`).
  - `test_appended_list_item_is_tagged` (`- !literal https://x`).
  - `test_new_key_override_under_include_is_tagged` (the step 5 override route).
  - `test_collection_value_strings_are_tagged` (`set a '{u: https://x, n: 1}'` → `u: !literal https://x`; D-69).
  - `test_collection_value_respects_nested_format_uri`.
  - `test_existing_literal_tag_is_kept` (`docs: !literal https://a` + `set docs plain` → `docs: !literal plain`; D-67, FR-644).
  - `test_include_flag_removes_existing_tag` (`docs: !literal https://a` + `set --include docs <web url>/d.md` → `docs: <url>`).
  - `test_include_at_format_uri_path_refused` (exit 3 naming the path; D-68).
  - `test_include_flag_without_include_like_value_is_a_noop` (same bytes as without it; FR-645).
  - `test_multiline_include_like_string_uses_literal_block` (`"https://x\ny"` → `a: !literal |-` + content; U-8).
  - `test_events_have_no_tag` (the history `new` is the plain URL; FR-646).
  - `test_text_include_target_written_untagged` (`set prompt https://x` where `prompt: file:p.md` → `p.md` contains `https://x`, no tag).
- [ ] T021 [P] [US5] Extend `tests/e2e/test_usage.py`: `test_include_on_other_subcommands_exits_2`, parametrised over `get a --include`, `show --include`, `history --include`, `watch --include` → exit 2 naming `--include`, no file changed. Also `test_include_with_a_value_exits_2` and `test_include_any_position_with_other_flags` (`set --include a 1 --reason r --in-include` → exit 0) (FR-645).
- [ ] T022 [US5] In `src/troupe/config/scalars.py`, add `tag: str | None = None` to `NewScalar`; `plain_value` ignores it.
  - In `src/troupe/config/edit/render.py`, `render_inline` returns `f"{scalar.tag} {text}"` when `scalar.tag` is set, and the literal-block header path (`render_literal` callers in `render_value_lines`/`render_block`) prefixes `tag + " "` before `|`. These are the only places; check with `grep -n "NewScalar(" src/troupe/config/edit` that every rendering route goes through them.
  - Comment: "the tag is spelled here and only here (research U-8)".
- [ ] T023 [US5] Create `src/troupe/config/edit/literals.py` (research U-8):
  - `mark(value: NewNode, path: ConfigPath, schema: Schema | None, include: bool) -> NewNode`. It walks `value` with `schema_child` from the subschema at `path` (computed from the root through `path.segments`) and returns a copy where each `NewScalar` whose value is a `str` with `include_ref(...)` set and not `is_uri(sub)` gets `tag=LITERAL_TAG` unless `include`. With `include`, a string under `is_uri(sub)` raises `WriteRefused(f"{path}: the schema marks it format: uri, so it cannot be an include; no file was changed")` (D-68).
  - Unit tests in `tests/unit/test_includes.py`: `test_mark_tags_include_like_strings`, `test_mark_respects_format_uri`, `test_mark_nested_paths`, `test_mark_include_flag`.
- [ ] T024 [US5] Wire `--include`:
  - In `src/troupe/cli.py`, add `set_parser.add_argument("--include", action="store_true", help="write an include-like VALUE as an include, not a !literal string")` and pass `include=args.include`.
  - In `src/troupe/config/commands.py` `set_value(..., include: bool = False)`: after `open_theatre`, `value = mark(value, path, loaded.schema, include)`, then pass `include=include` to `apply_set` → `plan_set` → `planner._replace_scalar`.
  - In `src/troupe/config/edit/planner.py` `_replace_scalar`, when the target node's tag is `LITERAL_TAG`: without `include`, drop the new scalar's tag (keep the existing one, FR-644); with `include`, start the replaced span at `target.node.start_mark` past any anchor (i.e. at the tag), so the tag and its space are removed. Comment: "spec FR-644, D-67".
  - Run T020/T021 to green.

**Checkpoint**: all five stories pass.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T025 [P] README (`README.md`): in the usage block, add `[--include]` to the `set` line. Add a "Remote includes and schema" bullet covering:
  - URL includes (YAML by URL path, else text; failed fetch → exit 4), shown with a one-line example;
  - read-only remote values (exit 3 names the include line), with new keys becoming local overrides;
  - `.troupe/troupe.schema.json` (2020-12; validation exit 4 / `set` exit 3; `format: uri` literals);
  - `!literal`, and `set` tagging with `--include`;
  - a note: "existing plain `https://` strings are now includes: mark them in the schema or with `!literal`".
  Also add `specs/007-remote-includes-schema/` to the closing links.
- [ ] T026 [P] In `specs/001-config-load-show-set/spec.md` FR-010, append "*(Extended by step 7: `https://`/`http://` strings are includes too, and literals never are; see `specs/007-remote-includes-schema/spec.md`, FR-600, FR-620.)*" (Principle VI).
- [ ] T027 Run the gates and show the output: `uv run pytest`, `uv run mypy --strict src tests`, `uv run ruff check .`, `uv run ruff format --check .`. Walk through `quickstart.md` and record the results. Commit in small steps with messages that say why.

---

## Dependencies & Execution Order

- T001 → T002 → Phase 2. In Phase 2, T003, T004 and T005 run in parallel; T006 comes after T003 and T004.
- US1 (T007–T011) needs Phase 2.
- US2 (T012–T014) needs US1, since it can only refuse writes to content that loads.
- US3 (T015–T017) needs Phase 2. Its tests need US1's fetching to show that nothing is fetched, so run it after US1.
- US4 (T018–T019) needs T017 (schema loading).
- US5 (T020–T024) needs T017 (`Loaded.schema`, `schema_child`) and T016 (tag skipping in `content_start`).
- Polish comes last.

## Parallel Opportunities

- T003, T004 and T005 run in parallel.
- Each story's test task ([P]) can be written while the previous story's implementation finishes: T007/T008 alongside T006; T012 alongside T011; T015 and T018 together; T020/T021 alongside T019.
- T025 and T026 run in parallel.

## Implementation Strategy

- **MVP**: Phases 1–3 (URL includes load). Phase 4 should follow immediately, before any release,
  because without it a `set` on remote content would reach the write guard only through mypy-forced
  `local_path`, with a raw message.
- **Then**: US3 (protects existing URL settings), US4, US5.
- Commit at each checkpoint, with a message that says why (Principle VI).
