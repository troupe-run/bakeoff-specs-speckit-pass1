<!--
Sync Impact Report
==================
Version change: (unversioned template) → 1.0.0
Bump rationale: first ratification; every placeholder replaced with project content.

Principles (template slot → adopted title):
  - PRINCIPLE_1 → I. The User's Files Are Sacred (NON-NEGOTIABLE)
  - PRINCIPLE_2 → II. Tests That Prove Behaviour (NON-NEGOTIABLE)
  - PRINCIPLE_3 → III. Done Means Verified
  - PRINCIPLE_4 → IV. One Decision, One Place
  - PRINCIPLE_5 → V. Deliver What Was Asked, Invent Nothing
  - added       → VI. Traceability

Added sections:
  - Technical Constraints (template SECTION_2)
  - Development Workflow (template SECTION_3)
  - Governance (filled)

Removed sections: none

Templates reviewed (not modified; they read this file at runtime):
  - .specify/templates/plan-template.md — "Constitution Check" gates derive from
    Principles I–VI and the Technical Constraints; no change needed.
  - .specify/templates/spec-template.md — no conflict.
  - .specify/templates/tasks-template.md — no conflict; note that Principle II makes
    tests mandatory for every behaviour, overriding any "tests are optional" wording.
  - .specify/templates/checklist-template.md — no conflict.

Choices made where the input left room (per Principle V):
  - Ratification date set to 2026-10-01 (date of first adoption; repository has only
    the initial commit).
  - "Where the next person will find them" (decision records) resolved to: the feature's
    Spec Kit artefacts, plus a comment at the one place in code that holds the decision.

Deferred TODOs: none.
-->

# troupe Configuration Subsystem Constitution

troupe runs teams of AI agents. This repository is troupe's configuration subsystem: a
command-line tool over YAML configuration files that people edit by hand and review as diffs.
It is built in stages and its requirements will change between stages. Each stage is built for
what that stage needs, in a shape that is easy to change for the next.

## Core Principles

### I. The User's Files Are Sacred (NON-NEGOTIABLE)

Users are developers who edit configuration by hand and review it as diffs. They value their files
staying exactly as written over speed.

- The tool MUST NOT reformat, reorder, re-indent, re-quote, or otherwise rewrite any part of a
  user's file that the user did not ask to change. Comments, blank lines, key order, quoting style
  and line endings outside the requested change MUST survive byte-for-byte.
- A requested change MUST produce the smallest diff that achieves it.
- When the right behaviour is unclear, the tool MUST take the conservative choice that cannot lose
  or corrupt a user's data (e.g. refuse and explain rather than guess and write), and the choice
  MUST be stated in the spec or plan.
- A write MUST NOT leave a file half-written: either the whole change lands or the file is
  untouched.
- Every error message MUST name the path or file involved.

Rationale: a tool that silently rewrites hand-written configuration destroys the trust and the
review workflow it exists to support.

### II. Tests That Prove Behaviour (NON-NEGOTIABLE)

- Every behaviour MUST have a test that fails when that behaviour breaks.
- A test's name MUST state what it proves, and its body MUST check exactly that — no more, no less.
- A test that would pass whatever the code does MUST NOT be written; it is worse than no test.
  When in doubt, break the behaviour deliberately and confirm the test fails.
- Tests MUST exercise the real shapes the code will meet: real YAML files on disk, real
  `.troupe/` directory layouts, real CLI invocations and their actual output. Hand-written
  stand-ins that might differ from reality MUST NOT replace them.
- File-preservation guarantees (Principle I) MUST be tested by comparing the exact bytes of files
  before and after an operation.

Rationale: tests are the only durable evidence that behaviour holds as requirements change stage
by stage.

### III. Done Means Verified

- Code MUST be fully typed and pass `mypy --strict` with no errors.
- `ruff` (lint and format check) MUST be clean.
- Nothing is reported as working until the test suite, mypy and ruff have been run and their
  results shown. Claims without shown output do not count.
- Failures MUST be reported as failures, with their output; skipped steps MUST be named as
  skipped.

