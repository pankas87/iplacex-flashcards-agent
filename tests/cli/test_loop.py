"""cli/loop.py — input() monkeypatcheado, process_week mockeada. Ningún test puede quedar
bloqueado esperando stdin real: toda secuencia termina en 'salir' o en EOFError.
"""

from unittest.mock import patch

from flashcards_agent.cli.loop import ask_run_scope, main


def _inputs(*lines):
    return patch("builtins.input", side_effect=list(lines))


def test_main_dispatches_known_command_then_exits():
    with (
        _inputs("procesar Nivelación Matemática, Semana 2", "ejercicios", "salir"),
        patch("flashcards_agent.cli.loop.process_week") as mock_process,
    ):
        main()

    mock_process.assert_called_once_with("nivelacion-matematica", 2, scope="theory+practice")


def test_main_natural_language_input_never_calls_process_week(capsys):
    with (
        _inputs("generame flashcards de mate para la semana que viene", "salir"),
        patch("flashcards_agent.cli.loop.process_week") as mock_process,
    ):
        main()

    mock_process.assert_not_called()
    captured = capsys.readouterr()
    assert "[error]" in captured.out
    assert "comando no reconocido" in captured.out


def test_main_returns_cleanly_on_eof(capsys):
    with (
        patch("builtins.input", side_effect=EOFError),
        patch("flashcards_agent.cli.loop.process_week") as mock_process,
    ):
        main()

    mock_process.assert_not_called()
    assert "Hasta luego." in capsys.readouterr().out


def test_main_reports_unexpected_exception_and_keeps_looping(capsys):
    with (
        _inputs("procesar Nivelación Matemática, Semana 2", "ejercicios", "salir"),
        patch(
            "flashcards_agent.cli.loop.process_week",
            side_effect=RuntimeError("fallo inesperado"),
        ) as mock_process,
    ):
        main()

    assert mock_process.call_count == 1
    captured = capsys.readouterr()
    assert "error inesperado procesando el comando" in captured.out
    assert "RuntimeError" in captured.out
    assert "fallo inesperado" in captured.out
    assert "Hasta luego." in captured.out  # el loop siguió y llegó a 'salir'


def test_main_empty_input_reprompts_without_side_effects():
    with (
        _inputs("", "   ", "salir"),
        patch("flashcards_agent.cli.loop.process_week") as mock_process,
    ):
        main()

    mock_process.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────
# ask_run_scope() — IPL-32
# ─────────────────────────────────────────────────────────────────────────


def test_ask_run_scope_accepts_theory_on_first_answer():
    with _inputs("teoria"):
        assert ask_run_scope() == "theory"


def test_ask_run_scope_accepts_practice_on_first_answer():
    with _inputs("ejercicios"):
        assert ask_run_scope() == "theory+practice"


def test_ask_run_scope_reprompts_once_on_invalid_answer(capsys):
    with _inputs("qué?", "ejercicios"):
        result = ask_run_scope()

    assert result == "theory+practice"
    captured = capsys.readouterr()
    assert captured.out.count("[error]") == 1
    assert "Opciones:" in captured.out


def test_ask_run_scope_falls_back_to_theory_after_max_attempts(capsys):
    with patch("builtins.input", side_effect=["a", "b", "c"]) as mock_input:
        result = ask_run_scope()

    assert result == "theory"
    assert mock_input.call_count == 3
    captured = capsys.readouterr()
    assert "se asume 'solo teoría'" in captured.out


def test_ask_run_scope_empty_lines_count_as_attempts():
    with patch("builtins.input", side_effect=["", "", ""]) as mock_input:
        result = ask_run_scope()

    assert result == "theory"
    assert mock_input.call_count == 3


def test_ask_run_scope_returns_none_on_eof():
    with patch("builtins.input", side_effect=EOFError):
        assert ask_run_scope() is None


def test_ask_run_scope_returns_none_on_keyboard_interrupt():
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        assert ask_run_scope() is None


def test_main_asks_scope_for_any_known_subject_not_just_soporte(capsys):
    with (
        _inputs("procesar mate, semana 3", "teoria", "salir"),
        patch("flashcards_agent.cli.loop.process_week") as mock_process,
    ):
        main()

    assert "¿Qué generamos en esta corrida?" in capsys.readouterr().out
    mock_process.assert_called_once_with("nivelacion-matematica", 3, scope="theory")


def test_main_does_not_ask_scope_for_help_or_natural_language(capsys):
    with (
        _inputs("ayuda", "salir"),
        patch("flashcards_agent.cli.loop.process_week") as mock_process,
    ):
        main()

    assert "¿Qué generamos en esta corrida?" not in capsys.readouterr().out
    mock_process.assert_not_called()


def test_main_eof_during_scope_question_exits_cleanly_without_error_report(capsys):
    with (
        patch("builtins.input", side_effect=["procesar Nivelación Matemática, Semana 2", EOFError]),
        patch("flashcards_agent.cli.loop.process_week") as mock_process,
    ):
        main()

    mock_process.assert_not_called()
    captured = capsys.readouterr()
    assert "Hasta luego." in captured.out
    assert "error inesperado" not in captured.out


def test_main_keyboard_interrupt_during_scope_question_exits_cleanly():
    with (
        patch(
            "builtins.input",
            side_effect=["procesar Nivelación Matemática, Semana 2", KeyboardInterrupt],
        ),
        patch("flashcards_agent.cli.loop.process_week") as mock_process,
    ):
        main()

    mock_process.assert_not_called()
