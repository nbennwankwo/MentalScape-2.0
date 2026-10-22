"""Profile the main data file of each MHSDS Monthly Statistics release.

Every monthly release of the Mental Health Services Monthly Statistics comes
with one large long-format CSV. Each row holds one value for one measure, for
one organisation or area, for one breakdown (for example "Sub ICB of GP
Practice or Residence; Age Band").

This module reads those files with DuckDB, which lets us describe a file of
close to a million rows with a handful of SQL queries, and writes five small
tidy tables per release.

    releases        one row per release with its shape and schema
    measures        one row per measure ID and name in a release
    breakdowns      one row per breakdown in a release
    geography       one row per organisation or area code in a release
    england_values  the England level value of every measure in a release

The tables are written as CSV so they can be read by anyone and diffed in git.

Run it from the repository root, for example

    python -m mentalscape.profiling.mhsds_release_profile data/raw/mhsds_monthly --out data/interim/profiles
"""

from __future__ import annotations

import argparse
import logging
import re
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

LOGGER = logging.getLogger(__name__)

# Columns found in every main data file published from July 2022 onwards.
EXPECTED_COLUMNS = (
    "REPORTING_PERIOD_START",
    "REPORTING_PERIOD_END",
    "STATUS",
    "BREAKDOWN",
    "PRIMARY_LEVEL",
    "PRIMARY_LEVEL_DESCRIPTION",
    "SECONDARY_LEVEL",
    "SECONDARY_LEVEL_DESCRIPTION",
    "MEASURE_ID",
    "MEASURE_NAME",
    "MEASURE_VALUE",
)

# The publication uses an asterisk for values suppressed to protect privacy.
SUPPRESSION_MARKER = "*"

# Dates have been published as both 01/07/2022 and 2022-07-01 over the years.
# Dates have been published in five styles, 01/07/2022, 1/4/2024, 01/06/24,
# 2023-06-01 and 01-04-2025. Each is matched exactly so that a two digit year
# is never read as a year in the first century.
DATE_SQL = (
    "CASE "
    "WHEN regexp_matches(trim({col}), '^[0-9]{{1,2}}/[0-9]{{1,2}}/[0-9]{{4}}$') THEN strptime(trim({col}), '%d/%m/%Y') "
    "WHEN regexp_matches(trim({col}), '^[0-9]{{1,2}}/[0-9]{{1,2}}/[0-9]{{2}}$') THEN strptime(trim({col}), '%d/%m/%y') "
    "WHEN regexp_matches(trim({col}), '^[0-9]{{4}}-[0-9]{{1,2}}-[0-9]{{1,2}}$') THEN strptime(trim({col}), '%Y-%m-%d') "
    "WHEN regexp_matches(trim({col}), '^[0-9]{{1,2}}-[0-9]{{1,2}}-[0-9]{{4}}$') THEN strptime(trim({col}), '%d-%m-%Y') "
    "END"
)


@dataclass(frozen=True)
class ReleaseProfile:
    """The five summary tables for one release."""

    release: pd.DataFrame
    measures: pd.DataFrame
    breakdowns: pd.DataFrame
    geography: pd.DataFrame
    england_values: pd.DataFrame


def _date(col: str) -> str:
    return DATE_SQL.format(col=col)


def find_input_files(inputs: Iterable[Path], extract_dir: Path) -> Iterator[Path]:
    """Yield CSV paths from a mix of CSV files, zip files and folders.

    Zip files are opened and the largest CSV inside is taken as the main data
    file. It is extracted once into extract_dir and reused on later runs.
    """
    for item in inputs:
        if item.is_dir():
            children = sorted(p for p in item.rglob("*") if p.suffix.lower() in {".csv", ".zip"})
            yield from find_input_files(children, extract_dir)
        elif item.suffix.lower() == ".csv":
            yield item
        elif item.suffix.lower() == ".zip":
            yield _extract_main_csv(item, extract_dir)
        else:
            LOGGER.warning("Skipping %s because it is not a CSV or zip file", item)


