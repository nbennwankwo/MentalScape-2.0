"""Classification tests built from real card titles published by NHS England."""

from __future__ import annotations

import pytest

from mentalscape.ingest.classify import classify

CASES = [
    # title, filename, page title, kind, version, month, revision
    (
        "MHSDS Monthly: End of Year Final August 2025 MHSDS Data File",
        "MHSDS Data_AugFinal__2025.zip",
        "",
        "main",
        "final",
        "2025-08",
        1,
    ),
    (
        "MHSDS Monthly: Performance August 2025 MHSDS Data File",
        "MHSDS Data_AugPerf_2025.zip",
        "",
        "main",
        "performance",
        "2025-08",
        1,
    ),
    (
        "MHSDS Monthly: Performance July 2022 MHSDS Data File V4",
        "MHSDS Data_JulPrf_2022_v4.csv",
        "",
        "main",
        "performance",
        "2022-07",
        4,
    ),
    (
        "MHSDS Monthly: Performance April 2024 MHSDS Data File v2",
        "MHSDS Data_AprPerf_2024_v2.zip",
        "",
        "main",
        "performance",
        "2024-04",
        2,
    ),
    (
        "MHSDS Monthly: Performance April 2026 MHSDS Data File",
        "MHSDS Data_AprPerf_2026 v2.zip",
        "",
        "main",
        "performance",
        "2026-04",
        2,
    ),
    (
        "MHSDS Monthly: Provisional May 2023 MHSDS Data File V3",
        "MHSDS Data_MayP_2023 v3.csv",
        "",
        "main",
        "provisional",
        "2023-05",
        3,
    ),
    (
        "MHSDS Monthly: End of Year Final July 2022 MHSDS Data File",
        "MHSDS Data_Jul_EOY_F_2022.csv",
        "",
        "main",
        "final",
        "2022-07",
        1,
    ),
    (
        "MHSDS Monthly: Performance April Data Quality VODIM and Integrity File",
        "DQ_vodim_AprPerf_2026.csv",
        "Mental Health Services Monthly Statistics, Performance April 2026",
        "dq_vodim",
        "performance",
        "2026-04",
        1,
    ),
    (
        "MHSDS Monthly: Performance July 2022, Provisional August 2022 Data Quality Comments File",
        "MHSDS DQ_prov_comms_JulPrf_AugP_2022.csv",
        "",
        "dq_comments",
        "performance",
        "2022-07",
        1,
    ),
    (
        "MHSDS Monthly: Performance March 2023 Provsional April 2023 Data Quality Comments File",
        "x.csv",
        "",
        "dq_comments",
        "performance",
        "2023-03",
        1,
    ),
    (
        "MHSDS Monthly: End of Year Final April 2024 Out of Area Placements",
        "MHSDS Data_OAPs_AprFinal_2024.zip",
        "",
        "oaps",
        "final",
        "2024-04",
        1,
    ),
    (
        "MHSDS Monthly: End of Year Final Time Series for Out of Area Placements May 2022 to April 2024",
        "MHSDS Data_OAPs_AprFinal_2024.zip",
        "",
        "time_series",
        "final",
        "2024-04",
        1,
    ),
    (
        "MHSDS Monthly: Performance February 2024 to April 2024 Access and Waiting Times Reference Tables",
        "MHSDS AWT_AprPerf_2024.xlsx",
        "",
        "awt_tables",
        "performance",
        "2024-04",
        1,
    ),
    (
        "MHSDS Monthly: End of Year Final August 2025 Referral Spells",
        "MHSDS Data_4WW_AugFinal_2025.zip",
        "",
        "referral_spells",
        "final",
        "2025-08",
        1,
    ),
    (
        "MHSDS Monthly: Performance July 2026 Data Coverage File",
        "DQ_coverage_JulPerf_2026.csv",
        "",
        "dq_coverage",
        "performance",
        "2026-07",
        1,
    ),
    (
        "MHSDS Monthly: End of Year Final April 2024 Mental Health Services Measures to support the Adult Social "
        "Care Outcome Framework",
        "ASCOF_AprFinal_2024.zip",
        "",
        "ascof",
        "final",
        "2024-04",
        1,
    ),
    (
        "MHSDS End of Year Final March 2024 Restrictive Interventions",
        "x.zip",
        "",
        "restrictive_interventions",
        "final",
        "2024-03",
        1,
    ),
    (
        "Restated April 2026 data based on May 2026 data cut",
        "Restated April 2026 data based on May 2026 data cut v2.zip",
        "",
        "restated_main",
        "restated",
        "2026-04",
        2,
    ),
    ("MHSDS Annual: April 2022 to March 2023 MHSDS Data File", "x.csv", "", "annual_main", "unversioned", "2023-03", 1),
    (
        "MHSDS Monthly: July 2026 Number of referrals and people waiting for treatment across mental health and "
        "talking therapies",
        "x.zip",
        "",
        "combined_backlog",
        "unversioned",
        "2026-07",
        1,
    ),
    ("MHSDS Monthly: Final March 2022 MHSDS Data File", "x.csv", "", "main", "final", "2022-03", 1),
]


@pytest.mark.parametrize(("title", "filename", "page_title", "kind", "version", "month", "revision"), CASES)
def test_classify_real_titles(title, filename, page_title, kind, version, month, revision):
    found = classify(title, filename, page_title)
    assert (found.kind, found.version, found.reporting_month, found.revision) == (kind, version, month, revision)


def test_vodim_word_is_not_read_as_a_revision():
    assert classify("MHSDS Monthly: Performance July 2026 Data Quality VODIM and Integrity File").revision == 1


def test_title_without_month_has_no_reporting_month():
    assert classify("Pre-Release Access List").reporting_month is None
