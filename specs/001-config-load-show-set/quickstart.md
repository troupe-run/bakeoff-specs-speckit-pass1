# Quickstart / validation guide — Step 1

Run from the repository root. Prerequisites: `uv` and Python 3.12+.

## Quality gates (Principle III)

```sh
uv sync
uv run pytest
uv run mypy --strict src tests
uv run ruff check . && uv run ruff format --check .
```

All four must pass, with their output shown, before the work is reported done.

## Manual end-to-end walk-through

```sh
T=$(mktemp -d); mkdir -p "$T/.troupe/agents" "$T/.troupe/prompts"
cat > "$T/.troupe/troupe.yml" <<'EOF'
# troupe theatre
model:
  name: 'opus'
  temperature: 0.2   # creative
tools: [git, shell]
agents:
  coder: file:agents/coder.yaml
prompt: file:prompts/system.md
EOF
printf 'model: sonnet\nretries: 2\n' > "$T/.troupe/agents/coder.yaml"
printf 'Be terse.\n' > "$T/.troupe/prompts/system.md"
cp -r "$T/.troupe" "$T/orig"
```

| Step | Command | Expected |
|---|---|---|
| 1 | `uv run troupe config show model.temperature --theatre "$T"` | `0.2`, exit 0 |
| 2 | `uv run troupe config show agents.coder.model --theatre "$T"` | `sonnet` |
| 3 | `uv run troupe config show prompt --theatre "$T"` | `Be terse.` |
| 4 | `uv run troupe config show tools --theatre "$T"` | exit 5, stderr names `tools`, stdout empty |
| 5 | `uv run troupe config history --theatre "$T"` | 7 `import` lines, seq 1–7 |
| 6 | `uv run troupe config set model.temperature 0.75 --theatre "$T"` | exit 0; `diff -r "$T/orig" "$T/.troupe"` (ignoring `events.sqlite3*`) shows only `  temperature: 0.75  # creative` |
| 7 | `uv run troupe config set model.name sonnet --theatre "$T"` | line becomes `  name: 'sonnet'` |
| 8 | `uv run troupe config set tools.2 lint --theatre "$T"` | line becomes `tools: [git, shell, lint]` |
| 9 | `uv run troupe config set agents.coder.retries 3 --theatre "$T"` | only `agents/coder.yaml` changes |
| 10 | `uv run troupe config set agents.coder '{a: 1}' --theatre "$T"` | exit 3, no file changes |
| 11 | `uv run troupe config set prompt '"Be kind.\n"' --theatre "$T"` | `system.md` is exactly `Be kind.\n` |
| 12 | `uv run troupe config history model --theatre "$T"` | import lines for `model.*` plus the two `set` lines |
| 13 | `uv run troupe config set model.temperature 0.75 --theatre "$T"` | exit 0, no file change, no new event |

Error checks: remove `troupe.yml` → any command exits 4; create both `troupe.yml` and
`troupe.yaml` → exit 4; point an include at a missing file → exit 4.

The automated suite encodes each of these as byte-comparison tests (see `tasks.md` once generated).
