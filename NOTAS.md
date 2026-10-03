# Notas del proyecto

## Versión objetivo
**Cisco Packet Tracer 6.0.1.0011** (confirmada por el usuario en Help → About).

Evidencia en `documentación/`: IOS 15, routers 1941/2901/2911 y HSRP (`whatsNew.htm`),
Script Modules `.pts` desde la 5.3.3 (`scriptModules.htm`), IPC por TCP puerto 39000 (`ipc.htm`).

## Objetivo
Equivalente local de https://github.com/Mats2208/MCP-Packet-Tracer adaptado a la 6.0.1:
servidor MCP en Python + puente HTTP en 127.0.0.1 (con token) + extensión `.pts`
que ejecuta el JavaScript dentro de Packet Tracer.

## Restricciones de la 6.0.1
- Script Engine = Qt Script (ECMAScript antiguo): sin `let`/`const`/funciones flecha; `JSON` no garantizado.
- Catálogo de dispositivos y cables limitado a lo que existe en la 6.0.1.
- Pendiente: referencia de la API IPC (archivos `.pki`), necesaria para no inventar métodos.

## Hallazgos del árbol de instalación (pt_arbol.txt)
- 1500 archivos / 97 carpetas. **No hay archivos `.pki`**: la referencia de la API IPC no viene instalada.
- El catálogo de dispositivos va compilado en `PacketTracer6.exe`; no hay lista en disco.
- Qt 4 (`QtScript4.dll`): confirma Qt Script antiguo.
- `extensions/IpcLog` (ExApp) registra llamadas IPC: útil para descubrir la API.
- `extensions/scriptTemplates/*.ptst` son plantillas de Script Module (cifradas).
- `templates/*.ptd` solo 4 plantillas: 1841+WIC-2T, 2621XM+NM-2FE2W+2×WIC-2T, 2811+NM-ESW-161+2×WIC-2T, PC inalámbrico.
- Dispositivos vistos en `art/`: routers 1841, 1941, 2620XM, 2621XM, 2811, 2901, 2911; switches 2950, 2950T, 2960-24TT, 3560;
  Linksys WRT300N, hub, repeater, bridge, cloud, DSL/cable modem, AP, server, PC, laptop, PDA, tablet, impresora, TV, teléfono IP 7960, teléfono analógico, HomeVoIP, splitter coaxial.
- `saves/` trae 49 ejemplos `.pkt/.pka` (cifrados).

## Siguiente paso
Ejecutar `sondeo/sondeo_ipc.js` en PT 6.0.1 y volcar la salida para conocer la API real.

## Resultado del sondeo 1 (PT 6.0.1.0011)
- `ipc`: appWindow, commandLog, ipcManager, multiUserManager, network, simulation.
- `network`: solo getDevice / getDeviceAt / getDeviceCount (no crea dispositivos).
- `device` (81 métodos): enterCommand, getCommandLine, addModule/removeModule, addSubInt, setHostName, setEnableSecret,
  setBannerMotd, addUserPass, setPower, moveToLocation, serializeToXml, getPort/getPortAt/getPortCount, getModel, getType...
- `port` (108 métodos): IPv4/IPv6, OSPF (coste, timers, md5), EIGRP pasivo, RIP, ACL in/out, NAT, DHCP client, ancho de banda, duplex, getLink.
- `appWindow` (69 métodos): fileNew/Open/Save/SaveAs, getActiveWorkspace, getVersion, isRealtime/Simulation/LogicalMode...
- `simulation`: isSimulationMode, getFrameInstanceAt/Count.
- Modelos vistos: Router-PT-Empty, Switch-PT-Empty, PC-PT, Server-PT, Laptop-PT, AccessPoint-PT, AccessPoint-PT-A.
- Tipos: 0 router, 1 switch, 7 AP, 8 PC, 9 server, 17 laptop.
- Pendiente: crear dispositivos/cables (probablemente `getActiveWorkspace().getLogicalWorkspace()`) -> `sondeo/sondeo2_ipc.js`.

## Resultado del sondeo 2 (PT 6.0.1.0011)
- `appWindow.getVersion()` = `6.0.1.0011`; base path `C:/Program Files (x86)/Cisco Packet Tracer 6.0.1`.
- `getActiveWorkspace().getLogicalWorkspace()` expone: addDevice, createLink, deleteLink, removeDevice, addNote, drawLine/drawCircle,
  getCanvasItemIds, moveCanvasItemBy, getWorkspaceImage, getState...
- `commandLine` (terminal): enterCommand, enterChar, getOutput, getPrompt, getMode, getCommandInput, historiales.
- `link`: getPort1, getPort2, getOtherPort, getLinkType, getConnectionType.
- `commandLog`: getEntryAt/getEntryCount/setEnabled/clear.
- `addDevice(0,"2911",100,100)` -> "Invalid arguments": las firmas reales aún no se conocen (sondeo 3).
- Los argumentos IPC llegan como texto ("0","2911",...).

## Resultado del sondeo 3 y búsqueda en PacketTracer6.exe
- `lw.addDevice(...)` es solo `this._parser.ipcCall('addDevice', arguments)`; `_parser` = className, createObject, ipcCall, uuid (no describe firmas).
- Un error de IPC dentro de un script aborta toda la ejecución (try/catch no lo captura). Para probar llamadas sueltas usar el cuadro de entrada de la ventana Debug.
- `addDevice(0,"2911",100,100)` -> "Invalid arguments" (privilegios OK). Firma real aún desconocida.
- El .exe contiene solo los nombres de métodos de LogicalWorkspace (no tipos de parámetros), más el evento `deviceAdded(name, model)` / `deviceRemoved(name)`.
- Modelos internos vistos en el .exe: PC-PT, Laptop-PT, TV-PT, TabletPC-PT, Pda-PT, WirelessEndDevice-PT, WiredEndDevice-PT.
- Plan: registrar `deviceAdded` y arrastrar dispositivos a mano para ver la cadena exacta de `model` que usa la 6.0.1.

## Resultado de pruebas en la ventana Debug (PT 6.0.1.0011)
- Escrituras funcionan: `device.setName()` OK, `lw.removeDevice("nombre")` -> true.
- `lw.createLink("Router1","GigabitEthernet0/0","Switch1","FastEthernet0/1",8100)` -> true (**cable como entero**; con `"auto"` da Invalid arguments).
  Enum de cables (según repo de referencia): 8100 straight, 8101 cross, 8102 roll, 8103 fiber, 8104 phone, 8105 cable, 8106 serial, 8107 auto, 8108 console.
- Evento `lw.registerEvent("deviceAdded", null, function(src,args){ args.name, args.model })` funciona; modelos internos: `2911`, `2960-24TT`, `PC-PT`, `Switch-PT-Empty`.
- No existen globales `addDevice` ni `addLink` en la 6.0.1.
- `lw.addDevice(type, model, x, y)` sigue dando Invalid arguments con (0,"2911",100,100), (1,"2960-24TT",300,100), (8,"PC-PT",100,200), con decimales y con 3 argumentos. Pendiente: firma real.
- Los argumentos IPC se serializan como `nombre("a","b",...)` (todo entre comillas); un error IPC detiene el script (el depurador captura la excepción).
- Doc pública de la API: https://tutorials.ptnetacad.net/help/default/IpcAPI/class_logical_workspace.html (bloqueada desde el entorno del asistente).

