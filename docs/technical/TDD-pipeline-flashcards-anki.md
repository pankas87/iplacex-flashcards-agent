# TDD — Pipeline de generación de flashcards Anki para autoestudio

> Documento de diseño (TDD/RFC) del bucle macro de Ironspec AI (§6.1). Este documento se
> *shapea* a la altura correcta y de él se derivan, en el ciclo siguiente, las decisiones
> (ADR) y las SPEC-EXEC que ejecuta Claude Code con Spec Kit (Spec → Plan → Tasks →
> Implement). **No contiene SPEC-EXEC ni ADRs** — son el output de la etapa siguiente.

**Estado:** shaping cerrado — pasa la Definition of Shapeable (§6.4, verificación al final de
este documento).
**Enmendado 2026-08-06 por [ADR-0002](../adr/0002-ejercicios-desde-fuentes-externas-curadas.md)**
— §2.2, §2.5, §4.2, §4.5.2, §4.6 y §5.2 US-3 fueron revisados: el sub-pipeline práctico pasa de
"generar todo por LLM" a "usar ejercicios de fuentes externas curadas, con generación por LLM
como fallback". Las secciones afectadas lo señalan inline.
**Enmendado 2026-08-07 por [ADR-0003](../adr/0003-jerarquia-de-fuentes-para-ejercicios-practicos.md)**
— tras inspeccionar el material real, el sub-pipeline práctico pasa a una **jerarquía de tres
niveles**: (1) ejercicios del material propio del curso, (2) fuentes externas curadas,
(3) generación por LLM. ADR-0002 no se revierte: su mecanismo de curación externa sigue vigente,
baja de nivel 1 a nivel 2.
**Appetite:** 1 semana para el build inicial (§1.3, fase 1). La funcionalidad de corrección de
cards (§2.6) tiene su propio appetite de semana 2 y está fuera de este documento salvo como
idea general registrada.

---

## 1. Problemática / necesidad

### 1.1 Estado actual

Cursando Ingeniería en Ciberseguridad en IPLACEX (modalidad bimestral), 3ra semana de clases.
El primer examen de cada asignatura del bimestre se disponibiliza la semana que viene. Todo el
material del bimestre — seis semanas de contenido por materia, en Nivelación Matemática y
Soporte en Software y Hardware — ya está publicado de una vez; no llega incrementalmente
semana a semana como en un curso típico.

Hoy, sin ningún sistema de repetición espaciada armado sobre este material, el estudio consiste
en resolver los ejercicios con el PDF a mano al lado para autovalidar la respuesta contra la
clave. No hay mecanismo de repaso distribuido en el tiempo: la exposición al contenido es una
sola pasada, y lo que no se retiene en esa pasada no vuelve a aparecer hasta que el estudiante
decida releerlo por su cuenta.

### 1.2 Por qué cargar Anki a mano no alcanza

Cargar dos materias × seis semanas de contenido en Anki a mano es fricción suficiente para
abandonar el sistema antes de que la repetición espaciada empiece a pagar dividendos — el
costo de entrada mata la adopción antes de generar valor. Es exactamente el patrón que
justifica automatizar en vez de simplemente "usar Anki": el problema no es la herramienta, es
el costo de poblarla a mano sobre seis semanas de material heterogéneo por materia.

### 1.3 Alcance del dolor que este documento ataca

- **Fase 1 (appetite: 1 semana).** Semanas 1-2 de Nivelación Matemática y de Soporte SW-HW,
  listas antes del examen de la semana próxima.
- **Fase 2 (modo estable, sin fecha límite dura).** Procesamiento incremental on-demand,
  semana a semana, para las semanas 3-6 restantes del bimestre y las materias que se sumen en
  bimestres futuros. El pipeline construido en fase 1 debe soportar esto sin rediseño — es
  parte de por qué la arquitectura de agente + taxonomía se fija ahora y no se pospone.

### 1.4 Fuera de alcance (explícito)

- Actividades prácticas hands-on (instalación de software, configuración de red con capturas
  de pantalla, autoevaluación tipo Likert). No son preguntables como flashcard sin
  reinterpretarlas por completo — quedan fuera de la generación automática.
- Corrección de cards existentes vía agente conversacional — diferido a semana 2 (§2.6).
- Cualquier materia más allá de las dos del bimestre actual.
- Procesamiento de contenido embebido como figura (diagramas, capturas) más allá de
  detectarlo y avisarlo — parking lot, ver §4.4.

---

## 2. Alternativas evaluadas

Las decisiones ya fijadas (mono-perfil, taxonomía `Materia::Unidad`) **no** aparecen acá — no
están en discusión; se documentan como decisiones fijadas directamente en §4.

### 2.1 Formato de entrega a Anki: genanki (.apkg) vs. AnkiConnect (API HTTP)

| | genanki | AnkiConnect |
|---|---|---|
| Mecanismo | Genera `.apkg` offline | API HTTP sobre el perfil activo |
| Fricción recurrente | Import manual cada corrida | Inserción directa, sin paso manual |
| Dedup pre-inserción | No — hay que resolverlo aparte | `canAddNotes` antes de insertar |

**Elegida: AnkiConnect.** El flujo es recurrente (semana a semana, fase 2), así que el costo de
reimportar `.apkg` a mano se paga una y otra vez con genanki. AnkiConnect lo elimina y además
habilita dedup en el momento de la inserción, no como paso separado.

### 2.2 Origen de los ejercicios prácticos

> **Historial de enmiendas.** La versión original evaluaba dos opciones (extraer del material
> propio vs. generar por LLM) y elegía **generación**.
> [ADR-0002](../adr/0002-ejercicios-desde-fuentes-externas-curadas.md) (2026-08-06) incorporó
> una tercera — **fuentes externas curadas** — como vía primaria.
> [ADR-0003](../adr/0003-jerarquia-de-fuentes-para-ejercicios-practicos.md) (2026-08-07), tras
> inspeccionar el material real, **rehabilitó la extracción del material propio** y la puso en
> primer lugar. El texto de abajo es la versión vigente.

