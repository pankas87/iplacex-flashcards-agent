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
    SCOPE_HELP_TEXT,
    SCOPE_QUESTION,
    Command,
    ExitCommand,
    HelpCommand,
    ProcessCommand,
    RunScope,
    UnknownCommand,
    parse_command,
    parse_run_scope,
)
from flashcards_agent.cli.pipeline import process_week

_PROMPT = "flashcards> "
_SCOPE_PROMPT = "alcance [teoria/ejercicios]: "
_SCOPE_MAX_ATTEMPTS = 3
_SCOPE_FALLBACK: RunScope = "theory"


def ask_run_scope() -> RunScope | None:
    """Pregunta interactiva y determinística de alcance (IPL-32) — sin pasar por el modelo,
    mismo principio que el dispatch de US-8. None significa "el estudiante cortó la sesión"
    (EOFError/KeyboardInterrupt), NUNCA se deja propagar: EOFError es subclase de Exception y
    la captura ancha de main() la reportaría como "error inesperado" con el loop siguiendo —
    justo lo contrario de lo que pedir Ctrl-D/Ctrl-C significa.
    """
    output.info(SCOPE_QUESTION)
    for _ in range(_SCOPE_MAX_ATTEMPTS):
        try:
            raw = input(_SCOPE_PROMPT)
        except (EOFError, KeyboardInterrupt):
            return None

        scope = parse_run_scope(raw)
        if scope is not None:
            return scope
        output.err(SCOPE_HELP_TEXT)

    output.warn(
        f"no se reconoció una respuesta válida tras {_SCOPE_MAX_ATTEMPTS} intentos — "
        "se asume 'solo teoría'. Corré 'procesar' de nuevo y respondé 'ejercicios' si "
        "querías teoría + ejercicios prácticos."
    )
    return _SCOPE_FALLBACK


def dispatch(command: Command) -> bool:
    """Ejecuta un comando. True: seguir el loop. False: terminar.

    Ya NO es pura para ProcessCommand (IPL-32): lee stdin vía ask_run_scope() antes de
    invocar process_week(). Sigue siendo el punto exacto que US-9 volverá async
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
            scope = ask_run_scope()
            if scope is None:
                output.info("Hasta luego.")
                return False
            process_week(subject_slug, week, scope=scope)
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
