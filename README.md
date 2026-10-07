# troupe — configuration subsystem

troupe is an AI orchestration tool. Each project ("theatre") keeps its configuration in
`.troupe/troupe.yml` (or `.troupe/troupe.yaml`), which can be split across files with `file:`
includes and can include shared team configuration from `https://` URLs. This package provides `troupe config`, which reads and changes that configuration without
disturbing the hand-written files, and records every change as an event.

```sh
uv run troupe config get PATH           [--theatre DIR]   # print a scalar setting
uv run troupe config show [PATH] [--sources] [--theatre DIR]   # print a setting or a section as YAML
uv run troupe config set PATH VALUE [--reason TEXT] [--in-include] [--expand-alias] [--include] [--theatre DIR]   # change it in the file that holds it
uv run troupe config history [PATH]     [--theatre DIR]   # list changes as JSON Lines
uv run troupe config watch              [--theatre DIR]   # record hand edits as they happen
```

- `PATH` is dotted (`agents.coder.model`); a digit segment indexes a list (`tools.0`).
- `VALUE` is one YAML 1.2 flow node: `0.2`, `true`, `null`, `abc`, `"0.2"`, `{a: 1}`, `[a, b]`,
  `"line one\nline two\n"`.
- `show` prints a section (or, without `PATH`, the whole configuration) as YAML with every include
  resolved — text includes as literal blocks. `--sources` adds `# from <file>` to each value, naming
  the file it lives in, relative to the theatre:

  ```sh
  $ uv run troupe config show agents --sources
  coder:
    model: sonnet # from .troupe/agents/coder.yaml
  ```
- `set` changes only the bytes of the value: comments, quoting, indentation and layout elsewhere
  stay exactly as written. Every edit is re-read and checked before the file is replaced; if it
  cannot be written safely, nothing changes and the command exits 3.
- An include may carry **overrides**: write it as a mapping with `$ref` and the keys to change.
  The value is the included content deep-merged with them (mappings merge; scalars and lists
  replace). Included files are shared, so `set` never adds a new key to one: a new key under an
  included section is written as an override in the file holding the include, converting a
  one-line include first:

  ```yaml
  coder: file:agents/coder.yaml  # c       →    coder:  # c
                                                  $ref: file:agents/coder.yaml
                                                  temperature: 0.3
  ```

  Existing values still change where they live (the override if overridden, else the included
  file); list appends and keys inside list items go to the file holding the list. Overrides on a
  non-YAML include exit 4; replacing a section partly from an included file exits 3.
- When a new key genuinely belongs in the shared file, say so: `set --in-include PATH VALUE`
  writes it into the included file instead (the including file is not touched). The flag changes
  nothing else: existing values, list appends and keys inside list items land where they would
  without it.
- YAML anchors are shared: setting a value defined at an anchor (`&name`) changes it at the anchor,
  and so everywhere it is aliased. A path reached **through** an alias (`*name`) is refused (exit 3);
  `set --expand-alias PATH VALUE` first replaces that alias with a block-style copy of the anchored
  value, then sets the value in the copy (other aliases still refer to the anchor). Merge keys
  (`<<`) are never written.

  ```yaml
  coder:                                  coder:
    settings: *d          →                 settings:  # expanded from *d by troupe
                                              model: sonnet
  ```
- **Remote includes**: a string starting `https://` or `http://` is an include too, fetched each
  time the configuration loads — YAML if the URL's path ends `.yml`/`.yaml`, otherwise text. A
  failed fetch (no connection, non-2xx status, more than 10 seconds, not UTF-8, invalid YAML) exits 4.
  Remote content is read-only: changing a value that comes from it exits 3 and names the include
  line to change instead; a new key under it still becomes a local override. Remote content may not
  include local `file:`s. `show --sources` labels remote values with their URL.

  ```yaml
  agents: https://config.example.com/team/agents.yaml
  ```
- **Schema**: `.troupe/troupe.schema.json` (JSON Schema 2020-12), if present, describes the
  configuration. A configuration that does not validate exits 4 on every command; a `set` that would
  make it invalid exits 3. `format` is not checked; it marks literals.
- **Literals**: existing plain `https://`, `http://` and `file:` strings are now includes. A string
  is taken literally instead when the schema marks its path `"format": "uri"` (found through
  `properties`, `additionalProperties` and `items`) or when it is tagged `!literal`:

  ```yaml
  api:
    endpoint: https://api.example.com/v1        # format: uri in the schema
  docs: !literal https://example.com/guide.yaml
  ```

  `set` writes an include-like VALUE tagged `!literal` (`docs: !literal https://…`) unless the
  schema marks PATH `format: uri`; `set --include PATH VALUE` writes it as an include instead.
- Hand edits are recorded too: every command except `history` first records, as `set`/`remove`
  events, whatever was edited in the files since the last command. `watch` does the same within
  2 seconds of each edit until you stop it (Ctrl-C or SIGTERM); a formatting- or comment-only edit
  records nothing, and a `set` made while `watch` runs is recorded once.
- Every history line also says who made the change, how, when, why, and what changed with it:

  ```text
  {"seq": 3, "op": "set", "path": "b.0", "old": "x", "new": "z", "actor": {"kind": "agent", "id": "coder-7"}, "via": "cli", "at": "2026-10-04T09:06:00.000003Z", "reason": "trim", "change": "5c2f…"}
  ```

  `actor` comes from `TROUPE_ACTOR=human:<id>` or `agent:<id>` (unset → you, by login name;
  anything else → exit 2, for every command). `via` is `cli`, `file` (a hand edit) or `import`
  (the first command); hand edits and imports have actor `{"kind": "unknown", "id": null}`.
  `reason` is the text given with `set --reason`, else `null`. All events one `set`, one
  reconcile or the import records share one `change` and one UTC `at`.
- State (the event store) lives in `<theatre>/.troupe/events.sqlite3`, with
  `events.sqlite3.lock` beside it so that concurrent commands record each change once.

| Exit | Meaning |
|---|---|
| 0 | success |
| 2 | usage error |
| 3 | write refused (no file changed) |
| 4 | configuration cannot be loaded |
| 5 | path not found, or the wrong kind of node for the command (e.g. `get` of a section) |

## Development

```sh
uv sync
uv run pytest
uv run mypy --strict src tests
uv run ruff check . && uv run ruff format --check .
```

Specification, design decisions and task list: [`specs/001-config-load-show-set/`](specs/001-config-load-show-set/)
(load, show, set, history) and [`specs/002-config-file-sync/`](specs/002-config-file-sync/) (sync with
files, watch) and [`specs/003-config-get-show/`](specs/003-config-get-show/) (get, show as YAML) and
[`specs/004-config-lineage/`](specs/004-config-lineage/) (lineage) and
[`specs/005-include-overrides/`](specs/005-include-overrides/) (overrides) and
[`specs/006-set-in-include/`](specs/006-set-in-include/) (`set --in-include`) and
[`specs/007-remote-includes-schema/`](specs/007-remote-includes-schema/) (remote includes, schema,
literals).
