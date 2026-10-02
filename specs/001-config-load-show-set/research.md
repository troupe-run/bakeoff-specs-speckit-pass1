# Research: troupe configuration — load, show, set, history (Step 1)

Each entry gives the decision, why it was made, and what else was considered. Behaviour choices that
the product owner's contract leaves open are in `spec.md` (D-1 … D-9). This file records technical
choices (R-1 … R-16) and the finer behaviour choices that only come up at design level (B-1 … B-12).
Library facts below were checked in a scratch project with `uv add eventsourcing ruamel.yaml` on
2026-10-02 (eventsourcing 9.5.5, ruamel.yaml 0.19.1, Python 3.12.14).

## Technical choices

### R-1 YAML parser: `ruamel.yaml` composer, used for positions only

- **Decision**: Parse each file with `ruamel.yaml`'s `YAML(typ="rt").compose(text)`, giving a node
  graph (`ScalarNode`, `MappingNode`, `SequenceNode`) where each node has `style` / `flow_style` and
  `start_mark.index` / `end_mark.index`. We never use ruamel's dumper or round-trip loader to write.
- **Rationale**: Byte-surgical write-back needs exact source spans for every value. Verified: the
  indices are code-point offsets into the string we pass in, CRLF line endings stay intact if the
  file is read with `newline=""`, a quoted scalar's span includes its quotes, a multi-line plain
  scalar's span covers all its lines, and a block scalar's span runs from the indicator to the end of
  its content (including trailing blank lines). ruamel defaults to YAML 1.2, so `yes` is a string.
- **Alternatives**: ruamel round-trip dump — re-emits the whole file and normalises spacing, quoting
  and comments, so it breaks Principle I. PyYAML — YAML 1.1 only (`yes` → true), wrong typing.
  A hand-written YAML parser — far more code and risk than reading spans from a mature parser.

### R-2 Scalar typing: our own YAML 1.2 core-schema resolver

- **Decision**: One function, `resolve_plain(text) -> Scalar`, implements the YAML 1.2 core schema
  regular expressions (null `null|Null|NULL|~|""`, bool `true|True|TRUE|false|False|FALSE`, int
  decimal/`0o`/`0x`, float incl. `.inf`/`.nan`); quoted and block scalars are always strings. Explicit
  standard tags (`!!str`, `!!int`, …) are honoured.
- **Rationale**: The contract fixes the core schema; owning the rules in one place (Principle IV)
  means file values and command-line VALUEs are typed identically, and the same function decides
  whether a string can be written plain (R-8). ruamel's resolver tags are not relied on.
- **Alternatives**: Trust ruamel's tags — workable today but couples typing to library internals.

### R-3 Parsing VALUE

- **Decision**: Compose VALUE with the same parser; accept it only if it is exactly one node and
  either a scalar or a flow collection (`flow_style is True`), recursively typed with R-2. Anything
  else (parse error, empty input, a block collection such as `a: b` or `- x`) → exit 2.
- **Rationale**: The contract says VALUE is "a single YAML 1.2 flow node"; a block collection is not
  one. Empty VALUE (`''`) composes to nothing → usage error rather than a silent null.
- **Alternatives**: Accept block collections leniently — invents behaviour (Principle V).

### R-4 Event store: `eventsourcing` with its SQLite persistence module

- **Decision**: A `TheatreConfig` aggregate (fixed id: `uuid5` of a constant) whose only domain
  event is `LeafChanged(op, path, old, new)`; an `Application` configured through its `env` argument
  with `PERSISTENCE_MODULE=eventsourcing.sqlite` and `SQLITE_DBNAME=<theatre>/.troupe/events.sqlite3`.
  The aggregate's state (dict of leaf path → value) is the projection; `history` reads the
  aggregate's stored events in order; `seq` is the event's position among `LeafChanged` events
  (1-based).
