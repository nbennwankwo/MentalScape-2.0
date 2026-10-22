"""Collect MHSDS Monthly Statistics files from NHS England.

The command has two steps.

    discover  read the series page and every release page in scope, classify
              every file and write catalogue.csv
    run       discover, then download every wanted file that is not already in
              the manifest, store it under its asset name and update
              manifest.csv

It is designed to run on GitHub Actions, which can reach the NHS England
website. The workflow then uploads the new files and the manifest to the
data-mhsds-monthly GitHub Release (see docs/adr/0009).

Examples

    python -m mentalscape.ingest.mhsds discover --out-dir data/interim/ingest
    python -m mentalscape.ingest.mhsds run --out-dir data/interim/ingest --manifest data/interim/ingest/manifest.csv
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from mentalscape.ingest.classify import classify
from mentalscape.ingest.manifest import (
    CatalogueEntry,
    ManifestEntry,
    read_manifest,
    store_file,
    write_catalogue,
    write_manifest,
)
from mentalscape.ingest.nhs_pages import SERIES_URL, page_in_scope, parse_release_page, parse_series_page

LOGGER = logging.getLogger(__name__)
USER_AGENT = "MentalScape-2.0 open data pipeline (+https://github.com/nbennwankwo/MentalScape-2.0)"


@dataclass(frozen=True)
class IngestConfig:
    first_month: str
    kinds_wanted: frozenset[str]
    versions_wanted: frozenset[str]

    @classmethod
    def from_sources_yaml(cls, path: Path) -> IngestConfig:
        source = yaml.safe_load(path.read_text(encoding="utf-8"))["sources"]["mhsds_monthly"]
        return cls(
            first_month=str(source["first_month_in_scope"]),
            kinds_wanted=frozenset(source["kinds_wanted"]),
            versions_wanted=frozenset(source["versions_wanted"]),
        )


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retry = Retry(total=4, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def judge(kind: str, version: str, month: str | None, config: IngestConfig) -> tuple[bool, str]:
    """Decide whether a file is wanted, and say why not when it is not."""
    if month is None:
        return False, "no reporting month in title"
    if month < config.first_month:
        return False, "before first month in scope"
    if kind not in config.kinds_wanted:
        return False, f"kind {kind} not wanted"
    if version not in config.versions_wanted:
        return False, f"version {version} not wanted"
    return True, ""


def discover(session: requests.Session, config: IngestConfig, delay: float = 1.0) -> list[CatalogueEntry]:
    """Read every release page in scope and classify every file on it."""
    first_year = int(config.first_month[:4])
    series = session.get(SERIES_URL, timeout=60)
    series.raise_for_status()
    pages = [p for p in parse_series_page(series.text) if page_in_scope(p, first_year)]
    LOGGER.info("Found %s release pages in scope", len(pages))

    seen: set[str] = set()
    catalogue: list[CatalogueEntry] = []
    for page in pages:
        time.sleep(delay)
        response = session.get(page.url, timeout=60)
        if response.status_code == 404:
            LOGGER.info("Skipping %s, not published yet", page.url)
            continue
        response.raise_for_status()
        for card in parse_release_page(response.text, page.url):
            if card.source_url in seen:
                continue
            seen.add(card.source_url)
            found = classify(card.card_title, card.original_filename, card.page_title or page.title)
            wanted, reason = judge(found.kind, found.version, found.reporting_month, config)
            catalogue.append(
                CatalogueEntry(
                    page_url=card.page_url,
                    page_title=card.page_title or page.title,
                    card_title=card.card_title,
                    source_url=card.source_url,
                    original_filename=card.original_filename,
                    file_type=card.file_type,
                    size_text=card.size_text,
                    kind=found.kind,
                    version=found.version,
                    reporting_month=found.reporting_month or "",
                    revision=found.revision,
                    wanted=wanted,
                    reason=reason,
                )
            )
    LOGGER.info("Classified %s files, %s wanted", len(catalogue), sum(c.wanted for c in catalogue))
    return catalogue


def download(session: requests.Session, url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, timeout=300, stream=True) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)


def collect_new(
    session: requests.Session,
    catalogue: list[CatalogueEntry],
    manifest: list[ManifestEntry],
    assets_dir: Path,
    limit: int | None = None,
    delay: float = 1.0,
) -> list[ManifestEntry]:
    """Download wanted files whose source URL is not yet in the manifest."""
    known = {row.source_url for row in manifest}
    todo = [c for c in catalogue if c.wanted and c.source_url not in known]
    todo.sort(key=lambda c: (c.reporting_month, c.kind, c.version), reverse=True)
    if limit is not None:
        todo = todo[:limit]
    LOGGER.info("%s wanted files are new", len(todo))

    new_rows = []
    tmp = assets_dir / ".download"
    for entry in todo:
        time.sleep(delay)
        temp_file = tmp / entry.original_filename
        LOGGER.info("Downloading %s %s %s", entry.kind, entry.reporting_month, entry.version)
        download(session, entry.source_url, temp_file)
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_rows.append(store_file(temp_file, entry, assets_dir, stamp))
        temp_file.unlink()
    return new_rows


def write_summary(catalogue: list[CatalogueEntry], new_rows: list[ManifestEntry], path: Path) -> None:
    """Write a short Markdown summary for the GitHub Actions job page."""
    wanted = [c for c in catalogue if c.wanted]
    kinds: dict[str, int] = {}
    for c in catalogue:
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    lines = [
        "## MHSDS ingest",
        "",
        f"- Files listed on release pages in scope {len(catalogue)}",
        f"- Files wanted {len(wanted)}",
        f"- New files collected this run {len(new_rows)}",
        "",
        "| Kind | Files listed |",
        "|---|---:|",
        *[f"| {k} | {n} |" for k, n in sorted(kinds.items())],
    ]
    if new_rows:
        lines += ["", "| New asset | Bytes stored |", "|---|---:|"]
        lines += [f"| {r.asset_name} | {r.stored_bytes:,} |" for r in new_rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Collect MHSDS Monthly Statistics files from NHS England.")
    parser.add_argument("command", choices=["discover", "run"])
    parser.add_argument("--config", type=Path, default=Path("config/sources.yaml"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/interim/ingest"))
    parser.add_argument("--manifest", type=Path, help="existing manifest.csv, if any")
    parser.add_argument("--limit", type=int, help="download at most this many new files")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds to wait between requests")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = IngestConfig.from_sources_yaml(args.config)
    session = make_session()
    catalogue = discover(session, config, args.delay)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_catalogue(catalogue, args.out_dir / "catalogue.csv")

    new_rows: list[ManifestEntry] = []
    if args.command == "run":
        existing = read_manifest(args.manifest) if args.manifest else []
        new_rows = collect_new(session, catalogue, existing, args.out_dir / "assets", args.limit, args.delay)
        write_manifest(existing + new_rows, args.out_dir / "manifest.csv")
        (args.out_dir / "new_assets.txt").write_text("".join(f"{r.asset_name}\n" for r in new_rows), encoding="utf-8")
    write_summary(catalogue, new_rows, args.out_dir / "summary.md")


if __name__ == "__main__":
    main()
