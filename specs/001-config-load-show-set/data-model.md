# Data Model: troupe configuration — Step 1

## Value types

- **Scalar** = `str | int | float | bool | None` (YAML 1.2 core schema, research R-2). Equality
  between scalars is type-exact (`1`, `1.0` and `true` are all different).
- **Value** = `Scalar | list[Value] | dict[str, Value]`.

## ConfigPath

- `segments: tuple[str, ...]` from splitting on `.`; a segment of only ASCII digits is an index.
- Validation: non-empty, no empty segment → otherwise usage error (exit 2).
- `dotted` form is the canonical string used in events and messages.

## SourceFile

A file read from disk.

| Field | Meaning |
|---|---|
| `path` | Absolute path |
| `text` | Decoded UTF-8 text, line endings preserved |
| `newline` | `"\r\n"` if the first line ending is CRLF, else `"\n"` (spec D-6) |
| `kind` | `yaml` (name ends `.yml`/`.yaml`) or `text` |

## Located node tree (result of loading)

Every node of the effective configuration remembers where its bytes are.

- **LocatedScalar**: `value: Scalar`, `file: SourceFile`, `span: (start, end)`, `style` (plain,
  `'`, `"`, `|`, `>`), `in_flow: bool`.
- **LocatedMapping**: `entries: list[(key: LocatedScalar, value: LocatedNode)]`, `file`, `flow: bool`,
  `span`.
- **LocatedSequence**: `items: list[LocatedNode]`, `file`, `flow: bool`, `span`.
- **TextInclude**: a string leaf whose value is the target's text. `include: LocatedScalar` (the
  `file:` string), `target: SourceFile`.
- **YAMLInclude marker**: when a node came from a `file:` string to a YAML file, the embedded root
  node carries `included_by: LocatedScalar` so rule 4 (exit 3) can be detected.

Validation during load (exit 4 on failure, message names the file): config file found exactly once
(FR-002); every file parses as a single YAML document; main file root is a mapping or empty (D-5);
include target exists and is a regular file; no file appears twice on the current include chain
(cycle).

## Leaves

`leaves(tree) -> dict[str, Scalar]` — ordered by document order with includes expanded in place;
keys are dotted paths (`list.0`); text includes are string leaves; empty collections contribute
nothing (B-12).

## Edit (internal)

- `Splice(start, end, replacement)` on one `SourceFile`.
- `EditPlan(file, splices, expected_value)` — applied to a copy, re-loaded and verified (R-7)
  before writing.

## Event store

- **Aggregate** `TheatreConfig`, id = `uuid5(NAMESPACE_URL, "troupe:theatre-config")` (one per store,
  and the store is per theatre).
  - State: `leaves: dict[str, Scalar]` — the projection.
  - Event `LeafChanged(op: "import" | "set" | "remove", path: str, old: Scalar, new: Scalar)`.
    Applying: `remove` deletes `path`; otherwise sets `leaves[path] = new`.
- **Lifecycle**:
  1. *Not imported*: no aggregate in the store.
  2. *Imported*: created, then one `import` event per leaf (old null) saved in one `save()`.
  3. Each `set` that changes leaves saves its `set` events then its `remove` events (D-3) in one
     `save()` after the file write.
- **History record** (output): `{"seq", "op", "path", "old", "new"}` where `seq` is the 1-based
  position of the event among the aggregate's `LeafChanged` events.

## Event derivation for `set`

Given `before = leaves(load())` and `after = leaves(load with edited text)`:

- for `p` in `after` order: if `p` not in `before` or `before[p]` ≠ `after[p]` (type-exact) →
  `set(p, before.get(p), after[p])`;
- for `p` in `before` order: if `p` not in `after` → `remove(p, before[p], None)`.
