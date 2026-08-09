"""Gramática de comandos del CLI (TDD §4.3, US-8) — dispatch determinístico, CERO LLM.

v1 fija solo "procesar", "salir" y "ayuda" (TDD §4.3, nota 2026-08-09, IPL-31); "listar" y
"consultar estado" quedan diferidos. Un input que no matchea la gramática NUNCA dispara una
llamada al modelo en esta card — el fallback a lenguaje natural es US-9.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from flashcards_agent.models.card import (
    known_subject_names,
    normalize_subject_name,
    subject_slug_from_name,
)

_PROCESS_RE = re.compile(
    r"^procesar\s+(?P<subject>.+?)\s*(?:,\s*)?semana\s+(?P<week>\S+)\s*$",
    re.IGNORECASE,
)
# La coma es OPCIONAL (el Gherkin de US-8 usa "Nivelación Matemática, Semana 2"; sin coma no
# debería fallar). `week` se captura como \S+, NO \d+, a propósito: así "procesar mate, semana
# dos" matchea la FORMA del comando y produce un error específico sobre la semana, en vez de
# caer en el genérico "comando no reconocido".

_EXIT_WORDS = frozenset({"salir", "exit", "quit"})
_HELP_WORDS = frozenset({"ayuda", "help", "?"})

HELP_TEXT = (
    "Comandos disponibles:\n"
    "  procesar <materia>, semana <N>  — genera e inserta flashcards para esa semana (pregunta el alcance)\n"
    "  ayuda                            — muestra este mensaje\n"
    "  salir                            — termina el programa\n"
    f"Materias conocidas: {', '.join(known_subject_names())}"
)


@dataclass(frozen=True)
class ProcessCommand:
    subject_slug: str
    week: int


@dataclass(frozen=True)
class ExitCommand:
    pass


@dataclass(frozen=True)
class HelpCommand:
    pass


@dataclass(frozen=True)
class UnknownCommand:
    reason: str


Command = ProcessCommand | ExitCommand | HelpCommand | UnknownCommand


def parse_command(raw: str) -> Command | None:
    stripped = raw.strip()
    if not stripped:
        return None

    folded = stripped.casefold()
    if folded in _EXIT_WORDS:
        return ExitCommand()
    if folded in _HELP_WORDS:
        return HelpCommand()

    match = _PROCESS_RE.match(stripped)
    if match is None:
        return UnknownCommand(f"comando no reconocido: '{stripped}'.\n{HELP_TEXT}")

    subject_raw = match.group("subject")
    week_raw = match.group("week")

    if not week_raw.isdigit() or int(week_raw) <= 0:
        return UnknownCommand(f"la semana debe ser un número entero positivo: '{week_raw}'")

    subject_slug = subject_slug_from_name(subject_raw)
    if subject_slug is None:
        return UnknownCommand(
            f"materia no reconocida: '{subject_raw}'. Conocidas: {', '.join(known_subject_names())}"
        )

    return ProcessCommand(subject_slug=subject_slug, week=int(week_raw))


# ─────────────────────────────────────────────────────────────────────────
# Sub-prompt de alcance (IPL-32) — se pregunta después de un ProcessCommand válido, antes
# de invocar process_week(). Mismo principio: micro-gramática determinística, cero LLM,
# cero SDK, cero I/O — este módulo sigue testeándose puro, sin mocks. La pregunta interactiva
# en sí (input()) vive en cli/loop.py, no acá.
# ─────────────────────────────────────────────────────────────────────────

RunScope = Literal["theory", "theory+practice"]
# Vive acá y NO en cli/pipeline.py: pipeline.py importa toda la cadena pesada (anki.client,
# generate/*, ingest/*) — si el Literal viviera ahí, este módulo tendría que importarla para
# tiparse, perdiendo su propiedad de módulo liviano testeable sin mocks. La dependencia queda
# unidireccional: pipeline -> commands (commands NO importa pipeline).

_THEORY_ONLY_ANSWERS: frozenset[str] = frozenset(
    {"1", "t", "teoria", "teorica", "solo teoria", "solo teorica", "solo la teoria"}
)
_THEORY_AND_PRACTICE_ANSWERS: frozenset[str] = frozenset(
    {
        "2",
        "e",
        "p",
        "ejercicios",
        "practica",
        "practicas",
        "practicos",
        "ejercicios practicos",
        "teoria y ejercicios",
        "teoria + ejercicios",
        "teoria+ejercicios",
        "ambos",
        "ambas",
        "todo",
    }
)
# Sets escritos YA NORMALIZADOS (sin tildes, minúsculas, "-"/"_" -> espacio, espacios
# colapsados) — normalize_subject_name() normaliza igual, así que la comparación calza.

SCOPE_QUESTION = (
    "¿Qué generamos en esta corrida? 'teoria' = solo cards teóricas (V/F) desde el material; "
    "'ejercicios' = teoría + ejercicios prácticos (pareo EJ_/R_ del material)."
)

SCOPE_HELP_TEXT = (
    "Respuesta no reconocida. Opciones: 'teoria' (solo teoría) o 'ejercicios' "
    "(teoría + ejercicios prácticos)."
)


def parse_run_scope(raw: str) -> RunScope | None:
    normalized = normalize_subject_name(raw)
    if not normalized:
        return None
    if normalized in _THEORY_ONLY_ANSWERS:
        return "theory"
    if normalized in _THEORY_AND_PRACTICE_ANSWERS:
        return "theory+practice"
    return None


def describe_scope(scope: RunScope) -> str:
    return "solo teoría" if scope == "theory" else "teoría + ejercicios prácticos"
