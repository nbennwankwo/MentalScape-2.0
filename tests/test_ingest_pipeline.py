"""Tests for page parsing, the manifest and the download loop, with no network access."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from mentalscape.ingest import mhsds
from mentalscape.ingest.manifest import (
    CatalogueEntry,
    ManifestEntry,
    preferred_files,
    read_manifest,
    store_file,
    write_manifest,
)
from mentalscape.ingest.nhs_pages import page_in_scope, parse_release_page, parse_series_page

FIXTURES = Path(__file__).parent / "fixtures" / "nhs"
SERIES_URL = mhsds.SERIES_URL
CONFIG = mhsds.IngestConfig(
    first_month="2022-07",
    kinds_wanted=frozenset({"main", "oaps", "dq_vodim"}),
    versions_wanted=frozenset({"final", "performance"}),
)


def test_series_page_lists_release_pages_once():
    pages = parse_series_page((FIXTURES / "series_page.html").read_text())
    urls = [p.url for p in pages]
    assert len(urls) == len(set(urls)) == 5
    assert all(u.startswith(SERIES_URL + "/") for u in urls)
    in_scope = {p.url.rsplit("/", 1)[-1] for p in pages if page_in_scope(p, 2022)}
    assert "final-november-provisional-december-2019" not in in_scope
    assert {"performance-august-2026", "national-estimates"} <= in_scope


def test_release_page_cards_are_parsed():
    cards = parse_release_page((FIXTURES / "release_page.html").read_text(), "https://example.test/page")
    assert len(cards) == 5  # the article link to the data hub is not a file
    main = next(c for c in cards if "MHSDS Data File" in c.card_title)
    assert main.original_filename == "MHSDS Data_AprPerf_2026 v2.zip"
    assert (main.file_type, main.size_text) == ("zip", "11 MB")
    assert main.page_title == "Mental Health Services Monthly Statistics, Performance April 2026"


def test_judge_explains_skips():
    assert mhsds.judge("main", "final", "2025-08", CONFIG) == (True, "")
    assert mhsds.judge("main", "provisional", "2025-08", CONFIG)[1] == "version provisional not wanted"
    assert mhsds.judge("ascof", "final", "2025-08", CONFIG)[1] == "kind ascof not wanted"
    assert mhsds.judge("main", "final", "2022-06", CONFIG)[1] == "before first month in scope"
    assert mhsds.judge("main", "final", None, CONFIG)[1] == "no reporting month in title"


def _entry(**overrides) -> CatalogueEntry:
    base = dict(
        page_url="https://example.test/page",
        page_title="t",
        card_title="c",
        source_url="https://files.digital.nhs.uk/x/y/file.csv",
        original_filename="file.csv",
        file_type="csv",
        size_text="1 KB",
        kind="main",
        version="final",
        reporting_month="2025-08",
        revision=1,
        wanted=True,
        reason="",
    )
    base.update(overrides)
    return CatalogueEntry(**base)


def test_store_file_gzips_csv_and_keeps_zip(tmp_path: Path):
    csv_file = tmp_path / "file.csv"
    csv_file.write_text("a,b\n1,2\n")
    row = store_file(csv_file, _entry(), tmp_path / "assets", "2026-10-22T00:00:00Z")
    assert row.asset_name.startswith("mhsds__main__2025-08__final__r1__") and row.asset_name.endswith(".csv.gz")
    with gzip.open(tmp_path / "assets" / row.asset_name) as handle:
        assert handle.read() == b"a,b\n1,2\n"

    zip_file = tmp_path / "file.zip"
    zip_file.write_bytes(b"PK fake zip")
    zrow = store_file(zip_file, _entry(original_filename="file.zip", file_type="zip"), tmp_path / "assets", "t")
    assert zrow.asset_name.endswith(".zip") and zrow.stored_sha256 == zrow.original_sha256


def _row(month: str, version: str, revision: int = 1, stamp: str = "2026-01-01T00:00:00Z") -> ManifestEntry:
    return ManifestEntry(
        asset_name=f"{month}-{version}-{revision}",
        kind="main",
        reporting_month=month,
        version=version,
        revision=revision,
        source_url=f"u-{month}-{version}-{revision}",
        page_url="p",
        card_title="c",
        original_filename="f",
        original_bytes=1,
        original_sha256="s",
        stored_bytes=1,
        stored_sha256="s",
        downloaded_at_utc=stamp,
    )


def test_preferred_files_prefers_final_then_revision():
    rows = [
        _row("2025-08", "performance"),
        _row("2025-08", "final"),
        _row("2026-04", "performance", 1),
        _row("2026-04", "performance", 2),
    ]
    chosen = {r.reporting_month: (r.version, r.revision) for r in preferred_files(rows, "main")}
    assert chosen == {"2025-08": ("final", 1), "2026-04": ("performance", 2)}


def test_manifest_round_trip(tmp_path: Path):
    rows = [_row("2025-08", "final"), _row("2024-01", "performance")]
    write_manifest(rows, tmp_path / "manifest.csv")
    by_name = lambda rs: sorted(rs, key=lambda r: r.asset_name)  # noqa: E731
    assert by_name(read_manifest(tmp_path / "manifest.csv")) == by_name(rows)
    assert read_manifest(tmp_path / "missing.csv") == []


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body
        self.status_code = 200

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeSession:
    def __init__(self):
        self.calls: list[str] = []

    def get(self, url, timeout=None, stream=False):
        self.calls.append(url)
        return FakeResponse(b"MEASURE_ID\nMHS01\n")


def test_collect_new_skips_files_already_in_manifest(tmp_path: Path):
    catalogue = [
        _entry(source_url="https://files.digital.nhs.uk/a/new.csv", original_filename="new.csv"),
        _entry(source_url="https://files.digital.nhs.uk/a/old.csv", original_filename="old.csv"),
        _entry(source_url="https://files.digital.nhs.uk/a/skip.csv", wanted=False, reason="kind not wanted"),
    ]
    existing = [_row("2025-07", "final")]
    existing[0] = ManifestEntry(**{**existing[0].__dict__, "source_url": "https://files.digital.nhs.uk/a/old.csv"})
    session = FakeSession()
    new = mhsds.collect_new(session, catalogue, existing, tmp_path / "assets", delay=0)
    assert session.calls == ["https://files.digital.nhs.uk/a/new.csv"]
    assert len(new) == 1 and (tmp_path / "assets" / new[0].asset_name).exists()


@pytest.mark.parametrize("limit", [0, 1])
def test_collect_new_respects_limit(tmp_path: Path, limit: int):
    catalogue = [
        _entry(
            source_url=f"https://files.digital.nhs.uk/a/{i}.csv",
            original_filename=f"{i}.csv",
            reporting_month=f"2025-0{i}",
        )
        for i in range(1, 4)
    ]
    new = mhsds.collect_new(FakeSession(), catalogue, [], tmp_path / "assets", limit=limit, delay=0)
    assert len(new) == limit
