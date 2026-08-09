"""cli/pipeline.py — orquestación (US-8, IPL-31).

group_exercise_documents() se testea puro, con SourceDocument construidos a mano. process_week()
se testea con sus colaboradores mockeados (patch en el namespace de flashcards_agent.cli.pipeline,
mismo patrón que tests/generate/test_practice.py), más dos tests marcados @_requires_material
(skip accionable si material/ no está — CLAUDE.md) que ejercitan discover_week + el pareo real
sin tocar LLM ni Anki, calcado del patrón de tests/generate/test_practice.py.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from flashcards_agent.anki.client import AnkiConnectError, AnkiConnectStatus
from flashcards_agent.cli.pipeline import (
    ExerciseGroup,
    group_exercise_documents,
    process_week,
)
from flashcards_agent.ingest.exercises import (
    extract_exercise_statements,
    pair_exercises,
    parse_answer_key,
)
from flashcards_agent.ingest.reader import discover_week
from flashcards_agent.models.card import PracticeCardCandidate, TheoryCardCandidate
from flashcards_agent.models.content import ContentSegment, PageText, SourceDocument

_requires_material = pytest.mark.skipif(
    not Path("material/2026-b3/nivelacion-matematica/semana-1/Mate - Semana 1 - EJ_1.1.docx").exists(),
    reason="material/2026-b3/ no disponible en este checkout (gitignoreado, CLAUDE.md)",
)

_OK_STATUS = AnkiConnectStatus(ok=True, version=6, detail="AnkiConnect vivo")
_DOWN_STATUS = AnkiConnectStatus(ok=False, version=None, detail="no se pudo conectar")


def _doc(kind, name, subject_slug="nivelacion-matematica", week=1) -> SourceDocument:
    return SourceDocument(
        path=Path(name),
        kind=kind,
        subject_slug=subject_slug,
        week=week,
        pages=(PageText(number=1, text="x", image_count=0),),
    )


def _segment(flavor: str, topic_tag: str = "mcm", body: str = "cuerpo") -> ContentSegment:
    return ContentSegment(
        title="t", body=body, topic_tag=topic_tag, flavor=flavor, source_ref="doc.pdf, p. 1"
    )


def _theory_candidate(n: int = 1) -> TheoryCardCandidate:
    return TheoryCardCandidate(
        front=f"¿Verdadero o falso? afirmación {n}",
        back="Verdadero — porque sí",
        deck="Nivelación Matemática::Semana 1",
        tags=("mcm", "nivel-1", "verificado"),
        fuente="doc.pdf, p. 1",
        level=1,
    )


def _practice_candidate(n: int = 1) -> PracticeCardCandidate:
    return PracticeCardCandidate(
        front=f"enunciado {n}",
        back=str(n),
        deck="Nivelación Matemática::Semana 1",
        tags=("mcm", "verificado"),
        fuente=f"EJ_1.1.docx, ej. {n}",
    )


# ─────────────────────────────────────────────────────────────────────────
# group_exercise_documents — puro
# ─────────────────────────────────────────────────────────────────────────


def test_group_exercise_documents_pairs_two_complete_groups():
    documents = [
        _doc("exercises", "Mate - Semana 1 - EJ_1.1.docx"),
        _doc("answer_key", "Mate - Semana 1 - R_1.1.pdf"),
        _doc("exercises", "Mate - Semana 1 - EJ_1.2.docx"),
        _doc("answer_key", "Mate - Semana 1 - R_1.2.pdf"),
        _doc("theory", "Nivelación Matemática - Semana 1.pdf"),
    ]

    groups = group_exercise_documents(documents)

    assert groups == (
        ExerciseGroup(
            key="1.1",
            exercises=documents[0],
            answer_key=documents[1],
        ),
        ExerciseGroup(
            key="1.2",
            exercises=documents[2],
            answer_key=documents[3],
        ),
    )


def test_group_exercise_documents_warns_and_skips_orphan_exercises(capsys):
    documents = [_doc("exercises", "Mate - Semana 1 - EJ_1.1.docx")]

    groups = group_exercise_documents(documents)

    assert groups == ()
    captured = capsys.readouterr()
    assert "EJ_1.1.docx" in captured.out
    assert "sin su archivo R_" in captured.out


def test_group_exercise_documents_warns_and_skips_orphan_answer_key(capsys):
    documents = [_doc("answer_key", "Mate - Semana 1 - R_1.1.pdf")]

    groups = group_exercise_documents(documents)

    assert groups == ()
    captured = capsys.readouterr()
    assert "R_1.1.pdf" in captured.out
    assert "sin su archivo EJ_" in captured.out


def test_group_exercise_documents_empty_when_only_theory():
    documents = [_doc("theory", "Nivelación Matemática - Semana 1.pdf")]

    assert group_exercise_documents(documents) == ()


# ─────────────────────────────────────────────────────────────────────────
# process_week — colaboradores mockeados
# ─────────────────────────────────────────────────────────────────────────

_PATCH_ROOT = "flashcards_agent.cli.pipeline"


def test_process_week_unknown_subject_short_circuits(capsys):
    with (
        patch(f"{_PATCH_ROOT}.check_connection") as mock_conn,
        patch(f"{_PATCH_ROOT}.discover_week") as mock_discover,
    ):
        report = process_week("algebra-lineal", 1)

    assert report.status == "materia-desconocida"
    mock_conn.assert_not_called()
    mock_discover.assert_not_called()
    assert "materia desconocida" in capsys.readouterr().out


def test_process_week_no_connection_short_circuits_before_reading_material():
    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_DOWN_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week") as mock_discover,
        patch(f"{_PATCH_ROOT}.segment") as mock_segment,
        patch(f"{_PATCH_ROOT}.theory_candidates") as mock_theory,
        patch(f"{_PATCH_ROOT}.level1_candidates") as mock_practice,
        patch(f"{_PATCH_ROOT}.add_candidates") as mock_add,
    ):
        report = process_week("nivelacion-matematica", 1)

    assert report.status == "sin-conexion"
    mock_discover.assert_not_called()
    mock_segment.assert_not_called()
    mock_theory.assert_not_called()
    mock_practice.assert_not_called()
    mock_add.assert_not_called()


def test_process_week_no_material_short_circuits():
    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[]),
        patch(f"{_PATCH_ROOT}.theory_candidates") as mock_theory,
        patch(f"{_PATCH_ROOT}.level1_candidates") as mock_practice,
        patch(f"{_PATCH_ROOT}.add_candidates") as mock_add,
    ):
        report = process_week("nivelacion-matematica", 2)

    assert report.status == "sin-material"
    mock_theory.assert_not_called()
    mock_practice.assert_not_called()
    mock_add.assert_not_called()


def test_process_week_passes_only_theory_flavor_segments_and_counts_skipped():
    theory_doc = _doc("theory", "Nivelación Matemática - Semana 1.pdf")
    segments = (
        _segment("theory", topic_tag="mcm"),
        _segment("theory", topic_tag="mcd"),
        _segment("practice"),
        _segment("discard"),
    )

    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[theory_doc]),
        patch(f"{_PATCH_ROOT}.segment", return_value=segments) as mock_segment,
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=()) as mock_theory,
        patch(f"{_PATCH_ROOT}.level1_candidates", return_value=()) as mock_practice,
        patch(f"{_PATCH_ROOT}.add_candidates", return_value=()),
    ):
        report = process_week("nivelacion-matematica", 1)

    mock_segment.assert_called_once_with(theory_doc)
    theory_arg = mock_theory.call_args.args[0]
    assert theory_arg == segments[:2]
    assert report.theory_segments == 2
    assert report.skipped_segments == 2
    mock_practice.assert_called_once_with((), "nivelacion-matematica", 1)


def test_process_week_segment_runtime_error_skips_document_and_continues(capsys):
    theory_doc = _doc("theory", "Nivelación Matemática - Semana 1.pdf")

    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[theory_doc]),
        patch(f"{_PATCH_ROOT}.segment", side_effect=RuntimeError("sin structured_output")),
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=()) as mock_theory,
        patch(f"{_PATCH_ROOT}.level1_candidates", return_value=()),
        patch(f"{_PATCH_ROOT}.add_candidates", return_value=()),
    ):
        report = process_week("nivelacion-matematica", 1)

    assert report.status == "ok"
    mock_theory.assert_called_once_with((), "nivelacion-matematica", 1)
    captured = capsys.readouterr()
    assert "Nivelación Matemática - Semana 1.pdf" in captured.out
    assert "segmentación falló" in captured.out


def test_process_week_inserts_concatenation_of_theory_and_practice_candidates():
    theory_doc = _doc("theory", "Nivelación Matemática - Semana 1.pdf")
    theory_cards = (_theory_candidate(1), _theory_candidate(2))
    practice_cards = (_practice_candidate(1),)
    all_cards = theory_cards + practice_cards

    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[theory_doc]),
        patch(f"{_PATCH_ROOT}.segment", return_value=(_segment("theory"),)),
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=theory_cards),
        patch(f"{_PATCH_ROOT}.level1_candidates", return_value=practice_cards),
        patch(f"{_PATCH_ROOT}.add_candidates", return_value=all_cards) as mock_add,
    ):
        report = process_week("nivelacion-matematica", 1)

    mock_add.assert_called_once_with(all_cards, None)
    assert report.status == "ok"
    assert report.theory_cards == 2
    assert report.practice_cards == 1
    assert report.generated == 3
    assert report.inserted == 3
    assert report.not_inserted == 0


def test_process_week_ankiconnect_error_during_insertion_preserves_counts(capsys):
    theory_doc = _doc("theory", "Nivelación Matemática - Semana 1.pdf")
    theory_cards = (_theory_candidate(1),)

    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[theory_doc]),
        patch(f"{_PATCH_ROOT}.segment", return_value=(_segment("theory"),)),
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=theory_cards),
        patch(f"{_PATCH_ROOT}.level1_candidates", return_value=()),
        patch(f"{_PATCH_ROOT}.add_candidates", side_effect=AnkiConnectError("boom")),
    ):
        report = process_week("nivelacion-matematica", 1)

    assert report.status == "error-insercion"
    assert report.theory_cards == 1
    assert report.inserted == 0
    assert "inserción abortada" in capsys.readouterr().out


def test_process_week_calls_collaborators_in_order():
    call_order: list[str] = []
    theory_doc = _doc("theory", "Nivelación Matemática - Semana 1.pdf")

    def _track(name):
        def _side_effect(*_args, **_kwargs):
            call_order.append(name)
            if name == "check_connection":
                return _OK_STATUS
            if name == "discover_week":
                return [theory_doc]
            if name == "segment":
                return (_segment("theory"),)
            if name in ("theory_candidates", "level1_candidates"):
                return ()
            if name == "add_candidates":
                return ()
            return None

        return _side_effect

    with (
        patch(f"{_PATCH_ROOT}.check_connection", side_effect=_track("check_connection")),
        patch(f"{_PATCH_ROOT}.discover_week", side_effect=_track("discover_week")),
        patch(f"{_PATCH_ROOT}.segment", side_effect=_track("segment")),
        patch(f"{_PATCH_ROOT}.theory_candidates", side_effect=_track("theory_candidates")),
        patch(f"{_PATCH_ROOT}.level1_candidates", side_effect=_track("level1_candidates")),
        patch(f"{_PATCH_ROOT}.add_candidates", side_effect=_track("add_candidates")),
    ):
        process_week("nivelacion-matematica", 1)

    assert call_order.index("check_connection") < call_order.index("discover_week")
    assert call_order.index("discover_week") < call_order.index("segment")
    assert call_order.index("segment") < call_order.index("theory_candidates")
    assert call_order.index("theory_candidates") < call_order.index("add_candidates")
    assert call_order.index("level1_candidates") < call_order.index("add_candidates")


# ─────────────────────────────────────────────────────────────────────────
# process_week — scope="theory" (IPL-32): la rama práctica se saltea por completo
# ─────────────────────────────────────────────────────────────────────────


def test_process_week_theory_scope_never_calls_exercise_collaborators():
    theory_doc = _doc("theory", "Nivelación Matemática - Semana 1.pdf")
    ej_doc = _doc("exercises", "Mate - Semana 1 - EJ_1.1.docx")
    r_doc = _doc("answer_key", "Mate - Semana 1 - R_1.1.pdf")

    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[theory_doc, ej_doc, r_doc]),
        patch(f"{_PATCH_ROOT}.segment", return_value=(_segment("theory"),)),
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=(_theory_candidate(1),)),
        patch(f"{_PATCH_ROOT}.group_exercise_documents") as mock_group,
        patch(f"{_PATCH_ROOT}.pair_exercises") as mock_pair,
        patch(f"{_PATCH_ROOT}.level1_candidates") as mock_practice,
        patch(f"{_PATCH_ROOT}.add_candidates", return_value=(_theory_candidate(1),)),
    ):
        report = process_week("nivelacion-matematica", 1, scope="theory")

    mock_group.assert_not_called()
    mock_pair.assert_not_called()
    mock_practice.assert_not_called()
    assert report.scope == "theory"
    assert report.practice_requested is False
    assert report.exercise_groups == 0
    assert report.pairing_failures == 0
    assert report.exercise_pairs == 0
    assert report.practice_cards == 0
    assert report.theory_cards == 1


def test_process_week_theory_scope_summary_omits_exercise_lines(capsys):
    theory_doc = _doc("theory", "Nivelación Matemática - Semana 1.pdf")

    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[theory_doc]),
        patch(f"{_PATCH_ROOT}.segment", return_value=(_segment("theory"),)),
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=(_theory_candidate(1),)),
        patch(f"{_PATCH_ROOT}.add_candidates", return_value=(_theory_candidate(1),)),
    ):
        process_week("nivelacion-matematica", 1, scope="theory")

    captured = capsys.readouterr().out
    assert "ejercicios: omitidos" in captured
    assert "grupo(s) EJ/R" not in captured
    assert "prácticos descartados" not in captured


def test_process_week_default_scope_matches_ipl31_behavior_exactly():
    # Sin pasar scope, el comportamiento es idéntico a IPL-31 (default = "theory+practice").
    theory_doc = _doc("theory", "Nivelación Matemática - Semana 1.pdf")

    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[theory_doc]),
        patch(f"{_PATCH_ROOT}.segment", return_value=(_segment("theory"),)),
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=()),
        patch(f"{_PATCH_ROOT}.level1_candidates", return_value=()) as mock_practice,
        patch(f"{_PATCH_ROOT}.add_candidates", return_value=()),
    ):
        report = process_week("nivelacion-matematica", 1)

    mock_practice.assert_called_once()
    assert report.scope == "theory+practice"
    assert report.practice_requested is True


def test_process_week_all_five_statuses_propagate_scope():
    with patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS):
        assert process_week("algebra-lineal", 1, scope="theory").scope == "theory"

    with patch(f"{_PATCH_ROOT}.check_connection", return_value=_DOWN_STATUS):
        assert process_week("nivelacion-matematica", 1, scope="theory").scope == "theory"

    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[]),
    ):
        assert process_week("nivelacion-matematica", 1, scope="theory").scope == "theory"

    theory_doc = _doc("theory", "Nivelación Matemática - Semana 1.pdf")
    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[theory_doc]),
        patch(f"{_PATCH_ROOT}.segment", return_value=(_segment("theory"),)),
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=(_theory_candidate(1),)),
        patch(f"{_PATCH_ROOT}.add_candidates", side_effect=AnkiConnectError("boom")),
    ):
        report = process_week("nivelacion-matematica", 1, scope="theory")
        assert report.status == "error-insercion"
        assert report.scope == "theory"

    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.discover_week", return_value=[theory_doc]),
        patch(f"{_PATCH_ROOT}.segment", return_value=(_segment("theory"),)),
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=(_theory_candidate(1),)),
        patch(f"{_PATCH_ROOT}.add_candidates", return_value=(_theory_candidate(1),)),
    ):
        report = process_week("nivelacion-matematica", 1, scope="theory")
        assert report.status == "ok"
        assert report.scope == "theory"


# ─────────────────────────────────────────────────────────────────────────
# Material real — solo las capas sin LLM ni Anki (CLAUDE.md: skip accionable)
# ─────────────────────────────────────────────────────────────────────────


@_requires_material
def test_real_material_mate_s1_two_groups_forty_pairs_total():
    documents = discover_week("nivelacion-matematica", 1)
    groups = group_exercise_documents(documents)

    assert len(groups) == 2

    total_pairs = 0
    for group in groups:
        statements = extract_exercise_statements(group.exercises.path)
        answers = parse_answer_key(group.answer_key.pages)
        pairs = pair_exercises(statements, answers, group.exercises.path.name)
        total_pairs += len(pairs)

    assert total_pairs == 40


@_requires_material
def test_real_material_soporte_s1_pairing_failure_does_not_abort_week():
    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.segment", return_value=()),
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=()),
        patch(f"{_PATCH_ROOT}.level1_candidates", return_value=()),
        patch(f"{_PATCH_ROOT}.add_candidates", return_value=()),
    ):
        report = process_week("soporte-sw-hw", 1)

    assert report.status == "ok"
    assert report.pairing_failures == 1
    assert report.exercise_groups == 1


@_requires_material
def test_real_material_soporte_s1_theory_scope_has_no_pairing_failure(capsys):
    # Motivación de IPL-32: con scope="theory" nunca se intenta el pareo, así que el
    # desacuerdo real de conteo (5 vs 10) de Soporte S1 nunca se dispara — contraste directo
    # con el test de arriba (scope por default -> pairing_failures==1).
    with (
        patch(f"{_PATCH_ROOT}.check_connection", return_value=_OK_STATUS),
        patch(f"{_PATCH_ROOT}.segment", return_value=()),
        patch(f"{_PATCH_ROOT}.theory_candidates", return_value=()),
        patch(f"{_PATCH_ROOT}.add_candidates", return_value=()),
    ):
        report = process_week("soporte-sw-hw", 1, scope="theory")

    assert report.status == "ok"
    assert report.pairing_failures == 0
    assert report.exercise_groups == 0
    captured = capsys.readouterr().out
    assert "conteo desparejo" not in captured
    assert "enunciados vs" not in captured
