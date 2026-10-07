# Feature Specification: troupe configuration — remote includes and a schema (Step 7)

**Feature Branch**: `main` (delivery is on `main`; no feature branch)

**Created**: 2026-10-07

**Status**: Draft

**Input**: User description: "Step 7 — remote includes and a schema. Includes can now point at
`https://` URLs (shared team configuration). They are read-only from troupe's point of view: refuse
changes to their values, and tell the user which include line to change instead. The configuration is
described by a JSON Schema at `.troupe/troupe.schema.json`. Some settings are URLs that must never be
treated as includes; the schema marks those with `"format": "uri"`, and a `!literal` tag marks any
other value that must be taken literally. Contract sections added: Remote includes and schema."

The product owner's contract section **Remote includes and schema** is normative, together with the
sections already in force from steps 1–6 (see `specs/001-config-load-show-set/spec.md` through
`specs/006-set-in-include/spec.md`, and the step 6 *Aliases* section recorded in
`.specify/bugs/yaml-alias-set/assessment.md`). The requirements below restate it so each rule can be
tested on its own. Where this spec and the contract seem to differ, the contract wins and this spec is
corrected. Choices the contract leaves open are recorded under **Decisions on open points**.

Contract text (verbatim):

> - A string starting `https://` or `http://` is also an include; it is fetched when the configuration
>   loads (YAML if the URL path ends `.yml`/`.yaml`, otherwise text). A failed fetch → exit 4.
> - Changing a value that comes from a remote include → exit 3; stderr contains the include string
>   exactly as written in the local file. (New keys under a remote include become local overrides, per
>   step 5.)
> - `<dir>/.troupe/troupe.schema.json` (JSON Schema 2020-12), if present, describes the configuration. A
>   string whose schema — found through `properties`, `items` and `additionalProperties` — has
>   `"format": "uri"` is a literal, not an include. A string tagged `!literal` is a literal.
> - The loaded configuration must validate against the schema, else exit 4. A `set` that would make it
>   invalid → exit 3.
> - `set PATH VALUE` where `VALUE` is a string that would be read as an include and the schema does not
>   mark `PATH` as `format: uri` writes it tagged `!literal`, unless `--include` is given.

**What this changes**: step 1 FR-010 (an include is a string starting `file:`) is extended: a string
starting `https://` or `http://` is also an include, and a string that is a *literal* (FR-620) is
never an include, whatever its prefix. Step 5 FR-400 (mapping-form includes) applies to every include
string, so `$ref` may name a URL. Every other requirement and decision of steps 1–6 remains in force.

## User Scenarios & Testing *(mandatory)*

The users are developers in teams that publish shared configuration at a URL (for example a team-wide
`agents.yaml` on an internal web server) and include it in each project. They edit their own files by
hand, review them as diffs, and must not be surprised by a URL setting suddenly being fetched.

### User Story 1 - Include shared team configuration from a URL (Priority: P1)

A developer writes `agents: https://config.example.com/team/agents.yaml` in `troupe.yml`. Every
command sees the fetched content as if it were written there: `get`, `show`, `show --sources` and
history all work with it.

**Why this priority**: This is the feature's purpose; everything else protects it.

**Independent Test**: Serve fixture files from a local web server during the test, include them from
`troupe.yml`, and compare `get`/`show`/`show --sources`/`history` output with the expected
configuration.

**Acceptance Scenarios**:

1. **Given** `troupe.yml` contains `agents: https://<server>/agents.yaml` and the server returns
   `coder:\n  model: opus\n`, **When** the user runs `config get agents.coder.model`, **Then** stdout
   is `opus\n` and the exit code is 0.
2. **Given** `prompt: https://<server>/prompts/system.md` and the server returns `Be brief.\n`,
   **When** the user runs `config get prompt`, **Then** stdout is the text exactly, as a text
   include (the URL path does not end `.yml`/`.yaml`).
3. **Given** the URL `https://<server>/agents.yaml?rev=3` (the URL path ends `.yaml`, a query
   follows), **When** the configuration loads, **Then** the content is read as YAML.
