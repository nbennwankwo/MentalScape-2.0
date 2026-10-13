"""Build a month by month change log of the MHSDS Monthly Statistics.

This module reads the summary tables written by mhsds_release_profile and
compares every release with the one before it. It records

    measures that appear for the first time
    measures that disappear
    measures whose name changes while the ID stays the same
    likely replacements, where one ID disappears and a similar one appears
    breakdowns that are added or removed
    organisation and area codes that appear, disappear or are renamed
    changes to the file layout, status labels, date style and line endings
    large month on month jumps in England level values, which often mark a
    change of method rather than a real change in services

The outputs are tidy CSV files in data/reference and a generated Markdown
report. Every row can be traced back to the release that caused it.

Run it from the repository root, for example

    python -m mentalscape.profiling.mhsds_change_log --profiles data/interim/profiles
"""

from __future__ import annotations

import argparse
import logging
import re
from difflib import SequenceMatcher
from itertools import pairwise
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)

# A likely replacement needs names this similar (0 to 1 scale).
REPLACEMENT_SIMILARITY = 0.80
# England level jumps are only flagged for values at least this large.
STEP_MIN_VALUE = 500
# and only when the value moves by more than this factor in one month.
STEP_FACTOR = 1.5


def canonical_geo_level(label: str) -> str:
    """Map the many published geography labels onto five stable levels."""
    text = label.lower()
    if "sub icb" in text:
        return "Sub ICB"
    if "icb" in text:
        return "ICB"
    if "commissioning region" in text:
        return "Commissioning Region"
    if "local authority" in text:
        return "Local Authority"
    if "provider" in text:
        return "Provider"
    return label


