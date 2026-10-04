# Feature Specification: troupe configuration — lineage (Step 4)

**Feature Branch**: `main` (delivery is on `main`; no feature branch)

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Step 4 — lineage. Configuration changes in troupe are made by people
and by AI agents. We need a history we can audit: for any setting, who changed it (a human or an
agent, and which one), how (CLI, file edit, or first import), when (UTC timestamp), why (optional
`troupe config set --reason "…"`), and what else changed with it (one change id per command). Where
something is genuinely unknown, say so explicitly rather than guessing. Lineage must survive restarts
and be readable through `troupe config history`. Contract sections added: Lineage."

The product owner's contract section **Lineage** is normative, together with the sections already in
force from steps 1–3 (see `specs/001-config-load-show-set/spec.md`,
`specs/002-config-file-sync/spec.md`, `specs/003-config-get-show/spec.md`). The requirements below
restate it so each rule is individually testable; where this spec and the contract appear to differ,
the contract wins and this spec is corrected. Choices the contract leaves open are recorded under
**Decisions on open points**.

Contract text (verbatim):

> Every `history` event also has:
> - `"actor"`: `{"kind": "human" | "agent" | "unknown", "id": <string or null>}`
> - `"via"`: `"import"` | `"cli"` | `"file"`
> - `"at"`: RFC 3339 UTC timestamp ending in `Z`
> - `"reason"`: the text given with `set --reason TEXT`, else `null`
> - `"change"`: a string identifying the command (or file reconcile, or import) that produced the
>   event; every event one command produces has the same `change`, and no two commands share one
>
> A CLI command's actor comes from the `TROUPE_ACTOR` environment variable, `human:<id>` or
> `agent:<id>` (anything else → exit 2); unset → `{"kind": "human", "id": <login name>}`. Imports and
> file-originated events have actor `{"kind": "unknown", "id": null}`.

**What step 4 changes from steps 1–3.** Every `history` line gains five fields (FR-300). `set` gains
an option `--reason TEXT` (FR-330). Every `config` command reads `TROUPE_ACTOR` and refuses an
invalid value with exit 2 (FR-320 – FR-323). Step 2's closing assumption ("History needs no field to
tell hand edits from `set` commands") is superseded: `via` now tells them apart. Nothing else about
loading, writing back, reconciling, `get`, `show` or `watch` changes.

## User Scenarios & Testing *(mandatory)*

The users are the people who review and audit a theatre's configuration — developers, and the
operators of the AI agents that also change it. When a setting has a surprising value, they want to
know who set it, how, when and why, and which other settings were changed in the same action; and
they want the record to admit what it does not know instead of inventing an author.

### User Story 1 - Know who changed a setting, and how (Priority: P1)

An auditor lists a setting's history and sees, for each change, whether it was made by a named human,
a named agent, or an unknown author (a hand edit or the first import), and whether it came through the
command line, a file edit, or the import.

**Why this priority**: "Who changed it?" is the core of auditing changes made by both people and
agents; without it the other fields have no context.

**Independent Test**: On a fresh theatre, run `config history` (import), `config set` with
`TROUPE_ACTOR` unset, `human:alice` and `agent:coder-7`, make a hand edit followed by `config get`,
then compare each `config history` line's `actor` and `via` with the expected values.

**Acceptance Scenarios**:

1. **Given** a theatre never used before with leaf `a: 1`, **When** the user runs `config history`,
   **Then** the `import` event has `"actor": {"kind": "unknown", "id": null}` and `"via": "import"`.
2. **Given** an imported theatre and `TROUPE_ACTOR=agent:coder-7`, **When** the user runs
   `config set a 2`, **Then** the `set` event has `"actor": {"kind": "agent", "id": "coder-7"}` and
   `"via": "cli"`.
3. **Given** `TROUPE_ACTOR=human:alice`, **When** the user runs `config set a 3`, **Then** the event's
   actor is `{"kind": "human", "id": "alice"}`.
4. **Given** `TROUPE_ACTOR` is unset and the command runs as login name `dev`, **When** the user runs
   `config set a 4`, **Then** the event's actor is `{"kind": "human", "id": "dev"}`.
5. **Given** an imported theatre, **When** the user edits `a: 4` to `a: 5` in their editor and then runs
   `config get a` with `TROUPE_ACTOR=agent:coder-7`, **Then** the reconcile `set` event has
   `"actor": {"kind": "unknown", "id": null}` and `"via": "file"` — the agent that ran `get` is not
   credited with the hand edit.
6. **Given** `watch` is running, **When** the user edits a value by hand, **Then** the recorded event
   has actor `{"kind": "unknown", "id": null}` and `"via": "file"`.
