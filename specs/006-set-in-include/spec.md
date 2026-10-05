# Feature Specification: troupe configuration — `set --in-include` (Step 5, CR-B)

**Feature Branch**: `main` (delivery is on `main`; no feature branch)

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "CR-B: but let me put it in the shared file when I mean to. Sometimes a
new setting genuinely belongs in the shared file. Give `set` an explicit way to do that. Contract
sections added: In-include."

This change request belongs to step 5 and builds on CR-A (`specs/005-include-overrides/spec.md`),
which makes `set` write a new key under included content as an override in the including file. The
contract section **In-include** is normative, together with the sections in force from steps 1–4 and
CR-A. The requirements below restate it so each rule is individually testable; where this spec and the
contract appear to differ, the contract wins and this spec is corrected. Choices the contract leaves
open are recorded under **Decisions on open points**.

Contract text (verbatim):

> - `set --in-include PATH VALUE` writes a new key into the included file instead (the step 1 rule).

"The step 1 rule" is step 1 FR-022: a new key is written into the file containing the deepest existing
ancestor mapping of PATH, creating any missing intermediate mappings in that file.

## User Scenarios & Testing *(mandatory)*

The users are developers who share included files between projects. By default (CR-A) a new setting
stays in their own project as an override; sometimes they decide the setting belongs to everyone who
shares the file, and say so explicitly.

### User Story 1 - Add a setting to the shared file on purpose (Priority: P1)

A developer adds a new setting under an included section with `--in-include`. It is written into the
included (shared) file, exactly as step 1 did, and the including file is unchanged.

**Why this priority**: This is the whole change request.

**Independent Test**: For a theatre whose `troupe.yml` includes `agents/coder.yaml`, run
`config set --in-include` for a new key under the included section and compare every file's bytes
before and after.

**Acceptance Scenarios**:

1. **Given** `troupe.yml` contains `  coder: file:agents/coder.yaml  # c` and `coder.yaml` contains
   `model: sonnet\n`, **When** the user runs
   `config set --in-include agents.coder.temperature 0.3`, **Then** `coder.yaml` becomes
   `model: sonnet\ntemperature: 0.3\n`, `troupe.yml` is byte-for-byte unchanged (still scalar form),
   and the exit code is 0.
2. **Given** the same theatre, **When** the user runs `config set --in-include
   agents.coder.limits.retries 3` and `coder.yaml` has no `limits`, **Then** `limits:` and
   `retries: 3` are written as new block lines in `coder.yaml` at its indentation.
3. **Given** `coder` is in mapping form with an override `limits: {timeout: 30}` and `coder.yaml`
   contains `limits:` / `  retries: 2`, **When** the user runs
   `config set --in-include agents.coder.limits.backoff 2`, **Then** `backoff: 2` is written under
   `limits` in `coder.yaml`, and `troupe.yml` is unchanged.
4. **Given** the same theatre, **When** the user runs the same command without `--in-include`,
   **Then** the CR-A rule applies: the key is written as an override in `troupe.yml` and `coder.yaml`
   is unchanged — the default is not affected by this change request.
5. **Given** nested includes `troupe.yml` → `coder.yaml` → `model.yaml`, **When** the user sets a new
   key under `agents.coder.model` with `--in-include`, **Then** it is written into `model.yaml`, the
   file holding the deepest existing ancestor.

---

### User Story 2 - The option is predictable everywhere else (Priority: P2)

`--in-include` only decides where a *new key* under included content goes. Everywhere else `set`
behaves exactly as without it, and other subcommands reject the option.

**Why this priority**: Users and agents will pass the option habitually; it must never surprise them
or touch a file they did not expect.

**Independent Test**: Run `set --in-include` on existing values, list appends and keys in the main
file, compare the bytes with the same `set` without the option; run other subcommands with the option
and check exit 2.

**Acceptance Scenarios**:

1. **Given** an existing overridden value `agents.coder.model` (override in `troupe.yml`), **When** the
   user runs `config set --in-include agents.coder.model haiku`, **Then** the override in `troupe.yml`
   changes, exactly as without the option (D-50).
2. **Given** an existing value not overridden, **When** the user sets it with `--in-include`, **Then**
   it changes in the file it comes from, as without the option.
3. **Given** a new key whose deepest existing ancestor is in the main file, **When** the user sets it
   with `--in-include`, **Then** it is written in the main file, as without the option.
4. **Given** a list in an included file, **When** the user appends with `--in-include`, **Then** the
   item is appended in the file holding the list, as without the option.
5. **Given** any theatre, **When** the user runs `config get --in-include a`, `config show
   --in-include`, `config history --in-include` or `config watch --in-include`, **Then** the exit code
   is 2, stdout is empty, stderr names the option, and no file changes.
6. **Given** a `set --in-include` that writes a new key, **When** the user runs `config history`,
   **Then** the events are recorded as for any `set` (one `set` event per new leaf, `via` `cli`,
   the actor and any `--reason` given).

---

### Edge Cases

- **Option position**: `--in-include` may appear anywhere among `set`'s arguments (before or after
  PATH and VALUE), like `--reason`; the two may be combined.
