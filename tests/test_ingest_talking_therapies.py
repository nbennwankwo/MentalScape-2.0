"""Tests for the NHS Talking Therapies classifier, using real card titles."""

from __future__ import annotations

from pathlib import Path

import pytest

from mentalscape.ingest import series
from mentalscape.ingest.manifest import read_catalogue
from mentalscape.ingest.talking_therapies import SPEC, classify

IAPT_PAGE = (
    "Psychological Therapies: reports on the use of IAPT services, England, "
    "January 2023 Final including a report on the IAPT Employment Advisers pilot"
)
TT_SERIES = "NHS Talking Therapies Monthly Statistics Including Employment Advisors"
TT_2023_PAGE = f"{TT_SERIES}, Performance May 2023, Provisional June 2023"
TT_PAGE = f"{TT_SERIES}, Performance June 2026 and Quarter 1 2026/27 data"


@pytest.mark.parametrize(
    ("title", "filename", "page", "expected"),
    [
        (
            "IAPT Monthly Activity Data File - July 2022 v2",
            "iapt_month_jul_22_activity_updated.csv",
            IAPT_PAGE.replace("January 2023", "July 2022"),
            ("activity", "final", "2022-07", 2),
        ),
        # No version in the title or file name, so the page title decides.
        (
            "IAPT Monthly Activity Data File - January 2023",
            "iapt_month_Jan_23_activity.zip",
            IAPT_PAGE,
            ("activity", "final", "2023-01", 1),
        ),
        ("IAPT Data Quality Report - February 2023 Primary", "x.csv", IAPT_PAGE, ("dq", "provisional", "2023-02", 1)),
        (
            "IAPT Monthly Activity Data File - February 2023",
            "iapt_month_feb_2023_activity v2.csv",
            IAPT_PAGE.replace("January 2023", "February 2023"),
            ("activity", "final", "2023-02", 2),
        ),
        (
            "NHS Talking Therapies Monthly Activity Data File - June 2023 Provisional",
            "nhstalkingtherapies_month_jun_2023_activity_provisional.csv",
            TT_2023_PAGE,
            ("activity", "provisional", "2023-06", 1),
        ),
        (
            "NHS Talking Therapies Monthly Activity Data File - June 2026",
            "nhstalkingtherapies_month_jun_2026_activity_performance.csv",
            TT_PAGE,
            ("activity", "performance", "2026-06", 1),
        ),
        (
            "NHS Talking Therapies Monthly Activity Data File - July 2025 Final",
            "nhstalkingtherapies_month_jul_2025_activity_final.csv",
            "NHS Talking Therapies Monthly Statistics Including Employment Advisors, Final July 2025",
            ("activity", "final", "2025-07", 1),
        ),
        (
            "Monthly Report on Employment Advisor NHS Talking Therapies services - Data File, June 2026",
            "nhstalkingtherapies_month_jun_2026_ea_performance.csv",
            TT_PAGE,
            ("employment_advisers", "performance", "2026-06", 1),
        ),
        (
            "Monthly Time Series for Key Measures - June 2025 - June 2026",
            "nhstalkingtherapies_time_series_jun_2025_jun_2026_key_measures.csv",
            TT_PAGE,
            ("time_series", "performance", "2026-06", 1),
        ),
        (
            "NHS Talking Therapies Quarter 1 2026/27 Activity Data - zipped files",
            "nhstalkingtherapies_quarterly_data_q1_26_27.zip",
            TT_PAGE,
            ("quarterly_activity", "unversioned", None, 1),
        ),
    ],
)
def test_real_card_titles(title, filename, page, expected):
    found = classify(title, filename, page)
    assert (found.kind, found.version, found.reporting_month, found.revision) == expected


def test_committed_catalogue_has_one_main_file_for_every_month():
    catalogue = read_catalogue(Path(__file__).parents[1] / "data" / "reference" / "talking_therapies_catalogue.csv")
    wanted = [c for c in catalogue if c.wanted and c.kind == "activity"]
    months = sorted(c.reporting_month for c in wanted)
    assert months[0] == "2022-07" and len(months) == len(set(months)) == 50
    assert {c.version for c in wanted} <= {"final", "performance"}


def test_series_main_kind_drives_the_staleness_check():
    from datetime import date

    from mentalscape.ingest.manifest import CatalogueEntry

    entry = CatalogueEntry("", "", "", "u", "f.csv", "csv", "", "activity", "performance", "2026-08", 1, True, "")
    ok, message = series.check_catalogue([entry], date(2026, 10, 22), main_kind=SPEC.main_kind)
    assert ok and "activity" in message
