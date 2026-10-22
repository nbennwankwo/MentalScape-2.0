# Data sources

The machine readable version of this register is [`config/sources.yaml`](../config/sources.yaml). This page explains what each source is, why it is used and what to watch out for.

## Mental Health Services Monthly Statistics (MHSDS Monthly)

**What it is.** NHS England's monthly publication built from the Mental Health Services Data Set. It covers people in contact with NHS funded secondary mental health, learning disability and autism services in England. It excludes people who are only in contact with NHS Talking Therapies. The series runs from January 2016.

**What we use.** The main data file of every release from July 2022, the month ICBs were created, plus the out of area placements, referral spells, restrictive interventions and data quality files.

**What it can tell us.** Counts and rates of referrals, contacts, people in contact, waiting, Mental Health Act use, admissions and more, by provider, Sub ICB, ICB, region and England, and increasingly by age, sex, ethnicity and deprivation.

**What it cannot tell us.** NHS England states that the data are known to be incomplete. Differences between areas or over time may come from real differences in illness or services, or from differences in data completeness. Small numbers are suppressed with an asterisk. In the August 2026 release about four in five published values are suppressed, mostly at provider level.

**Versions.** Each month is first published as *Performance* data. For some years NHS England later reissues an *End of Year Final* version that includes late submissions. Release pages list End of Year Final main data files for every month from July 2022 to March 2026. The legacy copies used by MentalScape 1.0 mix the two, with 2023-24 as Final and 2024-25 as Performance. The pipeline keeps both versions and uses the final one when it exists.

**Status.** Collected automatically since October 2026, with every main data file from July 2022 to August 2026 loaded into the warehouse ([pipeline](data/pipeline.md)).

**Licence.** Open Government Licence v3.0.

**Read next.** The full history of how this publication changed between July 2022 and August 2026 is in [data/mhsds_change_log.md](data/mhsds_change_log.md).

## NHS Talking Therapies monthly statistics

**What it is.** The monthly publication for NHS Talking Therapies for anxiety and depression, formerly IAPT. It is a separate dataset from MHSDS and covers a large share of adult mental health demand.

**Why we need it.** Without it the picture of adult demand is incomplete. MentalScape 1.0 used it for the simulation.

**Status.** Collected automatically since October 2026, with every activity file from July 2022 to August 2026 loaded into the warehouse ([pipeline](data/pipeline.md)). Of the 50 months, 11 use the Final version and 39 the Performance version.

**What to watch out for.** No ICB level is published, so ICB figures are built from Sub ICBs. Only counts can be added up, and only where no Sub ICB value is suppressed, which affects about three in four published values, mostly at provider level. Nine NHS England commissioning hubs, mostly for prisons and secure settings, appear among the Sub ICBs but are not places.

## English Indices of Deprivation 2025

**What it is.** The official measure of relative deprivation for 33,755 small areas (LSOAs, 2021 boundaries) in England, published on 30 October 2025. It combines seven domains, and also publishes child and older people indices.

**Why we need it.** Deprivation is one of the strongest known drivers of mental health need. The MHSDS publication now includes its own deprivation breakdowns for some measures, but the full index lets us build need indicators for every area.

**Status.** Collected automatically since October 2026 and summarised for every Sub ICB, ICB and local authority ([pipeline](data/pipeline.md)).

**Caution.** The release itself says it should not be treated as a time series against the 2019 index. It uses new geography, new indicators and new denominators. MentalScape 1.0 used the 2019 index on 2011 boundaries, so this is a replacement, not an update.

## ONS population estimates and geography lookups

**Why we need them.** Rates per 100,000 need populations, and the April 2026 ICB mergers mean areas must be mapped between old and new boundaries. NHS England notes that ONS population figures on the new boundaries are due in autumn 2026.

**What we use.** LSOA estimates by single year of age and sex for mid-2022 to mid-2024, and the ONS lookups from LSOA to Sub ICB, ICB and local authority for July 2022 and every April since 2023, plus the lookups that describe the April 2023 local government changes.

**Status.** Collected automatically since October 2026. Population is built up from LSOAs for every area on each boundary edition, which gives figures on the April 2026 ICB boundaries before ONS publishes its own. Months after mid-2024 use the mid-2024 estimate until the next one appears, and the warehouse says so wherever it does.

## NHS workforce statistics

**Why we need them.** Staffing is the main constraint on capacity, and the simulation needs it. Legacy copies exist. Automated download comes in Phase 3, with the simulation that uses it.

## Patient level MHSDS (not available)

An enquiry has been made to the NHS England Data Access Request Service about pseudonymised record level MHSDS. Approval is uncertain and would take time. The project does not depend on it. See [ADR 0005](adr/0005-open-data-first-synthetic-patient-level.md).