| | Material propio del curso | Fuentes externas curadas | Generación por LLM |
|---|---|---|---|
| Fidelidad del enunciado | Alta — redactado por el docente de la asignatura | Alta — redactado por un tercero con intención pedagógica | Depende de que el agente formule bien |
| Fidelidad de la respuesta | **No se confía** — se recomputa en Python (§4.6) | **No se confía** — se recomputa en Python (§4.6) | **No se confía** — se recomputa en Python (§4.6) |
| Calibración al examen real | **Máxima** — es el material que evalúa la asignatura | Media — buen ejercicio, pero no calibrado al criterio del curso | Media — sigue el patrón del material, sin validación docente |
| Cobertura | Limitada al volumen de cada semana (y no todas traen `EJ_*.docx`) | Amplia — muchos sitios por tema | Superset amplio, sin techo natural |
| Riesgo principal | Pareo enunciado↔clave posicional (mitigado: un desajuste se detecta, no se inserta) | Deriva de tema y fragilidad del scraping | Alucinación en el contenido generado (§2.3) |

**Elegida: jerarquía de tres niveles** — material propio → externo curado → generación por LLM,
en ese orden de preferencia por aprendizaje esperado, bajando de nivel solo cuando el anterior
no rinde un ejercicio adecuado (detalle operativo en §4.5.2).

El criterio que ordena la jerarquía es la **calibración al examen real**, que es el objetivo
declarado del proyecto (§1.1, §1.3): los ejercicios del propio curso son los que mejor predicen
cómo evalúa la asignatura. Los niveles 2 y 3 existen porque el nivel 1 tiene techo — no todas
las semanas traen archivo de ejercicios (ej. Nivelación Matemática 3-6 no lo trae).

En **los tres** niveles, la respuesta se recomputa de forma independiente en Python antes de
insertar (§2.3, §4.6). Ni la clave `R_*.pdf` del curso ni la respuesta publicada por un sitio
externo se toman como verdad — son insumo de contraste. Eso es lo que hace que sumar orígenes
no sume clases de riesgo sobre el *resultado*: solo sobre la *selección* del ejercicio.

### 2.3 Verificación de contenido matemático generado: cómputo determinístico vs. confiar en el LLM

| | Confiar en el LLM | Tool de cómputo en Python |
|---|---|---|
| Certeza del resultado | El LLM no está diseñado para aritmética exacta | Determinística — el resultado es correcto por construcción |
| Costo de build | Cero | Bajo — los algoritmos (mcm, mcd, operatoria básica) son simples de codificar |
| Cobertura | Todo tipo de contenido | Solo lo computable; V/F conceptual queda fuera |

**Elegida: híbrida.** Tool en Python para contenido matemático verificable (mcm, mcd, operatoria
con enteros y fracciones), grounding explícito contra el campo `fuente` para contenido
conceptual/V/F donde no hay cómputo determinístico posible sobre lenguaje.

### 2.4 Esquema de trazabilidad: tag único `#generado` vs. campos separados `fuente` + `verificado`

Ninguna card se transcribe literal del material del curso: o se genera, o se toma de una fuente
externa y se normaliza. Un tag binario "generado sí/no" no discrimina nada útil en ese universo.

**Elegida:** dos campos distintos — `fuente` (puntero de trazabilidad, no fidelidad literal) y
`verificado` (tag, si la respuesta pasó verificación explícita antes de insertarse).

> **Nota 2026-08-06 ([ADR-0002](../adr/0002-ejercicios-desde-fuentes-externas-curadas.md)).**
> La redacción original de esta sección se apoyaba en que "prácticamente el 100% de las cards
> son generadas", premisa que la enmienda vuelve falsa (ahora una parte viene de fuentes
> externas). La **conclusión no cambia** — de hecho se refuerza: el origen de cada card
> (externo vs. generado) ya queda discriminado por el propio `fuente`, que apunta a una URL o
> al material canónico según el caso (§2.5). No hace falta un tag adicional para eso.

### 2.5 Fuente en el backside: puntero vs. cita textual

| | Puntero (ref. a sección/página) | Cita textual breve |
|---|---|---|
| Costo de generación | Bajo | Más caro, requiere recortar bien |
| Riesgo de desincronía | Ninguno — no copia nada | Puede desalinearse si el material cambia de versión |
| Efecto en el estudio | Obliga a volver al material original para validar | Se valida sin salir de Anki |

**Elegida: puntero.** Además de ser más liviano de generar, el efecto de forzar volver al
material original es deseado — refuerza el repaso en sí mismo, no es solo trazabilidad técnica.

> **Enmienda 2026-08-06/07 ([ADR-0002](../adr/0002-ejercicios-desde-fuentes-externas-curadas.md),
> [ADR-0003](../adr/0003-jerarquia-de-fuentes-para-ejercicios-practicos.md)) — `fuente` tiene
> cuatro casos, no uno.** La decisión de "puntero, no cita" no cambia; lo que cambia es **a
> dónde** apunta, según el origen de la card:
>
> | Origen de la card | `fuente` apunta a |
> |---|---|
> | Ejercicio del material propio (nivel 1, §4.5.2) | Archivo + n° de ejercicio (ej. `Mate - Semana 1 - EJ_1.1.docx, ej. 13`) |
> | Ejercicio de fuente externa curada (nivel 2, §4.5.2) | La **URL** del ejercicio original |
> | Ejercicio generado por LLM (nivel 3, §4.5.2) | Sección/página del material canónico |
> | Card teórica / V-F (§4.5.1) | Sección/página del material canónico |
>
> En el caso de fuente externa se pierde el efecto de "volver al material propio" que motivó la
> decisión original, y se gana atribución explícita del ejercicio de terceros — que es lo
> correcto cuando el enunciado no es propio. En los otros tres casos el efecto original se
> mantiene intacto. Sigue siendo puntero y no cita textual en todos los casos.

