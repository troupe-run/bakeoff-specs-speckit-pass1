# CLI Contract: `troupe config` (Step 7 additions)

The contracts of steps 1–6 stay in force. Step 7 adds one `set` option, a new kind of include, the
`!literal` tag and an optional schema file. No output format or exit code is added.

## `set` option

```text
troupe config set PATH VALUE [--include] [--in-include] [--expand-alias] [--reason TEXT] [--theatre DIR]
```

| Option | Meaning |
|---|---|
| `--include` | write an include-like VALUE (`https://…`, `http://…`, `file:…`) as an include, untagged. No effect on other values. Not accepted by other subcommands (exit 2). |

## Include strings

| String (not a literal) | Value |
|---|---|
| `file:<path>` | local file, YAML if the name ends `.yml`/`.yaml`, else its text (step 1) |
| `https://…` / `http://…` | fetched each load; YAML if the URL path (no query/fragment) ends `.yml`/`.yaml`, else the body text |

Both forms work in scalar form and as `$ref` (step 5). A failed fetch → exit 4. That covers no
connection, a non-2xx status, more than 10 s, a body that is not UTF-8, or invalid YAML. A `file:`
include inside fetched content → exit 4.

## Literals

```yaml
api:
  endpoint: https://api.example.com/v1        # literal if the schema marks api.endpoint format: uri
docs: !literal https://example.com/guide.yaml # literal by tag
notes: !literal file:notes.md                 # literal by tag
```

## Schema file

`<theatre>/.troupe/troupe.schema.json`, JSON Schema 2020-12.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "api": {"type": "object", "properties": {"endpoint": {"type": "string", "format": "uri"}}},
    "agents": {"type": "object", "additionalProperties": {"properties": {"homepage": {"format": "uri"}}}},
    "mirrors": {"type": "array", "items": {"type": "string", "format": "uri"}}
  }
}
```

| Situation | Exit | stderr names |
|---|---|---|
| schema not JSON / not a valid 2020-12 schema / other `$schema` / `$ref` outside the document | 4 | the schema file |
| loaded configuration invalid | 4 | the schema file and a failing path |
| `set` would make it invalid | 3 | PATH and the schema file |

## `set` and remote content

| Situation | Result |
|---|---|
| new key under remote content, local including file | override in the including file (step 5) |
| existing value overridden locally | the local override changes |
| any other write into remote content | exit 3: `PATH: comes from the remote include <string as written> (line N of <file>); remote content is read-only — change that include line instead; no file was changed` |

## `set` and include-like VALUEs

| VALUE string | Schema marks the string's path `format: uri` | `--include` | Written |
|---|---|---|---|
| include-like | no | no | `key: !literal <value>` |
| include-like | yes | no | `key: <value>` |
| include-like | no | yes | `key: <value>` (an include; must load, else exit 3) |
| include-like | yes | yes | exit 3 |
| other | — | any | as before |

Replacing a value that is already tagged `!literal` keeps the tag, unless `--include` removes it.

## `show --sources`

A value from fetched content is annotated `# from <URL as written in the include string>`.
