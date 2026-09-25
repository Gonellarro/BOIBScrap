"""Extracción de edictos de las secciones configuradas."""

import re
from urllib.parse import urlparse

from .client import BoibClient
from .html_tools import absolute_links, parse_page
from .models import Bulletin
from .sections import Section


def section_url(client: BoibClient, bulletin: Bulletin, section: Section) -> str:
    parser = parse_page(client.get_text(bulletin.url))
    expected_path = f"/{section.slug}/"
    for link in absolute_links(parser.links, bulletin.url):
        path = urlparse(link["href"]).path.casefold()
        label = link["text"].casefold()
        if expected_path in path or label.startswith(section.label.casefold()):
            return link["href"]
    # Las categorías del BOIB mantienen estos identificadores internos.
    return (
        f"{client.base_url}ca/{bulletin.year}/{bulletin.internal_id}/"
        f"{section.slug}/{section.category_id}"
    )


def dispositions(
    client: BoibClient, bulletin: Bulletin, section: Section
) -> tuple[str, list[dict[str, str]]]:
    category_url = section_url(client, bulletin, section)
    parser = parse_page(client.get_text(category_url))
    links = absolute_links(parser.links, category_url)
    base = f"/{bulletin.year}/{bulletin.internal_id}/"
    found: dict[str, str] = {}
    for link in links:
        path = urlparse(link["href"]).path
        match = re.search(re.escape(base) + r"(\d+)/([^/]+)/?$", path)
        is_eli_html = "/eli/" in path and path.endswith("/html")
        if "/pdf/" in path or path.endswith("/pdf") or "/xml/" in path or path.endswith("/xml"):
            continue
        if match:
            title = link.get("context_title") or link["text"]
            if title.casefold() in {"versió html", "versión html", "versió pdf", "versión pdf"}:
                title = match.group(2).rstrip("-").replace("-", " ").capitalize()
            title = title or f"Edicto {match.group(1)}"
        elif is_eli_html:
            title = link.get("context_title") or "Disposición BOIB"
        else:
            continue
        previous = found.get(link["href"], "")
        if len(title) > len(previous):
            found[link["href"]] = title
    return category_url, [
        {"url": url, "title": title}
        for url, title in sorted(found.items(), key=lambda item: item[1].casefold())
    ]
