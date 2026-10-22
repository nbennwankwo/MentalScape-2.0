"""Collect NHS Talking Therapies monthly statistics from NHS England.

The publication was called "Psychological Therapies, Reports on the use of IAPT
services" until April 2023 and "NHS Talking Therapies Monthly Statistics
Including Employment Advisors" from May 2023. The two names have separate
series pages, and tools/discover_in_browser.js walks both.

Card titles look like

    IAPT Monthly Activity Data File - July 2022 v2
    IAPT Data Quality Report - August 2022 Primary
    NHS Talking Therapies Monthly Activity Data File - June 2023 Provisional
    NHS Talking Therapies Monthly Activity Data File - July 2025 Final

and the rules below were written against all 380 cards published on release
pages from January 2022 to August 2026, captured in October 2026.

The version is read from the card title, then from the file name, and finally
from the release page title. Before May 2023 each release carried a Final
month and a Primary month. Until October 2023 it carried a Performance month
and a Provisional month. Primary and Provisional are early versions that are
replaced a month later, so they are treated alike.

    python -m mentalscape.ingest.talking_therapies classify --cards talking_therapies_cards.json
    python -m mentalscape.ingest.talking_therapies collect --manifest manifest.csv --out-dir data/interim/ingest
    python -m mentalscape.ingest.talking_therapies check
"""

from __future__ import annotations

import re
from pathlib import Path

from mentalscape.ingest import series
from mentalscape.ingest.classify import (
    MONTH_NUMBER,
    MONTH_RE,
    Classification,
    classify_month,
    classify_revision,
)

# Order matters. The first matching phrase decides the kind.
KIND_RULES: tuple[tuple[str, str], ...] = (
    ("pre-release access", "pre_release_access"),
    ("time series", "time_series"),
    ("rolling quarter", "rolling_quarter"),
    ("quarterly report", "ea_quarterly"),
    ("quarterly reports", "ea_quarterly"),
    ("quarterly activity", "quarterly_activity"),
    ("activity data - zipped", "quarterly_activity"),
    ("employment advis", "employment_advisers"),
    ("data quality report", "dq"),
    ("monthly activity data file", "activity"),
)
RANGE_KINDS = {"time_series", "rolling_quarter"}

VERSION_WORDS = {
    "final": "final",
    "performance": "performance",
    "provisional": "provisional",
    "primary": "provisional",
}
VERSION_RE = re.compile(r"\b(Final|Performance|Provisional|Primary)\b", re.IGNORECASE)
FILE_VERSION_RE = re.compile(r"[_-](final|performance|provisional|primary)(?=[_.\s-]|$)", re.IGNORECASE)


def classify_kind(title: str) -> str:
    text = title.lower()
    for phrase, kind in KIND_RULES:
        if phrase in text:
            return kind
    return "other"


def _page_version_for(month: str, page_title: str) -> str | None:
    """Find the version a release page gives a month, as in "Performance August 2023, Provisional September 2023"."""
    for match in MONTH_RE.finditer(page_title):
        name, year = match.group(1), match.group(2)
        if not year or f"{int(year):04d}-{MONTH_NUMBER[name.lower()]:02d}" != month:
            continue
        before = VERSION_RE.findall(page_title[max(0, match.start() - 14) : match.start()])
        after = VERSION_RE.match(page_title[match.end() :].lstrip())
        if after:
            return VERSION_WORDS[after.group(1).lower()]
        if before:
            return VERSION_WORDS[before[-1].lower()]
    return None


def classify_version(title: str, filename: str, page_title: str, month: str | None) -> str:
    match = VERSION_RE.search(title)
    if match:
        return VERSION_WORDS[match.group(1).lower()]
    match = FILE_VERSION_RE.search(Path(filename).stem)
    if match:
        return VERSION_WORDS[match.group(1).lower()]
    if month:
        from_page = _page_version_for(month, page_title)
        if from_page:
            return from_page
    return "unversioned"


def classify(title: str, filename: str = "", page_title: str = "") -> Classification:
    clean = re.sub(r"\s+", " ", title).strip()
    kind = classify_kind(clean)
    month = classify_month(clean, kind if kind in RANGE_KINDS else "", page_title)
    if kind in RANGE_KINDS:
        month = _last_month(clean, page_title) or month
    return Classification(
        kind=kind,
        version=classify_version(clean, filename, page_title, month),
        reporting_month=month,
        revision=classify_revision(clean, filename),
    )


def _last_month(title: str, page_title: str) -> str | None:
    matches = MONTH_RE.findall(title)
    if not matches:
        return None
    name, year = matches[-1]
    if not year:
        return classify_month(name, "", page_title)
    return f"{int(year):04d}-{MONTH_NUMBER[name.lower()]:02d}"


SPEC = series.SeriesSpec(
    key="talking_therapies_monthly",
    label="NHS Talking Therapies",
    classifier=classify,
    catalogue=Path("data/reference/talking_therapies_catalogue.csv"),
    asset_prefix="talking_therapies",
    main_kind="activity",
)


def main(argv: list[str] | None = None) -> None:
    series.main(SPEC, argv)


if __name__ == "__main__":
    main()