4. **Given** the fixture of scenario 1, **When** the user runs `config show agents --sources`,
   **Then** `model` is annotated `# from https://<server>/agents.yaml`.
5. **Given** the server is unreachable, returns a non-success status, times out, returns text that is
   not UTF-8, or returns invalid YAML for a `.yaml` URL, **When** the user runs any command that loads
   the configuration, **Then** the exit code is 4, stdout is empty, stderr names the URL and the local
   file that contains it, and no file changes.
6. **Given** `coder: {$ref: https://<server>/coder.yaml, model: sonnet}` and the remote file has
   `model: opus`, **When** the user runs `config get agents.coder.model`, **Then** stdout is
   `sonnet\n` (overrides apply to remote includes as to `file:` includes, step 5).
7. **Given** a never-imported theatre with a remote include, **When** the user runs `config history`,
   **Then** there is one `import` event per leaf of the configuration, including the remote leaves.

---

### User Story 2 - Remote values are read-only; the user is told which include line to change (Priority: P1)

A developer tries to change a setting whose value comes from a remote include. troupe cannot write to
a URL, so it refuses, and the message says which include line in which local file brought the value
in. A *new* key under the remote section still works: it becomes a local override, as in step 5.

**Why this priority**: Without the refusal, a `set` could silently do nothing useful or write to the
wrong place; the contract requires it.

**Independent Test**: With a remote include, run `config set` for an existing remote value, for a list
append in remote content and for a new key, and compare exit codes, stderr and file bytes.

**Acceptance Scenarios**:

1. **Given** `troupe.yml` line 3 is `  coder: "https://<server>/coder.yaml"  # team` and the remote
   file has `model: opus`, **When** the user runs `config set agents.coder.model sonnet`, **Then** the
   exit code is 3, stdout is empty, stderr contains `https://<server>/coder.yaml` exactly as written
   between the quotes, names `.troupe/troupe.yml` and line 3, and no file changes.
2. **Given** the same theatre, **When** the user runs `config set agents.coder.temperature 0.3`,
   **Then** the include is converted to mapping form and `temperature: 0.3` is written as an override
   in `troupe.yml`, exactly as step 5 does for a `file:` include, and the exit code is 0.
3. **Given** the override `model: sonnet` exists locally under the remote include, **When** the user
   runs `config set agents.coder.model haiku`, **Then** the local override changes (it is not a value
   that comes from the remote include).
4. **Given** the remote file has `tools: [git]`, not overridden, **When** the user runs
   `config set agents.coder.tools.1 lint` (an append) or sets a key inside a list item of remote
   content, **Then** the exit code is 3 with the same message as scenario 1, since the change would
   have to be written in the remote file (step 5 FR-424).
5. **Given** a remote text include `prompt: https://<server>/system.md`, **When** the user runs
   `config set prompt "New text"`, **Then** the exit code is 3 and stderr contains the URL.
6. **Given** `troupe.yml` → `file:agents.yaml` → `coder: https://<server>/coder.yaml`, **When** the user
   changes a remote value, **Then** stderr names `agents.yaml` (the local file that holds the URL) and
   its line.
7. **Given** a new key under remote content, **When** the user runs `config set --in-include` for it,
   **Then** the exit code is 3 with the same message (the included file is remote and cannot be
   written).

---

### User Story 3 - URL settings stay URLs: schema `format: uri` and `!literal` (Priority: P1)

A team's configuration has settings that hold URLs, such as an API endpoint. Since step 7, a string
starting `https://` would be fetched as an include. The schema marks those settings with
`"format": "uri"`, so they stay plain strings. Any other value can be marked `!literal` in the file.

**Why this priority**: Without it, existing URL settings would be fetched and could make the
configuration unloadable. This affects every project that has a URL setting.

**Independent Test**: With a schema marking some paths `format: uri`, and some values tagged
`!literal`, load configurations containing URL- and `file:`-like strings at those paths and check that
nothing is fetched or read and `get` prints the string.

