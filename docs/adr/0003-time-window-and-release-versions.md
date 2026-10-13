# ADR 0003 Start in July 2022 and prefer End of Year Final releases

- **Status** Proposed
- **Date** 2026-10-13

## Context

The MHSDS Monthly Statistics run from January 2016. ICBs and Sub ICBs were created on 1 July 2022, and the publication has reported on that geography since then. Earlier months use Clinical Commissioning Groups, which would need a separate mapping.

The Phase 0 change log also showed that NHS England publishes some months twice. The first version is labelled Performance. A later End of Year Final version includes late submissions and corrections. The legacy copies from MentalScape 1.0 mix the two.

## Decision

1. The modelling window starts with July 2022.
2. The raw layer keeps every version of every file, with its label, download date and checksum.
3. The staging layer uses End of Year Final where it exists and Performance otherwise, and records which one was used for every value.

## Alternatives considered

- **Go back to 2016.** More history helps seasonal models, but the CCG to Sub ICB mapping and older measure definitions would add a lot of work and new error. This can be revisited once the core pipeline works.
- **Use only the first published version.** Simpler, but knowingly uses data that NHS England has since corrected.

## Consequences

About four years of monthly data, which is enough for seasonal models but short for long term trends. Every value can be traced to the exact file and version it came from.
