"""generate/practice.py — mockea el SDK, no llama al LLM real en cada corrida de tests.

Los fixtures de structured_output son la salida REAL y completa de llamadas reales al SDK
(verificación hecha durante la implementación de SPEC-1-IT4, 2026-08-08, contra los
enunciados reales de mcm/mcd de Mate S1 EJ_1.1/R_1.1, IPL-26/27, más un enunciado
no-arítmético para el caso no-traducible) — no fabricados (CLAUDE.md: "golden files,
siempre reales — nunca fabricados para que el test pase").

La llamada real también reveló que Sonnet, a diferencia de Haiku en classify/segmenter.py,
a veces intercala un turno de texto explicativo antes de llamar la tool de structured
output — motivo del max_turns=3 en practice.py (no 1).
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage

from flashcards_agent.generate.practice import deck_name, level1_candidates, translate_exercise
from flashcards_agent.ingest.exercises import (
    extract_exercise_statements,
    pair_exercises,
    parse_answer_key,
)
from flashcards_agent.ingest.reader import read_pdf
from flashcards_agent.models.content import ExercisePair

_MATE_S1 = Path("material/2026-b3/nivelacion-matematica/semana-1")
_EJ_DOCX = _MATE_S1 / "Mate - Semana 1 - EJ_1.1.docx"
_R_PDF = _MATE_S1 / "Mate - Semana 1 - R_1.1.pdf"

_requires_material = pytest.mark.skipif(
    not _EJ_DOCX.exists(),
    reason="material/2026-b3/ no disponible en este checkout (gitignoreado, CLAUDE.md)",
)

# statement real de Mate S1 EJ_1.1, ej. 12 — mcm(4, 3). Copiado literal para no depender de
# material/ en los tests que no necesitan ir a buscar el par completo.
_EJ_12_STATEMENT = (
    "Miguel tiene que ir a comprar abarrotes al supermercado. Cada 4 días va a comprar lo "
    "que le mandan sus padres, y cada 3 días su abuela le manda a comprar también. "
    "Suponiendo que hoy ya ha realizado las dos compras juntas ¿Dentro de cuantos días "
    "tendrá que volver a comprar los dos pedidos juntos?"
)
_EJ_12_STRUCTURED = {
    "steps": [{"operation": "mcm", "operands": [4, 3]}],
    "translatable": True,
    "topic_tag": "mcm",
}

# ej. 17 — mcd(25, 15, 90) seguido de 3 divisiones con StepRef, es el único de los seis con
# un plan multi-step: buen caso para testear translate_exercise() por separado.
_EJ_17_STATEMENT = (
    "María y Carolina tiene 25 perlas blancas, 15 perlas azules y 90 perlas rojas. Ellas "
    "quieren hacer el mayor número de collares iguales sin que sobre ninguna perla. "
    "¿Cuántos collares iguales pueden hacer?, ¿Cuántas perlas de cada color tendrá cada "
    "collar?"
)
_EJ_17_STRUCTURED = {
    "steps": [
        {"operation": "mcd", "operands": [25, 15, 90]},
        {"operation": "divide", "operands": [25, {"step": 0}]},
        {"operation": "divide", "operands": [15, {"step": 0}]},
        {"operation": "divide", "operands": [90, {"step": 0}]},
    ],
    "translatable": True,
    "topic_tag": "mcd",
}

_NON_ARITHMETIC_STATEMENT = "Describe brevemente la importancia del respeto en la sala de clases."
_NON_ARITHMETIC_STRUCTURED = {"steps": [], "topic_tag": "", "translatable": False}

# Los seis ejercicios de mcm/mcd que el acceptance criteria de IPL-28 nombra explícitamente,
# con la traducción real capturada del SDK y el resultado esperado de execute_plan().
_KNOWN_MCM_MCD: dict[int, tuple[dict, str]] = {
    12: ({"steps": [{"operation": "mcm", "operands": [4, 3]}], "translatable": True, "topic_tag": "mcm"}, "12"),
    13: ({"steps": [{"operation": "mcm", "operands": [15, 10]}], "translatable": True, "topic_tag": "mcm"}, "30"),
    15: (
        {"steps": [{"operation": "mcm", "operands": [6, 4, 12]}], "translatable": True, "topic_tag": "mcm"},
        "12",
    ),
    17: (_EJ_17_STRUCTURED, "18"),
    19: ({"steps": [{"operation": "mcd", "operands": [45, 60]}], "translatable": True, "topic_tag": "mcd"}, "15"),
    20: ({"steps": [{"operation": "mcd", "operands": [12, 8]}], "translatable": True, "topic_tag": "mcd"}, "4"),
}


def _real_pairs() -> tuple[ExercisePair, ...]:
    statements = extract_exercise_statements(_EJ_DOCX)
    answers = parse_answer_key(read_pdf(_R_PDF))
    return pair_exercises(statements, answers, "EJ_1.1.docx")


def _fake_query_for(mapping: dict[str, dict]):
    async def _fake_query(*, prompt, options):
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="test",
            structured_output=mapping[prompt],
        )

    return _fake_query


def test_deck_name_nivelacion_matematica():
    assert deck_name("nivelacion-matematica", 1) == "Nivelación Matemática::Semana 1"


def test_deck_name_soporte_sw_hw():
    assert deck_name("soporte-sw-hw", 3) == "Soporte HW-SW::Semana 3"


def test_translate_exercise_returns_plan_with_step_refs():
    fake_query = _fake_query_for({_EJ_17_STATEMENT: _EJ_17_STRUCTURED})

    with patch("flashcards_agent.generate.practice.query", new=fake_query):
        translation = translate_exercise(_EJ_17_STATEMENT)

    assert translation is not None
    assert translation.topic_tag == "mcd"
    assert len(translation.plan.steps) == 4
    assert translation.plan.steps[0].operation == "mcd"
    assert translation.plan.steps[0].operands == (25, 15, 90)
    assert translation.plan.steps[3].operands[0] == 90


def test_translate_exercise_returns_none_when_not_translatable():
    fake_query = _fake_query_for({_NON_ARITHMETIC_STATEMENT: _NON_ARITHMETIC_STRUCTURED})

    with patch("flashcards_agent.generate.practice.query", new=fake_query):
        translation = translate_exercise(_NON_ARITHMETIC_STATEMENT)

    assert translation is None


@_requires_material
def test_level1_candidates_produces_verified_candidates_for_known_mcm_mcd_exercises():
    pairs = _real_pairs()
    subset = tuple(p for p in pairs if p.index in _KNOWN_MCM_MCD)
    mapping = {p.statement: _KNOWN_MCM_MCD[p.index][0] for p in subset}
    fake_query = _fake_query_for(mapping)

    with patch("flashcards_agent.generate.practice.query", new=fake_query):
        candidates = level1_candidates(subset, "nivelacion-matematica", 1)

    assert len(candidates) == 6
    computed_by_source = {c.fuente: c.back for c in candidates}
    for pair in subset:
        _, expected_back = _KNOWN_MCM_MCD[pair.index]
        assert computed_by_source[pair.source_ref] == expected_back

    for candidate in candidates:
        assert candidate.fuente != ""
        assert "verificado" in candidate.tags
        assert candidate.deck == "Nivelación Matemática::Semana 1"


def test_level1_candidates_discards_on_forced_disagreement(capsys):
    pair = ExercisePair(
        index=12,
        statement=_EJ_12_STATEMENT,
        published_answer="Dentro de 99 días.",  # alterada — mcm(4,3) = 12, no 99
        source_ref="EJ_1.1.docx, ej. 12",
    )
    fake_query = _fake_query_for({_EJ_12_STATEMENT: _EJ_12_STRUCTURED})

    with patch("flashcards_agent.generate.practice.query", new=fake_query):
        candidates = level1_candidates((pair,), "nivelacion-matematica", 1)

    assert candidates == ()
    captured = capsys.readouterr()
    assert "EJ_1.1.docx, ej. 12" in captured.out
    assert "cómputo no coincide" in captured.out


def test_level1_candidates_discards_non_translatable_and_continues_with_rest(capsys):
    translatable_pair = ExercisePair(
        index=12,
        statement=_EJ_12_STATEMENT,
        published_answer="Dentro de 12 días.",
        source_ref="EJ_1.1.docx, ej. 12",
    )
    non_translatable_pair = ExercisePair(
        index=1,
        statement=_NON_ARITHMETIC_STATEMENT,
        published_answer="cualquier cosa",
        source_ref="synthetic.docx, ej. 1",
    )
    mapping = {
        _EJ_12_STATEMENT: _EJ_12_STRUCTURED,
        _NON_ARITHMETIC_STATEMENT: _NON_ARITHMETIC_STRUCTURED,
    }
    fake_query = _fake_query_for(mapping)

    with patch("flashcards_agent.generate.practice.query", new=fake_query):
        candidates = level1_candidates(
            (non_translatable_pair, translatable_pair), "nivelacion-matematica", 1
        )

    assert len(candidates) == 1
    assert candidates[0].fuente == "EJ_1.1.docx, ej. 12"
    captured = capsys.readouterr()
    assert "synthetic.docx, ej. 1: no traducible" in captured.out


def test_level1_candidates_topic_tag_override():
    pair = ExercisePair(
        index=12,
        statement=_EJ_12_STATEMENT,
        published_answer="Dentro de 12 días.",
        source_ref="EJ_1.1.docx, ej. 12",
    )
    fake_query = _fake_query_for({_EJ_12_STATEMENT: _EJ_12_STRUCTURED})

    with patch("flashcards_agent.generate.practice.query", new=fake_query):
        candidates = level1_candidates(
            (pair,), "nivelacion-matematica", 1, topic_tag_override="operatoria_semana_1"
        )

    assert candidates[0].tags == ("operatoria_semana_1", "verificado")