**Acceptance Scenarios**:

1. **Given** the schema
   `{"properties": {"api": {"properties": {"endpoint": {"type": "string", "format": "uri"}}}}}` and
   `troupe.yml` has `api: {endpoint: https://api.example.com/v1}`, **When** the user runs
   `config get api.endpoint`, **Then** stdout is `https://api.example.com/v1\n` and no fetch happens.
2. **Given** the schema marks `mirrors` as `{"type": "array", "items": {"type": "string", "format":
   "uri"}}`, **When** `mirrors: [https://a.example, https://b.example]` loads, **Then** both are
   strings and nothing is fetched.
3. **Given** the schema has `"agents": {"additionalProperties": {"properties": {"homepage": {"format":
   "uri"}}}}`, **When** `agents.coder.homepage: https://example.com` loads, **Then** it is a string.
4. **Given** no schema and `docs: !literal https://example.com/guide.yaml`, **When** the user runs
   `config get docs`, **Then** stdout is `https://example.com/guide.yaml\n` and nothing is fetched;
   `!literal file:notes.md` likewise is the string `file:notes.md` and the file is not read.
5. **Given** a configuration with literals, **When** the user runs `config history`, **Then** each
   literal is one leaf whose value is its string; no tag appears in any event.

---

### User Story 4 - The configuration is validated against the schema (Priority: P2)

When `.troupe/troupe.schema.json` exists, the loaded configuration must conform to it. A broken
configuration is reported when it loads. A `set` that would break the configuration is refused before
any file is written.

**Why this priority**: It protects teams from invalid configuration reaching agents, but it builds on
loading (Stories 1 and 3).

**Independent Test**: With a schema requiring `agents.coder.model` to be a string from an `enum`, load
valid and invalid configurations and run valid and invalid `set` commands. Compare exit codes, stderr
and file bytes.

**Acceptance Scenarios**:

1. **Given** a schema requiring `temperature` to be a number and `troupe.yml` has
   `temperature: warm`, **When** the user runs any command that loads the configuration, **Then** the
   exit code is 4, stdout is empty, stderr names the schema file and the path `temperature`.
2. **Given** a valid configuration, **When** the user runs `config set temperature warm`, **Then** the
   exit code is 3, stderr names the path and the schema file, no file changes and no event is
   recorded.
3. **Given** a valid configuration, **When** the user runs `config set temperature 0.5`, **Then** it
   succeeds as before.
4. **Given** remote content that makes the configuration invalid, **When** any command loads it,
   **Then** exit 4.
5. **Given** `troupe.schema.json` is not valid JSON or is not a valid JSON Schema, **When** any command
   loads the configuration, **Then** exit 4 naming the schema file.
6. **Given** no schema file, **When** any command runs, **Then** behaviour is exactly as in steps 1–6
   except for remote includes and `!literal`.

---

### User Story 5 - `set` writes include-like strings as literals unless asked (Priority: P2)

A developer sets a value that happens to look like an include (`https://…`, `http://…`, `file:…`).
Unless the schema already marks the path as a URI, troupe writes it tagged `!literal`, so the value
stays the string that was set. To create an include on purpose, the developer passes `--include`.

**Why this priority**: Without it, `set` of a URL string would silently create an include and fetch
it, so `get` would not return what was just set.

**Independent Test**: Run `config set` with include-like and ordinary strings, with and without a
schema `format: uri` at the path and with and without `--include`, and compare the bytes written.

**Acceptance Scenarios**:

1. **Given** no schema and `docs: old`, **When** the user runs
   `config set docs https://example.com/guide`, **Then** the line becomes
   `docs: !literal https://example.com/guide` and `config get docs` prints the URL.
2. **Given** the schema marks `api.endpoint` `format: uri`, **When** the user runs
   `config set api.endpoint https://api.example.com/v2`, **Then** it is written without a tag.
3. **Given** no schema, **When** the user runs `config set --include agents
   https://<server>/agents.yaml` for a new key `agents`, **Then** it is written without a tag, it
   becomes an include, and the content is fetched to check that it loads.
