# TDD — Pipeline de generación de flashcards Anki para autoestudio

> Documento de diseño (TDD/RFC) del bucle macro de Ironspec AI (§6.1). Este documento se
> *shapea* a la altura correcta y de él se derivan, en el ciclo siguiente, las decisiones
> (ADR) y las SPEC-EXEC que ejecuta Claude Code con Spec Kit (Spec → Plan → Tasks →
> Implement). **No contiene SPEC-EXEC ni ADRs** — son el output de la etapa siguiente.

**Estado:** shaping cerrado — pasa la Definition of Shapeable (§6.4, verificación al final de
este documento).
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

### 2.2 Extracción de ejercicios existentes vs. generación de ejercicios nuevos por patrón

| | Extracción | Generación por patrón |
|---|---|---|
| Fidelidad | Alta — la respuesta ya está validada en el material | Depende de que el agente resuelva/formule bien |
| Cobertura | Limitada al set finito de ejercicios que ya existen | Superset amplio, sin techo natural del material original |
| Matching fuente↔respuesta | Necesario y fue identificado como riesgo (archivos separados: `EJ_X.docx` vs `R_X.pdf`) | No aplica — no hay respuesta preexistente que parear |

**Elegida: generación.** Interesa cobertura amplia del material, no solo el set de ejercicios
que ya trae cada semana. Se pierde la garantía de fidelidad de una respuesta ya validada; se
gana no estar limitado al volumen fijo de ejercicios existentes. Esto desplaza el riesgo
principal de "matching frágil" a "alucinación en contenido generado" (ver §2.3).

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

Con el pivote de §2.2, prácticamente el 100% de las cards son generadas — un tag binario
"generado sí/no" deja de discriminar nada útil.

**Elegida:** dos campos distintos — `fuente` (referencia a sección/página del material canónico
del que salió el patrón o dato teórico; trazabilidad, no fidelidad literal) y `verificado` (tag,
si la respuesta pasó verificación explícita antes de insertarse).

### 2.5 Fuente en el backside: puntero vs. cita textual

| | Puntero (ref. a sección/página) | Cita textual breve |
|---|---|---|
| Costo de generación | Bajo | Más caro, requiere recortar bien |
| Riesgo de desincronía | Ninguno — no copia nada | Puede desalinearse si el material cambia de versión |
| Efecto en el estudio | Obliga a volver al material original para validar | Se valida sin salir de Anki |

**Elegida: puntero.** Además de ser más liviano de generar, el efecto de forzar volver al
material original es deseado — refuerza el repaso en sí mismo, no es solo trazabilidad técnica.

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
| Sin cobertura de todo el material antes del examen | Superset generado por aprendizaje esperado/subsección × nivel de dificultad, no limitado al set de ejercicios que ya existen | % de aprendizajes esperados de semana 1-2 con al menos N cards insertadas |
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
- Tool de verificación matemática — cómputo determinístico en Python (mcm, mcd, operatoria con
  enteros y fracciones) independiente del LLM.
- Cliente AnkiConnect (`canAddNotes`, `addNotes`, `deckNames`, `version` para healthcheck).

**Selección de modelo por tarea (§4.5 de Ironspec):**

| Tarea | Modelo | Por qué |
|---|---|---|
| Clasificación de contenido (qué sabor es, qué tema/tag corresponde) | Ligero (Haiku) | Tarea acotada, respuesta estrecha |
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

### 4.5 Generación de contenido — dos sub-pipelines

**4.5.1 Teórico / teórico-práctico.** Toma el contenido de los PDF de material de estudio como
fuente canónica y los patrones de formulación de pregunta que ya aparecen en el material (ej.
las afirmaciones V/F de Soporte: *"El software de sistema es responsable únicamente de las
funciones relacionadas con la conectividad a internet"* → patrón de afirmación falsable sobre
una definición). Genera un superset por **aprendizaje esperado / subsección** del material, con
**3 niveles de dificultad × 5-8 cards por nivel**.

**4.5.2 Práctico.** Genera enunciados nuevos siguiendo el patrón de los ejercicios existentes
como ejemplo — no los extrae. Ejemplo de patrón tomado de Nivelación Matemática Semana 1 (el
problema de "los viajeros" de mcm): enunciado con dos eventos periódicos que coinciden en el
tiempo, pide encontrar cuándo vuelven a coincidir. El agente genera una variante nueva del mismo
patrón (otros números, otro contexto narrativo) y resuelve él mismo el enunciado que genera.

