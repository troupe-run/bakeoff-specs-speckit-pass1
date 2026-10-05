# Feature Specification: troupe configuration — include overrides (Step 5)

**Feature Branch**: `main` (delivery is on `main`; no feature branch)

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "Step 5 — a change request. CR-A: keep shared includes shared. Included
files are shared between projects. Adding a new setting under an included section must no longer
modify the shared file: it should be added in the including file, as an override. Existing settings
still change where they live. Contract sections added: Overrides (replaces rule 2 under
`set PATH VALUE`)."

The product owner's contract section **Overrides** is normative, together with the sections already in
force from steps 1–4 (see `specs/001-config-load-show-set/spec.md`,
`specs/002-config-file-sync/spec.md`, `specs/003-config-get-show/spec.md`,
`specs/004-config-lineage/spec.md`). The requirements below restate it so each rule is individually
testable; where this spec and the contract appear to differ, the contract wins and this spec is
corrected. Choices the contract leaves open are recorded under **Decisions on open points**.

Contract text (verbatim):

> - An include may be written in **mapping form**: a mapping with a `$ref` key whose value is the
>   include string. Its other keys are **overrides**: the value is the included content deep-merged
>   with the overrides (mappings merge recursively; scalars and lists in the override replace).
> - A new key whose deepest existing ancestor comes from an included file is written as an override
>   in the file that contains the include reference (the *including* file). A scalar-form include is
>   first converted to mapping form, indented at the file's indentation, keeping any end-of-line
>   comment on the key's line:
>   `coder: file:agents/coder.yaml  # c` → `coder:  # c` / `  $ref: file:agents/coder.yaml` /
>   `  temperature: 0.3`
> - Appending a list item is not a new key: the item is appended in the file that holds the list.
>   Likewise, a new key inside a list item is written in the file that holds the list, since
>   overrides cannot address list items.
> - Overrides apply only to YAML includes; a mapping-form include of any other file with sibling keys
>   → exit 4.
> - Setting an existing value that is overridden changes the override; one that is not overridden is
>   still changed in the file it comes from.

