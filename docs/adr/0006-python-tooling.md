# ADR 0006 Python tooling

- **Status** Accepted (Kemi, 22 October 2026)
- **Date** 2026-10-13

## Context

MentalScape 1.0 used a local virtual environment with no lock file, no linter, no automated tests and notebooks committed with outputs. That makes the work hard for anyone else to run or trust.

## Decision

| Need | Tool |
|---|---|
| Python version and environment | uv, with a lock file |
| Package layout | `src/mentalscape`, installable |
| Lint and format | ruff |
| Tests | pytest, run in CI on every push |
| Pre commit checks | pre-commit, including a large file guard and notebook output stripping |
| Notebooks | exploration only, outputs stripped |

## Alternatives considered

Conda is familiar from the MSc and handles scientific packages well, but uv is faster, simpler to reproduce in CI and increasingly standard.

## Consequences

One command sets up the project on any machine. Code quality is checked automatically rather than by memory.
