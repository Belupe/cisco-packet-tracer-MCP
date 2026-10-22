# PRUEBAS_EN_CLASE.md — Qué hay que mejorar y probar en Packet Tracer 6.0.1

> **Estado: plan de pruebas.** Nada de lo que aparece aquí como «falta» está implementado, y nada de lo que hay que
> «sondear» está comprobado en una 6.0.1. Este archivo dice **qué falta, qué probar y cómo saber que ha salido bien**.
> Se ha escrito leyendo el código de `pt601_mcp/` y el del proyecto de referencia
> ([Mats2208/MCP-Packet-Tracer](https://github.com/Mats2208/MCP-Packet-Tracer), pensado para PT 8.2/9.0).

Cuatro bloques:
1. [Herramientas de puertos más completas](#1-herramientas-de-puertos)
2. [Capturas de ventanas de Windows](#2-capturas-de-pantalla-en-windows-ui_open-capture-close)
3. [Cubrir todos los servicios de servidor](#3-todos-los-servicios-de-servidor)
4. [Comprobación con el sobrecillo (PDU simple)](#4-comprobación-con-el-sobrecillo-add-simple-pdu)

Al final: [orden de pruebas para clase](#5-orden-sugerido-en-clase) y [registro de resultados](#6-registro-de-resultados).

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

### 1.6 Criterio de aceptación
- `pt_inspect_ports` en una red real (la del último trabajo) devuelve sin errores todos los campos de P1.2 para router, switch y PC, y **detecta** un cable con el puerto apagado (`setPower(false)`).
- Cada setter de `pt_set_port` cambia el valor y se refleja en la ventana gráfica; los que no funcionen se **quitan** de la herramienta (no se dejan fingiendo que funcionan).
- IOS de tuning y port-security verificado con `show` (`show port-security interface …`, `show ip ospf interface …`).

---

## 2. Capturas de pantalla en Windows (`ui_open`, `capture`, `close`…)

### 2.1 Qué se quiere
Capturas **de la interfaz gráfica** de Packet Tracer: el mapa y las ventanas de configuración de cada equipo (como las que se sacan en clase con la
Herramienta Recortes). El texto de la terminal **no** vale como evidencia.

### 2.2 Qué tiene el proyecto de referencia (no lo tenemos)
| Herramienta suya | Qué hace |
|---|---|
| `pt_screenshot` (`filename`, `fmt`, `output_dir`) | Captura el **mapa** con `getWorkspaceImage`. PT devuelve los bytes como **texto de decimales con signo separados por comas** (un PNG empieza por `-119,80,78,71,13,10,26,10`); hay que convertirlos a sin signo y comprobar la firma del formato |
| `pt_ui_open` (`device`, `tab`, `app`, `section`, `scroll_to_end`) | Abre la ventana de un equipo **sin mover el ratón ni teclear**, en una pestaña (*Physical, Config, CLI, Desktop, Services, Programming, Attributes*), aplicación de escritorio (*ip_configuration, command_prompt, web_browser, email, firewall, vpn…*) o sección (*Settings*, una interfaz, *DHCP, DNS, HTTP, EMAIL, FTP…*) |
| `pt_ui_capture` (`device`) | Guarda un **PNG de la ventana** del equipo (o de la principal), **aunque esté tapada** (`PrintWindow` con `PW_RENDERFULLCONTENT`). Devuelve la ruta del archivo, no la imagen |
| `pt_ui_close` (`device`) | Cierra la ventana de un equipo, o todas |
| `pt_ui_mode` | `headless` (todo por API) o `ui` (además enseña lo que hace en las ventanas) |

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
- `pt_screenshot`: PNG válido del mapa (la firma se comprueba), no vacío, nombre sano y ruta devuelta.
- `pt_ui_open` + `pt_ui_capture`: PNG **no negro** de (a) *Config* de un router, (b) *Services → DHCP/DNS/HTTP* de un servidor, (c) *Desktop → IP Configuration* de un PC, con la pestaña correcta.
- Sin mover el ratón del usuario (o avisando si hay que hacerlo) y **sin borrar nada por un clic** (comprobar siempre que *Select* está activa).
- Si la ventana está tapada, la captura sigue saliendo bien (o se avisa).

### 2.7 Riesgos
Escalado de pantalla (DPI) que descuadra la captura; ventanas de Qt 4 que `PrintWindow` pinta en negro; UI Automation que no ve los controles de Qt 4;
el clic sobre el icono con la herramienta equivocada; cada llamada «de ventana» puede dejar ventanas abiertas (cerrarlas siempre al terminar).

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
| **AAA** | `AcsServer` (`addToUserMap`, `addToClientMap`, `enableACSServerService`) | **Nada**: ni siquiera está en `pt_server_services` | Encender; **clientes** (nombre, IP, clave secreta, tipo Radius o Tacacs) y **usuarios** (usuario, contraseña) |
| **NTP** | `NtpServer` (`setEnabled`, `setKeyID`, `getKeyId`, `getServerMd5Str`) | Encender/apagar; validado con `ntp server <ip>` + `show ntp status` en el router | **Autenticación** (clave y contraseña) y fijar la fecha/hora a mano |
| **EMAIL** | `SmtpServer`, `Pop3Server`, `EmailServer` (`addUser`, `deleteUser`, `changePassword`) | Encender/apagar SMTP y POP3 | **Dominio** (botón *Set*) y **cuentas**; **cliente de correo** (`EmailClient`) para enviar y recibir |
| Ajustes globales | — | Gateway y DNS (`pt_set_ip`) | *Algorithm Settings* (máx. conexiones, sesiones abiertas, timeout): sin explorar |
| Interfaces (2) | puertos | IP y máscara | Estado, ancho de banda, dúplex, MAC, link-local, IPv6 (ver el bloque 1) |
| Desktop | `HttpClient`, `EmailClient`, `PppoeClient`, `IcmpProcess`… | IP Configuration (`pt_set_ip`), Command Prompt (`pt_cli` en un PC), Web Browser (`pt_http_get`) | Email, PPPoE Dialer, VPN, Text Editor, Traffic Generator, Firewall, y *Terminal* (consola de un router a través de un PC) |

El proyecto de referencia cubre `pt_server_dhcp`, `pt_server_dns`, `pt_server_http` (páginas), `pt_server_service` (tftp, ftp, syslog, email), `pt_email_client`,
`pt_host_firewall`, `pt_terminal` y `pt_web_browser`, pero **tampoco cubre AAA**, y su API es la de PT 8/9: hay que reverificarlo todo en la 6.0.1.

### 3.3 Qué hacer (propuesta de herramientas)
`pt_server_services` ampliada con `aaa`; `pt_dhcp_server` con **varios pools** y exclusiones; `pt_server_http` (páginas, usuario);
`pt_server_ftp` (cuentas y permisos); `pt_server_email` (dominio y cuentas); `pt_server_aaa` (clientes y usuarios); `pt_server_ntp` (autenticación, hora);
`pt_server_syslog` (leer registro); `pt_server_tftp` (listar y quitar); `pt_server_dns_read` (leer registros del XML) más el flujo guiado de alta manual;
`pt_email_client`, `pt_host_firewall` y `pt_terminal` en los equipos.

### 3.4 Pruebas en clase
**P3.1 — Métodos reales de cada servicio** (solo lectura). Con un `Server-PT` de pruebas, `pt_describe` con `process` = `DhcpServer`, `DnsServer`, `HttpServer`,
`HttpsServer`, `TftpServer`, `FtpServer`, `SmtpServer`, `Pop3Server`, `EmailServer`, `NtpServer`, `SyslogServer`, `AcsServer`.
Anota la lista de métodos de cada uno. Si algún proceso no existe, `getProcess` devuelve `null`.

**P3.2 — Por servicio: escribir, leer para verificar y comprobar desde un cliente.** Hazlo **de uno en uno** y anota en el registro (sección 6):
| Servicio | Escribir | Verificar leyendo | Comprobar desde un cliente |
|---|---|---|---|
| DHCP varios pools | `addPool`, `addExcludedAddress` (probar firmas una a una) | `getPoolCount`, `getPoolAt(n)` | Un PC de otra red recibe IP del pool correcto (`ipconfig`) |
| HTTP páginas | probar los setters que salgan en P3.1 | `getPage` | `pt_http_get` devuelve el texto nuevo |
| FTP cuentas | `getFtpUserAccountManager` → añadir usuario con permisos | leer cuentas | En un PC: `ftp <ip>` con usuario y clave |
| EMAIL | `EmailServer.addUser`; dominio | leer usuarios | `EmailClient` de un PC: configurar, enviar y recibir |
| AAA | `addToClientMap`, `addToUserMap`, `enableACSServerService` | leer mapas | En un router: `aaa new-model` + servidor Radius/Tacacs y probar un acceso |
| NTP | clave (`setKeyID`) y hora | `getKeyId`, `getServerMd5Str` | `show ntp status` en el router |
| SYSLOG | — (solo lectura) | leer entradas | En un router: `logging host <ip>`, provocar un evento y mirar el registro |
| TFTP | listar y quitar imagen | lista | En un router: `copy running-config tftp` |
| DNS | (alta manual en *Services → DNS*) | leer `<NAMESERVER-DATABASE>` con `serializeToXml` | `nslookup <nombre>` en un PC y `pt_http_get` por nombre |

**P3.3 — Cada servicio se ve en la ventana gráfica.** Tras cada escritura, abre *Services* del servidor y comprueba que lo escrito aparece (es la prueba de que se escribió
en el almacén que usa la interfaz, el fallo que dio el DNS).

### 3.5 Criterio de aceptación
- Cada servicio de la tabla tiene: herramienta, **lectura de verificación** y comprobación desde un cliente documentada.
- Lo que no se pueda hacer por IPC (como los registros DNS) queda como **flujo guiado** con su comprobación y apuntado en `NOTAS.md` y `CLAUDE.md`.
- Se probó **encender y apagar** cada servicio (no solo encender) y que el estado se ve en la ventana.

---

## 4. Comprobación con el sobrecillo (Add Simple PDU)

### 4.1 Qué se quiere
Usar el **sobre** de la barra de herramientas (*Add Simple PDU*) para demostrar, **en una captura**, que se han probado:
equipo ↔ equipo, equipo → servidores y equipo → routers, y que en la lista de PDU sale **Successful**.

### 4.2 Qué dice la ayuda de la 6.0.1 (`mode_simulation*.htm`, `mode_realtime.htm`)
- El PDU simple es una forma gráfica de enviar un ping de una sola vez; solo funciona entre equipos con **una interfaz con IP**.
- En **Realtime** el ping ocurre al instante y el resultado se ve en la **User Created Packet Window**. En **Simulación** el paquete queda en cola hasta pulsar *Auto Capture/Play*.
- La lista (*Protocol Data Units List*) tiene las columnas **Fire** (doble clic: reenvía el PDU), **Last Status** (*Successful*, *Fail* o *In Progress*), **Source** y **Destination**
  (y *Edit*). Pertenece a un *escenario* (por defecto *Scenario 0*), y *Toggle PDU List Window* la saca a una ventana propia.
- Un escenario se reinicia si se escribe un comando en configuración global de un equipo, así que hay que **lanzar los PDU después de configurar**.

### 4.3 Qué hay hoy y qué dice el proyecto de referencia
- Nosotros: `pt_ping`, `pt_ping_matrix` (todos contra todos) y `pt_traceroute`, todos por la **consola**; `pt_realtime` pone el modo Tiempo real. **Nada usa el sobre.**
- Ellos: `pt_verify_connectivity` (ping de consola) y las de simulación (`pt_simulation_mode`, `pt_simulation_step`, `pt_read_packet_trace`).
  Y **declaran que no se puede**: *«PT does not expose it to extensions (the "Add Simple PDU" is GUI-only)»* y *«`pt_send_pdu` does NOT exist»* (lo afirma su documentación, escrita para PT 8/9; no sabemos si en la 6.0.1 es igual).
- En la 6.0.1 `ipc.appWindow()` expone `getUserCreatedPDU`, `getPDUListWindow`, `getSimulationPanel`, `getCommonToolbar`, `getRealtimeToolbar`, `getSimulationToolbar`…
  (`NOTAS.md`: «sin explorar»). **No sabemos qué métodos tienen**: puede que la 6.0.1 sí deje crear o leer PDU, o puede que no.

### 4.4 Plan: tres caminos, de mejor a peor
1. **Por API** (si P4.1 y P4.2 lo permiten): crear el PDU y leer su *Last Status*.
2. **Por interfaz**: seleccionar la herramienta del sobre, clicar el origen y el destino (UI Automation o clics: **riesgo de dejar activa una herramienta equivocada**) y leer el estado de la lista.
3. **Modo guiado** (siempre posible): el asistente deja todo preparado (Realtime, red convergida, ventana de la lista de PDU abierta y visible) y te dice
   qué parejas clicar; después **lee o captura** la lista con las herramientas del bloque 2.
En los tres, la prueba se cierra con la **captura de la lista de PDU** (bloque 2) mostrando *Successful*, y con `pt_ping` por consola como comprobación de respaldo.

### 4.5 Pruebas en clase
**P4.1 — ¿Qué métodos tienen esos objetos?** (solo lectura) `pt_eval`, una vez por objeto (`getUserCreatedPDU`, `getPDUListWindow`, `getSimulationPanel`):
```js
(function () { var o = ipc.appWindow().getUserCreatedPDU(); var k = []; var m; for (m in o) { k.push(m); } k.sort(); return k.join(", "); })()
```
Busca nombres como `add…`, `get…Count`, `…Status`, `fire`. **Apunta la lista completa en `NOTAS.md`.**

**P4.2 — ¿Se puede leer lo que crea el usuario?** Pon PT en Tiempo real, crea **a mano** un sobre entre dos PCs con ping correcto y, con los métodos de P4.1,
intenta leer cuántos PDU hay, su origen, destino y estado. Después mira si hay método para crear uno (solo si P4.1 lo muestra; **una firma por llamada**).

**P4.3 — Si hay que leerlo de la interfaz:** repite la prueba P2.4 (UI Automation) con la ventana *User Created Packet Window* y comprueba si el texto *Successful* aparece como elemento legible.

**P4.4 — Matriz de pruebas mínima** (cuando haya camino): el escenario de clase con sus parejas.
| Tipo de prueba | Ejemplo | Esperado |
|---|---|---|
| Equipo ↔ equipo (misma red) | PC1 → PC2 | Successful |
| Equipo ↔ equipo (otra sede, a través de routers) | PC de la sede A → PC de la sede B | Successful |
| Equipo → servidor (DHCP, DNS, web…) | PC → cada servidor | Successful |
| Equipo → router (su gateway) | PC → router de su sede | Successful |
Si algún PDU sale *Fail* en el primer intento, **dispáralo otra vez** (doble clic en *Fire*): el primero puede perderse por ARP o por la convergencia (OSPF tarda ~40 s).

### 4.6 Nota para la documentación de este cambio *(revisar al documentarlo)*
Cuando se documente este cambio hay que comprobar y dejar escrito:
- [ ] El requisito tal cual: **captura de la lista de PDU con *Successful*** para equipo ↔ equipo, equipo → servidor y equipo → router.
- [ ] Qué camino se usó (API, interfaz o guiado) y por qué los otros no valían.
- [ ] Que se probó en **Tiempo real** y después de configurar y converger la red (los escenarios se reinician con la configuración global).
- [ ] La matriz de 4.4 con el resultado de cada pareja, y la captura de cada ventana/lista usada (bloque 2).
- [ ] Que la prueba de respaldo por consola (`pt_ping`) coincide con lo que dice la lista de PDU.
- [ ] Los límites que haya: si el sobre no se puede automatizar en la 6.0.1, **decirlo claramente** en vez de simularlo con pings de consola.

### 4.7 Criterio de aceptación
Una captura de la lista de PDU (o de la ventana principal con la lista visible) donde se vean las parejas de la matriz con **Last Status = Successful**, generada
siguiendo uno de los tres caminos, y la tabla 4.5 rellenada.

---

## 5. Orden sugerido en clase
1. **Preparar (5 min):** archivo de pruebas, Debug cerrada, `pt_status` conectado, Tiempo real (`pt_realtime`).
2. **Solo lectura (15 min):** P1.1, P1.2, P3.1, P4.1, P2.1, P2.3. Con esto se sabe qué es posible antes de escribir una línea de código.
3. **Capturas (15 min):** P2.2 y P2.4. Decidir en ese momento si el PNG automático sirve para la clase (punto pendiente de 2.4).
4. **Escrituras reversibles (20 min):** P1.3 y P1.4; después P3.2 servicio por servicio (los más usados primero: HTTP, FTP, EMAIL).
5. **Sobre (10 min):** P4.2 y P4.4 con la red que ya tengas montada.
6. **Cerrar:** rellenar la sección 6, pasar los hallazgos a `NOTAS.md` y actualizar «Lo primero que probablemente haya que reparar» en `CLAUDE.md`.

## 6. Registro de resultados
Copia esta tabla en `NOTAS.md` (o rellénala aquí) con la fecha de la prueba. Estados: ✔ funciona · ✘ falla · ➖ no existe en la 6.0.1.

| ID | Prueba | Estado | Valor o mensaje real | ¿Se ve en la ventana gráfica? | Notas |
|---|---|---|---|---|---|
| P1.1 | Métodos de puerto en switch, PC, servidor | | | — | |
| P1.2 | Leer datos de un puerto (con y sin cable) | | | — | |
| P1.3 | Escrituras reversibles de puerto (una fila por setter) | | | | |
| P1.4 | IOS de tuning y port-security | | | — | |
| P1.5 | Módulos reales de Router/Switch-PT-Empty | | | — | |
| P2.1 | `getWorkspaceImage` | | | — | |
| P2.2 | `PrintWindow` de la ventana principal | | | — | |
| P2.3 | `DialogManager` | | | | |
| P2.4 | UI Automation ve pestañas | | | — | |
| P3.1 | Métodos de cada servicio (12 procesos) | | | — | |
| P3.2 | Servicios: DHCP multipool / HTTP / FTP / EMAIL / AAA / NTP / SYSLOG / TFTP / DNS | | | | |
| P4.1 | Métodos de `getUserCreatedPDU` y compañía | | | — | |
| P4.2 | Leer o crear un PDU por API | | | | |
| P4.3 | Leer la lista de PDU desde la interfaz | | | | |
| P4.4 | Matriz de 4 tipos de pareja en *Successful* | | | | |