## HITO: addDevice funciona en la 6.0.1 con DOS argumentos
- `lw.addDevice(0, "2911")` -> devuelve el nombre auto (ej. `Router2`) y dispara `deviceAdded`.
  Con coordenadas (4 args), nombre extra o cualquier otra forma -> "Invalid arguments".
  (La doc moderna y PTBuilder usan `addDevice(type, model, x, y)`; la 6.0.1 no.)
- Posición: usar después `device.moveToLocation(x, y)` (existe en `device`); nombre: `device.setName(n)`.
- Receta mínima ya validada: addDevice(type, model) -> setName -> moveToLocation -> createLink(..., 8100) -> enterCommand.
- Tipos para addDevice: 0 router, 1 switch, 8 PC (los de `getType()`); laptop = 17 en la 6.0.1 (PTBuilder usa 18 en PT modernos).
- Pendiente: canal de comunicación con el exterior (sondeo/sondeo4_canal.js: ¿systemFileManager? ¿web view con XHR?).

## Sondeo 4 (canal con el exterior) y consola
- Script Engine 6.0.1: SIN `systemFileManager` y SIN `XMLHttpRequest` -> no hay buzón de archivos.
  Sí: `webViewManager.createWebView(titulo, url, w, h)`, `$se`, `$wvc/$wvca`, `setInterval`, almacén de datos, `_ScriptModule.ipcCall...`.
- Canal elegido: web view (QtWebKit) con polling HTTP a un servidor local; el panel llama a `$se("runCode", ...)`.
- Consola de un router nuevo: prompt `Continue with configuration dialog? [yes/no]:` -> enviar `no` antes de configurar.
- Prototipo en `prototipo/` (servidor.py + script_engine.js + interface.html). SIN token todavía: añadir autenticación antes de uso real.
- Servidor alternativo en PowerShell (`prototipo/servidor.ps1` + cliente `prototipo/pt.ps1`), sin admin ni Python.
  Diseño sin hilos: `/run` devuelve un id y el cliente consulta `/get?id=N`. Sin probar todavía en Windows.

## Canal web view resuelto (diseño)
- `$se`/`webView` NO existen en páginas `http://` (solo en interfaces `this-sm:`); `XMLHttpRequest` sí existe en el panel.
- `WV.evaluateJavaScript("1+1")` DEVUELVE el valor (`2`) -> el Script Engine consulta al panel con `setInterval`:
  panel (http) hace polling a `/next` y guarda en `pending`; engine llama `__take()`, ejecuta `eval(code)` y responde con `__result(id, enc)`.
- Código y resultado codificados con `encodeURIComponent`. `servidor.ps1` + `pt.ps1` probados por el usuario hasta la entrega al panel.
- Miembros de WebView: evaluateJavaScript(Async), evaluateCall(Async), setUrl, setHtml, show, hide, setGeometry, setWindowTitle, getWebViewId...

## HITO: canal completo funcionando (PT 6.0.1.0011, probado por el usuario)
- `pt.ps1 "ipc.network().getDeviceCount()"` -> `0` con el workspace vacío y `1` tras añadir un switch a mano.
- Cadena validada: cliente PowerShell -> `servidor.ps1` (127.0.0.1:54321) -> panel web view (XHR) -> Script Engine (`evaluateJavaScript`) -> `ipc` -> resultado de vuelta.
- Siguiente: (1) prueba de topología completa desde fuera (addDevice 2 args + setName + moveToLocation + createLink 8100 + consola con `no` al diálogo inicial),
  (2) token/autenticación en el puente, (3) servidor MCP (Python) que use este puente, (4) catálogo de modelos de la 6.0.1.

## HITO: topología completa construida y con ping desde fuera (PT 6.0.1.0011)
Probado por el usuario con `pt.ps1`: T-R1 (2911) + T-S1 (2960-24TT) + T-PC1/T-PC2, 3 cables, IPs, config de router por consola, ping PC1 -> router con respuesta (los primeros paquetes se pierden por ARP/STP: 1 de 4).
Lecciones para el constructor final:
- `setName` NO impide nombres duplicados por IPC (la GUI sí). Comprobar `net.getDevice(nombre)` ANTES de renombrar; `getDevice` devuelve el primero. Los duplicados se apilan en la misma posición y no se ven.
- `lw.removeDevice(nombre)` borra uno por llamada (bucle hasta `false`).
- `cl.enterCommand(...)` en routers es síncrono; en PCs `ping` devuelve al instante y la salida llega después: leer `cl.getOutput()` pasados unos segundos (y `isPortUp/isProtocolUp` para estado de enlaces).
- Router nuevo: responder `no` y luego `""` al diálogo inicial; luego `enable` / `configure terminal`.
- Cada comando de `pt.ps1` es independiente; las variables `lw`/`net` globales se definen una vez por arranque del módulo.

## Servidor MCP propio: `pt601_mcp/` (v0.1.0)
- Solo stdlib, protocolo MCP implementado a mano, puente HTTP con token + Host check, sin endpoint /run.
- 12 herramientas (`pt_status`, `pt_add_device`, `pt_add_link`, `pt_cli`, `pt_ping`...). Catálogo con modelos verificados/sin verificar.
- 20 pruebas offline (`tests/test_pt601.py`) + prueba e2e por stdio con panel simulado: OK.
- Pendiente de validar en un PT real: arranque con Python portátil, conexión desde VS Code, y que el panel con token funcione en el web view.

## v0.2: herramientas de alto nivel, documentación y skill
- Nuevas herramientas: `pt_build_topology` (plan JSON, autoposicionado, puertos automáticos, `@VECINO`), `pt_connect`, `pt_list_ports`,
  `pt_config`, `pt_router_config` (interfaces/subinterfaces dot1q/static/OSPF/EIGRP/RIP/DHCP), `pt_switch_config` (VLAN/access/trunk/SVI),
  `pt_dhcp_server`, `pt_dns_server`, `pt_describe`, `pt_clear_workspace`.
- Servicios de Server-PT: basados en la API moderna (`getProcess("DhcpServerMain")`, `addNewPool`, `addIpAddress`) con tolerancia a variantes.
  **SIN VALIDAR en la 6.0.1**: si fallan, `pt_describe device process=DhcpServerMain` lista los métodos reales.
- Documentación: `pt601_mcp/README.md`, `pt601_mcp/docs/herramientas.md`, `pt601_mcp/docs/ejemplos.md`; skill en `skill/SKILL.md`.
- 39 pruebas offline (`python3 -m unittest discover -s tests -v`).

