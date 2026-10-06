# Bug Verification: Setting a value reached through a YAML alias changes the anchor (and every other alias)

- **Slug**: yaml-alias-set
- **Tested**: 2026-10-06
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The reported symptom no longer reproduces. `set coder.settings.model sonnet` now exits 3, mentions
`--expand-alias` and leaves the file unchanged. Every other reproduction step from the assessment behaves
as the Aliases contract requires. The new tests, the full suite, lint and the type check all pass on commit
`8ec062d`.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction: the reported case (step 2) | `troupe config set coder.settings.model sonnet` on the issue's `troupe.yml` | pass | exit 3, stderr mentions `--expand-alias`, file byte-identical |
| Reproduction: new key through an alias (step 3) | `set coder.settings.temperature 0.2` | pass | exit 3, file unchanged |
| Reproduction: anchored scalar (step 4) | `set m 6` / `set y 7` with `m: &x 5`, `y: *x` | pass | `m: &x 6` (anchor kept, `y` follows it); `y: 7` replaces only the alias |
| Reproduction: replacing the alias itself (step 5) | `set coder.settings '{a: 1}'` | pass | only `coder.settings` changes; `defaults: &d` and `reviewer.settings: *d` untouched |
| Reproduction: `--expand-alias` exists (step 6) | `set --expand-alias coder.settings.model sonnet` | pass | `settings:  # expanded from *d by troupe` then `model: sonnet`; `reviewer.settings: *d` still an alias |
| Contract: setting at the anchor | `set defaults.model sonnet` | pass | only the anchored line changes; the aliases follow |
| New tests | `uv run pytest tests/e2e/test_set_alias.py` | pass | 13 passed (12 of them failed with `src/` at the pre-fix HEAD, per fix.md) |
| Regression suite | `uv run pytest` | pass | 795 passed, 1 skipped |
| Lint / type-check | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src tests` | pass | all clean |

## Output Excerpts

```text
## set coder.settings.model sonnet -> exit 3; changed=False
   stderr: troupe: error: coder.settings.model: goes through the alias *d in …/troupe.yml; changing it
   would change &d and every alias of it. Use `set --expand-alias` to give it its own copy first
## set --expand-alias coder.settings.model sonnet -> exit 0; changed=True
   coder:
     settings:  # expanded from *d by troupe
       model: sonnet
   reviewer:
     settings: *d

tests/e2e/test_set_alias.py: 13 passed in 6.34s
full suite: 795 passed, 1 skipped in 265.10s
```

## Residual Risks

- `<<` merge keys are still read as ordinary keys rather than merged. Writes through them are refused,
  which meets "never written", but reading them is outside this fix.
- An alias inside a flow collection cannot be expanded (exit 3, "expand it by hand"). Neither can an
  expansion whose change would land in another file.
- Replacing the alias node itself is allowed, not refused. The contract does not settle this; it is the
  open question in assessment.md.
- The composer subclass depends on ruamel's `Composer.compose_node` and node `__slots__`; a ruamel upgrade
  could break it. The e2e tests would catch that.
- Recursive anchors were already unsupported before this fix and still are.

## Recommendation

Close the bug: it is verified end-to-end. The issue's exact scenario and every reproduction step in the
assessment were run through the real CLI on the committed code. The contract's open question (whether
replacing an alias node itself should also be refused) can be decided separately if the maintainers want
the stricter behaviour.
