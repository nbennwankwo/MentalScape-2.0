# ADR 0002 Use a SQL warehouse built with PostgreSQL and dbt

- **Status** Accepted in principle (use SQL, decided by Kemi). Tool choice proposed.
- **Date** 2026-10-13

## Context

MentalScape 1.0 held its data in CSV files and pandas notebooks. That made it hard to rerun, hard to test and easy to break silently when NHS England changed a file. The project also needs to demonstrate real data engineering, and SQL is the shared language of data teams in the NHS and in industry.

## Decision

1. Store all data in **PostgreSQL**, in three schemas called raw, staging and marts.
2. Write every transformation in SQL with **dbt**, so that each model is version controlled, documented and tested.
3. Use **DuckDB** locally for profiling and quick exploration. Its SQL is close enough to PostgreSQL that queries move across with little change.

## Alternatives considered

- **DuckDB only.** Simpler and very fast, but a single file database is a weaker demonstration of a production warehouse and is harder to serve to a live dashboard with several users.
- **A cloud warehouse such as BigQuery or Snowflake.** Strong for a CV, but adds cost and account setup, and the data volume here does not need it.
- **SQLite.** Too limited for analytical SQL and concurrent access.

## Consequences

The project gains tested, documented, rerunnable transformations and a realistic warehouse. It needs a PostgreSQL instance, locally through Docker and later a small hosted one.
