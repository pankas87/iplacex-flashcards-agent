"""generate/theory.py — mockea el SDK, no llama al LLM real en cada corrida de tests.

Los fixtures _MCM_LEVELS y _HARDWARE_LEVELS son la salida REAL y completa de llamadas reales
al SDK (verificación hecha durante la implementación de SPEC-1-IT6, 2026-08-09) — no
fabricados (CLAUDE.md: "golden files, siempre reales — nunca fabricados para que el test
pase"). _MCM_LEVELS viene de segmentar "Nivelación Matemática - Semana 1.pdf" (IPL-26) y pedir
generate_statements() sobre el segmento topic_tag="mcm" (p. 9) en los 3 niveles.
_HARDWARE_LEVELS viene del mismo mecanismo sobre "Soporte Hardware - Semana 1.pdf",
topic_tag="hardware-basico" (p. 6). Ambas corridas confirmaron materia-agnosticismo (US-5/US-6,
TDD §5.1) y revelaron dos comportamientos reales que los tests de abajo cubren:

- La cita real "2 × 2 × 3 × 3 × 3 × 5 = 540" (27 caracteres normalizados) es evidencia
  numérica legítima y específica de un ejemplo del material, no una locución trivial — motivó
  bajar _MIN_EVIDENCE_CHARS de 30 a 20 en verify/grounding.py (OQ-A del spec, resuelta). Con
  ese ajuste, las 23 afirmaciones crudas del fixture de mcm pasan el chequeo de GROUNDING sin
  excepción.
- Ambos fixtures traen afirmaciones repetidas VERBATIM entre niveles (mcm: 1 caso entre nivel
  1 y 2; hardware: 2 casos, nivel 1↔2 y nivel 2↔3) — el dedupe acumulado por segmento (no el
  grounding) es lo que las descarta. Son dos mecanismos independientes: grounding confirma que
  la evidencia existe en el pasaje; dedupe evita repetir la misma afirmación entre niveles del
  superset.

_MCM_LEVELS/_HARDWARE_LEVELS se capturaron bajo la redacción original del prompt ("Generá
entre 5 y 8"), previa a la revisión de TDD §4.5.1 del 2026-08-09 (IPL-30) que convirtió 5-8 en
un piso de referencia, no un techo. Siguen siendo válidos para testear grounding/dedupe (esos
mecanismos no dependen de la redacción del prompt). El comportamiento de "generar más si el
pasaje da para más" se valida con el test sintético
test_theory_candidates_keeps_all_grounded_above_reference_floor, y se confirmó además en vivo
contra el mismo pasaje real de mcm con el prompt nuevo: 13/10/12 afirmaciones por nivel
(vs. 8/7/8 con la redacción vieja) — no se recapturó como fixture nuevo para no inflar este
archivo con datos redundantes para lo que el mecanismo ya prueba.

Los casos de borde puramente mecánicos (descarte por grounding, RuntimeError por nivel, rango
5-8, tag de tema vacío, flavor no-theory, body corto) usan un body sintético: no hay juicio
pedagógico que validar ahí, solo el mecanismo de orquestación (mismo criterio que
_NON_ARITHMETIC_STATEMENT en tests/generate/test_practice.py).
"""

from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage

from flashcards_agent.generate.theory import _user_prompt, theory_candidates
from flashcards_agent.models.content import ContentSegment

# ─────────────────────────────────────────────────────────────────────────
# Fixtures reales — Nivelación Matemática S1, p. 9, topic_tag="mcm" (2026-08-09)
# ─────────────────────────────────────────────────────────────────────────

_MCM_SEGMENT = ContentSegment(
    title="Mínimo común múltiplo (m.c.m): concepto y cálculo",
    body=(
        "El mínimo común múltiplo (m.c.m) de dos o más números naturales es el menor número "
        "natural que es múltiplo común de todos ellos. Método de cálculo: (1) Identificar "
        "números primos que dividen a cada número. (2) Realizar divisiones sucesivas hasta "
        "llegar a 1. (3) Multiplicar todos los divisores primos utilizados. Ejemplo: "
        "m.c.m(45, 27, 12) se calcula dividiendo entre 2, 2, 3, 3, 3, 5, resultando 2 × 2 × 3 "
        "× 3 × 3 × 5 = 540. El m.c.m es necesario para resolver problemas matemáticos, "
        "factorizar y trabajar con fracciones de denominadores distintos."
    ),
    topic_tag="mcm",
    flavor="theory",
    source_ref="Nivelación Matemática - Semana 1.pdf, p. 9",
)