### 2.6 Corrección de cards existentes — parking lot / fuera de alcance en v1

AnkiConnect soporta localizar (`findNotes` + `notesInfo`) y corregir (`updateNoteFields`) una
nota sin resetear su historial de repaso ni su programación SM-2 — editar contenido es seguro,
Anki solo pierde el historial si se resetea la card explícitamente.

Hay una alternativa real sin resolver todavía: **corrección vía agente conversacional**
("Claude, corregí la card sobre tal cosa") vs. **edición manual directa en Anki** (ya existe,
cero trabajo de build, pero saca del flujo conversacional). Queda **fuera de alcance para v1**
— excede el appetite de la semana 1. Se retoma en semana 2 de desarrollo, cuando el mecanismo
de validación contra `fuente` (§2.5) empiece a encontrar errores reales que corregir.

### 2.7 Interfaz del agente: loop persistente vs. invocación puntual por comando

| | Loop persistente | Invocación puntual (proceso por comando) |
|---|---|---|
| Arranque en frío | Se paga una sola vez al iniciar el loop | Se repaga en cada comando |
| Contexto de sesión | Se mantiene en memoria entre comandos | Hay que reconstruirlo cada vez |
| Robustez a fallos | Un proceso colgado bloquea toda la sesión | Un fallo no afecta a comandos futuros |

**Elegida: loop persistente.** Evita repagar el arranque del agente (autenticación, carga de
contexto) en cada comando y mantiene contexto de sesión (qué ya se procesó en esta corrida) sin
reconstruirlo. El costo — un proceso zombie si algo cuelga — se acepta dado el contexto de uso
personal, no concurrente.

---

## 3. Lo que se gana al automatizar

### 3.1 Valor por-ticket (cada sesión de estudio)

| Dolor | Cómo lo resuelve el pipeline | Prueba |
|---|---|---|
| Sin cobertura de todo el material antes del examen | Superset por aprendizaje esperado/subsección × nivel de dificultad, alimentado por la jerarquía de tres niveles — material propio, fuentes externas curadas, generación por LLM (§4.5.2) — así ninguna subsección queda sin cards por falta de ejercicios en el material | % de aprendizajes esperados de semana 1-2 con al menos N cards insertadas |
| Costo de poblar Anki a mano | Ingesta automática desde PDF/DOCX + inserción vía AnkiConnect | Tiempo de carga por semana de material < tiempo que tomaría cargar a mano |
| Respuestas matemáticas generadas potencialmente erróneas | Tool de verificación determinística en Python antes de insertar | 100% de las cards con tag `verificado` tienen resultado confirmado por cómputo, no solo por el LLM |
| Dificultad de validar contra el original al repasar | Campo `fuente` como puntero en el backside de cada card | Toda card insertada tiene `fuente` no vacío |

### 3.2 Valor estructural (a lo largo del bimestre/carrera)

| Pilar | Qué incluye | Mecanismo |
|---|---|---|
| Historial de repaso unificado | Un solo perfil, un solo dashboard, sin fragmentar por materia o bimestre | Mono-perfil *(decisión fijada, §4.1)* |
| Filtrado cruzado por tema | Repasar "todo lo de mcm" o "todo lo de redes" sin importar en qué unidad o materia apareció | Tema como tag, no como submazo *(decisión fijada, §4.4)* |
| Pipeline reutilizable | La arquitectura del agente no se rediseña cuando entra la próxima materia o bimestre | Clasificación + generación desacopladas del contenido específico de una materia |
| Independencia del volumen de material | El appetite de una semana escala a semanas siguientes sin reconstruir el sistema | Modo incremental on-demand (§1.3, fase 2) ya contemplado en el diseño inicial |

---

## 4. Comportamiento esperado del sistema

### 4.1 Configuración Anki + AnkiConnect

- **Mono-perfil *(decisión fijada)*.** Un solo perfil Anki para toda la carrera —no uno por
  materia ni por bimestre. AnkiConnect opera sobre el perfil activo; no hace falta `loadProfile`
  en el flujo normal porque no hay múltiples perfiles en juego.
- **Networking WSL ↔ Windows.** Anki + AnkiConnect corren en Windows; el agente corre en WSL
  Ubuntu. Dos vías, en orden de preferencia:
  1. **Mirrored networking mode** de WSL2 (si la versión de Windows/WSL lo soporta) —
     localhost en WSL resuelve directo al host, sin configuración adicional en AnkiConnect.
  2. **Fallback:** `webBindAddress` de AnkiConnect configurado para escuchar en todas las
     interfaces (no solo loopback), y el agente en WSL resolviendo la IP del host Windows
     (vía `/etc/resolv.conf` o `ip route show default`) en vez de `localhost`.
- **Riesgo nombrado:** instalación del plugin AnkiConnect en sí — falla de instalación o de
  arranque del servidor HTTP bloquea todo el pipeline aguas abajo. Se verifica con un healthcheck
  simple (`version` request) antes de cualquier operación de escritura.
