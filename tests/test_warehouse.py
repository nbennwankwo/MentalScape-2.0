"""Warehouse tests on the synthetic fixture, using DuckDB so they run anywhere.

The same build runs on PostgreSQL in the warehouse CI job.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from mentalscape.ingest.manifest import read_manifest
from mentalscape.warehouse.fixture import build_fixture
from mentalscape.warehouse.load import choose_files, load, materialise_csv

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fixture_paths(tmp_path_factory) -> tuple[Path, Path, Path]:
    root = tmp_path_factory.mktemp("warehouse")
    manifest, assets = build_fixture(root / "fixture")
    return root, manifest, assets


def test_preferred_files_pick_final_march(fixture_paths):
    _, manifest, _ = fixture_paths
    chosen = {r.reporting_month: r.version for r in choose_files(read_manifest(manifest), "main")}
    assert chosen == {"2026-02": "final", "2026-03": "final", "2026-04": "performance"}


def test_materialise_handles_zip_gzip_and_mixed_line_endings(fixture_paths, tmp_path):
    _, manifest, assets = fixture_paths
    for row in read_manifest(manifest):
        csv_path = materialise_csv(assets / row.asset_name, tmp_path / row.asset_name)
        assert b"\r\n" not in csv_path.read_bytes() or b"\n" not in csv_path.read_bytes().replace(b"\r\n", b"")


def test_raw_load_into_duckdb(fixture_paths):
    root, manifest, assets = fixture_paths
    db = root / "raw_only.duckdb"
    total = load(manifest, assets, "duckdb", db, work_dir=root / "work")
    con = duckdb.connect(str(db), read_only=True)
    assert con.execute("select count(*) from raw.mhsds_main").fetchone()[0] == total == 49
    assert con.execute("select count(*) from raw.mhsds_files where is_preferred = 'True'").fetchone()[0] == 3
    con.close()


@pytest.mark.slow
def test_dbt_build_on_fixture(fixture_paths, monkeypatch):
    pytest.importorskip("dbt.cli.main")
    root, manifest, assets = fixture_paths
    db = root / "warehouse.duckdb"
    load(manifest, assets, "duckdb", db, work_dir=root / "work2")
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
    membership = con.execute(
        "select sub_icb_code, icb_code, valid_from_month from marts.geo_sub_icb_membership order by 1, 3"
    ).fetchall()
    assert ("06Q", "QH8", "2026-02") in membership and ("06Q", "D7T5G", "2026-04") in membership
    carried = con.execute(
        "select valid_to_month, months_carried_forward from marts.geo_sub_icb_membership "
        "where sub_icb_code = '06Q' and icb_code = 'QH8'"
    ).fetchone()
    assert carried == ("2026-03", 1)
    assert con.execute("select status from marts.dim_sub_icb where sub_icb_code = 'D4U1Y'").fetchone()[0] == "retired"
    assert con.execute("select windows from marts.dim_mhsds_measure where measure_id = 'MHS32'").fetchone()[0] == "1,3"
    assert (
        con.execute("select version_used from marts.dim_mhsds_release where release_month = '2026-03'").fetchone()[0]
        == "final"
    )
    con.close()


def test_profiles_default_path_is_inside_data():
    assert "data/warehouse/mentalscape.duckdb" in (REPO / "warehouse" / "profiles.yml").read_text()
    assert os.path.exists(REPO / "warehouse" / "dbt_project.yml")
