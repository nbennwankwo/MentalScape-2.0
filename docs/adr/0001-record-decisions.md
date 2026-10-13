# ADR 0001 Record significant decisions as ADRs

- **Status** Accepted
- **Date** 2026-10-13
- **Decided by** Kemi Ben-Nwankwo

## Context

MentalScape 1.0 made many sound choices, but the reasons were scattered across notebooks and chat history. When a choice is questioned months later, by an examiner, an employer or a future collaborator, the reasoning needs to be easy to find.

## Decision

Every significant decision is written as a short Architecture Decision Record in `docs/adr`, numbered in order. Records are never rewritten. A changed decision gets a new record that supersedes the old one.

## Alternatives considered

A single decisions log file was simpler but becomes long and hard to link to.

## Consequences

A little writing for each big choice. In return, the project can always answer the question "why did you do it this way".
