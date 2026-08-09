"""Tipos de candidato a flashcard producidos por generate/ (TDD §4.7)."""

from __future__ import annotations

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


def deck_name(subject_slug: str, week: int) -> str:
    return f"{_DECK_NAMES[subject_slug]}::Semana {week}"


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
