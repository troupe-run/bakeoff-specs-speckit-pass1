# Quickstart: validate step 7 (remote includes and a schema)

Prerequisites: `uv sync` at the repository root (installs `jsonschema`), and `python3` for a local
web server.

## Gates (Principle III: run them and show the output)

```sh
uv run pytest
uv run mypy --strict src tests
uv run ruff check . && uv run ruff format --check .
```

## Manual walk-through

```sh
T=$(mktemp -d); W=$(mktemp -d); mkdir -p $T/.troupe
printf 'coder:\n  model: opus\n  tools: [git]\n' > $W/agents.yaml
printf 'Be brief.\n' > $W/system.md
(cd $W && python3 -m http.server 8765 --bind 127.0.0.1 >/dev/null 2>&1 &)
printf 'agents: http://127.0.0.1:8765/agents.yaml  # team\nprompt: http://127.0.0.1:8765/system.md\n' > $T/.troupe/troupe.yml

uv run troupe config get agents.coder.model --theatre $T          # opus
uv run troupe config get prompt --theatre $T                      # Be brief.
uv run troupe config show agents --sources --theatre $T           # # from http://127.0.0.1:8765/agents.yaml

# A URL setting with no schema is an include: every command now fetches it.
printf 'api:\n  endpoint: https://api.example.com/v1\n' >> $T/.troupe/troupe.yml
uv run troupe config get prompt --theatre $T; echo "exit $?"      # exit 4 unless api.example.com/v1 can be fetched

cat > $T/.troupe/troupe.schema.json <<'JSON'
{"properties": {"api": {"properties": {"endpoint": {"type": "string", "format": "uri"}}},
                "temperature": {"type": "number"}}}
JSON
uv run troupe config get api.endpoint --theatre $T                # https://api.example.com/v1, nothing fetched

uv run troupe config set agents.coder.model sonnet --theatre $T; echo "exit $?"
# exit 3; stderr contains http://127.0.0.1:8765/agents.yaml and "line 1 of .troupe/troupe.yml"
uv run troupe config set agents.coder.temperature 0.3 --theatre $T   # local override in troupe.yml

uv run troupe config set temperature warm --theatre $T; echo "exit $?"  # exit 3, names the schema
uv run troupe config set docs https://example.com/guide --theatre $T
grep docs $T/.troupe/troupe.yml                                   # docs: !literal https://example.com/guide
uv run troupe config set api.endpoint https://api.example.com/v2 --theatre $T   # written untagged

kill %1 2>/dev/null; pkill -f "http.server 8765"
uv run troupe config get agents.coder.model --theatre $T; echo "exit $?"   # exit 4, names the URL
```

## What the tests cover

See [contracts/cli.md](contracts/cli.md) for formats and outcomes and [data-model.md](data-model.md)
for the classification and refusal rules. The automated suite serves fixtures from a local HTTP and
HTTPS server (research U-11). It checks each spec acceptance scenario end to end on real theatres,
comparing the bytes of every file and counting server requests where nothing may be fetched.
