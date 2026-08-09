"""Orquestación ingesta -> clasificación -> generación -> verificación -> inserción (US-8,
TDD §4.1, §4.3, §4.8). Encadena piezas ya existentes y probadas (IPL-26/28/29/30); no rediseña
ninguna.

Síncrona y sin estado de sesión, a propósito: classify.segmenter.segment(),
generate.practice.translate_exercise() y generate.theory.generate_statements() llaman
asyncio.run() internamente, que no puede invocarse desde un event loop ya corriendo. Cuando
US-9 vuelva async el loop de CLI, la migración es local a cli.loop.dispatch()
(asyncio.to_thread sobre process_week), sin tocar esta capa ni los sub-módulos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from flashcards_agent import output
from flashcards_agent.anki.client import AnkiConnectError, add_candidates, check_connection
from flashcards_agent.classify.segmenter import segment
from flashcards_agent.generate.practice import level1_candidates
from flashcards_agent.generate.theory import theory_candidates
from flashcards_agent.ingest.exercises import (
    ExercisePairingError,
    extract_exercise_statements,
    pair_exercises,
    parse_answer_key,
)
from flashcards_agent.ingest.reader import discover_week, exercise_key
from flashcards_agent.models.card import CardCandidate, deck_name, known_subjects
from flashcards_agent.models.content import ExercisePair, SourceDocument


@dataclass(frozen=True)
class ExerciseGroup:
    key: str
    exercises: SourceDocument
    answer_key: SourceDocument


def group_exercise_documents(documents: Sequence[SourceDocument]) -> tuple[ExerciseGroup, ...]:
    exercises_by_key: dict[str, SourceDocument] = {}
    answers_by_key: dict[str, SourceDocument] = {}

    for doc in documents:
        key = exercise_key(doc.path.name)
        if not key:
            continue
        if doc.kind == "exercises":
            exercises_by_key[key] = doc
        elif doc.kind == "answer_key":
            answers_by_key[key] = doc

    groups: list[ExerciseGroup] = []
    for key in sorted(set(exercises_by_key) | set(answers_by_key)):
        exercises_doc = exercises_by_key.get(key)
        answer_doc = answers_by_key.get(key)
        if exercises_doc is None:
            output.warn(f"{answer_doc.path.name}: sin su archivo EJ_ correspondiente — se salta")
            continue
        if answer_doc is None:
            output.warn(f"{exercises_doc.path.name}: sin su archivo R_ correspondiente — se salta")
            continue
        groups.append(ExerciseGroup(key=key, exercises=exercises_doc, answer_key=answer_doc))

    return tuple(groups)


@dataclass(frozen=True)
class WeekReport:
    subject_slug: str
    week: int
    status: Literal["ok", "sin-conexion", "sin-material", "materia-desconocida", "error-insercion"]
    documents: int = 0
    theory_segments: int = 0
    skipped_segments: int = 0
    theory_cards: int = 0
    exercise_groups: int = 0
    pairing_failures: int = 0
    exercise_pairs: int = 0
    practice_cards: int = 0
    inserted: int = 0

    @property
    def generated(self) -> int:
        return self.theory_cards + self.practice_cards

    @property
    def not_inserted(self) -> int:
        return self.generated - self.inserted


def process_week(
    subject_slug: str,
    week: int,
    root: Path = Path("material"),
    base_url: str | None = None,
) -> WeekReport:
    if subject_slug not in known_subjects():
        output.err(f"materia desconocida: '{subject_slug}'")
        return WeekReport(subject_slug=subject_slug, week=week, status="materia-desconocida")

    # 1. Healthcheck primero — TDD §4.1 escenario 2. Antes de leer material, antes de
    #    gastar un solo token.
    status = check_connection(base_url)
    if not status.ok:
        output.err(status.detail)
        return WeekReport(subject_slug=subject_slug, week=week, status="sin-conexion")
    output.info(f"AnkiConnect vivo (v{status.version})")

    # 2. Descubrir material de la semana.
    documents = discover_week(subject_slug, week, root=root)
    if not documents:
        output.warn(f"{subject_slug} semana {week}: sin material en {root} — nada que procesar")
        return WeekReport(subject_slug=subject_slug, week=week, status="sin-material")
    output.info(f"{len(documents)} documento(s) encontrados para {subject_slug} semana {week}")

    # 3. Teoría: segmentar cada doc kind="theory" y acumular segmentos por flavor.
    theory_segments = []
    skipped_segments = 0
    for doc in documents:
        if doc.kind != "theory":
            continue
        try:
            segments = segment(doc)
        except RuntimeError as exc:
            output.warn(f"{doc.path.name}: segmentación falló ({exc}) — se salta el documento")
            continue
        for seg in segments:
            if seg.flavor == "theory":
                theory_segments.append(seg)
            else:
                skipped_segments += 1

    # 4. Práctico: agrupar y parear ejercicios por clave (puede haber más de un par por semana).
    groups = group_exercise_documents(documents)
    pairs: list[ExercisePair] = []
    pairing_failures = 0
    for group in groups:
        statements = extract_exercise_statements(group.exercises.path)
        answers = parse_answer_key(group.answer_key.pages)
        try:
            pairs.extend(pair_exercises(statements, answers, group.exercises.path.name))
        except ExercisePairingError as exc:
            output.warn(str(exc))
            pairing_failures += 1
            continue

    # 5. Aviso de volumen antes de generar — informativo, sin gate de confirmación (v1 sin dry-run).
    output.info(
        f"a generar: {len(theory_segments)} segmento(s) teórico(s) x 3 niveles + "
        f"{len(pairs)} ejercicio(s) — llamadas al modelo"
    )

    theory_cards = theory_candidates(tuple(theory_segments), subject_slug, week)
    practice_cards = level1_candidates(tuple(pairs), subject_slug, week)

    # 6. Insertar.
    candidates: tuple[CardCandidate, ...] = theory_cards + practice_cards
    try:
        inserted = add_candidates(candidates, base_url)
    except AnkiConnectError as exc:
        output.err(f"inserción abortada: {exc}")
        return WeekReport(
            subject_slug=subject_slug,
            week=week,
            status="error-insercion",
            documents=len(documents),
            theory_segments=len(theory_segments),
            skipped_segments=skipped_segments,
            theory_cards=len(theory_cards),
            exercise_groups=len(groups),
            pairing_failures=pairing_failures,
            exercise_pairs=len(pairs),
            practice_cards=len(practice_cards),
            inserted=0,
        )

    report = WeekReport(
        subject_slug=subject_slug,
        week=week,
        status="ok",
        documents=len(documents),
        theory_segments=len(theory_segments),
        skipped_segments=skipped_segments,
        theory_cards=len(theory_cards),
        exercise_groups=len(groups),
        pairing_failures=pairing_failures,
        exercise_pairs=len(pairs),
        practice_cards=len(practice_cards),
        inserted=len(inserted),
    )

    # 7. Resumen agregado — no duplica los avisos por ítem que ya emitieron los sub-módulos.
    output.info(f"documentos: {report.documents}")
    output.info(f"segmentos: {report.theory_segments} teóricos procesados, {report.skipped_segments} salteados (practice/discard)")
    output.info(f"ejercicios: {report.exercise_groups} grupo(s) EJ/R, {report.pairing_failures} con conteo desparejo, {report.exercise_pairs} enunciado(s) pareados")
    output.info(f"prácticos descartados antes de insertar: {report.exercise_pairs - report.practice_cards} (no traducibles o cómputo != clave, ver avisos arriba)")
    output.info(f"generados: {report.theory_cards} teóricos + {report.practice_cards} prácticos = {report.generated}")
    output.ok(
        f"insertados {report.inserted}/{report.generated} en {deck_name(subject_slug, week)} "
        f"— {report.not_inserted} no insertados (duplicado/rechazo/no verificable, ver avisos)"
    )

    return report
