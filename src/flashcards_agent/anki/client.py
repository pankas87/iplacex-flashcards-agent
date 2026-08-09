"""Cliente AnkiConnect — punto único de verdad para conectividad e inserción (TDD §4.1, §4.8).

Contrato de "version"/"modelNames"/"createModel"/"canAddNotes"/"addNotes"/"notesInfo"
verificado contra fuente primaria (git.foosoft.net/alex/anki-connect, agosto 2026):
request {"action": ..., "version": 6, "params": {...}}; response
{"result": <valor>, "error": null} en éxito, {"result": null, "error": "<msg>"} en error.
Puerto default 8765, webBindAddress default 127.0.0.1. duplicateScope acepta el string
"deck" (no "deckName") para acotar la detección de duplicados al mazo destino (TDD §4.8) —
cualquier otro valor cae a la colección completa.
"""

from __future__ import annotations

import html
import subprocess
from dataclasses import dataclass
from typing import Any

import httpx

from flashcards_agent import output
from flashcards_agent.models.card import CardCandidate

_DEFAULT_URL = "http://localhost:8765"
_TIMEOUT_SECONDS = 3.0

# Note type propio (ADR-0004) — el perfil real del desarrollador solo trae los note types
# stock de Anki, ninguno con un campo `Fuente`. El pipeline lo provisiona si falta.
_MODEL_NAME = "Flashcards Agent"
_MODEL_FIELDS = ("Front", "Back", "Fuente")
_MODEL_TEMPLATE = {
    "Name": "Card 1",
    "Front": "{{Front}}",
    "Back": "{{FrontSide}}<hr id=answer>{{Back}}<br><small>{{Fuente}}</small>",
}


@dataclass(frozen=True)
class AnkiConnectStatus:
    ok: bool
    version: int | None
    detail: str


class AnkiConnectError(Exception):
    """Fallo de conectividad o de la API de AnkiConnect en una acción de escritura."""


