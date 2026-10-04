# Quickstart: validate step 4 (lineage)

Prerequisites: `uv sync` at the repository root.

## Gates (Principle III — run and show the output)

```sh
uv run pytest
uv run mypy --strict src tests
uv run ruff check . && uv run ruff format --check .
```

## Manual walk-through

```sh
T=$(mktemp -d); mkdir -p $T/.troupe
printf 'a: 1\nb: [x, y]\n' > $T/.troupe/troupe.yml

uv run troupe config history --theatre $T
#  3 import lines: actor unknown/null, via "import", same "change", reason null

TROUPE_ACTOR=agent:coder-7 uv run troupe config set b '[z]' --reason trim --theatre $T
uv run troupe config history b --theatre $T
#  b.0 set + b.1 remove: actor agent/coder-7, via "cli", reason "trim", one shared "change"
#  and one shared "at" ending in Z

sed -i.bak 's/a: 1/a: 2/' $T/.troupe/troupe.yml
TROUPE_ACTOR=human:alice uv run troupe config get a --theatre $T     # prints 2
uv run troupe config history a --theatre $T
#  last line: via "file", actor unknown/null — alice is not credited

uv run troupe config set a 3 --theatre $T                          # TROUPE_ACTOR unset
uv run troupe config history a --theatre $T | tail -1
#  actor {"kind": "human", "id": "<your login name>"}, reason null

TROUPE_ACTOR=robot:x uv run troupe config history --theatre $T; echo "exit $?"
#  exit 2, stderr names TROUPE_ACTOR, nothing printed on stdout
TROUPE_ACTOR= uv run troupe config get a --theatre $T; echo "exit $?"     # exit 2
uv run troupe config get a --reason x --theatre $T; echo "exit $?"       # exit 2
```

Re-running `config history` in a new shell with a different `TROUPE_ACTOR` prints the earlier lines
byte-for-byte unchanged (SC-304).

## What the tests cover

See [contracts/cli.md](contracts/cli.md) for the line format and [data-model.md](data-model.md) for
which unit gets which lineage. The automated suite checks each spec acceptance scenario end-to-end on
real theatres through the real CLI.
