---
name: packet-tracer-601
description: Controla Cisco Packet Tracer 6.0.1 en tiempo real mediante el MCP local packet-tracer-601 (herramientas pt_*). Úsala siempre que el usuario pida crear, ampliar, configurar, documentar o probar redes en Packet Tracer 6.0.1: mapas de red, routers, switches, VLAN, OSPF/EIGRP/RIP, servidores DHCP/DNS, direccionamiento IP o pings.
---

# Packet Tracer 6.0.1 (MCP local `packet-tracer-601`)

Esta versión de Packet Tracer es **antigua (6.0.1.0011)**: su API difiere de la de las versiones modernas.
No uses nombres de métodos, modelos o puertos de memoria: usa las herramientas `pt_*` y el catálogo.

## Flujo de trabajo
1. `pt_status` — comprueba que PT está conectado. Si no lo está, pide al usuario que arranque el Script Module
   (Start) y deje abierta la ventana «PT-MCP local». No sigas hasta que responda.
2. `pt_list_devices` — mira qué hay ya en el workspace (no dupliques, no borres sin permiso).
3. **Para redes completas usa `pt_build_topology`** con un plan JSON (primero `dry_run: true` si es grande).
   Para cambios pequeños usa las herramientas sueltas.
4. Verifica: `pt_list_ports`, `pt_cli` con `show ip interface brief`, `pt_ping`.
5. Resume al usuario qué creaste (nombres, IPs, VLANs) y cualquier paso que diera `ERR`.

## Herramientas
- Consulta: `pt_status`, `pt_catalog`, `pt_list_devices`, `pt_list_ports`, `pt_read_output`, `pt_describe`, `pt_snapshot` (red entera: posiciones, IPs, cables, servicios),
  `pt_inspect_ports` (estado real de cada puerto y anomalías), `pt_server_read` (todo *Config → SERVICES*: registros DNS con TTL, FTP, correo…)
- Puertos y servicios: `pt_set_port` (un puerto: descripción, encendido, velocidad, dúplex, MAC; modo access/trunk, VLAN y port-security por IOS),
  `pt_server_ftp`, `pt_server_email`, `pt_add_module` con `count`
- Capturas (para documentar): `pt_screenshot` (mapa), `pt_ui_open` (ventana de un equipo en la pestaña/sección pedida, con captura),
  `pt_ui_capture`, `pt_ui_close`. Se guardan en `capturas/`. Necesitan el mapa al 100 % de zoom.
  **Ojo:** una aplicación del Desktop abierta (IP Configuration…) escribe sus valores al cerrarse y pisa lo que haya cambiado el MCP. Las
  herramientas ya la cierran tras capturar; si el usuario tiene una abierta en un equipo, pídele que la cierre antes de cambiarle la IP
- Construcción: `pt_build_topology`, `pt_add_device`, `pt_connect` (puertos libres automáticos), `pt_add_link`, `pt_move_device`, `pt_remove_device`, `pt_clear_workspace` (exige `confirm`)
- Configuración: `pt_set_ip`, `pt_router_config`, `pt_switch_config`, `pt_config` (IOS libre), `pt_cli`, `pt_dhcp_server`, `pt_dns_server`
- Pruebas: `pt_ping`
- Avanzada: `pt_eval` (JavaScript dentro de PT; último recurso)

Referencia completa y esquemas: `pt601_mcp/docs/herramientas.md` y `pt601_mcp/docs/ejemplos.md`.

## Convenciones del usuario (`reglas.md`)
Antes de crear nada lee **`reglas.md`** (raíz del repositorio): define cómo se nombran los equipos y cómo se reparten IPs, VLANs, puertos y posiciones.
Manda sobre cualquier valor por defecto. Donde ponga `PENDIENTE`, pregunta una cosa corta al usuario; no inventes. Para redes grandes enseña
primero el plan (`pt_build_topology` con `dry_run: true`).
Para una práctica de servidores + sedes usa `pt_class_plan` (primero sin `build` para enseñar el plan). Usa siempre modelos `PT-Empty`.
En un Server-PT toca los servicios (`pt_server_services`) solo si el enunciado pide configurar ese servicio. Cuando el usuario enseñe un trabajo suyo, léelo con
`pt_snapshot` y anota en `reglas.md` las costumbres que deduzcas, sin pedir confirmación: solo dile qué has anotado.