_MCM_LEVELS: dict[int, list[dict]] = {
    1: [
        {
            "statement": "El m.c.m de dos o más números naturales es el menor número natural que es múltiplo común de todos ellos.",
            "truth_value": True,
            "evidence_quote": "el menor número natural que es múltiplo común de todos ellos",
            "explanation": "El pasaje define literalmente al m.c.m como el menor número natural que es múltiplo común de todos ellos.",
        },
        {
            "statement": "El m.c.m de dos o más números naturales es el mayor número natural que es múltiplo común de todos ellos.",
            "truth_value": False,
            "evidence_quote": "el menor número natural que es múltiplo común de todos ellos",
            "explanation": "El pasaje dice que es el menor número, no el mayor, por lo que la afirmación invierte la definición.",
        },
        {
            "statement": "El método de cálculo del m.c.m incluye identificar números primos que dividen a cada número.",
            "truth_value": True,
            "evidence_quote": "Identificar números primos que dividen a cada número.",
            "explanation": "Es exactamente el primer paso descrito en el método de cálculo del pasaje.",
        },
        {
            "statement": "En el método de cálculo del m.c.m se pueden usar como divisores tanto números primos como compuestos.",
            "truth_value": False,
            "evidence_quote": "Identificar números primos que dividen a cada número.",
            "explanation": "El pasaje especifica que los divisores usados deben ser números primos, no cualquier número compuesto.",
        },
        {
            "statement": "Tras las divisiones sucesivas, el método indica multiplicar todos los divisores primos utilizados.",
            "truth_value": True,
            "evidence_quote": "Multiplicar todos los divisores primos utilizados.",
            "explanation": "Este es el tercer paso del método de cálculo tal como aparece en el pasaje.",
        },
        {
            "statement": "Según el ejemplo del pasaje, el m.c.m(45, 27, 12) es igual a 540.",
            "truth_value": True,
            "evidence_quote": "2 × 2 × 3 × 3 × 3 × 5 = 540",
            "explanation": "El pasaje muestra explícitamente que el resultado del ejemplo es 540.",
        },
        {
            "statement": "El pasaje afirma que el m.c.m es necesario únicamente para factorizar, sin utilidad para resolver problemas matemáticos ni para trabajar con fracciones de denominadores distintos.",
            "truth_value": False,
            "evidence_quote": "El m.c.m es necesario para resolver problemas matemáticos, factorizar y trabajar con fracciones de denominadores distintos.",
            "explanation": "El pasaje lista tres utilidades del m.c.m, no solo la factorización, por lo que restringirlo a 'únicamente factorizar' es falso.",
        },
        {
            "statement": "El proceso de cálculo del m.c.m consiste en realizar divisiones sucesivas hasta llegar a 1.",
            "truth_value": True,
            "evidence_quote": "Realizar divisiones sucesivas hasta llegar a 1.",
            "explanation": "Este es el segundo paso del método de cálculo indicado literalmente en el pasaje.",
        },
    ],
    2: [
        {
            "statement": "El m.c.m de dos o más números naturales se define como el menor número natural que es múltiplo común de todos ellos.",
            "truth_value": True,
            "evidence_quote": "el menor número natural que es múltiplo común de todos ellos",
            "explanation": "El pasaje define textualmente el m.c.m como el menor número natural que es múltiplo común de todos los números dados.",
        },
        {
            "statement": "El m.c.m de dos o más números naturales es el mayor número natural que es múltiplo común de todos ellos.",
            "truth_value": False,
            "evidence_quote": "el menor número natural que es múltiplo común de todos ellos",
            "explanation": "El pasaje especifica que el m.c.m es el menor número, no el mayor, que es múltiplo común de todos ellos.",
        },
        {
            "statement": "El método de cálculo del m.c.m consiste en identificar números primos que dividen a cada número, realizar divisiones sucesivas hasta llegar a 1, y luego multiplicar todos los divisores primos utilizados.",
            "truth_value": True,
            "evidence_quote": "Identificar números primos que dividen a cada número. (2) Realizar divisiones sucesivas hasta llegar a 1. (3) Multiplicar todos los divisores primos utilizados.",
            "explanation": "El pasaje describe exactamente estos tres pasos como el método de cálculo del m.c.m.",
        },
        {
            "statement": "Según el ejemplo del pasaje, el m.c.m(45, 27, 12) es igual a 360.",
            "truth_value": False,
            "evidence_quote": "2 × 2 × 3 × 3 × 3 × 5 = 540",
            "explanation": "El pasaje indica que el resultado de la multiplicación de los divisores primos utilizados es 540, no 360.",
        },
        {
            "statement": "En el ejemplo del pasaje, para calcular el m.c.m(45, 27, 12) el número primo 3 se utiliza únicamente dos veces como divisor.",
            "truth_value": False,
            "evidence_quote": "dividiendo entre 2, 2, 3, 3, 3, 5",
            "explanation": "El pasaje muestra que el divisor primo 3 aparece tres veces en la secuencia de divisiones sucesivas, no dos.",
        },
        {
            "statement": "El m.c.m es necesario para resolver problemas matemáticos, factorizar y trabajar con fracciones de denominadores distintos.",
            "truth_value": True,
            "evidence_quote": "El m.c.m es necesario para resolver problemas matemáticos, factorizar y trabajar con fracciones de denominadores distintos.",
            "explanation": "El pasaje enumera exactamente estas tres aplicaciones del m.c.m.",
        },
        {
            "statement": "Según el pasaje, el m.c.m únicamente sirve para factorizar números, sin ninguna aplicación en fracciones de denominadores distintos.",
            "truth_value": False,
            "evidence_quote": "El m.c.m es necesario para resolver problemas matemáticos, factorizar y trabajar con fracciones de denominadores distintos.",
            "explanation": "El pasaje indica que el m.c.m tiene varias aplicaciones, incluyendo el trabajo con fracciones de denominadores distintos, por lo que restringirlo únicamente a la factorización contradice el texto.",
        },
    ],
    3: [
        {
            "statement": "El mínimo común múltiplo de dos o más números naturales es el menor número natural que es múltiplo común de todos ellos.",
            "truth_value": True,
            "evidence_quote": "el menor número natural que es múltiplo común de todos ellos",
            "explanation": "El pasaje define textualmente al m.c.m. como el menor número natural que es múltiplo común de todos los números considerados.",
        },
        {
            "statement": "El m.c.m. de dos o más números naturales es el mayor número natural que es múltiplo común de todos ellos.",
            "truth_value": False,
            "evidence_quote": "el menor número natural que es múltiplo común de todos ellos",
            "explanation": "El pasaje especifica que el m.c.m. es el menor número, no el mayor, que es múltiplo común de todos ellos.",
        },
        {
            "statement": "Según el método descrito, el último paso para obtener el m.c.m. consiste en multiplicar todos los divisores primos utilizados.",
            "truth_value": True,
            "evidence_quote": "Multiplicar todos los divisores primos utilizados",
            "explanation": "El paso 3 del método indica explícitamente que se deben multiplicar todos los divisores primos usados en las divisiones sucesivas.",
        },
        {
            "statement": "Según el método descrito, el último paso para obtener el m.c.m. consiste en sumar todos los divisores primos utilizados.",
            "truth_value": False,
            "evidence_quote": "Multiplicar todos los divisores primos utilizados",
            "explanation": "El pasaje indica que el paso final es multiplicar los divisores primos, no sumarlos.",
        },
        {
            "statement": "Al calcular el m.c.m(45, 27, 12) dividiendo sucesivamente entre 2, 2, 3, 3, 3 y 5, el resultado obtenido es 540.",
            "truth_value": True,
            "evidence_quote": "2 × 2 × 3 × 3 × 3 × 5 = 540",
            "explanation": "El ejemplo del pasaje muestra que multiplicando esos divisores primos el resultado final es 540.",
        },
        {
            "statement": "Al calcular el m.c.m(45, 27, 12) siguiendo el procedimiento del ejemplo, el resultado obtenido es 360.",
            "truth_value": False,
            "evidence_quote": "2 × 2 × 3 × 3 × 3 × 5 = 540",
            "explanation": "El pasaje establece explícitamente que el resultado de ese cálculo es 540, no 360.",
        },
        {
            "statement": "El m.c.m. es necesario, entre otras cosas, para trabajar con fracciones de denominadores distintos.",
            "truth_value": True,
            "evidence_quote": "trabajar con fracciones de denominadores distintos",
            "explanation": "El pasaje menciona explícitamente esta utilidad del m.c.m. junto con resolver problemas matemáticos y factorizar.",
        },
        {
            "statement": "El m.c.m. únicamente sirve para factorizar números y no tiene ninguna utilidad en problemas con fracciones.",
            "truth_value": False,
            "evidence_quote": "El m.c.m es necesario para resolver problemas matemáticos, factorizar y trabajar con fracciones de denominadores distintos",
            "explanation": "El pasaje señala que el m.c.m. tiene varias utilidades, incluyendo trabajar con fracciones, por lo que limitarlo únicamente a factorizar es una generalización indebida.",
        },
    ],
}