7. **Given** `TROUPE_ACTOR` is `robot:x`, `human`, `agent:`, `Human:alice` or the empty string,
   **When** the user runs any `config` command, **Then** the exit code is 2, stdout is empty, stderr
   names `TROUPE_ACTOR`, and nothing is recorded or written.

---

### User Story 2 - See which settings changed together (Priority: P1)

An auditor sees that several history lines share one `change` value and so were made by one action —
for example a `set` that replaced a list, or one hand edit that touched several keys — and can tell
them apart from the next action.

**Why this priority**: A multi-value change is only reviewable as a unit if its events can be grouped;
it is the other half of the contract's new information.

**Independent Test**: Run commands that produce several events each (import of several leaves; a
`set` replacing a list; a hand edit of two keys reconciled by `show`; a `set` preceded by an
unreconciled hand edit on a never-imported theatre) and check that `change` values are equal within
each unit and different between units.

**Acceptance Scenarios**:

1. **Given** a theatre never used before with leaves `a: 1` and `b: [x, y]`, **When** the user runs
   `config history`, **Then** the three `import` events share one `change` value.
2. **Given** `b: [x, y]`, **When** the user runs `config set b '[z]'`, **Then** the `set` event for
   `b.0` and the `remove` event for `b.1` share one `change` value, different from the import's.
3. **Given** an imported theatre, **When** the user edits two keys by hand and runs `config show`,
   **Then** the two reconcile events share one `change` value.
4. **Given** an imported theatre with an unreconciled hand edit of `a`, **When** the user runs
   `config set b 5`, **Then** the reconcile event for `a` and the `set` event for `b` have different
   `change` values (the hand edit and the command are different actions).
5. **Given** two separate `config set` commands that each record events, **When** the user lists
   history, **Then** their `change` values differ, even if they set the same path to values that
   alternate.
6. **Given** history listed with a PATH filter, **When** a unit's events are partly outside the
   filter, **Then** the printed events keep their `change` value (the value is the same as in the
   unfiltered listing).

---

### User Story 3 - Know when and why (Priority: P2)

A developer or agent changing a setting gives a reason (`config set --reason "…"`); an auditor later
sees the reason and the UTC time of every change.

**Why this priority**: Time and reason complete the audit trail, but are only useful once who and
what-else are recorded.

**Independent Test**: Note the UTC time before and after each command; run `config set` with and
without `--reason`; check `at` lies between the two times, ends in `Z`, parses as RFC 3339, and
`reason` is the given text or null.

**Acceptance Scenarios**:

1. **Given** an imported theatre, **When** the user runs
   `config set a 2 --reason "raise for load test"`, **Then** the event has
   `"reason": "raise for load test"`.
2. **Given** an imported theatre, **When** the user runs `config set a 3` without `--reason`, **Then**
   the event has `"reason": null`; import and reconcile events always have `"reason": null`.
3. **Given** `config set b '[z]' --reason "trim"` replacing `[x, y]`, **When** history is listed,
   **Then** both events of that `set` carry `"reason": "trim"`.
4. **Given** an unreconciled hand edit, **When** the user runs `config set c 1 --reason "x"`, **Then**
   the reconcile event's reason is null and only the `set` event's reason is `"x"`.
5. **Given** any recorded event, **When** history is listed, **Then** `at` is an RFC 3339 UTC
   timestamp ending in `Z`, no earlier than the start and no later than the end of the command (or
   `watch` reconcile) that recorded it, and every event of one `change` has the same `at`.
6. **Given** `--reason` given to `get`, `show`, `history` or `watch`, or `--reason` with no text,
   **When** the command runs, **Then** the exit code is 2 and nothing is recorded.

---

### User Story 4 - The audit trail survives restarts (Priority: P1)

Lineage is recorded with the events, so a later, separate command — after a reboot, or in a new
terminal with a different `TROUPE_ACTOR` — lists exactly the same lineage for earlier events.

**Why this priority**: An audit trail that is lost or rewritten is not an audit trail.

**Independent Test**: Record events with several actors and reasons, then run `config history` in new
processes with `TROUPE_ACTOR` unset and set to a different actor, and check every earlier line is
byte-for-byte identical.

**Acceptance Scenarios**:

1. **Given** events recorded by earlier commands, **When** `config history` runs in a new process,
   **Then** each earlier event's `actor`, `via`, `at`, `reason` and `change` are unchanged.
2. **Given** events recorded with `TROUPE_ACTOR=agent:a`, **When** history is listed with
   `TROUPE_ACTOR=human:b`, **Then** the earlier events still show `agent:a`'s actor.

---

### Edge Cases

