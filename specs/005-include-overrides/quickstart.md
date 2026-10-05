# Quickstart: validate step 5 (include overrides)

Prerequisites: `uv sync` at the repository root.

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
printf 'model: opus\nlimits: {retries: 2}\ntools: [git]\n' > $T/.troupe/agents/coder.yaml
cp $T/.troupe/agents/coder.yaml /tmp/coder.before

uv run troupe config set agents.coder.temperature 0.3 --theatre $T
cat $T/.troupe/troupe.yml
#  agents:
#    coder:  # c
#      $ref: file:agents/coder.yaml
#      temperature: 0.3
cmp $T/.troupe/agents/coder.yaml /tmp/coder.before && echo "shared file untouched"

uv run troupe config set agents.coder.limits.timeout 30 --theatre $T   # override in troupe.yml
uv run troupe config show agents.coder --sources --theatre $T
#  retries/model/tools from .troupe/agents/coder.yaml; temperature/timeout from .troupe/troupe.yml

uv run troupe config set agents.coder.model sonnet --theatre $T        # not overridden → coder.yaml
uv run troupe config set agents.coder.temperature 0.5 --theatre $T     # overridden → troupe.yml
uv run troupe config set agents.coder.tools.1 lint --theatre $T        # list append → coder.yaml

printf 'p: {$ref: file:p.md, x: 1}\n' >> $T/.troupe/troupe.yml; echo hi > $T/.troupe/p.md
uv run troupe config get agents.coder.model --theatre $T; echo "exit $?"   # exit 4, names troupe.yml
```

## What the tests cover

See [contracts/cli.md](contracts/cli.md) for the file format and placement table and
[data-model.md](data-model.md) for the merge and placement rules. The automated suite checks each
spec acceptance scenario end-to-end on real theatres, comparing the bytes of every file.
