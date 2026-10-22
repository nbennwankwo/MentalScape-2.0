"""Warehouse tests on the synthetic fixture, using DuckDB so they run anywhere.

The same build runs on PostgreSQL in the warehouse CI job.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from mentalscape.ingest.manifest import read_manifest
from mentalscape.warehouse.fetch import rows_to_fetch
from mentalscape.warehouse.fixture import build_fixture, write_xlsx
from mentalscape.warehouse.load import (
    SOURCES,
    choose_files,
    excel_to_csv,
    load_source,
    materialise,
    normalise_column,
    open_target,
    unique_columns,
)
from mentalscape.warehouse.summary import build_summary

REPO = Path(__file__).resolve().parents[1]
MHSDS = "data-mhsds-monthly"
TT = "data-talking-therapies-monthly"
REF = "data-reference"


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory) -> Path:
    return build_fixture(tmp_path_factory.mktemp("warehouse") / "fixture")


def load_all(raw_dir: Path, db: Path, work_dir: Path) -> dict[str, int]:
    totals = {}
    with open_target("duckdb", db, None) as target:
        for name, spec in SOURCES.items():
            folder = raw_dir / spec.release
            totals[name] = load_source(target, spec, folder / "manifest.csv", folder, work_dir=work_dir)
    return totals


def test_preferred_files_pick_final_march(raw_dir):
    for release, kind in ((MHSDS, "main"), (TT, "activity")):
        chosen = {
            r.reporting_month: r.version for r in choose_files(read_manifest(raw_dir / release / "manifest.csv"), kind)
        }
        assert chosen == {"2026-02": "final", "2026-03": "final", "2026-04": "performance"}


def test_fetch_takes_preferred_files_unless_asked_for_all(raw_dir):
    manifest = read_manifest(raw_dir / MHSDS / "manifest.csv")
    assert len(rows_to_fetch(manifest, ["main"], all_versions=False)) == 3
    assert len(rows_to_fetch(manifest, ["main"], all_versions=True)) == 4
    reference = read_manifest(raw_dir / REF / "manifest.csv")
    assert len(rows_to_fetch(reference, None, all_versions=False)) == len(reference) == 10


def test_materialise_handles_zip_gzip_and_mixed_line_endings(raw_dir, tmp_path):
    for row in read_manifest(raw_dir / MHSDS / "manifest.csv"):
        part = materialise(raw_dir / MHSDS / row.asset_name, tmp_path / row.asset_name)[0]
        data = part.path.read_bytes()
        assert b"\r\n" not in data or b"\n" not in data.replace(b"\r\n", b"")


def test_column_names_are_safe_short_and_stable():
    assert normalise_column("LSOA code (2021)") == "lsoa_code_2021"
    assert normalise_column("Income Score (rate)") == "income_score_rate"
    long_note = "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)"
    assert normalise_column(long_note) == "index_of_multiple_deprivation_imd_decile"
    # The real IoD file cuts one header off before its closing bracket.
    cut = "Children and Young People Sub-domain Decile (where 1 is most deprived 10% of LSO"
    assert normalise_column(cut) == "children_and_young_people_sub_domain_decile"
    very_long = "A" * 80
    assert len(normalise_column(very_long)) <= 63 and normalise_column(very_long) == normalise_column(very_long)
    assert normalise_column("2021 count") == "c_2021_count"
    assert unique_columns(["Total", "total", "TOTAL"]) == ["total", "total_2", "total_3"]


def test_workbook_sheets_become_csv_from_the_header_row(tmp_path):
    book = write_xlsx(
        tmp_path / "book.xlsx",
        {
            "Cover sheet": [["About this file"]],
            "Mid-2024 LSOA 2021": [["Title"], ["Note"], ["LAD 2023 Code", "Total"], ["E06000001", 12.0]],
            "Notes": [["Nothing to load"]],
        },
    )
    parts = excel_to_csv(book, tmp_path, "LAD 2023 Code")
    assert [p.sheet for p in parts] == ["Mid-2024 LSOA 2021"]
    assert parts[0].path.read_text().splitlines() == ["LAD 2023 Code,Total", "E06000001,12"]
    with pytest.raises(ValueError):
        excel_to_csv(book, tmp_path, "No such header")


def test_raw_load_into_duckdb(raw_dir):
    db = raw_dir.parent / "raw_only.duckdb"
    totals = load_all(raw_dir, db, raw_dir.parent / "work")
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("select count(*) from raw.mhsds_main").fetchone()[0] == totals["mhsds"] == 54
        assert con.execute("select count(*) from raw.mhsds_files where is_preferred = 'True'").fetchone()[0] == 3
        assert (
            con.execute("select count(*) from raw.talking_therapies_activity").fetchone()[0]
            == totals["talking_therapies"]
            == 48
        )
        sheets = con.execute(
            "select _sheet, count(*) from raw.ref_ons_lsoa_population_2022_2024 group by 1 order by 1"
        ).fetchall()
        assert sheets == [("Mid-2023 LSOA 2021", 7), ("Mid-2024 LSOA 2021", 7)]
        columns = {r[0] for r in con.execute("describe raw.ref_iod_2025_file7").fetchall()}
        assert {"lsoa_code_2021", "children_and_young_people_sub_domain_decile", "total_population_mid_2022"} <= columns
        assert con.execute("select count(*) from raw.reference_files").fetchone()[0] == 10
    finally:
        con.close()


@pytest.mark.slow
def test_dbt_build_on_fixture(raw_dir, monkeypatch):
    pytest.importorskip("dbt.cli.main")
    root = raw_dir.parent
    db = root / "warehouse.duckdb"
    load_all(raw_dir, db, root / "work2")
    monkeypatch.setenv("MENTALSCAPE_DUCKDB", str(db))
    command = [
        sys.executable,
        "-c",
        "from dbt.cli.main import cli; cli()",
        "build",
        "--project-dir",
        "warehouse",
        "--profiles-dir",
        "warehouse",
        "--target",
        "local",
        "--vars",
        "{min_sub_icbs_per_release: 2}",
        "--target-path",
        str(root / "dbt_target"),
        "--log-path",
        str(root / "dbt_logs"),
    ]
    # A separate process, so that dbt's database connection is closed afterwards.
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout[-3000:]

    con = duckdb.connect(str(db), read_only=True)
    q = con.execute
    try:
        # Geography across the April 2026 mergers.
        membership = q(
            "select sub_icb_code, icb_code, valid_from_month from marts.geo_sub_icb_membership order by 1, 3"
        ).fetchall()
        assert ("06Q", "QH8", "2026-02") in membership and ("06Q", "D7T5G", "2026-04") in membership
        carried = q(
            "select valid_to_month, months_carried_forward from marts.geo_sub_icb_membership "
            "where sub_icb_code = '06Q' and icb_code = 'QH8'"
        ).fetchone()
        assert carried == ("2026-03", 1)
        assert q("select status from marts.dim_sub_icb where sub_icb_code = 'D4U1Y'").fetchone()[0] == "retired"

        # MHSDS measures and versions.
        assert q("select windows from marts.dim_mhsds_measure where measure_id = 'MHS32'").fetchone()[0] == "1,3"
        assert (
            q("select version_used from marts.dim_mhsds_release where release_month = '2026-03'").fetchone()[0]
            == "final"
        )

        # NHS Talking Therapies, with the same ICBs as MHSDS in every month.
        icbs = dict(
            q(
                "select release_month, icb_code from marts.fct_talking_therapies_values "
                "where sub_icb_code = '06Q' and geo_level = 'Sub ICB' and measure_id = 'M001'"
            ).fetchall()
        )
        assert icbs == {"2026-02": "QH8", "2026-03": "QH8", "2026-04": "D7T5G"}
        march = q(
            "select value_numeric from marts.fct_talking_therapies_values "
            "where release_month = '2026-03' and group_type = 'England' and measure_id = 'M001'"
        ).fetchone()[0]
        assert march == 48000  # the final file, with doubled counts, won
        assert (
            q("select statistic from marts.dim_talking_therapies_measure where measure_id = 'M053'").fetchone()[0]
            == "Percentage"
        )
        placeholders = q(
            "select count(*) from marts.fct_talking_therapies_values "
            "where region_code = 'InvalidRegionCode' and value_text = '*'"
        ).fetchone()[0]
        assert placeholders == 6

        # Local authorities abolished in April 2023, from ONS lookups only.
        successors = q(
            "select old_code, new_code, change_type from marts.geo_local_authority_successor order by 1, 2"
        ).fetchall()
        assert ("E10000006", "E06000063", "split") in successors and ("E10000006", "E06000064", "split") in successors
        assert ("E07000028", "E06000063", "merged") in successors
        carlisle = q(
            "select status, successor_codes from marts.dim_local_authority where la_code = 'E07000028'"
        ).fetchone()
        assert carlisle == ("abolished", "E06000063")

        # Population built up from LSOAs, Welsh LSOAs dropped, on the boundaries in force each month.
        england = q(
            "select population from marts.fct_population_monthly "
            "where release_month = '2026-04' and geo_level = 'England' and age_band = 'All ages'"
        ).fetchone()[0]
        lsoas_total = q(
            "select sum(total) from staging.stg_ons__lsoa_population where population_year = 2024"
        ).fetchone()[0]
        assert england == lsoas_total
        essex = q(
            "select release_month, geo_code, population_year, basis_note from marts.fct_population_monthly "
            "where geo_level = 'ICB' and age_band = 'All ages' and geo_code in ('QH8', 'D7T5G') order by 1"
        ).fetchall()
        assert [r[:3] for r in essex] == [
            ("2026-02", "QH8", 2024),
            ("2026-03", "QH8", 2024),
            ("2026-04", "D7T5G", 2024),
        ]
        assert essex[0][3] == "latest ONS estimate used, mid-2024"
        bands = dict(
            q(
                "select age_band, population from marts.fct_population_monthly "
                "where release_month = '2026-04' and geo_level = 'England'"
            ).fetchall()
        )
        assert bands["0 to 17"] + bands["18 and over"] == bands["All ages"]
        assert bands["18 to 64"] + bands["65 and over"] == bands["18 and over"]

        # Deprivation summarised from LSOAs, ranked with 1 as the most deprived.
        ranked = q(
            "select geo_code, imd_average_score_rank from marts.fct_deprivation_area "
            "where boundary_edition = '2026-04' and geo_level = 'ICB' order by 2"
        ).fetchall()
        assert ranked == [("D7T5G", 1), ("S0E4D", 2), ("QHM", 3)]
        share = q(
            "select share_most_deprived_decile from marts.fct_deprivation_area "
            "where boundary_edition = '2026-04' and geo_level = 'Sub ICB' and geo_code = '06Q'"
        ).fetchone()[0]
        assert share == pytest.approx(1510 / (1510 + 1520))
    finally:
        con.close()

    summary = build_summary(db, root / "dbt_target" / "run_results.json", datetime(2026, 10, 22, tzinfo=UTC))
    assert "| NHS Talking Therapies | 2026-02 | 2026-04 | 3 | 48 |" in summary
    assert "warn_england_step_changes" in summary


def test_summary_explains_a_build_that_stopped_early(tmp_path):
    text = build_summary(None, tmp_path / "missing.json", datetime(2026, 10, 22, tzinfo=UTC))
    assert "stopped before dbt ran" in text


def test_summary_lists_failures(tmp_path):
    results = tmp_path / "run_results.json"
    results.write_text(
        json.dumps(
            {
                "results": [
                    {"unique_id": "model.mentalscape.fct_population", "status": "success"},
                    {
                        "unique_id": "test.mentalscape.assert_population_ages_add_up_to_total",
                        "status": "fail",
                        "failures": 3,
                    },
                ]
            }
        )
    )
    text = build_summary(None, results, datetime(2026, 10, 22, tzinfo=UTC))
    assert "## Failed tests" in text and "| assert_population_ages_add_up_to_total | 3 |" in text


def test_profiles_default_path_is_inside_data():
    assert "data/warehouse/mentalscape.duckdb" in (REPO / "warehouse" / "profiles.yml").read_text()
    assert os.path.exists(REPO / "warehouse" / "dbt_project.yml")
