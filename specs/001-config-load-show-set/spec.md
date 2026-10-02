# Feature Specification: troupe configuration — load, show, set, history (Step 1)

**Feature Branch**: `main` (delivery is on `main`; no feature branch)

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: "Step 1 — troupe configuration: load, show, set. Load the theatre's
configuration following includes; hold it as an event-sourced projection persisted under `.troupe/`;
`troupe config show PATH`, `troupe config set PATH VALUE` (byte-surgical write-back into whichever
file holds the value), and `troupe config history [PATH]`. Contract sections in force: General;
Includes; show PATH (step 1 and 2); set PATH VALUE; history [PATH]."

The product owner's contract text (sections *General*, *Includes*, *show PATH*, *set PATH VALUE*,
*history [PATH]*) is normative. The requirements below restate it so each rule is individually
testable; where this spec and the contract appear to differ, the contract wins and this spec is
corrected. Choices the contract leaves open are recorded under **Decisions on open points**.

## User Scenarios & Testing *(mandatory)*

The users are developers who keep a project's ("theatre's") troupe configuration in hand-written YAML
under `<theatre>/.troupe/`, possibly split across several files, and who review every change to those
files as a diff.

### User Story 1 - Read a setting (Priority: P1)

A developer asks for one setting by its dotted path and gets its value printed, regardless of which
file (main file or an included file) it lives in.

**Why this priority**: Reading the effective configuration, with includes resolved, is the
foundation every other command builds on, and is useful on its own.

**Independent Test**: Create a theatre with a main file and included files, run
`uv run troupe config show <path> --theatre <dir>` for values in each file, and compare stdout and
the exit code to the expected values.

**Acceptance Scenarios**:

1. **Given** `troupe.yml` contains `model: {temperature: 0.2}`, **When** the user runs
   `config show model.temperature`, **Then** stdout is `0.2\n` and the exit code is 0.
2. **Given** `troupe.yml` contains `agents: {coder: "file:agents/coder.yaml"}` and
   `agents/coder.yaml` (relative to `.troupe/`) contains `model: opus`, **When** the user runs
   `config show agents.coder.model`, **Then** stdout is `opus\n`.
3. **Given** `prompt: file:prompts/system.md` where `system.md` contains `Be terse.\n`, **When** the
   user runs `config show prompt`, **Then** stdout is exactly `Be terse.\n`.
4. **Given** `tools: [git, shell]`, **When** the user runs `config show tools.1`, **Then** stdout is
   `shell\n`; **When** they run `config show tools`, **Then** the exit code is 5, stdout is empty and
   stderr names `tools`.
5. **Given** no `.troupe/troupe.yml` and no `.troupe/troupe.yaml`, or both, **When** the user runs any
   `config` command, **Then** the exit code is 4 and stderr names the file(s).
6. **Given** an include whose target is missing, or includes that form a cycle, **When** the user runs
   any `config` command, **Then** the exit code is 4 and stderr names the offending file.

---

### User Story 2 - Change a setting without disturbing the file (Priority: P1)

A developer changes one setting from the command line. The change lands in the file where that
setting lives, and the resulting diff shows only the bytes of the value that changed — every comment,
blank line, indentation, quoting choice and key order elsewhere is untouched.

**Why this priority**: This is the core promise of the tool (Constitution Principle I); a write that
reformats a hand-edited file is worse than no tool.

**Independent Test**: For each write-back rule, take a fixture file, run `config set`, and compare the
exact bytes of every file in the theatre before and after against an expected result.

**Acceptance Scenarios**:

1. **Given** `  temperature: 0.2   # creative`, **When** the user runs
   `config set model.temperature 0.75`, **Then** the line becomes `  temperature: 0.75  # creative`
   (comment stays at its column) and no other byte in any file changes.
2. **Given** `name: 'coder'`, **When** the user sets `name` to `reviewer`, **Then** the line becomes
   `name: 'reviewer'` (quoting kept).
3. **Given** `agents.coder` is `file:agents/coder.yaml`, **When** the user sets
   `agents.coder.model sonnet`, **Then** only `agents/coder.yaml` changes.
4. **Given** `agents.coder` is `file:agents/coder.yaml`, **When** the user runs
   `config set agents.coder '{model: x}'`, **Then** the exit code is 3 and no file changes.
5. **Given** `prompt: file:prompts/system.md`, **When** the user sets `prompt` to
   `"New prompt\n"`, **Then** `system.md` contains exactly `New prompt\n` and `troupe.yml` is
   unchanged; if `system.md` used CRLF line endings it contains `New prompt\r\n`.
