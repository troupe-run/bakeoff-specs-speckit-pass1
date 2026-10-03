# Data Model: troupe configuration — Step 3

Step 1 and step 2 data models are unchanged: no event type, stored field or file is added. `get` and
`show` read the located tree that every command already loads, after the usual import/reconcile.

## Located tree (existing, newly read for sources)

| Node | Value shown | Source file (`--sources`) |
|---|---|---|
| `LocatedScalar` | `value` (typed scalar) | `file.path` — the file the scalar is written in (main file or YAML include) |
| `TextInclude` | `target.text` (CRLF → LF in YAML view, spec D-24) | `target.path` — the included text file |
| `LocatedMapping` | entries in document order | — (not a scalar) |
| `LocatedSequence` | items in order | — (not a scalar) |

An empty YAML include is a null `LocatedScalar` whose `file` is the included file (research G-6).

## View line (transient, `config/view.py`)

`show`'s output is a list of lines; each line is `(text, source)` where `source` is the
`SourceFile` of the scalar the line holds, or `None` for lines that hold no scalar (keys opening a
collection, literal-block content lines). With `--sources`, a line with a source is printed as
`text + " # from " + source_label(source)`; other lines are printed as `text`. Every line ends `\n`.

## Source label

`source_label(theatre, file)`: `file.path` relative to `theatre.resolve()`, `/` separators, `..`
segments for files outside the theatre (spec D-22, research G-4).

## Validation rules

- PATH resolution and its errors are step 1's `resolve` (exit 5).
- `get`: node must be `LocatedScalar` or `TextInclude`, else exit 5 with the `config show` hint.
- `show`: any node; PATH optional (root mapping when omitted).
- Read-back invariant (FR-214): parsing `show`'s output (with or without `--sources`) by YAML 1.2
  core-schema rules gives the configuration at PATH, except CRLF in text includes.