- **Actor ids with unusual text**: everything after the first `:` is the id, kept exactly
  (`agent:team:coder` → id `team:coder`; spaces and non-ASCII kept). An empty id (`human:`) → exit 2.
- **`TROUPE_ACTOR` set to the empty string** → exit 2 (it is set, and is neither form).
- **`TROUPE_ACTOR` invalid on a command that would record nothing** (`history`, a `get` with nothing
  to reconcile): still exit 2 — the variable is checked before anything else.
- **Login name cannot be determined** with `TROUPE_ACTOR` unset: actor is
  `{"kind": "human", "id": null}` — the author is a human, but which one is unknown; no name is guessed.
- **A `set` that changes nothing** (with or without `--reason`): no event is recorded, so its reason
  and actor appear nowhere.
- **A command whose reconcile records events and then fails** (exit 3 or 5): the reconcile events stand
  with their own lineage (`via` `file`, unknown actor); the failed command's own events do not exist.
- **First command on a theatre with `TROUPE_ACTOR` set**: the import events still have the unknown
  actor and `via` `import`.
- **`set` with `--reason` while `watch` runs**: exactly the `set`'s events, with its actor, reason and
  `change`; the write-back records nothing (step 2 FR-130).
- **Reason text containing newlines, quotes or non-ASCII**: kept exactly; history prints it as a valid
  JSON string.
- **`--reason ""`**: the reason was given, so `reason` is the empty string `""`, not null.
- **Several hand edits reconciled together** (step 2 D-14): they share one `change` and one `at`.
- **A reconcile, import or command that records no events**: no `change` value appears for it.
- **Clock set to a non-UTC time zone**: `at` is still in UTC with a `Z` suffix.

## Requirements *(mandatory)*

### Functional Requirements

Numbering continues from step 3 (FR-001 – FR-044, FR-100 – FR-131, FR-200 – FR-226 remain in force) at
FR-300.

**History fields**

- **FR-300**: Every line `config history [PATH]` prints MUST contain, in addition to step 1's `seq`,
  `op`, `path`, `old` and `new`, the fields `actor`, `via`, `at`, `reason` and `change`, in that order
  after `new`.
- **FR-301**: `actor` MUST be a JSON object with exactly the keys `kind` (`"human"`, `"agent"` or
  `"unknown"`) and `id` (a string, or null).
- **FR-302**: `via` MUST be `"import"` for events recorded by importing a theatre (step 1 FR-042),
  `"file"` for events recorded by reconciling (step 2 FR-110, whether triggered by a command or by
  `watch`), and `"cli"` for the events a `set` records for its own change (step 1 FR-043).
- **FR-303**: `at` MUST be an RFC 3339 timestamp in UTC ending in `Z`, recording when the event was
  recorded; all events of one `change` MUST have the same `at`.
- **FR-304**: `reason` MUST be the exact text given with `set --reason TEXT` on events with `via`
  `"cli"`, and null when no reason was given and on every `import` and `file` event.
- **FR-305**: `change` MUST be a non-empty string. All events recorded by one import share one
  `change`; all events recorded by one reconcile share one `change`; all events a `set` records for its
  own change share one `change`. No two of these units — in the same theatre's history — share a
  `change` value.
- **FR-306**: The lineage of an event MUST NOT change after it is recorded: every later listing, by any
  process, with any `TROUPE_ACTOR`, MUST print the same values. Lineage MUST be persisted with the
  events under `<dir>/.troupe/` (step 1 FR-003, FR-040).

**Actors**

- **FR-310**: Events with `via` `"import"` or `"file"` MUST have actor `{"kind": "unknown", "id": null}`.
- **FR-311**: Events with `via` `"cli"` MUST have the actor of the command that recorded them (FR-320 –
  FR-322).

**`TROUPE_ACTOR`**

- **FR-320**: When `TROUPE_ACTOR` is `human:<id>` or `agent:<id>` with a non-empty `<id>`, the command's
  actor MUST be `{"kind": "human" | "agent", "id": <id>}`, where `<id>` is everything after the first
  `:`, kept exactly. The prefixes are case-sensitive.
- **FR-321**: When `TROUPE_ACTOR` is unset, the command's actor MUST be
  `{"kind": "human", "id": <login name>}`, the login name of the user running the command; if no login
  name can be determined, `id` MUST be null.
- **FR-322**: When `TROUPE_ACTOR` is set to any other value (including the empty string and an empty
  `<id>`), every `config` command (`get`, `show`, `set`, `history`, `watch`) MUST exit 2, with empty
  stdout and a stderr message naming `TROUPE_ACTOR`.
- **FR-323**: `TROUPE_ACTOR` MUST be checked before the configuration is loaded, so an exit 2 for it
  records nothing (no import, no reconcile) and changes no file.

