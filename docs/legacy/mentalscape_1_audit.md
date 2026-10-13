# Audit of MentalScape 1.0

MentalScape 1.0 was the MSc Data Science dissertation at Loughborough University, submitted on 18 September 2025 and awarded a Distinction. It integrated machine learning, discrete event simulation and socioeconomic data across 106 Sub ICBs for July 2022 to June 2025.

This audit was carried out in October 2026 by reading the old project folder without changing it. Its purpose is to carry forward what was good and to fix what would not survive scrutiny.

## What the folder contains

| Part | Contents |
|---|---|
| Code | 7 Python modules, about 5,600 lines, covering cleaning, data quality, the IMD and ONS processor, the metric builder, a Midlands simulation and ML preprocessing |
| Notebooks | 9 numbered notebooks from integration to validation, the largest about 22 MB because outputs are saved inside |
| Data | about 8.3 GB of monthly MHSDS, Talking Therapies and out of area placement CSVs, plus IMD 2019, LSOA 2011 lookups, workforce and income files |
| Results | outputs for nine research questions, the simulation and the validation framework, with a duplicate `results copy` folder |
| Dashboard | a Streamlit dashboard specification written in September 2025, not built |
| Version control | none, the folder is not a git repository |

## What to keep

| Idea | Why it is worth keeping |
|---|---|
| Comparing models with and without socioeconomic features | A fair and useful research question. The honest result, that socioeconomic features helped on average but made 76.2 percent of metrics worse, is more interesting than a clean win |
| Sub ICB level analysis | The right level for planners, and still the most stable geography after the 2026 mergers |
| Discrete event simulation of pathways | The most distinctive part of the project and the one decision makers would value most |
| Triangulated validation, comparing simulation output with observed months | A strong idea that deserves to be automated |
| The finding that staff skills may matter more than capacity | Worth testing properly, it is question W2 in the decision maker list |
| Measure categorisation work | A useful starting point for the measure catalogue |

## What to rebuild properly

| Issue found | What 2.0 does instead |
|---|---|
| The 97.7 percent cross sectional accuracy, with household income (GDHI) carrying 87 to 92 percent of feature importance, is likely to reflect population size or area structure rather than true predictive skill. The dissertation itself notes the figure may be specific to the dataset | Every model is compared against simple baselines, including a population only model, using time based validation |
| In the simulation results, capacity factors of 3.0 and 4.0 give identical outputs, which suggests a cap or a bug | Simulation code gets unit tests and a check that more capacity never makes things worse without explanation |
| The validation summary shows June 2025 failing with a 16.3 percent referral gap | Validation thresholds are set before results are seen and failures are reported, not just passes |
| The simulation covers the Midlands only | Built for any region from the start |
| The dissertation abstract calls the data the "NHS Mental Health Services Dataset". The data used was the published Monthly Statistics, which are aggregates of that dataset | Precise naming everywhere. The record level dataset is only ever mentioned as a separate, unavailable source |
| IMD 2019 on 2011 LSOA boundaries | Indices of Deprivation 2025 on 2021 boundaries, treated as a new snapshot |
| No version control, no tests, notebooks with outputs | Git from day one, tests in CI, outputs stripped |

## New issues found in the legacy data during Phase 0

These were found by the profiling code in this repository and are documented in the [change log](../data/mhsds_change_log.md).

1. **Mixed formats inside one file.** All twelve monthly files for April 2023 to March 2024 contain two blocks of rows with different date styles (`2023-08-01` and `01/08/2023`), and in eleven of them the blocks also use different line endings. The blocks hold different measures and do not overlap, so no rows are duplicated, but any code that parses dates with one format would silently drop about a sixth of each file. The End of Year Final files for 2025-26, downloaded directly from NHS England in October 2026, also mix line endings, so this appears to be how NHS England assembles its final files rather than a fault in the local copies.
2. **Mixed release versions.** The 2023-24 files are End of Year Final versions, while the 2024-25 files are the earlier Performance versions, even though End of Year Final versions exist for 2024-25. Mixing versions matters, because a final file can carry a different measure list and different values from the first publication of the same month.
3. **A method change inside the training window.** NHS England changed the method for MHS30f, attended contacts with community mental health services, in May 2025. Its England value roughly tripled between April and May 2025, after falling by about two thirds when MHSDS version 6 arrived in April 2024. Any 1.0 model that used MHS30f was trained across two breaks.
4. **Strong school holiday seasonality.** Referrals to children and young people's services fall by about 40 percent every August and recover in September. Models without school term effects will misread this as noise.

## How to talk about 1.0 now

MentalScape 1.0 was a strong piece of MSc research that asked the right questions. MentalScape 2.0 is the version that a planner could rely on. It answers the same questions with reproducible engineering, stricter validation and a clearer account of what the data can and cannot support. Being open about what changed and why is a strength in interviews, not a weakness.