# ─────────────────────────────────────────────────────────────────────────
# Fixtures reales — Soporte Hardware S1, p. 6, topic_tag="hardware-basico" (2026-08-09)
# ─────────────────────────────────────────────────────────────────────────

_HARDWARE_SEGMENT = ContentSegment(
    title="Componentes físicos del computador y arquitectura interna",
    body=(
        "El hardware se refiere a las partes físicas de un computador, como la placa base, "
        "el procesador (CPU), la memoria RAM, los dispositivos de almacenamiento (disco "
        "duro, SSD), tarjetas gráficas, fuentes de alimentación y otros. Cada componente "
        "tiene una función específica que permite al dispositivo ejecutar programas y "
        "procesar datos. Entender cómo funcionan estos componentes y cómo interactúan entre "
        "sí es fundamental para cualquiera que desee realizar soporte de hardware, ya que la "
        "solución de problemas a menudo requiere un conocimiento profundo de la arquitectura "
        "interna del sistema."
    ),
    topic_tag="hardware-basico",
    flavor="theory",
    source_ref="Soporte Hardware - Semana 1.pdf, p. 6",
)

_HARDWARE_LEVELS: dict[int, list[dict]] = {
    1: [
        {
            "statement": "El hardware se refiere a las partes físicas de un computador.",
            "truth_value": True,
            "evidence_quote": "El hardware se refiere a las partes físicas de un computador, como la placa base, el procesador (CPU), la memoria RAM",
            "explanation": "El pasaje define literalmente el hardware como las partes físicas de un computador.",
        },
        {
            "statement": "La placa base es mencionada como un ejemplo de componente de hardware.",
            "truth_value": True,
            "evidence_quote": "como la placa base, el procesador (CPU), la memoria RAM, los dispositivos de almacenamiento",
            "explanation": "La placa base aparece explícitamente listada como ejemplo de hardware.",
        },
        {
            "statement": "El disco duro y el SSD son mencionados como ejemplos de dispositivos de almacenamiento.",
            "truth_value": True,
            "evidence_quote": "los dispositivos de almacenamiento (disco duro, SSD)",
            "explanation": "El pasaje cita el disco duro y el SSD como ejemplos de dispositivos de almacenamiento.",
        },
        {
            "statement": "Todos los componentes de hardware cumplen la misma función genérica dentro del computador.",
            "truth_value": False,
            "evidence_quote": "Cada componente tiene una función específica que permite al dispositivo ejecutar programas y procesar datos.",
            "explanation": "El pasaje indica que cada componente tiene una función específica, no una función genérica compartida por todos.",
        },
        {
            "statement": "Comprender el funcionamiento del hardware es irrelevante para quien desee realizar soporte técnico.",
            "truth_value": False,
            "evidence_quote": "Entender cómo funcionan estos componentes y cómo interactúan entre sí es fundamental para cualquiera que desee realizar soporte de hardware",
            "explanation": "El pasaje afirma que ese conocimiento es fundamental, no irrelevante, para quien haga soporte de hardware.",
        },
        {
            "statement": "La solución de problemas de hardware a menudo requiere un conocimiento profundo de la arquitectura interna del sistema.",
            "truth_value": True,
            "evidence_quote": "la solución de problemas a menudo requiere un conocimiento profundo de la arquitectura interna del sistema",
            "explanation": "Esta es una cita literal del pasaje sobre la necesidad de conocimiento profundo para la solución de problemas.",
        },
        {
            "statement": "La CPU se refiere únicamente a la memoria RAM del computador.",
            "truth_value": False,
            "evidence_quote": "el procesador (CPU), la memoria RAM",
            "explanation": "El pasaje lista la CPU y la memoria RAM como componentes distintos, no como sinónimos.",
        },
    ],
    2: [
        {
            # Duplicado verbatim del nivel 1, item 1 -- caso real de dedupe acumulado.
            "statement": "El hardware se refiere a las partes físicas de un computador.",
            "truth_value": True,
            "evidence_quote": "El hardware se refiere a las partes físicas de un computador",
            "explanation": "El pasaje define explícitamente el hardware como las partes físicas de un computador.",
        },
        {
            "statement": "Las tarjetas gráficas y las fuentes de alimentación son mencionadas en el pasaje como ejemplos de componentes de hardware.",
            "truth_value": True,
            "evidence_quote": "tarjetas gráficas, fuentes de alimentación y otros",
            "explanation": "El pasaje lista ambas como ejemplos dentro de la enumeración de componentes de hardware.",
        },
        {
            "statement": "Según el pasaje, únicamente el procesador (CPU) tiene una función específica dentro del computador.",
            "truth_value": False,
            "evidence_quote": "Cada componente tiene una función específica que permite al dispositivo ejecutar programas y procesar datos.",
            "explanation": "El pasaje indica que cada componente tiene una función específica, no solamente la CPU.",
        },
        {
            "statement": "Entender cómo funcionan los componentes de hardware y cómo interactúan entre sí es fundamental para quienes desean realizar soporte de hardware.",
            "truth_value": True,
            "evidence_quote": "Entender cómo funcionan estos componentes y cómo interactúan entre sí es fundamental para cualquiera que desee realizar soporte de hardware",
            "explanation": "El pasaje afirma directamente esta relación entre comprensión de los componentes y el soporte de hardware.",
        },
        {
            # Statement idéntico reaparece verbatim en nivel 3, item 6 -- segundo caso real de dedupe.
            "statement": "El pasaje afirma que la solución de problemas de hardware nunca requiere conocimiento de la arquitectura interna del sistema.",
            "truth_value": False,
            "evidence_quote": "la solución de problemas a menudo requiere un conocimiento profundo de la arquitectura interna del sistema",
            "explanation": "El pasaje dice que la solución de problemas 'a menudo' requiere ese conocimiento, no que 'nunca' lo requiere.",
        },
        {
            "statement": "El disco duro y el SSD son mencionados en el pasaje como ejemplos de dispositivos de almacenamiento.",
            "truth_value": True,
            "evidence_quote": "los dispositivos de almacenamiento (disco duro, SSD)",
            "explanation": "El pasaje agrupa explícitamente al disco duro y al SSD como ejemplos de dispositivos de almacenamiento.",
        },
        {
            "statement": "Según el pasaje, la placa base es clasificada como un dispositivo de almacenamiento junto con el disco duro y el SSD.",
            "truth_value": False,
            "evidence_quote": "como la placa base, el procesador (CPU), la memoria RAM, los dispositivos de almacenamiento (disco duro, SSD)",
            "explanation": "El pasaje enumera la placa base como un componente aparte, distinto de la categoría de dispositivos de almacenamiento que agrupa al disco duro y al SSD.",
        },
    ],
    3: [
        {
            "statement": "El hardware se refiere a las partes físicas de un computador, como la placa base, el procesador y la memoria RAM.",
            "truth_value": True,
            "evidence_quote": "El hardware se refiere a las partes físicas de un computador, como la placa base, el procesador (CPU), la memoria RAM, los dispositivos de almacenamiento (disco duro, SSD), tarjetas gráficas, fuentes de alimentación y otros.",
            "explanation": "El pasaje define explícitamente al hardware como las partes físicas del computador y cita esos ejemplos.",
        },
        {
            "statement": "Según el pasaje, la memoria RAM es un tipo de dispositivo de almacenamiento, igual que el disco duro y el SSD.",
            "truth_value": False,
            "evidence_quote": "la memoria RAM, los dispositivos de almacenamiento (disco duro, SSD)",
            "explanation": "El pasaje enumera la memoria RAM y los dispositivos de almacenamiento (disco duro, SSD) como categorías separadas, no como la misma categoría.",
        },
        {
            "statement": "El pasaje indica que las tarjetas gráficas y las fuentes de alimentación son el mismo componente de hardware.",
            "truth_value": False,
            "evidence_quote": "tarjetas gráficas, fuentes de alimentación y otros",
            "explanation": "El pasaje las lista como elementos distintos separados por comas dentro del listado de componentes de hardware.",
        },
        {
            "statement": "Cada componente de hardware mencionado en el pasaje cumple una función específica que permite al dispositivo ejecutar programas y procesar datos.",
            "truth_value": True,
            "evidence_quote": "Cada componente tiene una función específica que permite al dispositivo ejecutar programas y procesar datos.",
            "explanation": "El pasaje afirma textualmente que cada componente tiene una función específica con ese propósito.",
        },
        {
            "statement": "Según el pasaje, entender cómo interactúan los componentes de hardware entre sí es fundamental para quien desee realizar soporte de hardware.",
            "truth_value": True,
            "evidence_quote": "Entender cómo funcionan estos componentes y cómo interactúan entre sí es fundamental para cualquiera que desee realizar soporte de hardware",
            "explanation": "El pasaje establece esta relación de forma directa.",
        },
        {
            # Duplicado verbatim del nivel 2, item 5 (ver arriba) -- se descarta acá.
            "statement": "El pasaje afirma que la solución de problemas de hardware nunca requiere conocimiento de la arquitectura interna del sistema.",
            "truth_value": False,
            "evidence_quote": "la solución de problemas a menudo requiere un conocimiento profundo de la arquitectura interna del sistema.",
            "explanation": "El pasaje dice que 'a menudo' se requiere ese conocimiento, no que nunca se requiere; la afirmación invierte el sentido.",
        },
        {
            "statement": "Un técnico que debe diagnosticar una falla de hardware, según lo descrito en el pasaje, se beneficiaría de conocer en profundidad la arquitectura interna del sistema.",
            "truth_value": True,
            "evidence_quote": "la solución de problemas a menudo requiere un conocimiento profundo de la arquitectura interna del sistema",
            "explanation": "Aplicar la afirmación del pasaje a un caso de diagnóstico concreto es consistente con lo que este establece sobre la solución de problemas.",
        },
    ],
}


