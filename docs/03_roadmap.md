# Roadmap

The timeline assumes about 10 to 15 hours a week. Dates are targets, not promises. Each phase ends with something an employer could look at.

## Phase 0, foundations (October 2026)

| Item | Status | Where |
|---|---|---|
| Project charter with problem, users, scope and success measures | done | [00_project_charter.md](00_project_charter.md) |
| Decision maker personas and the questions they ask | done | [01_decision_makers.md](01_decision_makers.md) |
| Target architecture | done | [02_architecture.md](02_architecture.md) |
| Data source register | done | [04_data_sources.md](04_data_sources.md) and `config/sources.yaml` |
| Data governance statement | done | [05_data_governance.md](05_data_governance.md) |
| Ways of working, including how to work with Claude | done | [06_ways_of_working.md](06_ways_of_working.md) |
| Decision records for the first big choices | done | [adr/](adr/) |
| Audit of MentalScape 1.0, what to keep and what to fix | done | [legacy/mentalscape_1_audit.md](legacy/mentalscape_1_audit.md) |
| MHSDS release change log, July 2022 to August 2026 | done | [data/mhsds_change_log.md](data/mhsds_change_log.md) |
| Repository, licence, tooling, tests and CI | done | repository root |
| Interview guide and outreach message for planners | done | [research/interview_guide.md](research/interview_guide.md) |
| DARS enquiry for patient level MHSDS | sent by Kemi | email |
| Three to five conversations with planners | to do, Kemi | notes go in `docs/research/` |
| Portfolio site skeleton | to do | needs a second repository, `nbennwankwo.github.io` |

## Phase 1, data engineering (weeks 2 to 4)

- Automated discovery and download of every MHSDS monthly release, including End of Year Final reissues, on GitHub Actions
- Checksummed manifest of every file and version
- PostgreSQL warehouse with raw, staging and mart layers built in dbt
- Geography harmonisation across the April 2023 local authority changes and the April 2026 ICB mergers
- Release version handling, preferring End of Year Final over Performance where both exist
- Data tests driven by the change log findings
- Talking Therapies, Indices of Deprivation 2025 and ONS population loaded

**Visible result** one command, or one scheduled job, rebuilds the whole warehouse from source.

## Phase 2, forecasting and equity (weeks 5 to 7)

- Seasonal naive and simple statistical baselines for every series
- Models with time based validation only, never random splits
- School term and financial year effects
- Equity indicators by deprivation and ethnicity, with standardisation
- Peer groups of similar ICBs and Sub ICBs
- Model cards stating purpose, data, performance against baseline and limits

**Visible result** a forecast page per area that shows its error against a baseline.

## Phase 3, simulation (weeks 8 to 10)

- Discrete event simulation for at least one adult and one children's pathway, for every region rather than only the Midlands
- Calibration from published activity and waiting time measures
- Validation on held out months, with a pass mark set before results are seen
- Scenario engine for staffing, capacity and demand changes
- Clearly labelled synthetic patient level layer shaped like MHSDS, ready to be swapped for real data if DARS access is granted

## Phase 4, serving and dashboard (weeks 11 to 13)

- API over model outputs
- Interactive dashboard built around the decision maker questions
- Recommendation view with trade offs and uncertainty
- Deployed with Docker and continuous delivery

## Phase 5, GenAI analyst (weeks 14 to 16)

- Plain English questions answered through read only SQL on approved tables
- Every answer shows its query, its source release and any data quality caveat
- Test set of realistic questions with expected answers, run in CI

## Phase 6, polish and share (week 17 onwards)

- Case study write up, demo video and portfolio page
- Accessibility review of the dashboard
- Submissions to relevant student and early career awards
