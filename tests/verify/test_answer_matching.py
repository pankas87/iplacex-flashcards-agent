"""Test-first (CLAUDE.md): estos tests se escriben antes que verify/answer_matching.py.

Casos verificados contra el material real (Mate S1 R_1.1, IPL-26) — no fabricados.
"""

from fractions import Fraction

from flashcards_agent.verify.answer_matching import extract_numeric_values, matches


def test_extracts_single_plain_number():
    assert extract_numeric_values("Demorará 8 días.") == (Fraction(8),)


def test_extracts_chilean_thousands_separator():
    # ej. 2: "$14.850" -> 14850, el punto es separador de miles, no decimal.
    assert extract_numeric_values("Cada cuota tiene un valor de $14.850.") == (
        Fraction(14850),
    )


def test_extracts_plain_number_before_unit():
    assert extract_numeric_values("4 litros.") == (Fraction(4),)


def test_extracts_number_with_unit_suffix():
    # ej. 4: "Faltan por enviar 294 kilos."
    assert extract_numeric_values("Faltan por enviar 294 kilos.") == (Fraction(294),)


def test_extracts_number_glued_to_following_word():
    # ej. 17 real: "...azules y 18perlas rojas." (línea partida en el PDF, sin espacio).
    values = extract_numeric_values(
        "Pueden hacer 5 collares, cada uno con 5 perlas blancas, 3 perlas azules y "
        "18perlas rojas."
    )
    assert values == (Fraction(5), Fraction(5), Fraction(3), Fraction(18))


def test_matches_true_when_computed_is_among_extracted_values():
    # ej. 17 real: computed=5 (mcd) coincide con uno de los valores del texto multivalor.
    text = (
        "Pueden hacer 5 collares, cada uno con 5 perlas blancas, 3 perlas azules y "
        "18perlas rojas."
    )
    assert matches(Fraction(5), text) is True


def test_matches_false_when_computed_not_present():
    assert matches(Fraction(7), "Demorará 8 días.") is False


def test_matches_true_for_chilean_thousands_value():
    assert matches(Fraction(14850), "Cada cuota tiene un valor de $14.850.") is True
