"""Contra el material real (material/2026-b3/...) — gitignoreado, no versionado (CLAUDE.md).

No hay golden files congelados con texto de IPLACEX: leerlos frescos evita reproducir
contenido con copyright en un repo público. Si material/ no está presente (checkout limpio,
CI), los tests se saltan — mismo patrón que los tests de AnkiConnect (CLAUDE.md: "la
inicialización del entorno pertenece al entorno, no a los tests").
"""

from pathlib import Path

import pytest

from flashcards_agent.ingest.reader import discover_week, read_docx, read_pdf

_MATE_S1 = Path("material/2026-b3/nivelacion-matematica/semana-1")
_THEORY_PDF = _MATE_S1 / "Nivelación Matemática - Semana 1.pdf"
_EJ_DOCX = _MATE_S1 / "Mate - Semana 1 - EJ_1.1.docx"

pytestmark = pytest.mark.skipif(
    not _THEORY_PDF.exists(),
    reason="material/2026-b3/ no disponible en este checkout (gitignoreado, CLAUDE.md)",
)


def test_read_pdf_returns_one_page_text_per_page():
    pages = read_pdf(_THEORY_PDF)

    assert len(pages) == 21
    assert "m.c.m" in pages[9].text
    assert "Bibliografía" in pages[19].text


def test_read_pdf_captures_image_count_per_page():
    pages = read_pdf(_THEORY_PDF)

    assert all(page.image_count >= 0 for page in pages)
    assert pages[0].image_count >= 1  # portada


def test_read_docx_returns_nonempty_paragraphs_in_order():
    paragraphs = read_docx(_EJ_DOCX)

    assert len(paragraphs) >= 20
    assert paragraphs[0] == "GUIA DE EJERCICIOS"


def test_discover_week_classifies_by_filename_convention():
    documents = discover_week("nivelacion-matematica", 1)

    assert len(documents) == 5
    kinds = [doc.kind for doc in documents]
    assert kinds.count("theory") == 1
    assert kinds.count("exercises") == 2
    assert kinds.count("answer_key") == 2


def test_discover_week_returns_empty_for_unknown_week():
    documents = discover_week("nivelacion-matematica", 99)

    assert documents == []
