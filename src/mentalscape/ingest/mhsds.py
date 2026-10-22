"""Collect MHSDS Monthly Statistics files from NHS England.

NHS England serves its web pages and its files from two different hosts, and
they behave differently for automated clients (see docs/adr/0011).

    digital.nhs.uk        the release pages. These challenge cloud servers
                          such as GitHub Actions runners with a bot check.
    files.digital.nhs.uk  the files themselves. These download normally.

So the work is split into four commands.

    discover  read the release pages directly over HTTP and write the
              catalogue. Works only where NHS England allows it.
    classify  turn a card list saved by tools/discover_in_browser.js into the
              catalogue. This is how the catalogue is refreshed in practice.
    collect   download every wanted file in the catalogue that is not already
              in the manifest. Runs on GitHub Actions.
    check     fail if the catalogue looks out of date, so a scheduled run
              raises the alarm when it needs refreshing.

Examples

    python -m mentalscape.ingest.mhsds classify --cards mhsds_cards.json
    python -m mentalscape.ingest.mhsds collect --manifest manifest.csv --out-dir data/interim/ingest
    python -m mentalscape.ingest.mhsds check
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from mentalscape.ingest.classify import classify
from mentalscape.ingest.manifest import (
    CatalogueEntry,
    ManifestEntry,
    read_catalogue,
    read_manifest,
    store_file,
    write_catalogue,
    write_manifest,
)
from mentalscape.ingest.nhs_pages import (
    SERIES_URL,
    DownloadCard,
    page_in_scope,
    parse_release_page,
    parse_series_page,
)

LOGGER = logging.getLogger(__name__)
USER_AGENT = "MentalScape-2.0 open data pipeline (+https://github.com/nbennwankwo/MentalScape-2.0)"
DEFAULT_CATALOGUE = Path("data/reference/mhsds_catalogue.csv")
BLOCKED_MESSAGE = (
    "NHS England returned 403 for its release pages. Its pages challenge automated clients from cloud "
    "servers. Refresh the catalogue from a browser with tools/discover_in_browser.js and the classify "
    "command instead (see docs/data/pipeline.md)."
)


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


def cards_to_catalogue(cards: Iterable[DownloadCard], config: IngestConfig) -> list[CatalogueEntry]:
    """Classify download cards, dropping repeats of the same file."""
    seen: set[str] = set()
    catalogue: list[CatalogueEntry] = []
    for card in cards:
        if card.source_url in seen:
            continue
        seen.add(card.source_url)
        found = classify(card.card_title, card.original_filename, card.page_title)
        wanted, reason = judge(found.kind, found.version, found.reporting_month, config)
        catalogue.append(
            CatalogueEntry(
                page_url=card.page_url,
                page_title=card.page_title,
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
                note=found.note,
            )
        )
    LOGGER.info("Classified %s files, %s wanted", len(catalogue), sum(c.wanted for c in catalogue))
    return catalogue


def cards_from_json(path: Path) -> list[DownloadCard]:
    """Read the card list saved by tools/discover_in_browser.js."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [DownloadCard(**card) for card in payload["cards"]]


def discover(session: requests.Session, config: IngestConfig, delay: float = 1.0) -> list[CatalogueEntry]:
    """Read every release page in scope over HTTP and classify every file on it."""
    first_year = int(config.first_month[:4])
    series = session.get(SERIES_URL, timeout=60)
    if series.status_code == 403:
        raise PermissionError(BLOCKED_MESSAGE)
    series.raise_for_status()
    pages = [p for p in parse_series_page(series.text) if page_in_scope(p, first_year)]
    LOGGER.info("Found %s release pages in scope", len(pages))
    cards: list[DownloadCard] = []
    for page in pages:
        time.sleep(delay)
        response = session.get(page.url, timeout=60)
        if response.status_code == 404:
            LOGGER.info("Skipping %s, not published yet", page.url)
            continue
        response.raise_for_status()
        for card in parse_release_page(response.text, page.url):
            cards.append(card if card.page_title else DownloadCard(**{**card.__dict__, "page_title": page.title}))
    return cards_to_catalogue(cards, config)


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
    """Download wanted files whose source URL is not yet in the manifest, newest first."""
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
        LOGGER.info("Downloading %s %s %s r%s", entry.kind, entry.reporting_month, entry.version, entry.revision)
        download(session, entry.source_url, temp_file)
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_rows.append(store_file(temp_file, entry, assets_dir, stamp))
        temp_file.unlink()
    return new_rows