### 4.6 Verificación pre-inserción

- **Contenido matemático:** el agente genera enunciado + solución candidata; la tool de cómputo
  en Python resuelve el mismo problema de forma independiente; solo se inserta si ambos
  resultados coinciden. Si no coinciden, se descarta y se regenera (no se inserta contenido sin
  verificar).
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
  §4.6).

### 4.8 Dedup e inserción

`canAddNotes` contra el conjunto de notas a insertar antes de llamar `addNotes` — evita
duplicados dentro de una misma corrida y contra el estado ya existente del mazo.

---

## 5. Descomposición en user stories

Relación story:spec 1..n (§7.2 de Ironspec) — cada story puede derivar en una o más SPEC-EXEC
en el ciclo de Claude Code.

### 5.1 Priorización — orden de corte para el appetite de 1 semana

1. **US-1 a US-4** — setup + pipeline mínimo end-to-end en una sola materia/semana (Nivelación
   Matemática, Semana 1), para validar el pipeline completo con el riesgo técnico más nuevo
   (verificación matemática) antes de escalar.
2. **US-5 a US-7** — mismo pipeline aplicado a Soporte SW-HW Semana 1 (contenido conceptual/V/F,
   sin verificación por cómputo).
3. **US-8 en adelante** — Semana 2 de ambas materias, repitiendo el pipeline ya validado.

Si el appetite se agota antes de llegar al punto 3, el corte es: **Semana 2 se difiere**, no se
recorta la verificación ni el dedup — esos son los que sostienen la confianza en el contenido
insertado.

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

**US-3 — Generación de ejercicio práctico nuevo con verificación matemática**
```gherkin
Feature: Generación de ejercicios prácticos verificados
  Scenario: El agente genera un ejercicio nuevo de m.c.m siguiendo el patrón identificado
    Given el patrón de ejercicio de m.c.m fue identificado en US-2
    When el agente genera un enunciado nuevo con el mismo patrón y una solución candidata
    And la tool de cómputo en Python resuelve el mismo enunciado de forma independiente
    Then si ambos resultados coinciden, la card se marca con el tag "verificado"
    And si no coinciden, la card se descarta y el agente genera un nuevo intento
```

**US-4 — Inserción con dedup en Anki**
```gherkin
Feature: Inserción de flashcards sin duplicados
  Scenario: El agente inserta una card verificada en el mazo correspondiente
    Given una card de m.c.m fue generada y verificada (US-3)
    When el agente prepara la inserción
    Then el agente llama "canAddNotes" antes de insertar
    And si la card es un duplicado, no se inserta
    And si no lo es, se inserta en el deck "Nivelación Matemática::Semana 1" con el tag "mcm" y "verificado"
    And el campo "fuente" contiene un puntero a la sección del material del que salió el patrón
```

**US-5 — Generación de superset teórico por aprendizaje esperado**
```gherkin
Feature: Cobertura amplia del contenido teórico
  Scenario: El agente genera un superset de preguntas para un aprendizaje esperado de Soporte
    Given el material de "Soporte SW-HW — Semana 1" tiene un aprendizaje esperado sobre clasificación de software
    When el agente procesa esa subsección
    Then el agente genera 3 niveles de dificultad
    And cada nivel contiene entre 5 y 8 cards
    And cada card queda clasificada en el deck "Soporte HW-SW::Semana 1"
```

**US-6 — Generación de afirmación V/F siguiendo el patrón existente**
```gherkin
Feature: Generación de contenido V/F con grounding
  Scenario: El agente genera una afirmación V/F nueva sobre software de sistema
    Given el patrón de afirmaciones V/F de Soporte fue identificado (ej. "El software de sistema es responsable únicamente de...")
    And el contenido teórico fuente sobre software de sistema está disponible
    When el agente genera una afirmación nueva con el mismo patrón
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
  contenido embebido como figuras (§4.4).
- **¿El documento se puede descomponer en SPEC-EXECs que pasen el test de arranque en frío
  (G5)?** Sí — cada user story de §5.2 especifica el Given/When/Then con referencias concretas a
  decisiones ya fijadas (taxonomía, mono-perfil), tools ya definidas (verificación Python,
  cliente AnkiConnect) y modelos ya asignados por tarea (§4.2). Ninguna story depende de una
  decisión todavía abierta en este documento.

Las cuatro preguntas cierran en sí. El documento queda listo para alimentar el ciclo de Claude
Code con Spec Kit.
