# CLI Contract: `troupe config` (Step 5 additions)

The contracts of steps 1–4 (`specs/00{1,2,3,4}-*/contracts/cli.md`) stay in force. No subcommand,
option, output format or exit code is added. Step 5 changes what the configuration files may contain
and where `set` writes a new key.

## File format: mapping-form include

```yaml
agents:
  coder:                          # mapping form
    $ref: file:agents/coder.yaml  # the include string (scalar form: `coder: file:agents/coder.yaml`)
    temperature: 0.3              # override: replaces/merges into the included content
    limits:
      timeout: 30                 # mappings merge recursively; scalars and lists replace
```

| Form | Value |
|---|---|
| `{$ref: file:x.yaml}` | the content of `x.yaml` (same as `file:x.yaml`) |
| `{$ref: file:x.yaml, k: v, …}` | `x.yaml`'s content deep-merged with the overrides; `x.yaml` must hold a mapping (else exit 4) |
| `{$ref: file:x.md}` | the text of `x.md` |
| `{$ref: file:x.md, k: v, …}` | exit 4 on every command, stderr names the including file |
| `{$ref: <not a file: string>, …}` | an ordinary mapping |

`$ref` is never part of the value: not printed by `show`, no history events, `get …$ref` → exit 5.

## `set PATH VALUE` — where it writes

| Situation | Written in |
|---|---|
| existing value, overridden | the override, in the including file |
| existing value, not overridden | the file it comes from (possibly the shared file) |
| new key, deepest existing ancestor in the main file (incl. a mapping-form include's overrides there) | the main file |
| new key, deepest existing ancestor from an included file | an override in the nearest including file; scalar form converted first |
| append to a list (`PATH` ends in the list's length) | the file holding the effective list |
| new key inside a list item | the file holding the list |
| replace a whole include, or a mapping merging included and override keys | exit 3, nothing written |
| override position already holds an include | exit 3, nothing written |

Conversion examples (the first is the contract's):

```text
coder: file:agents/coder.yaml  # c        coder:  # c
                                    →       $ref: file:agents/coder.yaml
                                            temperature: 0.3

- file:a.yaml  # c                  →     - $ref: file:a.yaml  # c
                                            temperature: 0.3

agents: {coder: file:c.yaml}        →     agents: {coder: {$ref: file:c.yaml, temperature: 0.3}}
```