4. **Given** `--include` and a URL that cannot be fetched (or a `file:` target that does not exist),
   **When** the user runs the `set`, **Then** the exit code is 3 and no file changes.
5. **Given** `config set notes file:notes.md` (no `--include`), **When** it runs, **Then** it is written
   as `notes: !literal file:notes.md`.
6. **Given** `config set name coder` (not include-like), **When** it runs, **Then** no tag is written.
7. **Given** any theatre, **When** the user runs `config get --include a` (or `show`, `history`,
   `watch` with `--include`), **Then** exit 2.

---

### Edge Cases

- **Prefix match is exact**: only strings that start with `https://`, `http://` or `file:`, in that
  case, are include strings (`HTTPS://x`, ` https://x` and `ftp://x` are plain strings), consistent with
  step 1's `file:` rule.
- **Non-string scalars** are never includes or literals (e.g. a number).
- **Quoted URL strings** (`"https://…"`) are includes like plain ones. Quoting does not make a string
  literal; only the schema or `!literal` does.
- **Remote include inside remote content**: a remote YAML document may contain `https://`/`http://`
  includes; they are fetched too. Include cycles through URLs → exit 4, as step 1 FR-012.
- **`file:` include inside remote content** → exit 4, naming the URL (D-61).
- **The same URL included more than once in one command** is fetched once and used for every
  occurrence (D-62).
- **Redirects** are followed; the final response decides success (D-63).
- **Empty remote response**: a `.yaml` URL returning an empty body is an empty document (null), like an
  empty included file; a text URL returning an empty body is the empty string.
- **`!literal` on a non-string scalar** (`!literal 5`): the value is the string `5` (D-66).
  **`!literal` on a mapping or list** → exit 4 naming the file and line.
- **`!literal` on a `$ref` value**: the mapping is then an ordinary mapping with a `$ref` key, by step
  5 D-42 (the `$ref` value is not an include string).
- **Schema `format: uri` at a mapping-form include's path**: the rule applies only to strings. A
  mapping-form include is a mapping, so it is still an include.
- **Schema lookup** follows only `properties` (by key), `additionalProperties` (an object schema, for
  keys not listed in `properties`) and `items` (for any list index). Anything else (`$ref`, `allOf`,
  `anyOf`, `oneOf`, `patternProperties`, `prefixItems`, `if/then`) is not followed when deciding
  whether a string is a literal (D-64), though it is used for validation.
- **Existing `!literal` value changed to a non-include string**: the tag is kept (smallest diff,
  D-67). **Changed with `--include`**: the tag is removed and the value becomes an include.
- **`--include` at a path the schema marks `format: uri`** → exit 3: the schema says the value cannot
  be an include (D-68).
- **Include-like strings inside a collection VALUE** (`set a '{u: https://x}'`): each such string not
  marked `format: uri` by its own path is tagged `!literal`, unless `--include` (D-69).
- **Text include target written by `set`** (step 1 FR-021): file content is never read as an include,
  so no tag is written into it.
- **Remote content changes between commands**: the next command's reconcile records the difference as
  `set`/`remove` events with `via` `file` (D-65).
- **`watch`** does not poll URLs. It records remote changes when it next reconciles, as any command
  does (D-65). It treats a failed fetch or an invalid configuration like a broken file (step 2 D-13).
- **Schema file edited between commands**: a schema change can turn an include into a literal or the
  reverse. The next reconcile records the resulting configuration changes. `watch` watches the schema
  file as it watches configuration files.
- **Aliases** (step 6) in remote content: any change reached through them is a change of remote
  content → exit 3.
- **Error precedence**: loading errors (exit 4) are reported before any `set` refusal; on any non-zero
  exit, stdout is empty and no file changes.

## Requirements *(mandatory)*

### Functional Requirements

Steps 1–6 remain in force, except as stated under **What this changes**. Numbering continues at
FR-600.

**Remote includes (loading)**