def _fake_query_for(mapping: dict[str, dict | None]):
    async def _fake_query(*, prompt, options):
        structured = mapping[prompt]
        if structured is None:
            return
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="test",
            structured_output=structured,
        )

    return _fake_query


def _mapping_for(segment: ContentSegment, levels: dict[int, list[dict]]) -> dict[str, dict]:
    return {_user_prompt(segment, level): {"statements": items} for level, items in levels.items()}


# ─────────────────────────────────────────────────────────────────────────
# Tests con fixtures reales
# ─────────────────────────────────────────────────────────────────────────


def test_theory_candidates_mcm_all_grounded_with_one_cross_level_duplicate():
    mapping = _mapping_for(_MCM_SEGMENT, _MCM_LEVELS)
    fake_query = _fake_query_for(mapping)

    with patch("flashcards_agent.generate.theory.query", new=fake_query):
        candidates = theory_candidates((_MCM_SEGMENT,), "nivelacion-matematica", 1)

    by_level = {1: 0, 2: 0, 3: 0}
    for c in candidates:
        by_level[c.level] += 1
    # Nivel 2 pierde 1: "El m.c.m ... es el mayor número ..." (falsa) es duplicado verbatim
    # del mismo statement en nivel 1 — dedupe acumulado real, no un bug del test.
    assert by_level == {1: 8, 2: 6, 3: 8}
    assert len(candidates) == 22

    for c in candidates:
        assert c.deck == "Nivelación Matemática::Semana 1"
        assert c.fuente == "Nivelación Matemática - Semana 1.pdf, p. 9"
        assert "verificado" in c.tags
        assert "mcm" in c.tags
        assert f"nivel-{c.level}" in c.tags
        assert c.back in ("Verdadero", "Falso")
        assert c.front.startswith("¿Verdadero o falso? ")