- **Rationale**: The library is mandated. One aggregate gives a single totally-ordered stream, so
  `seq` is contiguous and needs no extra counter. SQLite is in the standard library, durable and
  atomic per save, and keeps everything under `.troupe/`. Verified: events persist across processes
  and `AggregateNotFoundError` signals "never imported".
- **Alternatives**: POPO (in-memory) persistence — does not survive between commands. One aggregate
  per leaf — no global order for `seq`. Writing JSON files ourselves — bypasses the mandated library.

### R-5 Where state lives

- **Decision**: `<theatre>/.troupe/events.sqlite3` (plus any SQLite journal files, also in
  `.troupe/`). The name is one constant. It can never collide with `troupe.yml`/`troupe.yaml`.
- **Rationale**: Contract: state only under `.troupe/`.

### R-6 Reading and writing files

- **Decision**: Read bytes, decode UTF-8, keep line endings (`newline=""`). Write by creating a
  temporary file in the target's directory, `fsync`, copy the original's permission bits, then
  `os.replace` over the original. Skip the write when bytes are identical (D-7).
- **Rationale**: Principle I: never half-written (D-8). The temporary file exists only for the
  duration of the write and is removed on failure.
- **Alternatives**: In-place truncate-and-write — can leave a half-written file.

### R-7 Edits are splices, verified by re-loading

- **Decision**: Every `set` is computed as a list of text splices `(start, end, replacement)` on one
  file's text. Before writing, the new text is parsed and the whole configuration re-loaded in
  memory with the new text substituted; the write proceeds only if (a) it parses, (b) the value at
  PATH equals the intended value (type-exact), and (c) every leaf outside PATH is unchanged.
  Otherwise the command exits 3 ("write refused") naming the path and file, and nothing is written.
- **Rationale**: Principle I's conservative rule (refuse rather than corrupt). It also catches the
  awkward corners (e.g. keep-chomping stealing blank lines, an unforeseen plain-scalar ambiguity)
  with one general mechanism instead of many special cases. The post-load also yields the event diff.
- **Alternatives**: Trust the renderer — any renderer bug silently corrupts a user's file.

### R-8 Rendering scalars and choosing styles

- **Decision**: One `render` module decides representability per style:
  - *plain*: the text is non-empty, single-line, has no leading/trailing space, does not start with
    an indicator character (`-?:,[]{}#&*!|>'"%@` and backtick, except `-?:` followed by a non-space),
    contains no `: ` or ` #`, does not end in `:`, contains no `,[]{}` when in a flow context, and
    `resolve_plain(text)` gives back the same typed value.
  - *single-quoted*: single-line and no control characters (`'` doubled as `''`).
  - *double-quoted*: always; escapes only `\\`, `\"` and control characters (C0, DEL and C1, via
    the named escapes `\0 \a \b \t \n \v \f \r \e \N` or `\xXX`); every other character —
    including U+2028/U+2029, which are not control characters — is written literally (FR-028).
    Plain and single-quoted styles are not used for strings containing U+FEFF, U+2028 or U+2029.
  Non-string scalars are written plain: integers in decimal, booleans `true`/`false`, null `null`,
  floats in the VALUE's own spelling when it came from the command line as a plain scalar
  (otherwise `repr()`, with `.inf`/`-.inf`/`.nan` for non-finite values).
- **Rationale**: Directly implements the contract's quoting rules with one definition per style.

### R-9 Comment columns and line geometry

- **Decision**: A `layout` module works on lines of one file's text (with their endings) and owns:
  indentation of a line; whether a line is blank/comment-only; finding a line's end-of-line comment
  (a `#` preceded by whitespace and outside any scalar span); the file's indentation step; the
  insertion point after a block collection (R-11). Columns are counted in code points.
- **Rationale**: One place for every geometric rule (Principle IV); all write rules reuse it.

### R-10 Indentation step of a file

- **Decision**: The step is the smallest positive difference between a block mapping's key column
  and the column of a nested block collection's entries found in the file (for sequences, the `-`
  column); default 2 if the file has no nesting.