- **FR-600**: A string value starting `https://` or `http://` that is not a literal (FR-620) MUST be
  treated as an include of that URL. A string starting `file:` that is not a literal remains a file
  include (step 1 FR-010). Include strings are recognised in scalar form and as the value of `$ref` in
  mapping form (step 5 FR-400).
- **FR-601**: A remote include MUST be fetched each time the configuration is loaded. Its content
  MUST be read as YAML when the URL's path component (excluding query and fragment) ends `.yml` or
  `.yaml`. Otherwise the value MUST be the response body as text, exactly.
- **FR-602**: A failed fetch MUST make the configuration unloadable: exit 4, empty stdout, stderr naming
  the URL and the local file that contains the include. A failed fetch is any of: no connection, a
  non-success final HTTP status, no complete response within 10 seconds (D-63), a body that is not
  UTF-8, or (for a YAML URL) a body that is not valid YAML.
- **FR-603**: Remote YAML content MUST be read like a local included file. Includes in it are
  followed, overrides apply (step 5), and anchors and aliases are resolved (step 6). There are two
  exceptions: a `file:` include in remote content MUST produce exit 4 naming the URL (D-61), and an
  include cycle through URLs MUST produce exit 4 (step 1 FR-012).
- **FR-604**: For `show --sources` (step 3), a value from remote content MUST be annotated with the URL
  of the remote document it comes from, as written in the include string.
- **FR-605**: Leaves from remote content MUST be imported, recorded and reconciled like any other leaves
  (steps 1, 2, 4).

**Remote includes (writing)**

- **FR-610**: A `set` that would change bytes of remote content MUST produce exit 3 with no file
  changed and no event recorded. This covers changing an existing value that is not overridden, a
  text include's text, a list append, a key inside a list item, a write through an alias, and a new
  key with `--in-include`.
- **FR-611**: The FR-610 message MUST contain the include string exactly as written in the local file
  (for a quoted scalar, the characters between the quotes). It MUST also name that local file
  (relative to the theatre, as step 3 `--sources` does) and the line number of the include. The local
  file is the nearest file on the include chain that is not remote. When the include is reached
  through further remote documents, the string shown is the outermost remote include, the one
  written in that local file.
- **FR-612**: A new key whose deepest existing ancestor comes from remote content MUST be written as an
  override in the including file, per step 5 FR-420 – FR-427. If that including file is itself remote
  (nested remote includes), the `set` MUST produce exit 3 per FR-610/FR-611 (D-60).
- **FR-613**: An existing value that is overridden in a local file MUST be changed in the override,
  per step 5 FR-430. Replacing the whole value at a remote include (scalar or mapping form) MUST
  produce exit 3, per step 1 FR-024.

**Literals**

- **FR-620**: A string is a **literal**, never an include, when either (a) it is tagged `!literal`, or
  (b) the schema (FR-630) is present and the subschema for the string's configuration path has
  `"format": "uri"`.
- **FR-621**: The subschema for a path MUST be found from the schema's root, one segment at a time:
  for a mapping key, its entry in `properties` if present, else `additionalProperties` if that is a
  schema object; for a list index, `items` if that is a schema object. If no subschema is found at a
  step, the string is not a literal by schema. No other keyword is followed (D-64).
- **FR-622**: A literal's value MUST be its string. The `!literal` tag MUST NOT appear in `get`,
  `show` or event values. `!literal` on a non-string scalar MUST give the scalar's text as a string,
  and `!literal` on a mapping or list MUST produce exit 4 naming the file (D-66).
- **FR-623**: `show` MUST print a literal as an ordinary string; it adds no tag (D-67).

**Schema and validation**

- **FR-630**: If `<dir>/.troupe/troupe.schema.json` exists, it MUST be read as a JSON Schema 2020-12
  document. If it is not valid JSON, is not a valid 2020-12 schema, declares a different `$schema`
  dialect, or contains a `$ref` that leaves the document, every command that loads the configuration
  MUST exit 4 naming the schema file.
