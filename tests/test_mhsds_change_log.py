from __future__ import annotations

from pathlib import Path

import pandas as pd

from conftest import make_rows
from mentalscape.profiling.mhsds_change_log import build, canonical_geo_level, name_key
from mentalscape.profiling.mhsds_release_profile import profile_many, write_tables

SUB_ICBS_2025 = {"06Q": "NHS MID AND SOUTH ESSEX ICB - 06Q", "D4U1Y": "NHS FRIMLEY ICB - D4U1Y"}
SUB_ICBS_2026 = {"06Q": "NHS ESSEX ICB - 06Q", "U2G6B": "NHS THAMES VALLEY ICB - U2G6B"}


def _build(write_csv, tmp_path: Path, files: list[Path]) -> dict[str, pd.DataFrame]:
    profiles = tmp_path / "profiles"
    write_tables(profile_many(files), profiles)
    return build(profiles, tmp_path / "reference", tmp_path / "report.md", tmp_path / "seeds")


def test_detects_added_removed_renamed_and_replaced(write_csv, tmp_path: Path):
    march = {
        "MHS01": ("People in contact with services", "1000"),
        "EIP64": ("EIP caseload measure", "10"),
        "CCR72": ("New Emergency Referrals to Crisis Care teams in the Reporting Period with first contact", "50"),
        "MHS26": ("Days of delayed discharge in RP", "5"),
    }
    april = {
        "MHS01": ("People with an open referral", "1000"),
        "CCR118": ("New Emergency Referrals to Crisis Care teams in the reporting period with first contact", "55"),
        "MHS26": ("Days of delayed discharge in rp", "5"),
        "MHS200": ("A brand new readmissions measure", "7"),
    }
    files = [
        write_csv("mar.csv", make_rows("01/03/2026", "31/03/2026", march, SUB_ICBS_2025)),
        write_csv("apr.csv", make_rows("01/04/2026", "30/04/2026", april, SUB_ICBS_2026)),
    ]
    out = _build(write_csv, tmp_path, files)
    events = out["mhsds_measure_events"].set_index("measure_id")

    assert events.loc["MHS200", "event"] == "added"
    assert events.loc["EIP64", "event"] == "removed"
    assert events.loc["MHS01", "event"] == "renamed"
    assert events.loc["MHS26", "event"] == "renamed (cosmetic)"
    assert events.loc["CCR72", "likely_replaced_by"] == "CCR118"

    geo = out["mhsds_geography_events"].set_index("code")
    assert geo.loc["D4U1Y", "event"] == "code removed"
    assert geo.loc["U2G6B", "event"] == "code added"
    assert geo.loc["06Q", "event"] == "renamed"

    catalogue = out["mhsds_measure_catalogue"].set_index("measure_id")
    assert not catalogue.loc["EIP64", "in_latest_release"]
    assert catalogue.loc["MHS01", "name_versions"] == 2
    assert (tmp_path / "report.md").read_text().startswith("# MHSDS Monthly Statistics")

    known = pd.read_csv(tmp_path / "seeds" / "mhsds_known_measures.csv")
    assert list(known.columns) == ["measure_id", "first_seen", "last_seen"]
    assert {"MHS200", "EIP64", "CCR72", "CCR118"} <= set(known["measure_id"])


def test_recurring_jumps_are_separated_from_one_offs(write_csv, tmp_path: Path):
    values = {
        ("2023-07", "31/07/2023"): "1000",
        ("2023-08", "31/08/2023"): "600",
        ("2024-07", "31/07/2024"): "1000",
        ("2024-08", "31/08/2024"): "600",
    }
    files = []
    for (month, end), value in values.items():
        start = f"01/{month[5:]}/{month[:4]}"
        rows = make_rows(start, end, {"CYP32": ("Referrals to CYP services", value)}, SUB_ICBS_2025)
        files.append(write_csv(f"{month}.csv", rows))
    out = _build(write_csv, tmp_path, files)
    steps = out["mhsds_england_step_changes"]
    assert set(steps["release_month"]) == {"2023-08", "2024-08"}
    assert set(steps["pattern"]) == {"recurring in this calendar month"}


def test_helpers():
    assert canonical_geo_level("Sub ICB of GP Practice or Residence; Age Band") == "Sub ICB"
    assert canonical_geo_level("ICB - GP Practice or Residence") == "ICB"
    assert canonical_geo_level("Commissioning Region; IMD Decile") == "Commissioning Region"
    assert name_key("Days of delayed discharge in RP") == name_key("days of delayed discharge in rp")
