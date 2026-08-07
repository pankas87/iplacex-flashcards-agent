"""Contra el material real para el caso feliz; sintético para el caso de error.

Ver nota de tests/ingest/test_reader.py sobre por qué no hay golden files congelados.
"""

from pathlib import Path

import pytest

from flashcards_agent.ingest.exercises import (
    ExercisePairingError,
    extract_exercise_statements,
    pair_exercises,
    parse_answer_key,
)
from flashcards_agent.ingest.reader import read_pdf

_MATE_S1 = Path("material/2026-b3/nivelacion-matematica/semana-1")
_EJ_DOCX = _MATE_S1 / "Mate - Semana 1 - EJ_1.1.docx"
_R_PDF = _MATE_S1 / "Mate - Semana 1 - R_1.1.pdf"

_requires_material = pytest.mark.skipif(
    not _EJ_DOCX.exists(),
    reason="material/2026-b3/ no disponible en este checkout (gitignoreado, CLAUDE.md)",
)


@_requires_material
def test_extract_exercise_statements_filters_headers_by_style():
    statements = extract_exercise_statements(_EJ_DOCX)

    assert len(statements) == 20
    assert "GUIA DE EJERCICIOS" not in statements
    assert "EJERCICIOS PROPUESTOS." not in statements


@_requires_material
def test_parse_answer_key_extracts_numbered_answers_in_order():
    pages = read_pdf(_R_PDF)

    answers = parse_answer_key(pages)

    assert len(answers) == 20
    assert answers[0] == "Demorará 8 días."


@_requires_material
def test_parse_answer_key_merges_wrapped_lines_into_one_answer():
    pages = read_pdf(_R_PDF)

    answers = parse_answer_key(pages)

    # El PDF parte esta respuesta en dos líneas ("...azules y" / "18perlas rojas."),
    # sin espacio entre "18" y "perlas" — no debe leerse como un ítem 18 nuevo.
    assert "18perlas" in answers[16] or "18 perlas" in answers[16]


@_requires_material
def test_pair_exercises_matches_statements_to_answers_positionally():
    pages = read_pdf(_R_PDF)
    statements = extract_exercise_statements(_EJ_DOCX)
    answers = parse_answer_key(pages)

    pairs = pair_exercises(statements, answers, "EJ_1.1.docx")

    assert len(pairs) == 20
    assert pairs[0].index == 1
    assert pairs[0].source_ref == "EJ_1.1.docx, ej. 1"
    assert pairs[0].published_answer == answers[0]


def test_pair_exercises_raises_on_count_mismatch():
    with pytest.raises(ExercisePairingError, match=r"3 enunciados vs 2 respuestas"):
        pair_exercises(("a", "b", "c"), ("x", "y"), "test.docx")