- **FR-631**: The loaded configuration MUST be validated against the schema. It is validated after
  includes, overrides, aliases and literals are resolved, with each text include and literal as a
  string and no `$ref` keys. A configuration that does not validate MUST make every command that loads
  it exit 4. Stderr MUST name the schema file and the path of at least one failing value.
- **FR-632**: `format` MUST NOT be checked as a validation assertion. It is used only by FR-620 (D-64).
- **FR-633**: A `set` whose resulting configuration would not validate MUST produce exit 3, with stderr
  naming PATH and the schema file, no file changed and no event recorded.
- **FR-634**: With no schema file, there MUST be no validation, and only `!literal` makes literals.

**set — include-like values**

- **FR-640**: When `set`'s VALUE is a string starting `https://`, `http://` or `file:`, and the schema
  does not mark PATH `format: uri`, the value MUST be written tagged `!literal` (`key: !literal
  https://…`), unless `--include` is given. The scalar after the tag MUST follow step 1's quoting rules
  (FR-026 – FR-028).
- **FR-641**: When the schema marks PATH `format: uri`, the value MUST be written without a tag.
- **FR-642**: With `--include`, the value MUST be written without a tag. It is an include, so the new
  configuration MUST load (target found, fetch succeeds, schema validates). Otherwise the `set` MUST
  produce exit 3 with no file changed. `--include` at a path the schema marks `format: uri` MUST
  produce exit 3 (D-68).
- **FR-643**: FR-640 – FR-642 MUST apply to every include-like string inside a collection VALUE, each
  judged by its own path (D-69).
- **FR-644**: Replacing an existing `!literal` value MUST keep the tag unless `--include` is given, in
  which case the tag and the space after it MUST be removed (D-67).
- **FR-645**: `troupe config set` MUST accept `--include` (a flag, no value) in any position, combined
  with any other `set` option. Other subcommands MUST reject it with exit 2, as step 5 FR-466 does for
  `--in-include`. With a VALUE that is not include-like, `--include` MUST change nothing.
- **FR-646**: Events for a `set` MUST record the string value, without the tag (step 1 FR-043).

**Errors**

- **FR-650**: Exit codes and messages follow step 1 FR-007 and FR-008. On any non-zero exit, stdout is
  empty, stderr names the path, file or URL involved, and no file is changed.

### Decisions on open points

Recorded per Constitution Principles V and VI.

- **D-60 Nested remote includes.** A new key whose nearest including file is remote cannot be written
  as an override there. Step 5 D-40 puts the override in the nearest including file, so the `set`
  is refused (exit 3) rather than placing the override further out. Reason: refusing cannot lose
  data, and the message names the local include line to change. If the product owner wants overrides
  written in the nearest *local* file instead, this is the one decision to change.
- **D-61 `file:` includes in remote content.** Exit 4. Reason: resolving them on the user's disk
  would let a remote document pull local files into the configuration. Resolving them against the URL
  would be a URL include that the contract does not describe. Refusing is the conservative choice.
- **D-62 One fetch per URL per command.** Every occurrence of a URL in one command, and the
  re-check after a `set` (step 1 "re-read and checked"), use the same fetched content. Reason: a
  command must see one consistent configuration, and a `set` must not fail because the server
  changed between reads.
- **D-63 Fetch behaviour.** Redirects are followed. Success means a 2xx final status. There is a
  10-second limit per fetch, no authentication, no cache between commands, and no retries. Reason: the
  contract defines only "a failed fetch"; these are the plainest choices. Each is held in one place
  (Principle IV).
- **D-64 Schema lookup and `format`.** Literals are found only through `properties`,
  `additionalProperties` and `items`, as the contract lists. Validation uses the full schema. `format`
  is an annotation, as JSON Schema 2020-12 specifies by default, so a non-URI string at a
  `format: uri` path is not invalid. Reason: the contract names the three keywords, and asserting
  formats would reject configurations that the default 2020-12 vocabulary accepts. Schema `$ref`s
  that leave the document are refused (FR-630), so the schema never causes a fetch.
