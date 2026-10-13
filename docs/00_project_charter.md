# Project charter

## The problem

NHS mental health services in England are under sustained pressure. Demand has grown faster than capacity, waits are long, and the burden falls unevenly across places and groups of people. The people who plan these services, in Integrated Care Boards (ICBs), NHS trusts and local public health teams, make allocation decisions every year with tools that are mostly backward looking. They see what happened last month. They rarely see what is likely to happen next, why one area differs from another, or what a change in staffing or capacity would actually do to waiting times.

Much of the evidence they need is already published every month as open data. It is hard to use because it is large, inconsistent over time, heavily suppressed at small geographies, and split across many publications.

## The vision

MentalScape 2.0 turns that open data into a decision support tool that a planner can trust and use.

1. It **collects** the right NHS England and ONS files automatically every month.
2. It **stores** them in a SQL warehouse with tests that catch breaking changes in the source data.
3. It **forecasts** demand for each area with honest uncertainty and honest validation.
4. It **simulates** service pathways so that planners can test "what if" changes before committing money.
5. It **recommends** allocations that balance waiting times, cost and fairness between places.
6. It **explains** itself through an interactive dashboard and a question answering assistant that only ever answers from the data.

## Who it is for

The primary users are the people who decide where mental health resources go. They are described in detail in [01_decision_makers.md](01_decision_makers.md).

A secondary audience is employers and reviewers who want to see how the work was done. For them the repository itself, its tests, its decision records and its honesty about limits are part of the product.

## Scope

**In scope**

- Secondary mental health, learning disability and autism services in England, as covered by the Mental Health Services Monthly Statistics
- NHS Talking Therapies, which is published separately and needed for the full picture of demand
- Geography at England, region, ICB and Sub ICB level
- Monthly data from July 2022, when ICBs were created, to the latest release
- Socioeconomic context from the English Indices of Deprivation 2025 and ONS population data

**Out of scope for now**

- Patient level records. These need approval through the NHS England Data Access Request Service. An enquiry has been sent. The design keeps a slot for them so they can be added later without a rebuild (see [ADR 0005](adr/0005-open-data-first-synthetic-patient-level.md)).
- Scotland, Wales and Northern Ireland, which publish different data
- Private sector provision and informal support

## What success looks like

| Area | Measure of success |
|---|---|
| Data | Every monthly release from July 2022 loads with one command, and a changed source file breaks a test rather than silently breaking a model |
| Forecasts | Every model beats a simple baseline on held out months, and the comparison is published |
| Simulation | The simulation reproduces held out months within a stated tolerance before any scenario result is shown |
| Recommendations | Each recommendation shows its trade off between waits, cost and fairness, with uncertainty |
| Users | At least three people who plan or commission services have seen it and said what they would change |
| Engineering | Tests and linting run on every change, and a new person can run the project from the README alone |

## Principles

1. **Honest before impressive.** A smaller claim that holds up beats a large claim that does not.
2. **Reproducible by default.** If it cannot be rerun from source, it does not count.
3. **Decisions are written down.** Every significant choice has a short decision record.
4. **Built for a real user.** Every feature traces back to a question a decision maker actually asks.
5. **Open data, handled carefully.** Even aggregate data can mislead, so suppression, coverage and data quality caveats travel with every number.