def test_theory_candidates_hardware_cross_level_duplicates_discarded(capsys):
    mapping = _mapping_for(_HARDWARE_SEGMENT, _HARDWARE_LEVELS)
    fake_query = _fake_query_for(mapping)

    with patch("flashcards_agent.generate.theory.query", new=fake_query):
        candidates = theory_candidates((_HARDWARE_SEGMENT,), "soporte-sw-hw", 1)

    by_level = {1: 0, 2: 0, 3: 0}
    for c in candidates:
        by_level[c.level] += 1
    # 7 + 7 + 7 crudas, menos 2 duplicados verbatim entre niveles (nivel 2 vs nivel 1, nivel 3 vs nivel 2).
    assert by_level == {1: 7, 2: 6, 3: 6}
    assert len(candidates) == 19

    for c in candidates:
        assert c.deck == "Soporte HW-SW::Semana 1"
        assert "hardware-basico" in c.tags

    captured = capsys.readouterr()
    assert captured.out.count("afirmación duplicada") == 2


# ─────────────────────────────────────────────────────────────────────────
# Casos de borde — mecanismo puro, body sintético (sin juicio pedagógico que validar)
# ─────────────────────────────────────────────────────────────────────────

_SYNTH_BODY = (
    "El protocolo HTTP es un protocolo de comunicación sin estado usado para la "
    "transferencia de hipertexto en la web. Cada solicitud HTTP es independiente de "
    "las solicitudes anteriores, sin memoria de estado entre ellas."
)

