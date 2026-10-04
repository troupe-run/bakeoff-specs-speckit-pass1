# CLI Contract: `troupe config` (Step 4 additions)

The contracts of steps 1–3 (`specs/00{1,2,3}-*/contracts/cli.md`) stay in force. This file adds the
lineage fields, `TROUPE_ACTOR` and `set --reason`.

## Invocation

```text
uv run troupe config set PATH VALUE [--reason TEXT] [--theatre DIR]
```

`--reason` is accepted only by `set`; `--reason` without TEXT, or on any other subcommand → exit 2.

## Environment

| Variable | Values | Effect |
|---|---|---|
| `TROUPE_ACTOR` | unset | actor of `set`'s events: `{"kind": "human", "id": <login name, or null if unknown>}` |
| | `human:<id>` / `agent:<id>`, `<id>` non-empty | actor `{"kind": "human"/"agent", "id": "<id>"}`; `<id>` is everything after the first `:` |
| | anything else (incl. empty, `human:`, `Human:x`, `robot:x`) | every `config` subcommand exits 2, stderr `troupe: error: TROUPE_ACTOR: …` naming the value; nothing loaded, recorded or written |

## `history` line format

Each line is one JSON object with keys in this order:

| Key | Value |
|---|---|
| `seq`, `op`, `path`, `old`, `new` | as step 1 |
| `actor` | `{"kind": "human" \| "agent" \| "unknown", "id": string \| null}` |
| `via` | `"import"` \| `"cli"` \| `"file"` |
| `at` | RFC 3339 UTC, `YYYY-MM-DDTHH:MM:SS.ffffffZ` |
| `reason` | string \| null |
| `change` | opaque string; equal for events of one unit, distinct between units |

Examples:

```text
{"seq": 1, "op": "import", "path": "a", "old": null, "new": 1, "actor": {"kind": "unknown", "id": null}, "via": "import", "at": "2026-10-04T09:00:00.000001Z", "reason": null, "change": "0b6e…"}
{"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2, "actor": {"kind": "unknown", "id": null}, "via": "file", "at": "2026-10-04T09:05:00.000002Z", "reason": null, "change": "a91d…"}
{"seq": 3, "op": "set", "path": "b.0", "old": "x", "new": "z", "actor": {"kind": "agent", "id": "coder-7"}, "via": "cli", "at": "2026-10-04T09:06:00.000003Z", "reason": "trim", "change": "5c2f…"}
{"seq": 4, "op": "remove", "path": "b.1", "old": "y", "new": null, "actor": {"kind": "agent", "id": "coder-7"}, "via": "cli", "at": "2026-10-04T09:06:00.000003Z", "reason": "trim", "change": "5c2f…"}
```

## Exit codes

Unchanged. New exit-2 causes: invalid `TROUPE_ACTOR` (any subcommand); `--reason` misuse.
