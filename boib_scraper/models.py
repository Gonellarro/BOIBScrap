"""Modelos de datos del scraper."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Bulletin:
    year: int
    internal_id: int
    number: int
    published_date: str
    url: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Match:
    term: str
    excerpt: str
    logic: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SearchResult:
    bulletin: Bulletin
    section: str
    section_url: str
    document_title: str
    document_url: str
    matches: tuple[Match, ...]
    pdf_url: str | None = None
    pdf_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "bulletin": self.bulletin.to_dict(),
            "section": self.section,
            "section_url": self.section_url,
            "document_title": self.document_title,
            "document_url": self.document_url,
            "pdf_url": self.pdf_url,
            "pdf_path": self.pdf_path,
            "matches": [match.to_dict() for match in self.matches],
        }