## v0.3: Switch-PT-Empty (primer hallazgo con el MCP conectado a un PT real, 2026-10-02)
- **Primera conexión real OK**: el MCP, el panel con token y el Script Engine funcionan en una 6.0.1.0011 (`pt_status`, `pt_add_device`, `pt_list_ports`, `pt_eval`).
- `Switch-PT-Empty` nace **sin puertos** (solo `Vlan1`). Hay que apagarlo y meterle módulos. Tiene 10 ranuras.
- Firma correcta: `d.addModule("<ranura>", 4, "PT-SWITCH-NM-1CFE")` -> `true`. La ranura n da el puerto `FastEthernet<n>/1`.
  El `4` (tipo de módulo) y el modelo se descubrieron con `d.registerEvent("moduleAdded", null, function(src,args){...})`
  (args.type=4, args.model) añadiendo un módulo a mano en la pestaña Physical.
- **Con 2 argumentos** (`addModule("0","PT-SWITCH-NM-1CFE")`) PT responde `Invalid arguments for IPC call "addModule"`.
- **Trampa de la ventana Debug**: ese error de IPC detiene el motor del módulo y `try/catch` no lo evita; hasta hacer Stop/Start
  todo lo demás da "PT no respondió en 25 s". Cierra la ventana Debug antes de probar cosas, y prueba UNA firma por llamada.
- El texto de `addModule` solo aparecía como nombre dentro de `PacketTracer6.exe` (sin firma): no hay documentación local del API.
- Arreglo: `catalog.EMPTY_MODULES` + `jsgen.add_device(..., modules)` + parámetro `ports` (1-10, por defecto 10) en `pt_add_device`
  y en los planes. `Router-PT-Empty` sigue sin poblarse (módulos de router sin comprobar).
- 41 pruebas offline.

## v0.3 (cont.): DHCP, cables y escenario de 3 ciudades validados en PT real (2026-10-02)
- Red construida de verdad: 4 `Switch-PT-Empty` (10 puertos), 15 equipos finales, 1 Server-PT; 19 cables; los 15 equipos reciben IP por DHCP.
- **Cable automático (8107) rechazado** en los puertos de módulo del Switch-PT-Empty; 8100 (recto) sí. `connect_auto` ahora prueba 8107 y, si falla,
  recto/cruzado según los equipos (mismos tipos -> cruzado primero). Probado en PT real: `pt_connect` OK en los 17 cables restantes.
- **DHCP de Server-PT**: el proceso se llama **`DhcpServer`** (no `DhcpServerMain`/`DHCPServerMain`: `getProcess` devuelve null si el nombre no existe).
  Miembros: addPool, getPool, getPoolAt, getPoolCount, addExcludedAddress, removePool, setEnable, isEnable...
  Hay un pool por defecto `serverPool` (192.168.1.0/24, rango 192.168.1.0-192.168.2.255) con getters/setters:
  `setStartIp`, `setEndIp`, `setDefaultRouter`, `setDnsServerIp` (cadenas de IP) -> **funcionan**. `setNetworkMask("255.255.255.0")` -> *Invalid arguments*
  (cuelga con Debug abierta): no se usa. `addNewPool` no existe. `jsgen.dhcp_server` reescrito; `max_users` se traduce a IP final (inicio + n - 1).
- **Los clientes DHCP no piden IP solos**: `p.setDhcpClientFlag(true)` antes de existir cable/servidor deja 0.0.0.0. Hay que lanzar `ipconfig /renew`
  desde la consola del PC (`pt_cli`). `pt_build_topology` ahora añade pasos "DHCP renovar X" tras configurar el servidor.
- `getDefaultGateway` no existe en el puerto de la 6.0.1 (TypeError normal). Los PCs/portátiles dan IP/máscara con `getIpAddress/getSubnetMask`.
- Regla práctica: **cada IPC con argumentos erróneos cuelga el motor mientras Debug esté abierta** (aparece sola); probar una llamada cada vez y
  tener a mano Stop/Start. Cada vez que cambie el código Python hay que recargar el servidor MCP (/mcp) y luego Stop/Start en PT (token nuevo).
- **Pendiente**: `jsgen.dns_server` sigue con nombres de la API moderna (`DnsServerMain`/`addIpAddress`): probablemente el proceso real sea `DnsServer`;
  comprobar con `pt_describe process=DnsServer` antes de tocarlo. 43 pruebas offline.


## 2026-10-03: reglas.md y mejoras pendientes
- Revisado el GitHub: el commit v0.3 (hecho desde el VS Code del usuario) valida en un PT real `Switch-PT-Empty` con módulos, cables auto con reintento,
  DHCP de Server-PT (`DhcpServer`) y una red de 3 ciudades con 15 equipos por DHCP. DNS sigue sin validar. 43 pruebas OK.
- Nuevo `reglas.md` (plantilla con `PENDIENTE`): el usuario define nombres, IPs, VLANs, puertos, servidores, seguridad y layout; manda sobre los defaults.
  `CLAUDE.md` y `skill/SKILL.md` obligan a leerlo antes de crear nada.
- `CLAUDE.md` recoge la mejora pedida: representar instrucciones e identificar la posición de los switches (dos lecturas posibles; hay que confirmar con el usuario).
  Observación del código: `plan.auto_layout` coloca todos los switches en el mismo nivel y no conoce sedes ni jerarquía núcleo/acceso.

## 2026-10-03 (aclaración del usuario)
- Posición de los equipos: en clase se usa un **esquema exacto de organización**; el mapa debe seguirlo (sección 7 de `reglas.md`, pendiente de rellenar).
  `plan.auto_layout` es genérico y no lo cumple; habrá que hacerlo configurable o usar posiciones explícitas.
- Interpretación de documentos con instrucciones (enunciados): lista de requisitos → preguntar huecos → aplicar `reglas.md` → plan con `dry_run` → verificar al final (ver `CLAUDE.md`).

## 2026-10-03: cómo debe aprender el MCP las costumbres del usuario
Objetivo: que el MCP se dé cuenta por sí solo de los detalles que en clase se dan por sabidos y el profesor no escribe en los enunciados
(cómo se posiciona todo, cómo se nombra, desde dónde se ponen las IPs…), y que mejore en todos los aspectos. Nada de esto se aplica aún; es la guía de diseño.

**Limitación a tener presente:** el modelo no recuerda nada entre sesiones por sí solo. Lo aprendido solo permanece si se **escribe** donde el asistente lo lee siempre.
Por eso hay tres capas, cada una con su sitio:

| Qué se aprende | Dónde se guarda | Quién lo aporta |
|---|---|---|
| Costumbres implícitas del usuario (nombres, inicio de IPs, orden de puertos, esquema del mapa, relación nombre↔IP) | `reglas.md` | El usuario, y el MCP las **deduce** de los trabajos del usuario |
| Lo que pide cada práctica | El enunciado de cada práctica | El profesor |
| Cómo se comporta Packet Tracer 6.0.1 (trampas, firmas, límites) | `NOTAS.md`, `CLAUDE.md`, código y pruebas | El MCP, al descubrirlo (ya funciona: v0.3) |