Rationale: "it should work" is not a result. Shown output is.

### IV. One Decision, One Place

- Each decision (a file name, a search rule, a precedence order, an error wording, a default) MUST
  live in exactly one named place in the code — a constant, function, or module — and every use
  MUST refer to it.
- Changing a decision later MUST be a one-place change, not a hunt.
- Build for the current stage only. Do not add speculative features or abstractions for
  imagined future stages; do keep the code shaped so the next stage's change is local.

Rationale: requirements will change between stages; scattered decisions turn each change into a
search for every copy.

### V. Deliver What Was Asked, Invent Nothing

- Deliver the whole of what is asked. Scope MUST NOT be quietly narrowed; if something cannot be
  done, say so explicitly and say why.
- Requirements come from the product owner. Requirements MUST NOT be invented.
- Before asking the product owner, look for the answer in everything reachable: the repository,
  the contract and the documents provided. Questions MUST then include what was found, the
  options, and a recommendation — not only the problem.
- Where the contract leaves a choice open, make the choice, and record what was chosen and why.

Rationale: invented requirements and silent scope cuts both produce something other than what was
asked for, and are found late.

### VI. Traceability

- Specification, code and tests MUST agree. When behaviour changes, all three MUST be updated in
  the same change.
- Significant decisions MUST be recorded with their reasons where the next person will find them:
  requirement choices in the feature's `spec.md`, technical choices in its `research.md` /
  `plan.md`, and a short comment at the one place in code that holds the decision (Principle IV).
- Commits MUST be small and meaningful, and each commit message MUST say why the change was made,
  not only what changed.

Rationale: the next person (or the next stage) must be able to see what the system does, why, and
where that is decided, without archaeology.

## Technical Constraints

These are fixed and are not open to reinterpretation by a feature plan.

- **Language and tooling**: Python 3.12 or later, managed with `uv`.
- **Entry point**: the CLI MUST run as `uv run troupe config …` from the repository root.
- **Event store and projection**: the `eventsourcing` library MUST be used.
- **Configuration location**: `<theatre>/.troupe/troupe.yml` or `<theatre>/.troupe/troupe.yaml`.
- **Platforms**: macOS and Linux. Windows is out of scope.
- **Performance**: there are no performance targets; configurations are small. Correctness and
  file preservation (Principle I) take priority over speed in every trade-off.
- **Quality gates**: `mypy --strict` and `ruff` clean (Principle III).

## Development Workflow

1. **Specify** (`/speckit-specify`, `/speckit-clarify`): capture what the product owner asked for.
   Open questions go to the product owner with findings, options and a recommendation
   (Principle V).
2. **Plan** (`/speckit-plan`): the plan's Constitution Check MUST evaluate every principle above
   and the Technical Constraints. Any violation MUST be justified in the plan's Complexity Tracking
   table or the plan does not proceed.
3. **Tasks** (`/speckit-tasks`): every behaviour in the spec MUST map to at least one test task
   (Principle II); tests are not optional in this project.
4. **Implement** (`/speckit-implement`): commit in small steps with messages that say why
   (Principle VI). Keep spec, code and tests in agreement as work proceeds.
5. **Verify**: run the tests, `mypy --strict` and `ruff`, and show the output before declaring the
   work done (Principle III).

## Governance

- This constitution supersedes other practices and conventions in this repository. Where a
  template or habit conflicts with it, the constitution wins.
- **Amendments** are made with `/speckit-constitution`, MUST state the reason for the change, and
  MUST be committed on their own with a message that says why.
- **Versioning** follows semantic versioning:
  - MAJOR — a principle or constraint is removed or redefined incompatibly.
  - MINOR — a principle or section is added, or guidance is materially expanded.
  - PATCH — clarifications and wording fixes that do not change meaning.
- **Compliance**: every plan's Constitution Check and every review MUST verify compliance with
  these principles. Unjustified complexity or unrecorded deviations are grounds to reject a change.

**Version**: 1.0.0 | **Ratified**: 2026-10-01 | **Last Amended**: 2026-10-01
