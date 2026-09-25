"""Secciones del BOIB admitidas por el scraper."""

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    code: str
    name: str
    slug: str
    category_id: int

    @property
    def label(self) -> str:
        return f"Secció {self.code}"


SECTIONS = {
    "I": Section("I", "Disposicions generals", "seccio-i-disposicions-generals", 471),
    "II": Section("II", "Autoritats i personal", "seccio-ii-autoritats-i-personal", 473),
    "III": Section(
        "III", "Altres disposicions i actes administratius",
        "seccio-iii-altres-disposicions-i-actes-administrat", 472,
    ),
    "V": Section("V", "Anuncis", "seccio-v-anuncis", 475),
}


def normalize_section(value: str) -> Section:
    """Acepta I/II/III/V o etiquetas como «Secció III»."""
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    match = re.fullmatch(r"(?:seccio(?:n)?\s*)?(i{1,3}|v)", value)
    if not match:
        valid = ", ".join(SECTIONS)
        raise ValueError(f"Sección no válida: {value!r}. Usa una de estas: {valid}")
    return SECTIONS[match.group(1).upper()]
