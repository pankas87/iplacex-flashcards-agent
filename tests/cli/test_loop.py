"""cli/loop.py — input() monkeypatcheado, process_week mockeada. Ningún test puede quedar
bloqueado esperando stdin real: toda secuencia termina en 'salir' o en EOFError.
"""

from unittest.mock import patch

from flashcards_agent.cli.loop import main


def _inputs(*lines):
    return patch("builtins.input", side_effect=list(lines))


def test_main_dispatches_known_command_then_exits():
    with (
        _inputs("procesar Nivelación Matemática, Semana 2", "salir"),
        patch("flashcards_agent.cli.loop.process_week") as mock_process,
    ):
        main()

    mock_process.assert_called_once_with("nivelacion-matematica", 2)


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
        _inputs("procesar Nivelación Matemática, Semana 2", "salir"),
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