def months_between(earlier: str, later: str) -> int:
    (y1, m1), (y2, m2) = (map(int, earlier.split("-")), map(int, later.split("-")))
    return (y2 - y1) * 12 + (m2 - m1)


def check_catalogue(catalogue: list[CatalogueEntry], today: date, max_lag_months: int = 3) -> tuple[bool, str]:
    """Check the newest wanted main data file is recent enough.

    NHS England publishes a month's data about two months later, so the newest
    main file should never be more than about three months behind today.
    """
    months = sorted(c.reporting_month for c in catalogue if c.wanted and c.kind == "main")
    if not months:
        return False, "The catalogue has no wanted main data files."
    lag = months_between(months[-1], f"{today.year:04d}-{today.month:02d}")
    if lag > max_lag_months:
        return False, (
            f"The newest main data file in the catalogue is {months[-1]}, {lag} months ago. "
            "Refresh the catalogue with tools/discover_in_browser.js and the classify command."
        )
    return True, f"The newest main data file in the catalogue is {months[-1]}, {lag} months ago."


def write_summary(catalogue: list[CatalogueEntry], new_rows: list[ManifestEntry], path: Path) -> None:
    """Write a short Markdown summary for the GitHub Actions job page."""
    wanted = [c for c in catalogue if c.wanted]
    kinds: dict[str, int] = {}
    for c in wanted:
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    lines = [
        "## MHSDS ingest",
        "",
        f"- Files in the catalogue {len(catalogue)}",
        f"- Files wanted {len(wanted)}",
        f"- New files collected this run {len(new_rows)}",
        "",
        "| Wanted kind | Files |",
        "|---|---:|",
        *[f"| {k} | {n} |" for k, n in sorted(kinds.items())],
    ]
    if new_rows:
        lines += ["", "| New asset | Bytes stored |", "|---|---:|"]
        lines += [f"| {r.asset_name} | {r.stored_bytes:,} |" for r in new_rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Collect MHSDS Monthly Statistics files from NHS England.")
    parser.add_argument("command", choices=["discover", "classify", "collect", "check"])
    parser.add_argument("--config", type=Path, default=Path("config/sources.yaml"))
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--cards", type=Path, help="card list saved by tools/discover_in_browser.js")
    parser.add_argument("--out-dir", type=Path, default=Path("data/interim/ingest"))
    parser.add_argument("--manifest", type=Path, help="existing manifest.csv, if any")
    parser.add_argument("--limit", type=int, help="download at most this many new files")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds to wait between requests")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = IngestConfig.from_sources_yaml(args.config)

    if args.command == "discover":
        try:
            write_catalogue(discover(make_session(), config, args.delay), args.catalogue)
        except PermissionError as error:
            LOGGER.error("%s", error)
            sys.exit(2)
    elif args.command == "classify":
        if args.cards is None:
            parser.error("classify needs --cards")
        write_catalogue(cards_to_catalogue(cards_from_json(args.cards), config), args.catalogue)
    elif args.command == "check":
        ok, message = check_catalogue(read_catalogue(args.catalogue), date.today())
        (LOGGER.info if ok else LOGGER.error)("%s", message)
        if not ok:
            sys.exit(1)
    else:
        catalogue = read_catalogue(args.catalogue)
        existing = read_manifest(args.manifest) if args.manifest else []
        new_rows = collect_new(make_session(), catalogue, existing, args.out_dir / "assets", args.limit, args.delay)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        write_manifest(existing + new_rows, args.out_dir / "manifest.csv")
        (args.out_dir / "new_assets.txt").write_text("".join(f"{r.asset_name}\n" for r in new_rows), encoding="utf-8")
        write_summary(catalogue, new_rows, args.out_dir / "summary.md")


if __name__ == "__main__":
    main()
