"""Tests for the reference file collector, with no network access."""

from __future__ import annotations

import zipfile
from pathlib import Path

from mentalscape.ingest import reference
from mentalscape.ingest.manifest import read_manifest

REPO = Path(__file__).parents[1]


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeSession:
    def __init__(self, bodies: dict[str, bytes]):
        self.bodies = bodies
        self.calls: list[str] = []

    def get(self, url, timeout=None, stream=False):
        self.calls.append(url)
        return FakeResponse(self.bodies[url])


def _entry(id_: str, filename: str, header: str = "") -> reference.ReferenceFile:
    return reference.ReferenceFile(
        id=id_,
        source="s",
        title=id_,
        edition="2026-04",
        url=f"https://example.test/{id_}",
        filename=filename,
        header_contains=header,
    )


def test_register_in_config_is_readable_and_unique():
    register = reference.read_register(REPO / "config" / "sources.yaml")
    assert len({r.id for r in register}) == len(register) >= 10
    assert all(r.url.startswith("https://") and r.edition for r in register)


def test_error_pages_and_wrong_headers_are_rejected(tmp_path: Path):
    good = tmp_path / "good.csv"
    good.write_text("LSOA21CD,SICBL26CD\n" + "E01000001,93C\n" * 10)
    page = tmp_path / "page.csv"
    page.write_text("<!DOCTYPE html><html>" + "x" * 200)
    wrong = tmp_path / "wrong.csv"
    wrong.write_text("FID,NAME\n" + "1,a\n" * 50)
    entry = _entry("lookup", "lookup.csv", "SICBL26CD")
    assert reference.looks_right(good, entry) == (True, "")
    assert not reference.looks_right(page, entry)[0]
    assert "header" in reference.looks_right(wrong, entry)[1]


def test_xlsx_must_be_a_zip_file(tmp_path: Path):
    real = tmp_path / "real.xlsx"
    with zipfile.ZipFile(real, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>" * 20)
    fake = tmp_path / "fake.xlsx"
    fake.write_text("not a workbook " * 20)
    entry = _entry("pop", "pop.xlsx")
    assert reference.looks_right(real, entry)[0] and not reference.looks_right(fake, entry)[0]


def test_collect_skips_known_files_and_reports_bad_ones(tmp_path: Path):
    good, bad = _entry("good", "good.csv", "CODE"), _entry("bad", "bad.csv", "CODE")
    session = FakeSession({good.url: b"CODE,NAME\n" + b"E1,a\n" * 40, bad.url: b"<html>" + b"x" * 200})
    rows, problems = reference.collect_new(session, [good, bad], [], tmp_path / "assets", delay=0)
    assert [r.kind for r in rows] == ["good"] and rows[0].asset_name.startswith("reference__good__2026-04__")
    assert len(problems) == 1 and problems[0].startswith("bad")
    again, _ = reference.collect_new(session, [good], rows, tmp_path / "assets", delay=0)
    assert again == [] and session.calls.count(good.url) == 1
    assert reference.missing_from_manifest([good, bad], rows) == ["bad"]


def test_main_writes_manifest_and_summary(tmp_path: Path, monkeypatch):
    config = tmp_path / "sources.yaml"
    config.write_text(
        "reference_files:\n  small:\n    source: s\n    title: Small\n    edition: '2026-04'\n"
        "    url: https://example.test/small\n    filename: small.csv\n    header_contains: CODE\n"
    )
    monkeypatch.setattr(
        reference, "make_session", lambda: FakeSession({"https://example.test/small": b"CODE\n" + b"E1\n" * 60})
    )
    reference.main(["collect", "--config", str(config), "--out-dir", str(tmp_path / "out"), "--delay", "0"])
    manifest = read_manifest(tmp_path / "out" / "manifest.csv")
    assert [m.kind for m in manifest] == ["small"]
    assert "Every registered file is collected" in (tmp_path / "out" / "summary.md").read_text()
