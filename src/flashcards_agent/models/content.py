"""Tipos compartidos entre módulos del pipeline de ingesta y clasificación."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class PageText:
    """Una unidad de texto extraído.

    Para PDF, una página real. Para DOCX (sin concepto de página), cada párrafo no vacío
    se representa como un PageText propio — number es la posición 1-indexed del párrafo,
    image_count siempre 0 (python-docx no da conteo de imágenes por párrafo).
    """

    number: int
    text: str
    image_count: int


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    kind: Literal["theory", "exercises", "answer_key"]
    subject_slug: str
    week: int
    pages: tuple[PageText, ...]


@dataclass(frozen=True)
class ExercisePair:
    index: int
    statement: str
    published_answer: str | None
    source_ref: str


@dataclass(frozen=True)
class ContentSegment:
    title: str
    body: str
    topic_tag: str
    flavor: Literal["theory", "practice", "discard"]
    source_ref: str
