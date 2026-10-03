# Feature Specification: troupe configuration — keep files and configuration in sync (Step 2)

**Feature Branch**: `main` (delivery is on `main`; no feature branch)

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "Step 2 — keep files and configuration in sync. People edit `.troupe/`
files directly, in their editor, while troupe is running. Add `troupe config watch`, which picks up
those edits as they happen, and make every command pick up edits made while nothing was running. When
troupe itself writes a change back to a file, that must not be picked up again as a new change.
Contract sections added: Sync with files."

The product owner's contract section **Sync with files** is normative, together with the step 1
sections already in force (see `specs/001-config-load-show-set/spec.md`). The requirements below
restate it so each rule is individually testable; where this spec and the contract appear to differ,
the contract wins and this spec is corrected. Choices the contract leaves open are recorded under
**Decisions on open points**.

Contract text (verbatim):

> - `troupe config watch --theatre <dir>` runs in the foreground until SIGINT or SIGTERM (then exits
>   0). Once it is watching, it prints one line `watching <dir>` to stdout and flushes. The line is a
>   promise: it is printed only after `watch` is able to observe changes. Within 2 seconds of any
>   change to the config file or an included file made after that line appears, it reconciles.
> - **Reconcile:** compare the files with the configuration and emit a `set`/`remove` event for each
>   leaf that differs. A formatting-only or comment-only edit emits nothing.
> - Every other command except `history` reconciles first, so edits made while nothing was running
>   are picked up. `history` never reconciles: it reports what has been recorded.
> - A `set` while `watch` runs emits exactly the `set`'s own events; its write-back produces no
>   further events.
> - An include added by a hand edit is followed; its leaves appear as `set` events.

**What step 2 changes from step 1.** Step 1 decision D-1 said hand edits made between commands are
not recorded as events. That decision is superseded: hand edits are now recorded by reconciling
(FR-110 – FR-122). Step 1's other rules — including that the first command imports the theatre
(FR-042, D-2) and that `history` imports a never-imported theatre — still hold.

## User Scenarios & Testing *(mandatory)*

The users are developers who keep a theatre's troupe configuration in hand-written YAML under
`<theatre>/.troupe/` and edit it in their editor, sometimes while troupe is running and sometimes
while nothing is running. They expect the recorded history to reflect every change to the effective
configuration, whoever made it — once, and only once.

### User Story 1 - Hand edits made while nothing was running are picked up (Priority: P1)

A developer edits a setting in their editor, then later runs any troupe config command. Before doing
its own work, the command notices the edit and records it, so `show` answers from the files as they
are and history lists the hand edit.

**Why this priority**: It needs no long-running process, covers the most common workflow (edit, then
run a command), and is the core of "reconcile" that `watch` reuses.

**Independent Test**: In a theatre that has been imported, change files by hand (values, comments,
formatting, includes), run `config show` / `config set`, then compare `config history` output with
the expected JSON Lines.

**Acceptance Scenarios**:

1. **Given** an imported theatre with `a: 1`, **When** the user edits the file to `a: 2` and runs
   `config show a`, **Then** stdout is `2\n`, and a following `config history` ends with
   `{"seq": N, "op": "set", "path": "a", "old": 1, "new": 2}`.
2. **Given** an imported theatre, **When** the user only re-indents lines, changes quoting that does
   not change a value (`a: x` → `a: "x"`), adds or edits comments, or adds blank lines, and then runs
   `config show a`, **Then** no event is recorded.
3. **Given** an imported theatre with `b: [x, y]`, **When** the user edits it to `b: [x]` and runs
   `config show b.0`, **Then** a `remove` event for `b.1` (`old` `y`, `new` null) is recorded.
4. **Given** an imported theatre, **When** the user adds a new key `c: 3` by hand and runs any
   reconciling command, **Then** a `set` event for `c` with `old` null and `new` 3 is recorded.
5. **Given** an imported theatre, **When** the user adds `agents: {coder: "file:agents/coder.yaml"}`
   by hand where `agents/coder.yaml` contains `model: opus` and `tools: [git]`, and runs any
   reconciling command, **Then** `set` events for `agents.coder.model` and `agents.coder.tools.0` are
   recorded.
6. **Given** an imported theatre with a hand edit `a: 1` → `a: 2` not yet reconciled, **When** the
   user runs `config set b 5`, **Then** history gains the reconcile event for `a` first, then the
   `set` event for `b`.
