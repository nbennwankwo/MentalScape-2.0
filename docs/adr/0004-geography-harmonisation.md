# ADR 0004 Harmonise geography across boundary changes

- **Status** Accepted (Kemi, 22 October 2026)
- **Date** 2026-10-13

## Context

The Phase 0 change log found three kinds of geography change between July 2022 and August 2026.

1. **ICB mergers from 1 April 2026.** Twelve ICBs were replaced by six new ones, taking England from 42 ICBs to 36. Frimley's Sub ICB disappeared and a new Thames Valley Sub ICB appeared. Twenty three Sub ICBs kept their code but now sit under a different ICB, so their published names changed.
2. **Local government reorganisation from 1 April 2023.** Cumbria, North Yorkshire and Somerset county and district councils were replaced by new unitary authorities.
3. **Label drift.** The same geography appears under several labels, for example "Sub ICB - GP Practice or Residence", "Sub ICB of GP Practice or Residence" and "Sub ICB of Residence". No measure appears under two labels in the same release.

## Decision

1. Map every published label onto five canonical levels, which are England, Commissioning Region, ICB, Sub ICB and Local Authority, plus Provider.
2. Treat the **Sub ICB code** as the stable building block, because most codes survived the 2026 mergers.
3. Keep a dated lookup table of Sub ICB to ICB membership, so any month can be shown on either the old or the new ICB boundaries.
4. Areas that were split, such as Frimley, are flagged and are not forced into a false continuous series.

## Alternatives considered

Rebuilding every series from LSOA level would be more exact, but the published data is not available at that level.

## Consequences

Trends can run across the 2026 mergers for most areas. A small number of split areas carry a break that is shown to users rather than hidden.

## Implementation note, 22 October 2026

Built in Phase 1 as `int_geo__sub_icb_monthly` and `geo_sub_icb_membership` in the warehouse. The ICB of each Sub ICB is read from the parent ICB named in the Sub ICB's own label, checked against that month's ICB rows. The March 2026 End of Year Final file gives 23 Sub ICBs only their post merger names, so for that file the ICB from the previous release is carried forward and labelled as such. Local authority harmonisation for the April 2023 changes is still to do and needs the ONS lookup.
