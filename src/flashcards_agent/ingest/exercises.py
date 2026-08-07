"""Pareo posicional de ejercicios y respuestas (ADR-0003)."""

from __future__ import annotations

import re
from pathlib import Path

import docx

from flashcards_agent.models.content import ExercisePair, PageText

_ANSWER_LINE = re.compile(r"^\s*(\d+)\.\s*(.*)$")


class ExercisePairingError(Exception):
    """El conteo de enunciados y respuestas no coincide — no se parea a ciegas (ADR-0003)."""


def extract_exercise_statements(path: Path) -> tuple[str, ...]:
    """Enunciados reales de un EJ_*.docx, excluyendo títulos/encabezados.

    Word marca los enunciados con el estilo "List Paragraph" (son una lista numerada) y
    los títulos ("GUIA DE EJERCICIOS", "EJERCICIOS PROPUESTOS.") con "Normal" — filtro
    por estilo, no por longitud, verificado contra el material real (Mate S1 EJ_1.1).
    """
    document = docx.Document(path)
    return tuple(
        p.text.strip()
        for p in document.paragraphs
        if p.text.strip() and p.style.name == "List Paragraph"
    )


def parse_answer_key(pages: tuple[PageText, ...]) -> tuple[str, ...]:
    """Extrae respuestas numeradas "1.", "2.", ... de la clave, en orden.

    Las líneas que no matchean el patrón de numeración se acumulan a la respuesta en
    curso (una respuesta puede envolver a más de una línea en el PDF).
    """
    full_text = "\n".join(page.text for page in pages)
    answers: list[str] = []
    current_lines: list[str] = []
    in_answer = False

    for line in full_text.splitlines():
        match = _ANSWER_LINE.match(line)
        if match:
            if in_answer:
                answers.append(" ".join(current_lines).strip())
            in_answer = True
            current_lines = [match.group(2).strip()]
        elif in_answer and line.strip():
            current_lines.append(line.strip())

    if in_answer:
        answers.append(" ".join(current_lines).strip())

    return tuple(answers)


def pair_exercises(
    statements: tuple[str, ...], answers: tuple[str, ...], source_name: str
) -> tuple[ExercisePair, ...]:
    if len(statements) != len(answers):
        raise ExercisePairingError(
            f"{source_name}: {len(statements)} enunciados vs {len(answers)} respuestas "
            "— no se parea a ciegas (ADR-0003)"
        )

    return tuple(
        ExercisePair(
            index=i + 1,
            statement=statement,
            published_answer=answer,
            source_ref=f"{source_name}, ej. {i + 1}",
        )
        for i, (statement, answer) in enumerate(zip(statements, answers, strict=True))
    )