7. **Given** an imported theatre with a hand edit not yet reconciled, **When** the user runs
   `config history`, **Then** the hand edit is not listed and no event is recorded; a later
   reconciling command records it.
8. **Given** a hand edit that is reconciled, **When** another reconciling command runs with no
   further edits, **Then** nothing more is recorded (each change is recorded once).

---

### User Story 2 - Live sync while editing (Priority: P1)

A developer starts `troupe config watch` in a terminal and keeps editing configuration files in their
editor. Each saved edit is recorded within 2 seconds, without running any other command.

**Why this priority**: It is the new command the step asks for and the only way edits are recorded
as they happen.

**Independent Test**: Start `uv run troupe config watch --theatre <dir>` as a subprocess, wait for
the `watching <dir>` line, edit files (in place and by the save-by-rename method editors use), wait
up to 2 seconds, and check `config history`; then send SIGINT or SIGTERM and check exit code 0.

**Acceptance Scenarios**:

1. **Given** a valid theatre, **When** the user runs `config watch --theatre <dir>`, **Then** exactly
   one line `watching <dir>` appears on stdout once it is ready, and the process keeps running.
2. **Given** `watch` has printed its line, **When** the user changes `a: 1` to `a: 2` in the main file,
   **Then** within 2 seconds history contains the `set` event for `a` (1 → 2).
3. **Given** `watch` is running, **When** the user changes a value inside an included YAML file, or
   changes the text of a text-include target, **Then** within 2 seconds the corresponding `set` event
   is recorded.
4. **Given** `watch` is running, **When** the user makes a comment-only or formatting-only edit,
   **Then** no event is recorded.
5. **Given** `watch` is running, **When** the user adds an include by hand and then edits a value in
   the newly included file, **Then** the include's leaves are recorded as `set` events within
   2 seconds of the first edit, and the later edit to the new file is recorded within 2 seconds of
   that edit.
6. **Given** `watch` is running, **When** it receives SIGINT or SIGTERM, **Then** it exits with code 0
   and prints nothing further on stdout.
7. **Given** a theatre that was never used, **When** the user starts `watch`, **Then** the theatre is
   imported (step 1 FR-042) before the `watching` line appears.

---

### User Story 3 - troupe's own write-backs are not recorded twice (Priority: P1)

A developer runs `troupe config set` while `watch` is running in another terminal. History shows
exactly the `set`'s events; `watch` does not record the file change the `set` made as a second,
duplicate change.

**Why this priority**: Without it, every `set` under `watch` would corrupt history with duplicates;
the step explicitly requires it.

**Independent Test**: Start `watch`, run `config set` several times (scalars, collections, text
includes, values that add and remove leaves), wait more than 2 seconds after each, and compare
history with the events the same `set`s produce without `watch`.

**Acceptance Scenarios**:

1. **Given** `watch` is running and `a` is 1, **When** the user runs `config set a 2` and waits
   3 seconds, **Then** history gained exactly one event (`set`, `a`, 1 → 2).
2. **Given** `watch` is running and `b` is `[x, y]`, **When** the user runs `config set b '[z]'`,
   **Then** history gained exactly a `set` for `b.0` and a `remove` for `b.1`, in that order, and
   nothing else.
3. **Given** `watch` is running and `prompt` is a text include, **When** the user sets `prompt`,
   **Then** exactly one `set` event for `prompt` is recorded.
4. **Given** `watch` is running, **When** the user makes a hand edit and, right after, runs
   `config set` on another path, **Then** the hand edit is recorded exactly once and the `set`'s
   events exactly once, whichever process notices the hand edit first.

---

### Edge Cases

- **Unloadable configuration while watching** (e.g. the editor saved a half-typed line, an include
  target is missing, or an include cycle was introduced): `watch` writes one message naming the file
  to stderr, records nothing, keeps running, and reconciles once the configuration loads again.
- **Unloadable configuration at start of `watch`**: `watch` exits 4 naming the file, without printing
  the `watching` line (same as every other command).
- **Unloadable configuration for another command**: exit 4 and nothing is recorded, as in step 1.
- **Save by rename**: editors that save by writing a new file and renaming it over the old one are
  detected the same as in-place writes.
- **File deleted and recreated** (including the main file): while it is missing the configuration
  cannot load (handled as above); once it is back, the next reconcile records the net difference.
