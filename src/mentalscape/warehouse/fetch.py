"""Download collected files from the project's data releases.

Each source has its own GitHub Release, and each release is public, so no
login is needed. Files land in data/raw/<release>/, next to that release's
manifest. Every file is checked against the stored checksum in the manifest,
and files already present with the right checksum are not downloaded again.

    python -m mentalscape.warehouse.fetch --source all
    python -m mentalscape.warehouse.fetch --source mhsds --kind main --kind oaps
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import requests

from mentalscape.ingest.manifest import ManifestEntry, preferred_files, read_manifest, sha256_of
from mentalscape.ingest.series import download, make_session
from mentalscape.warehouse.load import SOURCES

LOGGER = logging.getLogger(__name__)
REPOSITORY = "https://github.com/nbennwankwo/MentalScape-2.0"
RELEASE_BASE = f"{REPOSITORY}/releases/download/data-mhsds-monthly/"

# The kinds each source loads by default. Reference files are all loaded.
DEFAULT_KINDS = {"mhsds": ["main"], "talking_therapies": ["activity"], "reference": None}


def release_base(release: str) -> str:
    return f"{REPOSITORY}/releases/download/{release}/"


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


def rows_to_fetch(manifest: list[ManifestEntry], kinds: list[str] | None, all_versions: bool) -> list[ManifestEntry]:
    wanted = kinds or sorted({row.kind for row in manifest})
    if all_versions:
        return [r for r in manifest if r.kind in wanted]
    return [row for kind in wanted for row in preferred_files(manifest, kind)]


def fetch_source(
    session: requests.Session, source: str, raw_dir: Path, kinds: list[str] | None, all_versions: bool
) -> list[Path]:
    release = SOURCES[source].release
    dest = raw_dir / release
    dest.mkdir(parents=True, exist_ok=True)
    base = release_base(release)
    manifest = read_manifest(fetch_manifest(session, dest, base))
    rows = rows_to_fetch(manifest, kinds if kinds is not None else DEFAULT_KINDS[source], all_versions)
    paths = fetch_assets(session, rows, dest, base)
    LOGGER.info("Fetched %s %s files into %s", len(paths), source, dest)
    return paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download collected files from the data releases.")
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--kind", action="append", default=None, help="kind to fetch, repeatable")
    parser.add_argument("--all-versions", action="store_true", help="fetch every version, not only the preferred one")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    session = make_session()
    for source in list(SOURCES) if args.source == "all" else [args.source]:
        fetch_source(session, source, args.raw_dir, args.kind, args.all_versions)


if __name__ == "__main__":
    main()
