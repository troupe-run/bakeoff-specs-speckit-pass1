# Data Model: troupe configuration — lineage (Step 4)

Entities from steps 1–3 (theatre, configuration file, include, leaf, projection, reconcile, watched
file set, YAML view) are unchanged. Step 4 adds lineage to every event.

## Actor

| Field | Type | Rules |
|---|---|---|
| `kind` | `"human"` \| `"agent"` \| `"unknown"` | |
| `id` | string \| null | non-empty when given by `TROUPE_ACTOR`; the login name or null when `TROUPE_ACTOR` is unset; always null for `unknown` |

Sources (FR-310, FR-320 – FR-322):

| Situation | Actor |
|---|---|
| import, reconcile (by any command or `watch`) | `{"kind": "unknown", "id": null}` (`UNKNOWN_ACTOR`) |
| `set`'s own events, `TROUPE_ACTOR=human:<id>` / `agent:<id>` | `{"kind": "human"/"agent", "id": "<id>"}` (id = text after the first `:`, exact) |
| `set`'s own events, `TROUPE_ACTOR` unset | `{"kind": "human", "id": <login name or null>}` |
| `TROUPE_ACTOR` set to anything else (incl. `""`, `human:`) | no actor: every command exits 2 before loading |

## Lineage

One value per **unit** (an import, a reconcile, or a `set`'s own change), stamped on each of the
unit's events.

| Field | Type | Rules |
|---|---|---|
| `actor` | Actor | see above |
| `via` | `"import"` \| `"file"` \| `"cli"` | import → `import`; reconcile → `file`; `set` → `cli` |
| `at` | string | `YYYY-MM-DDTHH:MM:SS.ffffffZ`, UTC, taken once when the unit begins (research L-4) |
| `reason` | string \| null | `set --reason TEXT` → TEXT exactly (`""` allowed); otherwise null; always null for `import`/`file` |
| `change` | string | random UUID string, fresh per unit (research L-3) |

Invariants: all events of a unit have identical lineage; distinct units have distinct `change`;
lineage never changes once recorded.

## Event (`LeafChanged`, extended)

| Field | Type | Since |
|---|---|---|
| `op` | `import` \| `set` \| `remove` | step 1 |
| `path` | dotted string | step 1 |
| `old`, `new` | scalar \| null | step 1 |
| `actor_kind`, `actor_id`, `via`, `at`, `reason`, `change` | string \| null | step 4 |

`seq` is the event's position in the stream (from 1), as before.

## HistoryRecord / history line

`HistoryRecord(seq, op, path, old, new, lineage)`; printed by `history` as one JSON object per line:

```json
{"seq": 4, "op": "set", "path": "a", "old": 1, "new": 2, "actor": {"kind": "agent", "id": "coder-7"}, "via": "cli", "at": "2026-10-04T09:15:02.123456Z", "reason": "raise for load test", "change": "6f1c…"}
```

## Units recorded by one invocation

```text
set PATH VALUE on a theatre:
  never imported → [import unit: via import]          (no reconcile: step 1 FR-042)
  imported       → [reconcile unit: via file]          (only if something differs)
  then           → [set unit: via cli, actor, reason]  (only if something changes)
get / show       → import unit or reconcile unit, as above
history          → import unit if never imported; nothing otherwise
watch            → import unit or reconcile unit at start; one reconcile unit per later reconcile
```