**Bucle de aprendizaje a partir de los trabajos del usuario** (el usuario tiene hechas las mismas prácticas, salvo la documentación):
1. Un caso por práctica: enunciado + trabajo de referencia del usuario (`.pkt`; es binario y solo se lee abriéndolo en PT con el MCP conectado).
2. **Esperado:** abrir el `.pkt` y leer la red entera (nombres, IPs, VLANs, puertos, cables, posiciones) con una futura `pt_snapshot`.
3. **Obtenido:** pedir al MCP que construya la práctica desde el enunciado.
4. **Comparar** esperado y obtenido (hace falta un comparador): cada diferencia es un fallo de costumbre.
5. Cada diferencia se vuelve permanente: una regla en `reglas.md` o una corrección del código con su prueba.

**Deducción de costumbres:** en vez de que el usuario escriba cada norma, el asistente la deduce de varios trabajos y la **propone** con evidencia
(p. ej. *«el gateway es siempre la `.1`; visto en 4 de 4 prácticas; ¿la anoto?»*). Solo pasa a `reglas.md` cuando el usuario la confirma.
Cautelas: con una sola práctica no se distingue costumbre de coincidencia (hacen falta ~3 o más); nada deducido se aplica como regla sin confirmación.

**Costumbres que el MCP debe llegar a captar** (ejemplos dados por el usuario):
- Cómo se posiciona cada tipo de equipo en el mapa (esquema exacto de clase, sección 7 de `reglas.md`).
- Cómo se nombran los equipos.
- **El nombre del equipo corresponde a la IP de ese equipo** (ejemplo real del usuario). *Falta concretar el cómo*: ¿el nombre incluye el último octeto, la IP entera,
  el número de red? Se preguntará con ejemplos de sus prácticas antes de convertirlo en regla en `reglas.md`.

**Pendiente** (cuando se aborde): `pt_snapshot`, comparador esperado/obtenido, carpeta de casos (enunciado + trabajo de referencia), sección de «propuestas pendientes
de confirmar» en `reglas.md`. Si el repositorio es público, quitar datos personales de los trabajos antes de subirlos.

## 2026-10-03: primer trabajo real analizado (Práctica 2, «Ejercicio 4 DHCP») y herramientas nuevas
- **Dos servidores en el mismo puerto (fallo real):** en Windows `http.server` pone `SO_REUSEADDR`, que deja a DOS procesos escuchar en
  127.0.0.1:54321. Con dos sesiones de Claude había dos `run.py`: el panel de PT hablaba con el viejo y el nuevo decía «PT no conectado»
  (sin ningún 401). Arreglo: `bridge.ExclusiveHTTPServer` (`allow_reuse_address = False` + `SO_EXCLUSIVEADDRUSE` en Windows); la segunda
  instancia ya falla al abrir el puerto y avisa. Prueba: `test_port_is_exclusive`.
- **Panel:** ante un `HTTP 401` (servidor reiniciado, token nuevo) ahora se recarga solo (`location.reload()`); ya no hace falta Stop/Start
  cada vez que se reinicia el servidor MCP. (Requiere un Stop/Start la primera vez para cargar el panel nuevo.)
- **Registro en Claude Code:** `claude mcp add --scope user packet-tracer-601 "--" C:\Python312\python.exe D:\...\pt601_mcp\run.py`.
  Las herramientas no aparecen en la conversación en curso hasta recargar la ventana/sesión. El usuario SÍ tiene Python instalado (`C:\Python312`).
- **Servicios de Server-PT (6.0.1 real).** `getProcess(nombre)` devuelve null si no existe. Procesos y miembros comprobados:
  `DhcpServer` (setEnable/isEnable), `DnsServer` (setEnable/isEnabled, addIpAddress, removeIpAddress), `HttpServer` (setEnable/isEnabled),
  `HttpsServer` (setHttpsEnable/isHttpsEnabled), `TftpServer`, `FtpServer`, `NtpServer` (**setEnabled**/isEnabled), `SmtpServer`, `Pop3Server`,
  `SyslogServer` (setEnable/isEnabled), `EmailServer` (solo addUser). Todos los setters reciben un booleano (probados `setEnable(false)`,
  `setEnabled(false)`, `setHttpsEnable(false)`). No aparece ningún proceso AAA con los nombres probados.
- **Lectura de un `.pkt`:** dispositivo `getXCoordinate/getYCoordinate`; PC/servidor `getDhcpFlag` (los switches NO lo tienen: TypeError);
  puerto `getIpAddress/getSubnetMask/isDhcpClientOn/getLink`; enlace `getPort1/getPort2/getConnectionType` (8100/8101) y
  `puerto.getOwnerDevice().getName()`; pool `getStartIp/getEndIp/getSubnetMask/getDefaultRouter/getDnsServerIp/getDhcpPoolName`.
  El gateway de un PC no se lee por IPC: `ipconfig` en su consola (`pt_cli`).
- **Herramientas nuevas:** `pt_snapshot` (red entera: posiciones, IPs, cables con puertos, servicios y pools) y `pt_server_services`
  (deja encendidos solo los servicios indicados; también `"services": [...]` en `servers[]` del plan). 47 pruebas.
- **Costumbres aprendidas** (anotadas en `reglas.md`): nombre del equipo = último octeto de su IP; equipos desde la `.10`; gateway `.1`;
  servidor DHCP `.3` en su propio switch y con solo DHCP encendido; `Switch-PT-Empty` con los puertos justos, `Fa0/1` = uplink;
  cruzado entre switches y recto a equipos; esquema servidor → su switch → switches de sede → PCs arriba / portátiles abajo.
  `CopyNN` es el nombre que pone PT al copiar y pegar, no una convención.
- **Decisión del usuario:** el asistente anota reglas y cambia código sin pedir confirmación; solo informa. `ejemplos/` no se sube (`.gitignore`).
- **Pendiente:** `plan.auto_layout` con el esquema de clase y numeración desde la `.10`; notas en el mapa (`lw.addNote`, firma sin comprobar);
  argumentos de `DnsServer.addIpAddress`; comparador esperado/obtenido.
- **`device.serializeToXml()`** funciona en la 6.0.1 y devuelve TODA la configuración del equipo (7–10 KB): módulos por ranura (`<MODEL>PT-SWITCH-NM-1CFE</MODEL>`),
  `<IP>`, `<SUBNET>`, `<PORT_GATEWAY>`, `<PORT_DNS>`, `<PORT_DHCP_ENABLE>`, `<GATEWAY>`, `<SYS_NAME>` (hostname), DNS/correo/inalámbrico. Es la forma de
  leer lo que no tiene getter (gateway y DNS de un PC, módulos instalados). Práctica 2: switches con hostname por defecto `Switch` y sin configuración;
  equipos finales solo con IP/máscara/gateway (DNS vacío). Enunciados: la jerarquía de puntos está en la negrita del Word (sección 11 de `reglas.md`).

