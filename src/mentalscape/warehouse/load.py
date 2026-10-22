"""Load collected MHSDS files into the raw schema of the warehouse.

The raw schema is an exact copy of the source files, with every value kept as
text, plus a few columns that say which file each row came from. Cleaning and
typing happen later in dbt.

    raw.mhsds_main    every row of the preferred main data file for each month
    raw.mhsds_files   every row of the manifest, with a flag for the preferred file

Only the preferred version of each month is loaded (docs/adr/0003). Every
version stays available in the data release.

Two targets are supported (docs/adr/0010).

    python -m mentalscape.warehouse.load --manifest data/raw/release/manifest.csv \\
        --assets data/raw/release --target duckdb
    python -m mentalscape.warehouse.load ... --target postgres --dsn "$DATABASE_URL"
"""

from __future__ import annotations

import argparse
import gzip
import logging
import os
import shutil
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, fields
from pathlib import Path

from mentalscape.ingest.manifest import ManifestEntry, preferred_files, read_manifest
from mentalscape.profiling.mhsds_release_profile import EXPECTED_COLUMNS, normalise_line_endings

LOGGER = logging.getLogger(__name__)

META_COLUMNS = ("_asset_name", "_kind", "_reporting_month", "_version", "_revision", "_source_url")
SOURCE_COLUMNS = tuple(c.lower() for c in EXPECTED_COLUMNS)
MANIFEST_COLUMNS = (*(f.name for f in fields(ManifestEntry)), "is_preferred")


def materialise_csv(asset: Path, work_dir: Path) -> Path:
    """Turn a stored asset into a plain CSV file that reads cleanly."""
    work_dir.mkdir(parents=True, exist_ok=True)
    name = asset.name
    if name.endswith(".zip"):
        with zipfile.ZipFile(asset) as archive:
            members = [m for m in archive.infolist() if m.filename.lower().endswith(".csv")]
            if not members:
                raise ValueError(f"No CSV inside {asset}")
            member = max(members, key=lambda m: m.file_size)
            target = work_dir / (asset.stem + ".csv")
            with archive.open(member) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
    elif name.endswith(".csv.gz"):
        target = work_dir / name.removesuffix(".gz")
        with gzip.open(asset, "rb") as source, target.open("wb") as sink:
            shutil.copyfileobj(source, sink)
    elif name.endswith(".csv"):
        target = asset
    else:
        raise ValueError(f"Do not know how to read {asset}")
    clean, endings = normalise_line_endings(target, work_dir / "normalised")
    if endings.startswith("mixed"):
        LOGGER.info("%s has %s, read from a normalised copy", name, endings)
    check_header(clean)
    return clean


def check_header(csv_path: Path) -> None:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        header = handle.readline().strip().split(",")
    found = tuple(h.strip().strip('"').upper() for h in header)
    if found != EXPECTED_COLUMNS:
        raise ValueError(f"{csv_path.name} has columns {found}, expected {EXPECTED_COLUMNS}")


def choose_files(manifest: list[ManifestEntry], kind: str, first_month: str | None = None) -> list[ManifestEntry]:
    chosen = preferred_files(manifest, kind)
    return [r for r in chosen if first_month is None or r.reporting_month >= first_month]


def _manifest_rows(manifest: list[ManifestEntry], chosen: list[ManifestEntry]) -> list[tuple]:
    chosen_names = {r.asset_name for r in chosen}
    return [(*asdict(r).values(), r.asset_name in chosen_names) for r in manifest]


class DuckDBTarget:
    """Raw loading into a DuckDB file."""

    def __init__(self, path: Path):
        import duckdb

        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))

    def reset(self) -> None:
        self.con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        self.con.execute("DROP TABLE IF EXISTS raw.mhsds_main")
        self.con.execute("DROP TABLE IF EXISTS raw.mhsds_files")
        cols = ", ".join(f"{c} VARCHAR" for c in SOURCE_COLUMNS + META_COLUMNS)
        self.con.execute(f"CREATE TABLE raw.mhsds_main ({cols})")
        manifest_cols = ", ".join(f"{c} VARCHAR" for c in MANIFEST_COLUMNS)
        self.con.execute(f"CREATE TABLE raw.mhsds_files ({manifest_cols})")

    def load_csv(self, csv_path: Path, row: ManifestEntry) -> int:
        names = "[" + ", ".join(f"'{c}'" for c in SOURCE_COLUMNS) + "]"
        meta = (row.asset_name, row.kind, row.reporting_month, row.version, str(row.revision), row.source_url)
        before = self.con.execute("SELECT count(*) FROM raw.mhsds_main").fetchone()[0]
        self.con.execute(
            f"""
            INSERT INTO raw.mhsds_main
            SELECT *, ?, ?, ?, ?, ?, ?
            FROM read_csv(?, header = true, all_varchar = true, delim = ',', quote = '"', escape = '"',
                          names = {names})
            """,
            [*meta, str(csv_path)],
        )
        return self.con.execute("SELECT count(*) FROM raw.mhsds_main").fetchone()[0] - before

    def load_manifest(self, rows: list[tuple]) -> None:
        marks = ", ".join("?" for _ in MANIFEST_COLUMNS)
        self.con.executemany(f"INSERT INTO raw.mhsds_files VALUES ({marks})", [[str(v) for v in r] for r in rows])

    def close(self) -> None:
        self.con.close()


