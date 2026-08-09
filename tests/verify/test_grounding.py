"""verify/grounding.py — determinístico, sin LLM, testeado test-first (CLAUDE.md: verify/ es
la categoría "sí, con test-first"). Sin mocks del SDK: la función solo opera sobre strings."""

from flashcards_agent.verify.grounding import check_grounding

_BODY = (
    "El mínimo común múltiplo (m.c.m) de dos números es el menor número entero positivo que "
    "es múltiplo de ambos números a la vez. Por ejemplo, el m.c.m de 4 y 6 es 12."
)


def test_grounding_ok_with_exact_quote():
    result = check_grounding(
        statement="El m.c.m de dos números es el menor múltiplo común de ambos.",
        truth_value=True,
        evidence_quote="El mínimo común múltiplo (m.c.m) de dos números es el menor número "
        "entero positivo que es múltiplo de ambos números a la vez.",
        body=_BODY,
    )
    assert result.grounded is True
    assert result.reason == ""


def test_grounding_ok_with_different_case_and_whitespace():
    result = check_grounding(
        statement="cualquiera",
        truth_value=True,
        evidence_quote="EL MÍNIMO   COMÚN\nMÚLTIPLO (m.c.m) de dos números es el menor "
        "número entero positivo que es múltiplo de ambos números a la vez.",
        body=_BODY,
    )
    assert result.grounded is True
    assert result.reason == ""


def test_grounding_fails_when_quote_absent():
    result = check_grounding(
        statement="cualquiera",
        truth_value=True,
        evidence_quote="El máximo común divisor de dos números es el mayor divisor compartido.",
        body=_BODY,
    )
    assert result.grounded is False
    assert result.reason == "la evidencia no aparece en el pasaje fuente"


def test_grounding_fails_for_short_quote_even_if_substring():
    # Caso anti-trivialidad: "el m.c.m" ES substring literal del body, pero es una locución,
    # no una proposición — no puede sostener un valor de verdad por sí sola.
    result = check_grounding(
        statement="cualquiera",
        truth_value=True,
        evidence_quote="el m.c.m",
        body=_BODY,
    )
    assert result.grounded is False
    assert result.reason == "evidencia demasiado corta"


def test_grounding_fails_for_empty_quote():
    result = check_grounding(
        statement="cualquiera",
        truth_value=True,
        evidence_quote="   ",
        body=_BODY,
    )
    assert result.grounded is False
    assert result.reason == "evidencia vacía"


def test_grounding_fails_for_quote_longer_than_max():
    result = check_grounding(
        statement="cualquiera",
        truth_value=True,
        evidence_quote=_BODY * 3,
        body=_BODY * 3,
    )
    assert result.grounded is False
    assert result.reason == "evidencia demasiado larga"


def test_grounding_fails_for_empty_body():
    result = check_grounding(
        statement="cualquiera",
        truth_value=True,
        evidence_quote="El mínimo común múltiplo de dos números es el menor múltiplo común.",
        body="",
    )
    assert result.grounded is False
    assert result.reason == "la evidencia no aparece en el pasaje fuente"


def test_grounding_fails_when_false_statement_appears_verbatim_in_body():
    # Contradicción detectable en Python: si la card declara la afirmación FALSA pero el
    # propio pasaje la contiene textual, el pasaje afirma lo que la card niega.
    result = check_grounding(
        statement="El mínimo común múltiplo (m.c.m) de dos números es el menor número entero "
        "positivo que es múltiplo de ambos números a la vez.",
        truth_value=False,
        evidence_quote="Por ejemplo, el m.c.m de 4 y 6 es 12.",
        body=_BODY,
    )
    assert result.grounded is False
    assert result.reason == "afirmación declarada falsa aparece textual en el pasaje"


def test_grounding_ok_for_false_statement_with_contradicting_evidence():
    # El caso normal de una afirmación falsa: NO aparece textual en el body (fue alterada por
    # el generador), pero cita evidencia real y suficientemente larga que la contradice.
    result = check_grounding(
        statement="El m.c.m de dos números siempre es menor que su producto sin excepción.",
        truth_value=False,
        evidence_quote="Por ejemplo, el m.c.m de 4 y 6 es 12, que es igual a su producto, no menor.",
        body=_BODY + " Por ejemplo, el m.c.m de 4 y 6 es 12, que es igual a su producto, no menor.",
    )
    assert result.grounded is True
    assert result.reason == ""


def test_normalize_for_grounding_collapses_whitespace_and_case():
    from flashcards_agent.verify.grounding import normalize_for_grounding

    assert normalize_for_grounding("  Hola   Mundo\n\n") == normalize_for_grounding("hola mundo")