## 2026-10-03: segundo trabajo analizado (Práctica 1C, «Ejercicio 3»: 3 HTTP + DNS, 4 sedes, 172.26.1.0 / 255.255.0.0)
- **Coincide con la Práctica 2 (2 de 2):** nombre = último octeto; equipos desde la `.10` sin saltos; numeración empezando por la sede de abajo,
  portátiles antes que PCs y el más bajo a la derecha; `Fa0/1` de cada switch de sede = uplink y luego PCs y portátiles de izquierda a derecha;
  puertos justos; cruzado entre switches y recto al resto; hostname `Switch` sin tocar; esquema servidores → su switch → columna de sedes → PCs arriba/portátiles abajo.
- **Nuevo:** máscara por clase (`255.255.0.0` para 172.26.x.x); gateway `.1` también en servidores; DNS (`172.26.1.2`) puesto en todos los equipos y servidores;
  servidores en columna a la izquierda; nombres `HTTP-1..3` y `DNS`.
- **Distinto:** en el switch de servidores van primero los servidores y luego las sedes (en la P2 era al revés). Los servicios de los servidores están de fábrica
  y el DNS apagado y sin registros (`<DNS_SERVER><ENABLED>0`), o sea que esa práctica no configuraba servicios.
- **Dos Packet Tracer abiertos:** cada ventana de PT es un proceso con su propio motor de scripts. El módulo solo corre donde se pulsó Start; al abrir otro
  `.pkt` con doble clic se abre OTRO proceso sin módulo y el MCP sigue viendo el archivo antiguo. Comprobar con
  `Get-Process PacketTracer6 | Select MainWindowTitle`. Abrir con File → Open dentro del mismo PT, o Stop en uno y Start en el otro (nunca dos módulos a la vez).
- La configuración DNS de un Server-PT se lee en `serializeToXml()` → `<DNS_SERVER><ENABLED>…<NAMESERVER-DATABASE>`; gateway y DNS de un equipo, en `<GATEWAY>` y `<SERVER_IP>`.

## 2026-10-03: tercer trabajo analizado (Práctica 1B, «Ejercicio 2»: HTTP + DNS, 4 sedes, 192.168.1.0)
- **Confirma (3 de 3):** nombre = último octeto; sede de abajo primero, portátiles antes que PCs, el más bajo a la derecha; `Fa0/1` = uplink;
  puertos justos; cruzado entre switches; hostname sin tocar; gateway `.1`; mismo esquema del mapa. DNS del servidor puesto en todos los equipos (2 de 2 con DNS).
- **Regla de servicios aclarada por el usuario:** los servicios de un Server-PT solo se configuran (y se apagan los demás) si el enunciado pide ese
  servicio; si solo pide la IP, se dejan de fábrica. Al construir, `services` en el plan SOLO cuando el enunciado configure el servicio.
- **Puertos del switch de servidores:** servidores primero y luego switches (P1B y P1C; la P2 es la excepción).
- **Excepciones de este archivo** (sección 12 de `reglas.md`): numeración desde la `.20`, switch intermedio `sw-1`, un portátil de más y cuatro despistes de IP/gateway/DNS.
- Truco práctico: los scripts largos de edición con comillas simples fallan dentro de un heredoc de bash; escribirlos a un `.py` temporal y ejecutarlos.

## 2026-10-03: primera corrección hecha por el asistente en un trabajo real (Práctica 1B) y lo que enseñó de la API
- Hecho en PT: borrado el portátil sobrante de `SW-Jupiter` y su módulo; 18 equipos renombrados y con IP `.10`–`.27`, máscara, gateway `.1` y DNS `.3`;
  comprobado sin duplicados y con ping a `HTTP` (192.168.1.2) desde dos equipos. El primer ping tras encender un switch pierde 3 de 4 (STP).
- **Gateway de un PC/portátil:** `puerto.setDefaultGateway(ip)` solo cambia `<PORT_GATEWAY>`; el que enseña la ventana «IP Configuration» es el del
  dispositivo, `<GATEWAY>`, que se pone con **`device.setDefaultGateway(ip)`**. `jsgen.set_ip` ponía solo el del puerto: ahora pone los dos.
- **DNS de la configuración IP:** proceso **`DnsClient`** del equipo: `setServerIp("ip")` / `getServerIp()` (comprobado). Nuevo parámetro `dns` en
  `pt_set_ip` y en `hosts[]` del plan (`dns_server` en `servers[]`, porque `dns` ahí es el servicio).
- **Quitar un módulo:** `device.removeModule("<ranura>")` -> true (un solo argumento, con el equipo apagado; comprobado en `Switch-PT-Empty`).
  Los cables de los demás puertos se conservan tras apagar y encender.
- La consola de un PC solo admite `ipconfig <IP> <máscara> [<gateway>]`, `/renew` y `/release`: el DNS no se puede poner por consola.
- Nueva herramienta `pt_rename_device` (comprueba que el nombre nuevo no exista). 49 pruebas.

## 2026-10-03: cuarto trabajo analizado (Práctica 1A, «Ejercicio 1»: HTTP + DNS, 4 sedes, 172.26.1.0 / 255.255.0.0)
- Los 22 equipos cumplen todas las reglas (nombre = último octeto, `.10`–`.31`, orden de numeración y de puertos, cables, gateway, DNS, servicios de fábrica).
- Fallos del archivo (sección 12 de `reglas.md`, sin corregir): `HTTP` sin IP; switch `ServerMadrid` sin el prefijo `SW-` y con un módulo de más;
  enlaces a las sedes en el switch de servidores fuera del orden de arriba abajo.
- Orden vertical de los servidores: no hay patrón fijo todavía (P1A y P1B por IP ascendente; P1C en el orden del enunciado, con el DNS `.2` abajo).
- Para leer un archivo en una sola llamada sin pasar el límite de 6000 caracteres de `pt_eval`: una línea por equipo y nombres de puerto abreviados.

## 2026-10-03: corrección completa de la Práctica 1A por el asistente y más API descubierta
- Hecho en PT: IP/gateway/DNS del servidor `HTTP`; switch renombrado a `SW-ServerMadrid`; módulo sobrante quitado; los cuatro enlaces a las sedes
  recableados de arriba abajo; `HTTP` y `DNS` intercambiados de sitio. Verificado: sin puertos libres ni duplicados, 24 equipos con IP/máscara/gateway/DNS
  correctos y ping a `172.26.1.3` desde `10` (4/4) y `31` (3/4).
- **`lw.deleteLink("<dispositivo>", "<puerto>")`** -> true (dos argumentos; comprobado). Herramienta nueva `pt_remove_link`.
- **`moveToLocation(x, y)` y `getXCoordinate()/getYCoordinate()` no usan el mismo punto:** mover a (x, y) y leer devuelve (x+16, y+26) en un Server-PT y
  (x+25, y+12) en un switch (esquina frente a centro del icono). `jsgen._move` ahora mueve, mide el desfase y corrige, de modo que las coordenadas
  leídas con `pt_snapshot` valen tal cual para colocar. **Las construcciones anteriores a este cambio quedaban desplazadas esa cantidad.**
