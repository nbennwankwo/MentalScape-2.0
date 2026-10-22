"""Classify NHS England download cards into kind, version, month and revision.

Every file on an MHSDS Monthly Statistics release page sits in a download card
with a title such as

    MHSDS Monthly: End of Year Final August 2025 MHSDS Data File
    MHSDS Monthly: Performance July 2022 MHSDS Data File V4
    MHSDS Monthly: Performance April Data Quality VODIM and Integrity File

The wording has drifted over the years. The rules below were written against
every card title published on release pages from 2022 to 2026, 1,426 cards in
total, captured in October 2026.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
MONTH_NUMBER = {name.lower(): i for i, name in enumerate(MONTHS, start=1)}
MONTH_RE = re.compile(r"\b(" + "|".join(MONTHS) + r")(?:\s+(\d{4}))?\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20\d{2})\b")

# Order matters. The first matching phrase decides the kind.
KIND_RULES: tuple[tuple[str, str], ...] = (
    ("time series", "time_series"),
    ("access and waiting times", "awt_tables"),
    ("selected nhs england measures", "selected_measures"),
    ("new or expectant mothers", "perinatal"),
    ("adult social care", "ascof"),
    ("mental health act measures", "mha_measures"),
    ("number of referrals and people waiting", "combined_backlog"),
    ("restrictive interventions", "restrictive_interventions"),
    ("out of area placements", "oaps"),
    ("referral spells", "referral_spells"),
    ("data coverage", "dq_coverage"),
    ("vodim", "dq_vodim"),
    ("data quality comments", "dq_comments"),
    ("restated", "restated_main"),
    ("mhsds annual", "annual_main"),
    ("mhsds data file", "main"),
)

# Kinds whose title names a range of months. The reporting month is the last one.
RANGE_KINDS = {"time_series", "awt_tables", "selected_measures", "perinatal", "annual_main"}

# The first of these phrases in a title gives the version. "Provsional" is a
# real misspelling that appears on some release pages.
VERSION_RE = re.compile(r"\b(End of Year Final|End of Year|Final|Performance|Provisional|Provsional)\b", re.IGNORECASE)
VERSION_MAP = {
    "end of year final": "final",
    "end of year": "final",
    "final": "final",
    "performance": "performance",
    "provisional": "provisional",
    "provsional": "provisional",
}
VERSION_RANK = {"final": 3, "performance": 2, "provisional": 1}

REVISION_TITLE_RE = re.compile(r"\bv\s?(\d+)\b", re.IGNORECASE)
REVISION_FILE_RE = re.compile(r"[ _]v(\d+)(?=[ ._]|$)", re.IGNORECASE)


@dataclass(frozen=True)
class Classification:
    """What one download card contains."""

    kind: str
    version: str
    reporting_month: str | None
    revision: int
    note: str = ""


def classify_kind(title: str) -> str:
    text = title.lower()
    for phrase, kind in KIND_RULES:
        if phrase in text:
            return kind
    return "other"


def classify_version(title: str) -> str:
    match = VERSION_RE.search(title)
    if not match:
        return "restated" if "restated" in title.lower() else "unversioned"
    return VERSION_MAP[match.group(1).lower()]


def _page_year_for(month_name: str, page_title: str) -> int | None:
    """Find a year for a month written without one, using the page title."""
    for name, year in MONTH_RE.findall(page_title):
        if name.lower() == month_name.lower() and year:
            return int(year)
    years = YEAR_RE.findall(page_title)
    return int(years[-1]) if years else None


def classify_month(title: str, kind: str, page_title: str = "") -> str | None:
    """Return the reporting month as YYYY-MM, or None when no month is named."""
    matches = MONTH_RE.findall(title)
    if not matches:
        return None
    name, year = matches[-1] if kind in RANGE_KINDS else matches[0]
    year_number = int(year) if year else _page_year_for(name, page_title)
    if year_number is None:
        return None
    return f"{year_number:04d}-{MONTH_NUMBER[name.lower()]:02d}"


def classify_revision(title: str, filename: str = "") -> int:
    for pattern, text in ((REVISION_TITLE_RE, title), (REVISION_FILE_RE, filename.rsplit(".", 1)[0])):
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return 1


# File names such as "MHSDS Data_JulPerf_2026.zip" or "MHSDS Data_OAPs_MarFinal_2026.zip".
FILE_MONTH_RE = re.compile(
    r"(?<![A-Za-z])(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[ _]?"
    r"(?:Perf|Prf|Final|EOY_F|P|F)?[ _]*(20\d{2}|\d{2})(?!\d)",
    re.IGNORECASE,
)


def filename_month(filename: str) -> str | None:
    match = FILE_MONTH_RE.search(filename)
    if not match:
        return None
    year = int(match.group(2))
    year = year + 2000 if year < 100 else year
    return f"{year:04d}-{MONTH_NUMBER_SHORT[match.group(1).lower()]:02d}"


MONTH_NUMBER_SHORT = {name[:3].lower(): number for name, number in MONTH_NUMBER.items()}


def page_months(page_title: str) -> set[str]:
    """Every month a release page title names, with years filled in from the title."""
    months = set()
    for name, year in MONTH_RE.findall(page_title):
        year_number = int(year) if year else _page_year_for(name, page_title)
        if year_number:
            months.add(f"{year_number:04d}-{MONTH_NUMBER[name.lower()]:02d}")
    return months


@dataclass(frozen=True)
class MonthDecision:
    month: str | None
    note: str


def decide_month(title: str, kind: str, filename: str, page_title: str) -> MonthDecision:
    """Use the card title's month unless the page and the file name both contradict it.

    NHS England's card titles occasionally carry a typo. The March 2026 page,
    for example, lists "End of Year Final March 2025 Out of Area Placements"
    for the file MHSDS Data_OAPs_MarFinal_2026.zip. When the page title and the
    file name agree with each other and not with the card title, they win and
    a note records the correction.
    """
    from_title = classify_month(title, kind, page_title)
    if kind in RANGE_KINDS or from_title is None:
        return MonthDecision(from_title, "")
    from_file = filename_month(filename)
    on_page = page_months(page_title)
    if from_file and from_file != from_title and from_file in on_page and from_title not in on_page:
        return MonthDecision(from_file, f"card title says {from_title}, page and file name say {from_file}")
    return MonthDecision(from_title, "")


def classify(title: str, filename: str = "", page_title: str = "") -> Classification:
    clean = re.sub(r"\s+", " ", title).strip()
    kind = classify_kind(clean)
    month = decide_month(clean, kind, filename, page_title)
    return Classification(
        kind=kind,
        version=classify_version(clean),
        reporting_month=month.month,
        revision=classify_revision(clean, filename),
        note=month.note,
    )