6. **Given** `tools:` is a block list of two items followed by an indented comment line, **When** the
   user runs `config set tools.2 lint`, **Then** a `- lint` item is inserted below that comment line;
   **When** they run `config set tools.5 lint`, **Then** the exit code is 5.
7. **Given** a mapping `model:` with no `retries` key, **When** the user runs
   `config set model.limits.retries 3`, **Then** `limits:` and `retries: 3` are written as new block
   lines in the file holding `model`, at the file's indentation.
8. **Given** a folded (`>`) value, **When** the user changes one paragraph, **Then** the unchanged
   paragraphs keep their bytes and the changed one is re-wrapped at its previous width.

---

### User Story 3 - See what changed (Priority: P2)

A developer lists the history of configuration changes, for the whole configuration or for one
subtree, as machine-readable lines.

**Why this priority**: History is the visible benefit of the event-sourced store and supports review
and audit, but reading and writing settings come first.

**Independent Test**: On a fresh theatre, run `config history`, then several `config set` commands,
then `config history` and `config history <path>`, and compare the JSON Lines output.

**Acceptance Scenarios**:

1. **Given** a theatre never used before with leaves `a: 1` and `b: [x, y]`, **When** the user runs
   `config history`, **Then** stdout is three JSON lines: `import` events for `a`, `b.0`, `b.1`, with
   `seq` 1, 2, 3 and `old` null.
2. **Given** that theatre, **When** the user runs `config set a 2` and then `config history`,
   **Then** a fourth line `{"seq": 4, "op": "set", "path": "a", "old": 1, "new": 2}` follows.
3. **Given** `b: [x, y]`, **When** the user runs `config set b '[z]'`, **Then** history gains a
   `set` event for `b.0` (`x`→`z`) and a `remove` event for `b.1` (`old` `y`, `new` null).
4. **Given** any history, **When** the user runs `config history b`, **Then** only events whose path
   is `b` or starts with `b.` are printed (not, for example, `bb`).
5. **Given** `a` is already `2`, **When** the user runs `config set a 2`, **Then** no event is
   recorded and no file changes.
6. **Given** history was recorded, **When** a later, separate command runs, **Then** the earlier
   events are still listed (state survives between commands).

---

### Edge Cases

- **Path through a scalar**: `show a.b` or `set a.b 1` where `a` is a scalar (including a text include)
  → exit 5 naming the path.
- **Index on a mapping / key on a list**: a digit segment on a mapping, or a non-digit segment on a
  list → exit 5.
- **Missing path for show**: → exit 5.
- **Append index**: `set list.N` with N equal to the list's length appends; N greater → exit 5; this
  applies to block and flow lists.
- **Text include given a non-string**: `set prompt 3` where `prompt` is a text include → exit 3, no
  file changed.
- **Folded value gaining a more-indented line**: → exit 3, no file changed.
- **Invalid VALUE** (not exactly one YAML flow node), missing arguments, unknown subcommand or option
  → exit 2.
- **Unparseable YAML** in the main file or any included file → exit 4 naming that file.
- **Include chains**: an included YAML file may itself contain includes; paths resolve relative to the
  directory of the file that contains the `file:` string.
- **Set that changes nothing**: no file is written (bytes and modification are untouched) and no
  event is recorded; exit 0.
- **Replacing a collection with a scalar, or a scalar with a collection**: leaves that disappear get
  `remove` events; new leaves get `set` events. When a scalar becomes a block collection, the key's
  line keeps its bytes up to and including its end-of-line comment.
- **Multi-line string into a flow collection** (new key): written as a double-quoted flow scalar.
- **Failure after a partial computation**: on any non-zero exit no file is changed and no event is
  recorded; stdout is empty.

## Requirements *(mandatory)*

### Functional Requirements

**General**

- **FR-001**: The tool MUST be invoked as `troupe config <subcommand> --theatre <dir> [arguments]`,
  runnable as `uv run troupe …` from the repository root; `--theatre` MUST default to the current
  directory.
- **FR-002**: The configuration file MUST be `<dir>/.troupe/troupe.yml` or `<dir>/.troupe/troupe.yaml`;
  if neither or both exist the tool MUST exit 4.
- **FR-003**: The tool MUST keep its own state only under `<dir>/.troupe/` and MUST NOT create or
  modify any other file except as the write-back rules (FR-020 – FR-036) require.
- **FR-004**: A PATH MUST be keys separated by `.`; a segment of only digits MUST index a list,
  0-based.
- **FR-005**: VALUE MUST be parsed as a single YAML 1.2 core-schema flow node (`0.2` float, `true`
  boolean, `null` null, `abc` and `"0.2"` strings, `{a: 1}` mapping, `[a, b]` list,
  `"line one\nline two\n"` multi-line string). Configuration files MUST likewise be read with YAML 1.2
  core-schema typing (so `yes`/`on` are strings).
