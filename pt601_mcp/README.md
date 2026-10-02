# pt601_mcp — MCP local para Cisco Packet Tracer 6.0.1

Pídele a Claude (en VS Code o en terminal) que cree mapas de red, configure routers/switches/servidores
y haga pruebas de ping **en tiempo real dentro de tu Packet Tracer 6.0.1**. Todo corre en tu PC, sin
servidores externos, sin administrador y **sin instalar paquetes de Python** (solo biblioteca estándar).

> Versión objetivo: **Packet Tracer 6.0.1.0011** (Help → About). La 6.0.1 usa una API distinta de la
> de las versiones modernas; este proyecto ya incorpora esas diferencias (ver `docs/herramientas.md`).

```
VS Code / Claude Code ──stdio──> pt601_mcp ──HTTP 127.0.0.1:54321 (+token)──> panel (web view en PT)
                                                                                   │ evaluateJavaScript
                                                                                   ▼
                                                                          Script Engine de PT 6.0.1 → ipc
```

## Índice
1. [Instalación](#1-instalación-una-sola-vez) · 2. [Añadirlo a VS Code / Claude Code](#2-añadirlo-a-vs-code--claude-code)
3. [Uso diario](#3-uso-diario) · 4. [Skill de Claude (recomendado)](#4-skill-de-claude-recomendado)
5. [Solución de problemas](#5-solución-de-problemas) · 6. [Seguridad](#6-seguridad) · 7. [Pruebas](#7-pruebas-sin-packet-tracer)

Más documentación: [`docs/herramientas.md`](docs/herramientas.md) (referencia de todas las herramientas) y
[`docs/ejemplos.md`](docs/ejemplos.md) (prompts y planes JSON de ejemplo).

## 1. Instalación (una sola vez)

### 1.1 Python portátil (sin instalador ni administrador)
1. Descarga **Windows embeddable package (64-bit)** de https://www.python.org/downloads/windows/
   (`python-3.12.x-embed-amd64.zip`) y descomprímelo, por ejemplo en `C:\Users\<tú>\python312`.
2. Comprueba: `C:\Users\<tú>\python312\python.exe --version`.

### 1.2 Descargar este repositorio
Descarga el repo (zip o `git clone`) y anota la ruta de `pt601_mcp\run.py`.
Ejemplo: `C:\Users\<tú>\Downloads\cisco-packet-tracer-MCP-main\pt601_mcp\run.py`.

### 1.3 Extensión dentro de Packet Tracer
1. *Extensions → Scripting → New PT Script Module*.
2. Pestaña **Script Engine**: borra lo que haya y pega el contenido de `pt601_mcp/extension/script_engine.js`.
3. En la pestaña **General** marca **todos** los *Security Privileges*.
4. Pulsa **Start**: se abre la ventana **"PT-MCP local"** (puedes minimizarla, no cerrarla).
   Si el servidor aún no estaba en marcha, el módulo reintenta solo cada ~3 s.
5. Opcional pero cómodo: guarda el módulo y añádelo en *Extensions → Scripting → Configure PT Script Modules*
   para no volver a pegarlo.

## 2. Añadirlo a VS Code / Claude Code

### Claude Code (también la extensión de Claude Code en VS Code)
```powershell
claude mcp add --scope user packet-tracer-601 -- C:\Users\<tú>\python312\python.exe C:\ruta\al\repo\pt601_mcp\run.py
claude mcp list
```
En PowerShell, si el comando falla con `unknown option`, entrecomilla el separador: `"--"`.
`claude mcp list` debe mostrar `packet-tracer-601 … ✓ Connected`.

Alternativa por proyecto: archivo `.mcp.json` en la raíz de tu carpeta de trabajo:
```json
{
  "mcpServers": {
    "packet-tracer-601": {
      "command": "C:\\Users\\<tú>\\python312\\python.exe",
      "args": ["C:\\ruta\\al\\repo\\pt601_mcp\\run.py"]
    }
  }
}
```

### GitHub Copilot en VS Code (u otro cliente MCP de VS Code)
Archivo `.vscode/mcp.json` (o *MCP: Add Server* → stdio):
```json
{
  "servers": {
    "packet-tracer-601": {
      "type": "stdio",
      "command": "C:\\Users\\<tú>\\python312\\python.exe",
      "args": ["C:\\ruta\\al\\repo\\pt601_mcp\\run.py"]
    }
  }
}
```
Inicia el servidor desde el botón *Start* que VS Code muestra sobre la entrada y activa las herramientas en el chat (modo Agent).

> Cierra `servidor.ps1` / `servidor.py` del prototipo si siguen abiertos: usan el mismo puerto 54321.

## 3. Uso diario
1. Abre Packet Tracer 6.0.1 y un archivo (nuevo o existente).
2. En el Script Module pulsa **Start** (ventana "PT-MCP local" abierta). El servidor MCP lo arranca tu cliente
   (VS Code/Claude Code) automáticamente.
3. Pídele a Claude, por ejemplo: *«Comprueba el estado con pt_status»* y después
   *«Crea un mapa de red con un switch, 3 PCs y 2 portátiles; un servidor DHCP con IP 192.168.1.2 que reparta
   192.168.1.100-199 y un servidor DNS 192.168.1.3 con www.local»*.
4. Mira cómo aparece en tu PT en directo. Pídele ajustes: *«Añade un router, ponle la 192.168.1.1 y haz un ping desde PC1 al servidor DNS»*.

Si cambias de archivo `.pkt` en PT, el módulo sigue activo (es un módulo de PT, no del archivo).

## 4. Skill de Claude (recomendado)
La *skill* enseña a Claude el catálogo de herramientas, el flujo de trabajo y las particularidades de la 6.0.1
para que no invente nombres ni modelos. Instálala **globalmente** desde la raíz del repo:

PowerShell:
```powershell
New-Item -ItemType Directory -Force "$HOME\.claude\skills\packet-tracer-601" | Out-Null
Copy-Item skill\SKILL.md "$HOME\.claude\skills\packet-tracer-601\SKILL.md"
```
Linux/macOS/Git Bash: `mkdir -p ~/.claude/skills/packet-tracer-601 && cp skill/SKILL.md ~/.claude/skills/packet-tracer-601/SKILL.md`

Después reinicia Claude Code (o `/reload-skills`) y comprueba con `/skills`.

## 5. Solución de problemas
| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `pt_status` dice "PT no está conectado" | Módulo parado o ventana "PT-MCP local" cerrada | *Stop* y *Start* en el Script Module; deja la ventana abierta |
| Ventana "PT-MCP local" en blanco | PT arrancó el módulo antes que el servidor MCP | Espera ~3 s (reintenta solo) o pulsa Stop/Start |
| El panel muestra `HTTP 401` | El servidor MCP se reinició y cambió el token | Recarga: Stop/Start del módulo |
| Error por puerto 54321 en uso | `servidor.ps1`/`servidor.py` del prototipo abiertos, u otra instancia | Ciérralos; o usa `--port 54400` en `args` y cambia `URL` en `script_engine.js` |
| Las herramientas dan *timeout* | PT ocupado (simulación pesada) o ventana Debug abierta con un error | Cierra la ventana Debug del módulo y reintenta |
| `ya existe un dispositivo llamado X` | Nombre repetido (la 6.0.1 permitiría duplicados invisibles y no cablearía) | Usa otro nombre o `pt_remove_device` |
| `PT rechazo el cable` | Puerto ocupado o nombre de puerto incorrecto | `pt_list_ports` y usa `pt_connect` (elige puertos libres solo) |
| Un router no responde a comandos | Sigue en el diálogo inicial | `pt_cli` responde `no` automáticamente; si no, `pt_read_output` para ver el prompt |
| Servidor DHCP/DNS falla | La API de servicios puede variar en la 6.0.1 | `pt_describe` con `process="DhcpServer"` y pásame la lista de miembros |
| `pt_ping` pierde los primeros paquetes | Normal: ARP + convergencia del switch | Repite el ping |

## 6. Seguridad
Puerto solo en `127.0.0.1`, **token aleatorio por sesión** (solo lo recibe la página del panel), validación de
`Host` contra DNS rebinding, **sin endpoint de ejecución remota** y cuerpos limitados a 1 MB.
`pt_eval` ejecuta código dentro de PT por diseño: solo lo alcanza un cliente MCP que tú hayas autorizado.

## 7. Pruebas (sin Packet Tracer)
`python3 -m unittest discover -s tests -v`
