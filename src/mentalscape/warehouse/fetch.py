"""Download collected files from the data-mhsds-monthly GitHub Release.

The release is public, so no login is needed. Every file is checked against
the stored checksum in the manifest, and files already present with the right
checksum are not downloaded again.

    python -m mentalscape.warehouse.fetch --kind main --dest data/raw/release
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import requests

from mentalscape.ingest.manifest import ManifestEntry, preferred_files, read_manifest, sha256_of
from mentalscape.ingest.mhsds import download, make_session

LOGGER = logging.getLogger(__name__)
RELEASE_BASE = "https://github.com/nbennwankwo/MentalScape-2.0/releases/download/data-mhsds-monthly/"


def fetch_manifest(session: requests.Session, dest: Path, base_url: str = RELEASE_BASE) -> Path:
    target = dest / "manifest.csv"
    download(session, base_url + "manifest.csv", target)
    return target


def fetch_assets(
    session: requests.Session, rows: list[ManifestEntry], dest: Path, base_url: str = RELEASE_BASE
) -> list[Path]:
    """Download each asset unless a copy with the right checksum is already there."""
    paths = []
    for row in rows:
        target = dest / row.asset_name
        if target.exists() and sha256_of(target) == row.stored_sha256:
            LOGGER.info("Already have %s", row.asset_name)
        else:
            LOGGER.info("Downloading %s", row.asset_name)
            download(session, base_url + row.asset_name, target)
            if sha256_of(target) != row.stored_sha256:
                target.unlink()
                raise ValueError(f"Checksum mismatch for {row.asset_name}")
        paths.append(target)
    return paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download collected MHSDS files from the data release.")
    parser.add_argument("--dest", type=Path, default=Path("data/raw/release"))
    parser.add_argument("--kind", action="append", default=None, help="kind to fetch, repeatable (default main)")
    parser.add_argument("--all-versions", action="store_true", help="fetch every version, not only the preferred one")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    session = make_session()
    args.dest.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(fetch_manifest(session, args.dest))
    kinds = args.kind or ["main"]
    rows = (
        [r for r in manifest if r.kind in kinds]
        if args.all_versions
        else [row for kind in kinds for row in preferred_files(manifest, kind)]
    )
    fetch_assets(session, rows, args.dest)
    LOGGER.info("Fetched %s files into %s", len(rows), args.dest)


if __name__ == "__main__":
    main()