- **Option given twice**: accepted, same as once.
- **Option with a value** (`--in-include=yes`) → exit 2.
- **Ancestor is a merged mapping** (keys from the included file and from an override): the new key is
  written into the included file's part of that mapping (D-51).
- **Ancestor exists only in an override** (no counterpart in the included file): there is no included
  file to write into; the key is written in the file holding the override, as the step 1 rule gives
  (D-51).
- **Ancestor is a mapping-form include with no overrides**: written into the included file; the
  including file keeps its mapping form unchanged.
- **New key inside a list item** of an included file: written in the file holding the list, with or
  without the option (CR-A FR-424 and the step 1 rule agree).
- **Included file used by several keys** (`a: file:common.yaml`, `b: file:common.yaml`): a new key
  written with `--in-include` appears under both, as in step 1; events are recorded for both paths.
- **Errors**: every refusal of `set` (exit 3, 4, 5) is unchanged; on any non-zero exit no file changes.

## Requirements *(mandatory)*

### Functional Requirements

Numbering continues after CR-A (`specs/005-include-overrides/spec.md`, FR-400 – FR-450) at FR-460.

- **FR-460**: `troupe config set` MUST accept the option `--in-include` (a flag, no value) in any
  position among its arguments, alone or with `--reason`.
- **FR-461**: With `--in-include`, a new key MUST be written by the step 1 rule: into the file
  containing the deepest existing ancestor mapping of PATH, creating any missing intermediate mappings
  in that file. CR-A's override placement (FR-421 – FR-423, D-40, D-41, D-47, D-48) MUST NOT apply, and
  no include is converted to mapping form.
- **FR-462**: For a merged ancestor mapping, "the file containing the deepest existing ancestor
  mapping" MUST be the included file that holds that mapping's included part; an ancestor with no
  included part is in the file that holds it (D-51).
- **FR-463**: All formatting rules of steps 1 and 2 (placement after the last entry, quoting copied from
  siblings, block/flow style, indentation, line endings, atomic writes) MUST apply to the written key.
  After a successful `set --in-include`, the only bytes that change MUST be those of the new key's lines
  in the one file written.
- **FR-464**: With `--in-include`, setting an existing value, appending to a list, and adding a key
  inside a list item MUST behave exactly as without it (D-50).
- **FR-465**: Events and lineage of a `set --in-include` MUST be those of any `set` (step 1 FR-043,
  step 4): one `set` event per new leaf at every path where the new value appears.
- **FR-466**: Subcommands other than `set` MUST reject `--in-include` as an unknown option: exit 2,
  empty stdout, stderr naming the option, nothing loaded or written. `--in-include` given a value MUST
  also exit 2.

### Decisions on open points

Recorded per Constitution Principles V and VI.

- **D-50 `--in-include` on anything but a new key.** The option is accepted and changes nothing: an
  existing value still changes where it lives (CR-A FR-430/FR-431), and list appends and keys inside
  list items still go to the file holding the list. Reason: the contract defines the option only for a
  new key; for everything else the existing rules already say where the change lands, and refusing
  would make the option unsafe to pass habitually (e.g. by an agent that always wants shared writes).
  The alternative — making `--in-include` change an *overridden* existing value in the included file
  — would leave the override still winning, so the visible value would not change; rejected.
- **D-51 Merged ancestors.** When the deepest existing ancestor merges an included mapping with an
  override, the new key goes to the included (shared) file's mapping. Reason: the option exists to put
  a key in the shared file; writing into the override would ignore it. When the ancestor exists only in
  an override, there is no shared mapping at that path, and inventing one in the shared file would add
  keys the user did not ask for; the step 1 rule (the file holding the ancestor) applies.
- **D-52 Name and form.** `--in-include` is a flag of `set` only, like `--reason` (step 4 FR-332).
  Reason: the contract names it; consistency with existing options.

### Out of contract

In addition to the earlier lists: an option to force a write into the *including* file for an existing
non-overridden value (i.e. creating an override for an existing key); choosing which of several nested
included files receives the key.

### Key Entities

- **`--in-include`**: a flag of `set` that selects the step 1 placement rule for new keys.
- Entities of CR-A (mapping-form include, override, including file, shared file) are unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-460**: In 100% of fixtures where `set --in-include` adds a new key under included content
  (scalar and mapping form, block and flow, missing intermediates, nested includes, merged ancestors),
  the included file equals the expected bytes exactly and every other file is byte-for-byte unchanged.
- **SC-461**: For every fixture of steps 1–5 that does not add a new key under included content,
  `set --in-include` produces exactly the same files, exit code and history as `set` without it.
- **SC-462**: Every step 1 new-key-in-include fixture that CR-A changed passes again, unchanged, when run
  with `--in-include`.
- **SC-463**: `--in-include` on every other subcommand exits 2 with empty stdout and no file changed.

## Assumptions

- CR-A (`specs/005-include-overrides`) is implemented together with or before this change request;
  without CR-A the option would be indistinguishable from the default.
- Steps 1–4 and CR-A requirements and decisions remain in force; this CR adds an option and does not
  change any default.
- The README documents `--in-include` alongside CR-A's override rules (Principle VI).
- Users run on macOS or Linux; configurations are small.
