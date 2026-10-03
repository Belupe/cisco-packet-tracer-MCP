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
