"""Wrapper CLI standalone sobre anki/client.py::check_connection() — invocado por `just anki-check`.

No reimplementa la lógica de conexión: solo llama y reporta (TDD §4.1, un solo punto de verdad).
"""

import sys

from flashcards_agent import output
from flashcards_agent.anki.client import check_connection


def main() -> None:
    status = check_connection()
    if status.ok:
        output.ok(f"AnkiConnect vivo — versión {status.version}")
        sys.exit(0)
    output.err(status.detail)
    sys.exit(1)


if __name__ == "__main__":
    main()
