"""Descubrimiento y filtrado de boletines publicados."""

import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .client import BoibClient
from .html_tools import absolute_links, parse_page
from .models import Bulletin

_ISSUE_PATH = re.compile(r"/ca/(\d{4})/(\d+)(?:/|$)")
_MONTHS = {
    "gener": 1, "febrer": 2, "marc": 3, "març": 3, "abril": 4, "maig": 5,
    "juny": 6, "juliol": 7, "agost": 8, "setembre": 9,
    "octubre": 10, "novembre": 11, "desembre": 12,
}


class _AnnualCalendarParser(HTMLParser):
    """Asocia cada enlace del calendario anual con el mes de su tabla."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._table_year_month: tuple[int, int] | None = None
        self.entries: list[tuple[date, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            summary = attributes.get("summary") or ""
            match = re.search(r"de\s+([a-zà-ÿ]+)\s+de\s+(\d{4})", summary, re.IGNORECASE)
            month = _MONTHS.get(match.group(1).lower()) if match else None
            self._table_year_month = (int(match.group(2)), month) if month else None
        elif tag == "a" and self._table_year_month:
            href = attributes.get("href") or ""
            title = attributes.get("title") or ""
            day_match = re.search(r"del dia\s+(\d{1,2})", title, re.IGNORECASE)
            if href and day_match:
                year, month = self._table_year_month
                self.entries.append((date(year, month, int(day_match.group(1))), href))

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self._table_year_month = None


def _route(url: str) -> tuple[int, int] | None:
    match = _ISSUE_PATH.search(urlparse(url).path)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _bulletin_metadata(client: BoibClient, url: str) -> Bulletin:
    route = _route(url)
    if route is None:
        raise RuntimeError(f"No se reconoce la dirección de un BOIB: {url}")
    year, internal_id = route
    parser = parse_page(client.get_text(url))
    heading = " ".join(parser.text.split())
    match = re.search(
        r"BOIB\s+N[uú]m\.?\s*(\d+)\s*[-–]\s*(\d{1,2})\s*/\s*([a-zà-ÿ]+)\s*/\s*(\d{4})",
        heading,
        re.IGNORECASE,
    )
    if not match:
        raise RuntimeError(f"No se pudo leer el número y la fecha del boletín: {url}")
    day, month_name, issue_year = int(match.group(2)), match.group(3).lower(), int(match.group(4))
    month = _MONTHS.get(month_name)
    if month is None:
        raise RuntimeError(f"Mes catalán no reconocido en la página: {month_name}")
    published = date(issue_year, month, day)
    canonical_url = f"{client.base_url}ca/{year}/{internal_id}/"
    return Bulletin(year, internal_id, int(match.group(1)), published.isoformat(), canonical_url)


def _annual_calendar_entries(client: BoibClient, year: int) -> list[tuple[date, str]]:
    url = f"{client.base_url}ca/{year}/"
    parser = _AnnualCalendarParser()
    parser.feed(client.get_text(url))
    return [(published, urljoin(url, href)) for published, href in parser.entries]


def bulletins_in_range(client: BoibClient, start: date, end: date) -> list[Bulletin]:
    """Devuelve los boletines publicados dentro del intervalo inclusivo."""
    if start > end:
        raise ValueError("La fecha de inicio no puede ser posterior a la fecha de fin")

    candidates: dict[str, date] = {}
    for year in range(start.year, end.year + 1):
        for published, url in _annual_calendar_entries(client, year):
            if start <= published <= end:
                candidates[url] = published

    bulletins = []
    for url, calendar_date in sorted(candidates.items(), key=lambda entry: (entry[1], entry[0])):
        bulletin = _bulletin_metadata(client, url)
        if bulletin.published_date == calendar_date.isoformat():
            bulletins.append(bulletin)
    return sorted(bulletins, key=lambda bulletin: (bulletin.published_date, bulletin.number))


def _find_bulletins_on_date(client: BoibClient, requested_date: date) -> list[Bulletin]:
    return bulletins_in_range(client, requested_date, requested_date)


def latest_bulletins(client: BoibClient) -> list[Bulletin]:
    """Devuelve todos los números asociados a la fecha del último boletín."""
    home = parse_page(client.get_text(client.base_url))
    links = absolute_links(home.links, client.base_url)
    latest_link = next(
        (link for link in links if "darrer butlletí oficial" in link["text"].lower()),
        None,
    )
    if latest_link is None:
        raise RuntimeError("No se encontró en la portada el enlace al último BOIB")

    latest = _bulletin_metadata(client, latest_link["href"])
    published = date.fromisoformat(latest.published_date)

    # La portada suele mostrar el mes del último número y sus extraordinarios.
    candidates: set[str] = {latest.url}
    latest_in_calendar = False
    for link in links:
        route = _route(link["href"])
        day_text = re.fullmatch(r"\s*(\d{1,2})(?:\s*\*\s*E)?\s*", link["text"], re.IGNORECASE)
        if (
            route and route[0] == latest.year and day_text
            and int(day_text.group(1)) == published.day
        ):
            candidates.add(link["href"])
            if route == (latest.year, latest.internal_id):
                latest_in_calendar = True

    if not latest_in_calendar:
        return _find_bulletins_on_date(client, published)

    same_day = []
    for url in sorted(candidates):
        bulletin = _bulletin_metadata(client, url)
        if bulletin.published_date == latest.published_date:
            same_day.append(bulletin)
    return sorted(same_day, key=lambda bulletin: bulletin.number) or [latest]


def bulletins_on_date(client: BoibClient, requested_date: date) -> list[Bulletin]:
    """Encuentra todos los boletines de una fecha en el calendario anual oficial."""
    return _find_bulletins_on_date(client, requested_date)
