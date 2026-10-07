# Research: troupe configuration — remote includes and a schema (Step 7)

Each entry gives the decision, why it was made, and what else was considered. The spec records the
behaviour choices the contract leaves open (D-60 … D-70). This file records the technical choices for
step 7 (U-1 … U-12). Research from earlier steps (R-*, B-*, S-*, G-*, L-*, O-*) stays in force. It
also covers the step 6 alias design in `.specify/bugs/yaml-alias-set/`.

Facts checked against the installed libraries before deciding:

- `ruamel.yaml` round-trip compose keeps a scalar's tag as the string `'!literal'` (`node.tag`). The
  node's `start_mark` is at the tag (or at the anchor when `&a !literal x`), so the span the planner
  replaces today would include the tag.
- `jsonschema` 4.26 (with `referencing`) resolves under `uv` and provides `Draft202012Validator`.
  `check_schema` raises `SchemaError` for an invalid schema. `format` is not asserted unless a
  `format_checker` is passed. Errors carry `absolute_path`.
- `openssl` is available on the development machines (macOS and Linux both ship it), so tests can
  make a self-signed certificate for an HTTPS fixture server.

## U-1 One place decides what an include string is

- **Decision**: A new module `src/troupe/config/includes.py` holds the include vocabulary:
  `FILE_PREFIX = "file:"`, `REMOTE_PREFIXES = ("https://", "http://")`, `LITERAL_TAG = "!literal"`,
  and `include_ref(value) -> FileRef | UrlRef | None`. A `FileRef` holds the path after `file:`. A
  `UrlRef` holds the URL exactly as written. `include_ref` decides only by prefix. Whether a string
  at a given place *is* an include (it is not if it is a literal) is decided by
  `loader._Loader.is_include(scalar, schema)`, which combines `include_ref`, the tag and the
  subschema (U-5). `loader.INCLUDE_PREFIX`/`include_target` are replaced by these names. `REF_KEY`
  moves to `includes.py`.
- **Rationale**: Principle IV. The prefix test is used by the loader (reading), by the planner and
  `set` (FR-640, "would be read as an include") and by messages. Before this step it lived in the
  loader, which the planner imports. Keeping the rule in one small module avoids an import cycle.
- **Alternatives**: Extend `include_target` in the loader. That would mean the planner imports the
  loader for a string rule, and the literal rule would end up spread between the two.

## U-2 A source is a local file or a fetched document; only local files can be written

- **Decision**: `SourceFile.path` becomes `Path | str`, a URL string for a fetched document. A helper
  `files.local_path(source) -> Path` returns the path or raises the remote refusal (U-7). Every
  write site (`apply.apply_set`, `alias` expansion, `atomic_write`/`check_writable` callers) must use
  `local_path`. mypy `--strict` rejects passing `Path | str` where `Path` is needed, so a missed write
  site is a type error, not a silent bug. `Loaded.files` stays `dict[Path, SourceFile]` (local files
  only, so `watch` snapshots are unchanged). A new `Loaded.remote: dict[str, SourceFile]` holds the
  fetched documents. `Loaded.composed` is keyed by `Path | str`.
- **Rationale**: Messages already print `{file.path}`, so they name the URL for remote content with
  no change. Readers (`leaves`, `view`, reconcile) need no change. The type system enforces FR-610 at
  every write site (Principle I).
- **Alternatives**:
  - A separate `RemoteSource` class: every `isinstance` on sources would need a second branch, for
    the same effect.
  - A synthetic `Path` for URLs: `Path("https://a/b")` collapses `//`, and it would look writable.
  - Refusing early in `plan_set`: a refusal is needed on five different planning routes (existing
    value, append, list-item key, text include, alias, `--in-include`). The write site is the one
    place they all reach.

## U-3 Fetching: standard library, one fetch per URL per command

