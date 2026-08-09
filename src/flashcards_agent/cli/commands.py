"""Gramática de comandos del CLI (TDD §4.3, US-8) — dispatch determinístico, CERO LLM.

v1 fija solo "procesar", "salir" y "ayuda" (TDD §4.3, nota 2026-08-09, IPL-31); "listar" y
"consultar estado" quedan diferidos. Un input que no matchea la gramática NUNCA dispara una
llamada al modelo en esta card — el fallback a lenguaje natural es US-9.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from flashcards_agent.models.card import known_subject_names, subject_slug_from_name

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
    "  procesar <materia>, semana <N>  — genera e inserta flashcards para esa semana\n"
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
