# pt601_mcp — servidor MCP local para Packet Tracer 6.0.1

Solo biblioteca estándar de Python 3.8+ (no necesita `pip` ni administrador).
Un único proceso hace de servidor MCP (stdio) y de puente HTTP con Packet Tracer.

```
VS Code / Claude Code ──stdio──> pt601_mcp ──HTTP 127.0.0.1:54321 (+token)──> panel (web view en PT)
                                                                                   │ evaluateJavaScript
                                                                                   ▼
                                                                          Script Engine de PT 6.0.1 → ipc
```

## 1. Python portátil (sin instalar)
1. Descarga **Windows embeddable package (64-bit)** de https://www.python.org/downloads/windows/
   (`python-3.12.x-embed-amd64.zip`) y descomprímelo, p. ej. en `C:\Users\<tú>\python312`.
2. Comprueba: `C:\Users\<tú>\python312\python.exe --version`.

## 2. Extensión en Packet Tracer (una vez)
1. *Extensions → Scripting → New PT Script Module*.
2. Pestaña **Script Engine**: pega `pt601_mcp/extension/script_engine.js`.
3. Marca **todos** los *Security Privileges*. Guarda el módulo (para no repetirlo, añádelo a *Configure PT Script Modules*).
4. **Start**: abre la ventana "PT-MCP local". Si el servidor aún no estaba arrancado, el módulo reintenta solo cada ~3 s.

## 3. Conectar el cliente MCP
VS Code (`.vscode/mcp.json` o configuración de usuario):
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
Claude Code: `claude mcp add --scope user packet-tracer-601 -- C:\Users\<tú>\python312\python.exe C:\ruta\al\repo\pt601_mcp\run.py`

Cierra `servidor.ps1` / `servidor.py` del prototipo si siguen abiertos (usan el mismo puerto 54321).
Primera prueba: pídele al asistente `pt_status`.

## Herramientas
`pt_status`, `pt_catalog`, `pt_list_devices`, `pt_add_device`, `pt_remove_device`, `pt_move_device`,
`pt_add_link`, `pt_set_ip`, `pt_cli`, `pt_read_output`, `pt_ping`, `pt_eval` (avanzada).

## Particularidades de la 6.0.1 (ya resueltas aquí)
- `addDevice` solo acepta (tipo, modelo); la posición se aplica después con `moveToLocation`.
- `setName` no impide duplicados por IPC: `pt_add_device` comprueba antes que el nombre esté libre.
- El cable se pasa como entero (8100 recto, 8101 cruzado, 8107 auto…).
- Los routers nuevos piden el diálogo inicial: `pt_cli` responde `no` automáticamente.
- `ping` desde un PC termina después de devolver el control: `pt_ping` espera a las estadísticas.

## Seguridad
Puerto solo en 127.0.0.1, token aleatorio por sesión (lo recibe únicamente la página del panel),
validación de `Host` contra DNS rebinding, sin endpoint de ejecución remota y cuerpos limitados a 1 MB.
`pt_eval` ejecuta código dentro de PT por diseño: solo lo alcanza un cliente MCP que tú hayas autorizado.

## Pruebas (sin Packet Tracer)
`python3 -m unittest discover -s tests -v`