- **Decision**: `src/troupe/config/fetch.py` provides `fetch(url) -> str`, using `urllib.request`
  (no new dependency). It follows redirects (urllib's default). Success is a final status of
  200–299. It reads the body in chunks with a total deadline of `FETCH_TIMEOUT = 10.0` seconds
  (socket timeout set to the remaining time) and decodes UTF-8 strictly. Any failure (`URLError`,
  `HTTPError`, `TimeoutError`, `OSError`, `UnicodeDecodeError`, deadline passed) raises `LoadError`
  naming the URL and the file or URL holding the include. There are no retries and no cache between
  commands (D-63). Proxy settings come from the environment, as urllib does by default.
  The `_Loader` keeps `fetched: dict[str, SourceFile]` so a URL included twice is fetched once.
  `load(theatre, overrides, fetched=…)` and `reload` accept the previous load's `remote` documents,
  so `apply._reload` and `alias` expansion re-check against the same content (D-62). Only URLs not
  yet fetched (e.g. a new include written with `--include`) are fetched during the re-check.
- **Rationale**: urllib covers HTTP and HTTPS with system certificates, redirects and proxies, and
  it keeps the dependency list short. A total deadline is what "no complete response within 10
  seconds" means. A per-socket timeout alone would allow a slow trickle to last indefinitely.
- **Alternatives**: `httpx`/`requests` add a dependency for no needed feature. Re-fetching during
  the re-check could make a `set` fail because the server changed between two reads of one command.

## U-4 YAML or text, and where remote content can point

- **Decision**: `files.is_yaml_url(url)` is `urlsplit(url).path.endswith(YAML_SUFFIXES)`, reusing
  step 1's `YAML_SUFFIXES` and its case-sensitive test. A remote document is composed exactly like a
  local one (aliases included). In `_Loader.include`, a `FileRef` reached from a remote source raises
  `LoadError` (D-61). A `UrlRef` is followed from local or remote sources alike. The include chain
  becomes `tuple[Path | str, ...]`, with URLs compared as written, so a cycle through URLs is
  reported as step 1 FR-012 reports it.
- **Rationale**: Same rule as `file:` targets, held in one constant. Refusing `file:` inside remote
  content happens where the include is resolved, which is the only place it can be detected.

## U-5 The schema travels with the build; literals are decided while loading

- **Decision**: `src/troupe/config/schema.py` provides:
  - `SCHEMA_NAME = "troupe.schema.json"` (under `TROUPE_DIR`).
  - `load_schema(theatre) -> Schema | None` reads the file (missing → `None`), parses JSON,
    rejects a `$schema` other than `https://json-schema.org/draft/2020-12/schema`, and runs
    `Draft202012Validator.check_schema`. It also rejects any `$ref`/`$dynamicRef` whose value does
    not start with `#` (FR-630). Every failure is a `LoadError` naming the schema file.
  - `Schema.child(sub, segment) -> dict | None`, the lookup of FR-621. For a key segment: `properties[k]`
    if present, else `additionalProperties` if it is an object. For an index segment: `items` if it
    is an object. Anything that is not a JSON object gives `None`.
  - `is_uri(sub) -> bool`, true when `sub` is an object with `"format": "uri"`.
  - `Schema.validate(value)` raises `LoadError("<schema file>: <dotted path>: <message>")` using
    `best_match` over `iter_errors`, with no format checker (D-64).
  `_Loader.build` gains a `sub: dict | None` argument, the subschema at this node's configuration
  path. Mapping entries pass `child(sub, key)` and list items `child(sub, "0")`. Included content and
  mapping-form overrides pass the subschema of the position they occupy. A string is an include only
  if `include_ref(value)` is set, the node's tag is not `!literal`, and `not is_uri(sub)`.
- **Rationale**: The schema path of a value is its configuration path, and the builder already walks
  the configuration top-down, so passing the subschema down is enough. No second pass and no path
  strings are needed. Each rule lives in one function (Principle IV).
- **Alternatives**: Load first, then re-resolve literals. Includes change the tree's shape, so the
  first pass would already have fetched URLs that must not be fetched (SC-603).

## U-6 Validation runs inside `load`

- **Decision**: `load()` validates `to_value(root)` against the schema after building. That value
  has merged overrides, aliases resolved, text includes and literals as strings, and no `$ref`. A
  failure raises `LoadError`, which gives exit 4 (FR-631). `apply._reload` already turns a reload's
  `LoadError` into `WriteRefused` "would not load back (…)" with PATH in the message, which gives
  FR-633's exit 3, naming PATH and the schema file, with nothing written and no event recorded.
  `watch` treats it as any load failure (step 2 research S-5). `Loaded.schema` keeps the parsed
  schema so `set` can consult it (U-8). `watch.snapshot_of` adds the schema path (present or not),
  so editing, creating or deleting it triggers a reconcile.
- **Rationale**: Every command already funnels through `load`. One check placed there covers `get`,
  `show`, `set`, `history`, the import and `watch`. No new refusal path is needed for `set`.
- **Alternatives**: Validate per command. That means five call sites, and a forgotten one would
  let invalid configuration through.

## U-7 The remote refusal names the local include line

- **Decision**: `src/troupe/config/remote.py` has `remote_site(loaded, path) -> LocatedScalar` and
  `refuse_remote(loaded, path, source) -> WriteRefused`. `remote_site` walks PATH's segments from
  the root, as far as they exist. At each node it records `written_as`'s include scalar when that
  scalar's file is local and the node's content is remote. The last one recorded is the outermost
  remote include written in a local file, on the route PATH takes (FR-611). The message is
  `"{path}: comes from the remote include {as_written} (line {n} of {label}); remote content is
  read-only — change that include line instead; no file was changed"`. Here `as_written` is the
  scalar's source text without its quotes (D-70), `n = node.start_mark.line + 1`, and `label` is the
  theatre-relative path used by `--sources`. `files.local_path` raises a bare `RemoteSource`
  exception (a `WriteRefused` subclass). `apply_set` and `alias` catch it and re-raise with
  `refuse_remote`'s message, so PATH and the loaded tree are available.
- **Rationale**: The include line depends on the route taken (the same URL may be included twice).
  PATH determines the route, so walking PATH is the exact answer. A `RemoteSource` subclass keeps
  exit 3 and lets the low-level guard stay ignorant of the tree.
- **Alternatives**: Remember the first include site per URL in the loader. That gives the wrong line
  when a URL is included from two places.

## U-8 `set` of include-like strings: mark before planning, render the tag in one place

- **Decision**: `NewScalar` gains `tag: str | None = None`. A new function
  `literals.mark(value, path, schema, include: bool) -> NewNode` walks VALUE with the subschema at
  each string's path (FR-643). It tags a string with `LITERAL_TAG` when `include_ref(string)` is
  set, it is not under `format: uri`, and `include` is false. With `include` true, a string under
  `format: uri` raises `WriteRefused` (D-68). `commands.set_value` calls it after `parse_value`.
  `render.render_inline` and `render_literal`'s header prefix `tag + " "` whenever `tag` is set. They
  are the only places a scalar's text is produced, so every route (replace, new key, override,
  append, flow, block) gets the tag. `plain_value` ignores the tag, so `expected` values and events
  are plain strings (FR-646).
