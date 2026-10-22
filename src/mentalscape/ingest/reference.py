"""Collect reference files that live at fixed addresses.

The Indices of Deprivation, ONS population estimates and ONS geography
lookups are single files, not monthly series. Each one is listed under
reference_files in config/sources.yaml with an id, an edition and a URL. This
module downloads every listed file that is not yet in the manifest, checks it
looks like the expected data rather than an error page, and stores it with a
checksum, in the same way as the monthly series (docs/adr/0009).

A new edition of a file gets a new id and a new URL in the register, so an
older build can always be repeated from the files it used.

    python -m mentalscape.ingest.reference collect --manifest manifest.csv --out-dir data/interim/reference
    python -m mentalscape.ingest.reference check --manifest manifest.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests
import yaml

from mentalscape.ingest.manifest import CatalogueEntry, ManifestEntry, read_manifest, store_file, write_manifest
from mentalscape.ingest.series import download, make_session

LOGGER = logging.getLogger(__name__)
ASSET_PREFIX = "reference"


@dataclass(frozen=True)
class ReferenceFile:
    id: str
    source: str
    title: str
    edition: str
    url: str
    filename: str
    header_contains: str = ""

    def as_catalogue_entry(self) -> CatalogueEntry:
        suffix = Path(self.filename).suffix.lower().lstrip(".")
        return CatalogueEntry(
            page_url="",
            page_title=self.source,
            card_title=self.title,
            source_url=self.url,
            original_filename=self.filename,
            file_type=suffix,
            size_text="",
            kind=self.id,
            version="published",
            reporting_month=self.edition,
            revision=1,
            wanted=True,
            reason="",
        )


def read_register(path: Path) -> list[ReferenceFile]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8")).get("reference_files", {})
    return [ReferenceFile(id=key, **{k: str(v) for k, v in value.items()}) for key, value in entries.items()]


def looks_right(path: Path, entry: ReferenceFile) -> tuple[bool, str]:
    """Check a downloaded file is the data, not an HTML error page or an empty export."""
    suffix = Path(entry.filename).suffix.lower()
    if path.stat().st_size < 100:
        return False, f"{entry.id} is only {path.stat().st_size} bytes"
    if suffix in {".xlsx", ".zip"}:
        return (True, "") if zipfile.is_zipfile(path) else (False, f"{entry.id} is not a valid {suffix} file")
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        first_line = handle.readline()
    if first_line.lstrip().lower().startswith(("<!doctype", "<html", "{")):
        return False, f"{entry.id} looks like a web page or an error message, not a CSV file"
    if entry.header_contains and entry.header_contains not in first_line:
        return False, f"{entry.id} header does not contain {entry.header_contains!r}"
    return True, ""


def collect_new(
    session: requests.Session,
    register: list[ReferenceFile],
    manifest: list[ManifestEntry],
    assets_dir: Path,
    delay: float = 1.0,
) -> tuple[list[ManifestEntry], list[str]]:
    """Download every registered file whose URL is not yet in the manifest."""
    known = {row.source_url for row in manifest}
    new_rows: list[ManifestEntry] = []
    problems: list[str] = []
    tmp = assets_dir / ".download"
    for entry in register:
        if entry.url in known:
            continue
        time.sleep(delay)
        temp_file = tmp / entry.filename
        LOGGER.info("Downloading %s, edition %s", entry.id, entry.edition)
        try:
            download(session, entry.url, temp_file)
        except requests.RequestException as error:
            problems.append(f"{entry.id} could not be downloaded, {error}")
            continue
        ok, why = looks_right(temp_file, entry)
        if not ok:
            problems.append(why)
            temp_file.unlink()
            continue
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_rows.append(store_file(temp_file, entry.as_catalogue_entry(), assets_dir, stamp, prefix=ASSET_PREFIX))
        temp_file.unlink()
    return new_rows, problems


def missing_from_manifest(register: list[ReferenceFile], manifest: list[ManifestEntry]) -> list[str]:
    known = {row.source_url for row in manifest}
    return [entry.id for entry in register if entry.url not in known]


def write_summary(new_rows: list[ManifestEntry], problems: list[str], missing: list[str], path: Path) -> None:
    lines = ["## Reference files", "", f"- New files collected this run {len(new_rows)}"]
    lines += [f"- Still missing {', '.join(missing)}" if missing else "- Every registered file is collected"]
    if new_rows:
        lines += ["", "| New asset | Bytes stored |", "|---|---:|"]
        lines += [f"| {r.asset_name} | {r.stored_bytes:,} |" for r in new_rows]
    if problems:
        lines += ["", "### Problems", "", *[f"- {p}" for p in problems]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Collect reference files listed in config/sources.yaml.")
    parser.add_argument("command", choices=["collect", "check"])
    parser.add_argument("--config", type=Path, default=Path("config/sources.yaml"))
    parser.add_argument("--manifest", type=Path, help="existing manifest.csv, if any")
    parser.add_argument("--out-dir", type=Path, default=Path("data/interim/reference"))
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    register = read_register(args.config)
    existing = read_manifest(args.manifest) if args.manifest else []
    if args.command == "check":
        missing = missing_from_manifest(register, existing)
        if missing:
            LOGGER.error("Not yet collected %s", ", ".join(missing))
            sys.exit(1)
        LOGGER.info("All %s registered reference files are collected", len(register))
        return

    new_rows, problems = collect_new(make_session(), register, existing, args.out_dir / "assets", args.delay)
    manifest = existing + new_rows
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(manifest, args.out_dir / "manifest.csv")
    (args.out_dir / "new_assets.txt").write_text("".join(f"{r.asset_name}\n" for r in new_rows), encoding="utf-8")
    write_summary(new_rows, problems, missing_from_manifest(register, manifest), args.out_dir / "summary.md")
    for problem in problems:
        LOGGER.error("%s", problem)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
