# ADR 0008 Start a new repository and keep MentalScape 1.0 read only

- **Status** Accepted
- **Date** 2026-10-13
- **Decided by** Kemi Ben-Nwankwo

## Context

MentalScape 1.0 was the MSc dissertation, submitted in September 2025. It lives in a 9.3 GB folder that is not under version control and mixes data, notebooks, results and drafts. It is a valuable record of the research, but it is not a foundation that can be cleaned up in place without losing that record.

## Decision

MentalScape 2.0 is a new repository, both on Kemi's computer and on GitHub. The old folder stays untouched as an archive. Useful ideas and logic are carried across deliberately, rewritten with tests, and recorded in [the legacy audit](../legacy/mentalscape_1_audit.md).

## Consequences

A clean history from day one. Nothing is copied blindly, so every inherited idea gets a second look.
