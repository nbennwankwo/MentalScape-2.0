"""A small synthetic dataset that reproduces the real traps in MHSDS files.

The fixture has three release months, February to April 2026, built so that
the warehouse has to cope with the same problems as the real data.

    the April 2026 ICB mergers, with Sub ICB 06Q moving from Mid and South
    Essex ICB to Essex ICB
    Frimley's Sub ICB D4U1Y disappearing and Thames Valley's U2G6B appearing
    one Sub ICB code carrying two names in the same file
    a month where a Sub ICB carries only its post merger name
    all five date styles and mixed line endings
    MHS32 published for a one month and a three month window
    a status label with a trailing space
    two versions of March 2026, where the final one must win

All values are invented. It is used by the tests and by the PostgreSQL CI job.

    python -m mentalscape.warehouse.fixture --out data/interim/fixture
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from mentalscape.ingest.manifest import CatalogueEntry, ManifestEntry, store_file, write_manifest

HEADER = (
    "REPORTING_PERIOD_START,REPORTING_PERIOD_END,STATUS,BREAKDOWN,PRIMARY_LEVEL,PRIMARY_LEVEL_DESCRIPTION,"
    "SECONDARY_LEVEL,SECONDARY_LEVEL_DESCRIPTION,MEASURE_ID,MEASURE_NAME,MEASURE_VALUE"
)

BEFORE_MERGER = {
    "sub_icbs": [
        ("Sub ICB of GP Practice or Residence", "06Q", "NHS MID AND SOUTH ESSEX ICB - 06Q"),
        ("Sub ICB - GP Practice or Residence", "06Q", "NHS ESSEX ICB - 06Q"),
        ("Sub ICB of GP Practice or Residence", "D4U1Y", "NHS FRIMLEY ICB - D4U1Y"),
        ("Sub ICB of GP Practice or Residence", "00L", "NHS NORTH EAST AND NORTH CUMBRIA ICB - 00L"),
        ("Sub ICB of GP Practice or Residence", "UNKNOWN", "UNKNOWN"),
    ],
    "icbs": [
        ("QH8", "NHS MID AND SOUTH ESSEX INTEGRATED CARE BOARD"),
        ("QNQ", "NHS FRIMLEY INTEGRATED CARE BOARD"),
        ("QHM", "NHS NORTH EAST AND NORTH CUMBRIA INTEGRATED CARE BOARD"),
    ],
}
# Like the real March 2026 final file, produced after the mergers, so 06Q only
# carries its new name while the ICB rows are still the old ICBs.
MARCH_FINAL = {
    "sub_icbs": [
        ("Sub ICB of GP Practice or Residence", "06Q", "NHS ESSEX ICB - 06Q"),
        ("Sub ICB of GP Practice or Residence", "D4U1Y", "NHS FRIMLEY ICB - D4U1Y"),
        ("Sub ICB of GP Practice or Residence", "00L", "NHS NORTH EAST AND NORTH CUMBRIA ICB - 00L"),
    ],
    "icbs": BEFORE_MERGER["icbs"],
}
AFTER_MERGER = {
    "sub_icbs": [
        ("Sub ICB of GP Practice or Residence", "06Q", "NHS ESSEX ICB - 06Q"),
        ("Sub ICB of GP Practice or Residence", "U2G6B", "NHS THAMES VALLEY ICB - U2G6B"),
        ("Sub ICB of GP Practice or Residence", "00L", "NHS NORTH EAST AND NORTH CUMBRIA ICB - 00L"),
    ],
    "icbs": [
        ("D7T5G", "NHS ESSEX INTEGRATED CARE BOARD"),
        ("S0E4D", "NHS THAMES VALLEY INTEGRATED CARE BOARD"),
        ("QHM", "NHS NORTH EAST AND NORTH CUMBRIA INTEGRATED CARE BOARD"),
    ],
}

MONTHS = {
    # month: (geography, date style, status, first day, last day, previous quarter start)
    "2026-02": (BEFORE_MERGER, "iso", "Final", "2026-02-01", "2026-02-28", "2025-12-01"),
    "2026-03": (MARCH_FINAL, "dmy", "Final", "2026-03-01", "2026-03-31", "2026-01-01"),
    "2026-04": (AFTER_MERGER, "dmy", "Performance ", "2026-04-01", "2026-04-30", "2026-02-01"),
}


def _fmt(iso: str, style: str) -> str:
    """Write a date in one of the five styles NHS England has used."""
    year, month, day = iso.split("-")
    return {
        "iso": iso,
        "dmy": f"{day}/{month}/{year}",
        "dmy_unpadded": f"{int(day)}/{int(month)}/{year}",
        "dmy_two_digit_year": f"{day}/{month}/{year[2:]}",
        "dmy_hyphen": f"{day}-{month}-{year}",
    }[style]


# The rolling three month row of each month uses one of the rarer date styles.
QUARTER_STYLE = {"2026-02": "dmy_unpadded", "2026-03": "dmy_two_digit_year", "2026-04": "dmy_hyphen"}


def month_rows(month: str, scale: int = 1) -> list[str]:
    geo, style, status, first, last, quarter = MONTHS[month]
    start, end, q_start = _fmt(first, style), _fmt(last, style), _fmt(quarter, QUARTER_STYLE[month])
    rows = []

    def add(s: str, breakdown: str, code: str, name: str, mid: str, mname: str, value: str) -> None:
        rows.append(f'{s},{end},{status},{breakdown},{code},"{name}",NONE,NONE,{mid},"{mname}",{value}')

    for measure, name, base in (
        ("MHS01", "People with an open referral", 400000),
        ("MHS32", "Referrals starting in RP", 90000),
    ):
        add(start, "England", "England", "England", measure, name, str(base * scale))
        for code, icb_name in geo["icbs"]:
            add(start, "ICB of GP Practice or Residence", code, icb_name, measure, name, str(base * scale // 40))
        for breakdown, code, sub_name in geo["sub_icbs"]:
            add(start, breakdown, code, sub_name, measure, name, "*" if code == "UNKNOWN" else str(base * scale // 120))
    add(q_start, "England", "England", "England", "MHS32", "New referrals", str(270000 * scale))
    return rows


def _entry(month: str, version: str, filename: str) -> CatalogueEntry:
    return CatalogueEntry(
        page_url="https://example.test/fixture",
        page_title=f"Fixture {month}",
        card_title=f"MHSDS Monthly: {version} {month} MHSDS Data File",
        source_url=f"https://files.example.test/{version}/{filename}",
        original_filename=filename,
        file_type=filename.rsplit(".", 1)[-1],
        size_text="1 KB",
        kind="main",
        version=version,
        reporting_month=month,
        revision=1,
        wanted=True,
        reason="",
    )


def build_fixture(out_dir: Path) -> tuple[Path, Path]:
    """Write fixture assets and a manifest. Returns the manifest path and the assets folder."""
    staging = out_dir / "source"
    assets = out_dir / "assets"
    staging.mkdir(parents=True, exist_ok=True)
    rows: list[ManifestEntry] = []
    stamp = "2026-10-22T00:00:00Z"

    # February 2026, final, zipped, with mixed line endings as in real final files.
    feb = month_rows("2026-02")
    csv_path = staging / "MHSDS Data_FebFinal__2026.csv"
    half = len(feb) // 2
    csv_path.write_bytes(("\n".join([HEADER, *feb[:half]]) + "\n" + "\r\n".join(feb[half:]) + "\r\n").encode())
    zip_path = staging / "MHSDS Data_FebFinal__2026.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(csv_path, "MHSDS Data_FebFinal__2026/MHSDS Data_FebFinal__2026.csv")
    rows.append(store_file(zip_path, _entry("2026-02", "final", zip_path.name), assets, stamp))

    # March 2026, performance then final. The final one must win.
    for version, scale in (("performance", 1), ("final", 2)):
        path = staging / f"MHSDS Data_Mar{version.title()}_2026.csv"
        path.write_bytes(("\r\n".join([HEADER, *month_rows("2026-03", scale)]) + "\r\n").encode())
        rows.append(store_file(path, _entry("2026-03", version, path.name), assets, stamp))

    # April 2026, performance only, after the ICB mergers.
    apr = staging / "MHSDS Data_AprPerf_2026.csv"
    apr.write_bytes(("\r\n".join([HEADER, *month_rows("2026-04")]) + "\r\n").encode())
    rows.append(store_file(apr, _entry("2026-04", "performance", apr.name), assets, stamp))

    manifest = out_dir / "manifest.csv"
    write_manifest(rows, manifest)
    return manifest, assets


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write the synthetic warehouse fixture.")
    parser.add_argument("--out", type=Path, default=Path("data/interim/fixture"))
    args = parser.parse_args(argv)
    manifest, assets = build_fixture(args.out)
    print(f"Fixture manifest {manifest}")
    print(f"Fixture assets {assets}")


if __name__ == "__main__":
    main()