**What this replaces**: step 1 FR-022 ("a new key MUST be written into the file containing the
deepest existing ancestor mapping of PATH") is replaced by FR-420 – FR-427 below. Step 1 FR-020
("an existing value MUST be changed in the file that contains it") is refined by FR-430 – FR-432.
Every other requirement and decision of steps 1–4 remains in force.

## User Scenarios & Testing *(mandatory)*

The users are developers whose theatres include files shared with other projects (for example a
common `agents/coder.yaml`). They review every change as a diff, and a change made for one project
must not leak into the others through a shared file.

### User Story 1 - Add a setting to an included section without touching the shared file (Priority: P1)

A developer adds a setting that does not exist yet under a section that comes from a shared include.
The new setting is written in their own file, next to the include reference, as an override. The
shared file is byte-for-byte unchanged.

**Why this priority**: This is the change request itself; without it, every new setting silently
changes every project that shares the file.

**Independent Test**: Create a theatre whose `troupe.yml` includes `agents/coder.yaml`, run
`config set` for a new key under the included section, and compare the exact bytes of every file
before and after.

**Acceptance Scenarios**:

1. **Given** `troupe.yml` contains `  coder: file:agents/coder.yaml  # c` under `agents:` and
   `coder.yaml` has no `temperature`, **When** the user runs
   `config set agents.coder.temperature 0.3`, **Then** those lines in `troupe.yml` become
   `  coder:  # c`, `    $ref: file:agents/coder.yaml`, `    temperature: 0.3`; `coder.yaml` is
   byte-for-byte unchanged; `config get agents.coder.temperature` prints `0.3`.
2. **Given** `coder` is already in mapping form with `$ref` and an override `model: sonnet`, **When**
   the user sets a new key `agents.coder.temperature 0.3`, **Then** `temperature: 0.3` is added after
   the last override key in `troupe.yml`, and no other file changes.
3. **Given** `coder.yaml` contains `limits: {retries: 2}`, **When** the user runs
   `config set agents.coder.limits.timeout 30`, **Then** `troupe.yml` gains the override
   `limits:` / `timeout: 30` under `coder` (in block style at the file's indentation), `coder.yaml`
   is unchanged, and `config get agents.coder.limits.retries` still prints `2`.
4. **Given** the include is written in a flow mapping, e.g. `agents: {coder: file:agents/coder.yaml}`,
   **When** the user sets a new key under `agents.coder`, **Then** the include is converted to a flow
   mapping `{$ref: file:agents/coder.yaml, temperature: 0.3}` in place, and only that line changes.
5. **Given** the new key is set, **When** the user runs `config history`, **Then** one `set` event
   for `agents.coder.temperature` is recorded, with the lineage fields of step 4.

---

### User Story 2 - Read configurations that use overrides (Priority: P1)

A developer writes a mapping-form include by hand — `$ref` plus override keys — and every command
sees the merged value: `get` and `show` print it, `show --sources` names the file each value comes
from, history and reconcile record its leaves.

**Why this priority**: Overrides written by `set` must read back correctly, and users will also write
them by hand; reading comes before any further writing.

**Independent Test**: Hand-write fixtures with mapping-form includes (overrides of scalars, lists,
nested mappings, nested includes), run `get`, `show`, `show --sources` and `history`, and compare the
output with the expected merged configuration.

**Acceptance Scenarios**:

1. **Given** `coder.yaml` contains `model: opus` and `tools: [git, shell]`, and `troupe.yml` has
   `coder: {$ref: file:agents/coder.yaml, model: sonnet, tools: [lint]}`, **When** the user runs
   `config get agents.coder.model`, **Then** stdout is `sonnet\n`; `config get agents.coder.tools.0`
   prints `lint` and `config get agents.coder.tools.1` exits 5 (the override list replaces).
2. **Given** `coder.yaml` contains `limits: {retries: 2, timeout: 10}` and the override is
   `limits: {timeout: 30}`, **When** the user runs `config show agents.coder.limits`, **Then** stdout
   is `retries: 2\ntimeout: 30\n` (mappings merge recursively).
3. **Given** the fixture of scenario 2, **When** the user runs `config show agents.coder --sources`,
   **Then** `retries` is annotated `# from .troupe/agents/coder.yaml` and `timeout` and every other
   overridden scalar `# from .troupe/troupe.yml`; no `$ref` key appears in the output.
4. **Given** `prompt: {$ref: file:prompts/system.md}` (no sibling keys), **When** the user runs
   `config get prompt`, **Then** it prints the text of `system.md`, as a scalar-form text include does.
5. **Given** `prompt: {$ref: file:prompts/system.md, x: 1}`, **When** the user runs any `config`
   command, **Then** the exit code is 4, stdout is empty, and stderr names the file containing that
   mapping and the include.
6. **Given** a never-imported theatre with overrides, **When** the user runs `config history`,
   **Then** there is one `import` event per leaf of the merged configuration, and none for `$ref`.

---

### User Story 3 - Change an existing setting where it lives (Priority: P2)

A developer changes a setting that already exists. If the setting is overridden, the override is
changed; otherwise it is changed in the file it comes from, as before.

**Why this priority**: The change request explicitly keeps this behaviour; it must be correct for
overridden values, which are new in this step.

**Independent Test**: For a theatre with overridden and non-overridden settings under one include,
run `config set` on each and compare file bytes before and after.

**Acceptance Scenarios**:

1. **Given** `coder: {$ref: file:agents/coder.yaml, model: sonnet}` and `coder.yaml` has
   `model: opus`, **When** the user runs `config set agents.coder.model haiku`, **Then** only the
   override in `troupe.yml` changes (`model: haiku`), and `coder.yaml` is unchanged.
2. **Given** the same theatre and `coder.yaml` has `effort: low` that is not overridden, **When** the
   user runs `config set agents.coder.effort high`, **Then** only `coder.yaml` changes.
3. **Given** the setting is already the requested value, **When** the user sets it, **Then** no file
   changes and no event is recorded.

---

### User Story 4 - Lists stay in the file that holds them (Priority: P2)

Appending to a list, or adding a key inside a list item, writes into the file that holds the list,
because overrides cannot address list items.

**Why this priority**: It bounds where the new override rule applies; without it the tool might try
to write overrides it cannot express.

**Independent Test**: With lists in an included file and in an override, append items and add keys
inside items, and compare file bytes before and after.

**Acceptance Scenarios**:

1. **Given** `coder.yaml` has `tools: [git, shell]` (not overridden), **When** the user runs
   `config set agents.coder.tools.2 lint`, **Then** `lint` is appended in `coder.yaml`, and
   `troupe.yml` is unchanged.
2. **Given** `coder.yaml` has `steps:` with a mapping item `- name: build`, **When** the user runs
   `config set agents.coder.steps.0.retries 3`, **Then** `retries: 3` is written into that item in
   `coder.yaml`.
3. **Given** the override `tools: [lint]` in `troupe.yml`, **When** the user runs
   `config set agents.coder.tools.1 fmt`, **Then** `fmt` is appended to the override list in
   `troupe.yml` (the file that holds the effective list), and `coder.yaml` is unchanged.

---

### Edge Cases

- **Nested includes**: `troupe.yml` includes `agents/coder.yaml`, which includes `model.yaml` as
  `model: file:model.yaml`; a new key under `agents.coder.model` is written as an override in
  `coder.yaml`, the file that contains the include reference it comes through (D-40).
- **Ancestor present in an override**: when the deepest existing ancestor of a new key is a mapping
  written in an override (even if the included file also has that mapping), it comes from the file
  the override is written in (D-48): if that is the main file, the new key is written into the
  override's mapping there.
- **Override position not reachable through plain mappings** (the override already present at that
  position is itself an include, e.g. `limits: file:limits.yaml` as an override) → exit 3, no file
  changed (D-47).
- **Ancestor in the including file's own content**: a new key whose deepest existing ancestor is not
  from an include is written as before (step 1 FR-022 behaviour), into the file that holds it.
- **New key directly under the include's root** (`agents.coder.temperature` where `agents.coder` is
  the include): the include itself is the ancestor; it is converted to mapping form if needed.
- **Include as a list item** (`agents: [file:a.yaml]`): a new key under `agents.0` is written as an
  override on that list item, which is converted to mapping form within the list (D-41); a new key
  inside a list item *of an included file* is written in that included file (FR-424).
- **`$ref` whose value is not an include string** (e.g. `$ref: abc`, or a non-string): an ordinary
  mapping with a key `$ref`; no include happens (D-42).
- **Overrides on a YAML include whose content is not a mapping** (a list or scalar) → exit 4 naming
  the including file (D-43). With no sibling keys it is valid and the value is the included content.
- **Replacing a whole include** (`set agents.coder '{…}'`), in scalar or mapping form → exit 3, as
  step 1 FR-024; no file changes.
- **Replacing an overridden mapping that also has keys from the included file**
  (`set agents.coder.limits '{a: 1}'` when `retries` comes from `coder.yaml`) → exit 3, because no
  override can remove the included keys (D-44).
- **Override value that is itself an include** (`prompt: file:p.md` as an override key): followed as
  any include; setting it writes the target file (step 1 FR-021).
- **`$ref` as a path segment** (`get agents.coder.$ref`) → exit 5; `$ref` is not part of the value.
- **Mapping-form include of a missing file, or one that forms a cycle** → exit 4, as step 1 FR-012.
- **Hand edits that add, change or remove overrides** are reconciled as any hand edit (step 2): events
  follow the change in the merged configuration.
- **Converting a quoted include string** (`coder: "file:agents/coder.yaml"`): the `$ref` value keeps
  the original quoting (D-45).

## Requirements *(mandatory)*

### Functional Requirements

Numbering continues from step 4 (steps 1–4 remain in force, except as stated under **What this
replaces**) at FR-400.

**Mapping-form includes (reading)**

- **FR-400**: A mapping that has a `$ref` key whose value is an include string (a string starting with
  `file:`, step 1 FR-010) MUST be treated as a mapping-form include of that target, resolved relative
  to the directory of the file containing the mapping. Its other keys are its overrides.
- **FR-401**: For a YAML target, the value MUST be the included content deep-merged with the overrides:
  where both sides have a mapping, they merge key by key, recursively; anywhere else, the override's
  value (scalar, list, or mapping over a non-mapping) replaces the included value.
- **FR-402**: A mapping-form include with no override keys MUST have the same value as the scalar-form
  include of the same string, for YAML and non-YAML targets alike.
- **FR-403**: A mapping-form include of a non-YAML target that has any sibling key MUST make the
  configuration unloadable: exit 4, stderr naming the file that contains the mapping.
- **FR-404**: Override values MUST be read like any other value in the including file: includes in
  them are followed, and they may themselves be mapping-form includes.
- **FR-405**: The `$ref` key MUST NOT be part of the value: it is not a leaf, has no events, is not
  printed by `show`, and a PATH segment `$ref` at a mapping-form include is a missing path (exit 5).
- **FR-406**: Key order of a merged mapping MUST be the included content's order, with each overridden
  key at its included position, followed by override-only keys in the order they are written (D-46).
  This order applies to `show` output, import order and event order.
- **FR-407**: Missing targets and include cycles through `$ref` MUST produce exit 4, as step 1
  FR-012.
- **FR-408**: For each scalar, the source file (`show --sources`, step 3 FR-232) MUST be the file the
  effective value is written in: the including file for an overridden value, the included file
  otherwise.

**set — new keys (replaces step 1 FR-022)**

- **FR-420**: A new key MUST be written in the file containing its deepest existing ancestor mapping,
  creating any missing intermediate mappings there, unless FR-421 applies.
- **FR-421**: When that ancestor's content comes from an included YAML file (it is the include's root
  or lies within the included content; a merged mapping counts as coming from its override's file,
  D-48), the new key MUST be written as an override in the including file — the file that contains
  the include reference through which the ancestor is reached most directly (D-40) — with any missing
  intermediate mappings created in the override. Existing override mappings on the way MUST be
  reused, never duplicated. FR-424 takes precedence: an ancestor inside a list item is written in the
  file that holds the list.
