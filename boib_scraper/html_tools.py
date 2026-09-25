"""Utilidades HTML pequeñas, implementadas con la biblioteca estándar."""

from html.parser import HTMLParser
from urllib.parse import urljoin


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self._anchor: dict[str, str] | None = None
        self._capture_text = False
        self._skip_depth = 0
        self._paragraph_parts: list[str] | None = None
        self._last_document_title = ""
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a":
            self._anchor = {
                "href": attributes.get("href") or "",
                "text": "",
                "context_title": self._last_document_title,
            }
        if tag == "p":
            self._paragraph_parts = []
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._anchor is not None:
            self._anchor["text"] = " ".join(self._anchor["text"].split())
            self.links.append(self._anchor)
            self._anchor = None
        if tag == "p" and self._paragraph_parts is not None:
            paragraph = " ".join(" ".join(self._paragraph_parts).split())
            folded = paragraph.casefold()
            if paragraph and not folded.startswith(("número d", "número de")):
                self._last_document_title = paragraph
            self._paragraph_parts = None
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        self.text_parts.append(clean)
        if self._paragraph_parts is not None:
            self._paragraph_parts.append(clean)
        if self._anchor is not None:
            self._anchor["text"] += " " + clean

    @property
    def text(self) -> str:
        return "\n".join(part for part in self.text_parts if part).strip()


def parse_page(html: str) -> PageParser:
    parser = PageParser()
    parser.feed(html)
    return parser


def absolute_links(links: list[dict[str, str]], base_url: str) -> list[dict[str, str]]:
    return [
        {
            **item,
            "href": urljoin(base_url, item["href"]),
            "text": item.get("text", ""),
        }
        for item in links
        if item.get("href")
    ]