- **Existing tag** (FR-644): `scalars.content_start` also skips a `!literal` tag (only that tag, so
  other explicit tags keep step 1 behaviour). A replacement therefore lands after the tag and keeps
  it. `planner._replace_scalar` drops a `NewScalar`'s tag when the target already carries one. With
  `--include` it widens the replaced span back to the tag's start, removing the tag and its space.
  `scalars.resolve_node` returns the text for a `!literal` node before any other typing, which gives
  `!literal 5` as `"5"` (D-66). The loader raises `LoadError` for `!literal` on a collection.
- **Rationale**: The decision (FR-640 – FR-643) is made once, before planning. The spelling is
  produced once, in the renderer. Placement code is unchanged.
- **Alternatives**: Decide in each planner route. That is six routes, and a missed one would write
  an untagged URL that then gets fetched.

## U-9 CLI

- **Decision**: `set` gains `--include` (`store_true`) beside `--in-include` and `--expand-alias`,
  passed through `commands.set_value(..., include=…)`. argparse already rejects it on other
  subcommands with exit 2 and on `--include=x` (FR-645).
- **Rationale**: Same shape as the two earlier `set` flags (step 5 D-52).

## U-10 Views and lineage

- **Decision**: `view.source_label` returns the URL itself for a remote source (FR-604). `leaves`,
  `to_value`, `diff_events` and reconcile are unchanged: remote leaves are ordinary leaves (FR-605,
  D-65). `written_value` is unchanged: a remote include's `included_by` is its URL string, so the
  `--include` verification ("a `file:` string read back as the include it now names") also covers
  URLs.