- **FR-006**: Scalars MUST be printed as: strings exactly, plus `\n` unless already ending in `\n`;
  booleans `true`/`false`; null `null`; integers in decimal; floats as Python's `repr()`.
- **FR-007**: Exit codes MUST be: 0 success; 2 usage error; 3 write refused (no file changed);
  4 configuration cannot be loaded; 5 path not found or wrong kind of node for the command.
- **FR-008**: On any non-zero exit, stdout MUST be empty and stderr MUST contain a message naming the
  offending path or file.

**Includes**

- **FR-010**: A string value starting with `file:` MUST be treated as an include of the path after
  `file:`, resolved relative to the directory of the file containing the string.
- **FR-011**: If the target's name ends in `.yml` or `.yaml`, its parsed content MUST be embedded in
  place of the string; otherwise the value MUST be the target file's exact text (a string).
- **FR-012**: Includes MUST be followed recursively; a missing target or an include cycle MUST
  produce exit 4.

**show**

- **FR-015**: `config show PATH` MUST print the scalar at PATH per FR-006 (a text include prints as
  its text). A mapping or list at PATH, or a missing PATH, MUST produce exit 5.

**set — where the change is written**

- **FR-020**: An existing value MUST be changed in the file that contains it.
- **FR-021**: For a text include, the target file's content MUST become VALUE exactly; if the target
  file used CRLF line endings, the new content MUST use CRLF. A non-string VALUE MUST produce exit 3.
- **FR-022**: A new key MUST be written into the file containing the deepest existing ancestor
  mapping of PATH, creating any missing intermediate mappings in that file.
- **FR-023**: A PATH whose last segment equals a list's length MUST append to that list; a larger
  index MUST produce exit 5.
- **FR-024**: Replacing the value at a path whose whole value comes from an include (e.g.
  `agents.coder` when it is `file:agents/coder.yaml`) MUST produce exit 3.
- **FR-025**: After a successful `set`, the only bytes that differ in any file MUST be those the rules
  FR-020 – FR-036 require to change.

**set — how it is written**

- **FR-026**: A changed scalar MUST keep its quoting style if that style can represent the new value;
  otherwise plain if possible, else single-quoted, else double-quoted.
- **FR-027**: A new key, and a new string value, MUST copy the quoting style of the preceding sibling
  key or value; with no sibling, plain (or the minimal quoting the text needs).
- **FR-028**: A double-quoted scalar MUST escape only `\\`, `\"` and control characters (as `\t`,
  `\n`, …); every other character MUST be written literally.
- **FR-029**: A new collection value MUST be written in block style at the file's indentation
  (default 2), unless its parent is a flow collection, in which case it MUST be written in flow style.
- **FR-030**: A multi-line string replacing a plain or quoted scalar MUST be written as a literal block
  (`|`, or `|-` when the value has no trailing newline). A block scalar MUST keep its indicator and
  chomping unless the value's trailing newlines require a different chomping.
- **FR-031**: A new key whose value is a multi-line string MUST be written as a literal block per
  FR-030, unless its parent is a flow collection, where it MUST be a double-quoted flow scalar.
- **FR-032**: For folded (`>`) values: paragraphs whose text is unchanged MUST keep their bytes; a
  changed paragraph MUST be re-wrapped greedily by word at the width of the longest content line of
  that paragraph before the change (a word longer than the width takes a line of its own); a paragraph
  with no counterpart in the old value MUST be wrapped at the width of the value's longest old content
  line; a change that would put a more-indented line into a folded value MUST produce exit 3.
- **FR-033**: A new list item or mapping key MUST be placed after the collection's last entry and below
  any comment lines that follow it, before the next less-indented line; a comment line indented less
  than the collection's entries ends the collection.
- **FR-034**: In a flow collection, a new entry MUST be appended after the last entry, on that entry's
  line.
- **FR-035**: When a scalar is replaced by a block collection, the key's line MUST keep its bytes up to
  and including its end-of-line comment.
- **FR-036**: When a changed value's length changes, an end-of-line comment on that line MUST be moved
  back to its previous column; if the new value reaches that column, exactly one space MUST separate
  value and comment. No other line changes. Columns count Unicode code points.

**History and the event-sourced store**

- **FR-040**: The configuration MUST be held as an event-sourced projection, recorded with the
  `eventsourcing` library (a constraint fixed by the product owner and the constitution), persisted
  under `<dir>/.troupe/` so it survives between commands.
- **FR-041**: Events MUST be per leaf (a scalar, including a text-include string; list items are
  `list.0`, `list.1`, …).
