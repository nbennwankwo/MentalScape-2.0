# ADR 0007 Scheduled automation runs on GitHub Actions

- **Status** Proposed
- **Date** 2026-10-13

## Context

The pipeline must download new NHS files every month without anyone remembering to do it. The sandboxes used for development with Claude cannot reach the NHS England website, which was confirmed in Phase 0. GitHub's hosted runners can.

## Decision

Scheduled ingestion, profiling and data tests run as GitHub Actions workflows. Development and review happen locally or with Claude, and anything that needs the internet runs in CI.

## Alternatives considered

- **A cron job on a personal laptop.** Fails whenever the laptop is off.
- **A cloud scheduler.** More moving parts and cost than needed at this stage.

## Consequences

The project gains a free, visible and auditable schedule. Large raw files cannot be stored in git, so Phase 1 must choose where landed files live, for example GitHub Actions artifacts, a release asset or small cloud storage.
