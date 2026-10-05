# Data Model: troupe configuration — include overrides (Step 5)

Step 1–4 entities (`specs/00{1,2,3,4}-*/data-model.md`) stay in force. Step 5 changes only the
located tree the loader builds; events, lineage and the store are unchanged.

## Located tree (`src/troupe/config/tree.py`)

| Field | On | Meaning | New? |
|---|---|---|---|
| `file`, `node`, `in_flow`, `entries` / `items` | all | as before; for a merged mapping, `file`/`node` are the included (base) mapping's | — |
| `included_by: LocatedScalar \| None` | include roots | the include string: the scalar-form value, or the `$ref` value in mapping form | meaning widened |
| `include_site: LocatedMapping \| None` | include roots in mapping form | the raw mapping-form mapping `M` as written in the including file (entries include `$ref`; `$ref` not followed) | NEW |
| `overrides: LocatedMapping \| None` | `LocatedMapping` | the override mapping merged into this one (`M` at a root; the nested override mapping below); `None` = not merged | NEW |

Derived: `written_as(node) = include_site or included_by or None` — the node that represents the
whole value in the including file.

## Merge (`loader`)

```text
merge(base: LocatedMapping, over: entries of M without $ref, overrides=M) -> LocatedMapping
  entries = []
  for (k, v) in base.entries:
      if k in over:
          ov = over[k]
          if v and ov are both LocatedMapping: entries += (k_override, merge(v, ov.entries, overrides=ov))
          else:                                 entries += (k_override, ov)          # replaces
      else:                                     entries += (k, v)
  entries += override-only entries, in written order                               # D-46
```

Keys of overridden entries are the override's key scalars (their file is the including file), so a
`set` of that key's value finds the right line.

## Validation (exit 4 unless noted)

| Condition | Result |
|---|---|
| `$ref` value is not a string starting with `file:` | ordinary mapping (D-42) |
| `$ref` → non-YAML target, no other keys | `TextInclude` (FR-402) |
| `$ref` → non-YAML target, other keys | exit 4 naming the including file (FR-403) |
| `$ref` → YAML target whose content is not a mapping, other keys | exit 4 (D-43) |
| `$ref` → missing target / cycle | exit 4 as step 1 (FR-407) |
| path segment `$ref` | exit 5 (FR-405) |

## New-key placement (`edit/override.py`)

```text
Site = (root: Located, root_path: ConfigPath)            # include root and where it is
site_of: dict[file path, Site]   — set on entering an include root (key: target file),
                                   cleared on entering a list item
own(X) = file of X's innermost override if X is merged (D-48), else X.file
if own(X) is the main file or own(X) not in site_of: write in own(X)     (FR-420, FR-424)
else: write override at site_of[own(X)] with Q = path(root → X) + new segments   (FR-421)
      mapping form: walk Q through plain override mappings in M, then _new_key   (D-47 → exit 3)
      scalar form:  convert (block key / block list item / flow), then add Q    (FR-422, FR-423, D-41)
```

## Events

Unchanged (step 1 FR-041 – FR-044, step 4 lineage). Leaves are those of the merged tree, so an added
override records one `set` event per new leaf; converting to mapping form records nothing (FR-440).
