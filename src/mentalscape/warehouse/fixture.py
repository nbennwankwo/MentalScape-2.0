"""A small synthetic dataset that reproduces the real traps in every source.

The fixture is laid out exactly like the data releases, one folder per
release with a manifest and its assets, so the loader reads it the same way.

    data-mhsds-monthly/              MHSDS main data files, February to April 2026
    data-talking-therapies-monthly/  NHS Talking Therapies activity files, same months
    data-reference/                  IoD 2025, ONS population and ONS lookups

The MHSDS and Talking Therapies files reproduce

    the April 2026 ICB mergers, with Sub ICB 06Q moving from Mid and South
    Essex ICB to Essex ICB
    Frimley's Sub ICB D4U1Y disappearing and Thames Valley's U2G6B appearing
    one Sub ICB code carrying two names in the same file
    a month where a Sub ICB carries only its post merger name
    all five date styles and mixed line endings
    MHS32 published for a one month and a three month window
    a status label with a trailing space
    two versions of March 2026, where the final one must win
    local authority codes that end when Cumbria is reorganised
    Talking Therapies placeholders such as "all" and "InvalidRegionCode"

The reference files reproduce

    an IoD header cut off in the middle of a word, as in the real file
    a population workbook with title rows, a cover sheet, one sheet per year
    and a Welsh LSOA that must be dropped
    a July 2022 lookup on 2011 LSOAs and later ones on 2021 LSOAs
    Cumbria's districts merging into two unitary authorities, so the county
    is split

All values are invented. It is used by the tests and by the PostgreSQL CI job.

    python -m mentalscape.warehouse.fixture --out data/interim/fixture
    python -m mentalscape.warehouse.load --source all --raw-dir data/interim/fixture
"""

from __future__ import annotations

import argparse
import csv
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from mentalscape.ingest.manifest import CatalogueEntry, ManifestEntry, store_file, write_manifest

STAMP = "2026-10-22T00:00:00Z"

# MHSDS ----------------------------------------------------------------------

HEADER = (
    "REPORTING_PERIOD_START,REPORTING_PERIOD_END,STATUS,BREAKDOWN,PRIMARY_LEVEL,PRIMARY_LEVEL_DESCRIPTION,"
    "SECONDARY_LEVEL,SECONDARY_LEVEL_DESCRIPTION,MEASURE_ID,MEASURE_NAME,MEASURE_VALUE"
)

LA_BREAKDOWN = "Local Authority of Responsibility or Residence"

BEFORE_MERGER = {
    "sub_icbs": [
        ("Sub ICB of GP Practice or Residence", "06Q", "NHS MID AND SOUTH ESSEX ICB - 06Q"),
        ("Sub ICB - GP Practice or Residence", "06Q", "NHS ESSEX ICB - 06Q"),
        ("Sub ICB of GP Practice or Residence", "D4U1Y", "NHS FRIMLEY ICB - D4U1Y"),
        ("Sub ICB of GP Practice or Residence", "00L", "NHS NORTH EAST AND NORTH CUMBRIA ICB - 00L"),
        ("Sub ICB of GP Practice or Residence", "UNKNOWN", "UNKNOWN"),
    ],
    "icbs": [
        ("QH8", "NHS MID AND SOUTH ESSEX INTEGRATED CARE BOARD"),
        ("QNQ", "NHS FRIMLEY INTEGRATED CARE BOARD"),
        ("QHM", "NHS NORTH EAST AND NORTH CUMBRIA INTEGRATED CARE BOARD"),
    ],
    "local_authorities": [("E07000028", "Carlisle"), ("E10000006", "Cumbria")],
}
# Like the real March 2026 final file, produced after the mergers, so 06Q only
# carries its new name while the ICB rows are still the old ICBs.
MARCH_FINAL = {
    "sub_icbs": [
        ("Sub ICB of GP Practice or Residence", "06Q", "NHS ESSEX ICB - 06Q"),
        ("Sub ICB of GP Practice or Residence", "D4U1Y", "NHS FRIMLEY ICB - D4U1Y"),
        ("Sub ICB of GP Practice or Residence", "00L", "NHS NORTH EAST AND NORTH CUMBRIA ICB - 00L"),
    ],
    "icbs": BEFORE_MERGER["icbs"],
    "local_authorities": BEFORE_MERGER["local_authorities"],
}
AFTER_MERGER = {
    "sub_icbs": [
        ("Sub ICB of GP Practice or Residence", "06Q", "NHS ESSEX ICB - 06Q"),
        ("Sub ICB of GP Practice or Residence", "U2G6B", "NHS THAMES VALLEY ICB - U2G6B"),
        ("Sub ICB of GP Practice or Residence", "00L", "NHS NORTH EAST AND NORTH CUMBRIA ICB - 00L"),
    ],
    "icbs": [
        ("D7T5G", "NHS ESSEX INTEGRATED CARE BOARD"),
        ("S0E4D", "NHS THAMES VALLEY INTEGRATED CARE BOARD"),
        ("QHM", "NHS NORTH EAST AND NORTH CUMBRIA INTEGRATED CARE BOARD"),
    ],
    "local_authorities": [("E06000063", "Cumberland")],
}

