"""Entry point del CLI — loop persistente (TDD §4.3, US-8).

Python puro: el Claude Agent SDK no provee ninguna primitiva de REPL/loop interactivo
(verificado 2026-08-09 contra code.claude.com/docs/en/agent-sdk/python), y el dispatch
determinístico de esta card no pasa por el modelo por definición del Gherkin de US-8. El
fallback a lenguaje natural (US-9) todavía no existe — un input no reconocido termina en
output.err, nunca en una llamada al SDK.
"""

from __future__ import annotations

from flashcards_agent import output
from flashcards_agent.cli.commands import (
    HELP_TEXT,
    Command,
    ExitCommand,
    HelpCommand,
    ProcessCommand,
    UnknownCommand,
    parse_command,
)
from flashcards_agent.cli.pipeline import process_week

_PROMPT = "flashcards> "


def dispatch(command: Command) -> bool:
    """Ejecuta un comando. True: seguir el loop. False: terminar.

    Aislada de main() a propósito: es el punto exacto que US-9 volverá async
    (ClaudeSDKClient para el fallback NL + asyncio.to_thread sobre process_week).
    """
    match command:
        case ExitCommand():
            output.info("Hasta luego.")
            return False
        case HelpCommand():
            output.info(HELP_TEXT)
            return True
        case ProcessCommand(subject_slug=subject_slug, week=week):
            process_week(subject_slug, week)
            return True
        case UnknownCommand(reason=reason):
            output.err(reason)
            return True


def main() -> None:
    output.info(HELP_TEXT)
    while True:
        try:
            raw = input(_PROMPT)
        except (EOFError, KeyboardInterrupt):
            output.info("Hasta luego.")
            return

        command = parse_command(raw)
        if command is None:
            continue

        try:
            if not dispatch(command):
                return
        except Exception as exc:  # noqa: BLE001 — única captura ancha del código base, justificada
            # No es `except Exception: pass` (CLAUDE.md la prohíbe): reporta tipo y mensaje.
            # Un REPL no puede morir por el fallo de un comando puntual.
            output.err(f"error inesperado procesando el comando: {type(exc).__name__}: {exc}")
