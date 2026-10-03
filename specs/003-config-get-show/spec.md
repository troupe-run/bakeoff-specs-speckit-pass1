# Feature Specification: troupe configuration — `get` for values, `show` for anything (Step 3)

**Feature Branch**: `main` (delivery is on `main`; no feature branch)

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "Step 3 — `get` for values, `show` for anything. We are changing
`show`. From now on `troupe config get PATH` prints a single value — what `show` used to do.
`troupe config show [PATH]` prints either a value or a whole section as YAML, and with `--sources`
says which file each value comes from. Contract sections added: get and show (replaces "show PATH
(step 1 and 2)")."

The product owner's contract section **`get` and `show`** is normative and replaces step 1's section
*show PATH (step 1 and 2)*. Every other step 1 and step 2 section stays in force (see
`specs/001-config-load-show-set/spec.md` and `specs/002-config-file-sync/spec.md`). The requirements
below restate the contract so each rule is individually testable; where this spec and the contract
appear to differ, the contract wins and this spec is corrected. Choices the contract leaves open are
recorded under **Decisions on open points**.

Contract text (verbatim):

> - `get PATH` prints a scalar as `show` did in step 1. A mapping or list → exit 5, and stderr mentions
>   `config show`.
> - `show [PATH]` prints a scalar like `get`; a mapping or list is printed as YAML (block style, includes
>   resolved, text includes as literal blocks). `PATH` omitted → the whole configuration.
> - `show [PATH] --sources` prints the same YAML with an end-of-line comment `# from <file>` on every line that
>   holds a scalar, where `<file>` is the file the scalar comes from, relative to the theatre directory, with
>   `/` separators. A text include's value comes from the included file.

**What step 3 changes from steps 1 and 2.** Step 1 FR-015 (`show PATH` prints a scalar; a mapping or
list → exit 5) is replaced: that behaviour moves to `get` (FR-200 – FR-203), and `show` now prints
mappings and lists too (FR-210 – FR-226). Step 2's rule that every command except `history`
reconciles first applies to `get` as well (FR-204).

## User Scenarios & Testing *(mandatory)*

The users are developers who keep a theatre's troupe configuration in hand-written YAML under
`<theatre>/.troupe/`, split across several files with `file:` includes. They want one value for a
script, or a readable view of a whole section with includes resolved — and, when a value is
surprising, to know which file to open to change it.

### User Story 1 - Read one value for a script (Priority: P1)

A developer (or a script) asks for one setting with `get` and gets exactly the printed value, the
same way `show` printed it in step 1. Asking `get` for a whole section is refused with a hint to use
`show`.

**Why this priority**: `get` takes over the step 1 behaviour every existing user and script relies
on; without it the change to `show` would break them.

**Independent Test**: Create a theatre with a main file, a YAML include and a text include; run
`uv run troupe config get <path> --theatre <dir>` for scalars in each file and for a mapping and a
list; compare stdout, stderr and the exit code with the expected results.

**Acceptance Scenarios**:

1. **Given** `troupe.yml` contains `model: {temperature: 0.2}`, **When** the user runs
   `config get model.temperature`, **Then** stdout is `0.2\n` and the exit code is 0.
2. **Given** `agents: {coder: "file:agents/coder.yaml"}` where `agents/coder.yaml` contains
   `model: opus`, **When** the user runs `config get agents.coder.model`, **Then** stdout is `opus\n`.
3. **Given** `prompt: file:prompts/system.md` where `system.md` contains `Be terse.\n`, **When** the
   user runs `config get prompt`, **Then** stdout is exactly `Be terse.\n`.
4. **Given** `tools: [git, shell]`, **When** the user runs `config get tools`, **Then** the exit code
   is 5, stdout is empty, and stderr names `tools` and mentions `config show`.
5. **Given** `agents.coder` is a mapping, **When** the user runs `config get agents.coder`, **Then**
   the exit code is 5, stdout is empty, and stderr names `agents.coder` and mentions `config show`.
6. **Given** no key `missing`, **When** the user runs `config get missing`, **Then** the exit code is 5
   and stderr names `missing`.
7. **Given** a hand edit `a: 1` → `a: 2` not yet recorded, **When** the user runs `config get a`,
   **Then** stdout is `2\n` and history gains the reconcile `set` event for `a`.

---

### User Story 2 - See a section, or the whole configuration, as YAML (Priority: P1)

A developer runs `show` on a section (or on nothing, for everything) and sees it as one readable YAML
document with every include resolved in place — YAML includes expanded, text includes shown as
literal blocks — so they can read the effective configuration without opening several files.

**Why this priority**: It is the new capability the step asks for; it replaces having to open and
mentally merge every included file.

**Independent Test**: For fixtures with nested includes, text includes, lists of mappings, and
values that need quoting, run `config show [PATH]` and compare stdout byte-for-byte with the expected
YAML; also parse the output with YAML 1.2 core-schema rules and check it equals the configuration at
PATH.

**Acceptance Scenarios**:

1. **Given** `model: {temperature: 0.2}`, **When** the user runs `config show model.temperature`,
   **Then** stdout is `0.2\n` (same as `get`).
2. **Given** `troupe.yml`:
   ```yaml
   # main
   model: {temperature: 0.2, name: 'opus'}
   agents:
     coder: file:agents/coder.yaml
   prompt: file:prompts/system.md
   ```
   with `agents/coder.yaml` = `model: sonnet\ntools: [git, shell]\n` and `prompts/system.md` =
   `Be terse.\nNo jokes.\n`, **When** the user runs `config show`, **Then** stdout is exactly:
   ```yaml
   model:
     temperature: 0.2
     name: opus
   agents:
     coder:
       model: sonnet
       tools:
         - git
         - shell
   prompt: |
     Be terse.
     No jokes.
   ```
3. **Given** the same theatre, **When** the user runs `config show agents.coder`, **Then** stdout is
   exactly `model: sonnet\ntools:\n  - git\n  - shell\n`.
4. **Given** `tools: [git, shell]`, **When** the user runs `config show tools`, **Then** stdout is
   exactly `- git\n- shell\n`.
5. **Given** `steps: [{name: a, run: x}, {name: b}]`, **When** the user runs `config show steps`,
   **Then** stdout is exactly `- name: a\n  run: x\n- name: b\n`.
6. **Given** string values `"0.2"`, `"true"`, `"null"`, `""` and `"a: b"`, **When** they are shown in a
   section, **Then** each is quoted so that the YAML reads back as the same string, and plain strings
   such as `opus` or `yes` are not quoted.
7. **Given** a missing path, or a path that descends through a scalar, **When** the user runs
   `config show` on it, **Then** the exit code is 5 and stderr names the path.

---

### User Story 3 - Find out which file a value comes from (Priority: P2)

A developer sees a surprising value and runs `show --sources` to learn which file holds each value,
so they know which file to open and edit.

**Why this priority**: It builds on User Story 2's output and answers a frequent but secondary
question once includes spread a configuration over many files.

**Independent Test**: For a theatre with values in the main file, nested YAML includes, a text
include, and an include outside `.troupe/`, run `config show [PATH] --sources` and compare stdout
byte-for-byte with the expected annotated YAML.

**Acceptance Scenarios**:

1. **Given** the theatre of User Story 2 scenario 2, **When** the user runs `config show --sources`,
   **Then** stdout is exactly:
   ```yaml
   model:
     temperature: 0.2 # from .troupe/troupe.yml
     name: opus # from .troupe/troupe.yml
   agents:
     coder:
       model: sonnet # from .troupe/agents/coder.yaml
       tools:
         - git # from .troupe/agents/coder.yaml
         - shell # from .troupe/agents/coder.yaml
   prompt: | # from .troupe/prompts/system.md
     Be terse.
     No jokes.
   ```
2. **Given** the same theatre, **When** the user runs `config show agents --sources`, **Then** stdout
   is the `agents` section alone, annotated the same way.
3. **Given** `shared: file:../common/shared.yaml` (a file outside `.troupe/`, in `<theatre>/common/`),
   **When** the user runs `config show shared --sources`, **Then** each scalar line ends with
   `# from common/shared.yaml`.
4. **Given** `model: {temperature: 0.2}`, **When** the user runs
   `config show model.temperature --sources`, **Then** stdout is `0.2 # from .troupe/troupe.yml\n`
   (D-23).
5. **Given** the output of any `show --sources`, **When** it is parsed as YAML, **Then** it reads back
   as the same values as `show` without `--sources` (the comments add nothing to the values).

---

### Edge Cases

- **Empty configuration** (empty main file): `show` prints `{}\n`; `show --sources` prints `{}\n`
  (no scalar, so no comment).
- **Empty mapping or list inside a section**: printed in flow form, `{}` or `[]`, the only exception to
  block style (block style cannot write an empty collection); not annotated, as it is not a scalar.
- **Multi-line string that is not a text include** (e.g. a literal block in a YAML file): printed as a
  literal block, like a text include; with `--sources` it is annotated with the YAML file it is in.
- **Text include whose text has no trailing newline, more than one trailing newline, or is empty**:
  still a literal block, with the chomping indicator that reads back as the exact text (`|-`, `|+`).
- **Text include whose first line starts with a space**: literal block with an explicit indentation
  indicator so it reads back as the exact text.
- **Text include with CRLF line endings**: shown as a literal block of its lines (D-24).
- **Text include whose text starts with `file:`**: shown as its text; it is not followed again.
- **Single-line text include** (`Be terse.\n`): in a section, still a literal block (`prompt: |`);
  as a scalar at PATH, `show` and `get` print the text exactly.
- **Text include shown as a scalar with `--sources`**: printed as a top-level literal block with the
  comment on its header line (D-23).
- **Same file included twice** (two keys pointing to the same YAML file): both sections are shown in
  full, each annotated with that file.
- **Include target reached through `..` or a symbolic link**: `<file>` is the path as written, made
  relative to the theatre directory and lexically normalised (D-22); links are not resolved.
- **Keys that need quoting** (e.g. a key `true` or `"a: b"`): quoted like string values.
- **Floats** `inf`, `-inf`, `nan` inside a section: written `.inf`, `-.inf`, `.nan` so they read back
  as floats; as a scalar at PATH they print as `get` prints them (step 1 FR-006).
- **Hand edits not yet recorded**: `get` and `show` reconcile first (step 2), so they print the files
  as they are.
- **Usage errors**: `get` with no PATH, `get`/`show` with an extra argument, `get --sources`, an
  unknown option → exit 2, stdout empty, nothing recorded.
- **Unloadable configuration**: `get` and `show` exit 4 naming the file, as every command.

## Requirements *(mandatory)*

### Functional Requirements

Numbering continues from step 2 (step 1 FR-001 – FR-044 and step 2 FR-100 – FR-131 remain in force,
except FR-015, which this section replaces) at FR-200.

**get**

- **FR-200**: The tool MUST provide `troupe config get PATH [--theatre <dir>]`; PATH is required.
- **FR-201**: `get` MUST print the scalar at PATH exactly as step 1 printed it with `show` (step 1
  FR-006; a text include prints as its text).
- **FR-202**: A mapping or list at PATH MUST produce exit 5 with empty stdout and a stderr message that
  names PATH and contains the text `config show`.
- **FR-203**: A missing PATH, or a PATH that descends through a scalar, uses a digit segment on a
  mapping or a non-digit segment on a list, MUST produce exit 5 naming PATH (as step 1 `show` did).
- **FR-204**: `get` and `show` MUST import a never-imported theatre and reconcile before printing,
  like every command except `history` (step 2 FR-120); they MUST NOT write any configuration file.

**show — what is printed**

- **FR-210**: The tool MUST provide `troupe config show [PATH] [--sources] [--theatre <dir>]`.
- **FR-211**: When PATH holds a scalar and `--sources` is not given, `show` MUST print exactly what
  `get PATH` prints.
- **FR-212**: When PATH holds a mapping or list, `show` MUST print that node as a YAML document; with
  PATH omitted it MUST print the whole configuration. Errors for PATH are as for `get` (FR-203).
- **FR-213**: The YAML MUST have every include resolved: a YAML include appears as its content,
  embedded in place; a text include appears as its text. Nothing from the source files other than
  values is reproduced (no comments, no `file:` strings, no original quoting or layout).
- **FR-214**: Parsing the printed YAML with YAML 1.2 core-schema rules MUST give exactly the
  configuration at PATH — same keys, same order, same values and types — except as stated in D-24.

**show — how the YAML is written**

- **FR-220**: Mappings and lists MUST be written in block style, indented 2 spaces per level; a list
  nested under a key is indented 2 spaces under that key (`tools:\n  - git`); a mapping or list that is
  a list item starts on the item's line (`- name: a\n  run: x`, `- - x`). Empty mappings and lists are
  written `{}` and `[]`.
- **FR-221**: Keys MUST appear in document order of the files, with includes expanded in place.
- **FR-222**: A string MUST be written plain when the plain form reads back as the same string;
  otherwise single-quoted when that can represent it; otherwise double-quoted (escaping only `\\`, `\"`
  and control characters, as step 1 FR-028). Keys follow the same rule.
- **FR-223**: A text include's value, and any other string containing a line break, MUST be written as
  a literal block scalar (`|`), with the chomping indicator (`|` one trailing newline, `|-` none, `|+`
  more than one) and, when needed, the indentation indicator that make it read back as the same text.
  Its content lines are indented 2 spaces deeper than the key or `-` it belongs to.
- **FR-224**: Other scalars MUST be written as: booleans `true`/`false`; null `null`; integers in
  decimal; floats as Python's `repr()` except infinities and NaN as `.inf`, `-.inf`, `.nan`.
- **FR-225**: Every line of output MUST end with `\n`; there MUST be no document markers (`---`,
  `...`) and no trailing blank line beyond what a `|+` block's own content requires.

**show --sources**

- **FR-230**: With `--sources`, `show` MUST print the same YAML as without it, except that every line
  that holds a scalar ends with ` # from <file>` (one space, then the comment). Lines that hold no
  scalar (a key that opens a mapping or list, `{}`, `[]`) get no comment.
- **FR-231**: For a literal block scalar the comment MUST go on its header line (`prompt: | # from …`);
  its content lines MUST NOT be changed.
- **FR-232**: `<file>` MUST be the file the scalar is written in: the main configuration file for its
  own values, the included YAML file for values inside it (at any include depth), and, for a text
  include, the included text file.
- **FR-233**: `<file>` MUST be given relative to the theatre directory, with `/` separators and no
  leading `./`; e.g. `.troupe/troupe.yml`, `.troupe/agents/coder.yaml`.
- **FR-234**: When PATH holds a scalar, `show PATH --sources` MUST print that scalar as a one-node YAML
  document written per FR-222 – FR-224 with the comment per FR-230 – FR-231 (D-23).

**Errors**

- **FR-240**: Exit codes and messages follow step 1 (FR-007, FR-008): usage errors exit 2,
  unloadable configuration exits 4, path errors exit 5; on any non-zero exit stdout is empty and
  stderr names the path or file.

### Decisions on open points

Recorded per Constitution Principles V and VI.

- **D-20 `get` and `show` reconcile.** The step 2 contract says every command except `history`
  reconciles first; `get` is such a command, so it reconciles too. Reason: `get` must answer from the
  files as they are, and the hand edit is then recorded once.
- **D-21 YAML layout.** The contract fixes block style and literal blocks but not the layout. Chosen:
  2-space indentation, lists indented under their key, minimal quoting, document order (FR-220 –
  FR-225). Reason: it matches the default indentation step 1 writes (FR-029), is the most common
  hand-written layout, and reads back as the same values (FR-214), so the output can be pasted into a
  configuration file. Empty collections use `{}` / `[]` because block style cannot express them.
- **D-22 `<file>` for files outside the theatre directory.** "Relative to the theatre directory" is
  taken literally: a file outside it is given with `..` segments (e.g. `../shared/x.yaml`). The path is
  normalised lexically from the include strings as written; symbolic links are not resolved. Reason:
  it names the file the user wrote in the include, and resolving links could name a file the user
  never referred to.
- **D-23 `--sources` on a scalar.** The contract says `show` prints a scalar like `get`, and that
  `--sources` prints "the same YAML" annotated, but does not say what `--sources` does for a scalar.
  Chosen: the scalar is printed as YAML with the comment (e.g. `0.2 # from .troupe/troupe.yml`; a text
  include as `| # from .troupe/prompts/system.md` followed by its indented lines). Reason: the user
  asked where the value comes from, and `--sources` must answer that; printing it as YAML is the only
  form that can carry the comment and is consistent with section output. Without `--sources`, a scalar
  is printed exactly as `get` prints it, as the contract requires.
- **D-24 CRLF text includes.** A YAML literal block cannot hold a carriage return; YAML reads its line
  breaks as `\n`. Chosen: a text include is always shown as a literal block, as the contract requires,
  with each of its lines as a content line; a CRLF file therefore reads back with `\n` line breaks.
  `get` (and `show` on the scalar) still print the text exactly. Reason: the contract's "text includes
  as literal blocks" is explicit, and `show`'s YAML is for reading; `get` remains the exact form.
  This is the only exception to FR-214. Other non-printable characters in a text include that a
  literal block cannot hold are out of contract.
- **D-25 Separator before the comment.** One space before `#`, the minimum YAML requires. Reason:
  the contract gives no column; one space is predictable for scripts and readers alike.
- **D-26 `--sources` placement.** `--sources` is an option of `show` only; it may appear before or
  after PATH. On `get` it is a usage error (exit 2).

### Out of contract

In addition to the step 1 and step 2 lists: text includes containing control characters other than
tab and line breaks; non-UTF-8 text; configurations with keys that are not strings (e.g. digit-only
keys, as step 1).

### Key Entities

- **Scalar / leaf**: as in step 1; the unit `get` prints and `--sources` annotates.
- **Section**: a mapping or list at PATH (or the whole configuration), printed by `show` as YAML.
- **Source file**: for each scalar, the file it is written in (main file, YAML include, or text include
  target), named relative to the theatre directory.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-201**: Every step 1 `show PATH` scenario that printed a scalar gives the same stdout, stderr and
  exit code under `get`; every step 1 scenario that refused a mapping or list exits 5 under `get` with
  `config show` in stderr.
- **SC-202**: For fixtures covering the main file, YAML includes nested at least two levels deep, text
  includes, lists of mappings, nested lists, empty collections and strings that need quoting, `show`'s
  output equals the expected bytes exactly, and reading it back gives the configuration at PATH
  (100% of fixtures; CRLF per D-24).
- **SC-203**: In `show --sources` output, 100% of lines that hold a scalar carry the correct
  `# from <file>`, and no other line carries one.
- **SC-204**: `get` and `show` never change any configuration file (bytes compared before and after)
  and record only reconcile and import events.

## Assumptions

- Step 1 and step 2 contract sections, requirements and decisions remain in force, except step 1
  FR-015, which this step replaces.
- Existing tests and documentation for step 1 `show PATH` are moved to `get` or updated to the new
  `show` behaviour in the same change (Principle VI).
- `history`, `set` and `watch` are unchanged.
- Users run on macOS or Linux; configurations are small.
