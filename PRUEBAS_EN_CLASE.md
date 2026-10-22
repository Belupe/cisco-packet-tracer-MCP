# PRUEBAS_EN_CLASE.md — Qué hay que mejorar y probar en Packet Tracer 6.0.1

> **Estado: plan de pruebas.** Nada de lo que aparece aquí como «falta» está implementado, y nada de lo que hay que
> «sondear» está comprobado en una 6.0.1. Este archivo dice **qué falta, qué probar y cómo saber que ha salido bien**.
> Se ha escrito leyendo el código de `pt601_mcp/` y el del proyecto de referencia
> ([Mats2208/MCP-Packet-Tracer](https://github.com/Mats2208/MCP-Packet-Tracer), pensado para PT 8.2/9.0).

**Para qué sirve.** Completar las herramientas para que el MCP sepa **interpretar tu forma de trabajo**, tanto en la **práctica**
(Packet Tracer) como en la **documentación**. Prioridades: **1)** interfaces y puertos, **2)** capturas automáticas de las ventanas que
hagan falta, **3)** servicios de servidor. De momento se trabaja con las **interfaces gráficas** de los equipos; la terminal (pestaña CLI) queda en **segundo plano**.
Lo que no se necesite ahora (como AAA) queda marcado como no prioritario.

Tres bloques y un apéndice para explorar:
1. [Herramientas de puertos más completas](#1-herramientas-de-puertos)
2. [Capturas de ventanas de Windows](#2-capturas-de-pantalla-en-windows-ui_open-capture-close)
3. [Cubrir todos los servicios de servidor](#3-todos-los-servicios-de-servidor)

Al final: [orden de pruebas para clase](#4-orden-sugerido-en-clase), [registro de resultados](#5-registro-de-resultados) y un
[apéndice para explorar](#apéndice-para-explorar-sin-compromiso-el-sobrecillo) (sin compromiso).

---

## 0. Reglas para probar (para el usuario y para el asistente)
1. **Usa un archivo de pruebas** (*File → New*), nunca la práctica que vayas a entregar. Estas pruebas crean, mueven y cambian cosas.
2. **Cierra la ventana Debug** del Script Module. Con Debug abierta, una llamada IPC con argumentos erróneos cuelga el motor
   (hay que hacer Stop/Start). Con Debug cerrada, el error vuelve como texto.
3. **Una prueba por llamada**, y primero las de solo lectura. En las de escritura: **lee el valor antes, cámbialo, lee después y restáuralo**.
4. **No adivines la API** (regla 1 de `CLAUDE.md`): lo que no aparezca en `pt_describe`/`for..in` no se llama.
5. **Todo hallazgo** se apunta en `NOTAS.md`; todo arreglo lleva su prueba en `tests/`.
6. El JavaScript que va a PT es Qt Script (ES3): sin `let`, `const`, flechas ni `JSON`. Las líneas de este archivo ya cumplen eso.
7. Cómo lanzar los sondeos con el MCP: `pt_eval` con el código tal cual; `pt_describe` con `device` y `process` o `port`.

---

## 1. Herramientas de puertos

### 1.1 Qué tenemos hoy (leído del código)
| Herramienta nuestra | Qué hace exactamente |
|---|---|
| `pt_list_ports` | Por puerto: **nombre, libre o conectado, `isPortUp`**. Nada más |
| `pt_connect` | Elige puertos libres solos (ignora Console, Aux, Serial, Wireless, Vlan, Loopback, USB, Modem, Async, Rs232, Coaxial, Cellular; prefiere FastEthernet y luego Gigabit). Cables 8100 recto, 8101 cruzado, 8107 auto y 8103 fibra; si el auto falla, reintenta recto/cruzado. Avisa de la distancia física |
| `pt_add_link` / `pt_remove_link` | Cable entre puertos explícitos / quitar el cable de un puerto (`deleteLink`) |
| `pt_add_module` / `pt_remove_module` | Un módulo por llamada, solo en `Switch-PT-Empty` y `Router-PT-Empty` (apaga, añade, enciende, `skipBoot`) |
| `pt_set_ip` | En un puerto: IP, máscara, gateway (puerto y dispositivo), DHCP, DNS |
| `pt_snapshot` | Por puerto con IP o cable: nombre, IP, máscara, DHCP, tipo de cable y vecino |
| `pt_add_device` con `ports` | Puebla un `Switch-PT-Empty` con 1–10 puertos FastEthernet |

### 1.2 Lo que tiene el proyecto de referencia y nosotros no
| Herramienta suya | Qué hace (según su código y descripción) | ¿Qué le hace falta a la 6.0.1? |
|---|---|---|
| **`pt_inspect_ports`** (`device`, `only_linked`) | Estado real de cada puerto: línea y protocolo (`isPortUp`, `isProtocolUp`), MAC (`getMacAddress`), IP y máscara, dúplex (`isFullDuplex`), ancho de banda (`getBandwidth`), MTU (`getMtu`), delay (`getDelay`), descripción (`getDescription`), CDP (`isCdpEnable`), cliente DHCP (`isDhcpClientOn`), modo NAT y ACL aplicadas. **Marca anomalías**: cable conectado con el puerto caído, línea arriba con protocolo caído | Todos esos métodos **aparecen en la lista de 108 métodos de puerto del sondeo 1** (de un `Router-PT-Empty`): muy probable que sirvan. Falta comprobar sus valores y en switches/PCs |
| **`pt_set_port`** (`device`, `interface`, valores centinela) | Cambia atributos sin entrar en `configure terminal`: `bandwidth` (kbps), `bandwidth_auto`, `full_duplex`, `duplex_auto`, `description`, `mac_address`, `power`, `zone_member`, `proxy_arp`, `ike`. Solo aplica lo que se pasa y dice qué se aplicó | Existen en 6.0.1: `setBandwidth`, `setBandwidthAutoNegotiate`, `setFullDuplex`, `setDuplexAutoNegotiate`, `setDescription`, `setMacAddress`, `setPower`, `setZoneMemberName`, `setProxyArpEnabled`. **`ike` no tiene método** en la lista de la 6.0.1 (descartarlo) |
| **`pt_apply_interface_tuning`** (`router`, `interface`) | Vía CLI: `clock_rate` (solo serial, extremo DCE), `bandwidth`, `ospf_cost`, `ospf_priority`, `ospf_hello_interval`, `ospf_dead_interval`, `ospf_auth_key`, `ospf_md5_key_id` + `ospf_md5_key`, `delay`; con `dry_run` | Son comandos IOS: no depende de la API. Hay que comprobar los comandos en el IOS de la 6.0.1 |
| **`pt_apply_port_security`** (`switch`, `port`) | Vía CLI: `max_mac`, `violation` (`shutdown`, `restrict`, `protect`), `sticky`, `static_macs`; con `dry_run` | Comandos IOS del switch 2960: comprobar sintaxis en la 6.0.1 |
| **`pt_read_device_panel`** (`device`) | De una vez, lo que muestran las pestañas: modelo, encendido, si es host, DHCP, **por puerto: IP, máscara, MAC, estado, IPv6, firewall, ancho de banda**; en servidores, qué servicios están encendidos | La parte de puertos es lo mismo que `pt_inspect_ports`; la de servicios ya la cubre `pt_snapshot` |
| **`pt_list_modules`** | Lista los módulos del catálogo de PT (nombres exactos) | Nosotros solo conocemos `PT-SWITCH-NM-1CFE` y los de `catalog.MODULES`: hay que sacar la lista real de la 6.0.1 |
| **`pt_install_modules_batch`** | Instala N módulos en varios equipos en una sola llamada (apagar → `addModule` × N → encender) | Nuestro `pt_add_module` hace uno por llamada |
| `pt_delete_link` | Quitar el cable de un puerto | **Ya lo tenemos** como `pt_remove_link` |

### 1.3 Extras de la 6.0.1 que el proyecto de referencia **no** usa (opcionales, ya aparecen en el sondeo 1)
`getLightStatus` (color de la luz del enlace), `getRemotePortName` (puerto del otro extremo), `getBia`, `getClockRate`, `getType`,
`getPower`, `getIpv6Addresses`/`isIpv6Enabled`, `getOspfCost/Priority/HelloInterval/DeadInterval/AuthType`, `isRipPassive`, `isRipSplitHorizon`,
`isProxyArpEnabled`, `getZoneMemberName`, `getAclInID`/`getAclOutID`.
Setters: `setMtu`, `setIpMtu`, `setDelay`, `setClockRate`, `setCdpEnable`, `setNatMode`, `setAclInID/OutID`, `setOspf*`, `setRipPassive`, `setRipSplitHorizon`, `setIpv6*`.
Sirven para una `pt_inspect_ports` más rica que la de referencia (p. ej. mostrar la luz del enlace y el puerto remoto).

### 1.4 Qué hacer (propuesta)
1. **Nueva `pt_inspect_ports`** (`device`, `only_linked`, `detalle`): tabla por puerto con estado, protocolo, MAC, IP/máscara, dúplex, ancho de banda, MTU, delay, descripción, CDP, DHCP, NAT, ACL, luz y puerto remoto, **y avisos** (cable con puerto caído; línea arriba y protocolo caído). Ampliar `pt_list_ports` con un parámetro `detalle` también valdría.
2. **Nueva `pt_set_port`** con valores centinela (como la de referencia), sin `ike`, y que diga qué se aplicó.
3. **`pt_apply_interface_tuning` y `pt_apply_port_security`** generando IOS desde `ios.py` (con `dry_run`).
4. **`pt_list_modules`** con el catálogo real de la 6.0.1, y **`pt_add_module` que acepte varios módulos** (o `pt_install_modules_batch`).

### 1.5 Pruebas en clase (solo lectura primero)
**P1.1 — ¿los métodos de puerto existen en un switch, un PC y un servidor, no solo en un router?** Con `pt_describe` (`device`, `port`) en un puerto de cada tipo y compara las listas.

**P1.2 — Leer todos los datos de un puerto conectado** (cambia `R1` y el puerto por uno con cable). `pt_eval`:
```js
(function () { var p = ipc.network().getDevice("R1").getPort("GigabitEthernet0/0"); var o = []; var g = ["getName","getMacAddress","getIpAddress","getSubnetMask","getBandwidth","getMtu","getDelay","getDescription","getClockRate","getNatMode","getAclInID","getAclOutID","getLightStatus","getRemotePortName","getBia","getType","getPower"]; var i; for (i = 0; i < g.length; i++) { var v; try { v = (typeof p[g[i]] == "function") ? p[g[i]]() : "(no existe)"; } catch (e) { v = "ERROR " + e; } o.push(g[i] + "=" + v); } var b = ["isPortUp","isProtocolUp","isFullDuplex","isDuplexAutoNegotiate","isBandwidthAutoNegotiate","isCdpEnable","isDhcpClientOn","isProxyArpEnabled"]; var j; for (j = 0; j < b.length; j++) { var w; try { w = (typeof p[b[j]] == "function") ? p[b[j]]() : "(no existe)"; } catch (e2) { w = "ERROR " + e2; } o.push(b[j] + "=" + w); } return o.join("\n"); })()
```
Repite en un puerto **sin cable** y compara (¿qué devuelve `getLightStatus` con y sin cable? ¿y `isPortUp`?). Apunta los valores reales: sirven para interpretar los avisos de `pt_inspect_ports`.

**P1.3 — Escrituras reversibles, una por una.** Plantilla con la descripción (lee antes, cambia, lee después, restaura):
```js
(function () { var p = ipc.network().getDevice("R1").getPort("GigabitEthernet0/0"); var antes = p.getDescription(); p.setDescription("PRUEBA-MCP"); var despues = p.getDescription(); p.setDescription(antes); return "antes=[" + antes + "] despues=[" + despues + "] restaurado=[" + p.getDescription() + "]"; })()
```
Repite el patrón (cambiando getter y setter) con: `setFullDuplex(true/false)` + `isFullDuplex`, `setDuplexAutoNegotiate`, `setBandwidth(100000)` + `getBandwidth`, `setBandwidthAutoNegotiate`, `setMtu`, `setDelay`, `setCdpEnable`, `setProxyArpEnabled`, `setMacAddress` (anota el formato que acepta) y `setPower(false)` + `setPower(true)` (**tira el enlace un momento**; restáuralo siempre).
Anota para cada una: ¿se acepta?, ¿el valor cambia en el getter?, ¿**se ve en la ventana gráfica del equipo** (pestaña Config → interfaz)?

**P1.4 — IOS de las herramientas por CLI** (en un router y un switch de pruebas, con `pt_cli`): `bandwidth 100000`, `delay 10`, `ip ospf cost 5`, `ip ospf hello-interval 5`, `ip ospf priority 10` en un router; `switchport port-security`, `switchport port-security maximum 2`, `switchport port-security violation restrict`, `switchport port-security mac-address sticky` en un puerto de acceso del switch. Apunta cuáles acepta el IOS de la 6.0.1 y cuáles dan `% Invalid input`.

**P1.5 — Catálogo de módulos reales.** Sondear qué módulos acepta un `Router-PT-Empty` y un `Switch-PT-Empty` (nombres y tipos). La vía que ya funcionó: registrar el evento `moduleAdded` y añadir módulos a mano en la pestaña *Physical*:
```js
(function () { var d = ipc.network().getDevice("R1"); d.registerEvent("moduleAdded", null, function (src, args) { dprint("MODULO tipo=" + args.type + " modelo=" + args.model); }); return "escuchando"; })()
```
(Para ver `dprint` hace falta la ventana Debug; ciérrala después. Es la única prueba de este archivo que la necesita.)

**P1.6 — Campos de la ventana sin método conocido (*Tx Ring Limit*, *VLAN Switch Mode*).** Con `pt_describe` (`device` = un switch, `port` = `FastEthernet0/1`) y con
`pt_describe` (`device` = el switch, `process` = `VlanManager`: el proyecto de referencia lo usa en PT 9; en la 6.0.1 puede no existir o llamarse distinto, y si `getProcess`
da `null` se anota). Busca nombres con `Vlan`, `Trunk`, `TxRing` o `Mode`. Si no hay nada, esos campos se configuran por IOS (`pt_switch_config`) y se **anota como límite**.

### 1.6 Criterio de aceptación
- `pt_inspect_ports` en una red real (la del último trabajo) devuelve sin errores todos los campos de P1.2 para router, switch y PC, y **detecta** un cable con el puerto apagado (`setPower(false)`).
- Cada setter de `pt_set_port` cambia el valor y se refleja en la ventana gráfica; los que no funcionen se **quitan** de la herramienta (no se dejan fingiendo que funcionan).
- IOS de tuning y port-security verificado con `show` (`show port-security interface …`, `show ip ospf interface …`).

### 1.7 Los campos de la interfaz gráfica de un puerto (lo que el MCP debe poder controlar)
Es lo que la ayuda de la 6.0.1 dice que se ve y se cambia en la ventana de una interfaz (pestaña *Config* → INTERFACE → el puerto), y el método de la API que se
conoce para cada campo (de la lista de 108 métodos de puerto del sondeo 1, tomada de un puerto de router). **Todo «por probar» está sin comprobar** (P1.2, P1.3, P1.6).

| Campo en la ventana | En qué equipos (según la ayuda) | Método conocido en la API | Estado |
|---|---|---|---|
| **Port Status** (encendido o apagado) | Router, switch, PC, servidor | `setPower` / `getPower`, `isPortUp` | por probar |
| **IP Address** y **Subnet Mask** | Router, PC, servidor (el switch no tiene IP en la interfaz) | `setIpSubnetMask` / `getIpAddress`, `getSubnetMask` | ✔ ya se usa (`pt_set_ip`) |
| **MAC Address** | Router (Ethernet), PC, servidor | `setMacAddress` / `getMacAddress` | por probar |
| **Bandwidth** (y su modo automático) | Router (Ethernet), switch, PC, servidor | `setBandwidth`, `setBandwidthAutoNegotiate` / `getBandwidth`, `isBandwidthAutoNegotiate` | por probar |
| **Duplex** (y su modo automático) | Router (Ethernet), switch, PC, servidor | `setFullDuplex`, `setDuplexAutoNegotiate` / `isFullDuplex`, `isDuplexAutoNegotiate` | por probar |
| **Clock Rate** | Router (interfaz serie) | `setClockRate` / `getClockRate` | por probar |
| **Tx Ring Limit** | Router, switch | **ninguno en esa lista** | investigar (P1.6) |
| **VLAN Switch Mode** (acceso o troncal), **VLAN** del puerto y VLANs del troncal | Switch | **ninguno de puerto en esa lista** (por IOS sí: `pt_switch_config`) | investigar (P1.6) |
| **Link Local Address** y **IPv6 Address** | PC, portátil, servidor | `setIpv6LinkLocal`, `addIpv6Address`, `setIpv6AddressAutoConfig`, `setIpv6Enabled` / `getIpv6Address(es)`, `getIpv6LinkLocal` | por probar |
| **SSID** (interfaz inalámbrica) | PC, portátil, tablet, PDA | `setSsid` / `getSsid` del módulo inalámbrico (ya descubierto, ver `NOTAS.md`) | ver `NOTAS.md` |

**Consecuencia:** `pt_set_port` y `pt_inspect_ports` deben cubrir **estos campos** (los de la ventana), no solo los que el proyecto de referencia eligió. Y cada campo se da por bueno
cuando, al cambiarlo por la API, **se ve cambiado en la ventana gráfica** (P1.3).

---

## 2. Capturas de pantalla en Windows (`ui_open`, `capture`, `close`…)

### 2.1 Qué se quiere
Que el MCP **haga automáticamente una captura de la ventana que haga falta** (el mapa, o la ventana de configuración de un equipo),
sin que tengas que ir abriéndola y recortándola a mano. Son capturas **de la interfaz gráfica** de Packet Tracer (como las que se
sacan en clase con la Herramienta Recortes); el texto de la terminal **no** vale como evidencia.

**Para poder capturar una ventana hay que poder abrirla.** Por eso este bloque necesita herramientas que **abran la interfaz de cada
equipo** y la dejen en la pestaña correcta antes de capturarla. El flujo completo es:

1. **Abrir** la ventana del equipo (`ui_open`).
2. **Elegir** la pestaña o sección que se necesita (Config, Desktop, Services…).
3. **Capturar** esa ventana (`ui_capture`).
4. **Cerrarla** (`ui_close`), para no dejar ventanas abiertas.

Ejemplos de qué ventana abrir para cada evidencia (las pestañas salen de la ayuda local; **qué captura pide cada práctica hay que confirmarlo con lo que exijan en clase**):
| Equipo | Ventana que hay que abrir | Qué se ve |
|---|---|---|
| Router | *Config* → una interfaz (p. ej. FastEthernet0/0), *Config* → Global (Settings) o Routing (Static, RIP) | Estado del puerto, IP y máscara, nombre. En la parte de abajo, PT enseña los **comandos IOS equivalentes** |
| Switch | *Config* → Global, Switching (base de VLAN) o una interfaz | VLAN, puertos, nombre |
| PC o portátil | *Desktop* → IP Configuration (y *Config* → Global/Interfaz) | IP, máscara, gateway, DNS |
| Servidor | *Config* → SERVICES → DHCP, DNS, HTTP, FTP, EMAIL… y *Config* → INTERFACE | Configuración de cada servicio (en la 6.0.1 los servicios cuelgan de *Config*, según la ayuda) |
| Mapa | Espacio de trabajo lógico | La topología completa (`pt_screenshot`) |

### 2.2 Qué tiene el proyecto de referencia (no lo tenemos)
| Herramienta suya | Qué hace |
|---|---|
| `pt_screenshot` (`filename`, `fmt`, `output_dir`) | Captura el **mapa** con `getWorkspaceImage`. PT devuelve los bytes como **texto de decimales con signo separados por comas** (un PNG empieza por `-119,80,78,71,13,10,26,10`); hay que convertirlos a sin signo y comprobar la firma del formato |
| `pt_ui_open` (`device`, `tab`, `app`, `section`, `scroll_to_end`) | Abre la ventana de un equipo **sin mover el ratón ni teclear**, en una pestaña (*Physical, Config, CLI, Desktop, Services, Programming, Attributes*), aplicación de escritorio (*ip_configuration, command_prompt, web_browser, email, firewall, vpn…*) o sección (*Settings*, una interfaz, *DHCP, DNS, HTTP, EMAIL, FTP…*) |
| `pt_ui_capture` (`device`) | Guarda un **PNG de la ventana** del equipo (o de la principal), **aunque esté tapada** (`PrintWindow` con `PW_RENDERFULLCONTENT`). Devuelve la ruta del archivo, no la imagen |
| `pt_ui_close` (`device`) | Cierra la ventana de un equipo, o todas |
| `pt_ui_mode` | `headless` (todo por API) o `ui` (además enseña lo que hace en las ventanas) |

**Prioridad en esta fase:** alta para `pt_ui_open`, `pt_ui_capture`, `pt_ui_close`, `pt_read_device_panel`, `pt_screenshot` y `pt_ui_mode`; **segundo plano** para la terminal (pestaña CLI y `pt_terminal`) y el Command Prompt, que de momento se usan poco.

**Ojo con los nombres de las pestañas:** los de su `pt_ui_open` son de PT 8/9 (*Services*, *Attributes*, *Programming*). La ayuda de la 6.0.1 solo habla de *Config*, *CLI* y *Desktop* (y `NOTAS.md` de *Physical*, que se usó con éxito), y **sitúa los servicios dentro de *Config → SERVICES***. Hay que comprobarlo en el PT real (ver 2.6).

Cómo abren las ventanas (según su `presenter.py`, verificado por ellos en **PT 9.0.1**):
1. Si el diálogo ya existe (aunque esté oculto): `ipc.appWindow().getDialogManager().getDialog(nombre).setVisible(true)`.
2. Si no existe, PT no ofrece llamada: **envían un clic** (`PostMessage`, sin mover el cursor real) al icono del equipo en el lienzo.
   **Peligro:** con la herramienta *Delete* activa ese clic **borraría el equipo**; hay que dejar activa *Select* antes.
3. Pestañas, secciones y aplicaciones de escritorio se eligen con **UI Automation** (necesita el extra `[ui]`, o sea `comtypes`).
4. La captura es `PrintWindow`, con un codificador PNG propio (sin Pillow).

### 2.3 Qué sabemos de la 6.0.1 (sondeos y árbol de instalación)
- `ipc.appWindow()` expone `getDialogManager`, `getActiveDialog`, `getPhysicalLocationDialog`, `getAdminDialog`, `getInfoDialog`, `getPaletteDialog`, `getCommonToolbar`…
  y `LogicalWorkspace` expone **`getWorkspaceImage`**. **Ninguno está probado** en nuestro PT.
- PT 6.0.1 usa **Qt 4** (`QtGui4.dll`) y la instalación trae `bin\accessible`: parece que incluye el soporte de accesibilidad de Qt,
  que es lo que UI Automation necesita para ver pestañas y botones. Hay que comprobarlo.
- **Restricción nuestra:** solo biblioteca estándar (sin `comtypes`). Alternativas que **no instalan nada**: `ctypes` para Win32 y
  PowerShell con `System.Windows.Automation` (viene con Windows).

### 2.4 Qué hacer (propuesta)
1. **`pt_screenshot`** del mapa con `getWorkspaceImage` (si P2.1 funciona; no depende de Windows).
2. **`pt_ui_capture`** con `ctypes` + `PrintWindow` (sin dependencias).
3. **`pt_ui_open` / `pt_ui_close`**: primero por `DialogManager` si funciona (P2.3); para pestañas y secciones, UI Automation vía PowerShell (P2.4).
   El clic sobre el icono **solo** como último recurso, con *Select* activa y avisando al usuario.
4. **Herramienta Recortes de Windows.** No se puede automatizar del todo (`ms-screenclip:` y `Win+Mayús+S` piden que elijas el recuadro a mano).
   Propuesta: `PrintWindow` como equivalente automático (la imagen resultante es la misma ventana) y un **modo guiado** de respaldo: el asistente abre la ventana en la pestaña
   correcta y te dice «pulsa Win+Mayús+S y recorta», y tú lo haces. **Decisión pendiente (¿vale el PNG automático para la clase?)**.

### 2.5 Pruebas en clase
**P2.1 — ¿`getWorkspaceImage` devuelve la imagen y en qué formato?** `pt_eval`:
```js
(function () { var lw = ipc.appWindow().getActiveWorkspace().getLogicalWorkspace(); var b = lw.getWorkspaceImage("PNG"); var s = String(b); return "tipo=" + typeof b + " largo_texto=" + s.length + " inicio=" + s.substring(0, 40); })()
```
Esperado si funciona como en 9.0: empieza por `-119,80,78,71,13,10,26,10` y el texto mide decenas de miles de caracteres. Si falla o va vacío, anótalo.
Si funciona, la imagen en texto ocupa cientos de KB: **no se puede devolver en la respuesta del MCP** (se recorta a 6000 caracteres); hay que decodificarla, guardarla en un archivo y devolver solo la ruta. Comprobar también que cabe en el límite de 1 MB del puente (con un mapa grande puede no caber).

**P2.2 — ¿`PrintWindow` captura la ventana de PT 6.0.1 (Qt 4) sin dejarla en negro?** PowerShell, con PT abierto
(**no probado por mí en Windows**; si da error, copia el mensaje):
```powershell
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System; using System.Runtime.InteropServices; using System.Drawing; using System.Drawing.Imaging;
public static class Cap {
  [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  public static string Save(IntPtr h, string path) {
    RECT r; if (!GetWindowRect(h, out r)) return "sin ventana";
    int w = r.R - r.L, hh = r.B - r.T; if (w <= 0 || hh <= 0) return "tamano 0";
    using (Bitmap bmp = new Bitmap(w, hh)) {
      using (Graphics g = Graphics.FromImage(bmp)) { IntPtr dc = g.GetHdc(); bool ok = PrintWindow(h, dc, 2); g.ReleaseHdc(dc); if (!ok) return "PrintWindow fallo"; }
      bmp.Save(path, ImageFormat.Png); return "ok " + w + "x" + hh;
    }
  }
}
'@
$p = Get-Process | Where-Object { $_.ProcessName -like "PacketTracer*" -and $_.MainWindowHandle -ne 0 } | Select-Object -First 1
[Cap]::Save($p.MainWindowHandle, "$env:USERPROFILE\pt_captura_test.png")
```
Abre `pt_captura_test.png`: ¿se ve el mapa o sale negro/recortado? Repite con la ventana **tapada por otra** y con la escala de pantalla al 100 % y al 125 %.

**P2.3 — ¿`DialogManager` sirve en la 6.0.1?** `pt_eval` (solo lectura primero):
```js
(function () { var dm = ipc.appWindow().getDialogManager(); var k = []; var m; for (m in dm) { k.push(m); } k.sort(); return k.join(", "); })()
```
Si lista `getDialog`, prueba con un equipo que **tenga su ventana ya abierta una vez**:
```js
(function () { var dm = ipc.appWindow().getDialogManager(); var dlg = null; try { dlg = dm.getDialog("R1"); } catch (e) { return "ERROR " + e; } if (!dlg) { return "sin dialogo"; } var k = []; var m; for (m in dlg) { k.push(m); } k.sort(); return k.join(", "); })()
```
y, si aparece `setVisible`, llámalo con `true` y mira si la ventana sale.

**P2.4 — ¿UI Automation ve las pestañas de la ventana de un equipo?** Con la ventana de un router abierta (PowerShell, no probado):
```powershell
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$p = Get-Process | Where-Object { $_.ProcessName -like "PacketTracer*" -and $_.MainWindowHandle -ne 0 } | Select-Object -First 1
$root = [System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$all | Select-Object -First 80 | ForEach-Object { $_.Current.ControlType.ProgrammaticName + " | " + $_.Current.Name }
```
Si salen elementos con nombres como *Config*, *CLI*, *Physical*, UI Automation sirve; si sale casi vacío, hará falta otro camino (clics con coordenadas, más frágil).

### 2.6 Criterio de aceptación
- Se anotan **los nombres reales de las pestañas** que ve UI Automation (¿existe *Services* como pestaña propia en un servidor, o cuelga de *Config → SERVICES*?).
- `pt_screenshot`: PNG válido del mapa (la firma se comprueba), no vacío, nombre sano y ruta devuelta.
- `pt_ui_open` + `pt_ui_capture`: PNG **no negro** de (a) *Config* de un router, (b) *Config → SERVICES → DHCP/DNS/HTTP* de un servidor, (c) *Desktop → IP Configuration* de un PC, con la pestaña correcta.
- Sin mover el ratón del usuario (o avisando si hay que hacerlo) y **sin borrar nada por un clic** (comprobar siempre que *Select* está activa).
- Si la ventana está tapada, la captura sigue saliendo bien (o se avisa).

### 2.7 Riesgos
Escalado de pantalla (DPI) que descuadra la captura; ventanas de Qt 4 que `PrintWindow` pinta en negro; UI Automation que no ve los controles de Qt 4;
el clic sobre el icono con la herramienta equivocada; cada llamada «de ventana» puede dejar ventanas abiertas (cerrarlas siempre al terminar).

### 2.8 Mapa de interfaces: qué ventana abrir para cada tarea (6.0.1, según la ayuda local)
Esto es lo que el MCP tiene que saber para **elegir la ventana correcta** antes de capturarla o de usarla. Los nombres salen de `config_routers.htm`, `config_switches.htm`,
`config_PCs.htm`, `config_servers.htm` y `config_others.htm`; **hay que comprobarlos en el PT real** (2.6).

| Tarea | Equipo | Dónde, en la ventana del equipo | Qué hay ahí |
|---|---|---|---|
| Estado, IP, MAC, ancho de banda y dúplex de un puerto | Router | *Config* → INTERFACE → el puerto | Port Status, IP, máscara, Tx Ring Limit; Ethernet: MAC, Bandwidth, Duplex; serie: Clock Rate |
| Puerto de un switch, VLAN y modo troncal | Switch | *Config* → INTERFACE → el puerto | Port Status, Bandwidth, Duplex, VLAN Switch Mode, VLAN o VLANs del troncal, Tx Ring Limit |
| Crear o borrar VLAN | Switch (y routers 1841 y 2811) | *Config* → SWITCHING → VLAN Database | Nombre y número, botones Add y Remove |
| Nombre del equipo y archivos de configuración | Router, switch | *Config* → GLOBAL → Settings | Display name y hostname; borrar NVRAM, guardar, exportar, cargar y fusionar configuración |
| Rutas estáticas o RIP | Router | *Config* → ROUTING → Static o RIP | Redes y siguientes saltos |
| IP, máscara, gateway y DNS (DHCP o estática) | PC, portátil | *Desktop* → IP Configuration (y *Config* → GLOBAL e INTERFACE) | DHCP o Static, IPv4 e IPv6 |
| Servicios | Servidor | *Config* → SERVICES → HTTP, DHCP, TFTP, DNS, SYSLOG, AAA, NTP, EMAIL, FTP | Configuración de cada servicio |
| Interfaz de un servidor (hasta 2) | Servidor | *Config* → INTERFACE | Port Status, Bandwidth, Duplex, MAC, IP, máscara, link local, IPv6 |
| Pruebas de conectividad, web y correo | PC, portátil, servidor | *Desktop* → Command Prompt, Web Browser, Email, Traffic Generator… | — |
| Módulos, apagar y encender | Todos | *Physical* | Añadir o quitar módulos, botón de encendido |
| Bridge, repetidor, nube y otros | — | *Config* → GLOBAL e INTERFACE (muy simples) | Bridge: Port Status, Bandwidth, Duplex; repetidor: sin ajustes |

Aplicaciones del *Desktop* de un PC según la ayuda: IP Configuration, Dial-up, Terminal, Command Prompt, Web Browser, PC Wireless, VPN, Traffic Generator,
MIB Browser, PPPoE Dialer, Text Editor, Email y Cisco IP Communicator. De momento solo importan **IP Configuration** y, más adelante, Web Browser y Email.
Todas las ventanas de router y switch tienen abajo la lista de **comandos IOS equivalentes** a lo que se hace en la interfaz.

---

## 3. Todos los servicios de servidor

### 3.1 Qué trae un Server-PT en la 6.0.1
Según vuestra ayuda local (`documentación/config_servers.htm`), pestaña **Config**: ajustes globales, *Algorithm Settings*, y los servicios
**HTTP, DHCP, TFTP, DNS, SYSLOG, AAA, NTP, EMAIL, FTP** (en la instalación hay además una carpeta `saves\Server\HTTPS`), más las interfaces (hasta 2).
Pestaña **Desktop**: *IP Configuration, Command Prompt, Traffic Generator, Text Editor, Web Browser, PPPoE Dialer, VPN*.

### 3.2 Estado de cada servicio (lo que ya sabemos, de `NOTAS.md` y del código)
| Servicio | Proceso IPC descubierto | Lo que hace hoy el MCP | Lo que falta (exacto) |
|---|---|---|---|
| **DHCP** | `DhcpServer` | Encender/apagar. Pool por defecto `serverPool`: IP inicial y final, router y DNS (`pt_dhcp_server`). Lectura en `pt_snapshot` | **Varios pools** (`addPool`, `removePool`) y **direcciones excluidas** (`addExcludedAddress`): existen y no se usan. La máscara del pool **no** se puede cambiar (`setNetworkMask` da `Invalid arguments`) |
| **DNS** | `DnsServer` | Encender/apagar | Los registros **no se pueden crear por IPC** (conclusión firme en `NOTAS.md`: `addIpAddress` escribe en un almacén que nadie consulta; los reales viven en `<NAMESERVER-DATABASE>` de `serializeToXml`). Sí se puede **leer** ese XML: falta una herramienta de lectura de registros (A, CNAME, SOA, NS) y un flujo guiado para crearlos a mano |
| **HTTP / HTTPS** | `HttpServer`, `HttpsServer` | Encender/apagar. Lado cliente: `pt_http_get` | **Editar páginas** (`index.html`, `helloworld.html`, `image.html`…) y **usuario/contraseña** (`getPage`, `setUsername`, `setPassword` existen y no se usan) |
| **TFTP** | `TftpServer` | Encender/apagar | Listar y quitar imágenes IOS de la lista |
| **FTP** | `FtpServer` (`getFtpUserAccountManager`) | Encender/apagar | **Cuentas** (usuario, contraseña) y **permisos** (Write, Read, Delete, Rename, List); listar y quitar archivos |
| **SYSLOG** | `SyslogServer` | Encender/apagar | **Leer el registro** (hora, equipo, mensaje) |
| **AAA** *(no prioritario)* | `AcsServer` (`addToUserMap`, `addToClientMap`, `enableACSServerService`) | **Nada**: ni siquiera está en `pt_server_services` | Encender; **clientes** (nombre, IP, clave secreta, tipo Radius o Tacacs) y **usuarios** (usuario, contraseña) |
| **NTP** | `NtpServer` (`setEnabled`, `setKeyID`, `getKeyId`, `getServerMd5Str`) | Encender/apagar; validado con `ntp server <ip>` + `show ntp status` en el router | **Autenticación** (clave y contraseña) y fijar la fecha/hora a mano |
| **EMAIL** | `SmtpServer`, `Pop3Server`, `EmailServer` (`addUser`, `deleteUser`, `changePassword`) | Encender/apagar SMTP y POP3 | **Dominio** (botón *Set*) y **cuentas**; **cliente de correo** (`EmailClient`) para enviar y recibir |
| Ajustes globales | — | Gateway y DNS (`pt_set_ip`) | *Algorithm Settings* (máx. conexiones, sesiones abiertas, timeout): sin explorar |
| Interfaces (2) | puertos | IP y máscara | Estado, ancho de banda, dúplex, MAC, link-local, IPv6 (ver el bloque 1) |
| Desktop | `HttpClient`, `EmailClient`, `PppoeClient`, `IcmpProcess`… | IP Configuration (`pt_set_ip`), Command Prompt (`pt_cli` en un PC), Web Browser (`pt_http_get`) | Email, PPPoE Dialer, VPN, Text Editor, Traffic Generator, Firewall, y *Terminal* (consola de un router a través de un PC) |

El proyecto de referencia cubre `pt_server_dhcp`, `pt_server_dns`, `pt_server_http` (páginas), `pt_server_service` (tftp, ftp, syslog, email), `pt_email_client`,
`pt_host_firewall`, `pt_terminal` y `pt_web_browser`. Su API es la de PT 8/9: hay que reverificarlo todo en la 6.0.1.

### 3.3 Qué hacer (propuesta de herramientas)
`pt_dhcp_server` con **varios pools** y exclusiones; `pt_server_http` (páginas, usuario);
`pt_server_ftp` (cuentas y permisos); `pt_server_email` (dominio y cuentas); `pt_server_ntp` (autenticación, hora);
`pt_server_syslog` (leer registro); `pt_server_tftp` (listar y quitar); `pt_server_dns_read` (leer registros del XML) más el flujo guiado de alta manual;
`pt_email_client`, `pt_host_firewall` y `pt_terminal` en los equipos.

AAA (`AcsServer`) **no es prioritario** y queda fuera de este plan por ahora.

### 3.4 Pruebas en clase
**P3.1 — Métodos reales de cada servicio** (solo lectura). Con un `Server-PT` de pruebas, `pt_describe` con `process` = `DhcpServer`, `DnsServer`, `HttpServer`,
`HttpsServer`, `TftpServer`, `FtpServer`, `SmtpServer`, `Pop3Server`, `EmailServer`, `NtpServer`, `SyslogServer`, `AcsServer`.
Anota la lista de métodos de cada uno. Si algún proceso no existe, `getProcess` devuelve `null`.

**P3.2 — Por servicio: escribir, leer para verificar y comprobar desde un cliente.** Hazlo **de uno en uno** y anota en el registro (sección 5):
| Servicio | Escribir | Verificar leyendo | Comprobar desde un cliente |
|---|---|---|---|
| DHCP varios pools | `addPool`, `addExcludedAddress` (probar firmas una a una) | `getPoolCount`, `getPoolAt(n)` | Un PC de otra red recibe IP del pool correcto (`ipconfig`) |
| HTTP páginas | probar los setters que salgan en P3.1 | `getPage` | `pt_http_get` devuelve el texto nuevo |
| FTP cuentas | `getFtpUserAccountManager` → añadir usuario con permisos | leer cuentas | En un PC: `ftp <ip>` con usuario y clave |
| EMAIL | `EmailServer.addUser`; dominio | leer usuarios | `EmailClient` de un PC: configurar, enviar y recibir |
| AAA *(opcional)* | `addToClientMap`, `addToUserMap`, `enableACSServerService` | leer mapas | En un router: `aaa new-model` + servidor Radius/Tacacs y probar un acceso |
| NTP | clave (`setKeyID`) y hora | `getKeyId`, `getServerMd5Str` | `show ntp status` en el router |
| SYSLOG | — (solo lectura) | leer entradas | En un router: `logging host <ip>`, provocar un evento y mirar el registro |
| TFTP | listar y quitar imagen | lista | En un router: `copy running-config tftp` |
| DNS | (alta manual en *Config → SERVICES → DNS*) | leer `<NAMESERVER-DATABASE>` con `serializeToXml` | `nslookup <nombre>` en un PC y `pt_http_get` por nombre |

**P3.3 — Cada servicio se ve en la ventana gráfica.** Tras cada escritura, abre *Config → SERVICES* del servidor y comprueba que lo escrito aparece (es la prueba de que se escribió
en el almacén que usa la interfaz, el fallo que dio el DNS).

### 3.5 Criterio de aceptación
- Cada servicio de la tabla tiene: herramienta, **lectura de verificación** y comprobación desde un cliente documentada.
- Lo que no se pueda hacer por IPC (como los registros DNS) queda como **flujo guiado** con su comprobación y apuntado en `NOTAS.md` y `CLAUDE.md`.
- Se probó **encender y apagar** cada servicio (no solo encender) y que el estado se ve en la ventana.

---

## 4. Orden sugerido en clase
1. **Preparar (5 min):** archivo de pruebas, Debug cerrada, `pt_status` conectado, Tiempo real (`pt_realtime`).
2. **Solo lectura (15 min):** P1.1, P1.2, P1.6, P3.1, P2.1, P2.3. Con esto se sabe qué es posible antes de escribir una línea de código.
3. **Capturas (15 min):** P2.2 y P2.4. Decidir en ese momento si el PNG automático sirve para la clase (punto pendiente de 2.4).
4. **Escrituras reversibles (20 min):** P1.3 y P1.4; después P3.2 servicio por servicio (los más usados primero: HTTP, FTP, EMAIL).
5. **Si sobra tiempo:** el apéndice (E1), solo lectura.
6. **Cerrar:** rellenar la sección 5, pasar los hallazgos a `NOTAS.md` y actualizar «Lo primero que probablemente haya que reparar» en `CLAUDE.md`.

## 5. Registro de resultados
Copia esta tabla en `NOTAS.md` (o rellénala aquí) con la fecha de la prueba. Estados: ✔ funciona · ✘ falla · ➖ no existe en la 6.0.1.

| ID | Prueba | Estado | Valor o mensaje real | ¿Se ve en la ventana gráfica? | Notas |
|---|---|---|---|---|---|
| P1.1 | Métodos de puerto en switch, PC, servidor | | | — | |
| P1.2 | Leer datos de un puerto (con y sin cable) | | | — | |
| P1.3 | Escrituras reversibles de puerto (una fila por setter) | | | | |
| P1.4 | IOS de tuning y port-security | | | — | |
| P1.5 | Módulos reales de Router/Switch-PT-Empty | | | — | |
| P1.6 | Campos sin método conocido (Tx Ring Limit, VLAN Switch Mode) | | | | |
| P2.1 | `getWorkspaceImage` | | | — | |
| P2.2 | `PrintWindow` de la ventana principal | | | — | |
| P2.3 | `DialogManager` | | | | |
| P2.4 | UI Automation ve pestañas | | | — | |
| P3.1 | Métodos de cada servicio (12 procesos) | | | — | |
| P3.2 | Servicios: DHCP multipool / HTTP / FTP / EMAIL / NTP / SYSLOG / TFTP / DNS (AAA opcional) | | | | |
| E1 | *(opcional, apéndice)* Métodos de `getUserCreatedPDU` y compañía | | | — | |

---

## Apéndice. Para explorar (sin compromiso): el sobrecillo
> **No es una prioridad ni un requisito de este plan.** Se deja anotado para mirarlo si sobra tiempo; sin criterios de aceptación.

**La idea:** usar el sobre de la barra de herramientas (*Add Simple PDU*) para tener, en una captura, la lista de PDU con *Successful*
entre equipos, servidores y routers.

**Lo que ya se sabe**
- Ayuda de la 6.0.1: el PDU simple es un ping de una sola vez; la lista tiene las columnas *Fire*, *Last Status* (*Successful*, *Fail* o *In Progress*),
  *Source* y *Destination*; en Tiempo real el resultado sale al instante. Un escenario se reinicia si se escribe configuración global en un equipo.
- El proyecto de referencia **afirma que no se puede crear un PDU por API** (su documentación está escrita para PT 8/9). En la 6.0.1 existen
  `getUserCreatedPDU`, `getPDUListWindow` y `getSimulationPanel` en `ipc.appWindow()`, pero **no se ha mirado qué métodos tienen**.
- Hoy el MCP comprueba conectividad por la consola (`pt_ping`, `pt_ping_matrix`, `pt_traceroute`); nada usa el sobre.

**Exploración mínima (solo lectura).** `pt_eval`, una vez por objeto (`getUserCreatedPDU`, `getPDUListWindow`, `getSimulationPanel`):
```js
(function () { var o = ipc.appWindow().getUserCreatedPDU(); var k = []; var m; for (m in o) { k.push(m); } k.sort(); return k.join(", "); })()
```
Anota la lista de métodos en `NOTAS.md`: dirá si merece la pena seguir. Si algún día se sigue, habría tres caminos (API, manejar la interfaz, o un modo
guiado en el que el asistente lo prepara todo y tú pulsas el sobre), y la captura de la lista saldría de las herramientas del bloque 2.
