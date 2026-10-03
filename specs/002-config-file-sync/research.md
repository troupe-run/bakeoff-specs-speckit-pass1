# Research: troupe configuration — keep files and configuration in sync (Step 2)

Each entry gives the decision, why it was made, and what else was considered. Behaviour choices the
contract leaves open are in `spec.md` (D-10 … D-17). This file records the technical choices for step 2
(S-1 … S-9). Step 1's research (`specs/001-config-load-show-set/research.md`, R-1 … R-16, B-1 … B-12)
stays in force. Library facts were checked against the locked versions (eventsourcing 9.5.5,
Python 3.12) on 2026-10-03.

## S-1 Reconcile = diff of file leaves against projection leaves

- **Decision**: `reconcile(loaded, store)` computes `diff_events(store.leaves(), leaves(loaded.root))`
  with the existing step 1 `diff_events` and records the result in one save. `ConfigStore` gains
  `leaves()`, returning the aggregate's `leaves` dict (the projection).
- **Rationale**: The projection is already maintained by every recorded event (import, set, remove);
  comparing against it is exactly "compare the files with the configuration" (spec D-10). Reusing
  `diff_events` keeps one definition of "differs" (type-exact `scalars_equal`, FR-111) and one event
  order (step 1 D-3) — Principle IV. Comparing leaves, not bytes, makes formatting- and comment-only
  edits produce nothing by construction (FR-112).
- **Order of `remove` events**: `diff_events` emits removes in the order of its `before` dict, here the
  projection's insertion order — leaves in the order they were first recorded (import order, then
  newly created leaves appended; a changed leaf keeps its place). Spec FR-114 is worded to match.
- **Atomicity (FR-115)**: `ConfigStore.record` saves all pending aggregate events with one
  `Application.save`, which the SQLite recorder writes in one transaction.
- **Alternatives**: Keep a byte snapshot of the files in `.troupe/` and diff that — duplicates state
  the projection already has, and does not by itself give leaf-level events. Re-run step 1's
  `apply_set` machinery — irrelevant; there is no planned edit to verify.

## S-2 Which commands reconcile, and where

- **Decision**: `open_theatre(theatre, *, reconcile: bool)` in `commands.py` (the existing one place
  that loads + imports) gains the flag. `show`, `set` and `watch` pass `True`; `history` passes
  `False`. On first use it imports and does not reconcile (nothing can differ).
- **Rationale**: One function decides "what every command does before its own work" (Principle IV);
  `history`'s exception (FR-121) is visible at its one call site.
- **Exit-code interplay (FR-122)**: Usage errors from argparse, `ConfigPath.parse` and `parse_value`
  already happen before `open_theatre`, so they record nothing. Reconcile events are saved inside
  `open_theatre`, before the command's own work, so they stand if that work raises exit 3 or 5. A load
  failure raises before the store is touched.

## S-3 Mutual exclusion: one lock file, held across load → write → record

- **Decision**: A new `troupe/config/lock.py` with one context manager `theatre_lock(theatre)` that takes
  an exclusive `fcntl.flock` on `<theatre>/.troupe/events.sqlite3.lock` (constant
  `LOCK_FILENAME = STORE_FILENAME + ".lock"`). Every command holds it from just before loading until it
  has recorded its events: `show`/`history` around `open_theatre`; `set` around `open_theatre` +
  `apply_set` + `store.record`; `watch` around each reconcile only (never while idle).
- **Rationale**: FR-130/FR-131 are race conditions between processes. Without the lock: (a) `watch`
  could load the file a `set` has just written before the `set` has recorded its events, and record
  them again; (b) `watch` and a command could both reconcile the same hand edit. With the lock held
  across "load, compare, write, record", whoever comes second sees a projection that already matches
  the files and records nothing. Blocking `flock` is advisory, released by the kernel if a process dies
  (no stale-lock clean-up), and available on macOS and Linux. The file name starts with
  `STORE_FILENAME`, so it is grouped with the store's own files (and excluded by the test suite's
  snapshot helper like `events.sqlite3-wal`).
- **Opening the lock file**: `os.open(path, O_RDWR | O_CREAT, 0o644)`; on `PermissionError` fall back to
  `O_RDONLY` (flock works on a read-only descriptor on both platforms). If it cannot be opened at all,
  raise `LoadError` naming the lock file (exit 4), consistent with step 1's store errors.
- **Alternatives**: SQLite `BEGIN EXCLUSIVE` on a second connection — the eventsourcing application's own
  connection would then block on its own save (self-deadlock). Ignoring self-written changes by
  remembering the bytes a `set` wrote — fragile (a hand edit with the same bytes, ordering between
  processes) and still leaves race (b). eventsourcing's optimistic concurrency (version conflict) —
  detects a conflicting save but would turn the race into a failed command, not exactly-once.

## S-4 Observing changes: polling the exact bytes that were parsed

- **Decision**: `watch` polls every `POLL_INTERVAL = 0.2` seconds. Its snapshot maps each watched path
  to the bytes last seen (or `None` if missing): every file in `Loaded.files` (the main file and every
  file reached by includes — exactly the files the reconcile parsed, encoded back from their text, which
  is lossless for UTF-8) plus both `CONFIG_NAMES` candidates in `.troupe/`. A poll re-reads those paths;
  any difference triggers a reconcile, after which the snapshot is rebuilt from the new `Loaded`
  (FR-104: added includes become watched, removed ones stop being watched).