- **Cables nuevos entre switches tardan ~30–50 s en dejar pasar tráfico** (STP): el primer ping tras recablear o tras apagar/encender un switch falla entero
  o casi; esperar y repetir antes de dar la prueba por mala.
- Herramienta nueva `pt_remove_module` (`removeModule("<ranura>")`, apagando y encendiendo). 28 herramientas, 50 pruebas.

## 2026-10-03: investigación libre en un archivo vacío (notas, router vacío, DNS, posiciones) y generador de planes de clase
- **Notas del mapa:** `lw.addNote(x, y, tamaño_letra, "texto")` -> id `{uuid}` (4 argumentos; comprobado). `lw.getCanvasItemIds()` (lista separada por comas),
  `getCanvasItemX(id)/getCanvasItemY(id)` (devuelven ~x+26, y+6 respecto a lo pedido para un texto tipo IP) y `lw.removeCanvasItem(id)` -> true.
  El texto de una nota no se puede leer. Herramientas `pt_add_note`, `pt_list_notes`, `pt_remove_note`; sección `notes` en los planes.
- **`Router-PT-Empty`:** nace sin puertos y con 10 ranuras. `addModule("<ranura>", 3, modelo)` (tipo de módulo **3**; el del switch es 4). Modelos que acepta
  y puerto que dan: `PT-ROUTER-NM-1CFE` FastEthernet<n>/0, `-1CGE` GigabitEthernet<n>/0, `-1S` y `-1SS` Serial<n>/0, `-1FFE` FastEthernet (fibra),
  `-1FGE` GigabitEthernet (fibra), `-1CE` Ethernet<n>/0, `-1AM` Modem<n>/0. `pt_add_device` le pone 2 FastEthernet por defecto (`ports` para otro número).
  Un tipo de módulo equivocado devuelve `false` (no da error IPC), así que se puede sondear en bucle.
- **Posición de equipos recién creados:** al terminar el script que crea un equipo, PT lo recoloca solo (la x baja medio icono; la y no). Medir el desfase
  dentro del mismo script no sirve: `pt_add_device` ahora hace el ajuste fino en una segunda llamada (`move_device`), que sí es exacta en equipos asentados.
- **DNS de Server-PT: limitación sin resolver.** `DnsServer.addIpAddress("nombre", "ip")` devuelve true, `getEntryCount()` sube y `getIpAddOfDomain` devuelve la IP,
  pero un PC no resuelve el nombre (`nslookup`: *Non-existent domain*; el PC sí llega al servidor) y `<NAMESERVER-DATABASE/>` sigue vacío en el XML, ni
  reiniciando el servicio. Otros miembros: getEntryAt (objeto con `first`/`second`), isDomainNameExisted, removeIpAddress, get/setPortNumber.
  `pt_dns_server` avisa de ello. **Siguiente paso:** que el usuario cree un registro A a mano y leer el XML del servidor para ver cómo se guarda.
- **`pt_class_plan`** (`plan.class_plan`): del enunciado (switch de servidores, servidores con IP, sedes con nº de PCs/portátiles) saca el plan completo con las
  reglas de clase. Probado en PT real con una red reducida (2 servidores, 2 sedes, 6 equipos): 29 pasos sin error, posiciones exactas tras el ajuste,
  gateway/DNS correctos y ping al servidor. Los servicios solo entran en el plan si se indican (`services`, `dhcp`).
- Los switches también tienen proceso `DnsClient` (sin uso): `pt_snapshot` solo muestra gateway/DNS cuando hay alguno puesto. 32 herramientas, 58 pruebas.

## 2026-10-03: quinto archivo analizado (`ESQUEMA1.pkt`: 4 routers, 8 redes, rutas estáticas) y dos arreglos de consola
- Primera llamada real a `pt_snapshot` como herramienta (tras recargar VS Code): funciona y lee también los routers (IP por interfaz).
- **Este archivo es del curso pasado y NO es fuente de reglas** (dicho por el usuario): sirve para mejorar las herramientas, no para `reglas.md`.
  Lo que contiene, como referencia técnica: `Router-PT-Empty` + `PT-ROUTER-NM-1CFE`, un switch entre cada router y lo demás, cable recto,
  una red /24 por switch, red de tránsito en un switch central, router = `.1` de cada LAN, PCs en la `.10`, rutas estáticas, nombres de fábrica.
  Las reglas de routers siguen `PENDIENTE` hasta ver una práctica de este curso.
- **Consola dormida:** una consola sin usar está en `getMode() == "logout"` con `getPrompt() == ""`; el primer `enterCommand` solo la despierta y se pierde
  (se perdía el `enable` y los `show` daban «Invalid input» en modo usuario). `jsgen.cli` ahora manda un Enter antes si la ve así.
- **`terminal length 0` no existe** en el IOS de la 6.0.1 y `show running-config` se queda en `--More--` (se sale mandando `q`). Para leer la configuración
  entera: `serializeToXml()` → `<RUNNINGCONFIG><LINE>…`. Herramienta nueva `pt_running_config`. `show ip route` y `show ip protocols` caben sin paginar.
- Las rutas puestas desde la pestaña Config de PT aparecen como `ip route <red> <máscara> <siguiente salto>`. 33 herramientas, 60 pruebas.

## 2026-10-03: retos libres sobre `4.pkt` (archivo del curso pasado; NO es fuente de reglas, solo de herramientas)
Archivo: 2 routers `Router-PT-Empty`, 2 LAN con Server-PT DHCP, 2 `AccessPoint-PT` con WPA2-PSK y portátiles wifi, red de tránsito por un switch.

**Reto 1: tercera red con router nuevo, DHCP en el router y rutas estáticas — conseguido** (pings cruzados entre las 3 LAN, también desde wifi).
- `pt_router_config` validado en PT real con un `Router-PT-Empty` nuevo: responde solo al diálogo inicial, interfaces, rutas estáticas y `dhcp_pools`
  (el pool del router repartió `.10` y `.11` con `excluded` `.1`–`.9`).
- **Trampa grande — distancia física.** Cada equipo tiene una posición física (`<COORD_SETTINGS><X_COORD>` en `serializeToXml`). Los que vienen en un
  archivo hecho a mano están en ~(1918, 1918); los creados por IPC nacen en (0, 0). **Un cable de cobre entre uno y otro se crea (`createLink` = true) pero
  queda sin señal**: puerto del switch `down/down`, interfaz del router `up / protocol down (disabled)`. Nuevo↔nuevo y viejo↔viejo funcionan.
  La **fibra sí funciona** (`PT-SWITCH-NM-1FFE` + `PT-ROUTER-NM-1FFE`, cable 8103; los puertos se siguen llamando `FastEthernet<n>/…`).
  `device.moveToLocInPhysicalWS(x, y)` devuelve false (también en equipos antiguos) y `getXPhysicalWS()` da -1: no se puede acercar el equipo por IPC;
  `getGeoView()`/`getRackView()` no exponen nada útil. `pt_connect`/`pt_add_link` ahora **avisan** cuando la distancia supera 100 y el cable no es fibra.
  Consecuencia práctica: ampliar un `.pkt` existente con equipos nuevos exige fibra en los enlaces nuevo↔antiguo; construir desde cero no tiene este problema.
