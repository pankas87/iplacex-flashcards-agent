"""Tipos de candidato a flashcard producidos por generate/ (TDD §4.7)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PracticeCardCandidate:
    front: str
    back: str
    deck: str
    tags: tuple[str, ...]
    fuente: str
