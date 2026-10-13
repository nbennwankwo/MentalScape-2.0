# Notes for Claude

Read this file at the start of every session on this repository.

## The project

MentalScape 2.0 is a decision support tool for NHS mental health service planning in England, built on open NHS England and ONS data. It is the professional rebuild of Kemi's MSc dissertation, MentalScape 1.0. The full context is in `docs/00_project_charter.md`.

## Who decides

Kemi Ben-Nwankwo is the product owner and approves every merge to `main` and every decision record. Claude proposes, builds, explains and challenges. Claude marks its own technical recommendations as **Proposed** in decision records until Kemi accepts them.

## How Kemi likes to work

- Explain simply and in depth. Repetition helps her learn, so recap key ideas.
- Analogies only when she says an explanation has not landed.
- British spelling everywhere.
- In code, no emoji, tick marks or decorative symbols in print statements, docstrings or comments.
- In prose written for her, avoid colons and semicolons.
- Disagree honestly when needed, without a combative tone.

## Where things are

| Path | What |
|---|---|
| `src/mentalscape/` | Python package |
| `src/mentalscape/profiling/` | MHSDS release profiler and change log builder |
| `tests/` | pytest tests, synthetic fixtures only |
| `config/sources.yaml` | data source register read by the pipeline |
| `docs/03_roadmap.md` | phase plan and current status |
| `docs/adr/` | decision records |
| `docs/data/mhsds_change_log.md` | what changed in the source data and what it means |
| `data/reference/` | small committed reference tables |

## Commands

```
make setup      # uv environment and git hooks
make check      # ruff and pytest, as CI does
make profile    # profile MHSDS files in data/raw/mhsds_monthly
make changelog  # rebuild the change log and reference tables
```

## Rules

1. Never commit data, secrets or notebook outputs.
2. Every change has tests and passes `make check`.
3. Significant choices get a decision record in `docs/adr`.
4. Respect suppression. Never back calculate a value published as an asterisk.
5. Keep caveats with numbers, for example NHS England's warnings about MHS148 and EIP68.
6. The development sandbox cannot reach the NHS England website. Anything that needs to download runs in GitHub Actions.

## Session routine

At the start, read this file, `docs/03_roadmap.md` and the newest decision records, then say what the next step is. At the end, update the roadmap status and `CHANGELOG.md`, and offer a short recap quiz.
