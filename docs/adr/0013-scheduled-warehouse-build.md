# ADR 0013 Rebuild the whole warehouse on a schedule and publish the result

- **Status** Proposed
- **Date** 2026-10-22
- **Proposed by** Claude, for Kemi Ben-Nwankwo to accept

## Context

Phase 1's visible result is that one command, or one scheduled job, rebuilds the whole warehouse from source. `make warehouse` does this on a laptop. The pull request checks only build the small synthetic fixture, so nothing yet proves the full real build still passes after each new release, and no one can use the warehouse without building it first.

## Decision

1. A `Build warehouse` workflow runs after any ingest workflow finishes on `main`, every Saturday, and by hand. It fetches every source from the data releases, loads them into DuckDB and runs `dbt build`, so every model and every data test runs on all real months.
2. The job fails on any dbt error. Warnings, such as large month to month jumps, are listed in the job summary for a person to read.
3. The built DuckDB file is compressed and published to a `warehouse-latest` release, replacing the previous build, together with the build summary and dbt's `run_results.json`. Anyone can download it and query it straight away.
4. The full build runs on DuckDB. PostgreSQL stays proven on every pull request with the fixture (ADR 0010) and takes over in production in Phase 4.

## Alternatives considered

- **Build on PostgreSQL in the scheduled job.** Proves PostgreSQL on real volumes, but takes much longer and leaves nothing reusable behind, because the database disappears with the runner.
- **Commit the built database.** Breaks the rule that data never goes into git.

## Consequences

A broken release, a new date style or a geography change shows up within a day as a failed run and an email, rather than when someone next builds by hand. The published warehouse holds only published aggregate statistics, the same as the raw releases.
