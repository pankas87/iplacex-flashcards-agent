# Fuente única de comandos de entorno del proyecto (CLAUDE.md, TDD §4.1).
# Cualquier operación nueva sobre el entorno se agrega como target acá, no como comando suelto.

default:
    @just --list

# Healthcheck de AnkiConnect — scripts/anki_healthcheck.py (TDD §4.1, IPL-25)
anki-check:
    uv run python scripts/anki_healthcheck.py
