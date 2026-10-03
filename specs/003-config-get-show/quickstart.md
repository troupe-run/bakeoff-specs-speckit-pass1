# Quickstart / validation guide — Step 3

Run from the repository root. Prerequisites: `uv` and Python 3.12+.

## Quality gates (Principle III)

```sh
uv sync
uv run pytest
uv run mypy --strict src tests
uv run ruff check . && uv run ruff format --check .
```

All must pass, with output shown, before the work is reported done.

## Scenario theatre

```sh
T=$(mktemp -d); mkdir -p "$T/.troupe/agents" "$T/.troupe/prompts"
cat > "$T/.troupe/troupe.yml" <<'EOF'
# main
model: {temperature: 0.2, name: 'opus'}
agents:
  coder: file:agents/coder.yaml
prompt: file:prompts/system.md
EOF
printf 'model: sonnet\ntools: [git, shell]\n' > "$T/.troupe/agents/coder.yaml"
printf 'Be terse.\nNo jokes.\n' > "$T/.troupe/prompts/system.md"
```

## `get`

```sh
uv run troupe config get model.temperature --theatre "$T"   # 0.2
uv run troupe config get prompt --theatre "$T"              # Be terse.\nNo jokes.\n exactly
uv run troupe config get agents.coder --theatre "$T"; echo $?   # 5; stderr mentions `config show`
```

## `show`

```sh
uv run troupe config show model.temperature --theatre "$T"  # 0.2 (same as get)
uv run troupe config show --theatre "$T"                    # spec User Story 2, scenario 2
uv run troupe config show agents.coder --theatre "$T"       # model: sonnet / tools: / - git / - shell
uv run troupe config show --sources --theatre "$T"          # spec User Story 3, scenario 1
uv run troupe config show model.temperature --sources --theatre "$T"  # 0.2 # from .troupe/troupe.yml
```

Expected layouts: [contracts/cli.md](contracts/cli.md).

## Read-back check

```sh
uv run troupe config show --sources --theatre "$T" \
  | uv run python -c 'import sys; from ruamel.yaml import YAML; print(YAML(typ="safe").load(sys.stdin))'
# {'model': {'temperature': 0.2, 'name': 'opus'}, 'agents': {...}, 'prompt': 'Be terse.\nNo jokes.\n'}
```

## Files untouched

`get` and `show` must leave every file under `$T` byte-identical (the test suite compares
`Theatre.snapshot()` before and after).