def _post(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(base_url, json=payload, timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _request_version(base_url: str) -> AnkiConnectStatus:
    payload = {"action": "version", "version": 6}
    try:
        body = _post(base_url, payload)
    except httpx.HTTPError as exc:
        return AnkiConnectStatus(ok=False, version=None, detail=f"no se pudo conectar a {base_url}: {exc}")

    error = body.get("error")
    if error is not None:
        return AnkiConnectStatus(ok=False, version=None, detail=f"AnkiConnect respondió con error: {error}")

    return AnkiConnectStatus(ok=True, version=body.get("result"), detail=f"AnkiConnect vivo en {base_url}")


def _resolve_host_ip() -> str | None:
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    parts = result.stdout.split()
    if "via" in parts:
        return parts[parts.index("via") + 1]
    return None


def check_connection(base_url: str | None = None) -> AnkiConnectStatus:
    """Confirma conectividad con AnkiConnect.

    Intenta localhost primero; si falla y no se pasó un base_url explícito, reintenta
    una vez contra la IP del host Windows (networking WSL↔Windows, docs/technical/environment.md).
    """
    primary_url = base_url or _DEFAULT_URL
    status = _request_version(primary_url)
    if status.ok or base_url is not None:
        return status

    host_ip = _resolve_host_ip()
    if host_ip is None:
        return AnkiConnectStatus(
            ok=False,
            version=None,
            detail=f"{status.detail}; no se pudo resolver la IP del host Windows para el fallback",
        )

    fallback_url = f"http://{host_ip}:8765"
    return _request_version(fallback_url)


def _request(action: str, params: dict[str, Any] | None = None, base_url: str | None = None) -> Any:
    """Ejecuta cualquier acción de AnkiConnect, con el mismo fallback WSL↔Windows que
    check_connection() (TDD §4.1), generalizado más allá de "version". Levanta
    AnkiConnectError en fallo de conectividad (ambos intentos) o si la respuesta trae un
    "error" no nulo.
    """
    payload: dict[str, Any] = {"action": action, "version": 6}
    if params is not None:
        payload["params"] = params

    primary_url = base_url or _DEFAULT_URL
    try:
        body = _post(primary_url, payload)
    except httpx.HTTPError as exc:
        if base_url is not None:
            raise AnkiConnectError(f"no se pudo conectar a {primary_url}: {exc}") from exc

        host_ip = _resolve_host_ip()
        if host_ip is None:
            raise AnkiConnectError(
                f"no se pudo conectar a {primary_url}: {exc}; "
                "no se pudo resolver la IP del host Windows para el fallback"
            ) from exc

        fallback_url = f"http://{host_ip}:8765"
        try:
            body = _post(fallback_url, payload)
        except httpx.HTTPError as fallback_exc:
            raise AnkiConnectError(f"no se pudo conectar a {fallback_url}: {fallback_exc}") from fallback_exc

    error = body.get("error")
    if error is not None:
        raise AnkiConnectError(f"AnkiConnect respondió con error en '{action}': {error}")
    return body.get("result")


def ensure_note_type(base_url: str | None = None) -> None:
    """Crea el note type "Flashcards Agent" (Front/Back/Fuente) si no existe — idempotente.

    No reconcilia esquema si el modelo ya existe con campos distintos (ADR-0004, fuera de
    alcance v1): asume que si el nombre existe, la estructura es la esperada.
    """
    existing_models = _request("modelNames", base_url=base_url)
    if _MODEL_NAME in existing_models:
        return

    _request(
        "createModel",
        {
            "modelName": _MODEL_NAME,
            "inOrderFields": list(_MODEL_FIELDS),
            "cardTemplates": [_MODEL_TEMPLATE],
        },
        base_url=base_url,
    )


def _ensure_decks(candidates: tuple[CardCandidate, ...], base_url: str | None) -> None:
    """Crea cada deck destino si no existe.

    addNotes NO autocrea el deck — verificado contra AnkiConnect real durante el smoke test
    de IPL-29: addNote devuelve error "deck was not found" contra un deck inexistente.
    createDeck es idempotente (mismo deck id si ya existe, sin error), así que no hace falta
    chequear existencia primero como en ensure_note_type().
    """
    for deck in {candidate.deck for candidate in candidates}:
        _request("createDeck", {"deck": deck}, base_url=base_url)


def _note_payload(candidate: CardCandidate) -> dict[str, Any]:
    # Los campos de Anki se renderizan como HTML — escapar acá, en el único punto de entrada
    # a AnkiConnect, cubre ambos tipos de candidato sin que generate/ tenga que preocuparse por
    # HTML. No hay markup intencional en front/back/fuente hoy (OQ-C, IPL-30): si alguna vez se
    # necesita, se agrega DESPUÉS de este escape, no antes.
    return {
        "deckName": candidate.deck,
        "modelName": _MODEL_NAME,
        "fields": {
            "Front": html.escape(candidate.front),
            "Back": html.escape(candidate.back),
            "Fuente": html.escape(candidate.fuente),
        },
        "tags": list(candidate.tags),
        # duplicateScope "deck" acota la detección de duplicados al mazo destino (TDD §4.8:
        # "contra el estado ya existente del mazo") — no a la colección completa.
        "options": {"allowDuplicate": False, "duplicateScope": "deck"},
    }


def add_candidates(
    candidates: tuple[CardCandidate, ...], base_url: str | None = None
) -> tuple[CardCandidate, ...]:
    """Inserta candidatos verificados en Anki, con dedup y verificación post-inserción (TDD §4.8).

    canAddNotes antes de addNotes; un duplicado, un rechazo de addNotes, o un desacuerdo con
    notesInfo descartan ese candidato puntual (con output.warn) sin interrumpir el resto del
    batch — mismo principio de resiliencia que generate.practice.level1_candidates (IPL-28).
    No confía en el HTTP 200 de addNotes como prueba de inserción correcta: confirma contra
    notesInfo antes de dar un candidato por insertado.
    """
    if not candidates:
        return ()

    ensure_note_type(base_url)
    _ensure_decks(candidates, base_url)

    notes = [_note_payload(candidate) for candidate in candidates]
    can_add = _request("canAddNotes", {"notes": notes}, base_url=base_url)

    to_insert: list[tuple[CardCandidate, dict[str, Any]]] = []
    for candidate, note, addable in zip(candidates, notes, can_add, strict=True):
        if addable:
            to_insert.append((candidate, note))
        else:
            output.warn(f"{candidate.fuente}: card duplicada, no se inserta")

    if not to_insert:
        return ()

    note_ids = _request("addNotes", {"notes": [note for _, note in to_insert]}, base_url=base_url)

    inserted: list[CardCandidate] = []
    inserted_ids: list[int] = []
    for (candidate, _), note_id in zip(to_insert, note_ids, strict=True):
        if note_id is None:
            output.warn(f"{candidate.fuente}: addNotes rechazó la inserción")
            continue
        inserted.append(candidate)
        inserted_ids.append(note_id)

    if not inserted_ids:
        return ()

    infos = _request("notesInfo", {"notes": inserted_ids}, base_url=base_url)

    verified: list[CardCandidate] = []
    for candidate, note_id, info in zip(inserted, inserted_ids, infos, strict=True):
        if not info or info.get("noteId") != note_id:
            output.warn(f"{candidate.fuente}: inserción no verificable vía notesInfo")
            continue
        verified.append(candidate)

    return tuple(verified)
