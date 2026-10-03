# Data Model: troupe configuration — Step 2

Step 1's data model (`specs/001-config-load-show-set/data-model.md`) is unchanged: the same value
types, `ConfigPath`, `SourceFile`, located node tree, leaves, `LeafEvent` and `TheatreConfig`
aggregate. Step 2 adds no event type and no stored field; it adds the entities below.

## Projection leaves (existing, newly read)

`TheatreConfig.leaves: dict[str, Scalar]` — dotted leaf path → value, in the order leaves were first
recorded. Exposed as `ConfigStore.leaves()`. It is the "configuration" reconcile compares against
(spec D-10).

| Event | Effect on `leaves` |
|---|---|
| `import` / `set` of a new path | appended at the end |
| `set` of an existing path | value replaced, position kept |
| `remove` | entry deleted |

## Reconcile (transient)

Input: the `Loaded` configuration and the store. Output: `list[LeafEvent]`, recorded in one save.

- `set` (old = projection value, or null if absent) for each file leaf that is new or not
  `scalars_equal` to the projection value — in file document order.
- `remove` (new = null) for each projection leaf absent from the files — in projection order.
- Empty list → nothing saved.

Invariant after any successful reconcile or `set`, while the theatre lock is held:
`store.leaves()` equals `leaves(load(theatre).root)` (type-exact, same key set).

## Theatre lock

`<theatre>/.troupe/events.sqlite3.lock` — empty file, created on first use, used only for an exclusive
advisory lock. Holders:

| Command | Held from … to … |
|---|---|
| `show` | before load → after reconcile |
| `history` | before load → after import (if any) |
| `set` | before load → after its events are recorded |
| `watch` | before each load → after that reconcile's events are recorded (not while idle) |

## Watch state (in memory, `watch` process only)

| Field | Meaning |
|---|---|
| `snapshot: dict[Path, bytes \| None]` | For each watched path, the bytes last parsed (or `None` if absent): all files in `Loaded.files` plus both config-name candidates under `.troupe/` |
| `broken: bool` | The last reconcile failed to load; retry on every poll |
| `last_error: str \| None` | Last message written to stderr; an identical message is not repeated |
| `stop: threading.Event` | Set by the SIGINT/SIGTERM handler |

State transitions:

```text
start ──load+import+reconcile ok──▶ watching (print line) ──bytes differ──▶ reconcile
  │                                    ▲                                     │ ok: rebuild snapshot
  └─LoadError → exit 4                 └─────────────────────────────────────┘
                                       watching ◀──ok── broken ◀──LoadError── reconcile
                                                         │ (retry every poll; stderr once per message)
any state ──SIGINT/SIGTERM──▶ finish current reconcile ──▶ exit 0
```
