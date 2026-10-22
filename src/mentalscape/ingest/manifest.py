"""The catalogue of published files and the manifest of collected files.

Two tables keep track of the source data.

    catalogue   every file NHS England lists on the release pages in scope,
                with its classification and whether the pipeline wants it
    manifest    every file the pipeline has actually downloaded and stored,
                with checksums, so any past build can be repeated exactly

The manifest is append only. A file is identified by its source URL, so a
reissued file, which NHS England always publishes at a new URL, becomes a new
row rather than overwriting an old one.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from mentalscape.ingest.classify import VERSION_RANK


@dataclass(frozen=True)
class CatalogueEntry:
    page_url: str
    page_title: str
    card_title: str
    source_url: str
    original_filename: str
    file_type: str
    size_text: str
    kind: str
    version: str
    reporting_month: str
    revision: int
    wanted: bool
    reason: str
    note: str = ""


@dataclass(frozen=True)
class ManifestEntry:
    asset_name: str
    kind: str
    reporting_month: str
    version: str
    revision: int
    source_url: str
    page_url: str
    card_title: str
    original_filename: str
    original_bytes: int
    original_sha256: str
    stored_bytes: int
    stored_sha256: str
    downloaded_at_utc: str


def _write(rows: Iterable[object], row_type: type, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = [f.name for f in fields(row_type)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_catalogue(rows: Iterable[CatalogueEntry], path: Path) -> None:
    """Write the catalogue in a stable order so that git diffs show only real changes."""
    ordered = sorted(rows, key=lambda r: (r.reporting_month, r.kind, r.version, r.revision, r.source_url))
    _write(ordered, CatalogueEntry, path)


def read_catalogue(path: Path) -> list[CatalogueEntry]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    out = []
    for row in rows:
        row["revision"] = int(row["revision"])
        row["wanted"] = row["wanted"] == "True"
        out.append(CatalogueEntry(**row))
    return out


def write_manifest(rows: Iterable[ManifestEntry], path: Path) -> None:
    ordered = sorted(rows, key=lambda r: (r.kind, r.reporting_month, r.version, r.revision, r.asset_name))
    _write(ordered, ManifestEntry, path)


def read_manifest(path: Path) -> list[ManifestEntry]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    out = []
    for row in rows:
        for name in ("revision", "original_bytes", "stored_bytes"):
            row[name] = int(row[name])
        out.append(ManifestEntry(**row))
    return out


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def asset_name(kind: str, reporting_month: str, version: str, revision: int, sha256: str, suffix: str) -> str:
    """Build a unique, readable asset name such as mhsds__main__2025-08__final__r1__3f2a9c1d0b.zip"""
    return f"mhsds__{kind}__{reporting_month}__{version}__r{revision}__{sha256[:10]}{suffix}"


def store_file(downloaded: Path, entry: CatalogueEntry, out_dir: Path, downloaded_at_utc: str) -> ManifestEntry:
    """Copy a downloaded file into out_dir under its asset name, gzipping CSV files."""
    original_sha = sha256_of(downloaded)
    suffix = Path(entry.original_filename).suffix.lower() or f".{entry.file_type}"
    out_dir.mkdir(parents=True, exist_ok=True)
    if suffix == ".csv":
        stored_suffix = ".csv.gz"
        name = asset_name(entry.kind, entry.reporting_month, entry.version, entry.revision, original_sha, stored_suffix)
        target = out_dir / name
        with downloaded.open("rb") as source, gzip.GzipFile(target, "wb", mtime=0) as sink:
            shutil.copyfileobj(source, sink)
    else:
        name = asset_name(entry.kind, entry.reporting_month, entry.version, entry.revision, original_sha, suffix)
        target = out_dir / name
        shutil.copyfile(downloaded, target)
    return ManifestEntry(
        asset_name=name,
        kind=entry.kind,
        reporting_month=entry.reporting_month,
        version=entry.version,
        revision=entry.revision,
        source_url=entry.source_url,
        page_url=entry.page_url,
        card_title=entry.card_title,
        original_filename=entry.original_filename,
        original_bytes=downloaded.stat().st_size,
        original_sha256=original_sha,
        stored_bytes=target.stat().st_size,
        stored_sha256=sha256_of(target),
        downloaded_at_utc=downloaded_at_utc,
    )


def preferred_files(manifest: Iterable[ManifestEntry], kind: str) -> list[ManifestEntry]:
    """Pick one file per reporting month for a kind.

    End of Year Final beats Performance, which beats Provisional. Within a
    version the highest revision wins, then the most recent download.
    """
    best: dict[str, ManifestEntry] = {}
    for row in manifest:
        if row.kind != kind:
            continue
        key = (VERSION_RANK.get(row.version, 0), row.revision, row.downloaded_at_utc)
        current = best.get(row.reporting_month)
        if current is None or key > (VERSION_RANK.get(current.version, 0), current.revision, current.downloaded_at_utc):
            best[row.reporting_month] = row
    return [best[month] for month in sorted(best)]
