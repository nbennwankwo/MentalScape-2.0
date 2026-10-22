"""Read the MHSDS Monthly Statistics series page and its release pages.

The series page links to one page per release. Each release page lists its
files as download cards. These functions only parse HTML, so they can be
tested without the internet. Fetching lives in mentalscape.ingest.mhsds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

SERIES_URL = (
    "https://digital.nhs.uk/data-and-information/publications/statistical/mental-health-services-monthly-statistics"
)
FILES_HOST = "files.digital.nhs.uk"
SERIES_TITLE = "Mental Health Services Monthly Statistics"


@dataclass(frozen=True)
class ReleasePage:
    url: str
    title: str


@dataclass(frozen=True)
class DownloadCard:
    page_url: str
    page_title: str
    card_title: str
    source_url: str
    original_filename: str
    file_type: str
    size_text: str


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_series_page(html: str, series_url: str = SERIES_URL) -> list[ReleasePage]:
    """Return every release page linked from the series page, without duplicates."""
    soup = BeautifulSoup(html, "html.parser")
    series_path = urlparse(series_url).path.rstrip("/") + "/"
    pages: dict[str, ReleasePage] = {}
    for link in soup.find_all("a", href=True):
        title = _clean(link.get("title"))
        url = urljoin(series_url, link["href"])
        if not title.startswith(SERIES_TITLE) or not urlparse(url).path.startswith(series_path):
            continue
        pages.setdefault(url, ReleasePage(url=url, title=title))
    return list(pages.values())


def page_in_scope(page: ReleasePage, first_year: int) -> bool:
    """Keep pages whose title names first_year or later, or names no year at all."""
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", page.title)]
    return not years or max(years) >= first_year


def parse_release_page(html: str, page_url: str) -> list[DownloadCard]:
    """Return every downloadable file on a release page."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    page_title = _clean(heading.get_text()) if heading else ""
    cards = []
    for card in soup.select("div.nhsd-m-download-card"):
        link = card.find("a", href=True)
        if link is None or urlparse(link["href"]).netloc != FILES_HOST:
            continue
        title_tag = card.find("p")
        type_tag = card.select_one(".nhsd-a-tag--meta")
        size_tag = card.select_one(".nhsd-a-tag--meta-light")
        cards.append(
            DownloadCard(
                page_url=page_url,
                page_title=page_title,
                card_title=_clean(title_tag.get_text() if title_tag else link.get_text()),
                source_url=link["href"],
                original_filename=unquote(urlparse(link["href"]).path.rsplit("/", 1)[-1]),
                file_type=_clean(type_tag.get_text() if type_tag else "").lower(),
                size_text=_clean(size_tag.get_text() if size_tag else ""),
            )
        )
    return cards
