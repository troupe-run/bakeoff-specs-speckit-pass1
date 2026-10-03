# Quickstart / validation guide — Step 2

Run from the repository root. Prerequisites: `uv` and Python 3.12+.

## Quality gates (Principle III)

```sh
uv sync
uv run pytest
uv run mypy --strict src tests
uv run ruff check . && uv run ruff format --check .
```

All must pass, with output shown, before the work is reported done.

## Edits made while nothing runs

```sh
T=$(mktemp -d); mkdir -p "$T/.troupe"
printf 'a: 1\nb: [x, y]\n' > "$T/.troupe/troupe.yml"
uv run troupe config history --theatre "$T"              # 3 import lines
printf '# note\na:   1\nb: [x, y]\n' > "$T/.troupe/troupe.yml"
uv run troupe config show a --theatre "$T"               # 1; no event (comment/format only)
printf 'a: 2\nb: [x]\n' > "$T/.troupe/troupe.yml"
uv run troupe config history --theatre "$T"              # still 3 lines: history never reconciles
uv run troupe config show a --theatre "$T"               # 2
uv run troupe config history --theatre "$T"              # + set a 1→2, + remove b.1
```

## Live sync

```sh
uv run troupe config watch --theatre "$T" &  W=$!        # prints: watching <T>
printf 'a: 3\nb: [x]\n' > "$T/.troupe/troupe.yml"; sleep 2
uv run troupe config history a --theatre "$T"            # ends with set a 2→3
uv run troupe config set a 4 --theatre "$T"; sleep 3
uv run troupe config history a --theatre "$T"            # exactly one more line: set a 3→4
printf 'a: 4\nb: [x]\nc: file:c.yaml\n' > "$T/.troupe/troupe.yml"
printf 'k: v\n' > "$T/.troupe/c.yaml"; sleep 2
uv run troupe config history c --theatre "$T"            # set c.k (null → v)
printf 'a: [\n' > "$T/.troupe/troupe.yml"; sleep 1       # stderr: one error naming troupe.yml
printf 'a: 5\n' > "$T/.troupe/troupe.yml"; sleep 2       # set a 4→5, remove b.0, remove c.k
kill -INT $W; wait $W; echo $?                           # 0
```

The automated suite encodes each step as an end-to-end test (see `tasks.md` once generated).
