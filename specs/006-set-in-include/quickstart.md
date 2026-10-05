# Quickstart: validate step 5 CR-B (`set --in-include`)

Prerequisites: `uv sync` at the repository root; CR-A implemented.

## Gates (Principle III — run and show the output)

```sh
uv run pytest
uv run mypy --strict src tests
uv run ruff check . && uv run ruff format --check .
```

## Manual walk-through

```sh
T=$(mktemp -d); mkdir -p $T/.troupe/agents
printf 'agents:\n  coder: file:agents/coder.yaml  # c\n' > $T/.troupe/troupe.yml
printf 'model: sonnet\n' > $T/.troupe/agents/coder.yaml
cp $T/.troupe/troupe.yml /tmp/main.before

uv run troupe config set --in-include agents.coder.temperature 0.3 --theatre $T
cat $T/.troupe/agents/coder.yaml          # model: sonnet / temperature: 0.3
cmp $T/.troupe/troupe.yml /tmp/main.before && echo "including file untouched"

uv run troupe config set agents.coder.effort high --theatre $T     # no flag: override (CR-A)
cat $T/.troupe/troupe.yml                 # coder:  # c / $ref: … / effort: high

uv run troupe config set agents.coder.effort low --in-include --theatre $T
#  existing overridden value: the override changes, as without the flag (D-50)

uv run troupe config get a --in-include --theatre $T; echo "exit $?"   # exit 2
```

See [contracts/cli.md](contracts/cli.md) for the full effect table.