- **Why the `watching` line is a true promise (FR-102)**: the snapshot is the bytes the startup reconcile
  actually parsed, taken under the lock. Any change after that — including one made between the
  reconcile and the printing of the line — makes the next poll's bytes differ. Nothing depends on
  modification times, so sub-second edits, same-size edits and coarse file-system timestamps cannot
  hide a change, and save-by-rename (new inode) is seen like an in-place write.
- **Latency**: worst case ≈ one poll interval + lock wait + load time, well under 2 s for small
  configurations (FR-103).
- **Alternatives**: `watchdog`/inotify/FSEvents — a new dependency, macOS FSEvents can coalesce with
  latency, watching scattered include targets outside `.troupe/` means one watch per directory, and the
  "able to observe" moment is harder to establish; it would still need the byte comparison to ignore
  no-op events. mtime/size polling — misses same-size edits within the timestamp granularity.

## S-5 `watch` while the configuration cannot be loaded

- **Decision**: At startup a `LoadError` propagates (exit 4, no `watching` line). After startup, a failed
  reconcile records nothing, writes `troupe: error: <message>` to stderr unless it is identical to the
  previous message, and leaves `watch` in a *broken* state in which it retries the reconcile on every
  poll until one succeeds (then the snapshot is rebuilt and the message memory cleared).
- **Rationale**: In the broken state the set of files that matter is unknown (e.g. the missing include
  target the user is about to create), so retrying each poll is simpler and more certain than guessing
  which paths to watch; loading a small configuration five times a second costs nothing. Suppressing
  repeated identical messages keeps stderr readable (spec FR-106 "one message").
- **Store errors** (e.g. the store is not writable) during a later reconcile are handled the same way.

## S-6 Signals and clean exit

- **Decision**: `watch` installs handlers for SIGINT and SIGTERM first thing, which only set a
  `threading.Event`; the loop waits with `stop.wait(POLL_INTERVAL)` and checks the event between
  reconciles. On stop it returns normally, the CLI writes no further output, and the process exits 0.
- **Rationale**: A reconcile in progress is never interrupted, so its events are saved whole or (on a
  store error) not at all (FR-115); no `KeyboardInterrupt` traceback; exit 0 for both signals (FR-105).
  A signal arriving while blocked on the lock is handled when the lock is granted (PEP 475 retries the
  call after the handler runs); the `set` holding it finishes in well under a second.

## S-7 Printing the `watching` line

- **Decision**: `commands.watch(theatre, display, announce)` takes an `announce: Callable[[str], None]`;
  the CLI passes a function that writes the line as UTF-8 to `sys.stdout.buffer` and flushes. `display`
  is computed in `cli.py` in one function: the `--theatre` argument as given, else `$TROUPE_THEATRE` as
  given, else `str(Path.cwd())` (spec D-11). `watch` returns `""`, so `main()` prints nothing more.
- **Rationale**: Step 1's CLI returns a command's whole stdout at the end; `watch` must write mid-run,
  and the callback keeps output formatting in the CLI layer.

## S-8 Event attribution and concurrent hand edits during a `set`

- **Decision**: No change to `apply_set`. Under the lock, `set` reconciles first, so its `before` leaves
  equal the projection, and the events it records are exactly `diff_events(before, after)`.
- **Consequence**: A hand edit to *another* file made after the `set` loaded but before it wrote is not
  in the `set`'s `after` (computed from the in-memory reload), so the next reconcile records it — once.
  A hand edit to the *same* file at that moment is out of contract (spec D-16).

## S-9 Testing approach

- **Reconcile on commands**: end-to-end tests (real CLI, real files) that edit files between commands and
  compare `history` JSON Lines exactly; comment-/format-only edits leave history byte-identical;
  `history` alone records nothing; reconcile before a failing `set` (exit 3/5) stands.
- **watch**: tests start `troupe config watch --theatre <dir>` with `subprocess.Popen`, read the first
  stdout line with a timeout, edit files (in place and via write-temp-then-`os.replace`), then poll
  `config history` (which never reconciles, so it observes only what `watch` recorded) until a 2-second
  deadline. Every test ends by sending SIGINT or SIGTERM and asserting exit 0 and stdout ==
  `watching <dir>\n`. A pytest fixture guarantees the process is killed on test failure.
- **Edit immediately after the line**: an edit made with no delay after the line is read must be
  recorded within 2 s (the promise, FR-102).
- **Exactly-once**: with `watch` running, run ≥10 `set`s (scalar, collection replace, text include) and
  compare the full history with the same sequence run without `watch` (SC-103). Hand edit immediately
  followed by `set` on another path → each event once.
- **The lock is what makes it work** (Principle II, "break it deliberately"): a test holds
  `theatre_lock` in the test process, makes a hand edit, and asserts `watch` records nothing while the
  lock is held and records the edit within 2 s of release. A unit test wraps `ConfigStore.record` during
  `set` to assert the lock is held (a non-blocking `flock` from another descriptor fails) at the moment
  events are recorded.
- Unit tests for `reconcile` cover: changed, added, removed leaves; type-only change (`1` → `"1"`);
  no-op; event order.