## U-11 Tests

- **Decision**: A pytest fixture `web` in `tests/conftest.py` starts a `ThreadingHTTPServer` on
  `127.0.0.1:0` serving a per-test directory. It records each request path, so SC-603 can assert
  zero requests. Special paths answer with a status (`/status/404`), stall (`/stall`, for the 10 s
  limit, one slow test), redirect, or send non-UTF-8 bytes. A `web_tls` variant wraps the socket
  with a certificate made by `openssl req -x509` at session start, and passes `SSL_CERT_FILE` to the
  child `troupe`, so `https://` is exercised for real. `base_env` drops `http_proxy`, `https_proxy`,
  `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` and `NO_PROXY`, so a developer's proxy cannot decide a
  test. Every spec acceptance scenario gets an e2e test. Byte comparison of every theatre file uses
  the existing `assert_set`/`assert_refused`. Unit tests cover `Schema.child`, `is_uri`, `mark` and
  `include_ref`.
- **Rationale**: Principle II asks for real shapes: real HTTP responses and real TLS, not a stubbed
  fetch.
- **Alternatives**: Monkeypatching `fetch`. It can't reach the child process, and it would not prove
  the HTTP behaviour.

## U-12 Dependency and documentation

- **Decision**: Add `jsonschema>=4.23` to `pyproject.toml` dependencies (`uv add jsonschema`). It is
  the reference 2020-12 implementation, and writing a validator by hand would be a large invented
  surface. The README gets a "Remote includes and schema" paragraph that covers URL includes, the
  read-only rule, the schema file, `!literal` and `set --include`. It also warns that existing plain
  URL strings are now includes. Step 1's spec FR-010 gets a note: "Extended by step 7".
- **Rationale**: Principles IV and VI.

## U-13 Decisions made while implementing

Recorded per Constitution VI; each was found during `/speckit-implement` or convergence.

- **Alias expansion keeps `!literal` tags.** `set --expand-alias` writes a copy of the anchored
  value (step 6). The copy is built from the located tree (`edit/alias._copy`), not from plain
  values, so a tagged string is written tagged again and an include string untagged. Without this
  a literal URL in the copy would become an include, and the re-check would refuse the `set`.
- **`types-jsonschema` dev dependency.** `jsonschema` ships no type information. The stub
  package keeps `mypy --strict` checking `schema.py` instead of treating the library as `Any`.
- **Removing a tag with `--include` (FR-644).** The replaced span starts at the tag, for plain,
  quoted, flow, block and empty scalars alike. A literal block keeps its indicator (step 1
  FR-030), so `a: !literal |` becomes `a: |-` with the include string as its content. The same
  work found that an empty tagged value (`a: !literal`) could not be set without `--include`.
  `planner._after_properties` now skips a `!literal` tag as it skips an anchor, so the tag is kept
  and the value written after it.
- **`FetchError` and `watch`.** `fetch.FetchError` (a `LoadError`, so still exit 4) marks every
  failure to fetch or read a remote include. That covers fetch failures and invalid YAML in
  fetched content. `watch` reports it like a broken file but does not retry on every poll. It
  re-reads the bytes of the files from its last successful load and fetches again only after one
  of them (or the schema file) changes (D-65). Broken local files keep step 2's every-poll retry.
- **Nested fetch failures name the local include.** The loader remembers, for each fetched URL,
  the include string in a local file it is reached through. Errors fetching a URL included from
  remote content add `(included through <string> at line N of <file>)` (FR-602). `as_written`
  lives in `tree.py` so the loader and `remote.py` share it.
