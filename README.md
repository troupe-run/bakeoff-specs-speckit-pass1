# troupe — configuration subsystem

troupe is an AI orchestration tool. Each project ("theatre") keeps its configuration in
`.troupe/troupe.yml` (or `.troupe/troupe.yaml`), which can be split across files with `file:`
includes. This package provides `troupe config`, which reads and changes that configuration without
disturbing the hand-written files, and records every change as an event.

```sh
uv run troupe config show PATH          [--theatre DIR]   # print a scalar setting
uv run troupe config set PATH VALUE     [--theatre DIR]   # change it in the file that holds it
uv run troupe config history [PATH]     [--theatre DIR]   # list changes as JSON Lines
```

- `PATH` is dotted (`agents.coder.model`); a digit segment indexes a list (`tools.0`).
- `VALUE` is one YAML 1.2 flow node: `0.2`, `true`, `null`, `abc`, `"0.2"`, `{a: 1}`, `[a, b]`,
  `"line one\nline two\n"`.
- `set` changes only the bytes of the value: comments, quoting, indentation and layout elsewhere
  stay exactly as written. Every edit is re-read and checked before the file is replaced; if it
  cannot be written safely, nothing changes and the command exits 3.
- State (the event store) lives in `<theatre>/.troupe/events.sqlite3`.

| Exit | Meaning |
|---|---|
| 0 | success |
| 2 | usage error |
| 3 | write refused (no file changed) |
| 4 | configuration cannot be loaded |
| 5 | path not found, or the wrong kind of node for the command |

## Development

```sh
uv sync
uv run pytest
uv run mypy --strict src tests
uv run ruff check . && uv run ruff format --check .
```

Specification, design decisions and task list: [`specs/001-config-load-show-set/`](specs/001-config-load-show-set/).