_SYNTH_SEGMENT = ContentSegment(
    title="HTTP",
    body=_SYNTH_BODY,
    topic_tag="http",
    flavor="theory",
    source_ref="synthetic.pdf, p. 1",
)


def _good_statement(n: int, level: int) -> dict:
    quotes = [
        "protocolo de comunicación sin estado",
        "usado para la transferencia de hipertexto en la web",
        "Cada solicitud HTTP es independiente de las solicitudes anteriores",
        "sin memoria de estado entre ellas",
        "transferencia de hipertexto en la web",
        "Cada solicitud HTTP es independiente",
        "protocolo de comunicación sin estado usado",
        "las solicitudes anteriores, sin memoria de estado",
    ]
    return {
        "statement": f"Afirmación sintética grounded número {n} (nivel {level}).",
        "truth_value": True,
        "evidence_quote": quotes[n % len(quotes)],
        "explanation": "sintético",
    }


def _uniform_levels(n_per_level: int) -> dict[int, list[dict]]:
    return {level: [_good_statement(i, level) for i in range(n_per_level)] for level in (1, 2, 3)}


def test_theory_candidates_skips_non_theory_flavor_without_sdk_call():
    segments = (
        ContentSegment(title="x", body=_SYNTH_BODY, topic_tag="x", flavor="practice", source_ref="s, p.1"),
        ContentSegment(title="x", body=_SYNTH_BODY, topic_tag="x", flavor="discard", source_ref="s, p.2"),
    )

    async def _fail_if_called(*, prompt, options):
        raise AssertionError("no debería llamarse al SDK para flavor != 'theory'")
        yield  # pragma: no cover

    with patch("flashcards_agent.generate.theory.query", new=_fail_if_called):
        candidates = theory_candidates(segments, "soporte-sw-hw", 1)

    assert candidates == ()


