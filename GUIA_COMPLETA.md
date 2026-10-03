# Guía completa: MCP local para Packet Tracer 6.0.1

Esta guía explica **qué es cada pieza, cómo encajan, qué está probado de verdad y qué no**, y cómo reparar
lo que falle. Está pensada para leerla de arriba abajo una vez y luego usarla como consulta.

> **Estado honesto.** Todo el código se ha probado con 39 pruebas automáticas sin Packet Tracer. Contra un
> Packet Tracer 6.0.1 real se han probado a mano: crear dispositivos, moverlos, renombrarlos, cablearlos,
> poner IP, configurar un router por consola y hacer ping. **Sin probar en la práctica:** el servidor MCP
> completo con token, las herramientas de alto nivel (`pt_build_topology` y compañía) y los servidores
> DHCP/DNS de Server-PT.

---

## 1. El problema y la idea
Packet Tracer no se controla desde fuera: no tiene API de red. Pero la 6.0.1 trae **Script Modules**, programas en
JavaScript que corren *dentro* de PT y pueden manipular la red (`ipc.network()`, etc.). La idea:

1. Un Script Module dentro de PT abre un **panel** (navegador embebido) y ejecuta el código que recibe.
2. Un **servidor local** (Python) le entrega ese código por HTTP.
3. Ese servidor es además un **servidor MCP**, así que Claude (VS Code, Claude Code…) puede llamarlo como
   herramientas: «crea un router», «haz un ping».

```
Claude ──(MCP por stdin/stdout)──> pt601_mcp ──(HTTP 127.0.0.1:54321 + token)──> panel ──> Script Engine ──> PT
```

## 2. Las piezas, de fuera hacia dentro
| Pieza | Dónde | Qué hace |
|---|---|---|
| **Cliente MCP** | VS Code (extensión de Claude) | Lanza `python.exe run.py` y habla con él por stdin/stdout |
| **`pt601_mcp/mcpproto.py`** | Python | Protocolo MCP mínimo escrito a mano (`initialize`, `tools/list`, `tools/call`) |
| **`pt601_mcp/tools.py`** | Python | Las 36 herramientas `pt_*`; convierten una orden en JavaScript |
| **`pt601_mcp/jsgen.py`** | Python | Fábrica de JavaScript seguro (escapa los valores del usuario) |
| **`pt601_mcp/ios.py`** | Python | Genera comandos IOS (interfaces, OSPF, VLAN, DHCP…) y valida IPs/máscaras |
| **`pt601_mcp/plan.py`** | Python | Valida planes JSON, autoposiciona, resuelve `@VECINO` |
| **`pt601_mcp/catalog.py`** | Python | Modelos de dispositivo y tipos de cable de la 6.0.1 |
| **`pt601_mcp/bridge.py`** | Python | Servidor HTTP local con token; cola de órdenes y resultados |
| **`pt601_mcp/extension/interface.html`** | Se sirve por HTTP | El panel: pregunta al servidor «¿hay algo?» y guarda lo que llega |
| **`pt601_mcp/extension/script_engine.js`** | Pegado en PT | Cada 250 ms pregunta al panel, ejecuta el código con `eval` y devuelve el resultado |

### El recorrido de una orden (ejemplo: `pt_add_device`)
1. Claude llama a `pt_add_device(name="R1", model="2911")`.
2. `tools.py` valida el modelo en `catalog.py` y pide a `jsgen.py` el JavaScript.
3. `bridge.py` lo mete en una cola y espera.
4. El panel (que hace `GET /next?t=TOKEN` en bucle) recibe el código.
5. El Script Engine, con un temporizador, llama a `__take()` en el panel (`evaluateJavaScript` **devuelve** el valor),
   ejecuta el código dentro de PT y le devuelve el resultado con `__result(...)`.
6. El panel hace `POST /result`; el servidor despierta a la herramienta, que contesta a Claude.

## 3. Por qué está hecho así (lo que se descubrió en tu PT)
Estas son las particularidades de la 6.0.1.0011 que condicionan todo el diseño. Están comprobadas en tu máquina salvo
donde se indique:

- **No hay archivos ni red en el Script Engine** (`systemFileManager` y `XMLHttpRequest` no existen) → hace falta un
  panel (web view) que sí pueda usar HTTP.
- **`$se` y `webView` no existen en páginas `http://`** (solo en interfaces internas `this-sm:`) → por eso el motor
  *pregunta* al panel y no al revés.
- **`addDevice` solo acepta 2 argumentos** (tipo, modelo). Las versiones modernas aceptan 4 (con x, y). La posición
  se pone después con `moveToLocation`.
- **`createLink` exige el tipo de cable como número** (8100 recto, 8101 cruzado, 8107 automático). El texto `"auto"` falla.
- **`setName` permite nombres duplicados** por IPC (la interfaz gráfica no). Duplicados = dispositivos invisibles
  apilados que luego no se pueden cablear. Por eso `pt_add_device` comprueba antes.
- **Los routers nuevos preguntan** `Continue with configuration dialog? [yes/no]:`. Hay que responder `no` y Enter.
- **`enterCommand` en routers es síncrono**; en PCs, `ping` devuelve el control antes de acabar (hay que leer la
  salida después).
- **Un error de IPC detiene el script si la ventana Debug está abierta** (el depurador lo captura). Con Debug cerrada,
  `try/catch` funciona.