- **Include removed by a hand edit**: the leaves that came from it get `remove` events; the formerly
  included file is no longer watched, and later edits to it record nothing.
- **Include target changed** (`file:a.yaml` → `file:b.yaml`): leaves that differ get `set`/`remove`
  events; leaves with equal values get none.
- **Scalar replaced by a collection by hand, or the reverse**: the old leaf gets a `remove` event and
  the new leaves get `set` events, as for `set` in step 1.
- **Include targets outside `.troupe/`**: watched like any other included file.
- **Several edits in quick succession**: may be reconciled together; the events then describe the net
  difference between the configuration and the files (an edit undone before it is reconciled records
  nothing).
- **Hand edit that changes a value's type but not its text meaning** (`a: 1` → `a: "1"`): the leaf's
  value differs (integer vs string), so a `set` event is recorded.
- **Command fails after reconciling** (`set` refused with exit 3, or a path error with exit 5): the
  reconcile events stand, as the import does in step 1 (D-2).
- **Signal during a reconcile**: the reconcile's events are recorded all together or not at all.
- **Usage errors for `watch`** (extra arguments, unknown option): exit 2, nothing recorded.

## Requirements *(mandatory)*

### Functional Requirements

Numbering continues from step 1 (FR-001 – FR-044 remain in force) at FR-100.

**watch**

- **FR-100**: The tool MUST provide `troupe config watch [--theatre <dir>]`, with `--theatre`
  defaulting as for every other command; it takes no positional arguments.
- **FR-101**: `watch` MUST load the configuration, import a never-imported theatre (FR-042) and
  reconcile (FR-110) before it announces that it is watching.
- **FR-102**: `watch` MUST print exactly one line `watching <dir>` to stdout, and flush it, only once
  it is able to observe changes to the configuration file and every included file; any change made
  after the line appears MUST be observed.
- **FR-103**: Within 2 seconds of any change to the configuration file or any currently included file
  (YAML or text include, wherever it is located) made after the `watching` line appears, `watch` MUST
  reconcile.
- **FR-104**: After each reconcile, the set of watched files MUST be the configuration file plus every
  file currently reached by includes: includes added by hand edits are followed (and then watched),
  includes removed are no longer watched.
- **FR-105**: `watch` MUST run in the foreground until it receives SIGINT or SIGTERM, then exit with
  code 0. Apart from the one `watching` line, it MUST print nothing to stdout.
- **FR-106**: If the configuration cannot be loaded at start, `watch` MUST exit 4 per step 1 (FR-007,
  FR-008) without printing the `watching` line. If it cannot be loaded during a later reconcile,
  `watch` MUST write one stderr message naming the file, record nothing, keep running, and reconcile
  again on the next change.

**Reconcile**

- **FR-110**: Reconciling MUST compare the leaves of the configuration loaded from the files (step 1
  FR-041) with the leaves of the recorded configuration, and record one event per leaf that differs:
  a `set` event for a leaf whose value changed (`old` the recorded value, `new` the file value) or
  that is new (`old` null); a `remove` event (`new` null) for a recorded leaf that no longer exists.
- **FR-111**: Leaves are equal only if both their type and value are equal (so `1` and `"1"` differ;
  `1` and `1.0` differ).
- **FR-112**: An edit that changes no leaf — formatting, indentation, quoting, comments, blank lines,
  key order, line endings, or switching between block and flow style — MUST record nothing.
- **FR-113**: Includes MUST be followed when reconciling exactly as when loading (step 1 FR-010 –
  FR-012); leaves of an include added by a hand edit MUST appear as `set` events.
- **FR-114**: The events of one reconcile MUST be ordered `set` events in document order of the files,
  then `remove` events in document order of the recorded configuration (same order as step 1 D-3).
- **FR-115**: The events of one reconcile MUST be recorded all together or not at all.
- **FR-116**: A reconcile when nothing differs MUST record nothing.

**Which commands reconcile**

- **FR-120**: `show`, `set` and `watch` MUST reconcile after loading the configuration and importing a
  never-imported theatre, and before doing their own work, so `show` and `set` act on, and history
  records, the files as they are.
- **FR-121**: `history` MUST NOT reconcile; it lists only events already recorded (it still imports a
  never-imported theatre per step 1 FR-042).
- **FR-122**: Reconcile events recorded by a command stand even if the command then fails with exit 3
  or 5. A command that exits 4 records nothing. Usage errors (exit 2) detected before the
  configuration is loaded record nothing.

