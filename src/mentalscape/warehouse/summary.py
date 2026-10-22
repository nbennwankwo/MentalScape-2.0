"""Write a short Markdown summary of a warehouse build.

The scheduled build (docs/adr/0013) adds this summary to the job page and
publishes it with the warehouse, so anyone can see what was built, what each
source covers and which warnings need a person to look at them.

    python -m mentalscape.warehouse.summary --duckdb-path data/warehouse/mentalscape.duckdb \\
        --run-results warehouse/target/run_results.json --out build_summary.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

# (label, table, month column) for the monthly sources.
MONTHLY_SOURCES = (
    ("MHSDS Monthly Statistics", "marts.dim_mhsds_release", "release_month"),
    ("NHS Talking Therapies", "marts.dim_talking_therapies_release", "release_month"),
)


def read_run_results(path: Path) -> list[dict]:
    """Return one dict per dbt node with its name, kind, status, failures and message."""
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = []
    for result in data.get("results", []):
        unique_id = result.get("unique_id", "")
        nodes.append(
            {
                "name": unique_id.split(".")[-1] if unique_id.startswith("model.") else unique_id.split(".")[2],
                "kind": unique_id.split(".")[0],
                "status": result.get("status", ""),
                "failures": result.get("failures"),
                "message": (result.get("message") or "").strip(),
            }
        )
    return nodes


def results_section(nodes: list[dict]) -> list[str]:
    counts = Counter(node["status"] for node in nodes)
    lines = ["## Results", "", "| Status | Nodes |", "|---|---|"]
    lines += [f"| {status} | {count} |" for status, count in sorted(counts.items())]
    for status, title in (("error", "Errors"), ("fail", "Failed tests"), ("warn", "Warnings to review")):
        flagged = [n for n in nodes if n["status"] == status]
        if flagged:
            lines += ["", f"## {title}", "", "| Node | Rows found | Message |", "|---|---|---|"]
            lines += [
                f"| {n['name']} | {n['failures'] if n['failures'] is not None else ''} | {n['message'][:200]} |"
                for n in flagged
            ]
    return lines


def coverage_section(duckdb_path: Path) -> list[str]:
    import duckdb

    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        lines = ["## Coverage", "", "| Source | First month | Last month | Months | Values |", "|---|---|---|---|---|"]
        for label, table, column in MONTHLY_SOURCES:
            try:
                first, last, months, values = con.execute(
                    f"select min({column}), max({column}), count(*), sum(values_loaded) from {table}"
                ).fetchone()
                lines.append(f"| {label} | {first} | {last} | {months} | {values:,} |")
            except duckdb.Error:
                lines.append(f"| {label} | not built | | | |")
        try:
            editions, years = con.execute(
                "select string_agg(distinct boundary_edition, ', ' order by boundary_edition), "
                "string_agg(distinct cast(population_year as varchar), ', ' order by cast(population_year as varchar)) "
                "from marts.fct_population"
            ).fetchone()
            lines += ["", f"ONS boundary editions {editions}. Population estimates for mid-year {years}."]
        except duckdb.Error:
            lines += ["", "Population tables were not built."]
        tables = con.execute(
            "select table_name, estimated_size from duckdb_tables() where schema_name = 'marts' order by table_name"
        ).fetchall()
        lines += ["", "## Mart tables", "", "| Table | Rows |", "|---|---|"]
        lines += [f"| {name} | {rows:,} |" for name, rows in tables]
        return lines
    finally:
        con.close()


def build_summary(duckdb_path: Path | None, run_results: Path | None, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["# Warehouse build", "", f"Built {stamp}.", ""]
    if run_results is not None and run_results.exists():
        lines += [*results_section(read_run_results(run_results)), ""]
    else:
        lines += ["No dbt results were found, so the build stopped before dbt ran.", ""]
    if duckdb_path is not None and duckdb_path.exists():
        lines += coverage_section(duckdb_path)
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Summarise a warehouse build as Markdown.")
    parser.add_argument("--duckdb-path", type=Path, default=Path("data/warehouse/mentalscape.duckdb"))
    parser.add_argument("--run-results", type=Path, default=Path("warehouse/target/run_results.json"))
    parser.add_argument("--out", type=Path, default=Path("build_summary.md"))
    args = parser.parse_args(argv)
    args.out.write_text(build_summary(args.duckdb_path, args.run_results), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