- **`setPower(false/true)` sin `skipBoot()` deja el equipo arrancando en tiempo real (minutos)**, con la consola en el cargador y sin servicio.
  `pt_remove_module` y el nuevo `pt_add_module` llaman a `skipBoot()`.
- **Un reinicio pierde la configuración no guardada**: tras configurar un router hay que hacer `write memory` (`save: true` en `pt_config` /
  `pt_router_config`, ahora también en el esquema de esta última).
- Añadir un módulo a un equipo ya creado funciona (`pt_add_module`): `addModule("<ranura>", tipo, modelo)` con tipo 4 en switch, 3 en router y
  **9 en portátil**. Quitar el módulo de cobre de un portátil: `removeModule("0")`.
- En un `.pkt` hecho a mano no vale suponer que `Fa0/1` del switch va al router: leer siempre los enlaces antes de tocar (me equivoqué una vez).
- Si mientras trabajo aparecen comandos que no he enviado en una consola (p. ej. `router rip`) o un equipo se reinicia, es el usuario tocando PT a la vez:
  volver a leer el estado antes de seguir.

**Reto 2: celda inalámbrica creada por IPC — conseguido.**
- Punto de acceso: `AccessPoint-PT` (puertos `Port 0` = cable, `Port 1` = radio). Proceso `WirelessServer`: getSsid/setSsid, getAuthenType,
  getWepProcess, resetAllAssociations. Por defecto SSID `Default` sin clave.
- Portátil inalámbrico: apagar, `removeModule("0")`, `addModule("0", 9, "PT-LAPTOP-NM-1W")` → puerto `Wireless0`. Proceso `WirelessClient`:
  setSsid/getSsid, getCurrentApMac (asociado si devuelve una MAC), perfiles (addProfile, setCurrentProfile…). `PT-LAPTOP-NM-1W-A` es la variante 802.11a.
- El enlace de un puerto inalámbrico es un objeto `Antenna` (sin `getPort1/getPort2`): rompía `pt_snapshot`; ahora lo marca como «inalámbrico».
- Con el mismo SSID en AP y portátil y DHCP activado, el portátil recibió IP del pool del router y respondió a ping entre redes.
- Pendiente: claves WPA (`getWepProcess`, sin explorar) y una herramienta `pt_wireless` que empaquete todo esto.

**Otros**
- `pt_ping` (y cualquier comando) lanzado en un PC mientras otro comando asíncrono (`ipconfig /renew`) sigue en marcha se pierde: esperar a que vuelva el prompt.
- En un router, una palabra que no es un comando en modo usuario (`end`) dispara «Translating… domain server» y bloquea la consola varios segundos.
- `NtpServer` del Server-PT: setEnabled/isEnabled, setKeyID/getKeyId, getServerMd5Str. `ntp server <ip>` en el router: sin comprobar todavía.
- Prueba intermitente arreglada: el puente contesta 404 a un POST desconocido **después** de leer el cuerpo (en Windows la conexión se cortaba a veces).
- 33 herramientas, 62 pruebas.

## 2026-10-03 (tarde): más retos sobre `4.pkt` — DNS a mano, navegador, red grande con OSPF (no son reglas)
**DNS: cómo guarda PT un registro hecho a mano.** El usuario creó `clase.com` → `192.168.43.2` en Services > DNS. En el XML del servidor:
`<DNS_SERVER><ENABLED>1</ENABLED><NAMESERVER-DATABASE><RESOURCE-RECORD><TYPE>A-REC</TYPE><NAME>clase.com</NAME><TTL>86400</TTL><IPADDRESS>…`.
`DnsServer.getEntryCount()` da 0 para ese registro: **son dos almacenes distintos**. `addIpAddress` escribe en el antiguo (el que nadie consulta) y no hay
ninguna función IPC que escriba en `NAMESERVER-DATABASE`. Conclusión: **los registros DNS se crean a mano**; el MCP solo puede encender el servicio,
poner el DNS en los equipos y comprobar que resuelve.

**Navegador por IPC (`HttpClient`).** En PC/portátil/servidor: `getProcess("HttpClient").go("http://…")` → true, y la página llega después a
`getLastPageContent()` (cadena vacía si no hubo respuesta o el nombre no se resuelve). Comprobado por IP y por nombre (`clase.com`), con control negativo
(nombre inexistente y servidor con HTTP apagado → vacío). Herramienta nueva `pt_http_get`: sirve para el «Demostrar que podemos conectarnos al Servidor Web».

**Otros procesos descubiertos** (sin usar aún): `HttpServer` (getPage, setUsername/setPassword), `FtpServer.getFtpUserAccountManager`,
`EmailServer` (addUser, deleteUser, changePassword), `AcsServer` (AAA: addToUserMap, addToClientMap, enableACSServerService), `ArpProcess.getArpTable`,
`IcmpProcess` (startPing, startTraceRoute), `DhcpClient` (dhcpRelease), `EmailClient`, `PppoeClient`, `TcpProcess`, `UdpProcess`, `SyslogServer`.

**Reto 3: red de empresa generada de una vez — conseguido.** `plan.routed_plan` / `pt_routed_plan`: un `Router-PT-Empty` + `Switch-PT-Empty` por sede,
switch central de tránsito (`10.0.0.0/24`), la `192.168.50.0/24` troceada en cuatro `/26`, OSPF área 0, DHCP en los routers de dos sedes, granja de
servidores (DNS, HTTP, NTP). Resultado en PT real: 20 equipos, 19 cables, 56 pasos sin error; OSPF converge en ~40 s (rutas `O` en `show ip route`);
los seis clientes DHCP recibieron exactamente la IP de su nombre (`74`→`.74` … `140`→`.140`); pings entre sedes; web por IP; NTP sincronizado
(`show ntp status`: *Clock is synchronized, stratum 2, reference is 192.168.50.4*).
- **Nombre = último octeto con subredes:** al trocear una sola `/24`, los equipos desde la `+10` de cada subred tienen octetos distintos (74, 138, 202…),
  así que el nombre por último octeto sigue siendo único. Con una `/24` por sede se repetiría (el generador usa entonces `<Sede>-<octeto>`).
- **DHCP en orden:** un cliente con DHCP activado pide IP por su cuenta en cuanto puede; para que nombre e IP coincidan hay que activar los clientes de uno
  en uno, en orden, esperando a que cada uno tenga IP. Los primeros `ipconfig /renew` fallan mientras el puerto del switch no reenvía (~30 s): reintentar.
  `build_topology` ahora lo hace así cuando el DHCP lo da un router del plan (`expect_ip` comprueba el resultado) y guarda los routers (`save`).
