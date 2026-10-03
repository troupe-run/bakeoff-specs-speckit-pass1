# Research: troupe configuration — `get` for values, `show` for anything (Step 3)

Each entry gives the decision, why it was made, and what else was considered. Behaviour choices the
contract leaves open are in `spec.md` (D-20 … D-26). This file records the technical choices for step 3
(G-1 … G-7). Step 1 research (R-*, B-*) and step 2 research (S-*) stay in force. Library behaviour was
checked against the locked ruamel.yaml on 2026-10-03.

## G-1 `get` is step 1's `show`, renamed; `show` dispatches on the node kind

- **Decision**: Rename `commands.show` to `commands.get` with one change: the "not a scalar" error
  message becomes `PATH: is a mapping, not a scalar; use \`troupe config show PATH\` to print it`
  (FR-202). The new `commands.show(theatre, path_text | None, sources)` loads the same way, resolves
  PATH (or takes the root), and then:
  - scalar or text include, no `--sources` → `format_scalar` (identical to `get`, FR-211);
  - otherwise → `view.render(node, sources=…)` (G-2).
- **Rationale**: `get` keeps one code path with step 1 (SC-201). Both commands share
  `open_theatre(reconcile=True)` and `resolve` (Principle IV); `get` is listed with the reconciling
  commands (D-20, step 2 FR-120) simply by calling `open_theatre` the same way.
- **Alternatives**: Keep `show` as the scalar printer and add a flag — contradicts the contract.

## G-2 A new module `config/view.py` renders the located tree as YAML

- **Decision**: `view.py` walks the located tree (`LocatedMapping`, `LocatedSequence`,
  `LocatedScalar`, `TextInclude`) directly — the tree already holds resolved includes and, for each
  scalar, the `SourceFile` it was read from — and produces output lines. For every scalar it yields
  the line text plus the source path, and appends ` # from <file>` when `sources` is set.
  Spelling of scalars and keys reuses `edit/render.py`: `render_inline(NewScalar(value), PLAIN,
  in_flow=False)` (plain → single → double, FR-222; `.inf`/`.nan` via `canonical_plain`, FR-224),
  `render_key`, and `render_literal(value, column, STEP)` for literal blocks (chomping and
  indentation indicator, FR-223).
- **Layout**: `STEP = 2` (the `show` indentation, one constant in `view.py`). Mapping entries at
  `column`; a non-empty collection value goes on following lines at `column + 2`; list items at
  `column` as `- `; a non-empty collection that is a list item starts on the item's line (compact
  form, `- k: v` / `- - x`); empty collections as `{}` / `[]` inline. This is the same layout as
  `render_block` (step 1 B-6), but `show` cannot use `render_block` because it needs per-scalar
  source comments and must force text includes into literal blocks even when single-line.
- **Rationale**: The located tree is the one place that knows where each value comes from; converting
  it to plain values first would lose the sources. Reusing render.py's scalar functions keeps one
  definition of "how a scalar is spelled" (Principle IV). `show`'s layout is a decision of its own
  (spec D-21), so it lives in its own module; `set`'s new-collection layout follows the edited file's
  indentation and is not changed.
- **Alternatives**: Serialise with ruamel's emitter — its quoting, literal-block and comment placement
  rules differ from ours (e.g. it cannot put a comment on a block-scalar header), and tests would pin
  library behaviour. Parametrise `render_block` with callbacks — couples `set`'s write-back code (the
  most delicate in the project) to a read-only view.

## G-3 Text includes and multi-line strings

- **Decision**: A `TextInclude` is always written as a literal block. Its text has `\r\n` replaced by
  `\n` first (spec D-24). If the result is still not `literal_representable` (other control
  characters — out of contract), it falls back to double quotes so the output stays valid YAML. Any
  other string containing `\n` and `literal_representable` is a literal block; otherwise it is written
  inline (double-quoted).
- **Rationale**: Contract "text includes as literal blocks"; spec FR-223 and D-24. `render_literal`
  already chooses `|`, `|-`, `|+` and the indentation indicator.
- **Verified**: ruamel reads `| # from x\n  Be terse.\n` as `"Be terse.\n"`, `a: |2 # c\n   lead\n`
  as `{"a": " lead\n"}`, `- k: |2\n     lead\n` as `[{"k": " lead\n"}]`, and top-level
  `|2- # c\n   lead\n` as `" lead"` — comments on block headers are allowed, and content at
  `column + 2` with indicator `2` reads back correctly at every depth including the top level.

## G-4 Source file paths

- **Decision**: `source_label(theatre, file) = os.path.relpath(file.path, theatre.resolve())` with
  `os.sep` replaced by `/` (one function in `view.py`). `file.path` is already the resolved path the
  loader keys files by; for a `TextInclude` the file is `target`, for every other scalar it is
  `LocatedScalar.file`.
- **Rationale**: Spec FR-232 – FR-233, D-22. `relpath` produces `..` segments for files outside the
  theatre and never a leading `./`. Resolving the theatre handles theatres reached through linked
  directories.
- **Alternatives**: Keep the include path as written — would need the loader to carry a second path
  per file, and would disagree with the file `set` writes to.

## G-5 `show SCALAR --sources`

- **Decision**: `view.render` of a scalar node produces one top-level YAML node: inline spelling (or a
  literal block header with content at column 2) plus the comment (spec D-23, FR-234). Without
  `--sources`, `show` never calls `view` for a scalar (G-1).
- **Verified**: `0.2 # from x\n` reads back as `0.2`; `'0.2' # c\n` as `"0.2"` (G-3 covers literals).

## G-6 Empty configuration and empty YAML includes

- **Decision**: An empty main file is a `LocatedMapping` with no entries → `{}\n`. An empty YAML include
  embeds as a null scalar sourced from the included file → `key: null # from <that file>`.
- **Rationale**: Follows the loader's existing representation (step 1 D-5); FR-214 holds.

## G-7 CLI

- **Decision**: argparse subparsers: `get PATH` (required); `show [PATH]` (`nargs="?"`) with
  `--sources` (`store_true`). argparse accepts options before or after the positional (D-26) and
  rejects `get --sources` as an unrecognised argument (exit 2 via the existing usage-error path).
- **Tests**: step 1 `show` tests that print scalars move to `get` (and one representative set is kept
  on `show` to prove FR-211); tests that expected `show` of a collection to exit 5 become `get` tests
  (with the `config show` hint) and `show` YAML tests. Usage tests: `get` with no PATH,
  `get --sources`, `show a b`.
