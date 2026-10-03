# CLI Contract: `troupe config` (Step 3 changes)

Step 1 (`specs/001-config-load-show-set/contracts/cli.md`) and step 2
(`specs/002-config-file-sync/contracts/cli.md`) stay in force, except that step 1's `show PATH` is
replaced by `get PATH` and the new `show` below.

## Invocation

```text
uv run troupe config get  PATH                 [--theatre DIR]
uv run troupe config show [PATH] [--sources]   [--theatre DIR]
```

Options may appear before or after PATH. `get` without PATH, `get --sources`, an extra positional, or
an unknown option → exit 2.

## Output

| Command | Node at PATH | stdout |
|---|---|---|
| `get PATH` | scalar / text include | the value per step 1 FR-006 |
| `get PATH` | mapping / list | nothing; exit 5; stderr `troupe: error: PATH: is a mapping, not a scalar; use \`troupe config show PATH\` to print it` (or `a list`) |
| `show PATH` | scalar / text include | same as `get PATH` |
| `show [PATH]` | mapping / list / omitted (whole configuration) | block-style YAML (below) |
| `show PATH --sources` | scalar / text include | the scalar as one YAML node + ` # from <file>` (spec D-23) |
| `show [PATH] --sources` | mapping / list / omitted | the same YAML, each scalar line + ` # from <file>` |

### YAML layout (spec FR-220 – FR-225, D-21)

```yaml
model:
  temperature: 0.2 # from .troupe/troupe.yml
  name: opus # from .troupe/troupe.yml
agents:
  coder:
    model: sonnet # from .troupe/agents/coder.yaml
    tools:
      - git # from .troupe/agents/coder.yaml
    steps:
      - name: a # from .troupe/agents/coder.yaml
        run: x # from .troupe/agents/coder.yaml
    extra: {}
prompt: | # from .troupe/prompts/system.md
  Be terse.
  No jokes.
```

(The same output without `--sources` has no `# from` comments.)

- 2-space indentation; lists indented under their key; collections in list items use the compact form.
- Strings: plain if that reads back as the same string, else `'single'`, else `"double"`.
- Text includes and other multi-line strings: literal blocks (`|`, `|-`, `|+`, with indentation
  indicator when the first line starts with a space); the comment goes on the header line.
- `true`/`false`, `null`, decimal integers, floats as `repr()` with `.inf`, `-.inf`, `.nan`.
- Empty collection: `{}` / `[]`, no comment. Empty configuration: `{}`.
- `<file>`: the file's real path relative to the theatre directory's real path, `/` separators.

## Exit codes

Unchanged: 0 success; 2 usage; 4 configuration cannot be loaded; 5 path not found / wrong kind of node.

## Side effects

| Command | Imports a never-imported theatre | Reconciles first | Writes configuration files |
|---|---|---|---|
| `get` | yes | yes | no |
| `show` | yes | yes | no |

`set`, `history` and `watch` are unchanged.
