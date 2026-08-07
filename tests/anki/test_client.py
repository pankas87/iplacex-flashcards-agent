from unittest.mock import Mock, patch

import httpx

from flashcards_agent.anki.client import check_connection


def _mock_response(result, error=None):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"result": result, "error": error}
    return response


@patch("flashcards_agent.anki.client.httpx.post")
def test_check_connection_success_on_localhost(mock_post):
    mock_post.return_value = _mock_response(result=6)

    status = check_connection()

    assert status.ok is True
    assert status.version == 6
    mock_post.assert_called_once()


@patch("flashcards_agent.anki.client._resolve_host_ip", return_value="172.20.176.1")
@patch("flashcards_agent.anki.client.httpx.post")
def test_check_connection_falls_back_to_host_ip(mock_post, _mock_resolve):
    mock_post.side_effect = [
        httpx.ConnectError("connection refused"),
        _mock_response(result=6),
    ]

    status = check_connection()

    assert status.ok is True
    assert status.version == 6
    assert mock_post.call_count == 2
    fallback_url = mock_post.call_args_list[1].args[0]
    assert "172.20.176.1" in fallback_url


@patch("flashcards_agent.anki.client._resolve_host_ip", return_value="172.20.176.1")
@patch("flashcards_agent.anki.client.httpx.post")
def test_check_connection_fails_when_both_paths_fail(mock_post, _mock_resolve):
    mock_post.side_effect = httpx.ConnectError("connection refused")

    status = check_connection()

    assert status.ok is False
    assert status.version is None
    assert "172.20.176.1" in status.detail


@patch("flashcards_agent.anki.client.httpx.post")
def test_check_connection_reports_ankiconnect_error_without_traceback(mock_post):
    mock_post.return_value = _mock_response(result=None, error="unsupported version")

    status = check_connection(base_url="http://localhost:8765")

    assert status.ok is False
    assert status.version is None
    assert "unsupported version" in status.detail
