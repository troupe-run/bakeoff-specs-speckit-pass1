# CLI Contract: `troupe config` (Step 2 additions)

Step 1's contract (`specs/001-config-load-show-set/contracts/cli.md`) stays in force. This file adds
the `watch` subcommand and the reconcile side effect.

## Invocation

```text
uv run troupe config watch               [--theatre DIR]
```

`--theatre` defaults as for every subcommand (`$TROUPE_THEATRE`, else the current directory). Any
positional argument → exit 2.

## Output

| Stream | Content |
|---|---|
| stdout | exactly one line `watching <dir>\n`, flushed once watching; nothing else, ever |
| stderr | `troupe: error: <message>` naming the file, once per distinct load failure while watching |

`<dir>` is the `--theatre` value as given, else `$TROUPE_THEATRE` as given, else the absolute path of
the current directory (spec D-11).

## Exit codes

| Code | When |
|---|---|
| 0 | stopped by SIGINT or SIGTERM |
| 2 | usage error |
| 4 | configuration (or event store / lock file) cannot be loaded at startup; the `watching` line is not printed |

## Side effects (all commands)

| Command | Imports a never-imported theatre | Reconciles first | Then |
|---|---|---|---|
| `get` (step 3) | yes | yes | prints the value |
| `show` | yes | yes | prints the value (step 3: or a section as YAML) |
| `set` | yes | yes | writes and records its own events |
| `watch` | yes | yes, then within 2 s of each change | — |
| `history` | yes | **no** | prints recorded events |

Reconcile events use the existing history line format, e.g.
`{"seq": 9, "op": "set", "path": "a", "old": 1, "new": 2}` and
`{"seq": 10, "op": "remove", "path": "b.1", "old": "y", "new": null}`.

State files under `DIR/.troupe/`: `events.sqlite3*` (step 1) and `events.sqlite3.lock` (new; the
cross-process lock, research S-3).
