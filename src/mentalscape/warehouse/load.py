"""Load collected files into the raw schema of the warehouse.

The raw schema is an exact copy of the source files, with every value kept as
text, plus a few columns that say which file each row came from. Cleaning and
typing happen later in dbt.

Each source has its own data release and its own raw tables.

    mhsds               raw.mhsds_main, raw.mhsds_files
    talking_therapies   raw.talking_therapies_activity, raw.talking_therapies_files
    reference           raw.ref_<id> for every file in reference_files, raw.reference_files

Column names come from each file's own header, made safe for SQL by
normalise_column. When files for one table have different columns, as the
IAPT and NHS Talking Therapies files do, the table gets every column and a
file without one leaves it empty.

For the monthly series only the preferred version of each month is loaded
(docs/adr/0003). Every version stays available in the data release.

Two targets are supported (docs/adr/0010).

    python -m mentalscape.warehouse.load --source all --target duckdb
    python -m mentalscape.warehouse.load --source mhsds --target postgres --dsn "$DATABASE_URL"
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import logging
import os
import re
import shutil
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from mentalscape.ingest.manifest import ManifestEntry, preferred_files, read_manifest
from mentalscape.profiling.mhsds_release_profile import EXPECTED_COLUMNS, normalise_line_endings

LOGGER = logging.getLogger(__name__)

META_COLUMNS = ("_asset_name", "_kind", "_reporting_month", "_version", "_revision", "_source_url", "_sheet")
MANIFEST_COLUMNS = (*(f.name for f in fields(ManifestEntry)), "is_preferred")
MAX_IDENTIFIER = 63  # PostgreSQL's limit on column names


@dataclass(frozen=True)
class TableSpec:
    """How the files of one kind become one raw table."""

    table: str
    kinds: tuple[str, ...]
    expected_columns: tuple[str, ...] | None = None
    # For Excel workbooks, the text of the first header cell. Rows above it are
    # titles and notes, and sheets without it are skipped.
    header_marker: str | None = None


@dataclass(frozen=True)
class SourceSpec:
    name: str
    release: str
    files_table: str
    tables: tuple[TableSpec, ...] = field(default_factory=tuple)
    # When true, every kind in the manifest becomes its own table, ref_<kind>.
    table_per_kind: bool = False
    header_markers: dict[str, str] = field(default_factory=dict)


SOURCES: dict[str, SourceSpec] = {
    "mhsds": SourceSpec(
        name="mhsds",
        release="data-mhsds-monthly",
        files_table="mhsds_files",
        tables=(TableSpec("mhsds_main", ("main",), expected_columns=EXPECTED_COLUMNS),),
    ),
    "talking_therapies": SourceSpec(
        name="talking_therapies",
        release="data-talking-therapies-monthly",
        files_table="talking_therapies_files",
        tables=(TableSpec("talking_therapies_activity", ("activity",)),),
    ),
    "reference": SourceSpec(
        name="reference",
        release="data-reference",
        files_table="reference_files",
        table_per_kind=True,
        header_markers={"ons_lsoa_population_2022_2024": "LAD 2023 Code"},
    ),
}


def normalise_column(name: str) -> str:
    """Turn a published column header into a safe, readable SQL column name.

    Long notes in brackets, such as "(where 1 is most deprived 10% of
    LSOAs)", are dropped, short ones such as "(rate)" are kept. A name that is
    still longer than PostgreSQL allows is cut and given a short checksum so
    that it stays unique and the same on every run.
    """
    text = re.sub(r"\(([^)]{13,})\)?", " ", name.strip())
    text = re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_").lower() or "column"
    if text[0].isdigit():
        text = f"c_{text}"
    if len(text) > MAX_IDENTIFIER:
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        text = f"{text[: MAX_IDENTIFIER - 9].rstrip('_')}_{digest}"
    return text


def unique_columns(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for name in names:
        base = normalise_column(name)
        seen[base] = seen.get(base, 0) + 1
        out.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return out


def read_header(csv_path: Path) -> list[str]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


@dataclass(frozen=True)
class Part:
    """One CSV ready to load, with the sheet it came from when the source was a workbook."""

    path: Path
    sheet: str = ""


def _excel_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def excel_to_csv(workbook: Path, work_dir: Path, header_marker: str) -> list[Part]:
    """Write each sheet that holds a table starting with header_marker as its own CSV."""
    from python_calamine import CalamineWorkbook

    book = CalamineWorkbook.from_path(str(workbook))
    parts = []
    for index, sheet_name in enumerate(book.sheet_names):
        sheet = book.get_sheet_by_name(sheet_name)
        target = work_dir / f"{workbook.stem}__sheet{index}.csv"
        found = False
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            for row in sheet.iter_rows():
                cells = [_excel_cell(v) for v in row]
                if not found:
                    found = bool(cells) and cells[0].strip() == header_marker
                    if not found:
                        continue
                if any(cells):
                    writer.writerow(cells)
        if found:
            parts.append(Part(target, sheet_name))
        else:
            target.unlink()
    if not parts:
        raise ValueError(f"No sheet in {workbook.name} has a table starting with {header_marker!r}")
    return parts


def materialise(asset: Path, work_dir: Path, header_marker: str | None = None) -> list[Part]:
    """Turn a stored asset into one or more plain CSV files that read cleanly."""
    work_dir.mkdir(parents=True, exist_ok=True)
    name = asset.name
    if name.endswith(".xlsx"):
        if header_marker is None:
            raise ValueError(f"{name} is a workbook, so it needs a header marker")
        return excel_to_csv(asset, work_dir, header_marker)
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
    return [Part(clean)]


def materialise_csv(asset: Path, work_dir: Path) -> Path:
    """Materialise an MHSDS main data file and check its header, as earlier versions did."""
    part = materialise(asset, work_dir)[0]
    check_header(part.path, EXPECTED_COLUMNS)
    return part.path


def check_header(csv_path: Path, expected: tuple[str, ...]) -> None:
    found = tuple(h.strip().upper() for h in read_header(csv_path))
    if found != expected:
        raise ValueError(f"{csv_path.name} has columns {found}, expected {expected}")


def choose_files(manifest: list[ManifestEntry], kind: str, first_month: str | None = None) -> list[ManifestEntry]:
    chosen = preferred_files(manifest, kind)
    return [r for r in chosen if first_month is None or r.reporting_month >= first_month]


def _manifest_rows(manifest: list[ManifestEntry], chosen: list[ManifestEntry]) -> list[tuple]:
    chosen_names = {r.asset_name for r in chosen}
    return [(*asdict(r).values(), r.asset_name in chosen_names) for r in manifest]


def _meta(row: ManifestEntry, sheet: str) -> tuple[str, ...]:
    return (row.asset_name, row.kind, row.reporting_month, row.version, str(row.revision), row.source_url, sheet)


class DuckDBTarget:
    """Raw loading into a DuckDB file."""

    def __init__(self, path: Path):
        import duckdb

        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))
        self.con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    def create_table(self, table: str, columns: list[str]) -> None:
        self.con.execute(f"DROP TABLE IF EXISTS raw.{table}")
        self.con.execute(f"CREATE TABLE raw.{table} ({', '.join(f'{c} VARCHAR' for c in columns)})")

    def add_column(self, table: str, column: str) -> None:
        self.con.execute(f"ALTER TABLE raw.{table} ADD COLUMN {column} VARCHAR")

    def load_csv(self, table: str, part: Part, columns: list[str], meta: tuple[str, ...]) -> int:
        names = "[" + ", ".join(f"'{c}'" for c in columns) + "]"
        meta_select = ", ".join(f"? AS {c}" for c in META_COLUMNS)
        before = self.con.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]
        self.con.execute(
            f"""
            INSERT INTO raw.{table} BY NAME
            SELECT *, {meta_select}
            FROM read_csv(?, header = true, all_varchar = true, delim = ',', quote = '"', escape = '"',
                          names = {names})
            """,
            [*meta, str(part.path)],
        )
        return self.con.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0] - before

    def load_rows(self, table: str, columns: tuple[str, ...], rows: list[tuple]) -> None:
        self.create_table(table, list(columns))
        marks = ", ".join("?" for _ in columns)
        self.con.executemany(f"INSERT INTO raw.{table} VALUES ({marks})", [[str(v) for v in r] for r in rows])

    def close(self) -> None:
        self.con.close()


class PostgresTarget:
    """Raw loading into PostgreSQL using COPY, the fastest way to load text."""

    def __init__(self, dsn: str):
        import psycopg

        self.con = psycopg.connect(dsn, autocommit=True)
        with self.con.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS raw")

    def create_table(self, table: str, columns: list[str]) -> None:
        with self.con.cursor() as cur:
            # CASCADE also drops the dbt staging views built on this table. dbt rebuilds them.
            cur.execute(f"DROP TABLE IF EXISTS raw.{table} CASCADE")
            cur.execute(f"CREATE TABLE raw.{table} ({', '.join(f'{c} TEXT' for c in columns)})")

    def add_column(self, table: str, column: str) -> None:
        with self.con.cursor() as cur:
            cur.execute(f"ALTER TABLE raw.{table} ADD COLUMN {column} TEXT")

    def load_csv(self, table: str, part: Part, columns: list[str], meta: tuple[str, ...]) -> int:
        file_columns = ", ".join(columns)
        with self.con.cursor() as cur:
            cur.execute(f"CREATE TEMP TABLE incoming ({', '.join(f'{c} TEXT' for c in columns)})")
            copy_sql = f"COPY incoming ({file_columns}) FROM STDIN WITH (FORMAT csv, HEADER true)"
            with cur.copy(copy_sql) as copy, part.path.open("rb") as handle:
                while chunk := handle.read(1 << 20):
                    copy.write(chunk)
            marks = ", ".join("%s" for _ in META_COLUMNS)
            cur.execute(
                f"INSERT INTO raw.{table} ({file_columns}, {', '.join(META_COLUMNS)}) "
                f"SELECT {file_columns}, {marks} FROM incoming",
                meta,
            )
            loaded = cur.rowcount
            cur.execute("DROP TABLE incoming")
        return loaded

    def load_rows(self, table: str, columns: tuple[str, ...], rows: list[tuple]) -> None:
        self.create_table(table, list(columns))
        marks = ", ".join("%s" for _ in columns)
        with self.con.cursor() as cur:
            cur.executemany(f"INSERT INTO raw.{table} VALUES ({marks})", [[str(v) for v in r] for r in rows])

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


def tables_for(spec: SourceSpec, manifest: list[ManifestEntry]) -> list[TableSpec]:
    if not spec.table_per_kind:
        return list(spec.tables)
    kinds = sorted({row.kind for row in manifest})
    return [TableSpec(f"ref_{kind}", (kind,), header_marker=spec.header_markers.get(kind)) for kind in kinds]


def load_table(
    target: DuckDBTarget | PostgresTarget,
    table: TableSpec,
    rows: list[ManifestEntry],
    assets_dir: Path,
    work_dir: Path,
) -> int:
    """Load every chosen file of one table, one file at a time.

    The table starts with the first file's columns. A later file that brings a
    new column adds it, so the table ends up with every column of every file.
    Each file is unpacked into its own folder, which is removed once loaded,
    so only one file is ever unpacked at a time.
    """
    columns: list[str] = []
    total = 0
    for row in rows:
        unpack_dir = work_dir / table.table / row.asset_name.split(".")[0]
        for part in materialise(assets_dir / row.asset_name, unpack_dir, table.header_marker):
            if table.expected_columns:
                check_header(part.path, table.expected_columns)
            file_columns = unique_columns(read_header(part.path))
            if not columns:
                columns = list(file_columns)
                target.create_table(table.table, columns + list(META_COLUMNS))
            for column in file_columns:
                if column not in columns:
                    target.add_column(table.table, column)
                    columns.append(column)
            loaded = target.load_csv(table.table, part, file_columns, _meta(row, part.sheet))
            LOGGER.info("%s %s %s %s rows", table.table, row.reporting_month, row.version, f"{loaded:,}")
            total += loaded
        shutil.rmtree(unpack_dir, ignore_errors=True)
    return total


def load_source(
    target: DuckDBTarget | PostgresTarget,
    spec: SourceSpec,
    manifest_path: Path,
    assets_dir: Path,
    first_month: str | None = None,
    work_dir: Path = Path("data/interim/load"),
) -> int:
    """Rebuild the raw tables of one source from its manifest."""
    manifest = read_manifest(manifest_path)
    if not manifest:
        raise ValueError(f"{manifest_path} lists no files")
    chosen_all: list[ManifestEntry] = []
    total = 0
    for table in tables_for(spec, manifest):
        chosen = [r for kind in table.kinds for r in choose_files(manifest, kind, first_month)]
        if not chosen:
            LOGGER.warning("No %s files to load into raw.%s", "/".join(table.kinds), table.table)
            continue
        chosen_all += chosen
        total += load_table(target, table, chosen, assets_dir, work_dir / spec.name)
    target.load_rows(spec.files_table, MANIFEST_COLUMNS, _manifest_rows(manifest, chosen_all))
    LOGGER.info("Loaded %s rows from %s", f"{total:,}", spec.name)
    return total


def load(
    manifest_path: Path,
    assets_dir: Path,
    target_kind: str,
    duckdb_path: Path,
    dsn: str | None = None,
    first_month: str | None = None,
    work_dir: Path = Path("data/interim/load"),
    source: str = "mhsds",
) -> int:
    """Rebuild the raw tables of one source. Kept for the original MHSDS call signature."""
    with open_target(target_kind, duckdb_path, dsn) as target:
        return load_source(target, SOURCES[source], manifest_path, assets_dir, first_month, work_dir)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load collected files into the raw schema.")
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="mhsds")
    parser.add_argument(
        "--raw-dir", type=Path, default=Path("data/raw"), help="folder holding one folder per data release"
    )
    parser.add_argument("--manifest", type=Path, help="manifest for a single source, overriding --raw-dir")
    parser.add_argument("--assets", type=Path, help="assets for a single source, overriding --raw-dir")
    parser.add_argument("--target", choices=["duckdb", "postgres"], default="duckdb")
    parser.add_argument("--duckdb-path", type=Path, default=Path("data/warehouse/mentalscape.duckdb"))
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--first-month", help="only load months from this one, as YYYY-MM")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    names = list(SOURCES) if args.source == "all" else [args.source]
    if (args.manifest or args.assets) and len(names) > 1:
        parser.error("--manifest and --assets work with a single --source")
    with open_target(args.target, args.duckdb_path, args.dsn) as target:
        for name in names:
            spec = SOURCES[name]
            folder = args.raw_dir / spec.release
            manifest = args.manifest or folder / "manifest.csv"
            assets = args.assets or folder
            load_source(target, spec, manifest, assets, args.first_month)


if __name__ == "__main__":
    main()
