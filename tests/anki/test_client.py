from unittest.mock import Mock, patch

import httpx
import pytest

from flashcards_agent.anki.client import (
    AnkiConnectError,
    _request,
    add_candidates,
    check_connection,
    ensure_note_type,
)
from flashcards_agent.models.card import PracticeCardCandidate


def _mock_response(result, error=None):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"result": result, "error": error}
    return response


def _candidate(index: int = 1, deck: str = "Nivelación Matemática::Semana 1") -> PracticeCardCandidate:
    return PracticeCardCandidate(
        front=f"enunciado {index}",
        back=str(index),
        deck=deck,
        tags=("mcm", "verificado"),
        fuente=f"EJ_1.1.docx, ej. {index}",
    )


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


@patch("flashcards_agent.anki.client._resolve_host_ip", return_value="172.20.176.1")
@patch("flashcards_agent.anki.client.httpx.post")
def test_request_falls_back_to_host_ip_like_check_connection(mock_post, _mock_resolve):
    mock_post.side_effect = [
        httpx.ConnectError("connection refused"),
        _mock_response(result=["Basic"], error=None),
    ]

    result = _request("modelNames")

    assert result == ["Basic"]
    assert mock_post.call_count == 2


@patch("flashcards_agent.anki.client._resolve_host_ip", return_value=None)
@patch("flashcards_agent.anki.client.httpx.post")
def test_request_raises_ankiconnect_error_when_both_paths_fail(mock_post, _mock_resolve):
    mock_post.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(AnkiConnectError):
        _request("modelNames")


@patch("flashcards_agent.anki.client.httpx.post")
def test_request_raises_ankiconnect_error_on_api_error(mock_post):
    mock_post.return_value = _mock_response(result=None, error="model already exists")

    with pytest.raises(AnkiConnectError, match="model already exists"):
        _request("createModel", {}, base_url="http://localhost:8765")


@patch("flashcards_agent.anki.client._request")
def test_ensure_note_type_skips_create_when_model_exists(mock_request):
    mock_request.return_value = ["Basic", "Flashcards Agent"]

    ensure_note_type()

    mock_request.assert_called_once_with("modelNames", base_url=None)


@patch("flashcards_agent.anki.client._request")
def test_ensure_note_type_creates_model_when_missing(mock_request):
    mock_request.side_effect = [["Basic"], None]

    ensure_note_type()

    assert mock_request.call_count == 2
    create_call = mock_request.call_args_list[1]
    assert create_call.args[0] == "createModel"
    assert create_call.args[1] == {
        "modelName": "Flashcards Agent",
        "inOrderFields": ["Front", "Back", "Fuente"],
        "cardTemplates": [
            {
                "Name": "Card 1",
                "Front": "{{Front}}",
                "Back": "{{FrontSide}}<hr id=answer>{{Back}}<br><small>{{Fuente}}</small>",
            }
        ],
    }


@patch("flashcards_agent.anki.client._request")
def test_add_candidates_returns_empty_tuple_for_no_candidates(mock_request):
    result = add_candidates(())

    assert result == ()
    mock_request.assert_not_called()


@patch("flashcards_agent.anki.client._request")
def test_add_candidates_calls_can_add_notes_before_add_notes_and_returns_inserted(mock_request):
    candidate = _candidate()
    mock_request.side_effect = [
        ["Flashcards Agent"],  # modelNames
        [123456],  # createDeck
        [True],  # canAddNotes
        [111],  # addNotes
        [{"noteId": 111}],  # notesInfo
    ]

    result = add_candidates((candidate,))

    actions_called = [call.args[0] for call in mock_request.call_args_list]
    assert actions_called == ["modelNames", "createDeck", "canAddNotes", "addNotes", "notesInfo"]
    assert result == (candidate,)


@patch("flashcards_agent.anki.client._request")
def test_add_candidates_creates_deck_before_inserting(mock_request):
    candidate = _candidate()
    mock_request.side_effect = [
        ["Flashcards Agent"],
        [123456],
        [True],
        [111],
        [{"noteId": 111}],
    ]

    add_candidates((candidate,))

    create_deck_call = mock_request.call_args_list[1]
    assert create_deck_call.args[0] == "createDeck"
    assert create_deck_call.args[1] == {"deck": candidate.deck}