- **FR-422**: A scalar-form include MUST first be converted to mapping form: in block context the key's
  line keeps its bytes up to and including the key's colon, followed by exactly the whitespace and
  end-of-line comment that followed the include string (nothing, if it had no comment); the include
  string and the space before it are removed. Then a `$ref` line with
  the include string is inserted below, indented one indentation step (the file's indentation, default
  2) deeper than the key, followed by the override. The contract example MUST hold exactly:
  `coder: file:agents/coder.yaml  # c` → `coder:  # c` / `  $ref: file:agents/coder.yaml` /
  `  temperature: 0.3`.
- **FR-423**: In flow context, the include string MUST be replaced in place by a flow mapping
  `{$ref: <include string>, <override>}`, per step 1 FR-029 and FR-034.
- **FR-424**: Appending a list item (index equal to the list's length) MUST be written in the file
  that holds the effective list, and a new key inside a list item MUST be written in the file that
  holds the list; neither is ever written as an override.
- **FR-425**: A new key under a mapping-form include that already exists MUST be placed after the
  include mapping's last entry per step 1 FR-033 / FR-034, with the quoting rules of step 1 FR-027.
- **FR-426**: Converting to mapping form and adding the override MUST be one write of the including
  file; the included file MUST be byte-for-byte unchanged.
- **FR-427**: All other writing rules (quoting, block/flow style, literal blocks, comment columns,
  line endings, atomic writes, no-op writes) MUST apply to overrides as in steps 1 and 2.

**set — existing values**

- **FR-430**: Setting an existing value that is overridden (the effective value is written in an
  override) MUST change the override in the including file.
- **FR-431**: Setting an existing value that is not overridden MUST change it in the file it comes
  from, even if that is a shared included file.
- **FR-432**: Replacing a mapping whose effective value merges keys from both an override and an
  included file MUST produce exit 3 with no file changed (D-44). Replacing the value at a path whose
  whole value is an include, in scalar or mapping form, MUST produce exit 3 (step 1 FR-024).

**History, lineage and reconcile**

- **FR-440**: Import, `set`, reconcile and `watch` MUST record events for leaves of the merged
  configuration exactly as for any other value; a `set` that adds an override records one `set` event
  per created leaf and none for `$ref` or for the conversion to mapping form. Lineage (step 4) is
  unchanged.
- **FR-441**: Files reached through `$ref` MUST be watched and reconciled like scalar-form include
  targets (step 2 FR-103).

**Errors**

- **FR-450**: Exit codes and messages follow step 1 FR-007 and FR-008: on any non-zero exit stdout is
  empty, stderr names the path or file, and no file is changed.

### Decisions on open points

Recorded per Constitution Principles V and VI.

- **D-40 Nested includes: the nearest including file.** When the deepest existing ancestor comes from
  a file that is itself reached through another include (e.g. `troupe.yml` → `coder.yaml` →
  `model.yaml`), the override is written in the file that contains the include reference to the file
  the ancestor comes from (`coder.yaml`). Reason: it is the literal reading of "the file that contains
  the include reference"; writing further out would need overrides that reach through two includes,
  which the contract does not describe. If the product owner wants overrides always written in the
  main file, this is the one decision to change.
- **D-41 An include that is a list item.** Overrides cannot address items *inside* a list, but a list
  item that is itself an include can carry its own overrides; it is converted to mapping form within
  the list (`- $ref: file:a.yaml` / `  temperature: 0.3`). Reason: the ancestor comes from an included
  file, so the contract's rule applies, and doing so keeps the shared file unchanged.
- **D-42 `$ref` whose value is not an include string.** The mapping is an ordinary mapping with a key
  named `$ref`. Reason: the contract defines mapping form only for a `$ref` "whose value is the include
  string"; treating other values as errors would refuse configurations that load today.
- **D-43 Overrides on a YAML include whose content is not a mapping.** Exit 4 naming the including
  file. Reason: overrides are keys and can only merge into a mapping; replacing a list or scalar with
  a mapping of overrides would silently discard the included content. Refusing is the conservative
  choice (Principle I).
- **D-44 Replacing a mapping that merges included and override keys.** Exit 3. Reason: an override can
  add or change keys but cannot remove keys of the included file, so the result could not equal the
  requested VALUE; writing to the shared file instead would defeat CR-A.
- **D-45 Writing the converted include string.** The `$ref` value keeps the include string's original
  bytes (including quoting); the `$ref` key is written plain. Reason: smallest diff (Principle I).
- **D-46 Key order of merged mappings.** Included order first, override-only keys after. Reason: an
  override changes a key's value, not its place, so `show` of a project that overrides one value still
  reads like the shared file.
- **D-47 An override position that is itself an include.** When the override that must receive the
  new key already holds an include at some step of its path (an override `limits: file:l.yaml`),
  `set` exits 3. Reason: the key could go into the override or into `l.yaml`, and `l.yaml` may be
  shared too; refusing cannot lose data (Principle I), and the user can write it by hand.
- **D-48 Which file a merged mapping comes from.** A mapping whose keys come from both an included
  file and an override counts, for FR-421, as coming from the file the override is written in.
  Reason: the user has already chosen to override that section in that file; when that file is itself
  included, the new key moves one level further out, so no shared file gains it.

### Out of contract

In addition to the earlier lists: two `$ref` keys in one mapping (not valid YAML anyway); overrides
that address list items by index (`tools: {0: x}`); removing a key that comes from an included file.

### Key Entities

- **Scalar-form include**: a `file:` string as in step 1.
- **Mapping-form include**: a mapping with `$ref` set to an include string; its other keys are
  overrides.
- **Override**: a key under a mapping-form include whose value replaces or merges into the included
  content; written in the including file.
- **Including file**: the file that contains an include reference.
- **Shared (included) file**: the file an include reference points to; may be shared by several
  theatres.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-401**: In 100% of fixtures where `set` adds a new key under included content (block and flow
  context, scalar and mapping form, nested intermediates, nested includes), every included file's
  bytes are identical before and after, and the including file equals the expected bytes exactly.
- **SC-402**: The contract's conversion example produces exactly the three lines given in the
  contract, with no other byte change in any file.
- **SC-403**: For fixtures covering scalar, list and nested-mapping overrides, `get`, `show` and
  `show --sources` output equals the expected merged configuration and source files exactly.
- **SC-404**: Every refusal (FR-403, FR-432, D-43) exits with the documented code, empty stdout, a
  stderr message naming the path or file, and no file changed.
- **SC-405**: All step 1–4 tests that do not add a new key under included content pass unchanged;
  those that did are updated to the override behaviour in the same change (Principle VI).

## Assumptions

- Steps 1–4 contract sections, requirements and decisions remain in force, except step 1 FR-022,
  replaced here, and FR-020, refined here.
- Users decide which files are shared; the tool treats every included file as possibly shared.
- Earlier specs and the README are updated to point to this step where their rules changed
  (Principle VI).
- Users run on macOS or Linux; configurations are small.