## Reglas
- **Modelos**: solo los de `pt_catalog`. Los verificados en 6.0.1: `2911`, `2960-24TT`, `PC-PT`, `Switch-PT-Empty`,
  `Router-PT-Empty`, `Server-PT`, `Laptop-PT`, `AccessPoint-PT`. Si usas uno «sin verificar», avisa al usuario.
- **Nombres únicos** por dispositivo. El MCP rechaza duplicados (la 6.0.1 los permitiría y quedarían invisibles).
- **Cableado**: deja que `pt_connect`/`links` elijan puertos. En planes, escribe `"@VECINO"` como puerto para
  referirte al puerto que enlaza con ese vecino (así la config IP del router coincide con el cable real).
- **IPs**: valida máscaras/gateways; usa subredes coherentes; el gateway de cada LAN es el router (o SVI).
  Los servidores llevan IP **estática**; los clientes, DHCP salvo que se pida otra cosa.
- **Routers nuevos**: `pt_cli` responde solo al diálogo inicial. Los comandos IOS van tal cual (`enable`, `configure terminal`…).
- **Ping**: los primeros paquetes se pierden por ARP/convergencia del switch; repite antes de dar un fallo por bueno. OSPF/EIGRP
  necesitan unos segundos.
- **DHCP/DNS en Server-PT**: si `pt_dhcp_server`/`pt_dns_server` fallan, ejecuta `pt_describe` con
  `process="DhcpServer"` (o `DnsServer`) y enseña la lista al usuario; no inventes métodos.
  Alternativa fiable para DHCP: pool en el router con `pt_router_config` (`dhcp_pools`).
- **No uses `pt_eval`** salvo que no exista herramienta. Si lo usas: JavaScript estilo ES3 (sin `let`/`const`/flechas/`JSON`),
  siempre devuelve texto, y nunca ejecutes código que no hayas entendido.
- **Destructivo**: no uses `pt_clear_workspace` ni `pt_remove_device` sin que el usuario lo haya pedido claramente.

## Plantilla de plan (`pt_build_topology`)
```json
{
  "devices": [{"name": "SW1", "model": "2960-24TT"}, {"name": "PC1", "model": "PC-PT"}, {"name": "SRV1", "model": "Server-PT"}],
  "links": [{"a": "SW1", "b": "PC1"}, {"a": "SW1", "b": "SRV1"}],
  "servers": [{"device": "SRV1", "ip": "192.168.1.2", "mask": "255.255.255.0", "gateway": "192.168.1.1",
               "dhcp": {"pool": "LAN", "start_ip": "192.168.1.100", "mask": "255.255.255.0", "gateway": "192.168.1.1", "dns": "192.168.1.3", "max_users": 100},
               "dns": {"records": [{"name": "www.local", "ip": "192.168.1.2"}]}}],
  "hosts": [{"device": "PC1", "dhcp": true}],
  "routers": [], "switches": [], "cli": []
}
```
Secciones opcionales: `routers[]` (`device`, `interfaces`, `static_routes`, `default_route`, `ospf`, `eigrp`, `rip`, `dhcp_pools`),
`switches[]` (`vlans`, `access_ports`, `trunk_ports`, `svi`), `cli[]` (`device`, `commands`).

## Si algo falla
Lee el mensaje del error (viene en español y dice la causa habitual). Si es de conexión: `pt_status`.
Tabla de problemas frecuentes en `pt601_mcp/README.md` (sección «Solución de problemas»).
