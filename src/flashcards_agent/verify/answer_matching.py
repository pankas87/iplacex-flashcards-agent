"""Extrae y compara valores numéricos de respuestas publicadas en prosa (TDD §4.6).

Asume formato chileno: punto como separador de miles, coma como separador decimal — el
único formato visto en el material real (Mate S1 R_1.1, IPL-26). Ver OQ-03 del spec
(SPEC-1-IT3-verify) sobre casos con decimales todavía no observados.
"""

from __future__ import annotations

import re
from fractions import Fraction

_NUMBER_PATTERN = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _parse_number(raw: str) -> Fraction:
    # Los puntos que matchean _NUMBER_PATTERN son siempre separadores de miles (la primera
    # alternativa exige grupos de exactamente 3 dígitos); la coma, si aparece, es decimal.
    normalized = raw.replace(".", "").replace(",", ".")
    return Fraction(normalized)


def extract_numeric_values(text: str) -> tuple[Fraction, ...]:
    return tuple(_parse_number(match.group()) for match in _NUMBER_PATTERN.finditer(text))


def matches(computed: Fraction, published_text: str) -> bool:
    return computed in extract_numeric_values(published_text)
