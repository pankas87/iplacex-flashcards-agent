"""Tipos de candidato a flashcard producidos por generate/ (TDD §4.7)."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# Mapeo slug de carpeta -> nombre de materia (TDD §4.4). Vive acá, no en generate/practice.py
# ni en generate/theory.py: este módulo ya posee el campo `deck` de los candidatos, así que su
# constructor pertenece acá — evita que los dos sub-pipelines hermanos (TDD §4.5) se acoplen
# entre sí o dupliquen el mapeo. Movido desde generate/practice.py (IPL-28) en IPL-30, sin
# cambio de contenido.
_DECK_NAMES: dict[str, str] = {
    "nivelacion-matematica": "Nivelación Matemática",
    "soporte-sw-hw": "Soporte HW-SW",
}

# Alias cortos NO inventados (IPL-31): son los prefijos que usa el material real
# ("Mate - Semana 1 - EJ_1.1.docx", "Soporte - Semana 1 - EJ_1.docx").
_SUBJECT_ALIASES: dict[str, str] = {
    "mate": "nivelacion-matematica",
    "soporte": "soporte-sw-hw",
}


def deck_name(subject_slug: str, week: int) -> str:
    return f"{_DECK_NAMES[subject_slug]}::Semana {week}"


def normalize_subject_name(name: str) -> str:
    """Normalización TOLERANTE para nombres de materia tipeados en el CLI (IPL-31).

    Descarta tildes, colapsa mayúsculas/guiones/whitespace. A propósito no es la misma
    normalización que verify/grounding.normalize_for_grounding(): ahí la exactitud
    verbatim es la garantía; acá es una afordancia de UX sobre input de terminal.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    collapsed = without_marks.replace("-", " ").replace("_", " ").casefold()
    return " ".join(collapsed.split())


def _build_subject_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for slug, display in _DECK_NAMES.items():
        for key in (slug, slug.replace("-", " "), display):
            lookup[normalize_subject_name(key)] = slug
    for alias, slug in _SUBJECT_ALIASES.items():
        lookup[normalize_subject_name(alias)] = slug
    return lookup


_SUBJECT_LOOKUP: dict[str, str] = _build_subject_lookup()


def subject_slug_from_name(name: str) -> str | None:
    return _SUBJECT_LOOKUP.get(normalize_subject_name(name))


def known_subjects() -> tuple[str, ...]:
    return tuple(_DECK_NAMES.keys())


def known_subject_names() -> tuple[str, ...]:
    return tuple(_DECK_NAMES.values())


@dataclass(frozen=True)
class PracticeCardCandidate:
    front: str
    back: str
    deck: str
    tags: tuple[str, ...]
    fuente: str


@dataclass(frozen=True)
class TheoryCardCandidate:
    front: str
    back: str
    deck: str
    tags: tuple[str, ...]
    fuente: str
    level: int  # 1 | 2 | 3 — dificultad. Dato interno: no viaja como campo a Anki, sí como tag.


CardCandidate = PracticeCardCandidate | TheoryCardCandidate
