"""cli/commands.py — puro, sin mocks: gramática determinística, cero LLM."""

from flashcards_agent.cli.commands import (
    ExitCommand,
    HelpCommand,
    ProcessCommand,
    UnknownCommand,
    parse_command,
)


def test_parse_command_matches_gherkin_wording():
    # Redacción literal del Gherkin de US-8 (TDD §5.2).
    assert parse_command("procesar Nivelación Matemática, Semana 2") == ProcessCommand(
        subject_slug="nivelacion-matematica", week=2
    )


def test_parse_command_tolerant_to_accents_case_and_missing_comma():
    variants = [
        "procesar nivelacion matematica, semana 2",
        "PROCESAR Nivelación Matemática semana 2",
        "procesar nivelacion-matematica, semana 2",
    ]
    expected = ProcessCommand(subject_slug="nivelacion-matematica", week=2)
    for variant in variants:
        assert parse_command(variant) == expected, variant


def test_parse_command_accepts_deck_name_and_short_alias_for_soporte():
    expected = ProcessCommand(subject_slug="soporte-sw-hw", week=1)
    assert parse_command("procesar Soporte SW-HW, semana 1") == expected
    assert parse_command("procesar soporte, semana 1") == expected


def test_parse_command_unknown_subject():
    result = parse_command("procesar Álgebra Lineal, semana 2")
    assert isinstance(result, UnknownCommand)
    assert "materia no reconocida" in result.reason
    assert "Nivelación Matemática" in result.reason
    assert "Soporte HW-SW" in result.reason


def test_parse_command_non_numeric_week_gives_specific_reason():
    result = parse_command("procesar mate, semana dos")
    assert isinstance(result, UnknownCommand)
    assert "la semana debe ser un número entero positivo" in result.reason
    assert "materia no reconocida" not in result.reason


def test_parse_command_week_zero_or_negative_is_invalid():
    for text in ("procesar mate, semana 0", "procesar mate, semana -1"):
        result = parse_command(text)
        assert isinstance(result, UnknownCommand), text
        assert "la semana debe ser un número entero positivo" in result.reason


def test_parse_command_exit_words_case_and_whitespace_insensitive():
    for text in ("salir", "exit", "quit", "SALIR ", " Exit"):
        assert parse_command(text) == ExitCommand(), text


def test_parse_command_help_words():
    for text in ("ayuda", "help", "?", "AYUDA"):
        assert parse_command(text) == HelpCommand(), text


def test_parse_command_empty_or_whitespace_returns_none():
    assert parse_command("") is None
    assert parse_command("   ") is None


def test_parse_command_natural_language_is_unknown_and_never_calls_the_model():
    # v1 no tiene fallback a NL (US-9): un input no reconocido nunca debe importar/llamar
    # nada del SDK. Este test lo asegura por construcción: cli/commands.py no importa
    # claude_agent_sdk en absoluto.
    import flashcards_agent.cli.commands as commands_module

    assert "claude_agent_sdk" not in commands_module.__dict__

    result = parse_command("generame flashcards de mate para la semana que viene")
    assert isinstance(result, UnknownCommand)
    assert "comando no reconocido" in result.reason
