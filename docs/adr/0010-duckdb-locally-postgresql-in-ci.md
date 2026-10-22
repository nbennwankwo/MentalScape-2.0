# ADR 0010 Run the warehouse on DuckDB locally and PostgreSQL in CI and production

- **Status** Accepted
- **Date** 2026-10-22
- **Decided by** Kemi Ben-Nwankwo (no Docker on the development Mac), tool choice by Claude

## Context

ADR 0002 chose PostgreSQL and dbt for the warehouse and DuckDB for local profiling. Running PostgreSQL on a Mac is easiest with Docker, which is not installed on the main development machine.

## Decision

The dbt project supports two targets with the same models.

1. **`local`** uses DuckDB, a single file database that needs no server. This is how the warehouse is built on a laptop.
2. **`ci`** and later **`prod`** use PostgreSQL. CI starts a PostgreSQL service and builds and tests the whole warehouse on every pull request, so the PostgreSQL version is always proven to work.

Where the two databases need different SQL, for example to parse dates, the difference lives in one small dbt macro rather than in the models.

## Alternatives considered

- **Install Docker Desktop.** Adds a large dependency for one database.
- **Postgres.app on the Mac.** Workable, but still a server to manage, and a DuckDB file is simpler for exploration.
- **DuckDB only.** Loses the demonstration of a production warehouse that a live dashboard can query.

## Consequences

Anyone can build the warehouse locally with one command and no server. Every change is still tested on PostgreSQL. The models must avoid SQL that only one of the two databases supports, and CI enforces this.