- **El motor es Qt Script (JavaScript antiguo)**: sin `let`, `const`, funciones flecha ni `JSON`.

## 4. Seguridad
El servidor ejecuta JavaScript dentro de Packet Tracer, así que es una superficie sensible. Medidas:
- Escucha solo en `127.0.0.1`.
- **Token aleatorio por sesión**; solo lo recibe la página del panel. `/next` y `/result` lo exigen
  (comparación en tiempo constante). Una web ajena no puede leer esa página (política de mismo origen).
- Comprobación de la cabecera `Host` (contra DNS rebinding).
- **No existe endpoint para enviar código por HTTP**: el código solo entra desde el propio proceso.
- Cuerpos limitados a 1 MB; todos los valores de usuario se escapan como literales JSON en el JavaScript.
- `pt_eval` es una puerta abierta *a propósito* (ejecuta JS arbitrario en PT): solo la alcanza un cliente MCP que tú
  hayas autorizado.

## 5. Qué es seguro y qué no (mapa de confianza)
| Funcionalidad | Estado |
|---|---|
| Crear/mover/renombrar/borrar dispositivos, cablear, IP en PCs, consola de router, ping | ✅ Probado en tu PT (con el prototipo `pt.ps1`) |
| Servidor MCP + puente con token, panel con token | ⚠️ Probado solo con panel simulado; **falta probarlo en PT real** |
| `pt_build_topology`, `pt_connect` (puertos automáticos), `@VECINO` | ⚠️ Probado solo con puente simulado |
| `pt_router_config` / `pt_switch_config` (genera IOS) | ✅ El IOS generado es estándar; ⚠️ falta ejecutarlo en PT |
| `pt_dhcp_server` (Server-PT) | ✅ Probado en tu PT: proceso `DhcpServer`, pool por defecto (`setStartIp/EndIp/DefaultRouter/DnsServerIp`) |
| `pt_dns_server` (Server-PT) | ❓ **Sin validar**: usa nombres de la API moderna (probable `DnsServer`) |
| Modelos de dispositivo distintos de los 9 verificados | ❓ Sin verificar en la 6.0.1 |

## 6. Cómo reparar lo que falle (receta general)
1. **Reproduce en pequeño.** Usa una sola herramienta (`pt_status`, luego `pt_add_device`…) en lugar del plan entero.
2. **Lee el mensaje de error.** Casi todos están en español y apuntan a la causa habitual.
3. **Mira el panel "PT-MCP local".** Muestra `conexión: ok/ERROR`, `recibidos` y `terminados` (¿llega el código? ¿vuelve?).
4. **Cierra la ventana Debug** del Script Module si buscas errores capturados por `try/catch`.
5. **Inspecciona la API real** con `pt_describe`: lista los métodos de un dispositivo, proceso (`DhcpServer`) o puerto.
6. **Aísla con `pt_eval`** para probar una línea de JavaScript suelta dentro de PT.
7. **Arregla y comprueba:** `python3 -m unittest discover -s tests -v` (o con el `python.exe` portátil).

### Si fallan los servidores DHCP/DNS (lo más probable)
1. Ejecuta `pt_describe` con `device` = tu servidor y `process` = `DhcpServerMain` (y luego `DnsServerMain`).
2. Si dice que no existe el proceso, prueba otros nombres en `jsgen._PROC_FINDER` (`DHCPServerMain`, `DhcpServer`…).
3. Con la lista real de miembros, ajusta `jsgen.dhcp_server` / `jsgen.dns_server`: son los intentos
   `addNewPool(8)`, `addNewPool(7)`, `addNewPool(6)`, `addIpAddress`, `addRecord`.
4. Alternativa que siempre funciona para DHCP: un pool en el router (`pt_router_config` → `dhcp_pools`).

## 7. Mapa de archivos del repositorio
```
GUIA_COMPLETA.md        esta guía
CLAUDE.md               contexto para el Claude de VS Code
reglas.md               TUS convenciones: nombres, IPs, VLANs, puertos, posiciones (el asistente las lee antes de crear nada)
NOTAS.md                diario técnico: hallazgos, hitos y lecciones
pt601_mcp/              EL PRODUCTO (servidor MCP)
  README.md             instalación y uso
  docs/herramientas.md  referencia de herramientas y esquemas
  docs/ejemplos.md      prompts y planes JSON
  extension/            lo que va dentro de Packet Tracer (panel + script engine)
skill/SKILL.md          skill de Claude (flujo de trabajo y reglas)
tests/                  pruebas automáticas sin Packet Tracer
prototipo/              prototipo previo (PowerShell/Python), útil para pruebas sueltas con pt.ps1
sondeo/                 scripts que usamos para descubrir la API de la 6.0.1
documentación/          ayuda local de Packet Tracer 6.0.1
```

## 8. Glosario rápido
- **MCP**: protocolo para que un asistente use herramientas externas.
- **Script Module (`.pts`)**: programa JavaScript que corre dentro de PT.
- **IPC**: la API interna de PT (`ipc.network()`, `ipc.appWindow()`…).
- **Web view**: ventana de navegador (QtWebKit) embebida en PT.
- **Server-PT**: el dispositivo servidor de PT (DHCP, DNS, HTTP, etc.).
- **@VECINO**: en los planes, «el puerto de este dispositivo que está cableado con VECINO».
