from __future__ import annotations

from pathlib import Path

from conftest import make_rows
from mentalscape.profiling.mhsds_release_profile import count_line_endings, profile_file

SUB_ICBS = {"00L": "NHS NORTH EAST AND NORTH CUMBRIA ICB - 00L", "W2U3Z": "NHS NORTH WEST LONDON ICB - W2U3Z"}
MEASURES = {"MHS01": ("People in contact with services", "1000"), "MHS32": ("New referrals", "250")}


def test_profile_reads_shape_and_suppression(write_csv, tmp_path: Path):
    path = write_csv("jul.csv", make_rows("01/07/2022", "31/07/2022", MEASURES, SUB_ICBS))
    profile = profile_file(path, work_dir=tmp_path / "norm")

    release = profile.release.iloc[0]
    assert release["release_month"] == "2022-07"
    assert release["n_rows"] == 6
    assert release["n_measures"] == 2
    # Four of the six rows are Sub ICB rows published as an asterisk.
    assert abs(release["share_suppressed"] - 4 / 6) < 1e-9
    assert release["date_style"] == "DD/MM/YYYY"
    assert release["line_endings"] == "LF"
    assert set(profile.geography["primary_code"]) == set(SUB_ICBS)
    assert set(profile.england_values["measure_id"]) == {"MHS01", "MHS32"}


def test_profile_handles_mixed_dates_and_line_endings(write_csv, tmp_path: Path):
    first = make_rows("2023-08-01", "2023-08-31", {"MHS01": MEASURES["MHS01"]}, SUB_ICBS)
    second = make_rows("01/08/2023", "31/08/2023", {"MHS32": MEASURES["MHS32"]}, SUB_ICBS)
    path = tmp_path / "stitched.csv"
    from conftest import HEADER

    content = "\n".join([HEADER, *first]) + "\n" + "\r\n".join(second) + "\r\n"
    path.write_bytes(content.encode())

    crlf, total = count_line_endings(path)
    assert 0 < crlf < total

    release = profile_file(path, work_dir=tmp_path / "norm").release.iloc[0]
    assert release["release_month"] == "2023-08"
    assert release["n_measures"] == 2
    assert release["date_style"].startswith("mixed")
    assert release["line_endings"].startswith("mixed")


def test_trailing_spaces_in_status_are_reported(write_csv, tmp_path: Path):
    rows = make_rows("01/06/2025", "30/06/2025", {"MHS01": MEASURES["MHS01"]}, SUB_ICBS)
    rows[0] = rows[0].replace("Performance", "Performance ")
    release = profile_file(write_csv("jun.csv", rows), work_dir=tmp_path / "norm").release.iloc[0]
    assert "'Performance '" in release["status_values"]