- `pt_server_services` validado en PT real (un servicio por servidor). `ntp server <ip>` + `show ntp status` funcionan; `show ntp associations` no existe.
- Si la consola de un router se quedó en `(config…)`, `enable` da error: `pt_cli` ahora manda `end` antes de empezar.
- El usuario no veía lo que construía porque lo puse a x>1400: **construir siempre en la zona visible** (cerca de lo existente o debajo), y decir dónde.
- 35 herramientas, 68 pruebas.

## 2026-10-03 (noche): toda la red de `4.pkt` unida, cortafuegos y más investigación del DNS (no son reglas)
**Reto 4: unir la red de arriba (192.168.40–43) con las cuatro sedes (192.168.50.x/26) — conseguido.**
- `R-Firewall` (`Router-PT-Empty`, 2 puertos): `Fa0/0 192.168.42.4` en `SW-Transito` y `Fa1/0 10.0.0.5` en `SW-Core` (un módulo más en cada switch con
  `pt_add_module`, validado como herramienta). OSPF área 0 en los ocho routers; los tres de arriba lo recibieron con `pt_router_config`.
- **OSPF tarda**: tras tocar un switch de tránsito (se reinicia) las adyacencias se rehacen; contar 1–2 minutos y mirar `show ip ospf neighbor`
  (`FULL`) y `show ip ospf database` antes de dar nada por roto. Las rutas `O` aparecen bastante después de ver `FULL`.
- Los routers antiguos tenían rutas estáticas hacia sus propias redes con salto `0.0.0.0` y hacia las vecinas; las quité al pasar a OSPF y ejecuté
  `clear ip ospf process` (pregunta `[no]:` → contestar `yes`). No quedó demostrado cuál de las dos cosas, o solo la espera, desbloqueó las redes 40 y 41.
- **Cortafuegos con ACL extendida** en `R-Firewall`: `access-list 110 deny icmp 192.168.41.0 0.0.0.255 192.168.50.0 0.0.0.63`, `permit ip any any`,
  `ip access-group 110 in` en `Fa0/0`. Verificado: `PC1` (41) no hace ping a los servidores (*Reply from 192.168.42.4: Destination host unreachable*),
  `PC0` (40) sí, y la web (TCP 80) pasa desde `PC1` y desde portátiles wifi de las dos mitades. `permit ip any any` deja pasar OSPF.
  `ios.router_config` admite ahora `acls: [{number, rules[], apply[{port, direction}]}]`.
- Pings entre extremos con TTL 125 (tres routers por medio).

**DNS automático: tres vías más probadas, ninguna sirve.**
1. Nombres de proceso alternativos (`NameServer`, `DnsServerProcess`…): no existen.
2. `DnsClient.addIpAddress(nombre, ip)` en el PC (caché local): devuelve true y `getIpOfHost` lo ve, pero ni `ping nombre` ni el navegador lo usan.
3. Reescribir el archivo: `appWindow.fileSaveToBytes()` devuelve un array de ~109 000 bytes con signo y existe `fileOpenFromBytes`, pero el contenido
   **no** es el XOR(longitud−i)+zlib de PT 5: la cabecera decodificada no es zlib y cambia en cada llamada. Sin conocer el cifrado no se puede editar.
   (Además reabrir el archivo entero para añadir un registro sería arriesgado.)
Conclusión firme: en la 6.0.1 el registro DNS se crea a mano; el MCP lo comprueba con `pt_http_get` o `nslookup`.
- `appWindow` expone además fileNew/fileOpen/fileSave/fileSaveAs, getPhysicalLocationDialog, getSimulationPanel, getUserCreatedPDU… (sin explorar).

**Consola:** PT recorta el historial de la consola y `pt_cli` devolvía páginas de salida vieja; ahora localiza lo nuevo por una marca. Con el usuario
trabajando a la vez en la pestaña Config de un router, la consola queda en `(config)` (ya se sale con `end`).

## 2026-10-03 (noche): herramientas nuevas validadas en PT real y un fallo de diseño corregido
- `pt_http_get` validada como herramienta: por IP, por nombre (`clase.com`) y caso negativo (servidor con HTTP apagado → error claro).
  `pt_cli` devuelve ya solo la salida nueva. `show access-lists` enseña los aciertos de cada regla (`4 match(es)` en el `deny`).
- **Fallo real de `pt_routed_plan`:** al construir una segunda red en el mismo archivo, los nombres por último octeto (`10`, `11`, `74`, `75`)
  ya existían. `pt_build_topology` no lo comprobaba: los equipos no se crearon y los pasos de cable y DHCP apuntaron a los equipos antiguos
  (sin daño: ya estaban por DHCP). Arreglo: la construcción **comprueba todos los nombres contra el archivo antes de crear nada** y aborta;
  `routed_plan` admite `host_names: "site"` (`Madrid-74`). El nombre por octeto solo es único dentro de una misma /24.
- `pt_routed_plan` con `build: true` validado en PT real (2 sedes, RIP v2, `/24` por sede, nombres `Norte-10`…): 23 de 25 pasos bien; rutas RIP,
  ping entre sedes y `startup-config` guardada. Los 2 fallos fueron de espera: **el primer cliente DHCP tras crear los cables tarda más de 25 s**
  (el puerto del switch aún no reenvía), siguió pidiendo y el siguiente se llevó su IP. Ahora se esperan 75 s y, si falla, se le desactiva el DHCP.
  Para deshacer un cruce: `ipconfig /release` en los dos, DHCP apagado en el segundo, renovar el primero, y luego el segundo.

## 2026-10-03 (noche): la red RIP unida al resto (redistribución RIP↔OSPF) y el modo Simulación (no son reglas)
- **Reto 5:** `R-Firewall` recibió un tercer puerto (`pt_add_module`, `Fa2/0 = 10.0.1.3`) hacia `SW-Rip`. En él: `router rip` (v2, `network 10.0.0.0`,
  `no auto-summary`, `passive-interface FastEthernet1/0`, **`redistribute ospf 1 metric 2`**) y `router ospf 1` con **`redistribute rip subnets`**.
  La 6.0.1 acepta los dos `redistribute`. Verificado: `Sur-11` (RIP) → servidor HTTP de la granja (OSPF), `PC0` (red antigua) → `Sur-10`,
  `140` (Cádiz) → `Norte-10`, y web desde `Norte-10` con `pt_http_get`. `network 10.0.0.0` es con clase: cubre también el núcleo OSPF, de ahí el `passive-interface`.
- **Modo Simulación = tiempo parado.** A mitad de la prueba PT estaba en Simulación (lo cambió el usuario): el ping se queda en «Pinging…» sin
  ninguna línea, los puertos de switch siguen en ámbar y no llegan rutas. `appWindow.isRealtimeMode()` lo detecta y
  `appWindow.getRSSwitch().showRealtimeMode()` lo devuelve a Tiempo real (comprobado). `pt_status` ahora avisa y hay herramienta `pt_realtime`.
  `getRSSwitch()` tiene también `showSimulationMode` (sin probar).
- Añadir un módulo a un router lo reinicia: tarda ~1–2 min en rehacer OSPF y RIP (actualizaciones cada 30 s). No dar nada por roto antes.
- 36 herramientas, 73 pruebas.