- **Rationale**: Contract says "the file's indentation (default 2)" without defining detection.

### R-11 Inserting new entries into block collections

- **Decision**: Insert after the collection's last entry, then after any following lines that are
  blank or comment lines indented at least as much as the entries, stopping at the first
  less-indented comment or content line; trailing blank lines directly before that stop line stay
  below the new entry. New lines use the file's line ending (D-6); if the file does not end with a
  line ending, one is added before the new line (the minimal required change).
- **Rationale**: Contract rule "New entries and trailing comments". Keeping blank separator lines
  below the new entry keeps the visual grouping of the next section.

### R-12 Folded (`>`) re-wrapping

- **Decision**: A `folded` module splits the old block into paragraphs (runs of non-blank content
  lines; separators are blank lines) and the new value into paragraphs (folding semantics: text
  between line breaks; `n` consecutive `\n` ⇒ `n−1` blank lines). Old and new paragraph texts are
  aligned with `difflib.SequenceMatcher`: *equal* runs keep their original bytes; in *replace* runs
  the k-th new paragraph is the counterpart of the k-th old one and is wrapped at that old
  paragraph's longest content-line width; surplus new paragraphs and *insert* runs have no
  counterpart and use the block's longest old content-line width. Wrapping is greedy on single
  spaces; a word wider than the width takes its own line. A new paragraph that begins with a space
  or tab, or whose wrapping would start a line with whitespace, would be "more-indented" → exit 3.
- **Rationale**: Implements the contract rule; alignment by text is what "paragraphs whose text is
  unchanged keep their bytes" needs when paragraphs are added or removed.

### R-13 CLI framework

- **Decision**: Standard-library `argparse` with a subparser per subcommand; `--theatre` accepted on
  each subcommand (default `.`); argparse's own exit 2 for usage errors, with stdout kept empty.
- **Rationale**: No dependency needed; argparse already uses exit code 2 for usage errors.
- **Alternatives**: click/typer — extra dependency, no benefit at this size.

### R-14 Errors and exit codes

- **Decision**: One `errors` module: `TroupeError(message)` subclasses `UsageError` (2),
  `WriteRefused` (3), `LoadError` (4), `PathError` (5), each carrying its exit code. Only the CLI
  entry point turns them into stderr + exit code. Every message is built with the offending path or
  file in it.
- **Rationale**: Principle IV — the code-to-meaning mapping lives in one place.

### R-15 Testing approach

- **Decision**: `pytest`. End-to-end tests run the real `troupe` console script (from the project's
  virtual environment) as a subprocess against theatres written to `tmp_path`, and compare stdout,
  stderr, exit code and the exact bytes of every file under the theatre before and after. One smoke
  test runs literally `uv run troupe config …` from the repository root. Unit tests cover the pure
  modules (resolver, renderer, folded wrapping, layout). Each write rule has a "breaks if the rule
  breaks" test (Principle II).
- **Rationale**: Constitution Principle II requires real files and real CLI invocations, and
  byte-comparison for preservation guarantees.

### R-16 Tooling

- **Decision**: `uv` project, `src/` layout, build backend `uv_build` (or hatchling if unavailable),
  console script `troupe = "troupe.cli:main"`; dev group: `pytest`, `mypy`, `ruff`. `mypy --strict`
  over `src` and `tests`; ruff lint + format check. ruamel.yaml ships `py.typed`; eventsourcing ships
  `py.typed`.

## Design-level behaviour choices

These refine the contract where it is silent; each is the conservative option.

- **B-1 Path resolution for `set`**: walk PATH through the loaded tree. A missing key ends the walk
  at the deepest existing mapping (rule 2). A digit segment on a mapping, a non-digit segment on a
  list, a segment below a scalar (including null and text includes), or an index beyond a list's
  length → exit 5. A digit segment for a missing key below a newly-created mapping is a key `"N"` —
  out of contract (digit-only keys).