def test_theory_candidates_empty_segments_returns_empty_without_sdk_call():
    async def _fail_if_called(*, prompt, options):
        raise AssertionError("no debería llamarse al SDK con segments vacío")
        yield  # pragma: no cover

    with patch("flashcards_agent.generate.theory.query", new=_fail_if_called):
        candidates = theory_candidates((), "soporte-sw-hw", 1)

    assert candidates == ()


def test_theory_candidates_skips_short_body_without_sdk_call(capsys):
    short_segment = ContentSegment(
        title="x", body="muy corto", topic_tag="x", flavor="theory", source_ref="synthetic.pdf, p. 9"
    )

    async def _fail_if_called(*, prompt, options):
        raise AssertionError("no debería llamarse al SDK con un body demasiado corto")
        yield  # pragma: no cover

    with patch("flashcards_agent.generate.theory.query", new=_fail_if_called):
        candidates = theory_candidates((short_segment,), "soporte-sw-hw", 1)

    assert candidates == ()
    captured = capsys.readouterr()
    assert "synthetic.pdf, p. 9" in captured.out
    assert "demasiado corto" in captured.out


def test_theory_candidates_discards_ungrounded_and_keeps_rest(capsys):
    levels = _uniform_levels(5)
    # En nivel 1, la afirmación 0 trae una cita inventada, ausente del pasaje.
    levels[1][0] = {
        "statement": "Afirmación con evidencia inventada.",
        "truth_value": True,
        "evidence_quote": "una cita completamente inventada que no aparece en el pasaje",
        "explanation": "sintético",
    }
    mapping = _mapping_for(_SYNTH_SEGMENT, levels)
    fake_query = _fake_query_for(mapping)

    with patch("flashcards_agent.generate.theory.query", new=fake_query):
        candidates = theory_candidates((_SYNTH_SEGMENT,), "soporte-sw-hw", 1)

    level1 = [c for c in candidates if c.level == 1]
    assert len(level1) == 4  # 5 generadas, 1 descartada por grounding
    captured = capsys.readouterr()
    assert "synthetic.pdf, p. 1" in captured.out
    assert "la evidencia no aparece en el pasaje fuente" in captured.out


