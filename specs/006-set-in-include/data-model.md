# Data Model: troupe configuration — `set --in-include` (Step 5, CR-B)

CR-A's data model (`specs/005-include-overrides/data-model.md`) stays in force. CR-B adds one field
and one input.

## Located tree

| Field | On | Meaning |
|---|---|---|
| `base: LocatedMapping \| None` | merged `LocatedMapping` | the included mapping before the overrides were merged in (its `entries` are only that file's); `None` when not merged |

Derived: `shared_part(X)` = follow `base` from X while the mapping is merged; the result is a plain
mapping in an included file.

## `set` input

| Input | Values | Default |
|---|---|---|
| `in_include` | `true` when `--in-include` is given | `false` |

## New-key placement (extends CR-A's)

```text
if in_include:
    target = shared_part(X) if X is merged else X          # step 1 rule, D-51
    _new_key(target, …)                                     # step 1 layout; content identity
else:
    CR-A placement (override at the include site, or in place)
```

Existing values, appends and keys in list items never reach this function, so the flag does not
affect them (D-50).
