# Entorno — Anki + AnkiConnect + WSL

> Runbook operativo. Distinto del README (vitrina/presentación del proyecto): esto es lo que
> se consulta para levantar y verificar el entorno real, y lo que un agente frío debe poder
> seguir sin preguntar (G5).

## Componentes

- **Anki** corre en **Windows**, con el plugin **AnkiConnect** instalado y habilitado.
- El **agente** corre en **WSL Ubuntu**, y habla con AnkiConnect vía HTTP.
- Mono-perfil (decisión fijada, TDD §4.1): un solo perfil de Anki para toda la carrera.

## Verificar que el entorno está arriba

Comando canónico (TDD §4.1 — instrucción de implementación para Claude Code):

```bash
just anki-check
```

Este target invoca `scripts/anki_healthcheck.py`, que hace un request `version` a AnkiConnect
y reporta si respondió y con qué versión. **No improvisar un curl o un script suelto distinto
de este** — si falta cubrir un caso nuevo, se extiende este script/target, no se crea uno
paralelo.

> Estado: `scripts/anki_healthcheck.py` y el target `anki-check` del `justfile` **todavía no
> existen** — son de los primeros artefactos que la SPEC-EXEC de `ProjectSetup` crea. Esta
> sección describe el comportamiento esperado; si al leer esto el script no existe todavía,
> es el primer paso pendiente, no un error del runbook.

## Networking WSL ↔ Windows

Dos vías, en orden de preferencia (TDD §4.1):

### 1. Mirrored networking mode (preferido)

Disponible en versiones recientes de WSL2/Windows 11. Si está activo, `localhost` dentro de
WSL resuelve directo al host Windows — no hace falta configuración adicional en AnkiConnect.

Verificar si está activo:

```bash
# Dentro de WSL
cat /etc/wsl.conf 2>/dev/null | grep -A5 '\[wsl2\]'
# o revisar %USERPROFILE%\.wslconfig en Windows, sección [wsl2], networkingMode=mirrored
```

Si está en modo mirrored, `just anki-check` debería funcionar contra `localhost:8765` (puerto
default de AnkiConnect) sin más configuración.

### 2. Fallback — `webBindAddress` + IP de host

Si mirrored mode no está disponible:

1. En Anki, configurar AnkiConnect (`Tools → Add-ons → AnkiConnect → Config`) para escuchar en
   todas las interfaces, no solo loopback:
   ```json
   { "webBindAddress": "0.0.0.0", "webBindPort": 8765 }
   ```
2. Desde WSL, resolver la IP del host Windows (no es `localhost` en este modo):
   ```bash
   ip route show default | awk '{print $3}'
   # o: cat /etc/resolv.conf | grep nameserver
   ```
3. Usar esa IP en vez de `localhost` para las requests a AnkiConnect.

**Verificar cuál de las dos vías aplica en el entorno real antes de fijar la configuración** —
no asumir mirrored mode disponible solo porque es el preferido.

## Instalación de AnkiConnect

1. En Anki (Windows): `Tools → Add-ons → Get Add-ons...`
2. Código del add-on: `2055492159`
3. Reiniciar Anki.
4. Confirmar con `just anki-check` (o, hasta que exista, un request manual a
   `http://localhost:8765` con body `{"action": "version", "version": 6}`).

## Troubleshooting

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `just anki-check` falla con timeout/connection refused | Anki cerrado, o AnkiConnect no instalado/habilitado | Abrir Anki, confirmar el add-on activo en la lista |
| Funciona con `localhost` un día y no otro | Mirrored mode inconsistente entre reinicios de WSL, o IP de host cambió | Reverificar con los comandos de la sección de networking, no asumir que la config de la última sesión sigue vigente |
| AnkiConnect responde pero `canAddNotes`/`addNotes` fallan | Perfil equivocado activo en Anki, o deck/note type no existen todavía | Confirmar mono-perfil activo; revisar taxonomía `Materia::Unidad` (TDD §4.4) |

Si aparece un síntoma nuevo no cubierto acá y su diagnóstico toma más de una pregunta de
warmup, es candidato a kaizen (`docs/kaizen-log.yaml`) con este archivo como artefacto a
corregir — no un ajuste que se resuelve una vez y se olvida.
