# CLI Contract: `troupe config` (Step 1)

The product owner's contract (quoted in `spec.md` input) is normative; this file fixes the command
surface the implementation exposes and the exact output shapes tests check.

## Invocation

```text
uv run troupe config show    PATH        [--theatre DIR]
uv run troupe config set     PATH VALUE  [--theatre DIR]
uv run troupe config history [PATH]      [--theatre DIR]
```

- `--theatre DIR` follows the subcommand, before or after its positional arguments; default `.`.
- VALUE is one argv element (shell-quote it), parsed as one YAML 1.2 flow node (research R-3).
- Negative numbers such as `-3` work as VALUE directly. A VALUE that begins with `-` followed by a
  non-digit may need to follow `--` (standard argparse convention), e.g. `troupe config set x -- -a`.

## Outputs

| Command | stdout on success | exit |
|---|---|---|
| `show PATH` | The scalar, printed per FR-006 | 0 |
| `set PATH VALUE` | nothing | 0 |
| `history [PATH]` | JSON Lines, one event per line, oldest first | 0 |

History line format (one compact JSON object, keys in this order):

```json
{"seq": 1, "op": "import", "path": "model.temperature", "old": null, "new": 0.2}
```

## Errors

On any failure: stdout empty; stderr one line `troupe: error: <message>` where the message names the
offending path or file; exit code:

| Code | Meaning | Examples |
|---|---|---|
| 2 | Usage error | unknown subcommand/option, missing PATH/VALUE, invalid VALUE, empty path segment |
| 3 | Write refused (no file changed) | replacing a YAML-included value; non-string into a text include; folded value would gain a more-indented line; edit fails verification |
| 4 | Configuration cannot be loaded | no/both config files; YAML syntax error; non-mapping root; missing include target; include cycle |
| 5 | Path not found / wrong kind of node | `show` of missing path or of a collection; descending through a scalar; index on a mapping or key on a list; list index > length |

## Side effects

- First successful configuration load against a theatre records the import (spec D-2), even for
  `show` and `history`.
- `set` writes at most the one file that holds the target value; state is written only under
  `DIR/.troupe/`.
