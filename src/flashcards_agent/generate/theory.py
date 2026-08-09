"""Sub-pipeline teórico (TDD §4.5.1, §4.6, US-5/US-6). Materia-agnóstico por diseño: opera
sobre cualquier ContentSegment con flavor="theory", venga de Soporte SW-HW o de Nivelación
Matemática (TDD §5.1, nota resuelta 2026-08-08).

Mismo mecanismo de llamada al SDK que classify/segmenter.py y generate/practice.py
(output_format con JSON schema, ya verificado contra la interfaz real del SDK en IPL-26/28).
Modelo sonnet (TDD §4.2: generación de contenido pedagógico).

El grounding NO se confía al LLM: el modelo debe citar un fragmento verbatim del pasaje
(evidence_quote) que sostiene el valor de verdad; verify.grounding.check_grounding() confirma
de forma independiente que esa cita existe realmente en el body — paralelo textual exacto de
cómo verify.answer_matching recomputa la respuesta matemática (ADR-0003).

5-8 cards por nivel es un PISO de referencia, no un techo (TDD §4.5.1, revisión 2026-08-09,
IPL-30): si el pasaje da para más afirmaciones falsables y verificables, se generan y se
conservan todas — el único límite es _SAFETY_CEILING, una cota técnica alta (costo/latencia),
no un objetivo pedagógico. Nunca se trunca contenido grounded por cantidad.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from flashcards_agent import output
from flashcards_agent.models.card import TheoryCardCandidate, deck_name
from flashcards_agent.models.content import ContentSegment
from flashcards_agent.verify.grounding import check_grounding, normalize_for_grounding

_MODEL = "sonnet"
_LEVELS: tuple[int, int, int] = (1, 2, 3)
# Piso de referencia (TDD §4.5.1) — no un techo. _SAFETY_CEILING es una cota puramente técnica
# (costo/latencia de la llamada, tamaño de la respuesta) para evitar generación sin límite si
# el modelo interpreta mal el prompt; NO es un objetivo pedagógico ni se trunca contenido
# grounded para llegar a él en el uso normal.
_MIN_PER_LEVEL = 5
_SAFETY_CEILING = 25
_VF_PREFIX = "¿Verdadero o falso? "

# Mismo umbral que verify.grounding._MIN_EVIDENCE_CHARS: si el pasaje entero es más corto que
# eso, ninguna cita podría verificar nunca — se salta el segmento antes de gastar 3 llamadas.
_MIN_BODY_CHARS = 30

_LEVEL_INSTRUCTIONS: dict[int, str] = {
    1: (
        "Nivel 1 — reconocimiento literal: la afirmación se decide leyendo UNA sola oración "
        "del pasaje (una definición, un nombre, una clasificación directa)."
    ),
    2: (
        "Nivel 2 — comprensión: la afirmación exige relacionar dos partes del pasaje, o "
        "distinguir un concepto de otro cercano que el propio pasaje define (alcance de una "
        "definición, cuantificadores 'únicamente'/'siempre'/'nunca')."
    ),
    3: (
        "Nivel 3 — aplicación: la afirmación exige aplicar lo que dice el pasaje a un caso "
        "concreto, o detectar una generalización indebida. IGUAL debe poder decidirse leyendo "
        "el pasaje — nunca con conocimiento externo, porque entonces no habría evidencia que "
        "citar."
    ),
}

_SYSTEM_PROMPT = (
    "Sos un redactor de flashcards de Verdadero/Falso sobre material de estudio de IPLACEX "
    "(Ingeniería en Ciberseguridad), para cualquier materia (matemática o técnica). El único "
    "patrón de pregunta permitido es la afirmación falsable de Verdadero/Falso — no generes "
    "selección múltiple ni ningún otro formato.\n\n"
    "El valor de verdad de cada afirmación se determina EXCLUSIVAMENTE contrastando contra el "
    "pasaje entregado en el mensaje del usuario, nunca con conocimiento propio sobre el tema.\n\n"
    "Por cada afirmación devolvés:\n"
    "- statement: la afirmación falsable, sin ningún prefijo tipo '¿Verdadero o falso?'.\n"
    "- truth_value: true o false.\n"
    "- evidence_quote: un fragmento COPIADO CARÁCTER POR CARÁCTER del pasaje (sin elipsis, "
    "sin reescritura, sin corchetes editoriales) que es el que decide la verdad o falsedad de "
    "la afirmación. Para una afirmación falsa, es el fragmento que la contradice.\n"
    "- explanation: una sola oración explicando por qué el valor de verdad es ese.\n\n"
    "Las afirmaciones falsas se construyen alterando el ALCANCE de lo que dice el pasaje "
    "(agregar 'únicamente'/'siempre'/'nunca', o intercambiar dos conceptos que el propio "
    "pasaje define) — nunca inventando datos ausentes del pasaje, porque entonces no habría "
    "cita posible que la sostenga. Apuntá a un balance aproximado entre afirmaciones "
    "verdaderas y falsas.\n\n"
    "IMPORTANTE sobre la cantidad: no te limites a un número chico. Cubrí TODAS las "
    "afirmaciones falsables y verificables distintas que el pasaje permite sostener con una "
    "cita — cada definición, cada paso de un procedimiento, cada dato o ejemplo numérico, "
    "cada alcance o cuantificador. El mínimo es 5, pero si el pasaje tiene más contenido "
    "verificable que eso, generá más: es preferible sobre-generar que dejar afirmaciones "
    "verificables sin cubrir. No generes afirmaciones redundantes solo para llegar a un número "
    "— cada una debe cubrir un dato o relación distinta del pasaje.\n\n"
    "Escribí símbolos matemáticos y desigualdades en palabras (ej. 'menor que', no '<') — el "
    "destino renderiza HTML y ese carácter se pierde."
)

_STATEMENTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "statements": {
            "type": "array",
            "minItems": _MIN_PER_LEVEL,
            "maxItems": _SAFETY_CEILING,
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "truth_value": {"type": "boolean"},
                    "evidence_quote": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": ["statement", "truth_value", "evidence_quote", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["statements"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class TruthStatement:
    statement: str
    truth_value: bool
    evidence_quote: str
    explanation: str
    level: int


def _user_prompt(segment: ContentSegment, level: int) -> str:
    return (
        f"{_LEVEL_INSTRUCTIONS[level]}\n\n"
        f"Generá al menos {_MIN_PER_LEVEL} afirmaciones de Verdadero/Falso para este pasaje — "
        "y más si el pasaje da para cubrir más contenido verificable distinto (ver "
        "instrucción sobre la cantidad más arriba):\n\n"
        f"{segment.body}"
    )


async def _generate_statements_async(segment: ContentSegment, level: int) -> tuple[TruthStatement, ...]:
    prompt = _user_prompt(segment, level)
    options = ClaudeAgentOptions(
        model=_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        output_format={"type": "json_schema", "schema": _STATEMENTS_SCHEMA},
        tools=[],
        # A diferencia de Haiku en classify/segmenter.py, Sonnet a veces intercala un turno
        # de texto explicativo antes de llamar la tool de structured output (hallazgo real de
        # IPL-28, generate/practice.py) — max_turns=1 corta esa respuesta a mitad de camino.
        max_turns=3,
    )

    structured: dict[str, Any] | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            structured = message.structured_output

    if structured is None:
        raise RuntimeError(f"generate_statements(): sin structured_output para {segment.source_ref} nivel {level}")

    return tuple(
        TruthStatement(
            statement=item["statement"],
            truth_value=item["truth_value"],
            evidence_quote=item["evidence_quote"],
            explanation=item["explanation"],
            level=level,
        )
        for item in structured["statements"]
    )


def generate_statements(segment: ContentSegment, level: int) -> tuple[TruthStatement, ...]:
    return asyncio.run(_generate_statements_async(segment, level))


def theory_candidates(
    segments: tuple[ContentSegment, ...], subject_slug: str, week: int
) -> tuple[TheoryCardCandidate, ...]:
    deck = deck_name(subject_slug, week)
    candidates: list[TheoryCardCandidate] = []

    for segment in segments:
        if segment.flavor != "theory":
            continue

        if len(normalize_for_grounding(segment.body)) < _MIN_BODY_CHARS:
            output.warn(f"{segment.source_ref}: pasaje demasiado corto para citar evidencia — segmento saltado")
            continue

        seen_statements: set[str] = set()

        for level in _LEVELS:
            try:
                statements = generate_statements(segment, level)
            except RuntimeError as exc:
                output.warn(f"{segment.source_ref} (nivel {level}): {exc}")
                continue

            level_candidates: list[TheoryCardCandidate] = []
            for stmt in statements:
                result = check_grounding(stmt.statement, stmt.truth_value, stmt.evidence_quote, segment.body)
                if not result.grounded:
                    output.warn(f"{segment.source_ref} (nivel {level}): {result.reason} — descartada")
                    continue

                normalized_statement = normalize_for_grounding(stmt.statement)
                if normalized_statement in seen_statements:
                    output.warn(f"{segment.source_ref} (nivel {level}): afirmación duplicada — descartada")
                    continue
                seen_statements.add(normalized_statement)

                tags: tuple[str, ...] = (f"nivel-{level}", "verificado")
                if segment.topic_tag:
                    tags = (segment.topic_tag, *tags)
                else:
                    output.warn(f"{segment.source_ref} (nivel {level}): topic_tag vacío")

                level_candidates.append(
                    TheoryCardCandidate(
                        front=_VF_PREFIX + stmt.statement,
                        back="Verdadero" if stmt.truth_value else "Falso",
                        deck=deck,
                        tags=tags,
                        fuente=segment.source_ref,
                        level=level,
                    )
                )

            if len(level_candidates) < _MIN_PER_LEVEL:
                output.warn(
                    f"{segment.source_ref} (nivel {level}): solo {len(level_candidates)} "
                    f"candidatos sobrevivieron el grounding (mínimo esperado {_MIN_PER_LEVEL})"
                )

            if level_candidates and len({c.back for c in level_candidates}) == 1:
                output.warn(
                    f"{segment.source_ref} (nivel {level}): todas las afirmaciones "
                    f"sobrevivientes son '{level_candidates[0].back}' — nivel pedagógicamente "
                    "trivial, revisar en la pasada golden"
                )

            candidates.extend(level_candidates)

    return tuple(candidates)