def _extract_main_csv(zip_path: Path, extract_dir: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        members = [m for m in archive.infolist() if m.filename.lower().endswith(".csv")]
        if not members:
            raise ValueError(f"No CSV found inside {zip_path}")
        main = max(members, key=lambda m: m.file_size)
        target = extract_dir / zip_path.stem / Path(main.filename).name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(main) as source, target.open("wb") as sink:
                while chunk := source.read(1 << 20):
                    sink.write(chunk)
        return target


def count_line_endings(csv_path: Path) -> tuple[int, int]:
    """Return the number of Windows style (CRLF) line endings and of all line endings."""
    crlf = total = 0
    previous_ended_in_cr = False
    with csv_path.open("rb") as handle:
        while chunk := handle.read(1 << 22):
            total += chunk.count(b"\n")
            crlf += chunk.count(b"\r\n")
            if previous_ended_in_cr and chunk.startswith(b"\n"):
                crlf += 1
            previous_ended_in_cr = chunk.endswith(b"\r")
    return crlf, total


def _normalised_copy(csv_path: Path, work_dir: Path) -> Path:
    """Write a copy of csv_path with every CRLF turned into LF."""
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / csv_path.name
    with csv_path.open("rb") as source, target.open("wb") as sink:
        carry = b""
        while chunk := source.read(1 << 22):
            chunk = carry + chunk
            carry = b"\r" if chunk.endswith(b"\r") else b""
            if carry:
                chunk = chunk[:-1]
            sink.write(chunk.replace(b"\r\n", b"\n"))
        sink.write(carry)
    return target


def _load(con: duckdb.DuckDBPyConnection, csv_path: Path, work_dir: Path) -> tuple[list[str], str]:
    """Load one CSV into a table called raw.

    Returns the original column names and a description of the line endings.
    Some legacy files mix Unix and Windows line endings because two published
    parts were joined into one file. Those files are read from a normalised
    copy so that every row parses the same way.
    """
    crlf, total = count_line_endings(csv_path)
    if crlf == 0:
        line_endings, read_path = "LF", csv_path
    elif crlf == total:
        line_endings, read_path = "CRLF", csv_path
    else:
        line_endings = f"mixed ({crlf} of {total} lines CRLF)"
        read_path = _normalised_copy(csv_path, work_dir)

    con.execute("DROP TABLE IF EXISTS raw")
    # The dialect is stated explicitly rather than guessed from a sample.
    con.execute(
        """
        CREATE TABLE raw AS SELECT * FROM read_csv(
            ?, all_varchar = true, header = true, delim = ',', quote = '"', escape = '"'
        )
        """,
        [str(read_path)],
    )
    original = [row[0] for row in con.execute("DESCRIBE raw").fetchall()]
    renames = {c: re.sub(r"\W+", "_", c.strip().upper()).strip("_") for c in original}
    for old, new in renames.items():
        if old != new:
            con.execute(f'ALTER TABLE raw RENAME COLUMN "{old}" TO {new}')
    missing = [c for c in EXPECTED_COLUMNS if c not in renames.values()]
    if missing:
        raise ValueError(f"{csv_path.name} is missing expected columns {missing}")
    return original, line_endings


def profile_file(
    csv_path: Path,
    con: duckdb.DuckDBPyConnection | None = None,
    work_dir: Path = Path("data/interim/normalised"),
) -> ReleaseProfile:
    """Profile one main data file and return its summary tables."""
    con = con or duckdb.connect()
    original_columns, line_endings = _load(con, csv_path, work_dir)

    # Trimmed working view so that stray spaces never create false differences.
    con.execute(
        f"""
        CREATE OR REPLACE VIEW t AS
        SELECT
            {_date("REPORTING_PERIOD_START")}::DATE AS period_start,
            {_date("REPORTING_PERIOD_END")}::DATE AS period_end,
            REPORTING_PERIOD_START AS period_start_raw,
            STATUS AS status_raw,
            trim(BREAKDOWN) AS breakdown,
            trim(split_part(BREAKDOWN, ';', 1)) AS geo_level,
            trim(PRIMARY_LEVEL) AS primary_code,
            trim(PRIMARY_LEVEL_DESCRIPTION) AS primary_name,
            trim(MEASURE_ID) AS measure_id,
            trim(regexp_replace(MEASURE_NAME, '\\s+', ' ', 'g')) AS measure_name,
            trim(MEASURE_VALUE) AS measure_value,
            trim(MEASURE_VALUE) = '{SUPPRESSION_MARKER}' AS is_suppressed,
            try_cast(trim(MEASURE_VALUE) AS DOUBLE) AS value_num
        FROM raw
        """
    )

    release_end = con.execute("SELECT max(period_end) FROM t").fetchone()[0]
    if release_end is None:
        raise ValueError(f"Could not read reporting period dates in {csv_path.name}")
    release_month = pd.Timestamp(release_end).strftime("%Y-%m")

    statuses = [r[0] for r in con.execute("SELECT DISTINCT status_raw FROM t ORDER BY 1").fetchall()]
    n_dmy, n_iso = con.execute(
        "SELECT sum((period_start_raw LIKE '__/__/____')::INT), sum((period_start_raw LIKE '____-__-__')::INT) FROM t"
    ).fetchone()
    if n_dmy and n_iso:
        date_style = f"mixed ({n_dmy} DD/MM/YYYY, {n_iso} YYYY-MM-DD)"
    else:
        date_style = "DD/MM/YYYY" if n_dmy else "YYYY-MM-DD"
    windows = con.execute(
        """
        SELECT period_start, period_end, count(*) AS n_rows, count(DISTINCT measure_id) AS n_measures
        FROM t GROUP BY 1, 2 ORDER BY 1
        """
    ).df()
    windows["months"] = (
        (windows["period_end"].dt.year - windows["period_start"].dt.year) * 12
        + (windows["period_end"].dt.month - windows["period_start"].dt.month)
        + 1
    )
    headline = con.execute(
        """
        SELECT count(*) AS n_rows,
               count(DISTINCT measure_id) AS n_measures,
               count(DISTINCT breakdown) AS n_breakdowns,
               avg(is_suppressed::INT) AS share_suppressed,
               sum(CASE WHEN value_num IS NULL AND NOT is_suppressed THEN 1 ELSE 0 END)
                   AS n_other_non_numeric
        FROM t
        """
    ).df()

    release = headline.assign(
        release_month=release_month,
        source_file=csv_path.name,
        status_values=" | ".join(repr(s) for s in statuses),
        date_style=date_style,
        line_endings=line_endings,
        columns=" | ".join(original_columns),
        windows=" | ".join(
            f"{int(m)}m from {s:%Y-%m} ({n} measures)"
            for s, m, n in zip(windows["period_start"], windows["months"], windows["n_measures"], strict=True)
        ),
    )

    measures = con.execute(
        """
        SELECT measure_id, measure_name,
               count(*) AS n_rows,
               sum(is_suppressed::INT) AS n_suppressed,
               count(DISTINCT breakdown) AS n_breakdowns,
               string_agg(DISTINCT breakdown, ' | ' ORDER BY breakdown) AS breakdowns,
               string_agg(DISTINCT strftime(period_start, '%Y-%m'), ' | ') AS period_starts
        FROM t GROUP BY 1, 2 ORDER BY 1, 2
        """
    ).df()

    breakdowns = con.execute(
        """
        SELECT breakdown, geo_level,
               count(*) AS n_rows,
               count(DISTINCT measure_id) AS n_measures,
               count(DISTINCT primary_code) AS n_units,
               avg(is_suppressed::INT) AS share_suppressed
        FROM t GROUP BY 1, 2 ORDER BY 1
        """
    ).df()

    geography = con.execute(
        """
        SELECT geo_level, primary_code, primary_name, count(*) AS n_rows
        FROM t WHERE geo_level <> 'England'
        GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
        """
    ).df()

    england_values = con.execute(
        """
        SELECT period_start, period_end, measure_id, measure_name, measure_value, value_num
        FROM t WHERE breakdown = 'England'
        ORDER BY measure_id, period_start
        """
    ).df()

    for frame in (measures, breakdowns, geography, england_values):
        frame.insert(0, "release_month", release_month)

    return ReleaseProfile(release, measures, breakdowns, geography, england_values)


def profile_many(paths: Iterable[Path]) -> dict[str, pd.DataFrame]:
    """Profile several files and stack the results table by table."""
    tables: dict[str, list[pd.DataFrame]] = {
        "releases": [],
        "measures": [],
        "breakdowns": [],
        "geography": [],
        "england_values": [],
    }
    con = duckdb.connect()
    for path in paths:
        LOGGER.info("Profiling %s", path.name)
        profile = profile_file(path, con)
        tables["releases"].append(profile.release)
        tables["measures"].append(profile.measures)
        tables["breakdowns"].append(profile.breakdowns)
        tables["geography"].append(profile.geography)
        tables["england_values"].append(profile.england_values)
    stacked = {name: pd.concat(frames, ignore_index=True) for name, frames in tables.items() if frames}
    if "releases" in stacked:
        duplicated = stacked["releases"]["release_month"].duplicated(keep=False)
        if duplicated.any():
            months = sorted(stacked["releases"].loc[duplicated, "release_month"].unique())
            raise ValueError(f"More than one file was found for release months {months}")
    return stacked


def write_tables(tables: dict[str, pd.DataFrame], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.sort_values(list(frame.columns[:2])).to_csv(out_dir / f"{name}.csv", index=False)
        LOGGER.info("Wrote %s rows to %s", len(frame), out_dir / f"{name}.csv")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs", nargs="+", type=Path, help="CSV files, zip files or folders")
    parser.add_argument("--out", type=Path, default=Path("data/interim/profiles"))
    parser.add_argument("--extract-dir", type=Path, default=Path("data/interim/extracted"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    paths = list(find_input_files(args.inputs, args.extract_dir))
    write_tables(profile_many(paths), args.out)


if __name__ == "__main__":
    main()


def normalise_line_endings(csv_path: Path, work_dir: Path) -> tuple[Path, str]:
    """Return a path that reads cleanly, plus a description of the original line endings.

    Files with a single style of line ending are returned unchanged. Files that
    mix Windows and Unix endings, as several End of Year Final files do, are
    copied with every ending made Unix style.
    """
    crlf, total = count_line_endings(csv_path)
    if crlf == 0:
        return csv_path, "LF"
    if crlf == total:
        return csv_path, "CRLF"
    return _normalised_copy(csv_path, work_dir), f"mixed ({crlf} of {total} lines CRLF)"