- **D-65 Remote changes are reconciled as file changes.** A difference between the recorded
  configuration and freshly fetched remote content is recorded by the next reconcile, with `via`
  `file` and the unknown actor (step 4). `watch` does not poll URLs. Reason: step 2 D-10 compares the
  configuration, not the files. Adding a new `via` value is not in the contract.
- **D-66 `!literal` on non-strings.** On a non-string scalar, `!literal` gives its text as a string.
  On a mapping or list it gives exit 4. Reason: the tag means "take this literally"; a collection
  cannot be a literal string, and guessing would hide a mistake.
- **D-67 Tags and `show`.** `show` prints literals as plain strings. When `set` replaces a value that
  already has a `!literal` tag, the tag is kept. Reason: `show` prints the resolved configuration (step
  3), and keeping the tag is the smallest diff (Principle I) and harmless.
- **D-68 `--include` against a `format: uri` path.** Exit 3. Reason: the schema says the value is a
  literal, so the requested include cannot exist; writing it would silently not do what was asked.
- **D-69 Include-like strings inside collection values.** Tagged like a top-level string. Reason: the
  contract's purpose is that set values are not read as includes unintentionally; a collection VALUE
  would otherwise create includes that fetch.
- **D-70 Quoting and the include string in messages.** "Exactly as written" is the scalar's text
  between its quotes (or the plain scalar). It is not normalised, decoded or resolved. Reason: the user
  can then find it in the file by searching.

### Out of contract

In addition to the earlier lists: authentication for remote includes; caching or offline use; proxy
configuration beyond the platform's defaults; a schema stored anywhere other than
`.troupe/troupe.schema.json`; asserting `format`; schemas in other dialects; editing the schema with
`troupe`; writing to remote content by any means.

### Key Entities

- **Remote include**: an include string starting `https://` or `http://`; its content is fetched and is
  read-only.
- **Local file**: a configuration file on disk (the main file or a `file:` include target); only local
  files are ever written.
- **Literal**: a string that is never an include, because it is tagged `!literal` or its schema has
  `format: uri`.
- **Schema**: `.troupe/troupe.schema.json`, a JSON Schema 2020-12 document. It validates the loaded
  configuration and marks URI settings.
- **`--include`**: a flag of `set` that writes an include-like VALUE as an include instead of a literal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-600**: For fixtures served from a local test server (YAML and text, plain and with query
  strings, scalar and mapping form, nested remote includes), `get`, `show`, `show --sources` and
  `history` output equals the expected configuration exactly.
- **SC-601**: Each failure kind in FR-602, and each of D-61 and include cycles, exits 4 with empty
  stdout and stderr naming the URL. No file changes in any of these cases.
- **SC-602**: Each kind of change to remote content listed in FR-610 exits 3. In each case stderr
  contains the include string exactly as written, the local file and the line, and every file is
  byte-for-byte unchanged.
- **SC-603**: For every literal rule (`!literal`; `format: uri` via `properties`,
  `additionalProperties`, `items`), a fixture shows that the string loads as written and no fetch or
  file read happens. The test server records zero requests.
- **SC-604**: Every validation failure on load exits 4, and every `set` that would invalidate exits 3,
  with no file changed and no event recorded.
- **SC-605**: For `set` of include-like strings, the written bytes equal the expected bytes exactly in
  every combination of schema marking and `--include`.
- **SC-606**: Every step 1–6 test passes unchanged when no schema exists and no string in its fixtures
  starts with `https://` or `http://`.

## Assumptions

- Steps 1–6 contract sections, requirements and decisions remain in force, except as stated under
  **What this changes**.
- Existing configurations that contain plain `https://`/`http://` strings are read as remote includes
  from this step on. Teams mark such settings in the schema or with `!literal`. This follows directly
  from the contract and is documented in the README.
- Tests use a local HTTP server started by the test suite, never the internet, so they are repeatable
  (Principle II: real fetches, real responses).
- The README documents remote includes, the schema, `!literal` and `--include` (Principle VI).
- Users run on macOS or Linux; configurations and remote documents are small.
