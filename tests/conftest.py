"""Shared helpers that build tiny MHSDS style files for the tests."""

from __future__ import annotations

from pathlib import Path

import pytest

HEADER = (
    "REPORTING_PERIOD_START,REPORTING_PERIOD_END,STATUS,BREAKDOWN,PRIMARY_LEVEL,"
    "PRIMARY_LEVEL_DESCRIPTION,SECONDARY_LEVEL,SECONDARY_LEVEL_DESCRIPTION,MEASURE_ID,MEASURE_NAME,MEASURE_VALUE"
)


def make_rows(start: str, end: str, measures: dict[str, tuple[str, str]], sub_icbs: dict[str, str]) -> list[str]:
    """Return CSV rows with one England row and one row per Sub ICB for each measure."""
    rows = []
    for measure_id, (name, england_value) in measures.items():
        rows.append(
            f'{start},{end},Performance,England,England,England,NONE,NONE,{measure_id},"{name}",{england_value}'
        )
        for code, sub_name in sub_icbs.items():
            rows.append(
                f"{start},{end},Performance,Sub ICB - GP Practice or Residence,{code},{sub_name},NONE,NONE,"
                f'{measure_id},"{name}",*'
            )
    return rows


@pytest.fixture
def write_csv(tmp_path: Path):
    def _write(name: str, rows: list[str], newline: str = "\n") -> Path:
        path = tmp_path / name
        path.write_bytes((newline.join([HEADER, *rows]) + newline).encode())
        return path

    return _write