- **Instrucción de implementación — script de validación + invocación canónica.** La
  verificación de conectividad (`version` request a AnkiConnect) se implementa como un script
  Python standalone (ej. `scripts/anki_healthcheck.py`), invocable manualmente vía un target de
  `justfile` (ej. `just anki-check`) — no como código ad-hoc reinventado en cada sesión de
  desarrollo. El agente reutiliza esta misma lógica para el healthcheck que corre antes de
  cualquier operación de escritura (no la duplica — un solo punto de verdad para "¿está viva la
  conexión?"). Este es de los primeros artefactos de tooling que Claude Code crea en el setup,
  antes que cualquier otra pieza del pipeline, porque todo lo demás depende de poder confirmar
  que Anki+AnkiConnect están arriba. El `justfile` queda así establecido como la fuente única de
  comandos de entorno de este proyecto — cualquier operación futura sobre el entorno (no solo el
  healthcheck) se agrega como target nuevo del mismo `justfile`, no como comando suelto.

### 4.2 Arquitectura del agente

Agente construido sobre Claude Agent SDK, corriendo en WSL Ubuntu.

**Tools:**
- Lector de PDF/DOCX (ingesta de material fuente).
- **Búsqueda web + fetch de páginas de ejercicios** — alimenta la curación de fuentes externas
  y la recolección de ejercicios por tema (§4.5.2, [ADR-0002](../adr/0002-ejercicios-desde-fuentes-externas-curadas.md)).
- Tool de verificación matemática — cómputo determinístico en Python (mcm, mcd, operatoria con
  enteros y fracciones) independiente del LLM.
- Cliente AnkiConnect (`canAddNotes`, `addNotes`, `deckNames`, `version` para healthcheck).

**Selección de modelo por tarea (§4.5 de Ironspec):**

| Tarea | Modelo | Por qué |
|---|---|---|
| Clasificación de contenido (qué sabor es, qué tema/tag corresponde) | Ligero (Haiku) | Tarea acotada, respuesta estrecha |
| Selección/normalización de ejercicio desde fuente externa (¿calza con el aprendizaje esperado? extraer enunciado limpio del HTML) | Ligero-balanceado | Tarea de juicio acotado sobre texto ya escrito, no de redacción original |
| Generación de contenido pedagógico (enunciados, preguntas V/F, explicaciones) | Balanceado (Sonnet) | Requiere calidad de redacción y coherencia pedagógica |
| Resolución matemática | No es el LLM — tool Python (§4.6) | El LLM no está diseñado para aritmética exacta |

### 4.3 Interfaz — CLI en loop

Loop persistente en WSL (§2.7). Dispatch en dos niveles:

1. **Comandos conocidos** (gramática finita, dispatch determinístico, sin pasar por el modelo).
2. **Fallback a lenguaje natural** — si el input no matchea la gramática conocida, cae al mismo
   agente que ya corre para generación (no una capa de NLU aparte).

Este documento fija la **arquitectura de alto nivel de los comandos** — qué comandos se prevén
necesarios — sin congelar nombres, flags ni contratos de parámetros exactos. Esa definición
final es trabajo de Claude Code al bajar este documento a SPEC-EXEC, usando el requerimiento en
Gherkin (§5) más su propio conocimiento del Claude Agent SDK (y herramientas disponibles en ese
contexto, como el servidor MCP de Context7 para consultar documentación del SDK).

Comandos previstos, a alto nivel:
- Procesar/generar flashcards para `<materia> <semana>`.
- Consultar estado (qué se generó, qué está pendiente).
- Listar materias/semanas disponibles.
- Salir.

### 4.4 Ingesta y clasificación de contenido

- **Taxonomía `Materia::Unidad` *(decisión fijada)*.** Dos niveles fijos de mazo — ejemplo:
  `Nivelación Matemática::Semana 1`, `Soporte HW-SW::Unidad 1`. Sin tercer nivel de mazo para
  tema. El tema específico (mcm, enteros, síntoma-diagnóstico, software de sistema, etc.) va
  como **tag**, no como submazo — permite filtrar por tema cruzando materias/unidades sin
  fragmentar la jerarquía de mazos.
- **Riesgos nombrados en la lectura de fuente:** contenido embebido como figura (ej. los árboles
  de factorización de mcm/mcd en Nivelación Matemática) puede perderse en una extracción de
  texto plana; variación de formato y caracteres entre PDF y DOCX.
- **Fuera de alcance explícito de la clasificación:** actividades prácticas hands-on y pautas de
  autoevaluación tipo Likert (§1.4) — el clasificador las descarta, no las envía a generación.

> **Parking lot 2026-08-07 — procesamiento de figuras, diferido, no la detección.** El riesgo
> de arriba se evaluó con datos, no solo de la inspección de un documento (validación de
> ADR-0003, Nivelación Matemática): el desarrollador, como estudiante real de Soporte SW-HW
> semanas 1-2, confirma que las imágenes contienen contenido relevante en **casos puntuales**
> (diagramas), pero el grueso de las explicaciones vive en el texto. La v1 **no construye**
> render-a-imagen ni fallback de visión — es una pieza de arquitectura cara (toca §4.2, tabla
> de modelos) para un riesgo acotado, no el caso general.
>
> **Comportamiento de v1:** `ingest/reader.py` ya captura `image_count` por página
> (SPEC-1-IT2). Cuando una página de contenido (no portada/contratapa) tiene poco texto y
> imágenes, se **detecta y se avisa** (`output.warn`), no se para el pipeline completo ni se
> intenta OCR/visión — la página se procesa con el texto que tenga, aunque quede incompleta.
> Esto no contradice "detener e informar" (`CLAUDE.md`): esa regla aplica cuando un **documento
> entero** no produce texto extraíble limpio, no cuando una página puntual dentro de un
> documento por lo demás legible tiene una figura.
>
> **Cuándo se retoma:** si el aviso de páginas figura-pesadas se vuelve frecuente al procesar
> Soporte SW-HW semanas 3-6 (todavía no inspeccionadas), o si el estudiante nota huecos de
> cobertura reales al repasar, es candidato a ADR — recién ahí, con evidencia de volumen, no
> antes.

### 4.5 Generación de contenido — dos sub-pipelines

**4.5.1 Teórico / teórico-práctico.** Toma el contenido de los PDF de material de estudio como
fuente canónica y los patrones de formulación de pregunta que ya aparecen en el material (ej.
las afirmaciones V/F de Soporte: *"El software de sistema es responsable únicamente de las
funciones relacionadas con la conectividad a internet"* → patrón de afirmación falsable sobre
una definición). Genera un superset por **aprendizaje esperado / subsección** del material, con
**3 niveles de dificultad × 5-8 cards por nivel**.

> **Aclaración de alcance 2026-08-08.** Este sub-pipeline es agnóstico de materia: aplica igual
> a las definiciones/conceptos de Nivelación Matemática (ej. la definición de m.c.m/m.c.d que
> `classify/segmenter.py` ya segmenta y tagea `flavor="theory"`, IPL-26) que al contenido
> conceptual de Soporte SW-HW. **No implica que Nivelación Matemática se cubra solo con
> ejercicios prácticos** — ver la nota en §5.1 sobre el hueco de cobertura actual en el roadmap.

> **Parking lot 2026-08-08 — cards de selección múltiple, fuera de alcance en v1.** v1 del
> sub-pipeline teórico genera exclusivamente el patrón V/F (afirmación falsable, TDD original).
> Selección múltiple — con una única opción correcta o con más de una — es un patrón de
> pregunta distinto: cambia el note type de Anki (campos de opciones + cuáles son correctas,
> no un booleano), el prompt de generación (hay que producir distractores plausibles, no solo
> una afirmación y su valor de verdad) y el grounding de verificación (contrastar cada opción
> contra `fuente`, no solo una afirmación). No se implementa en v1 por appetite — es una
> extensión real de superficie, no un ajuste menor a V/F. **Se retoma en una pasada futura**
> (candidato natural: cuando se aborde la Fase 2 de generación teórica, §5.1) como una
> ampliación explícita del note type y de `generate/` — no anticipar el diseño ahora.

**4.5.2 Práctico.** *(Reescrita 2026-08-07 —
[ADR-0003](../adr/0003-jerarquia-de-fuentes-para-ejercicios-practicos.md), que enmienda
[ADR-0002](../adr/0002-ejercicios-desde-fuentes-externas-curadas.md).)* **Jerarquía de tres
niveles** por aprendizaje esperado. Se intenta el nivel 1; solo si no rinde un ejercicio
adecuado se baja al 2, y luego al 3. Todos terminan en la misma verificación.

**Nivel 1 — Ejercicios del material propio del curso.** El material de cada semana puede traer
un archivo de ejercicios (`EJ_*.docx`) con su clave de respuestas (`R_*.pdf`). Es la vía
preferida: son los ejercicios que mejor predicen el examen real de la asignatura (§2.2).

> **Detalle de implementación que el pareo debe respetar** (observado en el material real,
> Nivelación Matemática Semana 1): los enunciados del DOCX son **párrafos planos sin
> numeración textual** — la numeración es formato de Word, no caracteres extraíbles — mientras
> que la clave del PDF **sí trae números explícitos** (`1.`, `2.`, `3.`…). El pareo
> enunciado↔respuesta es por **posición**, no por número extraído del enunciado. Si el conteo
> de enunciados y el de respuestas no coinciden, **detener e informar** (§7): no parear a
> ciegas. El costo de un pareo silenciosamente corrido es una card con la respuesta de otro
> ejercicio.

**Nivel 2 — Fuentes externas curadas por tema.** Cuando el nivel 1 no cubre el aprendizaje
esperado, o la semana no trae archivo de ejercicios (ej. Nivelación Matemática 3-6). Dos fases:

- *Curación (una vez por tema, no por corrida).* Se arma una lista de sitios con ejercicios
  buenos para cada tema (mcm, mcd, fracciones, …). Semilla: la **bibliografía que cada unidad
  trae al final de su material** — punto de partida autorizado por la propia asignatura; el
  material además **cita fuentes inline** a lo largo del texto, que sirven igual de semilla.
  Desde ahí se amplía con búsqueda web. El resultado es un **artefacto durable** (lista curada
  tema → fuentes), no un resultado de búsqueda efímero: hace las corridas repetibles y evita
  scrapear sitios arbitrarios cada semana.
- *Recolección y selección.* El agente trae candidatos desde las fuentes curadas del tema,
  extrae el enunciado limpio del HTML, y descarta los que no calzan con el aprendizaje esperado
  concreto (deriva de tema — riesgo de §2.2).

> **Contrato abierto — dónde vive la lista curada y con qué formato.** No se fija en este
> documento: se define en la SPEC-EXEC que implemente esta fase. Lo que sí queda fijado acá es
> que **tiene que ser un artefacto durable y versionado**, no estado en memoria del agente.

**Nivel 3 — Generación por LLM.** Si ninguno de los dos anteriores rinde un ejercicio adecuado,
el agente genera uno nuevo siguiendo el patrón de los ejercicios del material: ejemplo de patrón
de Nivelación Matemática Semana 1 (el problema de "los viajeros" de mcm) — enunciado con dos
eventos periódicos que coinciden en el tiempo, pide cuándo vuelven a coincidir; el agente
produce una variante nueva (otros números, otro contexto narrativo).

**Verificación — común a los tres niveles.** La tool de Python resuelve el ejercicio de forma
independiente (§4.6). Ni la clave `R_*.pdf` del curso ni la respuesta publicada por un sitio
externo se usan como respuesta: son insumo de contraste. La que va a la card es siempre la de
Python.

**Riesgos nombrados de esta vía:**
- **Pareo posicional en el nivel 1** — ver el detalle de implementación arriba. Mitigación: un
  desajuste de conteo detiene e informa; y aunque el pareo fallara, la verificación por cómputo
  produce un desacuerdo detectable en vez de una card incorrecta.
- **Deriva de tema** — un ejercicio del sitio correcto puede igual no corresponder al
  aprendizaje esperado específico. Mitigación: el paso de selección del nivel 2 es explícito,
  no implícito.
- **Fragilidad del scraping** — el HTML de cada sitio es distinto y puede cambiar. Mitigación
  parcial: la lista curada es chica y conocida, no un scraper genérico de la web abierta.
- **Envejecimiento de la lista curada** — un sitio puede caerse o cambiar. Se detecta al fallar
  la recolección; la lista es un artefacto editable, no código.
- **Atribución de ejercicios de terceros** — se resuelve con el campo `fuente` apuntando a la
  URL de origen (§2.5) y con el uso estrictamente personal del sistema (no se redistribuye ni
  se publica el mazo). Ver ADR-0002, "Consecuencias".

### 4.6 Verificación pre-inserción

- **Contenido matemático** *(actualizado 2026-08-06,
  [ADR-0002](../adr/0002-ejercicios-desde-fuentes-externas-curadas.md))*: la tool de cómputo
  en Python es **la única autoridad sobre la respuesta**, sea cual sea el origen del enunciado:
  - *Ejercicio de fuente externa:* la respuesta publicada por el sitio **no se confía**. Python
    resuelve el enunciado de forma independiente. Si el sitio publica una respuesta y **no
    coincide** con la de Python, se descarta el ejercicio entero (no se "corrige" ni se inserta
    con la respuesta de Python): un desacuerdo indica que el enunciado se extrajo mal o que el
    problema tiene condiciones que no se capturaron. Se pasa al siguiente candidato.
  - *Ejercicio generado por LLM (fallback):* el agente produce enunciado + solución candidata;
    Python resuelve el mismo problema; solo se inserta si coinciden. Si no, se descarta y se
    regenera.
  - En ningún caso se inserta contenido matemático sin que Python haya confirmado el resultado.
- **Contenido conceptual/V/F:** no hay cómputo determinístico posible sobre lenguaje. Mitigación:
  grounding explícito — la afirmación generada y su valor de verdad se contrastan contra el
  pasaje específico del `fuente` referenciado, no se generan libremente.
- Ambos casos, si pasan verificación, se marcan con el tag `verificado`.

### 4.7 Diseño de la nota (note type)

- **Front:** enunciado o afirmación generada.
- **Back:** solución/respuesta + campo `fuente` como puntero (sección/página del material
  canónico, §2.5) — no cita textual.
- **Deck:** `Materia::Unidad` *(decisión fijada, §4.4)*.
- **Tags:** tema específico (ej. `mcm`, `software-sistema`) + `verificado` cuando aplica (§2.4,
  §4.6). Para cards teóricas del superset (§4.5.1, US-5), suma un tag `nivel-N` (`nivel-1` /
  `nivel-2` / `nivel-3`) que identifica el nivel de dificultad — sigue siendo tag, no crea un
  tercer nivel de mazo (§4.4 intacto). *(Aclaración 2026-08-09, IPL-30.)*

### 4.8 Dedup e inserción

`canAddNotes` contra el conjunto de notas a insertar antes de llamar `addNotes` — evita
duplicados dentro de una misma corrida y contra el estado ya existente del mazo.

---

## 5. Descomposición en user stories

Relación story:spec 1..n (§7.2 de Ironspec) — cada story puede derivar en una o más SPEC-EXEC
en el ciclo de Claude Code.

### 5.1 Priorización — orden de corte para el appetite de 1 semana

1. **US-1 a US-4** (incluyendo US-3b) — setup + pipeline mínimo end-to-end en una sola
   materia/semana (Nivelación Matemática, Semana 1), para validar el pipeline completo con los
   riesgos técnicos más nuevos (verificación matemática y sourcing externo) antes de escalar.
2. **US-5 a US-7** — mismo pipeline aplicado a Soporte SW-HW Semana 1 (contenido conceptual/V/F,
   sin verificación por cómputo).
3. **US-8 en adelante** — Semana 2 de ambas materias, repitiendo el pipeline ya validado.

Si el appetite se agota antes de llegar al punto 3, el corte es: **Semana 2 se difiere**, no se
recorta la verificación ni el dedup — esos son los que sostienen la confianza en el contenido
insertado.

> **Hueco de cobertura señalado 2026-08-08, resuelto 2026-08-08 — Nivelación Matemática
> recibe cards teóricas desde la misma implementación de US-5/US-6.** El punto 2 (US-5 a US-7)
> estaba redactado originalmente solo contra Soporte SW-HW. Decisión: US-5 y US-6 se
> implementan de forma materia-agnóstica desde el inicio — cubren tanto Soporte SW-HW como
> Nivelación Matemática (ej. definiciones de m.c.m/m.c.d que `classify/segmenter.py` ya
> segmenta como `flavor="theory"`, IPL-26) en la misma pasada, no en una extensión futura. Los
> Gherkin de §5.2 reflejan ambas materias explícitamente. No fue necesaria una ADR: el propio
> sub-pipeline teórico (§4.5.1) ya era agnóstico de materia — esto era secuenciación de user
> stories, no una decisión de arquitectura.

> **Corte adicional 2026-08-06 ([ADR-0002](../adr/0002-ejercicios-desde-fuentes-externas-curadas.md)).**
> El sourcing externo (US-3b + Fase A/B de §4.5.2) es la pieza más cara que agrega esta
> enmienda, sobre un appetite de 1 semana que ya estaba comprometido. Si se come el appetite,
> **el corte es apagar el sourcing externo y correr todo por el fallback de generación por
> LLM** — que es el diseño original y ya está especificado. Lo que **no** se recorta sigue
> siendo la verificación por cómputo ni el dedup. Este orden de corte es deliberado: la
> degradación deja un sistema completo y funcional, no uno a medias.

### 5.2 User stories (Gherkin)

**US-1 — Healthcheck de AnkiConnect antes de operar**
```gherkin
Feature: Verificación de conectividad con Anki
  Scenario: El desarrollador valida la conexión manualmente antes de una sesión de trabajo
    Given Anki está abierto en Windows con el plugin AnkiConnect instalado
    And existe scripts/anki_healthcheck.py con la lógica de validación como función reutilizable
    And existe un target "anki-check" en el justfile de la raíz que invoca ese script
    When el desarrollador corre "just anki-check" desde WSL
    Then el comando hace un request "version" a AnkiConnect
    And si la respuesta falla, reporta el error de conectividad con un mensaje claro
    And si la respuesta es exitosa, confirma la versión de AnkiConnect detectada

  Scenario: El agente confirma que AnkiConnect está disponible antes de generar contenido
    Given Anki está abierto en Windows con el plugin AnkiConnect instalado
    And el agente corre en WSL con la configuración de networking de §4.1
    When el agente inicia una sesión de generación
    Then el agente reutiliza la misma función de scripts/anki_healthcheck.py (no duplica la lógica)
    And si la respuesta falla, el agente reporta el error de conectividad y no continúa
    And si la respuesta es exitosa, el agente procede a la siguiente etapa
```

**US-2 — Ingesta y clasificación de material teórico-matemático**
```gherkin
Feature: Clasificación de contenido fuente
  Scenario: El agente clasifica una sección del material de Nivelación Matemática Semana 1
    Given el PDF "Nivelación Matemática — Semana 1" está disponible como fuente
    When el agente procesa la sección de mínimo común múltiplo (m.c.m)
    Then el agente identifica el tema como "mcm"
    And el agente identifica el patrón de ejercicio ejemplo (problema de eventos periódicos que coinciden)
    And el agente descarta cualquier actividad hands-on o pauta de autoevaluación si apareciera en esa sección
```

**US-3 — Ejercicio práctico verificado, desde fuente externa o generado**
*(Reescrita 2026-08-07 — [ADR-0003](../adr/0003-jerarquia-de-fuentes-para-ejercicios-practicos.md).)*
```gherkin
Feature: Ejercicios prácticos verificados por cómputo
  Scenario: Nivel 1 — el agente usa un ejercicio del material propio del curso
    Given la semana trae un archivo de ejercicios "EJ_1.1.docx" y su clave "R_1.1.pdf"
    And el aprendizaje esperado en curso es sobre m.c.m
    When el agente extrae los enunciados del DOCX y las respuestas de la clave
    And parea enunciado con respuesta por posición
    And la tool de cómputo en Python resuelve el enunciado de forma independiente
    Then si el cómputo coincide con la clave, la card se marca con el tag "verificado"
    And el campo "fuente" indica el archivo y el número de ejercicio

  Scenario: Nivel 1 — el conteo de enunciados y respuestas no coincide
    Given un archivo de ejercicios y una clave con distinta cantidad de items
    When el agente intenta parear por posición
    Then el agente detiene el procesamiento de ese archivo e informa
    And no parea a ciegas ni inserta cards de ese archivo

  Scenario: Nivel 2 — la semana no trae ejercicios, se usa una fuente externa curada
    Given la semana no trae archivo de ejercicios para el aprendizaje esperado
    And existe una lista curada de fuentes para el tema "mcm" (US-3b)
    When el agente recolecta un ejercicio candidato desde esas fuentes
    And descarta los candidatos que no calzan con el aprendizaje esperado
    And la tool de cómputo en Python resuelve el enunciado de forma independiente
    Then la card se marca con el tag "verificado"
    And el campo "fuente" contiene la URL del ejercicio original

  Scenario: La respuesta de la fuente no coincide con el cómputo de Python
    Given un ejercicio candidato cuya fuente publica su propia respuesta
    And la fuente puede ser la clave del curso o un sitio externo
    When la tool de cómputo en Python resuelve el enunciado y obtiene un resultado distinto
    Then el ejercicio se descarta por completo
    And no se inserta usando el resultado de Python como respuesta
    And el agente pasa al siguiente candidato

  Scenario: Nivel 3 — ningún nivel anterior rinde, fallback a generación por LLM
    Given no hay ejercicio del material propio ni externo válido para el aprendizaje esperado
    When el agente genera un enunciado nuevo siguiendo el patrón del material (US-2)
    And la tool de cómputo en Python resuelve el mismo enunciado de forma independiente
    Then si ambos resultados coinciden, la card se marca con el tag "verificado"
    And si no coinciden, la card se descarta y el agente genera un nuevo intento
    And el campo "fuente" apunta a la sección del material canónico, no a una URL
```

**US-3b — Curación de fuentes externas por tema**
```gherkin
Feature: Lista curada de fuentes de ejercicios
  Scenario: El agente arma la lista de fuentes para un tema nuevo
    Given el material de la unidad trae una bibliografía al final
    And el tema "mcm" todavía no tiene fuentes curadas
    When el agente parte de esa bibliografía como semilla
    And amplía con búsqueda web sitios con ejercicios del mismo tema
    Then la lista curada queda guardada como artefacto durable y versionado
    And las corridas siguientes reutilizan esa lista en vez de volver a buscar desde cero
```

**US-4 — Inserción con dedup en Anki**
```gherkin
Feature: Inserción de flashcards sin duplicados
  Scenario: El agente inserta una card verificada en el mazo correspondiente
    Given una card de m.c.m fue obtenida y verificada (US-3, por cualquiera de sus dos vías)
    When el agente prepara la inserción
    Then el agente llama "canAddNotes" antes de insertar
    And si la card es un duplicado, no se inserta
    And si no lo es, se inserta en el deck "Nivelación Matemática::Semana 1" con el tag "mcm" y "verificado"
    And el campo "fuente" contiene un puntero no vacío, según el origen de la card (§2.5):
        la URL del ejercicio si vino de una fuente externa curada, o la sección del material
        canónico si fue generado por LLM
```

**US-5 — Generación de superset teórico por aprendizaje esperado (materia-agnóstica)**
```gherkin
Feature: Cobertura amplia del contenido teórico, para cualquier materia con contenido segmentado como teórico
  Scenario: El agente genera un superset de preguntas para un aprendizaje esperado de Soporte SW-HW
    Given el material de "Soporte SW-HW — Semana 1" tiene un aprendizaje esperado sobre clasificación de software
    When el agente procesa esa subsección
    Then el agente genera 3 niveles de dificultad
    And cada nivel contiene entre 5 y 8 cards
    And cada card queda clasificada en el deck "Soporte HW-SW::Semana 1"

  Scenario: El agente genera un superset de preguntas para un aprendizaje esperado de Nivelación Matemática
    Given el material de "Nivelación Matemática — Semana 1" tiene una subsección teórica sobre la definición de m.c.m (segmentada con flavor "theory" por classify/segmenter.py, IPL-26)
    When el agente procesa esa subsección
    Then el agente genera 3 niveles de dificultad
    And cada nivel contiene entre 5 y 8 cards
    And cada card queda clasificada en el deck "Nivelación Matemática::Semana 1"
```

**US-6 — Generación de afirmación V/F siguiendo el patrón existente (materia-agnóstica)**
```gherkin
Feature: Generación de contenido V/F con grounding, para cualquier materia
  Scenario: El agente genera una afirmación V/F nueva sobre software de sistema (Soporte SW-HW)
    Given el patrón de afirmaciones V/F de Soporte fue identificado (ej. "El software de sistema es responsable únicamente de...")
    And el contenido teórico fuente sobre software de sistema está disponible
    When el agente genera una afirmación nueva con el mismo patrón
    Then el agente determina el valor de verdad contrastando la afirmación contra el pasaje específico del material fuente
    And la card se marca "verificado" solo si esa contrastación fue explícita, no inferida libremente

  Scenario: El agente genera una afirmación V/F nueva sobre una definición matemática (Nivelación Matemática)
    Given el contenido teórico fuente sobre la definición de m.c.m está disponible (segmentado como flavor "theory")
    When el agente genera una afirmación falsable siguiendo el mismo patrón (ej. "El m.c.m de dos números siempre es menor que su producto")
    Then el agente determina el valor de verdad contrastando la afirmación contra el pasaje específico del material fuente
    And la card se marca "verificado" solo si esa contrastación fue explícita, no inferida libremente
```

**US-7 — Filtrado cruzado por tema (validación del valor estructural)**
```gherkin
Feature: Filtrado por tag de tema
  Scenario: El estudiante filtra todas las cards de un tema específico cruzando materias
    Given existen cards con el tag "mcm" en "Nivelación Matemática::Semana 1"
    And existen cards con otros tags en "Soporte HW-SW::Semana 1"
    When el estudiante filtra por el tag "mcm" en Anki
    Then solo aparecen las cards de ese tema, sin importar en qué deck viven
```

**US-8 — CLI: comando conocido**
```gherkin
Feature: Loop de CLI con dispatch determinístico
  Scenario: El estudiante pide procesar una semana con un comando conocido
    Given el loop del agente está corriendo
    When el estudiante ingresa el comando para procesar "Nivelación Matemática, Semana 2"
    Then el agente matchea el comando contra la gramática conocida sin pasar por el modelo
    And ejecuta el pipeline de ingesta → clasificación → generación → verificación → inserción para esa semana/materia
```

**US-9 — CLI: fallback a lenguaje natural**
```gherkin
Feature: Loop de CLI con fallback a lenguaje natural
  Scenario: El estudiante da una instrucción que no matchea ningún comando conocido
    Given el loop del agente está corriendo
    When el estudiante ingresa una instrucción en lenguaje natural que no matchea la gramática de comandos
    Then el input cae al agente conversacional
    And el agente interpreta la instrucción y responde o actúa en consecuencia
```

---

## 6. Verificación — Definition of Shapeable (§6.4)

- **¿El problema está definido con precisión suficiente para acotar el alcance?** Sí — semanas
  1-2 de dos materias específicas, con fecha límite concreta (examen de la semana próxima), y
  fuera de alcance explícito (§1.4) para lo que no entra.
- **¿El appetite está declarado?** Sí — 1 semana para el build inicial (§1.3, fase 1). La
  funcionalidad de corrección de cards tiene su propio appetite de semana 2, declarado por
  separado y fuera de este documento (§2.6).
- **¿Los riesgos técnicos principales están nombrados?** Sí: alucinación en contenido generado
  (mitigado en §2.3/§4.6 con verificación por cómputo y grounding), instalación del plugin
  AnkiConnect (§4.1), networking WSL↔Windows (§4.1), lectura correcta de PDF/DOCX incluyendo
  contenido embebido como figuras (§4.4). **Agregados por
  [ADR-0002](../adr/0002-ejercicios-desde-fuentes-externas-curadas.md) (§4.5.2):** deriva de
  tema en ejercicios externos, fragilidad del scraping, envejecimiento de la lista curada,
  atribución de ejercicios de terceros, y presión sobre el appetite (con su regla de corte
  explícita en §5.1).
- **¿El documento se puede descomponer en SPEC-EXECs que pasen el test de arranque en frío
  (G5)?** Sí — cada user story de §5.2 especifica el Given/When/Then con referencias concretas a
  decisiones ya fijadas (taxonomía, mono-perfil), tools ya definidas (verificación Python,
  cliente AnkiConnect) y modelos ya asignados por tarea (§4.2). Ninguna story depende de una
  decisión todavía abierta en este documento.

Las cuatro preguntas cierran en sí. El documento queda listo para alimentar el ciclo de Claude
Code con Spec Kit.
