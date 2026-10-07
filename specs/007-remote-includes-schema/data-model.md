# Data Model: troupe configuration — remote includes and a schema (Step 7)

Entities from steps 1–6 (`specs/00{1..6}-*/data-model.md`) stay in force. Events, lineage and the
store are unchanged. Step 7 changes what a source can be, how a string is classified while loading,
and how `set` spells include-like strings. Technical choices are in [research.md](research.md)
(U-1 … U-12).

## Source (`files.SourceFile`)

| Field | Meaning | Change |
|---|---|---|
| `path: Path \| str` | the resolved local path, or the URL exactly as written in the include string | widened (U-2) |
| `text` | the file's text, or the fetched body decoded as UTF-8 | — |
| `kind: "yaml" \| "text"` | from the path's name (`is_yaml_name`) or the URL path (`is_yaml_url`) | rule extended (U-4) |

`local_path(source) -> Path` gives the path, or raises `RemoteSource` (exit 3) for a URL. Every write
goes through it.

## Loaded (`loader.Loaded`)

| Field | Meaning | New? |
|---|---|---|
| `root` | the located tree | — |
| `files: dict[Path, SourceFile]` | local files only (what `watch` snapshots) | — |
| `remote: dict[str, SourceFile]` | fetched documents by URL; passed to re-checks so a command fetches each URL once (D-62) | NEW |
| `composed: dict[Path \| str, Any]` | composed nodes per source | key widened |
| `schema: Schema \| None` | the parsed schema, if the file exists | NEW |

## String classification (while loading)

```text
include_ref(s)  = FileRef(s[5:])  if s starts "file:"
                  UrlRef(s)        if s starts "https://" or "http://"
                  None             otherwise
is_include(scalar, sub) = scalar.value is a str
                          and include_ref(scalar.value) is not None
                          and scalar.node.tag != "!literal"
                          and not (sub is an object and sub["format"] == "uri")
```

`sub` is the subschema at the scalar's configuration path:

```text
child(sub, key)   = sub["properties"][key]      if present and an object
                    sub["additionalProperties"] if an object
                    None                        otherwise
child(sub, index) = sub["items"]                if an object, else None
root sub          = the schema document (None when there is no schema file)
```

Included content and a mapping-form include's overrides take the subschema of the position they fill.
`$ref` values are not configuration paths; they are always include strings when `include_ref` says so.

| Source of the include | `FileRef` | `UrlRef` |
|---|---|---|
| local file | read relative to the including file (step 1) | fetched (U-3) |
| remote document | exit 4 (D-61) | fetched |

## Scalars

| Written | Value | Notes |
|---|---|---|
| `!literal https://x` | `"https://x"` | never an include |
| `!literal 5` | `"5"` | D-66 |
| `!literal` on a mapping or list | exit 4 | D-66 |
| `https://x` at a `format: uri` path | `"https://x"` | never an include |
| `https://x` elsewhere | the fetched content | an include |

`NewScalar` (a command-line VALUE scalar) gains `tag: str | None`. `literals.mark` sets it to
`!literal` (FR-640 – FR-643), and the renderer writes it before the scalar's text. `plain_value`
ignores it.

## Schema (`schema.Schema`)

| Item | Rule |
|---|---|
| location | `<theatre>/.troupe/troupe.schema.json`; absent → no validation, no schema literals |
| dialect | `$schema` absent or `https://json-schema.org/draft/2020-12/schema`, else exit 4 |
| validity | `Draft202012Validator.check_schema`; invalid → exit 4 naming the file |
| references | `$ref`/`$dynamicRef` values must start with `#`, else exit 4 |
| validation | of the loaded value (overrides merged, includes and literals resolved, no `$ref`); `format` not asserted |
| failure on load | exit 4: `<schema file>: <dotted path>: <message>` |
| failure after a `set` | exit 3, via the re-check (`would not load back (…)`), nothing written |

## Remote refusal

| `set` would write… | Result |
|---|---|
| a local file | as steps 1–6 |
| a remote document (existing value, text include, append, key in a list item, alias expansion, `--in-include` key, override in a remote including file) | exit 3; stderr contains the outermost remote include string on PATH's route as written, its local file and its line |
