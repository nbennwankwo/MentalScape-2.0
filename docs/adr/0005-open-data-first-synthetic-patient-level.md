# ADR 0005 Build on open data first, with a clearly labelled synthetic patient level layer

- **Status** Accepted (Kemi, 22 October 2026)
- **Date** 2026-10-13

## Context

A discrete event simulation is best calibrated with patient level journeys, meaning when each person was referred, assessed, treated and discharged. That data exists in the record level Mental Health Services Data Set, but access needs a data sharing agreement through the NHS England Data Access Request Service. Applications carry fees, the published pages are written for organisations rather than individuals, and approval is uncertain. An enquiry was sent in October 2026.

## Decision

1. The project depends only on open published data.
2. Where the simulation needs patient level input, it uses **synthetic** journeys generated to match published aggregates such as monthly referral counts and waiting time distributions.
3. The synthetic data follows the same table structure as the relevant MHSDS tables, so that real data could replace it without redesign.
4. Every synthetic table, chart and result is labelled as synthetic wherever it appears.

## Alternatives considered

- **Wait for DARS.** This could take months or never happen.
- **Skip patient level modelling.** This would weaken the simulation, which is the most distinctive part of the project.

## Consequences

The simulation can be built and tested now. Its results are only as good as the published aggregates allow, and the documentation must say so plainly.