**troupe's own write-backs**

- **FR-130**: The file changes a `set` makes MUST NOT be recorded again by any reconcile — by `watch`
  or by a later command. A `set` MUST record exactly its own events (step 1 FR-043) whether or not
  `watch` is running.
- **FR-131**: When `watch` and another command run at the same time against the same theatre, every
  change to the files MUST be recorded exactly once: never twice, and never lost. History sequence
  numbers MUST stay contiguous with no duplicates.

### Decisions on open points

Recorded per Constitution Principles V and VI.

- **D-10 Reconcile compares against the recorded configuration.** "The configuration" in the contract
  is the configuration the recorded events describe (the projection), not a copy of the files kept
  elsewhere. This is what makes reconciling after a `set` find nothing to record (FR-130).
- **D-11 `watch` and the theatre directory in its line.** `<dir>` is the theatre directory exactly as
  given (by `--theatre`, or by `TROUPE_THEATRE`); when neither is given it is the absolute path of the
  current directory. Reason: the line then matches what the user typed, and is never a bare `.`.
- **D-12 `watch` reports events only by recording them.** The contract asks for one stdout line; `watch`
  prints no other stdout. Recorded events are visible with `history`. Load problems go to stderr.
- **D-13 `watch` survives a broken file.** Editors save partial or temporarily invalid files; exiting
  on the first one would make `watch` unusable. Conservative choice: report, record nothing, keep
  watching (FR-106). At startup there is nothing yet to keep, so `watch` fails like every other
  command.
- **D-14 Coalescing.** Several edits within the 2-second window may be reconciled together; history
  then records the net difference. The contract asks for reconciliation, not one event per save.
- **D-15 Failed command after reconcile.** The reconcile reflects the files and is true regardless of
  what the command does next, so it stands (FR-122), consistent with step 1 D-2 for import.
- **D-16 Concurrency scope.** `watch` running alongside one other command at a time is in scope
  (FR-131). Two `set`s at the same time, and a hand edit to a file at the same moment a `set` writes
  that same file, remain out of contract (step 1 "concurrent writers").
- **D-17 `watch` writes no configuration file.** `watch` only reads configuration files; it changes
  nothing outside the tool's own state under `.troupe/` (step 1 FR-003).

### Out of contract

In addition to step 1's list: two `set` (or other writing) commands at the same time; a hand edit and
a `set` writing the same file at the same moment; more than one `watch` on the same theatre; the
configuration file switching between `troupe.yml` and `troupe.yaml` while `watch` runs; network or
otherwise non-local file systems where change notification is unreliable.

### Key Entities

- **Recorded configuration (projection)**: the leaves and values the recorded events describe; the
  reference that reconciling compares the files against.
- **Reconcile**: one comparison of files with the recorded configuration, producing zero or more
  `set`/`remove` events recorded together.
- **Watched file set**: the configuration file and every file currently reached by includes; it
  changes as includes are added or removed.
- **Event**: as in step 1 (`seq`, `op`, `path`, `old`, `new`); reconcile events use the existing
  `set` and `remove` operations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-101**: For hand edits to the main file, a nested YAML include and a text include, history
  reflects each changed leaf within 2 seconds of the edit while `watch` runs, in 100% of test runs.
- **SC-102**: Comment-only and formatting-only edits record zero events, both under `watch` and on
  the next command.
- **SC-103**: Across at least 10 consecutive `set` commands made while `watch` runs, history equals
  the history the same commands produce without `watch` — zero duplicate or missing events, sequence
  numbers contiguous.
- **SC-104**: Edits made while nothing ran are reflected by the next `show` or `set`, and are never
  reflected by `history` alone.
- **SC-105**: `watch` exits 0 on SIGINT and on SIGTERM, and its stdout is exactly one `watching <dir>`
  line.
- **SC-106**: Any edit made after the `watching` line appears is reconciled — no edit made after the
  line is missed, in 100% of test runs.

## Assumptions

- Step 1's contract sections, requirements and decisions remain in force except D-1 as noted above.
- Users run on macOS or Linux on local file systems; configurations are small.
- A theatre has at most one `watch` running at a time.
- Hand edits are saved files; unsaved editor buffers are not visible to troupe.
- History needs no field to tell hand edits from `set` commands: the contract asks for `set`/`remove`
  events and does not ask for a source, so none is invented (Principle V).