class PostgresTarget:
    """Raw loading into PostgreSQL using COPY, the fastest way to load text."""

    def __init__(self, dsn: str):
        import psycopg

        self.con = psycopg.connect(dsn, autocommit=True)

    def reset(self) -> None:
        with self.con.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS raw")
            # CASCADE also drops the dbt staging views built on these tables. dbt rebuilds them.
            cur.execute("DROP TABLE IF EXISTS raw.mhsds_main CASCADE")
            cur.execute("DROP TABLE IF EXISTS raw.mhsds_files CASCADE")
            cols = ", ".join(f"{c} TEXT" for c in SOURCE_COLUMNS + META_COLUMNS)
            cur.execute(f"CREATE TABLE raw.mhsds_main ({cols})")
            cur.execute(f"CREATE TABLE raw.mhsds_files ({', '.join(f'{c} TEXT' for c in MANIFEST_COLUMNS)})")

    def load_csv(self, csv_path: Path, row: ManifestEntry) -> int:
        source_cols = ", ".join(SOURCE_COLUMNS)
        meta = (row.asset_name, row.kind, row.reporting_month, row.version, str(row.revision), row.source_url)
        with self.con.cursor() as cur:
            cur.execute(f"CREATE TEMP TABLE incoming ({', '.join(f'{c} TEXT' for c in SOURCE_COLUMNS)})")
            copy_sql = f"COPY incoming ({source_cols}) FROM STDIN WITH (FORMAT csv, HEADER true)"
            with cur.copy(copy_sql) as copy, csv_path.open("rb") as handle:
                while chunk := handle.read(1 << 20):
                    copy.write(chunk)
            cur.execute(f"INSERT INTO raw.mhsds_main SELECT {source_cols}, %s, %s, %s, %s, %s, %s FROM incoming", meta)
            loaded = cur.rowcount
            cur.execute("DROP TABLE incoming")
        return loaded

    def load_manifest(self, rows: list[tuple]) -> None:
        marks = ", ".join("%s" for _ in MANIFEST_COLUMNS)
        with self.con.cursor() as cur:
            cur.executemany(f"INSERT INTO raw.mhsds_files VALUES ({marks})", [[str(v) for v in r] for r in rows])

    def close(self) -> None:
        self.con.close()


@contextmanager
def open_target(kind: str, duckdb_path: Path, dsn: str | None) -> Iterator[DuckDBTarget | PostgresTarget]:
    if kind == "duckdb":
        target: DuckDBTarget | PostgresTarget = DuckDBTarget(duckdb_path)
    elif dsn:
        target = PostgresTarget(dsn)
    else:
        raise ValueError("PostgreSQL needs --dsn or the DATABASE_URL environment variable")
    try:
        yield target
    finally:
        target.close()


def load(
    manifest_path: Path,
    assets_dir: Path,
    target_kind: str,
    duckdb_path: Path,
    dsn: str | None = None,
    first_month: str | None = None,
    work_dir: Path = Path("data/interim/load"),
) -> int:
    """Rebuild the raw schema from the preferred main data file of every month."""
    manifest = read_manifest(manifest_path)
    chosen = choose_files(manifest, "main", first_month)
    LOGGER.info("Loading %s monthly main data files", len(chosen))
    total = 0
    with open_target(target_kind, duckdb_path, dsn) as target:
        target.reset()
        target.load_manifest(_manifest_rows(manifest, chosen))
        for row in chosen:
            csv_path = materialise_csv(assets_dir / row.asset_name, work_dir)
            loaded = target.load_csv(csv_path, row)
            LOGGER.info("%s %s %s rows", row.reporting_month, row.version, f"{loaded:,}")
            total += loaded
            if csv_path.parent == work_dir or work_dir in csv_path.parents:
                csv_path.unlink(missing_ok=True)
    LOGGER.info("Loaded %s rows in total", f"{total:,}")
    return total


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load collected MHSDS files into the raw schema.")
    parser.add_argument("--manifest", type=Path, default=Path("data/raw/release/manifest.csv"))
    parser.add_argument("--assets", type=Path, default=Path("data/raw/release"))
    parser.add_argument("--target", choices=["duckdb", "postgres"], default="duckdb")
    parser.add_argument("--duckdb-path", type=Path, default=Path("data/warehouse/mentalscape.duckdb"))
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--first-month", help="only load months from this one, as YYYY-MM")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load(args.manifest, args.assets, args.target, args.duckdb_path, args.dsn, args.first_month)


if __name__ == "__main__":
    main()
