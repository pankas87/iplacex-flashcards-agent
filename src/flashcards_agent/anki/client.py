"""Cliente AnkiConnect — punto único de verdad para conectividad (TDD §4.1).

Contrato de la acción "version" verificado contra fuente primaria (mirror README,
agosto 2026): request {"action": "version", "version": 6}; response
{"result": <int>, "error": null} en éxito, {"result": null, "error": "<msg>"} en error.
Puerto default 8765, webBindAddress default 127.0.0.1.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import httpx

_DEFAULT_URL = "http://localhost:8765"
_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class AnkiConnectStatus:
    ok: bool
    version: int | None
    detail: str


def _request_version(base_url: str) -> AnkiConnectStatus:
    payload = {"action": "version", "version": 6}
    try:
        response = httpx.post(base_url, json=payload, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return AnkiConnectStatus(ok=False, version=None, detail=f"no se pudo conectar a {base_url}: {exc}")

    body = response.json()
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
