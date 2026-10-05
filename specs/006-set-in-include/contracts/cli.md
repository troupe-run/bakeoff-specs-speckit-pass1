# CLI Contract: `troupe config` (Step 5, CR-B additions)

The contracts of steps 1–4 and CR-A (`specs/005-include-overrides/contracts/cli.md`) stay in force.

## Invocation

```text
uv run troupe config set PATH VALUE [--in-include] [--reason TEXT] [--theatre DIR]
```

- `--in-include` is a flag (no value) of `set` only; it may appear anywhere among `set`'s arguments
  and may be repeated.
- `--in-include=VALUE`, or `--in-include` on `get`, `show`, `history` or `watch` → exit 2, empty
  stdout, `troupe: error: …` naming the option on stderr; nothing loaded, recorded or written.

## Effect

| Situation | Without `--in-include` (CR-A) | With `--in-include` |
|---|---|---|
| new key, deepest existing ancestor from an included file | override in the including file | into the included file holding the ancestor (step 1 rule); including file untouched |
| new key, ancestor merges an included mapping and an override | override in the override's file | into the included file's part of the mapping |
| new key, ancestor only in an override / in the main file | in that file | in that file |
| existing value, list append, key inside a list item | CR-A rules | same as without |

Output, exit codes and `history` lines are those of `set`.
