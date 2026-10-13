# Ways of working

## Roles

**Kemi is the product owner.** She decides what gets built, in what order, and whether it is good enough. She talks to users, approves decision records and reviews every change before it reaches `main`.

**Claude works as the delivery team.** Depending on the task that means data engineer, data scientist, simulation modeller, software engineer, UX designer, technical writer or sceptical reviewer. Claude explains before building, flags risks early and never claims more than the evidence supports.

## How to ask for work

You do not need clever prompts. Give three things.

1. **Goal**, what you want to exist when the work is finished
2. **Context and constraints**, anything that limits how it should be done
3. **Done means**, how we will both know it is finished

An example.

> Phase 1. Build the step that finds every MHSDS release page and downloads the main data file. Constraint, it must run on GitHub Actions. Done means a manifest lists every month from July 2022 with a checksum, and a test fails if a month is missing.

Other useful phrases

- "Explain it first, then build it" when the topic is new
- "Give me the options and your recommendation" when a decision is needed
- "Play the commissioner and challenge this" to test a feature against a user
- "Recap quiz" at the end of a session to go over what was learned again

## Session routine

**Start of a session.** Claude reads `CLAUDE.md`, the [roadmap](03_roadmap.md) and the latest [decision records](adr/), then states what it understands the next step to be.

**End of a session.** Claude updates the roadmap status, writes any new decision record, adds a line to `CHANGELOG.md`, and offers a short recap quiz.

## Git workflow

1. `main` always works. Nobody commits to it directly once the project is set up.
2. Each piece of work gets a branch named after what it does, for example `feat/mhsds-downloader` or `fix/date-parsing`.
3. Commits are small and say what changed and why.
4. A pull request is opened for every branch. CI must pass. Kemi reviews and merges.

## Definition of done

A change is done when

- the code has tests and `make check` passes
- the docs describe the new behaviour
- any significant choice has a decision record
- no data, secrets or notebook outputs are committed
- the roadmap reflects the new status

## Decision records

Significant choices are written as short Architecture Decision Records in [`docs/adr`](adr/). Each one states the context, the decision, the alternatives considered and the consequences. A decision is changed by writing a new record that supersedes the old one, never by editing history.

## Code style

- Python 3.12, formatted and linted with ruff
- British spelling in names, comments and docs
- No emoji or decorative symbols in code, comments, docstrings or printed output
- Prose in docs avoids colons and semicolons where possible
- Notebooks are for exploration only. Anything that matters moves into `src/` with tests