def test_theory_candidates_captures_runtime_error_per_level_and_continues():
    levels = _uniform_levels(5)
    mapping = _mapping_for(_SYNTH_SEGMENT, levels)
    # Nivel 2 no devuelve structured_output -> generate_statements levanta RuntimeError.
    mapping[_user_prompt(_SYNTH_SEGMENT, 2)] = None
    fake_query = _fake_query_for(mapping)

    with patch("flashcards_agent.generate.theory.query", new=fake_query):
        candidates = theory_candidates((_SYNTH_SEGMENT,), "soporte-sw-hw", 1)

    by_level = {c.level for c in candidates}
    assert by_level == {1, 3}
    assert len([c for c in candidates if c.level == 1]) == 5
    assert len([c for c in candidates if c.level == 3]) == 5


def test_theory_candidates_keeps_all_grounded_above_reference_floor():
    # 5-8 es un piso de referencia, no un techo (TDD §4.5.1, revisión 2026-08-09, IPL-30): si
    # el pasaje rinde más de 8 afirmaciones grounded y no-duplicadas, NINGUNA se descarta.
    levels = _uniform_levels(5)
    levels[1] = [_good_statement(i, 1) for i in range(10)]
    mapping = _mapping_for(_SYNTH_SEGMENT, levels)
    fake_query = _fake_query_for(mapping)

    with patch("flashcards_agent.generate.theory.query", new=fake_query):
        candidates = theory_candidates((_SYNTH_SEGMENT,), "soporte-sw-hw", 1)

    level1 = [c for c in candidates if c.level == 1]
    assert len(level1) == 10


def test_theory_candidates_warns_when_below_min_after_survivors(capsys):
    levels = _uniform_levels(5)
    levels[1] = [_good_statement(i, 1) for i in range(3)]
    mapping = _mapping_for(_SYNTH_SEGMENT, levels)
    fake_query = _fake_query_for(mapping)

    with patch("flashcards_agent.generate.theory.query", new=fake_query):
        candidates = theory_candidates((_SYNTH_SEGMENT,), "soporte-sw-hw", 1)

    level1 = [c for c in candidates if c.level == 1]
    assert len(level1) == 3
    captured = capsys.readouterr()
    assert "solo 3 candidatos sobrevivieron" in captured.out


def test_theory_candidates_omits_empty_topic_tag(capsys):
    segment = ContentSegment(
        title="x", body=_SYNTH_BODY, topic_tag="", flavor="theory", source_ref="synthetic.pdf, p. 1"
    )
    levels = _uniform_levels(5)
    mapping = _mapping_for(segment, levels)
    fake_query = _fake_query_for(mapping)

    with patch("flashcards_agent.generate.theory.query", new=fake_query):
        candidates = theory_candidates((segment,), "soporte-sw-hw", 1)

    assert len(candidates) == 15
    for c in candidates:
        assert "" not in c.tags
        assert "verificado" in c.tags
        assert f"nivel-{c.level}" in c.tags
    captured = capsys.readouterr()
    assert captured.out.count("topic_tag vacío") == 15


def test_theory_candidates_warns_when_level_is_truth_value_uniform(capsys):
    levels = _uniform_levels(5)  # _good_statement() siempre produce truth_value=True
    mapping = _mapping_for(_SYNTH_SEGMENT, levels)
    fake_query = _fake_query_for(mapping)

    with patch("flashcards_agent.generate.theory.query", new=fake_query):
        candidates = theory_candidates((_SYNTH_SEGMENT,), "soporte-sw-hw", 1)

    level1 = [c for c in candidates if c.level == 1]
    assert len(level1) == 5
    assert all(c.back == "Verdadero" for c in level1)
    captured = capsys.readouterr()
    assert captured.out.count("nivel pedagógicamente trivial") == 3  # los 3 niveles son uniformes


def test_generate_statements_raises_runtime_error_without_structured_output():
    from flashcards_agent.generate.theory import generate_statements

    async def _no_result(*, prompt, options):
        return
        yield  # pragma: no cover

    with (
        patch("flashcards_agent.generate.theory.query", new=_no_result),
        pytest.raises(RuntimeError),
    ):
        generate_statements(_SYNTH_SEGMENT, 1)
