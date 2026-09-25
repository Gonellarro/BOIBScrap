"""Resolución y descarga de PDFs de disposiciones coincidentes."""

import hashlib
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from .client import BoibClient
from .html_tools import absolute_links, parse_page
from .models import SearchResult


def pdf_url_for_result(client: BoibClient, result: SearchResult) -> str:
    """Encuentra en la versión HTML el enlace oficial de descarga PDF."""
    page = parse_page(client.get_text(result.document_url))
    links = absolute_links(page.links, result.document_url)
    for link in links:
        path = urlparse(link["href"]).path.casefold()
        label = link["text"].strip().casefold()
        is_pdf_route = (
            ("/eboibfront/pdf/ca/" in path)
            or ("/eli/" in path and path.endswith("/pdf"))
        )
        if is_pdf_route and ("pdf" in label or path.endswith("/pdf")):
            return link["href"]

    # Las páginas ELI emparejan las mismas rutas con el sufijo /html o /pdf.
    path = urlparse(result.document_url).path
    if "/eli/" in path and path.endswith("/html"):
        return result.document_url[:-4] + "pdf"
    raise RuntimeError(f"No se encontró el enlace PDF en {result.document_url}")


def _filename(result: SearchResult) -> str:
    title = unicodedata.normalize("NFKD", result.document_title)
    title = title.encode("ascii", "ignore").decode("ascii").casefold()
    title = re.sub(r"[^a-z0-9]+", "_", title).strip("_")[:90] or "disposicion"
    digest = hashlib.sha1(result.document_url.encode("utf-8")).hexdigest()[:8]
    section = result.section.replace(" ", "_")
    return f"BOIB_{result.bulletin.number}_{section}_{title}_{digest}.pdf"


def download_pdf(
    client: BoibClient, result: SearchResult, destination: Path
) -> tuple[str, Path]:
    """Descarga y valida el PDF; conserva una copia válida si ya existe."""
    source_url = pdf_url_for_result(client, result)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / _filename(result)
    if target.is_file():
        with target.open("rb") as existing:
            if existing.read(5) == b"%PDF-":
                return source_url, target

    content = client.get_bytes(source_url)
    if not content.lstrip().startswith(b"%PDF-"):
        raise RuntimeError(f"La respuesta de {source_url} no parece ser un PDF")

    temporary = target.with_suffix(target.suffix + ".part")
    temporary.write_bytes(content)
    temporary.replace(target)
    return source_url, target