MONTHS = {
    # month: (geography, date style, status, first day, last day, previous quarter start)
    "2026-02": (BEFORE_MERGER, "iso", "Final", "2026-02-01", "2026-02-28", "2025-12-01"),
    "2026-03": (MARCH_FINAL, "dmy", "Final", "2026-03-01", "2026-03-31", "2026-01-01"),
    "2026-04": (AFTER_MERGER, "dmy", "Performance ", "2026-04-01", "2026-04-30", "2026-02-01"),
}


def _fmt(iso: str, style: str) -> str:
    """Write a date in one of the five styles NHS England has used."""
    year, month, day = iso.split("-")
    return {
        "iso": iso,
        "dmy": f"{day}/{month}/{year}",
        "dmy_unpadded": f"{int(day)}/{int(month)}/{year}",
        "dmy_two_digit_year": f"{day}/{month}/{year[2:]}",
        "dmy_hyphen": f"{day}-{month}-{year}",
    }[style]


# The rolling three month row of each month uses one of the rarer date styles.
QUARTER_STYLE = {"2026-02": "dmy_unpadded", "2026-03": "dmy_two_digit_year", "2026-04": "dmy_hyphen"}


def month_rows(month: str, scale: int = 1) -> list[str]:
    geo, style, status, first, last, quarter = MONTHS[month]
    start, end, q_start = _fmt(first, style), _fmt(last, style), _fmt(quarter, QUARTER_STYLE[month])
    rows = []

    def add(s: str, breakdown: str, code: str, name: str, mid: str, mname: str, value: str) -> None:
        rows.append(f'{s},{end},{status},{breakdown},{code},"{name}",NONE,NONE,{mid},"{mname}",{value}')

    for measure, name, base in (
        ("MHS01", "People with an open referral", 400000),
        ("MHS32", "Referrals starting in RP", 90000),
    ):
        add(start, "England", "England", "England", measure, name, str(base * scale))
        for code, icb_name in geo["icbs"]:
            add(start, "ICB of GP Practice or Residence", code, icb_name, measure, name, str(base * scale // 40))
        for breakdown, code, sub_name in geo["sub_icbs"]:
            add(start, breakdown, code, sub_name, measure, name, "*" if code == "UNKNOWN" else str(base * scale // 120))
    for code, la_name in geo["local_authorities"]:
        add(start, LA_BREAKDOWN, code, la_name, "MHS01", "People with an open referral", str(1000 * scale))
    add(q_start, "England", "England", "England", "MHS32", "New referrals", str(270000 * scale))
    return rows


def _entry(kind: str, month: str, version: str, filename: str, title: str = "") -> CatalogueEntry:
    return CatalogueEntry(
        page_url="https://example.test/fixture",
        page_title=f"Fixture {month}",
        card_title=title or f"Fixture {kind} {version} {month}",
        source_url=f"https://files.example.test/{version}/{filename}",
        original_filename=filename,
        file_type=filename.rsplit(".", 1)[-1],
        size_text="1 KB",
        kind=kind,
        version=version,
        reporting_month=month,
        revision=1,
        wanted=True,
        reason="",
    )


def build_mhsds(staging: Path, release: Path) -> list[ManifestEntry]:
    rows: list[ManifestEntry] = []

    # February 2026, final, zipped, with mixed line endings as in real final files.
    feb = month_rows("2026-02")
    csv_path = staging / "MHSDS Data_FebFinal__2026.csv"
    half = len(feb) // 2
    csv_path.write_bytes(("\n".join([HEADER, *feb[:half]]) + "\n" + "\r\n".join(feb[half:]) + "\r\n").encode())
    zip_path = staging / "MHSDS Data_FebFinal__2026.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(csv_path, "MHSDS Data_FebFinal__2026/MHSDS Data_FebFinal__2026.csv")
    rows.append(store_file(zip_path, _entry("main", "2026-02", "final", zip_path.name), release, STAMP))

    # March 2026, performance then final. The final one must win.
    for version, scale in (("performance", 1), ("final", 2)):
        path = staging / f"MHSDS Data_Mar{version.title()}_2026.csv"
        path.write_bytes(("\r\n".join([HEADER, *month_rows("2026-03", scale)]) + "\r\n").encode())
        rows.append(store_file(path, _entry("main", "2026-03", version, path.name), release, STAMP))

    # April 2026, performance only, after the ICB mergers.
    apr = staging / "MHSDS Data_AprPerf_2026.csv"
    apr.write_bytes(("\r\n".join([HEADER, *month_rows("2026-04")]) + "\r\n").encode())
    rows.append(store_file(apr, _entry("main", "2026-04", "performance", apr.name), release, STAMP))
    return rows


# NHS Talking Therapies ------------------------------------------------------

TT_HEADER = [
    "REPORTING_PERIOD_START",
    "REPORTING_PERIOD_END",
    "GROUP_TYPE",
    "ORG_CODE1",
    "ORG_NAME1",
    "ORG_CODE2",
    "ORG_NAME2",
    "MEASURE_ID",
    "MEASURE_NAME",
    "MEASURE_VALUE_SUPPRESSED",
]
TT_MEASURES = (
    ("M001", "Count_ReferralsReceived", 1200),
    ("M053", "Percentage_AccessingServices6WeeksFinishedCourseTreatment", 87),
)
TT_PROVIDER = ("RWN", "ESSEX PARTNERSHIP UNIVERSITY NHS FOUNDATION TRUST")


def tt_rows(month: str, scale: int = 1) -> list[list[str]]:
    geo, _, _, first, last, _ = MONTHS[month]
    # IAPT era files used day first dates, recent files use ISO dates.
    tt_style = "iso" if month == "2026-04" else "dmy"
    start, end = _fmt(first, tt_style), _fmt(last, tt_style)
    sub_icbs = {}
    for _, code, name in geo["sub_icbs"]:
        if code != "UNKNOWN":
            sub_icbs.setdefault(code, name)
    rows = []
    for measure_id, name, base in TT_MEASURES:
        value = base * scale if name.startswith("Count") else base

        def add(group: str, c1: str, n1: str, c2: str, n2: str, v: object, mid: str = measure_id, mn: str = name):
            rows.append([start, end, group, c1, n1, c2, n2, mid, mn, str(v)])

        add("England", "all", "all SubICBs", "all", "all Providers", value * 20)
        add("CommissioningRegion", "Y61", "EAST OF ENGLAND COMMISSIONING REGION", "all", "all Providers", value * 5)
        add("CommissioningRegion", "InvalidRegionCode", "Unknown", "all", "all Providers", "*")
        for code, sub_name in sub_icbs.items():
            add("SubICB", code, sub_name, "all", "all Providers", value)
        add("Provider", "all", "all SubICBs", *TT_PROVIDER, value * 2)
        add("SubICB/Provider", "06Q", sub_icbs["06Q"], *TT_PROVIDER, "*")
    return rows


def _write_csv(path: Path, header: list[str], rows: list[list[str]], line_end: str = "\n") -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator=line_end)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def build_talking_therapies(staging: Path, release: Path) -> list[ManifestEntry]:
    rows: list[ManifestEntry] = []

    def store(month: str, version: str, filename: str, scale: int = 1, line_end: str = "\n") -> None:
        path = _write_csv(staging / filename, TT_HEADER, tt_rows(month, scale), line_end)
        rows.append(store_file(path, _entry("activity", month, version, filename), release, STAMP, "talking_therapies"))

    store("2026-02", "final", "iapt_month_feb_26_activity.csv", line_end="\r\n")
    store("2026-03", "performance", "nhstalkingtherapies_month_mar_2026_activity_performance.csv")
    store("2026-03", "final", "nhstalkingtherapies_month_mar_2026_activity_final.csv", scale=2)
    store("2026-04", "performance", "nhstalkingtherapies_month_apr_2026_activity_performance.csv")
    return rows


# Reference files ------------------------------------------------------------

# (code, name, Sub ICB, ICB, local authority) for each LSOA. 2021 LSOAs are
# used from April 2023, 2011 LSOAs before.
SUB_ICB = {
    "06Q_old": ("E38000217", "06Q", "NHS Mid and South Essex ICB - 06Q"),
    "06Q_new": ("E38000217", "06Q", "NHS Essex ICB - 06Q"),
    "D4U1Y": ("E38000248", "D4U1Y", "NHS Frimley ICB - D4U1Y"),
    "U2G6B": ("E38000270", "U2G6B", "NHS Thames Valley ICB - U2G6B"),
    "00L": ("E38000130", "00L", "NHS North East and North Cumbria ICB - 00L"),
}
ICB = {
    "QH8": ("E54000026", "QH8", "NHS Mid and South Essex Integrated Care Board"),
    "D7T5G": ("E54000070", "D7T5G", "NHS Essex Integrated Care Board"),
    "QNQ": ("E54000034", "QNQ", "NHS Frimley Integrated Care Board"),
    "S0E4D": ("E54000071", "S0E4D", "NHS Thames Valley Integrated Care Board"),
    "QHM": ("E54000050", "QHM", "NHS North East and North Cumbria Integrated Care Board"),
}
LAD22 = {
    "basildon": ("E07000066", "Basildon"),
    "bracknell": ("E06000036", "Bracknell Forest"),
    "carlisle": ("E07000028", "Carlisle"),
    "allerdale": ("E07000026", "Allerdale"),
    "eden": ("E07000030", "Eden"),
}
LAD23 = {
    "basildon": ("E07000066", "Basildon"),
    "bracknell": ("E06000036", "Bracknell Forest"),
    "carlisle": ("E06000063", "Cumberland"),
    "allerdale": ("E06000063", "Cumberland"),
    "eden": ("E06000064", "Westmorland and Furness"),
}
# One row per LSOA, (index, place, Sub ICB before and after April 2026, ICB before and after)
LSOAS = [
    (1, "basildon", "06Q_old", "06Q_new", "QH8", "D7T5G"),
    (2, "basildon", "06Q_old", "06Q_new", "QH8", "D7T5G"),
    (3, "bracknell", "D4U1Y", "U2G6B", "QNQ", "S0E4D"),
    (4, "carlisle", "00L", "00L", "QHM", "QHM"),
    (5, "allerdale", "00L", "00L", "QHM", "QHM"),
    (6, "eden", "00L", "00L", "QHM", "QHM"),
]


def lsoa21(index: int) -> tuple[str, str]:
    place = LAD23[LSOAS[index - 1][1]][1]
    return f"E0100000{index}", f"{place} 00{index}A"


def health_lookup_rows(edition_year: int) -> tuple[list[str], list[list[str]]]:
    yy = f"{edition_year % 100:02d}"
    after_merger = edition_year >= 2026
    lsoa = "11" if edition_year == 2022 else "21"
    header = [
        f"LSOA{lsoa}CD",
        f"LSOA{lsoa}NM",
        f"SICBL{yy}CD",
        f"SICBL{yy}CDH",
        f"SICBL{yy}NM",
        f"ICB{yy}CD",
        f"ICB{yy}CDH",
        f"ICB{yy}NM",
        f"LAD{yy}CD",
        f"LAD{yy}NM",
        "ObjectId",
    ]
    rows = []
    for index, place, sub_before, sub_after, icb_before, icb_after in LSOAS:
        sub = SUB_ICB[sub_after if after_merger else sub_before]
        icb = ICB[icb_after if after_merger else icb_before]
        lad = (LAD22 if edition_year == 2022 else LAD23)[place]
        if edition_year == 2022:
            code, name = f"E0190000{index}", f"{lad[1]} 0{index}1B"
        else:
            code, name = lsoa21(index)
        rows.append([code, name, *sub, *icb, *lad, str(index)])
    return header, rows


IOD_DOMAINS = [
    ("Index of Multiple Deprivation (IMD)", False),
    ("Income", True),
    ("Employment", True),
    ("Education, Skills and Training", False),
    ("Health Deprivation and Disability", False),
    ("Crime", False),
    ("Barriers to Housing and Services", False),
    ("Living Environment", False),
    ("Income Deprivation Affecting Children Index (IDACI)", True),
    ("Income Deprivation Affecting Older People (IDAOPI)", True),
    ("Children and Young People Sub-domain", False),
    ("Adult Skills Sub-domain", False),
    ("Geographical Barriers Sub-domain", False),
    ("Wider Barriers Sub-domain", False),
    ("Indoors Sub-domain", False),
    ("Outdoors Sub-domain", False),
]
IOD_POPULATION = [
    "Total population: mid 2022",
    "Dependent Children aged 0-15: mid 2022",
    "Older population aged 60 and over: mid 2022",
    "Working age population 18-66 (for use with Employment Deprivation Domain): mid 2022",
]


def iod_header() -> list[str]:
    header = [
        "LSOA code (2021)",
        "LSOA name (2021)",
        "Local Authority District code (2024)",
        "Local Authority District name (2024)",
    ]
    for domain, is_rate in IOD_DOMAINS:
        header += [
            f"{domain} Score{' (rate)' if is_rate else ''}",
            f"{domain} Rank (where 1 is most deprived)",
            f"{domain} Decile (where 1 is most deprived 10% of LSOAs)",
        ]
    # The real file cuts this one header off mid word.
    cut = header.index("Children and Young People Sub-domain Decile (where 1 is most deprived 10% of LSOAs)")
    header[cut] = header[cut][:-3]
    return header + IOD_POPULATION


def iod_rows() -> list[list[str]]:
    deciles = [1, 2, 4, 6, 8, 10]
    rows = []
    for rank, (index, place, *_) in enumerate(LSOAS, start=1):
        code, name = lsoa21(index)
        lad = LAD23[place]
        row = [code, name, *lad]
        score = round(60 - rank * 8.5, 3)
        for _, is_rate in IOD_DOMAINS:
            value = round(0.4 - rank * 0.05, 3) if is_rate else score
            row += [str(value), str(rank), str(deciles[rank - 1])]
        row += [str(1500 + index * 10), "300", "350", "900"]
        rows.append(row)
    return rows


def population_sheet(year: int) -> list[list[object]]:
    """One worksheet as ONS lays it out, with three title rows above the table."""
    ages = [f"{sex}{age}" for sex in "FM" for age in range(91)]
    rows: list[list[object]] = [
        [f"Estimates by single year of age and sex for LSOAs, mid-{year}"],
        ["This worksheet contains one table."],
        ["To turn off freeze panes, select the View ribbon."],
        ["LAD 2023 Code", "LAD 2023 Name", "LSOA 2021 Code", "LSOA 2021 Name", "Total", *ages],
    ]
    places = [(index, LAD23[place]) for index, place, *_ in LSOAS] + [(9, ("W06000001", "Isle of Anglesey"))]
    for index, lad in places:
        code, name = lsoa21(index) if lad[0].startswith("E") else ("W01000001", "Isle of Anglesey 001A")
        counts = [(index * 7 + age * 3 + (5 if sex == "M" else 0) + year) % 13 + 1 for sex in "FM" for age in range(91)]
        rows.append([lad[0], lad[1], code, name, float(sum(counts)), *[float(c) for c in counts]])
    return rows


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def write_xlsx(path: Path, sheets: dict[str, list[list[object]]]) -> Path:
    """Write a minimal workbook with the standard library, text as inline strings."""
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package = "http://schemas.openxmlformats.org/package/2006/relationships"
    names = list(sheets)
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(names) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{overrides}</Types>"
    )
    root_rels = (
        f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{package}">'
        f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    )
    workbook = (
        f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{main}" xmlns:r="{rel}"><sheets>'
        + "".join(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(names, start=1)
        )
        + "</sheets></workbook>"
    )
    workbook_rels = (
        f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{package}">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(names) + 1)
        )
        + "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", content_types)
        book.writestr("_rels/.rels", root_rels)
        book.writestr("xl/workbook.xml", workbook)
        book.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for i, name in enumerate(names, start=1):
            cells = []
            for r, row in enumerate(sheets[name], start=1):
                parts = []
                for c, value in enumerate(row):
                    ref = f"{_column_letter(c)}{r}"
                    if isinstance(value, (int, float)):
                        parts.append(f'<c r="{ref}"><v>{value}</v></c>')
                    else:
                        parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
                cells.append(f'<row r="{r}">{"".join(parts)}</row>')
            book.writestr(
                f"xl/worksheets/sheet{i}.xml",
                f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{main}"><sheetData>'
                + "".join(cells)
                + "</sheetData></worksheet>",
            )
    return path


def build_reference(staging: Path, release: Path) -> list[ManifestEntry]:
    rows: list[ManifestEntry] = []

    def store(kind: str, edition: str, path: Path) -> None:
        rows.append(store_file(path, _entry(kind, edition, "published", path.name), release, STAMP, "reference"))

    for kind, edition, year in (
        ("lsoa11_sicbl_icb_lad_2022", "2022-07", 2022),
        ("lsoa21_sicbl_icb_lad_2023", "2023-04", 2023),
        ("lsoa21_sicbl_icb_lad_2024", "2024-04", 2024),
        ("lsoa21_sicbl_icb_lad_2025", "2025-04", 2025),
        ("lsoa21_sicbl_icb_lad_2026", "2026-04", 2026),
    ):
        header, body = health_lookup_rows(year)
        store(kind, edition, _write_csv(staging / f"{kind}.csv", header, body))

    lad_header = ["LAD22CD", "LAD22NM", "LAD22NMW", "LAD23CD", "LAD23NM", "LAD23NMW", "ObjectId"]
    lad_rows = [[*LAD22[p], "", *LAD23[p], "", str(i)] for i, p in enumerate(LAD22, start=1)]
    lad_rows.append(["W06000001", "Isle of Anglesey", "Ynys Mon", "W06000001", "Isle of Anglesey", "Ynys Mon", "9"])
    store("lad22_lad23", "2023-04", _write_csv(staging / "lad22_lad23.csv", lad_header, lad_rows))

    cumbria = ("E10000006", "Cumbria")
    essex = ("E10000012", "Essex")
    cty22 = [[*LAD22["basildon"], *essex, "1"]] + [
        [*LAD22[p], *cumbria, str(i)] for i, p in enumerate(["carlisle", "allerdale", "eden"], start=2)
    ]
    store(
        "lad22_cty22",
        "2022-12",
        _write_csv(staging / "lad22_cty22.csv", ["LAD22CD", "LAD22NM", "CTY22CD", "CTY22NM", "ObjectId"], cty22),
    )
    cty23 = [[*LAD23["basildon"], *essex, "1"]]
    store(
        "lad23_cty23",
        "2023-04",
        _write_csv(staging / "lad23_cty23.csv", ["LAD23CD", "LAD23NM", "CTY23CD", "CTY23NM", "ObjectId"], cty23),
    )

    store("iod_2025_file7", "2025-10", _write_csv(staging / "File_7_IoD2025.csv", iod_header(), iod_rows()))

    workbook = write_xlsx(
        staging / "sapelsoasyoa20232024.xlsx",
        {
            "Cover sheet": [["Population estimates for LSOAs, synthetic fixture"]],
            "Mid-2023 LSOA 2021": population_sheet(2023),
            "Mid-2024 LSOA 2021": population_sheet(2024),
        },
    )
    store("ons_lsoa_population_2022_2024", "2025-11", workbook)
    return rows


# Assembly -------------------------------------------------------------------

RELEASES = {
    "data-mhsds-monthly": build_mhsds,
    "data-talking-therapies-monthly": build_talking_therapies,
    "data-reference": build_reference,
}


def build_fixture(out_dir: Path) -> Path:
    """Write every fixture release with its manifest. Returns the folder holding the releases."""
    for release, builder in RELEASES.items():
        staging = out_dir / "source" / release
        folder = out_dir / release
        staging.mkdir(parents=True, exist_ok=True)
        folder.mkdir(parents=True, exist_ok=True)
        write_manifest(builder(staging, folder), folder / "manifest.csv")
    return out_dir


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write the synthetic warehouse fixture.")
    parser.add_argument("--out", type=Path, default=Path("data/interim/fixture"))
    args = parser.parse_args(argv)
    out = build_fixture(args.out)
    for release in RELEASES:
        print(f"Fixture release {out / release}")


if __name__ == "__main__":
    main()