def name_key(name: str) -> str:
    """Reduce a name to letters and digits so that cosmetic edits compare equal."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()


def measure_family(measure_id: str) -> str:
    match = re.match(r"[A-Za-z]+", str(measure_id))
    return match.group(0).upper() if match else str(measure_id)


def month_gap(previous: str, current: str) -> int:
    p, c = pd.Period(previous, "M"), pd.Period(current, "M")
    return (c - p).n - 1


def load_profiles(profile_dir: Path) -> dict[str, pd.DataFrame]:
    names = ("releases", "measures", "breakdowns", "geography", "england_values")
    tables = {n: pd.read_csv(profile_dir / f"{n}.csv", dtype=str, keep_default_na=False) for n in names}
    tables["releases"] = tables["releases"].sort_values("release_month").reset_index(drop=True)
    return tables


def measure_events(measures: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    """Compare the measure list of each release with the release before it."""
    names = (
        measures.groupby(["release_month", "measure_id"])["measure_name"]
        .agg(lambda s: " || ".join(sorted(set(s))))
        .reset_index()
    )
    by_month = {
        m: dict(zip(g["measure_id"], g["measure_name"], strict=True)) for m, g in names.groupby("release_month")
    }
    events: list[dict[str, object]] = []
    for previous, current in pairwise(months):
        before, after = by_month.get(previous, {}), by_month.get(current, {})
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        gap = month_gap(previous, current)
        for mid in sorted(set(after) & set(before)):
            if before[mid] != after[mid]:
                kind = "renamed (cosmetic)" if name_key(before[mid]) == name_key(after[mid]) else "renamed"
                events.append(
                    {
                        "release_month": current,
                        "compared_with": previous,
                        "months_missing_between": gap,
                        "event": kind,
                        "measure_id": mid,
                        "old_name": before[mid],
                        "new_name": after[mid],
                    }
                )
        replaced_by: dict[str, tuple[str, float]] = {}
        for old in removed:
            scored = [(new, similarity(before[old], after[new])) for new in added]
            if scored:
                best, score = max(scored, key=lambda pair: pair[1])
                if score >= REPLACEMENT_SIMILARITY:
                    replaced_by[old] = (best, score)
        for mid in added:
            events.append(
                {
                    "release_month": current,
                    "compared_with": previous,
                    "months_missing_between": gap,
                    "event": "added",
                    "measure_id": mid,
                    "old_name": "",
                    "new_name": after[mid],
                }
            )
        for mid in removed:
            row = {
                "release_month": current,
                "compared_with": previous,
                "months_missing_between": gap,
                "event": "removed",
                "measure_id": mid,
                "old_name": before[mid],
                "new_name": "",
            }
            if mid in replaced_by:
                new_id, score = replaced_by[mid]
                row["likely_replaced_by"] = new_id
                row["replacement_similarity"] = round(score, 2)
            events.append(row)
    columns = [
        "release_month",
        "compared_with",
        "months_missing_between",
        "event",
        "measure_id",
        "old_name",
        "new_name",
        "likely_replaced_by",
        "replacement_similarity",
    ]
    return pd.DataFrame(events).reindex(columns=columns)


def breakdown_events(breakdowns: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    sets = {m: set(g["breakdown"]) for m, g in breakdowns.groupby("release_month")}
    rows = []
    for previous, current in pairwise(months):
        for b in sorted(sets.get(current, set()) - sets.get(previous, set())):
            rows.append({"release_month": current, "compared_with": previous, "event": "added", "breakdown": b})
        for b in sorted(sets.get(previous, set()) - sets.get(current, set())):
            rows.append({"release_month": current, "compared_with": previous, "event": "removed", "breakdown": b})
    return pd.DataFrame(rows, columns=["release_month", "compared_with", "event", "breakdown"])


def geography_events(geography: pd.DataFrame, months: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Track codes and names at each canonical geography level.

    Returns the change events and a per release count of units per level.
    UNKNOWN and similar catch all codes are kept but marked.
    """
    geo = geography.assign(level=geography["geo_level"].map(canonical_geo_level))
    units = (
        geo.groupby(["release_month", "level", "primary_code"])["primary_name"]
        .agg(lambda s: " || ".join(sorted(set(s))))
        .reset_index()
    )
    counts = (
        units.assign(is_real=~units["primary_code"].str.upper().isin({"UNKNOWN", "INVALID", "MISSING", ""}))
        .groupby(["release_month", "level"])["is_real"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    lookup = {
        (m, lvl): dict(zip(g["primary_code"], g["primary_name"], strict=True))
        for (m, lvl), g in units.groupby(["release_month", "level"])
    }
    rows = []
    for level in ("Commissioning Region", "ICB", "Sub ICB", "Local Authority", "Provider"):
        for previous, current in pairwise(months):
            before, after = lookup.get((previous, level), {}), lookup.get((current, level), {})
            if not before or not after:
                continue
            for code in sorted(set(after) - set(before)):
                rows.append(
                    {
                        "release_month": current,
                        "compared_with": previous,
                        "level": level,
                        "event": "code added",
                        "code": code,
                        "old_name": "",
                        "new_name": after[code],
                    }
                )
            for code in sorted(set(before) - set(after)):
                rows.append(
                    {
                        "release_month": current,
                        "compared_with": previous,
                        "level": level,
                        "event": "code removed",
                        "code": code,
                        "old_name": before[code],
                        "new_name": "",
                    }
                )
            for code in sorted(set(before) & set(after)):
                if before[code] != after[code]:
                    kind = "renamed (cosmetic)" if name_key(before[code]) == name_key(after[code]) else "renamed"
                    rows.append(
                        {
                            "release_month": current,
                            "compared_with": previous,
                            "level": level,
                            "event": kind,
                            "code": code,
                            "old_name": before[code],
                            "new_name": after[code],
                        }
                    )
    columns = ["release_month", "compared_with", "level", "event", "code", "old_name", "new_name"]
    return pd.DataFrame(rows, columns=columns), counts


def england_step_changes(england: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    """Flag single month England values that jump sharply between consecutive releases."""
    frame = england.copy()
    frame["value"] = pd.to_numeric(frame["value_num"], errors="coerce")
    start = pd.to_datetime(frame["period_start"]).dt.to_period("M").astype(str)
    frame = frame[start == frame["release_month"]]  # single month window only
    frame = frame.groupby(["release_month", "measure_id"], as_index=False).agg(
        value=("value", "first"), measure_name=("measure_name", "first")
    )
    wide = frame.pivot(index="measure_id", columns="release_month", values="value")
    names = frame.drop_duplicates("measure_id", keep="last").set_index("measure_id")["measure_name"]
    rows = []
    for previous, current in pairwise(months):
        if previous not in wide or current not in wide or month_gap(previous, current) > 0:
            continue
        pair = wide[[previous, current]].dropna()
        pair = pair[(pair[previous] >= STEP_MIN_VALUE) | (pair[current] >= STEP_MIN_VALUE)]
        pair = pair[(pair[previous] > 0) & (pair[current] > 0)]
        ratio = pair[current] / pair[previous]
        flagged = pair[(ratio >= STEP_FACTOR) | (ratio <= 1 / STEP_FACTOR)]
        for mid, values in flagged.iterrows():
            rows.append(
                {
                    "release_month": current,
                    "measure_id": mid,
                    "measure_name": names.get(mid, ""),
                    "previous_value": values[previous],
                    "value": values[current],
                    "ratio": round(values[current] / values[previous], 2),
                }
            )
    columns = ["release_month", "measure_id", "measure_name", "previous_value", "value", "ratio"]
    steps = pd.DataFrame(rows, columns=columns)
    if steps.empty:
        return steps.assign(pattern=pd.Series(dtype=str))
    # A jump that happens in the same calendar month, in the same direction, in
    # more than one year is a seasonal or financial year pattern, not a break.
    steps["calendar_month"] = steps["release_month"].str[5:]
    steps["direction"] = (steps["ratio"] > 1).map({True: "up", False: "down"})
    repeats = steps.groupby(["measure_id", "calendar_month", "direction"])["release_month"].transform("nunique")
    steps["pattern"] = repeats.gt(1).map({True: "recurring in this calendar month", False: "one off"})
    return steps.drop(columns=["calendar_month", "direction"])


def measure_catalogue(measures: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    """One row per measure ID with its lifetime across the releases profiled."""
    position = {m: i for i, m in enumerate(months)}
    latest = months[-1]
    rows = []
    for mid, group in measures.groupby("measure_id"):
        seen = sorted(set(group["release_month"]), key=position.get)
        ordered = group.sort_values("release_month")
        name_history = list(dict.fromkeys(ordered["measure_name"]))
        absent_inside = [m for m in months[position[seen[0]] : position[seen[-1]] + 1] if m not in seen]
        last_row = ordered[ordered["release_month"] == seen[-1]]
        rows.append(
            {
                "measure_id": mid,
                "family": measure_family(mid),
                "latest_name": last_row["measure_name"].iloc[-1],
                "first_seen": seen[0],
                "last_seen": seen[-1],
                "in_latest_release": seen[-1] == latest,
                "releases_present": len(seen),
                "releases_absent_between": len(absent_inside),
                "name_versions": len(name_history),
                "name_history": " >> ".join(name_history),
                "latest_breakdowns": int(last_row["n_breakdowns"].astype(int).max()),
            }
        )
    return pd.DataFrame(rows).sort_values(["family", "measure_id"]).reset_index(drop=True)


def release_summary(tables: dict[str, pd.DataFrame], events: pd.DataFrame, geo_counts: pd.DataFrame) -> pd.DataFrame:
    rel = tables["releases"].copy()
    months = list(rel["release_month"])
    counts = events.pivot_table(
        index="release_month", columns="event", values="measure_id", aggfunc="count", fill_value=0
    )
    summary = rel[
        [
            "release_month",
            "source_file",
            "n_rows",
            "n_measures",
            "n_breakdowns",
            "share_suppressed",
            "status_values",
            "date_style",
            "line_endings",
            "windows",
        ]
    ].copy()
    summary["months_missing_before"] = [0] + [month_gap(a, b) for a, b in pairwise(months)]
    summary = summary.merge(counts.reset_index(), on="release_month", how="left")
    summary = summary.merge(geo_counts, on="release_month", how="left")
    for col in ("added", "removed", "renamed", "renamed (cosmetic)"):
        if col not in summary:
            summary[col] = 0
        summary[col] = summary[col].fillna(0).astype(int)

    # Inside one file, a code or measure ID should carry exactly one name.
    geo = tables["geography"].assign(level=tables["geography"]["geo_level"].map(canonical_geo_level))
    geo_conflicts = (
        geo.groupby(["release_month", "level", "primary_code"])["primary_name"]
        .nunique()
        .gt(1)
        .groupby("release_month")
        .sum()
        .rename("codes_with_conflicting_names")
    )
    measure_conflicts = (
        tables["measures"]
        .groupby(["release_month", "measure_id"])["measure_name"]
        .nunique()
        .gt(1)
        .groupby("release_month")
        .sum()
        .rename("measure_ids_with_conflicting_names")
    )
    summary = summary.merge(geo_conflicts.reset_index(), on="release_month", how="left")
    summary = summary.merge(measure_conflicts.reset_index(), on="release_month", how="left")
    for col in ("codes_with_conflicting_names", "measure_ids_with_conflicting_names"):
        summary[col] = summary[col].fillna(0).astype(int)
    return summary


def _md_escape(text: object) -> str:
    return str(text).replace("|", "/").replace("\n", " ").strip()


def render_markdown(outputs: dict[str, pd.DataFrame]) -> str:
    """Write the full month by month detail as Markdown.

    The text avoids colons and semicolons in prose to follow the house style.
    """
    summary = outputs["mhsds_release_summary"]
    m_events = outputs["mhsds_measure_events"].fillna("")
    b_events = outputs["mhsds_breakdown_events"]
    g_events = outputs["mhsds_geography_events"]
    steps = outputs["mhsds_england_step_changes"]
    months = list(summary["release_month"])

    lines = [
        "# MHSDS Monthly Statistics release by release detail",
        "",
        "This file is generated by `python -m mentalscape.profiling.mhsds_change_log`. "
        "Do not edit it by hand. The written explanation of what these changes mean is in "
        "[mhsds_change_log.md](mhsds_change_log.md).",
        "",
        f"It covers {len(months)} releases from {months[0]} to {months[-1]}.",
        "",
        "## Every release at a glance",
        "",
        "| Release | Status in file | Rows | Measures | Breakdowns | Suppressed | Added | Removed | Renamed "
        "| ICBs | Sub ICBs | Format notes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, r in summary.iterrows():
        notes = []
        if int(r["months_missing_before"]) > 0:
            notes.append(f"{int(r['months_missing_before'])} months not profiled before this")
        if str(r["date_style"]).startswith("mixed"):
            notes.append("mixed date styles")
        if str(r["line_endings"]).startswith("mixed"):
            notes.append("mixed line endings")
        if int(r.get("codes_with_conflicting_names", 0)):
            notes.append(f"{int(r['codes_with_conflicting_names'])} codes with two names")
        if int(r.get("measure_ids_with_conflicting_names", 0)):
            notes.append(f"{int(r['measure_ids_with_conflicting_names'])} measure IDs with two names")
        renamed = int(r["renamed"]) + int(r["renamed (cosmetic)"])
        cells = [
            r["release_month"],
            _md_escape(r["status_values"]),
            f"{int(r['n_rows']):,}",
            int(r["n_measures"]),
            int(r["n_breakdowns"]),
            f"{float(r['share_suppressed']):.1%}",
            int(r["added"]),
            int(r["removed"]),
            renamed,
            int(r.get("ICB", 0)),
            int(r.get("Sub ICB", 0)),
            ", ".join(notes),
        ]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")

    lines += ["", "## Changes release by release", ""]
    for month in months[1:]:
        me = m_events[m_events["release_month"] == month]
        be = b_events[b_events["release_month"] == month]
        ge = g_events[(g_events["release_month"] == month) & (g_events["level"] != "Provider")]
        pe = g_events[(g_events["release_month"] == month) & (g_events["level"] == "Provider")]
        se = steps[(steps["release_month"] == month) & (steps["pattern"] == "one off")]
        if me.empty and be.empty and ge.empty and se.empty:
            continue
        compared = me["compared_with"].iloc[0] if not me.empty else months[months.index(month) - 1]
        lines += [f"### {month}", "", f"Compared with {compared}.", ""]
        added = me[me["event"] == "added"]
        if not added.empty:
            lines += [f"**Measures added ({len(added)})**", ""]
            lines += [f"- `{r.measure_id}` {_md_escape(r.new_name)}" for r in added.itertuples()]
            lines.append("")
        removed = me[me["event"] == "removed"]
        if not removed.empty:
            lines += [f"**Measures removed ({len(removed)})**", ""]
            for r in removed.itertuples():
                hint = f" (likely replaced by `{r.likely_replaced_by}`)" if r.likely_replaced_by else ""
                lines.append(f"- `{r.measure_id}` {_md_escape(r.old_name)}{hint}")
            lines.append("")
        renamed = me[me["event"].str.startswith("renamed")]
        if not renamed.empty:
            lines += [f"**Measures renamed with the same ID ({len(renamed)})**", ""]
            for r in renamed.itertuples():
                tag = " (wording only)" if "cosmetic" in r.event else ""
                lines.append(
                    f'- `{r.measure_id}`{tag} was "{_md_escape(r.old_name)}" and is now "{_md_escape(r.new_name)}"'
                )
            lines.append("")
        if not be.empty:
            lines += [f"**Breakdowns added or removed ({len(be)})**", ""]
            lines += [f"- {r.event} {_md_escape(r.breakdown)}" for r in be.itertuples()]
            lines.append("")
        if not ge.empty:
            lines += [f"**Geography changes ({len(ge)})**", ""]
            for r in ge.itertuples():
                if r.event == "code added":
                    lines.append(f"- {r.level} code `{r.code}` added, {_md_escape(r.new_name)}")
                elif r.event == "code removed":
                    lines.append(f"- {r.level} code `{r.code}` removed, was {_md_escape(r.old_name)}")
                else:
                    lines.append(
                        f"- {r.level} code `{r.code}` renamed from {_md_escape(r.old_name)} to {_md_escape(r.new_name)}"
                    )
            lines.append("")
        if not pe.empty:
            counts = pe["event"].value_counts().to_dict()
            n_renamed = counts.get("renamed", 0) + counts.get("renamed (cosmetic)", 0)
            lines += [
                f"Provider list churn this release {counts.get('code added', 0)} added, "
                f"{counts.get('code removed', 0)} removed, {n_renamed} renamed.",
                "",
            ]
        if not se.empty:
            lines += [f"**One off jumps in England values ({len(se)})**", ""]
            for r in se.itertuples():
                lines.append(
                    f"- `{r.measure_id}` moved from {r.previous_value:,.0f} to {r.value:,.0f} "
                    f"(x{r.ratio}) {_md_escape(r.measure_name)}"
                )
            lines.append("")

    recurring = steps[steps["pattern"] != "one off"]
    if not recurring.empty:
        lines += [
            "## Recurring seasonal or financial year jumps",
            "",
            "These measures jump in the same calendar month in more than one year, so the jump is a "
            "pattern to model rather than a break to correct.",
            "",
            "| Measure | Months flagged | Typical factor | Name |",
            "|---|---|---:|---|",
        ]
        for mid, g in recurring.groupby("measure_id"):
            lines.append(
                f"| `{mid}` | {', '.join(sorted(g['release_month']))} | {g['ratio'].median():.2f} "
                f"| {_md_escape(g['measure_name'].iloc[0])} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def build(profile_dir: Path, reference_dir: Path, report_path: Path | None = None) -> dict[str, pd.DataFrame]:
    tables = load_profiles(profile_dir)
    months = list(tables["releases"]["release_month"])
    m_events = measure_events(tables["measures"], months)
    b_events = breakdown_events(tables["breakdowns"], months)
    g_events, g_counts = geography_events(tables["geography"], months)
    steps = england_step_changes(tables["england_values"], months)
    catalogue = measure_catalogue(tables["measures"], months)
    summary = release_summary(tables, m_events, g_counts)
    outputs = {
        "mhsds_release_summary": summary,
        "mhsds_measure_events": m_events,
        "mhsds_breakdown_events": b_events,
        "mhsds_geography_events": g_events,
        "mhsds_england_step_changes": steps,
        "mhsds_measure_catalogue": catalogue,
    }
    reference_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in outputs.items():
        frame.to_csv(reference_dir / f"{name}.csv", index=False)
        LOGGER.info("Wrote %s rows to %s", len(frame), reference_dir / f"{name}.csv")
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_markdown(outputs), encoding="utf-8")
        LOGGER.info("Wrote report to %s", report_path)
    return outputs


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profiles", type=Path, default=Path("data/interim/profiles"))
    parser.add_argument("--reference", type=Path, default=Path("data/reference"))
    parser.add_argument("--report", type=Path, default=Path("docs/data/mhsds_change_log_detail.md"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build(args.profiles, args.reference, args.report)


if __name__ == "__main__":
    main()
