"""Shared machinery for collecting a monthly NHS England statistical series.

MHSDS Monthly Statistics and NHS Talking Therapies are published the same way,
as a series page that links to one page per release, with each file in a
download card. Everything that does not depend on the series lives here. Each
series supplies a SeriesSpec with its own classifier, catalogue and asset
prefix (see mentalscape.ingest.mhsds and mentalscape.ingest.talking_therapies).

The work is split into commands, because NHS England's pages challenge cloud
servers while its files download normally (docs/adr/0011).

    classify  turn a card list saved by tools/discover_in_browser.js into the
              catalogue
    collect   download every wanted file in the catalogue that is not already
              in the manifest. Runs on GitHub Actions.
    check     fail if the catalogue looks out of date
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from mentalscape.ingest.classify import Classification
from mentalscape.ingest.manifest import (
    CatalogueEntry,
    ManifestEntry,
    read_catalogue,
    read_manifest,
    store_file,
    write_catalogue,
    write_manifest,
)
from mentalscape.ingest.nhs_pages import DownloadCard

LOGGER = logging.getLogger(__name__)
USER_AGENT = "MentalScape-2.0 open data pipeline (+https://github.com/nbennwankwo/MentalScape-2.0)"

Classifier = Callable[[str, str, str], Classification]


@dataclass(frozen=True)
class IngestConfig:
    first_month: str
    kinds_wanted: frozenset[str]
    versions_wanted: frozenset[str]

    @classmethod
    def from_sources_yaml(cls, path: Path, key: str = "mhsds_monthly") -> IngestConfig:
        source = yaml.safe_load(path.read_text(encoding="utf-8"))["sources"][key]
        return cls(
            first_month=str(source["first_month_in_scope"]),
            kinds_wanted=frozenset(source["kinds_wanted"]),
            versions_wanted=frozenset(source["versions_wanted"]),
        )


@dataclass(frozen=True)
class SeriesSpec:
    """Everything that differs between one NHS England series and another."""

    key: str
    label: str
    classifier: Classifier
    catalogue: Path
    asset_prefix: str
    main_kind: str


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


def cards_to_catalogue(
    cards: Iterable[DownloadCard], config: IngestConfig, classifier: Classifier
) -> list[CatalogueEntry]:
    """Classify download cards, dropping repeats of the same file."""
    seen: set[str] = set()
    catalogue: list[CatalogueEntry] = []
    for card in cards:
        if card.source_url in seen:
            continue
        seen.add(card.source_url)
        found = classifier(card.card_title, card.original_filename, card.page_title)
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
    asset_prefix: str = "mhsds",
    months: frozenset[str] | None = None,
) -> list[ManifestEntry]:
    """Download wanted files whose source URL is not yet in the manifest, newest first.

    months, when given, limits the run to those reporting months. Trial runs
    use it to try files from different eras of a publication.
    """
    known = {row.source_url for row in manifest}
    todo = [c for c in catalogue if c.wanted and c.source_url not in known]
    if months:
        todo = [c for c in todo if c.reporting_month in months]
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
        new_rows.append(store_file(temp_file, entry, assets_dir, stamp, prefix=asset_prefix))
        temp_file.unlink()
    return new_rows


def months_between(earlier: str, later: str) -> int:
    (y1, m1), (y2, m2) = (map(int, earlier.split("-")), map(int, later.split("-")))
    return (y2 - y1) * 12 + (m2 - m1)


def check_catalogue(
    catalogue: list[CatalogueEntry], today: date, max_lag_months: int = 3, main_kind: str = "main"
) -> tuple[bool, str]:
    """Check the newest wanted main data file is recent enough.

    NHS England publishes a month's data about two months later, so the newest
    main file should never be more than about three months behind today.
    """
    months = sorted(c.reporting_month for c in catalogue if c.wanted and c.kind == main_kind)
    if not months:
        return False, f"The catalogue has no wanted {main_kind} files."
    lag = months_between(months[-1], f"{today.year:04d}-{today.month:02d}")
    if lag > max_lag_months:
        return False, (
            f"The newest {main_kind} file in the catalogue is {months[-1]}, {lag} months ago. "
            "Refresh the catalogue with tools/discover_in_browser.js and the classify command."
        )
    return True, f"The newest {main_kind} file in the catalogue is {months[-1]}, {lag} months ago."


def write_summary(
    catalogue: list[CatalogueEntry], new_rows: list[ManifestEntry], path: Path, label: str = "MHSDS"
) -> None:
    """Write a short Markdown summary for the GitHub Actions job page."""
    wanted = [c for c in catalogue if c.wanted]
    kinds: dict[str, int] = {}
    for c in wanted:
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    lines = [
        f"## {label} ingest",
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


def build_parser(spec: SeriesSpec, commands: list[str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Collect {spec.label} files from NHS England.")
    parser.add_argument("command", choices=commands)
    parser.add_argument("--config", type=Path, default=Path("config/sources.yaml"))
    parser.add_argument("--catalogue", type=Path, default=spec.catalogue)
    parser.add_argument("--cards", type=Path, help="card list saved by tools/discover_in_browser.js")
    parser.add_argument("--out-dir", type=Path, default=Path("data/interim/ingest"))
    parser.add_argument("--manifest", type=Path, help="existing manifest.csv, if any")
    parser.add_argument("--limit", type=int, help="download at most this many new files")
    parser.add_argument("--months", help="only collect these reporting months, comma separated, for trial runs")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds to wait between requests")
    return parser


def run_command(spec: SeriesSpec, args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Run classify, check or collect for a series."""
    config = IngestConfig.from_sources_yaml(args.config, spec.key)
    if args.command == "classify":
        if args.cards is None:
            parser.error("classify needs --cards")
        write_catalogue(cards_to_catalogue(cards_from_json(args.cards), config, spec.classifier), args.catalogue)
    elif args.command == "check":
        ok, message = check_catalogue(read_catalogue(args.catalogue), date.today(), main_kind=spec.main_kind)
        (LOGGER.info if ok else LOGGER.error)("%s", message)
        if not ok:
            sys.exit(1)
    elif args.command == "collect":
        catalogue = read_catalogue(args.catalogue)
        existing = read_manifest(args.manifest) if args.manifest else []
        months = frozenset(args.months.split(",")) if args.months else None
        new_rows = collect_new(
            make_session(),
            catalogue,
            existing,
            args.out_dir / "assets",
            args.limit,
            args.delay,
            spec.asset_prefix,
            months,
        )
        args.out_dir.mkdir(parents=True, exist_ok=True)
        write_manifest(existing + new_rows, args.out_dir / "manifest.csv")
        (args.out_dir / "new_assets.txt").write_text("".join(f"{r.asset_name}\n" for r in new_rows), encoding="utf-8")
        write_summary(catalogue, new_rows, args.out_dir / "summary.md", spec.label)
    else:
        parser.error(f"unknown command {args.command}")


def main(spec: SeriesSpec, argv: list[str] | None = None) -> None:
    parser = build_parser(spec, ["classify", "collect", "check"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_command(spec, args, parser)
