"""classify/segmenter.py — mockea el SDK, no llama al LLM real en cada corrida de tests.

El fixture es la salida REAL y completa de una llamada real al SDK (verificación de
output_format/structured_output hecha durante la implementación de SPEC-1-IT2, 2026-08-07,
contra un prompt corto con un fragmento teórico + una actividad hands-on) — no fabricado
(CLAUDE.md: "golden files, siempre reales — nunca fabricados para que el test pase").
"""

from pathlib import Path
from unittest.mock import patch

from claude_agent_sdk import ResultMessage

from flashcards_agent.classify.segmenter import segment
from flashcards_agent.models.content import PageText, SourceDocument

_REAL_STRUCTURED_OUTPUT = {
    "segments": [
        {
            "title": "Definición: Mínimo Común Múltiplo",
            "body": "El mínimo común múltiplo (m.c.m) de dos números es el menor número que es múltiplo de ambos.",
            "topic_tag": "mcm_basicos",
            "flavor": "theory",
            "page": 1,
        },
        {
            "title": "Actividad práctica: Captura de pantalla",
            "body": "Instale el software indicado y tome una captura de pantalla del resultado.",
            "topic_tag": "hands_on_installation",
            "flavor": "discard",
            "page": 2,
        },
    ]
}


async def _fake_query(*, prompt, options):
    yield ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="test",
        structured_output=_REAL_STRUCTURED_OUTPUT,
    )


@patch("flashcards_agent.classify.segmenter.query", new=_fake_query)
def test_segment_maps_structured_output_to_content_segments():
    doc = SourceDocument(
        path=Path("fixture.pdf"),
        kind="theory",
        subject_slug="nivelacion-matematica",
        week=1,
        pages=(
            PageText(number=1, text="x" * 200, image_count=0),
            PageText(number=2, text="x" * 200, image_count=0),
        ),
    )

    segments = segment(doc)

    assert len(segments) == 2
    assert segments[0].flavor == "theory"
    assert segments[0].topic_tag == "mcm_basicos"
    assert segments[0].source_ref == "fixture.pdf, p. 1"
    assert segments[1].flavor == "discard"
    assert segments[1].source_ref == "fixture.pdf, p. 2"


@patch("flashcards_agent.classify.segmenter.query", new=_fake_query)
def test_segment_warns_on_figure_heavy_borderline_page(capsys):
    # p.1: portada, muy poco texto -> se descarta en silencio (conocida decorativa, ADR-0003).
    # p.2: texto intermedio + imagen -> caso borderline real (TDD §4.4 parking lot): se avisa
    # y se procesa igual, no se descarta.
    doc = SourceDocument(
        path=Path("fixture.pdf"),
        kind="theory",
        subject_slug="nivelacion-matematica",
        week=1,
        pages=(
            PageText(number=1, text="portada", image_count=1),
            PageText(number=2, text="x" * 150, image_count=1),
        ),
    )

    segment(doc)

    captured = capsys.readouterr()
    assert "poco texto" in captured.out
    assert "p. 2" in captured.out
    assert "p. 1" not in captured.out
