"""Verificación determinística de grounding textual, sin LLM (TDD §4.6, bullet
conceptual/V-F). Paralelo de verify/answer_matching.py: acá no hay cómputo posible sobre
lenguaje, así que lo que Python confirma de forma independiente es que la evidencia citada
por el generador EXISTE realmente en el pasaje fuente — no que el pasaje implique el valor de
verdad (eso queda para la revisión humana de golden cards, TDD/CLAUDE.md).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# Menos que esto no es una proposición, es una locución: no puede sostener un valor de verdad,
# y hace trivial el check de substring (cualquier fragmento corto matchea por casualidad).
# Calibrado con datos reales (IPL-30, 2026-08-09, ver OQ-A del spec): el piso original de 30
# descartaba evidencia numérica legítima y específica de un ejemplo real del material — ej.
# "2 × 2 × 3 × 3 × 3 × 5 = 540" (27 caracteres normalizados) es el resultado completo de un
# cálculo de m.c.m citado del pasaje, no una locución trivial.
_MIN_EVIDENCE_CHARS = 20
# Citar el pasaje entero es no citar nada — TDD §4.6 pide "el pasaje específico".
_MAX_EVIDENCE_CHARS = 400


def normalize_for_grounding(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(normalized.split())


@dataclass(frozen=True)
class GroundingResult:
    grounded: bool
    reason: str  # "" si grounded=True; si no, uno de los literales fijos de check_grounding()


def check_grounding(
    statement: str, truth_value: bool, evidence_quote: str, body: str
) -> GroundingResult:
    quote_norm = normalize_for_grounding(evidence_quote)
    body_norm = normalize_for_grounding(body)

    if not quote_norm:
        return GroundingResult(False, "evidencia vacía")
    if len(quote_norm) < _MIN_EVIDENCE_CHARS:
        return GroundingResult(False, "evidencia demasiado corta")
    if len(quote_norm) > _MAX_EVIDENCE_CHARS:
        return GroundingResult(False, "evidencia demasiado larga")
    if quote_norm not in body_norm:
        return GroundingResult(False, "la evidencia no aparece en el pasaje fuente")

    statement_norm = normalize_for_grounding(statement)
    if not truth_value and statement_norm in body_norm:
        return GroundingResult(False, "afirmación declarada falsa aparece textual en el pasaje")

    return GroundingResult(True, "")
