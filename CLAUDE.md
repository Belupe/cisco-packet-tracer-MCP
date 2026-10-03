# CLAUDE.md — MCP local para Cisco Packet Tracer 6.0.1

## Qué es este proyecto
Un servidor MCP **local** (Python, solo biblioteca estándar) que permite a Claude controlar **Cisco Packet Tracer 6.0.1.0011**
en tiempo real: crear dispositivos, cablear, configurar IP/IOS/servidores y hacer ping. El usuario habla español.
Lee `GUIA_COMPLETA.md` (arquitectura y mapa de confianza) y `NOTAS.md` (diario técnico) antes de tocar nada.
**Antes de crear o nombrar cualquier cosa en Packet Tracer, lee `reglas.md`**: ahí el usuario define cómo se nombran los equipos y
cómo se reparten IPs, VLANs, puertos y posiciones. Manda por encima de los valores por defecto. Donde ponga `PENDIENTE`, pregunta; no inventes.

## Estructura
- `pt601_mcp/` — el producto: `bridge.py` (HTTP + token), `mcpproto.py` (MCP por stdio), `tools.py` (23 herramientas),
  `jsgen.py` (JavaScript para PT), `ios.py` (comandos IOS), `plan.py` (planes JSON), `catalog.py` (modelos/cables),
  `extension/` (panel + script engine que se pegan/cargan en PT).
- `tests/` — pruebas sin PT: `python3 -m unittest discover -s tests -v` (o con el python portátil del usuario).
- `skill/SKILL.md` — skill para el asistente que use el MCP. `prototipo/`, `sondeo/` — herramientas de descubrimiento.
- `documentación/` — ayuda local de PT 6.0.1 (HTML). No la modifiques.

## Reglas de trabajo
1. **Nunca adivines la API de PT 6.0.1.** Difiere de la moderna. Si un método no está ya usado/probado en este repo,
   compruébalo con `pt_describe`/`pt_eval` o pide al usuario que ejecute un sondeo. Un error de PT suele ser un
   escueto `Invalid arguments for IPC call "X"`.
2. **El JavaScript que va a PT es Qt Script (ES3)**: sin `let`/`const`/flechas/`JSON`/`XMLHttpRequest` en el Script Engine.
   Los valores de usuario entran SIEMPRE por `jsgen.q()`. Compruebas sintaxis con `node --check` si hay node.
3. **Seguridad**: puerto solo en 127.0.0.1, token por sesión, sin endpoint de ejecución por HTTP. No debilites esto.
4. **Cada arreglo lleva su prueba** en `tests/` (debe fallar sin el arreglo). Ejecuta todo antes de entregar.
5. Estilo: Python 3.8+ (el python portátil del usuario es 3.12), sin dependencias externas, mensajes de error en español.
6. Commits en `main`, mensajes descriptivos. Actualiza `NOTAS.md` con cada hallazgo nuevo.
7. **Convenciones del usuario**: nombres, IPs, VLANs, puertos y layout salen de `reglas.md`. Si una petición lo contradice, avisa antes de
   construir. Si falta una regla, pregunta y propón anotarla en la sección 10 de `reglas.md` (solo con permiso del usuario).

## Particularidades de la 6.0.1 (comprobadas en la máquina del usuario)
- `lw.addDevice(tipo, modelo)` — **2 argumentos**; posición con `device.moveToLocation(x, y)`.
- `setName` no impide duplicados → comprobar antes; `getDevice(nombre)` devuelve el primero.
- `createLink(d1, p1, d2, p2, entero)`: 8100 recto, 8101 cruzado, 8107 auto.
- Router nuevo: responder `no` y `""` al diálogo `[yes/no]`. `enterCommand` en router es síncrono; el `ping` de un PC no.
- `WV.evaluateJavaScript(...)` devuelve el valor; `$se`/`webView` no existen en páginas `http://`.
- Un error IPC aborta el script si la ventana Debug está abierta.

## Lo primero que probablemente haya que reparar (sin validar en PT real)
1. **Servidor DNS de Server-PT** (`jsgen.dns_server`): basado en la API moderna (`DnsServerMain`, `addIpAddress`); el real
   probablemente sea `DnsServer`. Usa `pt_describe` con `process=DnsServer`. (El DHCP ya está validado: proceso `DhcpServer`, pool por defecto.)
2. **Puertos automáticos** (`jsgen.connect_auto`) y el parseo de `OK X:p <-> Y:q` en `tools.build_topology` (`@VECINO`).
3. **Panel con token** (`extension/interface.html`): probado solo con un panel simulado.
4. Modelos del catálogo marcados «sin verificar» (`catalog.py`).

## Mejoras pendientes pedidas por el usuario (actualizado 2026-10-03)
Petición: *mejorar el aprendizaje de representar instrucciones e identificar la posición de los switches.* Aclarado por el usuario:

**A. Interpretar documentos con instrucciones** (enunciados de clase, guiones de práctica). Antes de construir nada:
1. Extraer del documento una **lista de requisitos** (equipos, cantidades, IPs, VLANs, servicios, pruebas pedidas) y enseñársela al usuario.
2. Marcar lo que el documento **no dice** o dice de forma ambigua y **preguntar**; no rellenar huecos con suposiciones.
3. Completar nombres, IPs y puertos con `reglas.md`; si el documento y `reglas.md` chocan, avisar y que decida el usuario.
4. Traducirlo a un plan (`pt_build_topology`, primero `dry_run: true`) y enseñarlo.
5. Al terminar, **verificar contra la lista de requisitos** (`pt_list_devices`, `pt_list_ports`, `pt_cli`, `pt_ping`) e informar de lo que no se cumple.

**B. Posición de los switches y del resto de equipos: seguir el esquema exacto de organización que se usa en clase.**
- El esquema lo define el usuario en la sección 7 de `reglas.md` (aún por rellenar). **No inventes una disposición propia**: si falta, pregunta.
- Observación del código: `plan.auto_layout` es genérico (por niveles) y coloca **todos** los switches en el mismo nivel (`TIER_BY_KIND`: switch = 1),
  sin jerarquía núcleo/acceso ni sedes. Habrá que hacerlo configurable o sustituirlo por posiciones que sigan el esquema de clase
  (por ejemplo, posiciones explícitas por rol y sede). Hasta entonces, pasa `x`/`y` explícitos en el plan según `reglas.md`.
- El dispositivo ya expone `getXCoordinate`/`getYCoordinate` (sondeo 1): se pueden leer las posiciones reales y recolocar con `pt_move_device`.

**C. Datos útiles ya conocidos:** `Switch-PT-Empty` nace sin puertos (se le añaden módulos, ver `NOTAS.md`); el cable `auto` falla en puertos de
módulo y se reintenta recto/cruzado; con la ventana Debug abierta un error IPC cuelga el motor (Stop/Start).

## Cómo pedir datos al usuario
El usuario tiene PT 6.0.1 en Windows (sin Python instalado: usa el embeddable). Para descubrir algo, dale **líneas
cortas** para pegar en PowerShell/Debug y pide que te copie la salida completa. Cada paso debe ser pequeño y reversible.