@patch("flashcards_agent.anki.client._request")
def test_add_candidates_creates_deck_once_per_distinct_deck(mock_request):
    same_deck_a = _candidate(index=1, deck="Nivelación Matemática::Semana 1")
    same_deck_b = _candidate(index=2, deck="Nivelación Matemática::Semana 1")
    mock_request.side_effect = [
        ["Flashcards Agent"],
        [123456],
        [True, True],
        [111, 222],
        [{"noteId": 111}, {"noteId": 222}],
    ]

    add_candidates((same_deck_a, same_deck_b))

    create_deck_calls = [call for call in mock_request.call_args_list if call.args[0] == "createDeck"]
    assert len(create_deck_calls) == 1


@patch("flashcards_agent.anki.client._request")
def test_add_candidates_note_payload_uses_deck_scoped_dedup(mock_request):
    candidate = _candidate()
    mock_request.side_effect = [
        ["Flashcards Agent"],
        [123456],
        [True],
        [111],
        [{"noteId": 111}],
    ]

    add_candidates((candidate,))

    can_add_call = mock_request.call_args_list[2]
    note = can_add_call.args[1]["notes"][0]
    assert note["deckName"] == candidate.deck
    assert note["fields"] == {"Front": candidate.front, "Back": candidate.back, "Fuente": candidate.fuente}
    assert note["tags"] == list(candidate.tags)
    assert note["options"] == {"allowDuplicate": False, "duplicateScope": "deck"}


@patch("flashcards_agent.anki.client._request")
def test_add_candidates_escapes_html_in_note_fields(mock_request):
    # OQ-C (IPL-30): los campos de Anki se renderizan como HTML — un "<" o "&" sin escapar
    # puede romper el layout o desaparecer. front/back/fuente se escapan en _note_payload.
    candidate = PracticeCardCandidate(
        front="El resultado es menor que 10 & mayor que 5",
        back="<b>no debería renderizar como negrita</b>",
        deck="Nivelación Matemática::Semana 1",
        tags=("mcm", "verificado"),
        fuente="EJ_1.1.docx, ej. 1",
    )
    mock_request.side_effect = [
        ["Flashcards Agent"],
        [123456],
        [True],
        [111],
        [{"noteId": 111}],
    ]

    add_candidates((candidate,))

    can_add_call = mock_request.call_args_list[2]
    note = can_add_call.args[1]["notes"][0]
    assert note["fields"]["Front"] == "El resultado es menor que 10 &amp; mayor que 5"
    assert note["fields"]["Back"] == "&lt;b&gt;no debería renderizar como negrita&lt;/b&gt;"
    assert "<" not in note["fields"]["Front"]
    assert "<" not in note["fields"]["Back"]


@patch("flashcards_agent.anki.client._request")
def test_add_candidates_skips_duplicate_and_warns(mock_request, capsys):
    candidate = _candidate()
    mock_request.side_effect = [
        ["Flashcards Agent"],  # modelNames
        [123456],  # createDeck
        [False],  # canAddNotes -> duplicada
    ]

    result = add_candidates((candidate,))

    assert result == ()
    actions_called = [call.args[0] for call in mock_request.call_args_list]
    assert actions_called == ["modelNames", "createDeck", "canAddNotes"]
    captured = capsys.readouterr()
    assert candidate.fuente in captured.out
    assert "duplicada" in captured.out


@patch("flashcards_agent.anki.client._request")
def test_add_candidates_warns_when_addnotes_rejects(mock_request, capsys):
    candidate = _candidate()
    mock_request.side_effect = [
        ["Flashcards Agent"],
        [123456],
        [True],
        [None],  # addNotes rechaza pese a canAddNotes=True
    ]

    result = add_candidates((candidate,))

    assert result == ()
    captured = capsys.readouterr()
    assert candidate.fuente in captured.out
    assert "rechazó" in captured.out


@patch("flashcards_agent.anki.client._request")
def test_add_candidates_excludes_candidate_on_notesinfo_mismatch(mock_request, capsys):
    candidate = _candidate()
    mock_request.side_effect = [
        ["Flashcards Agent"],
        [123456],
        [True],
        [111],
        [{"noteId": 999}],  # mismatch: no confirma el noteId esperado
    ]

    result = add_candidates((candidate,))

    assert result == ()
    captured = capsys.readouterr()
    assert candidate.fuente in captured.out
    assert "no verificable" in captured.out


@patch("flashcards_agent.anki.client._request")
def test_add_candidates_continues_after_one_duplicate(mock_request):
    duplicate = _candidate(index=1)
    fresh = _candidate(index=2)
    mock_request.side_effect = [
        ["Flashcards Agent"],  # modelNames
        [123456],  # createDeck
        [False, True],  # canAddNotes
        [222],  # addNotes — solo para "fresh"
        [{"noteId": 222}],  # notesInfo
    ]

    result = add_candidates((duplicate, fresh))

    assert result == (fresh,)