- **FR-042**: The first command run against a theatre MUST import it: one `import` event per leaf,
  `old` null. `history` MUST also import a never-imported theatre. Importing MUST NOT reconcile (a
  theatre already imported is never re-imported).
- **FR-043**: A `set` MUST record one `set` event per leaf whose value it changes or creates and one
  `remove` event (`new` null) per leaf that no longer exists; a `set` that changes nothing MUST record
  nothing.
- **FR-044**: `config history [PATH]` MUST print events as JSON Lines, oldest first, each an object
  with at least `seq` (integer from 1), `op` (`import` | `set` | `remove`), `path` (dotted), `old` and
  `new` (JSON values). With PATH, only events whose path equals PATH or starts with `PATH.` MUST be
  printed.

### Decisions on open points

Recorded per Constitution Principles V and VI; each is the conservative reading of the contract.

- **D-1 Files are the source of truth for values.** `show` and `set` read the configuration from the
  files as they are at that moment, so hand edits are always respected. The event store records
  history; it is not consulted to answer `show`. A `set`'s events are computed by comparing the
  configuration loaded from the files immediately before and after the change. Hand edits made between
  commands are not recorded as events ("importing is not reconciling").
- **D-2 When import happens.** The import happens on the first command whose configuration loads
  successfully, before the command's own work, and stands even if that command then fails with exit
  2, 3 or 5. A command that exits 4 records nothing. Import order is document order (depth-first,
  includes expanded in place).
- **D-3 Event order within one `set`.** `set` events (in document order of the new value) come before
  `remove` events (in document order of the old value).
- **D-4 Wrong kind of node for `set`.** Descending through a scalar, using a digit segment on a
  mapping, or a non-digit segment on a list → exit 5.
- **D-5 Configuration root.** The main file's top level must be a mapping (or empty, treated as an
  empty mapping); any other top level → exit 4. Unparseable YAML in any loaded file → exit 4. Included
  YAML files may have any top-level node.
- **D-6 Line endings in YAML files.** Lines a `set` adds or rewrites in a YAML file use the line ending
  that file already uses (CRLF if its first line ending is CRLF, else LF). The same "first line ending"
  rule decides whether a text-include target "used CRLF" (FR-021).
- **D-7 No-op writes.** When a `set` would produce identical bytes, no file is rewritten at all.
- **D-8 Atomic writes.** Each file is replaced as a whole (never left half-written); events are recorded
  only after the file write succeeds.
- **D-9 Encoding.** Configuration and included files are UTF-8.

### Out of contract

Behaviour undefined and not tested: TAB before an end-of-line comment; multi-document files; YAML
anchors, aliases and merge keys (until step 6); concurrent writers; keys containing `.`; mappings with
digit-only keys; Windows.

### Key Entities

- **Theatre**: a project directory; its configuration and the tool's state live in `<theatre>/.troupe/`.
- **Configuration file**: the main file `troupe.yml`/`troupe.yaml` and every file reached by includes;
  each is hand-edited and must be preserved byte-for-byte outside requested changes.
- **Include**: a `file:` string; a YAML include embeds another file's structure, a text include
  supplies a string equal to the target's text.
- **Setting / leaf**: a scalar value addressed by a dotted path; the unit of events.
- **Event**: a recorded change to one leaf — sequence number, operation (`import`, `set`, `remove`),
  path, old value, new value.
- **Projection**: the configuration state rebuilt from the events, persisted under `.troupe/`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every write-back rule (FR-020 – FR-036), a fixture test shows that after `set` the
  bytes of every file in the theatre equal the expected bytes exactly — 100% of rules covered, zero
  unexpected byte differences.
- **SC-002**: For every non-zero exit path, tests confirm the documented exit code, empty stdout, a
  stderr message naming the path or file, and that no file in the theatre changed.
- **SC-003**: `show` returns the correct printed value for settings in the main file, in YAML includes
  nested at least two levels deep, and in text includes.
- **SC-004**: History survives between separate command invocations, and its sequence numbers are
  contiguous from 1 with no duplicates across at least 10 consecutive `set` commands.
- **SC-005**: A reviewer diffing a file after any `set` sees only the changed value's lines (plus any
  lines the rules require to be added) — no reformatting anywhere else.

## Assumptions

- Users run the tool on macOS or Linux with `uv` installed; Python 3.12+.
- Configurations are small; there are no performance targets (constitution, Technical Constraints).
- An include target path may be absolute or relative and may lead outside `.troupe/`; such files are
  still written back to when the contract requires it.
- `show PATH` follows the contract text marked "step 1 and 2"; no further step-2 behaviour is in scope.
- Commands other than `show`, `set` and `history` are not part of this step.
