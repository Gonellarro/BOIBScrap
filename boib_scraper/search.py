"""Búsqueda de términos en las versiones HTML de las disposiciones."""

import re
import unicodedata
from collections.abc import Callable

from .client import BoibClient
from .dispositions import dispositions
from .html_tools import parse_page
from .models import Bulletin, Match, SearchResult
from .sections import normalize_section


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _normalize_with_offsets(text: str) -> tuple[str, list[int]]:
    normalized: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(text):
        decomposed = unicodedata.normalize("NFKD", char.casefold())
        for item in decomposed:
            if not unicodedata.combining(item):
                normalized.append(item)
                offsets.append(index)
    return "".join(normalized), offsets


def _excerpt(text: str, start: int, end: int, radius: int = 110) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    excerpt = " ".join(text[left:right].split())
    return ("…" if left else "") + excerpt + ("…" if right < len(text) else "")


def search_bulletin(
    client: BoibClient,
    bulletin: Bulletin,
    terms: list[str],
    sections: list[str] | None = None,
    progress: Callable[[str], None] | None = None,
    together_terms: list[str] | None = None,
) -> list[SearchResult]:
    selected_sections = [normalize_section(value) for value in (sections or ["III"])]
    or_terms = [term.strip() for term in terms if term.strip()]
    and_terms = [term.strip() for term in (together_terms or []) if term.strip()]
    results: list[SearchResult] = []
    for section in selected_sections:
        if progress:
            progress(f"BOIB {bulletin.number}: localizando {section.label} — {section.name}")
        section_url, items = dispositions(client, bulletin, section)
        if progress:
            progress(f"BOIB {bulletin.number} / {section.label}: {len(items)} disposición(es) en {section_url}")
        for index, item in enumerate(items, start=1):
            if progress:
                progress(
                    f"BOIB {bulletin.number} / {section.label}: leyendo {index}/{len(items)}: "
                    f"{item['title']} — {item['url']}"
                )
            page = parse_page(client.get_text(item["url"]))
            normalized_text, offsets = _normalize_with_offsets(page.text)

            def find_term(term: str, logic: str) -> Match | None:
                normalized_term = normalize(term)
                if not normalized_term:
                    return None
                start = normalized_text.find(normalized_term)
                if start < 0:
                    return None
                original_start = offsets[start]
                original_end = offsets[start + len(normalized_term) - 1] + 1
                return Match(
                    term=term,
                    excerpt=_excerpt(page.text, original_start, original_end),
                    logic=logic,
                )

            or_matches = [match for term in or_terms if (match := find_term(term, "OR"))]
            and_matches = [match for term in and_terms if (match := find_term(term, "AND"))]
            and_group_satisfied = bool(and_terms) and len(and_matches) == len(and_terms)
            matched = or_matches + (and_matches if and_group_satisfied else [])
            if matched:
                if progress:
                    matched_terms = ", ".join(f"{match.logic}: {match.term}" for match in matched)
                    progress(f"BOIB {bulletin.number} / {section.label}: coincidencia para {matched_terms}")
                results.append(
                    SearchResult(
                        bulletin=bulletin,
                        section=section.label,
                        section_url=section_url,
                        document_title=item["title"],
                        document_url=item["url"],
                        matches=tuple(matched),
                    )
                )
    return results