**`set --reason`**

- **FR-330**: `config set PATH VALUE` MUST accept an optional `--reason TEXT`; TEXT is recorded as
  given (FR-304). `--reason` without TEXT MUST exit 2.
- **FR-331**: `--reason` MUST apply only to the events the `set` records for its own change, not to
  import or reconcile events recorded by the same invocation.
- **FR-332**: Commands other than `set` MUST NOT accept `--reason` (exit 2 as an unknown option).

### Decisions on open points

Recorded per Constitution Principles V and VI.

- **D-30 One invocation, up to three changes.** The contract says a `change` identifies "the command
  (or file reconcile, or import)". A `set` invocation may first import a never-imported theatre and/or
  reconcile hand edits before its own change (steps 1 and 2). These are separate units with separate
  `change` values: the import and the reconcile were not made by the command's actor and have their own
  `via` and actor (FR-310), so grouping them with the `set` would attribute a hand edit to the CLI
  user. "Every event one command produces" is read as the events of the command's own change.
- **D-31 `TROUPE_ACTOR` is checked by every command.** The contract makes it "a CLI command's actor"
  and says anything else exits 2, without limiting it to `set`. Checking it everywhere means an agent
  learns of a misconfigured identity on its first command, not on its first write — the conservative
  choice.
- **D-32 Empty values are invalid.** `TROUPE_ACTOR=""` and `human:` / `agent:` (empty id) are neither
  "unset" nor `human:<id>` / `agent:<id>` with an id, so they exit 2 rather than silently falling back
  to the login name or recording an empty id.
- **D-33 Id text is kept exactly.** Everything after the first `:` is the id, with no trimming or case
  folding, so an audit shows exactly what the caller declared.
- **D-34 Unknown login name.** If the login name cannot be determined, `id` is null rather than a guess
  (e.g. a numeric user id or `"unknown"`), following "say so explicitly rather than guessing".
- **D-35 One time per change.** All events of one `change` share one `at`, the moment the change is
  recorded (they are recorded together, step 2 FR-115). The contract fixes the format but not the
  precision; fractional seconds may appear. `at` reports the system clock and is not promised to
  increase with `seq` if the clock is moved back.
- **D-36 `--reason ""` is a given reason.** The contract says "the text given"; an empty text was given,
  so it is recorded as `""`.
- **D-37 `change` values are opaque.** The contract asks only that they identify a unit uniquely; their
  form is not part of the contract, and users MUST NOT rely on it beyond equality.
- **D-38 Field order.** Lineage fields follow step 1's fields in the contract's order (FR-300), so
  existing consumers reading by key are unaffected and lines stay readable.

### Out of contract

In addition to the lists of steps 1–3: event stores recorded before step 4 (their events carry no
lineage; how they would be listed is not defined, and a theatre's store is expected to be created by a
step 4 build); verifying that `TROUPE_ACTOR` tells the truth (it is a declaration, not
authentication); an actor or reason for hand edits (an editor gives troupe no author).

### Key Entities

- **Event**: as in steps 1–2 (`seq`, `op`, `path`, `old`, `new`), now with lineage.
- **Lineage**: the immutable facts recorded with an event — actor, via, at, reason, change.
- **Actor**: who made a change — kind (`human`, `agent`, `unknown`) and an id or null.
- **Change**: one unit of recording — an import, a reconcile, or a `set`'s own change — identified by
  a value shared by all its events and by no other unit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-301**: For every way an event is recorded (import, reconcile by a command, reconcile by `watch`,
  `set`), 100% of history lines carry all five lineage fields with the values FR-300 – FR-311 require.
- **SC-302**: Across at least 10 consecutive commands, each recording one or more events, the `change`
  values group events exactly by unit: equal within each unit, distinct between units, zero exceptions.
- **SC-303**: Every invalid `TROUPE_ACTOR` form listed in the edge cases yields exit 2 on every `config`
  command, with zero events recorded and zero file bytes changed.
- **SC-304**: History listed in a new process, with a different `TROUPE_ACTOR`, is byte-for-byte
  identical for all previously recorded events.
- **SC-305**: An auditor can answer who, how, when, why and what-else for any setting from
  `config history PATH` alone, with no other source.
- **SC-306**: No event credits a named human or agent with a change they did not make through the CLI:
  every `import` and `file` event has the unknown actor.

## Assumptions

- Steps 1–3's contract sections, requirements and decisions remain in force, except step 2's closing
  assumption about a source field, as noted above.
- `TROUPE_ACTOR` is set by whoever launches a human's or an agent's session; troupe trusts it.
- The system clock is reasonably accurate; troupe does not correct it.
- Users run on macOS or Linux, where a login name is normally available.
