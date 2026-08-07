"""Clasificación de contenido fuente — modelo ligero (TDD §4.2).

Segmentación SEMÁNTICA vía LLM, no por regex: la convención de marcado de aprendizajes
esperados no es consistente entre documentos (AE1: en algunos, nada en otros — ver
SPEC-1-IT2-ingest-classify.yaml, inputs.external_behaviors).
"""

from __future__ import annotations

import asyncio
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from flashcards_agent import output
from flashcards_agent.models.content import ContentSegment, SourceDocument

_MODEL = "haiku"

# Página de contenido con poco texto: probable portada/contratapa (descartable) o,
# si además trae imágenes, posible figura con contenido perdido (avisar, no procesar —
# parking lot TDD §4.4/§1.4, OQ-01 resuelta 2026-08-07).
_MIN_CONTENT_CHARS = 100
_FIGURE_HEAVY_CHARS = 300

_SYSTEM_PROMPT = (
    "Sos un clasificador de contenido educativo para un curso de IPLACEX "
    "(Ingeniería en Ciberseguridad). Recibís el texto de un documento de material de "
    "estudio, ya extraído y marcado con '[p. N]' antes de cada página. Segmentalo por "
    "aprendizaje esperado o subsección temática — la convención de marcado NO es "
    "consistente entre documentos, así que usá tu criterio semántico, no busques un "
    "patrón fijo. Para cada segmento asigná:\n"
    "- topic_tag: tema corto en minúsculas y sin espacios (ej. 'mcm', 'software-sistema')\n"
    "- flavor: 'theory' (contenido conceptual), 'practice' (patrón de ejercicio práctico), "
    "o 'discard' (actividades hands-on de instalación/capturas de pantalla, o "
    "autoevaluación tipo Likert — esas nunca son preguntables como flashcard)\n"
    "- page: el número de página [p. N] donde arranca el segmento"
)

_SEGMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "topic_tag": {"type": "string"},
                    "flavor": {"type": "string", "enum": ["theory", "practice", "discard"]},
                    "page": {"type": "integer"},
                },
                "required": ["title", "body", "topic_tag", "flavor", "page"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["segments"],
    "additionalProperties": False,
}


def _content_prompt(doc: SourceDocument) -> str:
    parts: list[str] = []
    for page in doc.pages:
        stripped = page.text.strip()
        if len(stripped) < _MIN_CONTENT_CHARS:
            continue  # portada/contratapa u otra página sin contenido sustantivo
        if page.image_count > 0 and len(stripped) < _FIGURE_HEAVY_CHARS:
            output.warn(
                f"{doc.path.name}, p. {page.number}: poco texto + {page.image_count} "
                "imagen(es) — posible contenido perdido (parking lot TDD §4.4)"
            )
        parts.append(f"[p. {page.number}]\n{page.text}")
    return "\n\n".join(parts)


async def _segment_async(doc: SourceDocument) -> tuple[ContentSegment, ...]:
    options = ClaudeAgentOptions(
        model=_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        output_format={"type": "json_schema", "schema": _SEGMENT_SCHEMA},
        tools=[],
        max_turns=1,
    )

    structured: dict[str, Any] | None = None
    async for message in query(prompt=_content_prompt(doc), options=options):
        if isinstance(message, ResultMessage):
            structured = message.structured_output

    if structured is None:
        raise RuntimeError(f"segment(): sin structured_output para {doc.path.name}")

    return tuple(
        ContentSegment(
            title=item["title"],
            body=item["body"],
            topic_tag=item["topic_tag"],
            flavor=item["flavor"],
            source_ref=f"{doc.path.name}, p. {item['page']}",
        )
        for item in structured["segments"]
    )


def segment(doc: SourceDocument) -> tuple[ContentSegment, ...]:
    return asyncio.run(_segment_async(doc))
