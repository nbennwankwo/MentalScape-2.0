"""Collect MHSDS Monthly Statistics files from NHS England.

NHS England serves its web pages and its files from two different hosts, and
they behave differently for automated clients (see docs/adr/0011).

    digital.nhs.uk        the release pages. These challenge cloud servers
                          such as GitHub Actions runners with a bot check.
    files.digital.nhs.uk  the files themselves. These download normally.

So the work is split into four commands. Everything except discover is shared
with the other NHS England series and lives in mentalscape.ingest.series.

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

import logging
import sys
import time
from collections.abc import Iterable
from datetime import date
from pathlib import Path

import requests

from mentalscape.ingest import series
from mentalscape.ingest.classify import classify
from mentalscape.ingest.manifest import CatalogueEntry, ManifestEntry, write_catalogue
from mentalscape.ingest.nhs_pages import (
    SERIES_URL,
    DownloadCard,
    page_in_scope,
    parse_release_page,
    parse_series_page,
)
from mentalscape.ingest.series import (
    IngestConfig,
    SeriesSpec,
    cards_from_json,
    download,
    judge,
    make_session,
)

__all__ = [
    "SERIES_URL",
    "SPEC",
    "IngestConfig",
    "cards_from_json",
    "cards_to_catalogue",
    "check_catalogue",
    "collect_new",
    "discover",
    "download",
    "judge",
    "make_session",
    "write_summary",
]

LOGGER = logging.getLogger(__name__)
DEFAULT_CATALOGUE = Path("data/reference/mhsds_catalogue.csv")
SPEC = SeriesSpec(
    key="mhsds_monthly",
    label="MHSDS",
    classifier=classify,
    catalogue=DEFAULT_CATALOGUE,
    asset_prefix="mhsds",
    main_kind="main",
)
BLOCKED_MESSAGE = (
    "NHS England returned 403 for its release pages. Its pages challenge automated clients from cloud "
    "servers. Refresh the catalogue from a browser with tools/discover_in_browser.js and the classify "
    "command instead (see docs/data/pipeline.md)."
)


def cards_to_catalogue(cards: Iterable[DownloadCard], config: IngestConfig) -> list[CatalogueEntry]:
    return series.cards_to_catalogue(cards, config, classify)


def collect_new(
    session: requests.Session,
    catalogue: list[CatalogueEntry],
    manifest: list[ManifestEntry],
    assets_dir: Path,
    limit: int | None = None,
    delay: float = 1.0,
) -> list[ManifestEntry]:
    return series.collect_new(session, catalogue, manifest, assets_dir, limit, delay, SPEC.asset_prefix)


def check_catalogue(catalogue: list[CatalogueEntry], today: date, max_lag_months: int = 3) -> tuple[bool, str]:
    return series.check_catalogue(catalogue, today, max_lag_months, SPEC.main_kind)


def write_summary(catalogue: list[CatalogueEntry], new_rows: list[ManifestEntry], path: Path) -> None:
    series.write_summary(catalogue, new_rows, path, SPEC.label)


def discover(session: requests.Session, config: IngestConfig, delay: float = 1.0) -> list[CatalogueEntry]:
    """Read every release page in scope over HTTP and classify every file on it."""
    first_year = int(config.first_month[:4])
    response = session.get(SERIES_URL, timeout=60)
    if response.status_code == 403:
        raise PermissionError(BLOCKED_MESSAGE)
    response.raise_for_status()
    pages = [p for p in parse_series_page(response.text) if page_in_scope(p, first_year)]
    LOGGER.info("Found %s release pages in scope", len(pages))
    cards: list[DownloadCard] = []
    for page in pages:
        time.sleep(delay)
        page_response = session.get(page.url, timeout=60)
        if page_response.status_code == 404:
            LOGGER.info("Skipping %s, not published yet", page.url)
            continue
        page_response.raise_for_status()
        for card in parse_release_page(page_response.text, page.url):
            cards.append(card if card.page_title else DownloadCard(**{**card.__dict__, "page_title": page.title}))
    return cards_to_catalogue(cards, config)


def main(argv: list[str] | None = None) -> None:
    parser = series.build_parser(SPEC, ["discover", "classify", "collect", "check"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "discover":
        config = IngestConfig.from_sources_yaml(args.config, SPEC.key)
        try:
            write_catalogue(discover(make_session(), config, args.delay), args.catalogue)
        except PermissionError as error:
            LOGGER.error("%s", error)
            sys.exit(2)
    else:
        series.run_command(SPEC, args, parser)


if __name__ == "__main__":
    main()
