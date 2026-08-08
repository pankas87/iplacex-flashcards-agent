"""Sub-pipeline práctico, nivel 1 — ejercicios del material propio (TDD §4.5.2, ADR-0003).

translate_exercise() sigue el mismo mecanismo que classify/segmenter.py (output_format con
JSON schema, ya verificado contra la interfaz real del SDK en IPL-26), con modelo Sonnet en
vez de Haiku: acá la calidad exigida es la de traducir un enunciado a operaciones exactas sin
inventar un plan dudoso, no una segmentación semántica gruesa (TDD §4.2).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from flashcards_agent import output
from flashcards_agent.models.card import PracticeCardCandidate
from flashcards_agent.models.content import ExercisePair
from flashcards_agent.verify.answer_matching import matches
from flashcards_agent.verify.executor import UnsupportedOperation, execute_plan
from flashcards_agent.verify.plan import ComputePlan, ComputeStep, StepRef

_MODEL = "sonnet"

# Mapeo slug de carpeta -> nombre de materia (TDD §4.4, mapeo pendiente hasta que una card lo
# necesitara — ésta es la primera).
_DECK_NAMES: dict[str, str] = {
    "nivelacion-matematica": "Nivelación Matemática",
    "soporte-sw-hw": "Soporte HW-SW",
}

_OPERATIONS = ("mcm", "mcd", "add", "subtract", "multiply", "divide")

_SYSTEM_PROMPT = (
    "Traducís enunciados de ejercicios matemáticos de Nivelación Matemática (IPLACEX) a un "
    "plan de cómputo exacto, ejecutable sin ambigüedad por un programa. El plan es una "
    "secuencia de pasos ('steps'); cada paso tiene:\n"
    "- operation: una de mcm, mcd, add, subtract, multiply, divide\n"
    "- operands: lista de operandos, cada uno un entero literal tomado del enunciado, o "
    "{\"step\": N} para referirse al resultado del paso N (0-indexed, pasos previos del "
    "mismo plan)\n"
    "subtract y divide toman exactamente 2 operandos, en el orden minuendo/sustraendo y "
    "dividendo/divisor. mcm y mcd solo aceptan operandos enteros.\n"
    "Si el enunciado no se puede traducir con exactitud a ese vocabulario — no es "
    "aritmético, requiere una operación fuera de esa lista, o los datos son ambiguos — "
    "marcá translatable=false y dejá steps como lista vacía. Nunca fuerces una traducción "
    "dudosa: es preferible declarar que no se puede traducir.\n"
    "topic_tag: tema corto en minúsculas y sin espacios (ej. 'mcm', 'mcd', 'operatoria'), "
    "vacío si translatable=false."
)

_TRANSLATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "translatable": {"type": "boolean"},
        "topic_tag": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": list(_OPERATIONS)},
                    "operands": {
                        "type": "array",
                        "items": {
                            "anyOf": [
                                {"type": "integer"},
                                {
                                    "type": "object",
                                    "properties": {"step": {"type": "integer"}},
                                    "required": ["step"],
                                    "additionalProperties": False,
                                },
                            ]
                        },
                    },
                },
                "required": ["operation", "operands"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["translatable", "topic_tag", "steps"],
    "additionalProperties": False,
}


def deck_name(subject_slug: str, week: int) -> str:
    return f"{_DECK_NAMES[subject_slug]}::Semana {week}"


@dataclass(frozen=True)
class ExerciseTranslation:
    plan: ComputePlan
    topic_tag: str


def _operand_from_json(raw: Any) -> int | StepRef:
    if isinstance(raw, dict):
        return StepRef(step=raw["step"])
    return raw


def _plan_from_json(steps: list[dict[str, Any]]) -> ComputePlan:
    return ComputePlan(
        steps=tuple(
            ComputeStep(
                operation=item["operation"],
                operands=tuple(_operand_from_json(op) for op in item["operands"]),
            )
            for item in steps
        )
    )


async def _translate_async(statement: str) -> ExerciseTranslation | None:
    options = ClaudeAgentOptions(
        model=_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        output_format={"type": "json_schema", "schema": _TRANSLATION_SCHEMA},
        tools=[],
        # A diferencia de Haiku en classify/segmenter.py, Sonnet a veces intercala un turno
        # de texto explicativo antes de llamar la tool de structured output (verificado
        # contra la interfaz real del SDK, IPL-28) — max_turns=1 corta esa respuesta a
        # mitad de camino y falla con "Reached maximum number of turns".
        max_turns=3,
    )

    structured: dict[str, Any] | None = None
    async for message in query(prompt=statement, options=options):
        if isinstance(message, ResultMessage):
            structured = message.structured_output

    if structured is None:
        raise RuntimeError(f"translate_exercise(): sin structured_output para {statement!r}")

    if not structured["translatable"]:
        return None

    return ExerciseTranslation(
        plan=_plan_from_json(structured["steps"]),
        topic_tag=structured["topic_tag"],
    )


def translate_exercise(statement: str) -> ExerciseTranslation | None:
    return asyncio.run(_translate_async(statement))


def level1_candidates(
    pairs: tuple[ExercisePair, ...],
    subject_slug: str,
    week: int,
    topic_tag_override: str | None = None,
) -> tuple[PracticeCardCandidate, ...]:
    deck = deck_name(subject_slug, week)
    candidates: list[PracticeCardCandidate] = []

    for pair in pairs:
        translation = translate_exercise(pair.statement)
        if translation is None:
            output.warn(f"{pair.source_ref}: no traducible")
            continue

        try:
            computed = execute_plan(translation.plan)
        except UnsupportedOperation:
            output.warn(f"{pair.source_ref}: no traducible")
            continue

        if pair.published_answer is None or not matches(computed, pair.published_answer):
            output.warn(f"{pair.source_ref}: cómputo no coincide con la clave — descartado")
            continue

        tag = topic_tag_override if topic_tag_override is not None else translation.topic_tag
        candidates.append(
            PracticeCardCandidate(
                front=pair.statement,
                back=str(computed),
                deck=deck,
                tags=(tag, "verificado"),
                fuente=pair.source_ref,
            )
        )

    return tuple(candidates)
