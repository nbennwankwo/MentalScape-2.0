# Decision makers and the questions they ask

This page describes who MentalScape 2.0 is for, what decisions they make, and the questions they bring. It is written from public knowledge of how NHS mental health planning works. It is a working hypothesis, not evidence. The interviews planned in [research/interview_guide.md](research/interview_guide.md) exist to test and correct it.

Each question carries an ID so that features, dashboard pages and model outputs can point back to the need they serve.

## 1. ICB commissioner for mental health

**Who** works for an Integrated Care Board and holds the budget for mental health services for a population of roughly one to three million people.

**Decisions** where to invest or disinvest across services and places, which providers to commission, how to meet national standards within a fixed budget.

**Pressures** a fixed allocation, national targets on access and waiting times, scrutiny from the ICB board, and since April 2026 a new ICB footprint for some areas after mergers.

| ID | Question | Why it matters |
|---|---|---|
| C1 | Where will demand outgrow capacity over the next 12 months, and by how much? | Gives time to act before waits grow |
| C2 | If I move money or staff from one service or place to another, what happens to waits? | Every investment has an opportunity cost |
| C3 | Which of my places are furthest from fair access relative to need? | Boards ask about inequalities and must report on them |
| C4 | How do we compare with similar ICBs, not just with England? | A fair comparison needs similar populations |
| C5 | Is this change real or is it a data quality problem? | Decisions made on bad data waste money |

## 2. Trust operational or service manager

**Who** runs community or inpatient mental health services in an NHS trust.

**Decisions** rotas, caseloads, where to put extra capacity, how to clear waiting lists.

| ID | Question | Why it matters |
|---|---|---|
| O1 | Where in the pathway do people wait longest, assessment or treatment? | Capacity added in the wrong place does nothing |
| O2 | How many more staff would bring a waiting list down by a given amount, and by when? | Turns a target into a plan |
| O3 | What happens to the queue in August and September when children's referrals drop and then surge? | Seasonal swings can be planned for |
| O4 | How many people are placed out of area, and what would it take to bring them back? | Out of area placements are costly and harmful |

## 3. Workforce planner

**Who** plans recruitment and training for mental health staff across a system.

| ID | Question | Why it matters |
|---|---|---|
| W1 | Which roles are the bottleneck for each pathway? | Recruitment money should follow the bottleneck |
| W2 | Does upskilling existing staff achieve more than adding headcount? | MentalScape 1.0 suggested it might, and that needs a proper test |

## 4. Public health and inequalities lead

**Who** works in a local authority or ICB on population health and health inequalities.

| ID | Question | Why it matters |
|---|---|---|
| P1 | How does access differ by deprivation, ethnicity, age and sex, after allowing for need? | Fair access is a legal and moral duty |
| P2 | Which areas combine high deprivation with low access? | These are the places to target first |
| P3 | Are gaps closing or widening over time? | Shows whether interventions work |

## 5. Board member or executive

**Who** sits on an ICB or trust board and approves strategy.

| ID | Question | Why it matters |
|---|---|---|
| B1 | What is the one page picture, and what do you recommend? | Boards have minutes, not hours |
| B2 | How confident are we in this recommendation? | A board needs to know the risk it is taking |

## How these questions shape the build

| Question IDs | Answered by |
|---|---|
| C1, O3 | Forecasting layer with seasonal and school term effects |
| C2, O1, O2, W1, W2 | Discrete event simulation with scenario controls |
| C3, P1, P2, P3 | Equity layer using deprivation and demographic breakdowns |
| C4 | Peer grouping of ICBs and Sub ICBs by population characteristics |
| C5 | Data quality layer built on the release change log and NHS data quality files |
| O4 | Out of area placements data |
| B1, B2 | Recommendation summary with uncertainty, and the question answering assistant |