- **B-2 Rule 4 scope**: exit 3 applies when the target node is the root of a YAML-included file
  (the whole value came from the `file:` string). Setting a text include is rule 1, not rule 4.
- **B-3 Scalar replaced by a block collection**: the scalar's text (and the spaces between `:` and
  it) is removed; if the line has an end-of-line comment it stays at its column; the new block
  lines follow that line. Leading `- ` for list items: a list item scalar becomes a compact block
  (`- a: 1` / following keys aligned under `a`).
- **B-4 Collection replaced by a scalar**: for a block collection, the lines from the first entry
  through the last entry's last line are removed (comment lines after the last entry stay), and
  the scalar is written after `key:` with one space. For a flow collection, the flow text is
  replaced in place.
- **B-5 Collection replaced by a collection**: the old collection's span (as in B-4) is replaced by
  the new collection rendered in the old one's style (block at the old entries' indentation, or
  flow). Comments inside the replaced span are removed with it — they described the old entries.
- **B-6 New collection inside a flow parent**: written in flow style, `{k: v}` / `[a, b]`, with
  `, ` separators.
- **B-7 List items holding new mappings**: compact form (`- k: v` with following keys aligned).
- **B-8 Literal block indentation**: the block's content indentation is the parent's indentation
  plus the file's step; if the value's first line starts with a space, an explicit indentation
  indicator is added. A string that cannot be a literal block (it contains `\r` or other control
  characters except tab, or would need trailing-space-only lines that change meaning) is written
  double-quoted instead.
- **B-9 Chomping**: no trailing `\n` → `-`; exactly one → clip (no indicator) unless the existing
  block was `+` and `+` still yields the exact value; more than one → `+`. Final verification (R-7)
  refuses rather than writes if the result would not re-load to the value.
- **B-10 History PATH filter** is a plain string filter: a PATH that has never existed prints nothing
  and exits 0. Its syntax is not validated beyond being non-empty.
- **B-11 JSON values in history** are emitted with `json.dumps(..., ensure_ascii=False)`, one object
  per line in key order `seq, op, path, old, new`.
- **B-12 Leaf order** is document order with includes expanded in place; empty collections have no
  leaves.
- **B-13 Comments after a growing flow collection**: when a new entry is appended to a flow
  collection, an end-of-line comment on that line returns to its previous column (one space if the
  line now reaches it), the same rule FR-036 applies to changed values — so aligned comment columns
  survive.
- **B-14 Folded blocks with more-indented lines**: a folded value that already contains
  more-indented lines cannot be split into foldable paragraphs reliably, so changing it is refused
  (exit 3) rather than guessed at.
- **B-15 Keep chomping and trailing blank lines**: when a literal block's chomping becomes (or is)
  `+`, the blank lines that follow its content are part of the value and are replaced with it, so
  they do not silently join the new value.
- **B-16 Permission and storage failures**: `set` refuses (exit 3, naming the file, nothing
  changed) when the file holding the value, its directory, or the event store is not writable —
  checked before the write, so a read-only file is never silently replaced by the atomic rename
  and a change is never written without its events. Any other failure to open or use the event
  store is a load error (exit 4) naming the store's file; no command ends in a traceback.
- **B-17 Setting a value to a `file:` string**: VALUE `file:x` is a string (FR-005), and once
  written it is an include (FR-010). `set` writes it like any string and verifies it by what is
  written (the `file:` string) rather than by the included content; the event's `new` is the
  loaded value (the target's text, for a text include). If the include cannot load (missing
  target, cycle), the write is refused (exit 3) with a message naming the target.
- **B-18 Insertion after keep-chomped blocks**: a new key or list item that follows a collection
  whose last value is a keep-chomped (`|+` / `>+`) block scalar goes below that block's trailing
  blank lines, because those lines are part of its value (B-15); after any other value, blank
  lines directly above the next section stay below the new entry (R-11).
