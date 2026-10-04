# Research: troupe configuration — lineage (Step 4)

Each entry gives the decision, why it was made, and what else was considered. Behaviour choices the
contract leaves open are in `spec.md` (D-30 … D-38). This file records the technical choices for step 4
(L-1 … L-8). Research from steps 1–3 (R-*, B-*, S-*, G-*) stays in force. Library behaviour was checked
against the locked `eventsourcing` 9.5.5 on 2026-10-04.

## L-1 Lineage is stored in the existing `LeafChanged` event

- **Decision**: `TheatreConfig.change` (the `@event("LeafChanged")` method) gains the arguments
  `actor_kind`, `actor_id`, `via`, `at`, `reason`, `change` (all `str` or `None`). `eventsourcing`
  persists every argument of a decorated method in the stored event and replays them when the
  aggregate is rebuilt, so lineage survives restarts with no new table or file (FR-306). The applied
  method appends them to the `HistoryRecord` it already builds.
- **Rationale**: One stream, one event type, one place that turns events into history (Principle IV).
  The event store is already the constitution-mandated home of history; lineage is part of each event's
  facts and must be exactly as durable and atomic as the event itself.
- **Alternatives**: A side table keyed by `seq` — two writes that could disagree; a second event type
  per unit ("ChangeStarted") — complicates replay and `history` filtering for no gain.

## L-2 One `Lineage` value per unit, created where the unit is recorded

- **Decision**: New module `config/lineage.py` holds `Actor` (kind, id), `Lineage` (actor, via, at,
  reason, change) and the constructors `Lineage.begin(actor, via, reason=None)` (fresh `change` and
  `at`) plus the constants `UNKNOWN_ACTOR`. `ConfigStore.import_leaves(leaves, lineage)` and
  `ConfigStore.record(events, lineage)` stamp every event of the call with the one lineage. Callers:
  `open_theatre` creates `Lineage.begin(UNKNOWN_ACTOR, "import")` for the import and
  `Lineage.begin(UNKNOWN_ACTOR, "file")` for the reconcile; `set_value` creates
  `Lineage.begin(actor, "cli", reason)` for its own events.
- **Rationale**: Each `store` call already saves one unit atomically (step 2 FR-115), so "one call, one
  lineage" gives FR-303 (same `at`) and FR-305 (same `change`) by construction. The mapping
  "import/file → unknown actor" lives in `open_theatre`, the single place both are recorded (FR-310).
  `record` returns early on an empty list, so a unit with no events leaves no trace.
- **Alternatives**: Pass lineage per event — allows a unit with mixed lineage by mistake.

## L-3 `change` is a random UUID (version 4) as a string

- **Decision**: `change = str(uuid.uuid4())`.
- **Rationale**: Unique across processes without coordination (a `set` and `watch` may record at
  nearly the same moment; the theatre lock already serialises them, but uniqueness does not depend on
  it). Opaque, as spec D-37 requires. 122 random bits make a collision within one history negligible.
- **Alternatives**: A counter stored in the aggregate — needs a read-modify-write and would let users
  read meaning into it; `seq` of the unit's first event — not known before saving and empty units have
  none; timestamp-based ids — can collide when the clock is moved back.

## L-4 `at` is captured once per unit, in UTC, with microseconds

- **Decision**: `at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")`, taken in `Lineage.begin`,
  i.e. immediately before the unit's events are computed and saved — inside the command's run, so it
  lies between the command's start and end (spec US3 scenario 5). The format function is one named
  function `format_at` in `lineage.py`.
- **Rationale**: RFC 3339 with a `Z` suffix as the contract requires (`isoformat()` would give
  `+00:00`). Microseconds keep successive units distinguishable. Stored as the formatted string, so
  `history` prints exactly what was recorded (FR-306).
- **Alternatives**: `eventsourcing`'s own per-event `timestamp` — differs between events of one save,
  violating FR-303, and its format is the library's, not the contract's.

## L-5 `TROUPE_ACTOR` is parsed once in the CLI, before any command runs

- **Decision**: `lineage.actor_from_env(environ) -> Actor` implements FR-320 – FR-322: unset → human
  with `login_name()`; `human:<id>` / `agent:<id>` with non-empty id (split on the first `:`, exact,
  case-sensitive) → that actor; anything else → `UsageError` naming `TROUPE_ACTOR` and the value
  (exit 2). `cli.run` calls it right after argument parsing and before dispatch, for every subcommand,
  and passes the actor to `commands.set_value` (FR-323, spec D-31). The environment variable name is
  the constant `ACTOR_ENV` in `lineage.py`.
- **Rationale**: Argument parsing does not touch the theatre, so checking right after it guarantees
  nothing is loaded, imported, reconciled or written when the actor is invalid. One function decides
  validity (Principle IV).
- **Alternatives**: Check only in `set` — rejected by spec D-31.

## L-6 The login name is `getpass.getuser()`, else null

- **Decision**: `login_name() -> str | None` returns `getpass.getuser()`, and `None` if it raises
  (`OSError`, or `KeyError` when the uid has no passwd entry), or returns an empty string (spec D-34).
- **Rationale**: `getpass.getuser()` is the standard way to get the login name on macOS and Linux: it
  reads `LOGNAME`, `USER`, `LNAME`, `USERNAME`, then the password database. `os.getlogin()` needs a
  controlling terminal and fails for agents and CI runs. Tests set `LOGNAME` to a known value to check
  FR-321, and remove all four variables and run under a uid without a passwd entry only where the
  environment allows (otherwise that path is covered by a unit test that injects the failure).
- **Alternatives**: `pwd.getpwuid(os.getuid())` alone — ignores `LOGNAME`, which is how the system
  reports the login name of a session.

## L-7 `history` prints the lineage fields after `new`, actor as a nested object

- **Decision**: `commands.history` builds each entry as
  `{seq, op, path, old, new, actor: {kind, id}, via, at, reason, change}` and dumps it with the existing
  `json.dumps(..., ensure_ascii=False)` (spec D-38). Reasons with newlines, quotes or non-ASCII are
  therefore valid JSON strings.
- **Rationale**: Existing keys keep their order and spelling; consumers reading by key are unaffected.

## L-8 Stores recorded before step 4 are not migrated

- **Decision**: No defaults are given to the new event arguments. A store written by steps 1–3 is out
  of contract (spec "Out of contract"); the plan adds no migration and no inferred lineage.
- **Rationale**: Principle V (invent nothing) and the spec's "say so explicitly rather than guessing":
  inferring `via` for old `set` events (CLI or hand edit?) is impossible. Behaviour on such a store
  is undefined and untested; no code is added for it (Principle IV: build for the current stage).
- **Alternatives**: Defaults `unknown`/`null` — would print a `via` that might be false.
