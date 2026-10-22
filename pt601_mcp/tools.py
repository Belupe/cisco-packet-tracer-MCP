"""Herramientas MCP para Packet Tracer 6.0.1 (traducen llamadas a JavaScript del puente)."""
import base64
import binascii
import os
import time

import ipaddress
import json
import re
import xml.etree.ElementTree as ET

from . import catalog, ios, jsgen, plan as planmod, winui
from .bridge import BridgeError


class ToolError(Exception):
    """Error pensado para que lo lea el usuario / el modelo."""


class Rich:
    """Resultado con texto e imagenes (bytes PNG). mcpproto lo convierte en contenido text + image."""

    def __init__(self, text, images=()):
        self.text, self.images = text, list(images)

    def __str__(self):
        return self.text


MAX_OUT = 6000
CAPTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "capturas")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
LIGHTS = {"0": "apagada", "1": "ambar", "2": "verde"}
# setAdminOpMode/getAdminOpMode de un puerto de switch (comprobado con el running-config en la 6.0.1).
SWITCH_MODES = {"0": "dynamic desirable", "1": "dynamic auto", "2": "trunk", "3": "access"}


# Ventana de un equipo en la 6.0.1 (655x521), medida en capturas el 2026-10-22. Coordenadas desde la esquina de la ventana.
UI_TAB_Y = 43
UI_TABS = {"physical": 42, "config": 108, "cli": 160, "desktop": 175, "custom interface": 271}
UI_TABS_BY_TYPE = {0: ("physical", "config", "cli"), 1: ("physical", "config", "cli"),
                   8: ("physical", "config", "desktop", "custom interface"), 9: ("physical", "config", "desktop", "custom interface"),
                   17: ("physical", "config", "desktop", "custom interface")}       # portatil: igual que el PC (medido)
_UI_HEAD = ["GLOBAL", "Settings", "Algorithm Settings"]
UI_SECTIONS = {0: _UI_HEAD + ["ROUTING", "Static", "RIP", "INTERFACE"],
               1: _UI_HEAD + ["SWITCH", "VLAN Database", "INTERFACE"],
               8: _UI_HEAD + ["Firewall", "IPv6 Firewall", "INTERFACE"],
               9: _UI_HEAD + ["SERVICES", "HTTP", "DHCP", "TFTP", "DNS", "SYSLOG", "AAA", "NTP", "EMAIL", "FTP",
                              "FIREWALL", "IPv6 FIREWALL", "INTERFACE"],
               17: _UI_HEAD + ["Firewall", "IPv6 Firewall", "INTERFACE"]}
UI_SECTION_X, UI_SECTION_Y0, UI_SECTION_DY, UI_SECTION_ROWS = 82, 75, 19, 20
UI_DESKTOP_PC = {"ip configuration": (90, 145), "dial-up": (210, 145), "terminal": (330, 145), "command prompt": (450, 145),
                 "web browser": (570, 145), "pc wireless": (90, 290), "vpn": (210, 290), "traffic generator": (330, 290),
                 "mib browser": (450, 290), "cisco ip communicator": (570, 290), "e mail": (90, 410), "email": (90, 410),
                 "pppoe dialer": (210, 410), "text editor": (330, 410)}
UI_DESKTOP_SERVER = {"ip configuration": (92, 140), "command prompt": (212, 140), "traffic generator": (332, 140),
                     "text editor": (452, 140), "web browser": (572, 140), "pppoe dialer": (92, 285), "vpn": (212, 285)}
UI_DESKTOP = {8: UI_DESKTOP_PC, 9: UI_DESKTOP_SERVER, 17: UI_DESKTOP_PC}
UI_DEVICE_TYPES = {0: "router", 1: "switch", 8: "PC", 9: "servidor", 17: "portatil"}
UI_ICON_DX = 15            # el punto logico del equipo cae en el borde izquierdo del icono, a media altura


def _safe_filename(name, default):
    """Nombre de archivo sin carpetas ni caracteres raros, siempre .png."""
    base = re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename(str(name or "").strip())).strip("._") or default
    return base if base.lower().endswith(".png") else base + ".png"


def _clip(text, limit=MAX_OUT):
    text = str(text)
    return text if len(text) <= limit else "...[recortado]...\n" + text[-limit:]


def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


S = {"type": "string"}
I = {"type": "integer"}
B = {"type": "boolean"}


class Tools:
    def __init__(self, bridge, js_timeout=25.0, ui=winui):
        self.bridge = bridge
        self.js_timeout = js_timeout
        self.ui = ui                     # ventanas de Windows; las pruebas lo sustituyen por uno falso
        self.registry = [
            ("pt_status", "Estado del puente y de Packet Tracer (version, numero de dispositivos).",
             _obj({}), self.status),
            ("pt_realtime",
             "Pone Packet Tracer en modo Tiempo real (si esta en Simulacion nada avanza: ping, DHCP, STP, OSPF/RIP).",
             _obj({}), self.realtime),
            ("pt_catalog", "Modelos de dispositivo y tipos de cable disponibles en PT 6.0.1.",
             _obj({}), self.catalog),
            ("pt_list_devices", "Lista los dispositivos del workspace (nombre, modelo, tipo, encendido, puertos).",
             _obj({}), self.list_devices),
            ("pt_add_device",
             "Crea un dispositivo. Falla si el nombre ya existe (PT 6.0.1 permite duplicados por IPC y despues no se pueden cablear).",
             _obj({"name": S, "model": S, "x": I, "y": I, "ports": I}, ["name", "model"]), self.add_device),
            ("pt_remove_device", "Borra un dispositivo por nombre (todas las copias).",
             _obj({"name": S}, ["name"]), self.remove_device),
            ("pt_rename_device",
             "Cambia el nombre de un dispositivo. Falla si el nombre nuevo ya existe (al renumerar varios, hazlo en un "
             "orden que nunca pise un nombre aun en uso).",
             _obj({"name": S, "new_name": S}, ["name", "new_name"]), self.rename_device),
            ("pt_move_device", "Mueve un dispositivo a (x, y).",
             _obj({"name": S, "x": I, "y": I}, ["name", "x", "y"]), self.move_device),
            ("pt_add_link",
             "Conecta dos puertos. cable: straight|cross|roll|fiber|serial|console|auto (por defecto auto). "
             "Ej.: port1='GigabitEthernet0/0', port2='FastEthernet0/1'.",
             _obj({"device1": S, "port1": S, "device2": S, "port2": S, "cable": S},
                  ["device1", "port1", "device2", "port2"]), self.add_link),
            ("pt_add_note",
             "Pone una nota de texto en el mapa (p. ej. la IP de un servidor encima de el). size = tamano de letra (10 por defecto).",
             _obj({"text": S, "x": I, "y": I, "size": I}, ["text", "x", "y"]), self.add_note),
            ("pt_list_notes", "Lista las notas y dibujos del mapa (id, x, y). El texto no se puede leer por IPC.",
             _obj({}), self.list_notes),
            ("pt_remove_note", "Borra una nota del mapa por su id (el que da pt_add_note / pt_list_notes).",
             _obj({"id": S}, ["id"]), self.remove_note),
            ("pt_remove_link", "Quita el cable conectado a un puerto de un dispositivo.",
             _obj({"device": S, "port": S}, ["device", "port"]), self.remove_link),
            ("pt_add_module",
             "Anade un modulo (un puerto) a un Switch-PT-Empty o Router-PT-Empty que ya existe. kind: fastethernet (por defecto), "
             "fiber y, en routers, gigabit, gigabit-fiber, serial, ethernet, modem. count=N pone N modulos en ranuras seguidas "
             "desde slot (un solo apagado). Apaga y enciende el equipo: guarda antes su "
             "configuracion (write memory) si es un router o switch ya configurado: al reiniciarse pierde lo no guardado.",
             _obj({"device": S, "slot": I, "kind": S, "count": I}, ["device", "slot"]), self.add_module),
            ("pt_remove_module",
             "Quita el modulo de una ranura (p. ej. un puerto que sobra en un Switch-PT-Empty: ranura n = FastEthernet<n>/1). "
             "Apaga y enciende el equipo; el puerto debe estar sin cable.",
             _obj({"device": S, "slot": I}, ["device", "slot"]), self.remove_module),
            ("pt_set_ip",
             "Configura IP en un PC/servidor/laptop (por defecto puerto FastEthernet0): ip, mask, gateway y dns "
             "(servidor DNS de la configuracion IP). dhcp=true activa cliente DHCP.",
             _obj({"device": S, "ip": S, "mask": S, "gateway": S, "dns": S, "port": S, "dhcp": B}, ["device"]), self.set_ip),
            ("pt_cli",
             "Envia comandos a la consola de un router/switch/PC y devuelve la salida nueva. Para routers nuevos "
             "responde solo 'no' al dialogo inicial. Ej.: ['enable','configure terminal','hostname R1']. "
             "interactive=true: una linea cada vez esperando la respuesta (para ftp/telnet desde un PC, que piden usuario y "
             "clave): ['ftp 192.168.1.2','usuario','clave','dir','quit']. wait_seconds = espera maxima por linea.",
             _obj({"device": S, "commands": {"type": "array", "items": S}, "answer_initial_dialog": B,
                   "interactive": B, "wait_seconds": I},
                  ["device", "commands"]), self.cli),
            ("pt_running_config",
             "Devuelve la configuracion en ejecucion (running-config) completa de un router o switch, sin paginar: "
             "interfaces con IP, rutas estaticas, VLAN... Mejor que 'show running-config' por consola.",
             _obj({"device": S}, ["device"]), self.running_config),
            ("pt_read_output", "Lee el final de la consola de un dispositivo.",
             _obj({"device": S, "tail_chars": I}, ["device"]), self.read_output),
            ("pt_ping",
             "Ejecuta ping desde un dispositivo y espera el resultado (los primeros paquetes pueden perderse por ARP/STP).",
             _obj({"device": S, "target": S, "wait_seconds": I}, ["device", "target"]), self.ping),
            ("pt_routing_audit",
             "Revisa las tablas de enrutamiento de TODOS los routers: averigua todas las redes del mapa y dice, router por router, "
             "cuantas conoce, si tiene ruta por defecto y cuales le faltan. save=true guarda ademas la configuracion de todos (write memory).",
             _obj({"save": B}, []), self.routing_audit),
            ("pt_ping_matrix",
             "Prueba de conectividad TODOS CONTRA TODOS: da un equipo (PC/portatil/servidor) por red y hace ping entre cada pareja, "
             "varias a la vez. Devuelve cuantas parejas responden y cuales fallan. Un ping prueba la ida y la vuelta.",
             _obj({"devices": {"type": "array", "items": S}, "wait_seconds": I}, ["devices"]), self.ping_matrix),
            ("pt_traceroute",
             "Traza la ruta (tracert) desde un PC/portatil/servidor hasta una IP: ensena por que routers pasa.",
             _obj({"device": S, "target": S, "wait_seconds": I}, ["device", "target"]), self.traceroute),
            ("pt_list_ports", "Lista los puertos de un dispositivo y si estan libres o conectados.",
             _obj({"device": S}, ["device"]), self.list_ports),
            ("pt_inspect_ports",
             "Estado REAL de cada puerto de un equipo (lo que se ve en Config > INTERFACE): encendido, linea y protocolo, luz, MAC, IP, "
             "ancho de banda, duplex, MTU, descripcion, VLAN (switch), vecino del cable. Marca anomalias (cable con el puerto caido, "
             "puerto apagado...). only_linked=true: solo los puertos con cable.",
             _obj({"device": S, "only_linked": B}, ["device"]), self.inspect_ports),
            ("pt_set_port",
             "Cambia UN puerto como en su ventana (Config > INTERFACE) y dice que se aplico. Por API: description, power (true/false), "
             "speed (auto|10|100|1000 Mbps), duplex (auto|full|half), mtu, mac (0011.2233.4455), cdp, proxy_arp. Por IOS (switch): "
             "mode (access|trunk), vlan, native_vlan, allowed_vlans, port_security {maximum, violation: shutdown|restrict|protect, "
             "sticky, macs}. Por IOS (router): ip_bandwidth (kbps), ip_delay (decenas de us), clock_rate, ospf {cost, priority, hello, "
             "dead, auth_key, md5_key_id, md5_key}. Solo cambia lo que se pasa. dry_run=true ensena lo que haria. save=true: write memory.",
             _obj({"device": S, "port": S, "description": S, "power": B, "speed": S, "duplex": S, "mtu": I, "mac": S,
                   "cdp": B, "proxy_arp": B, "mode": S, "vlan": I, "native_vlan": I,
                   "allowed_vlans": {"type": "array", "items": I}, "port_security": {"type": "object"},
                   "ip_bandwidth": I, "ip_delay": I, "clock_rate": I, "ospf": {"type": "object"}, "dry_run": B, "save": B},
                  ["device", "port"]), self.set_port),
            ("pt_screenshot",
             "Captura el MAPA (espacio de trabajo logico) como PNG: lo guarda en la carpeta capturas/ del proyecto y ensena la imagen. "
             "filename opcional (sin carpetas).",
             _obj({"filename": S}, []), self.screenshot),
            ("pt_dhcp_admin",
             "DHCP de un Server-PT, lo que no hace pt_dhcp_server: remove_pools=[nombres] quita pools (serverPool no se puede), "
             "exclude=[{start, end}] anade rangos excluidos, unexclude=[{start, end}] los quita. Sin parametros solo lista pools y "
             "exclusiones. OJO: en la 6.0.1 las exclusiones funcionan pero NO se ven en la ventana ni se guardan en el .pkt.",
             _obj({"device": S, "remove_pools": {"type": "array", "items": S},
                   "exclude": {"type": "array", "items": {"type": "object"}},
                   "unexclude": {"type": "array", "items": {"type": "object"}}}, ["device"]), self.dhcp_admin),
            ("pt_server_read",
             "Lee TODO lo que se ve en Config > SERVICES de un Server-PT (del XML del equipo): que servicios estan encendidos, "
             "registros DNS (nombre, tipo, IP, TTL), pools DHCP, cuentas FTP con permisos, dominio y cuentas de correo, NTP, AAA. "
             "Sirve para comprobar lo hecho a mano o por el MCP.",
             _obj({"device": S}, ["device"]), self.server_read),
            ("pt_server_ftp",
             "Crea cuentas FTP en un Server-PT: users=[{name, password, permissions}] (permisos con letras R W D N L = "
             "leer, escribir, borrar, renombrar, listar; por defecto RWDNL). Si la cuenta ya existe no la toca. "
             "remove=[nombres] borra cuentas.",
             _obj({"device": S, "users": {"type": "array", "items": {"type": "object"}}, "remove": {"type": "array", "items": S}},
                  ["device"]), self.server_ftp),
            ("pt_server_email",
             "Correo de un Server-PT: domain (el del boton Set de EMAIL) y cuentas users=[{name, password}]. "
             "Para encender SMTP/POP3 usa pt_server_services. Si la cuenta ya existe no la toca. remove=[nombres] borra cuentas.",
             _obj({"device": S, "domain": S, "users": {"type": "array", "items": {"type": "object"}},
                   "remove": {"type": "array", "items": S}}, ["device"]),
             self.server_email),
            ("pt_ui_open",
             "Abre la VENTANA de un equipo (como hacer clic en su icono) sin mover el raton, elige pestana (physical, config, cli, "
             "desktop, custom interface), seccion de Config (Settings, VLAN Database, Static, RIP, HTTP, DHCP, DNS, EMAIL, FTP, "
             "FastEthernet0/1...) y, en un PC, aplicacion del Desktop (ip configuration, command prompt, web browser...). "
             "Devuelve la captura de la ventana y la guarda en capturas/. El mapa debe estar a zoom 100 %.",
             _obj({"device": S, "tab": S, "section": S, "app": S, "filename": S}, ["device"]), self.ui_open),
            ("pt_ui_capture",
             "Captura como PNG la ventana de un equipo ya abierta (device) o, sin device, la ventana principal de Packet Tracer. "
             "La guarda en capturas/ y ensena la imagen.",
             _obj({"device": S, "filename": S}, []), self.ui_capture),
            ("pt_ui_close",
             "Oculta la ventana de un equipo (o todas sin device). Se oculta sin destruirla: pt_ui_open la vuelve a ensenar al momento.",
             _obj({"device": S}, []), self.ui_close),
            ("pt_connect",
             "Conecta dos dispositivos ELIGIENDO PUERTOS LIBRES automaticamente (o los que indiques). "
             "cable: auto (por defecto)|straight|cross|fiber.",
             _obj({"device1": S, "device2": S, "cable": S, "port1": S, "port2": S}, ["device1", "device2"]),
             self.connect),
            ("pt_config",
             "Aplica configuracion IOS multilinea a un router/switch (entra en enable + configure terminal y sale con end). "
             "save=true guarda con 'write memory'.",
             _obj({"device": S, "config": S, "save": B}, ["device", "config"]), self.config),
            ("pt_router_config",
             "Configura un router desde una descripcion: hostname, interfaces(port,ip,mask,vlan para subinterfaces), "
             "static_routes, default_route, ospf, eigrp, rip, dhcp_pools, extra. Ver docs/herramientas.md.",
             _obj({"device": S, "spec": {"type": "object"}, "save": B}, ["device", "spec"]), self.router_config),
            ("pt_vpn_ipsec",
             "Configura un extremo de una VPN IPsec sitio a sitio en un router 2811 (el Router-PT-Empty no admite VPN). "
             "spec={wan_port, peer, key, local:[{network, mask}], remote:[{network, mask}]}. Hay que configurar los DOS extremos, "
             "cada uno con el otro como peer y las redes invertidas. Comprueba con 'show crypto isakmp sa' tras un ping entre sedes.",
             _obj({"device": S, "spec": {"type": "object"}, "save": B}, ["device", "spec"]), self.vpn_ipsec),
            ("pt_switch_config",
             "Configura un switch desde una descripcion: hostname, vlans, access_ports, trunk_ports, svi, extra.",
             _obj({"device": S, "spec": {"type": "object"}}, ["device", "spec"]), self.switch_config),
            ("pt_dhcp_server",
             "Activa el servicio DHCP de un Server-PT y configura un pool: red y mascara (sacadas de start_ip y mask), inicio, "
             "fin (max_users), gateway y dns. pool: por defecto serverPool (el de fabrica); otro nombre crea un pool NUEVO "
             "(para otra red que llega por ip helper). IP estatica del servidor: usa pt_set_ip.",
             _obj({"device": S, "pool": S, "start_ip": S, "mask": S, "gateway": S, "dns": S, "max_users": I, "tftp": S},
                  ["device", "start_ip", "mask"]), self.dhcp_server),
            ("pt_dns_server",
             "Activa el servicio DNS de un Server-PT y crea registros A. records=[{name, ip}].",
             _obj({"device": S, "records": {"type": "array", "items": {"type": "object"}}}, ["device", "records"]),
             self.dns_server),
            ("pt_server_services",
             "Deja encendidos SOLO los servicios indicados de un Server-PT y apaga el resto. "
             "services: lista de dhcp|dns|http|https|tftp|ftp|smtp|pop3|ntp|syslog (email = smtp+pop3).",
             _obj({"device": S, "services": {"type": "array", "items": S}}, ["device", "services"]),
             self.server_services),
            ("pt_snapshot",
             "Lee la red ENTERA del archivo abierto: posicion (x,y) de cada equipo, IP/mascara/DHCP, cables con sus "
             "puertos y tipo, servicios y pool DHCP de los servidores. Para aprender de un trabajo ya hecho o verificar.",
             _obj({}), self.snapshot),
            ("pt_describe",
             "Introspeccion: lista los metodos de un dispositivo, de uno de sus procesos (process='DhcpServerMain') o de un puerto.",
             _obj({"device": S, "process": S, "port": S}, ["device"]), self.describe),
            ("pt_build_topology",
             "Construye una topologia COMPLETA desde un plan (devices, links, hosts, servers, routers, switches, cli) con "
             "autoposicionado y puertos automaticos (usa port '@VECINO' en interfaces/puertos para referirte al puerto que enlaza con VECINO). "
             "dry_run=true solo valida. Ver docs/ejemplos.md.",
             _obj({"plan": {"type": "object"}, "dry_run": B}, ["plan"]), self.build_topology),
            ("pt_class_plan",
             "Genera (y con build=true construye) una red con las CONVENCIONES DE CLASE de reglas.md a partir del enunciado: "
             "spec={server_switch, servers:[{name, ip, services?, dhcp?}], sites:[{name, pcs, laptops}], hosts_dhcp?, notes?}. "
             "Pone nombres por ultimo octeto desde la .10 (con hosts_dhcp=true NO renombra: PC0, Laptop0...), puertos justos, "
             "cables, posiciones del esquema, gateway .1 y DNS. "
             "Sin build devuelve el plan para revisarlo.",
             _obj({"spec": {"type": "object"}, "build": B}, ["spec"]), self.class_plan),
            ("pt_routed_plan",
             "Genera (y con build=true construye) una red CON ROUTERS: un Router-PT-Empty y un Switch-PT-Empty por sede, todos los "
             "routers unidos por un switch central, una subred por sede y encaminamiento. spec={lan_block, prefix (26 = trocear la /24), "
             "transit, routing: ospf|static|rip, core, origin:[x,y], host_names: octet|site, sites:[{name, pcs, laptops, dhcp?, servers?:[{name, services?}]}]}.",
             _obj({"spec": {"type": "object"}, "build": B}, ["spec"]), self.routed_plan),
            ("pt_http_get",
             "Abre una URL desde el navegador de un PC/portatil/servidor y devuelve la pagina (comprueba 'conectarse al Servidor Web', "
             "por IP o por nombre DNS). Vacio = no hubo respuesta.",
             _obj({"device": S, "url": S, "wait_seconds": I}, ["device", "url"]), self.http_get),
            ("pt_clear_workspace",
             "Borra TODOS los dispositivos. Exige confirm=true.",
             _obj({"confirm": B}, ["confirm"]), self.clear_workspace),
            ("pt_eval",
             "AVANZADO: ejecuta JavaScript (Qt Script, estilo ES3) dentro de PT y devuelve String(resultado).",
             _obj({"code": S}, ["code"]), self.eval),
        ]
        self.by_name = {name: (desc, schema, fn) for name, desc, schema, fn in self.registry}

    # ---- util ----------------------------------------------------------
    def listing(self):
        return [{"name": n, "description": d, "inputSchema": s} for n, d, s, _ in self.registry]

    def call(self, name, args):
        if name not in self.by_name:
            raise ToolError("Herramienta desconocida: %s" % name)
        return self.by_name[name][2](args or {})

    def _run(self, code, timeout=None):
        try:
            out = self.bridge.run_js(code, timeout or self.js_timeout)
        except BridgeError as exc:
            raise ToolError(str(exc))
        if out.startswith("ERROR"):
            raise ToolError(out)
        return out

    @staticmethod
    def _req(args, key):
        value = args.get(key)
        if value is None or str(value).strip() == "":
            raise ToolError("Falta el parametro obligatorio: %s" % key)
        return value

    # ---- herramientas --------------------------------------------------
    def status(self, args):
        info = self.bridge.status()
        lines = ["puente: puerto %(port)s | PT conectado: %(pt_connected)s | ultimo poll hace %(last_poll_ago)s s"
                 " | intentos no autorizados: %(unauthorized_attempts)s" % info]
        if info["pt_connected"]:
            parts = self._run(jsgen.status()).split("|")
            lines.append("Packet Tracer %s | %s dispositivos" % (parts[0], parts[1]))
            if len(parts) > 2 and parts[2].strip().lower() == "false":
                lines.append("AVISO: PT esta en modo SIMULACION: el tiempo no avanza (los ping se quedan sin respuesta, no hay DHCP, "
                             "STP ni rutas nuevas). Usa pt_realtime para volver a Tiempo real.")
        else:
            lines.append("PT no esta conectado: arranca el Script Module y deja abierta la ventana 'PT-MCP local'.")
        return "\n".join(lines)

    def realtime(self, args):
        if self._run(jsgen.realtime()).strip().lower() != "true":
            raise ToolError("PT no cambio a Tiempo real")
        return "OK Packet Tracer en Tiempo real"

    def catalog(self, args):
        return catalog.catalog_text()

    def list_devices(self, args):
        out = self._run(jsgen.list_devices())
        if not out.strip():
            return "(sin dispositivos)"
        rows = ["nombre | modelo | tipo | encendido | puertos"]
        for line in out.split("\n"):
            rows.append(" | ".join(line.split("\t")))
        return "\n".join(rows)

    def add_device(self, args):
        name = str(self._req(args, "name")).strip()
        try:
            model, dtype, verified = catalog.resolve_model(self._req(args, "model"))
        except catalog.CatalogError as exc:
            raise ToolError(str(exc))
        x, y = args.get("x"), args.get("y")
        modules = None
        spec = catalog.empty_module_spec(model)
        if spec:
            ports = args.get("ports")
            ports = spec["default"] if ports is None else ports
            if isinstance(ports, bool) or not isinstance(ports, int) or not 1 <= ports <= spec["slots"]:
                raise ToolError("'ports' debe ser un entero entre 1 y %d para %s" % (spec["slots"], model))
            modules = (spec["module"], spec["type"], ports)
        out = self._run(jsgen.add_device(name, model, dtype, x, y, dtype in catalog.BOOTING_TYPES, modules))
        if x is not None and y is not None:
            # Un equipo recien creado se recoloca solo al terminar el script que lo crea: se ajusta en otra llamada.
            self._run(jsgen.move_device(name, x, y))
        note = "" if verified else " (modelo sin verificar en 6.0.1)"
        if modules:
            note += " con %d puertos FastEthernet (modulos %s)" % (modules[2], modules[0])
        return out + note

    def remove_device(self, args):
        name = self._req(args, "name")
        n = int(self._run(jsgen.remove_device(name)))
        return "%d dispositivo(s) borrado(s) con el nombre %s" % (n, name) if n else "No existia %s" % name

    def move_device(self, args):
        return self._run(jsgen.move_device(self._req(args, "name"), self._req(args, "x"), self._req(args, "y")))

    def add_link(self, args):
        try:
            code = catalog.cable_code(args.get("cable") or "auto")
        except catalog.CatalogError as exc:
            raise ToolError(str(exc))
        d1, p1 = self._req(args, "device1"), self._req(args, "port1")
        d2, p2 = self._req(args, "device2"), self._req(args, "port2")
        out = self._run(jsgen.add_link(d1, p1, d2, p2, code))
        first, _, warn = out.strip().partition("\n")
        if first.strip().lower() != "true":
            raise ToolError("PT rechazo el cable %s %s <-> %s %s. Causas habituales: puerto ya ocupado, "
                            "nombre de puerto incorrecto o tipo de cable incompatible." % (d1, p1, d2, p2))
        return "OK cable %s:%s <-> %s:%s (codigo %d)%s" % (d1, p1, d2, p2, code, ("\n" + warn) if warn else "")

    def add_note(self, args):
        text = str(self._req(args, "text"))
        size = args.get("size") or 10
        if isinstance(size, bool) or not isinstance(size, int) or not 6 <= size <= 72:
            raise ToolError("'size' debe ser un entero entre 6 y 72")
        return self._run(jsgen.add_note(self._req(args, "x"), self._req(args, "y"), text, size))

    def list_notes(self, args):
        out = self._run(jsgen.list_notes())
        if not out.strip():
            return "(sin notas)"
        return "\n".join(["id | x | y"] + [" | ".join(line.split("\t")) for line in out.split("\n")])

    def remove_note(self, args):
        nid = self._req(args, "id")
        if self._run(jsgen.remove_note(nid)).strip().lower() != "true":
            raise ToolError("PT no borro la nota %s (id incorrecto?)" % nid)
        return "OK nota borrada"

    def remove_link(self, args):
        dev, port = self._req(args, "device"), self._req(args, "port")
        out = self._run(jsgen.remove_link(dev, port))
        if out.strip().lower() != "true":
            raise ToolError("PT no quito el cable de %s %s" % (dev, port))
        return "OK cable quitado de %s:%s" % (dev, port)

    def add_module(self, args):
        dev = self._req(args, "device")
        slot = self._req(args, "slot")
        if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
            raise ToolError("'slot' debe ser un entero >= 0")
        model = self._run(jsgen.wrap(jsgen.get_dev("d", dev) + " return String(d.getModel());"))
        if model not in catalog.MODULES:
            raise ToolError("Solo se anaden modulos a %s (este equipo es %s)" % (" y ".join(sorted(catalog.MODULES)), model))
        mtype, kinds = catalog.MODULES[model]
        kind = str(args.get("kind") or "fastethernet").strip().lower()
        if kind not in kinds:
            raise ToolError("kind desconocido para %s: %s. Opciones: %s" % (model, kind, ", ".join(sorted(kinds))))
        count = args.get("count", 1)
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 10:
            raise ToolError("'count' debe ser un entero entre 1 y 10")
        return self._run(jsgen.add_module(dev, slot, mtype, kinds[kind], count))

    def remove_module(self, args):
        slot = self._req(args, "slot")
        if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
            raise ToolError("'slot' debe ser un entero >= 0")
        return self._run(jsgen.remove_module(self._req(args, "device"), slot))

    def set_ip(self, args):
        dev = self._req(args, "device")
        dhcp = bool(args.get("dhcp"))
        if not dhcp:
            self._req(args, "ip")
            self._req(args, "mask")
        if args.get("dns"):
            try:
                ios.check_ip(args["dns"], "dns")
            except ios.ConfigError as exc:
                raise ToolError(str(exc))
        return self._run(jsgen.set_ip(dev, args.get("port") or "FastEthernet0", args.get("ip"),
                                      args.get("mask"), args.get("gateway"), dhcp, args.get("dns")))

    def rename_device(self, args):
        new = str(self._req(args, "new_name")).strip()
        return self._run(jsgen.rename_device(self._req(args, "name"), new))

    def _cli_interactive(self, dev, commands, wait):
        """Una linea cada vez, esperando su respuesta: para sesiones que piden datos (ftp: Username/Password, telnet...).
        Sin el Enter de 'despertar' (con el prompt vacio se tomaria como respuesta) y sin mandar la linea siguiente antes de
        que llegue su prompt (se perderia: comprobado con ftp el 2026-10-22)."""
        out = []
        for cmd in commands:
            start = int(self._run(jsgen.output_length(dev)))
            self._run(jsgen.send_only(dev, cmd))
            deadline, last, stable = time.time() + wait, None, 0
            while time.time() < deadline:
                time.sleep(0.5)
                text = self._run(jsgen.read_output(dev, start, 0))
                stable = stable + 1 if (text == last and text.strip()) else 0
                last = text
                tail = text.rstrip()
                # Terminada: 1 s sin cambios y acaba en algo con pinta de prompt (PC>, ftp>, Router#, Username:...), o 3 s
                # sin cambios aunque no lo parezca. Solo con el eco del comando (ipconfig /renew tarda) se sigue esperando.
                if (stable >= 2 and tail[-1:] in (">", "#", ":", "?")) or stable >= 6:
                    break
            out.append(last or "")
        return _clip("".join(out))

    def cli(self, args):
        commands = args.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ToolError("commands debe ser una lista no vacia de textos")
        if args.get("interactive"):
            wait = max(2, min(int(args.get("wait_seconds") or 10), 60))
            return self._cli_interactive(self._req(args, "device"), [str(c) for c in commands], wait)
        timeout = max(self.js_timeout, 10 + 1.0 * len(commands))
        out = self._run(jsgen.cli(self._req(args, "device"), [str(c) for c in commands],
                                  args.get("answer_initial_dialog", True)), timeout)
        return _clip(out)

    def running_config(self, args):
        return _clip(self._run(jsgen.running_config(self._req(args, "device"))), 20000)

    def read_output(self, args):
        tail = int(args.get("tail_chars") or 1500)
        return _clip(self._run(jsgen.read_output(self._req(args, "device"), None, tail)))

    def ping(self, args):
        dev, target = self._req(args, "device"), self._req(args, "target")
        wait = max(1, min(int(args.get("wait_seconds") or 25), 60))
        start = int(self._run(jsgen.output_length(dev)))
        self._run(jsgen.send_only(dev, "ping %s" % target))
        deadline = time.time() + wait
        out = ""
        while time.time() < deadline:
            time.sleep(1.0)
            out = self._run(jsgen.read_output(dev, start, 0))
            if "Ping statistics" in out or "Success rate" in out:
                return _clip(out)
        return _clip(out) + "\n[aviso: el ping no termino en %d s; vuelve a leer con pt_read_output]" % wait

    @staticmethod
    def _rounds(names):
        """Emparejamientos de liga (todos contra todos): en cada ronda cada equipo aparece una sola vez."""
        team = list(names) + ([None] if len(names) % 2 else [])
        n, out = len(team), []
        for _ in range(n - 1):
            pairs = [(team[i], team[n - 1 - i]) for i in range(n // 2)]
            out.append([(a, b) for a, b in pairs if a is not None and b is not None])
            team = [team[0]] + [team[-1]] + team[1:-1]
        return out

    def _ping_round(self, pairs, ips, wait):
        marks = [line.split("\t") for line in self._run(jsgen.ping_launch([(a, ips[b]) for a, b in pairs])).split("\n")]
        marks = [(m[0], int(m[1])) for m in marks]
        deadline, got = time.time() + wait, {}
        while True:
            time.sleep(1.0)
            for line in self._run(jsgen.ping_collect(marks)).split("\n"):
                name, _, val = line.partition("\t")
                got[name] = int(val)
            if all(v >= 0 for v in got.values()) or time.time() >= deadline:
                return got

    def routing_audit(self, args):
        out = self._run(jsgen.routing_audit(bool(args.get("save"))), timeout=90)
        rows = [line.split("\t") for line in out.split("\n") if line.strip()]
        nets = rows[0][1].split(",") if rows and rows[0][0] == "REDES" and len(rows[0]) > 1 and rows[0][1] else []
        if not nets or len(rows) < 2:
            return "(no hay routers con interfaces configuradas)"
        lines = ["Redes del mapa (%d): %s" % (len(nets), ", ".join(nets))]
        incomplete = 0
        for r in rows[1:]:
            name, known, total, default, saved, miss = (r + [""] * 6)[:6]
            reach = known == total or default == "si"
            if not reach:
                incomplete += 1
            txt = "  %s: conoce %s de %s redes, ruta por defecto: %s" % (name, known, total, default)
            if saved:
                txt += ", guardado: %s" % saved
            if miss:
                txt += " | no tiene ruta especifica a: %s%s" % (miss, " (las alcanza por la ruta por defecto)" if default == "si" else " -> INALCANZABLES")
            lines.append(txt)
        lines.append("Resultado: %s." % ("todos los routers alcanzan todas las redes" if not incomplete
                                         else "%d router(es) con redes inalcanzables" % incomplete))
        return "\n".join(lines)

    def ping_matrix(self, args):
        names = args.get("devices")
        if not isinstance(names, list) or len(names) < 2 or len(set(names)) != len(names):
            raise ToolError("devices debe ser una lista de al menos 2 equipos distintos (uno por red)")
        wait = max(10, min(int(args.get("wait_seconds") or 40), 120))
        ips = dict(line.split("\t") for line in self._run(jsgen.host_ips(names)).split("\n"))
        missing = [n for n in names if not ips.get(n)]
        if missing:
            raise ToolError("Sin IP o inexistentes: %s" % ", ".join(missing))
        ok, failed = [], []
        for pairs in self._rounds(names):
            got = self._ping_round(pairs, ips, wait)
            retry = [(a, b) for a, b in pairs if got.get(a, -1) <= 0]
            if retry:                                     # el primer intento se pierde a veces entero por ARP en cadena
                got.update(self._ping_round(retry, ips, wait))
            for a, b in pairs:
                (ok if got.get(a, -1) > 0 else failed).append((a, b, got.get(a, -1)))
        total = len(ok) + len(failed)
        lines = ["Conectividad todos contra todos: %d de %d parejas responden (%d equipos)." % (len(ok), total, len(names))]
        lines.append("Equipos: " + ", ".join("%s=%s" % (n, ips[n]) for n in names))
        if failed:
            lines.append("FALLAN:")
            lines += ["  %s (%s) <-> %s (%s)%s" % (a, ips[a], b, ips[b], " [sin terminar]" if r < 0 else "") for a, b, r in failed]
        else:
            lines.append("Ninguna pareja falla.")
        return "\n".join(lines)

    def traceroute(self, args):
        dev, target = self._req(args, "device"), self._req(args, "target")
        wait = max(5, min(int(args.get("wait_seconds") or 60), 120))
        start = int(self._run(jsgen.output_length(dev)))
        self._run(jsgen.send_only(dev, "tracert %s" % target))
        deadline, out = time.time() + wait, ""
        while time.time() < deadline:
            time.sleep(1.0)
            out = self._run(jsgen.read_output(dev, start, 0))
            if "Trace complete" in out:
                return _clip(out)
        return _clip(out) + "\n[aviso: la traza no termino en %d s]" % wait

    def eval(self, args):
        return _clip(self._run(self._req(args, "code")))

    # ---- herramientas de alto nivel ------------------------------------
    def list_ports(self, args):
        out = self._run(jsgen.list_ports(self._req(args, "device")))
        rows = ["puerto | estado | up"]
        rows += [" | ".join(line.split("\t")) for line in out.split("\n") if line.strip()]
        return "\n".join(rows)

    def inspect_ports(self, args):
        dev = self._req(args, "device")
        out = self._run(jsgen.inspect_ports(dev, bool(args.get("only_linked"))))
        cables = {}
        for cname, code in catalog.CABLES.items():
            cables.setdefault(str(code), cname)
        n = len(jsgen.PORT_FIELDS)
        lines, warns = [], []
        for line in out.split("\n"):
            if not line.strip():
                continue
            f = line.split("\t")
            name, v = f[0], dict(zip(jsgen.PORT_FIELDS, f[1:n + 1]))
            link = f[n + 1:n + 4] if len(f) >= n + 4 else None
            parts = ["encendido" if v["getPower"] == "true" else "APAGADO",
                     "linea %s / protocolo %s" % ("arriba" if v["isPortUp"] == "true" else "abajo",
                                                  "arriba" if v["isProtocolUp"] == "true" else "abajo"),
                     "luz %s" % LIGHTS.get(v["getLightStatus"], v["getLightStatus"] or "-")]
            if v["getIpAddress"] and v["getIpAddress"] != "0.0.0.0":
                parts.append("ip %s/%s%s" % (v["getIpAddress"], v["getSubnetMask"], " (DHCP)" if v["isDhcpClientOn"] == "true" else ""))
            elif v["isDhcpClientOn"] == "true":
                parts.append("ip por DHCP (sin direccion)")
            if v["getMacAddress"]:
                parts.append("mac %s" % v["getMacAddress"])
            if v["getBandwidth"] not in ("", "0"):
                parts.append("%s kbps%s" % (v["getBandwidth"], " auto" if v["isBandwidthAutoNegotiate"] == "true" else ""))
            if v["isFullDuplex"] and v["isPortUp"] == "true":         # caido, el duplex no esta negociado
                parts.append("%s duplex%s" % ("full" if v["isFullDuplex"] == "true" else "half",
                                              " auto" if v["isDuplexAutoNegotiate"] == "true" else ""))
            if v["getMtu"]:
                parts.append("mtu %s" % v["getMtu"])
            if v["getDelay"]:
                parts.append("delay %s" % v["getDelay"])
            if v["getAdminOpMode"]:
                mode = SWITCH_MODES.get(v["getAdminOpMode"], v["getAdminOpMode"])
                parts.append(("modo trunk (nativa %s)" % v["getNativeVlanId"]) if mode == "trunk"
                             else "modo %s, vlan %s" % (mode, v["getAccessVlan"]))
            if v["isCdpEnable"] == "false":
                parts.append("sin CDP")
            if v["getNatMode"] not in ("", "0"):
                parts.append("nat %s" % v["getNatMode"])
            if v["getAclInID"] or v["getAclOutID"]:
                parts.append("acl in=%s out=%s" % (v["getAclInID"] or "-", v["getAclOutID"] or "-"))
            if v["getDescription"]:
                parts.append('descripcion "%s"' % v["getDescription"])
            if link:
                parts.append("cable %s -> %s:%s" % (cables.get(link[0], link[0]), link[1], link[2]))
                if v["getPower"] == "false":
                    warns.append("%s: tiene cable pero el puerto esta APAGADO (en un router: falta 'no shutdown')" % name)
                elif v["isPortUp"] != "true":
                    warns.append("%s: tiene cable pero la linea esta caida (el otro extremo %s:%s apagado o sin senal)"
                                 % (name, link[1], link[2]))
                elif v["isProtocolUp"] != "true":
                    warns.append("%s: linea arriba pero protocolo caido" % name)
            else:
                parts.append("sin cable")
            lines.append("%s: %s" % (name, ", ".join(parts)))
        if not lines:
            return "(%s no tiene puertos%s)" % (dev, " con cable" if args.get("only_linked") else "")
        lines.append("AVISOS:" if warns else "Sin anomalias.")
        lines += ["  " + w for w in warns]
        return _clip("\n".join(lines), 20000)

    @staticmethod
    def _port_ops(args):
        """Setters de API de pt_set_port: [(setter, getter, literal_js)], en el orden en que se aplican."""
        ops = []
        if args.get("description") is not None:
            ops.append(("setDescription", "getDescription", jsgen.q(args["description"])))
        for key, setter, getter in (("power", "setPower", "getPower"), ("cdp", "setCdpEnable", "isCdpEnable"),
                                    ("proxy_arp", "setProxyArpEnabled", "isProxyArpEnabled")):
            if args.get(key) is not None:
                if not isinstance(args[key], bool):
                    raise ToolError("'%s' debe ser true o false" % key)
                ops.append((setter, getter, "true" if args[key] else "false"))
        speed = args.get("speed")
        if speed is not None:
            speed = str(speed).strip().lower()
            if speed == "auto":
                ops.append(("setBandwidthAutoNegotiate", "isBandwidthAutoNegotiate", "true"))
            elif speed in ("10", "100", "1000"):
                # setBandwidth es la velocidad fisica en kbps (sale como 'speed N' en el running-config).
                ops += [("setBandwidthAutoNegotiate", "isBandwidthAutoNegotiate", "false"),
                        ("setBandwidth", "getBandwidth", str(int(speed) * 1000))]
            else:
                raise ToolError("speed debe ser auto, 10, 100 o 1000")
        duplex = args.get("duplex")
        if duplex is not None:
            duplex = str(duplex).strip().lower()
            if duplex == "auto":
                ops.append(("setDuplexAutoNegotiate", "isDuplexAutoNegotiate", "true"))
            elif duplex in ("full", "half"):
                ops += [("setDuplexAutoNegotiate", "isDuplexAutoNegotiate", "false"),
                        ("setFullDuplex", "isFullDuplex", "true" if duplex == "full" else "false")]
            else:
                raise ToolError("duplex debe ser auto, full o half")
        if args.get("mtu") is not None:
            mtu = args["mtu"]
            if isinstance(mtu, bool) or not isinstance(mtu, int) or not 64 <= mtu <= 9216:
                raise ToolError("mtu debe ser un entero entre 64 y 9216")
            ops.append(("setMtu", "getMtu", str(mtu)))
        if args.get("mac"):
            try:
                ops.append(("setMacAddress", "getMacAddress", jsgen.q(ios.check_mac(args["mac"]))))
            except ios.ConfigError as exc:
                raise ToolError(str(exc))
        return ops

    def set_port(self, args):
        dev, port = self._req(args, "device"), str(self._req(args, "port")).strip()
        ops = self._port_ops(args)
        try:
            cmds = ios.port_config(port, args)
        except (ios.ConfigError, ValueError, TypeError) as exc:
            raise ToolError("valor invalido: %s" % exc)
        if not ops and not cmds:
            raise ToolError("No hay nada que cambiar: pasa al menos un campo (description, power, speed, mode, vlan...)")
        if args.get("save"):
            cmds = (cmds[:-1] + ["end"] if cmds else ["enable"]) + ["write memory"]
        if args.get("dry_run"):
            lines = ["Plan para %s %s:" % (dev, port)]
            lines += ["  API %s(%s)" % (s, lit) for s, _g, lit in ops]
            lines += ["  IOS %s" % c for c in cmds]
            return "\n".join(lines)
        out = []
        if ops:
            for line in self._run(jsgen.set_port(dev, port, ops)).split("\n"):
                setter, _, value = line.partition("\t")
                out.append("  %s -> %s" % (setter, value))
        if cmds:
            res = self.cli({"device": dev, "commands": cmds})
            bad = [ln for ln in str(res).splitlines() if "% Invalid" in ln or "% Incomplete" in ln or "% Ambiguous" in ln]
            out.append("  IOS: %d comandos%s" % (len(cmds), (" | RECHAZADOS: " + " / ".join(bad)) if bad else " aceptados"))
        return "OK %s %s\n%s" % (dev, port, "\n".join(out))

    def _map_png(self):
        out = self._run(jsgen.workspace_image("PNG"), timeout=60)
        try:
            data = base64.b64decode(out.strip(), validate=True)
        except (binascii.Error, ValueError):
            raise ToolError("PT devolvio una imagen que no es base64 valido (%d caracteres)" % len(out))
        if not data.startswith(PNG_SIGNATURE):
            raise ToolError("PT no devolvio un PNG (firma incorrecta)")
        return data

    @staticmethod
    def _save_png(data, filename, default):
        os.makedirs(CAPTURES_DIR, exist_ok=True)
        path = os.path.join(CAPTURES_DIR, _safe_filename(filename, default + "-" + time.strftime("%Y%m%d-%H%M%S")))
        with open(path, "wb") as fh:
            fh.write(data)
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        return "%s (%dx%d, %d KB)" % (path, width, height, max(1, len(data) // 1024))

    def screenshot(self, args):
        data = self._map_png()
        return Rich("OK mapa guardado en %s" % self._save_png(data, args.get("filename"), "mapa"), [data])

    # ---- ventanas de los equipos (bloque 2 de PRUEBAS_EN_CLASE.md) -------
    def _ui(self, fn, *a):
        try:
            return getattr(self.ui, fn)(*a)
        except winui.WinUiError as exc:
            raise ToolError(str(exc))

    def _wait_window(self, name, seconds=3.0):
        deadline = time.time() + seconds
        while True:
            hwnd, visible = self._ui("device_window", name)
            if hwnd and visible:
                return hwnd
            if time.time() >= deadline:
                return None
            time.sleep(0.25)

    def _canvas_offset(self, refs):
        """Desfase entre el PNG del mapa y la captura de la ventana principal (el lienzo puede estar desplazado).
        refs = [(x, y)] puntos logicos de equipos: se prueba un trozo de 12x12 en cada icono hasta que uno aparezca UNA vez."""
        _mw, _mh, mrows = self._ui("decode_png", self._map_png())
        main, _pid = self._ui("main_window")
        _w, _h, wrows = self._ui("capture", main, True)      # entera: los clics se miden desde la esquina de GetWindowRect
        for x, y in refs:
            sx, sy = int(x) + UI_ICON_DX - 6, int(y) - 6
            if sx < 0 or sy < 0 or sy + 12 > len(mrows) or (sx + 12) * 3 > len(mrows[0]):
                continue
            if not self.ui.distinctive(mrows, sx, sy):
                continue
            hits = self.ui.locate(wrows, mrows, sx, sy)
            if len(hits) == 1:
                return main, hits[0]
        raise ToolError("No encuentro el mapa dentro de la ventana de Packet Tracer. Pon el zoom al 100 %% y desplaza el mapa "
                        "para que se vea el equipo (o algun otro) y vuelve a probar.")

    def _open_by_click(self, name, x, y, refs):
        main, (dx, dy) = self._canvas_offset([(x, y)] + [r for r in refs if r != (x, y)])
        for ox, oy in ((UI_ICON_DX, 0), (25, 0), (5, 0), (UI_ICON_DX, -10)):
            self._ui("key", main, winui.VK_ESCAPE)              # herramienta Select: un clic con Delete activa borraria el equipo
            self._ui("click", main, x + ox + dx, y + oy + dy)
            for _ in range(8):
                time.sleep(0.25)
                if self._run(jsgen.ui_info(name)).startswith("si"):
                    return
        raise ToolError("Hice clic sobre %s y no se abrio su ventana. Comprueba que se ve en pantalla (zoom 100 %%) y que la "
                        "herramienta Select esta activa." % name)

    def _open_window(self, name):
        lines = self._run(jsgen.ui_info(name)).split("\n")
        head = lines[0].split("\t")
        exists, dtype = head[0] == "si", int(head[1])
        x, y = float(head[2]), float(head[3])
        ports = [p for p in head[4].split(",") if p] if len(head) > 4 else []
        if exists:
            self._run(jsgen.dialog_visible(name, True))
        else:
            refs = [(float(f[2]), float(f[3])) for f in (ln.split("\t") for ln in lines[1:]) if len(f) >= 4 and f[0] == "D"]
            self._open_by_click(name, x, y, refs)
        hwnd = self._wait_window(name)
        if not hwnd:
            raise ToolError("La ventana de %s no aparece" % name)
        return hwnd, dtype, ports

    @staticmethod
    def _section_row(dtype, ports, section):
        names = list(UI_SECTIONS[dtype]) + [p for p in ports if not p.startswith("Vlan")]
        wanted = section.strip().lower()
        for i, n in enumerate(names):
            if n.lower() == wanted:
                if i >= UI_SECTION_ROWS:
                    raise ToolError("La seccion %s queda fuera de la lista visible (habria que desplazarla)" % n)
                return n, UI_SECTION_Y0 + UI_SECTION_DY * i
        raise ToolError("Seccion desconocida para este equipo: %s. Opciones: %s" % (section, ", ".join(names)))

    def ui_open(self, args):
        name = str(self._req(args, "device")).strip()
        tab = str(args.get("tab") or "").strip().lower()
        section, app = args.get("section"), args.get("app")
        if (section or app) and not tab:
            tab = "desktop" if app else "config"
        hwnd, dtype, ports = self._open_window(name)
        if dtype not in UI_TABS_BY_TYPE and (tab or section or app):
            raise ToolError("Todavia no se el formato de la ventana de este tipo de equipo (%s): solo se puede abrir y capturar" % dtype)
        done = ["ventana de %s abierta" % name]
        if tab:
            if tab not in UI_TABS_BY_TYPE[dtype]:
                raise ToolError("Un %s no tiene la pestana %s. Opciones: %s" % (UI_DEVICE_TYPES[dtype], tab, ", ".join(UI_TABS_BY_TYPE[dtype])))
            self._ui("click", hwnd, UI_TABS[tab], UI_TAB_Y)
            time.sleep(0.4)
            done.append("pestana %s" % tab)
        if section:
            if tab != "config":
                raise ToolError("Las secciones (section) son de la pestana config")
            label, row_y = self._section_row(dtype, ports, str(section))
            self._ui("click", hwnd, UI_SECTION_X, row_y)
            time.sleep(0.4)
            done.append("seccion %s" % label)
        if app:
            if tab != "desktop" or dtype not in UI_DESKTOP:
                raise ToolError("Las aplicaciones (app) solo estan medidas en el Desktop de un PC y de un servidor")
            apps = UI_DESKTOP[dtype]
            pos = apps.get(str(app).strip().lower())
            if not pos:
                raise ToolError("Aplicacion desconocida en un %s: %s. Opciones: %s" % (UI_DEVICE_TYPES[dtype], app, ", ".join(sorted(apps))))
            # Si ya hay otra aplicacion abierta tapa los iconos: se cierra con su X (cada una la tiene en otro sitio).
            self._close_desktop_app(hwnd)
            self._ui("click", hwnd, pos[0], pos[1])
            time.sleep(0.6)
            done.append("aplicacion %s" % app)
            result = self._capture_window(hwnd, args.get("filename"), name, "OK " + ", ".join(done))
            # Y se cierra al terminar: una aplicacion abierta guarda los valores que ensena y, al cerrarla mas tarde, los
            # ESCRIBE en el equipo, pisando lo que haya cambiado el MCP entretanto (comprobado con el gateway, 2026-10-22).
            self._close_desktop_app(hwnd)
            result.text += " (aplicacion cerrada despues de la captura)"
            return result
        return self._capture_window(hwnd, args.get("filename"), name, "OK " + ", ".join(done))

    def _close_desktop_app(self, hwnd):
        _w, _h, rows = self._ui("capture", hwnd, True)
        close = self.ui.desktop_app_close(rows)
        if close:
            self._ui("click", hwnd, close[0], close[1])
            time.sleep(0.4)
        return bool(close)

    def _capture_window(self, hwnd, filename, default, prefix):
        w, h, rows = self._ui("capture", hwnd)
        data = self._ui("encode_png", w, h, rows)
        return Rich("%s. Captura: %s" % (prefix, self._save_png(data, filename, _safe_filename(default, "ventana")[:-4])), [data])

    def ui_capture(self, args):
        name = str(args.get("device") or "").strip()
        if name:
            hwnd, visible = self._ui("device_window", name)
            if not hwnd or not visible:
                raise ToolError("La ventana de %s no esta abierta: usa pt_ui_open" % name)
            return self._capture_window(hwnd, args.get("filename"), name, "OK ventana de %s" % name)
        main, _pid = self._ui("main_window")
        return self._capture_window(main, args.get("filename"), "packet-tracer", "OK ventana principal")

    def ui_close(self, args):
        name = str(args.get("device") or "").strip()
        names = [name] if name else [n for n in self._run(jsgen.open_dialogs()).split(",") if n]
        hidden, apps = [], []
        for n in names:
            hwnd, visible = self._ui("device_window", n)
            if hwnd and visible and self._close_desktop_app(hwnd):     # antes de ocultar: si no, guardaria valores viejos
                apps.append(n)
            if self._run(jsgen.dialog_visible(n, False)).strip() == "si":
                hidden.append(n)
        if not hidden:
            return "La ventana de %s no estaba abierta" % name if name else "OK ninguna ventana estaba abierta"
        extra = (" (cerrada la aplicacion del Desktop de %s)" % ", ".join(apps)) if apps else ""
        return "OK ocultas: %s%s. pt_ui_open las vuelve a ensenar." % (", ".join(hidden), extra)

    def connect(self, args):
        try:
            code = catalog.cable_code(args.get("cable") or "auto")
        except catalog.CatalogError as exc:
            raise ToolError(str(exc))
        p1, p2 = args.get("port1") or "", args.get("port2") or ""
        if code not in (8100, 8101, 8107, 8103) and not (p1 and p2):
            raise ToolError("Para ese tipo de cable indica port1 y port2 explicitamente")
        return self._run(jsgen.connect_auto(self._req(args, "device1"), self._req(args, "device2"), code, p1, p2))

    def _send_config(self, device, commands, save=False):
        commands = list(commands)
        if save:
            commands = commands[:-1] + ["end", "write memory"] if commands and commands[-1] == "end" else commands + ["write memory"]
        return self.cli({"device": device, "commands": commands})

    def config(self, args):
        device = self._req(args, "device")
        skip = ("enable", "configure terminal", "conf t", "end")
        lines = [ln.strip() for ln in str(self._req(args, "config")).splitlines()
                 if ln.strip() and ln.strip().lower() not in skip]
        return self._send_config(device, ["enable", "configure terminal"] + lines + ["end"], bool(args.get("save")))

    def router_config(self, args):
        try:
            cmds = ios.router_config(args.get("spec") or {})
        except (ios.ConfigError, KeyError, ValueError) as exc:
            raise ToolError("spec invalida: %s" % exc)
        return self._send_config(self._req(args, "device"), cmds, bool(args.get("save")))

    def vpn_ipsec(self, args):
        try:
            cmds = ios.ipsec_vpn(args.get("spec") or {})
        except (ios.ConfigError, KeyError, ValueError) as exc:
            raise ToolError("spec invalida: %s" % exc)
        dev = self._req(args, "device")
        return self._send_config(dev, ["enable", "configure terminal"] + cmds + ["end"], bool(args.get("save")))

    def switch_config(self, args):
        try:
            cmds = ios.switch_config(args.get("spec") or {})
        except (ios.ConfigError, KeyError, ValueError) as exc:
            raise ToolError("spec invalida: %s" % exc)
        return self._send_config(self._req(args, "device"), cmds, bool(args.get("save")))

    def dhcp_server(self, args):
        try:
            start, mask = ios.check_ip(self._req(args, "start_ip"), "start_ip"), ios.check_mask(self._req(args, "mask"))
            gw = ios.check_ip(args["gateway"], "gateway") if args.get("gateway") else ""
            dns = ios.check_ip(args["dns"], "dns") if args.get("dns") else ""
            tftp = ios.check_ip(args["tftp"], "tftp") if args.get("tftp") else ""
        except ios.ConfigError as exc:
            raise ToolError(str(exc))
        # La 6.0.1 no tiene "maximo de usuarios": el pool se define por IP inicial y final. tftp no se puede fijar por IPC.
        # pool: por defecto el de fabrica (serverPool); con otro nombre se crea un pool nuevo (addPool).
        pool = str(args.get("pool") or "serverPool").strip()
        if not re.match(r"^[A-Za-z0-9_-]{1,32}$", pool):
            raise ToolError("pool invalido: %r (letras, numeros, - y _)" % pool)
        try:
            users = int(args.get("max_users") or 50)
            net = ipaddress.ip_network("%s/%s" % (start, mask), strict=False)
            end = ipaddress.ip_address(int(ipaddress.ip_address(start)) + users - 1)
        except ValueError as exc:
            raise ToolError("max_users o rango invalido: %s" % exc)
        if users < 1 or end not in net:
            raise ToolError("El rango %s + %d usuarios se sale de la red %s" % (start, users, net))
        return self._run(jsgen.dhcp_server(self._req(args, "device"), gw, dns, start, str(end), mask,
                                           str(net.network_address), pool))

    @staticmethod
    def _ranges(items, what):
        out = []
        for r in items or []:
            if not isinstance(r, dict):
                raise ToolError("%s: cada rango es {start, end}" % what)
            try:
                a = ios.check_ip(r.get("start"), "%s.start" % what)
                b = ios.check_ip(r.get("end") or r.get("start"), "%s.end" % what)
            except ios.ConfigError as exc:
                raise ToolError(str(exc))
            if int(ipaddress.ip_address(a)) > int(ipaddress.ip_address(b)):
                raise ToolError("%s: el inicio %s es mayor que el final %s" % (what, a, b))
            out.append((a, b))
        return out

    def dhcp_admin(self, args):
        pools = [str(p).strip() for p in args.get("remove_pools") or []]
        for p in pools:
            if p.lower() == "serverpool":
                raise ToolError("serverPool es el pool de fabrica y no se puede quitar (tampoco desde la ventana)")
            if not re.match(r"^[A-Za-z0-9_-]{1,32}$", p):
                raise ToolError("nombre de pool invalido: %r" % p)
        exclude, unexclude = self._ranges(args.get("exclude"), "exclude"), self._ranges(args.get("unexclude"), "unexclude")
        out = self._run(jsgen.dhcp_admin(self._req(args, "device"), pools, exclude, unexclude))
        lines = []
        for row in out.split("\n"):
            f = row.split("\t")
            if f[0] in ("pool", "exclusion") and len(f) == 3:
                lines.append("  %s %s: %s" % (f[0], f[1], f[2]))
            elif f[0] == "POOLS":
                lines.append("Pools: %s" % (f[1] or "ninguno"))
            elif f[0] == "EXCLUSIONES":
                lines.append("Exclusiones: %s" % (f[1] or "ninguna"))
        if exclude or "Exclusiones: ninguna" not in lines:
            lines.append("AVISO: en la 6.0.1 las exclusiones del servidor funcionan, pero no se ven en Config > DHCP ni se guardan "
                         "en el .pkt. Para algo visible: empieza el pool despues de las IP fijas, o usa un router "
                         "(ip dhcp excluded-address).")
        return "\n".join(lines)

    def dns_server(self, args):
        records = args.get("records")
        if not isinstance(records, list) or not records:
            raise ToolError("records debe ser una lista [{name, ip}]")
        try:
            clean = [{"name": str(r["name"]).strip(), "ip": ios.check_ip(r["ip"], "registro %s" % r.get("name"))} for r in records]
        except (KeyError, ios.ConfigError) as exc:
            raise ToolError("registro invalido: %s" % exc)
        return self._run(jsgen.dns_server(self._req(args, "device"), clean))

    def server_read(self, args):
        name = self._req(args, "device")
        xml = self._run(jsgen.server_xml(name))
        sec = {}
        for tag in jsgen.SERVER_XML_SECTIONS:
            m = re.search(r"<%s>.*?</%s>" % (tag, tag), xml, re.S)
            if m:
                try:
                    sec[tag] = ET.fromstring(m.group(0))
                except ET.ParseError:
                    pass

        def val(node, path, default=""):
            found = node.find(path) if node is not None else None
            return (found.text or "").strip() if found is not None and found.text else default

        def onoff(node, path="ENABLED"):
            return "encendido" if val(node, path) == "1" else "apagado"
        lines = ["Servicios de %s:" % name]
        http = sec.get("HTTP_SERVER")
        if http is not None:
            extra = (" (usuario %s)" % val(http, "USERNAME")) if val(http, "USERNAME") else ""
            lines.append("HTTP: %s%s" % (onoff(http), extra))
        if sec.get("HTTPS_SERVER") is not None:
            lines.append("HTTPS: %s" % onoff(sec["HTTPS_SERVER"], "HTTPSENABLED"))
        dns = sec.get("DNS_SERVER")
        if dns is not None:
            recs = dns.findall("./NAMESERVER-DATABASE/RESOURCE-RECORD")
            lines.append("DNS: %s, %d registro(s)" % (onoff(dns), len(recs)))
            for r in recs:
                fields = ["%s=%s" % (c.tag.lower(), (c.text or "").strip()) for c in r if c.tag not in ("TYPE", "NAME")]
                lines.append("  %s %s %s" % (val(r, "NAME"), val(r, "TYPE"), " ".join(fields)))
        dhcp = sec.get("DHCP_SERVER")
        if dhcp is not None:
            pools = dhcp.findall("./POOLS/POOL")
            lines.append("DHCP: %s, %d pool(s)" % (onoff(dhcp), len(pools)))
            for p in pools:
                lines.append("  %s: %s - %s mascara %s gateway %s dns %s max %s" % (
                    val(p, "NAME"), val(p, "START_IP"), val(p, "END_IP"), val(p, "MASK"), val(p, "DEFAULT_ROUTER"),
                    val(p, "DNS_SERVER"), val(p, "MAX_USERS")))
        if sec.get("TFTP_SERVER") is not None:
            lines.append("TFTP: %s" % onoff(sec["TFTP_SERVER"]))
        ftp = sec.get("FTP_SERVER")
        if ftp is not None:
            accs = ftp.findall("./USER_ACCOUNT_MNGR/ACCOUNT")
            lines.append("FTP: %s, cuentas: %s" % (onoff(ftp), ", ".join(
                "%s/%s (%s)" % (val(a, "USERNAME"), val(a, "PASSWORD"), val(a, "PERMISSIONS")) for a in accs) or "ninguna"))
        ntp = sec.get("NTP_SERVER")
        if ntp is not None:
            auth = val(ntp, "ENABLED_SERVER_AUTHENTICATE") == "1"
            lines.append("NTP: %s, autenticacion %s" % (onoff(ntp), ("si (clave %s)" % val(ntp, "KEY")) if auth else "no"))
        if sec.get("SYSLOG_SERVER") is not None:
            entries = [c for c in sec["SYSLOG_SERVER"] if c.tag != "ENABLED"]
            lines.append("SYSLOG: %s%s" % (onoff(sec["SYSLOG_SERVER"]), (", %d entrada(s)" % len(entries)) if entries else ""))
        acs = sec.get("ACS_SERVER")
        if acs is not None:
            lines.append("AAA: %s, %d usuario(s), %d cliente(s)" % (onoff(acs), len(acs.findall("./USERS/*")),
                                                                     len(acs.findall("./ACS_CLIENTS/*"))))
        mail = sec.get("EMAIL_SERVER")
        if mail is not None:
            n = int(val(mail, "NO_OF_USERS", "0") or 0)
            users = ["%s/%s" % (val(mail, "USER%d" % i), val(mail, "PASSWORD%d" % i)) for i in range(n)]
            lines.append("EMAIL: SMTP %s, POP3 %s, dominio %s, cuentas: %s" % (
                onoff(mail, "SMTP_ENABLED"), onoff(mail, "POP3_ENABLED"), val(mail, "SMTP_DOMAIN") or "(sin dominio)",
                ", ".join(users) or "ninguna"))
        return "\n".join(lines)

    @staticmethod
    def _accounts(users, what):
        if not isinstance(users, list) or not users:
            raise ToolError("users debe ser una lista de cuentas [{name, password}]")
        out = []
        for u in users:
            if not isinstance(u, dict):
                raise ToolError("cada cuenta de %s es un objeto {name, password}" % what)
            name, pwd = str(u.get("name") or "").strip(), str(u.get("password") or "").strip()
            if not name or not pwd or any(c.isspace() for c in name + pwd):
                raise ToolError("cuenta de %s invalida: hace falta name y password, sin espacios (%r)" % (what, u))
            out.append((name, pwd, u))
        return out

    @staticmethod
    def _names(value, what):
        names = [str(n).strip() for n in (value or [])]
        if not isinstance(value or [], list) or any(not n or any(c.isspace() for c in n) for n in names):
            raise ToolError("remove debe ser una lista de nombres de cuenta %s, sin espacios" % what)
        return names

    def server_ftp(self, args):
        rows = []
        remove = self._names(args.get("remove"), "FTP")
        accounts = self._accounts(args.get("users"), "FTP") if (args.get("users") or not remove) else []
        for name, pwd, u in accounts:
            perms = str(u.get("permissions") or "RWDNL").strip().upper()
            if not perms or any(c not in "RWDNL" for c in perms) or len(set(perms)) != len(perms):
                raise ToolError("permissions invalidos para %s: %r (letras R W D N L, sin repetir)" % (name, perms))
            rows.append((name, pwd, "".join(c for c in "RWDNL" if c in perms)))       # en el orden de PT
        out = self._run(jsgen.ftp_users(self._req(args, "device"), rows, remove))
        return "FTP:\n" + "\n".join("  %s: %s" % tuple(line.split("\t", 1)) for line in out.split("\n") if "\t" in line)

    def server_email(self, args):
        domain = str(args.get("domain") or "").strip()
        if domain and (" " in domain or "." not in domain):
            raise ToolError("domain invalido: %r (ej. barriosmadrid.es)" % domain)
        users = [(n, p) for n, p, _u in self._accounts(args["users"], "correo")] if args.get("users") else []
        remove = self._names(args.get("remove"), "de correo")
        if not domain and not users and not remove:
            raise ToolError("Pasa domain, users, remove o varios")
        out = self._run(jsgen.email_setup(self._req(args, "device"), domain, users, remove))
        return "Correo:\n" + "\n".join("  %s: %s" % tuple(line.split("\t", 1)) for line in out.split("\n") if "\t" in line)

    def server_services(self, args):
        services = args.get("services")
        if not isinstance(services, list):
            raise ToolError("services debe ser una lista (vacia = apagar todos)")
        known = [k for k, _p, _s, _g in jsgen.SERVER_SERVICES]
        wanted = set()
        for s in services:
            key = str(s).strip().lower()
            if key == "email":
                wanted.update(("smtp", "pop3"))
            elif key in known:
                wanted.add(key)
            else:
                raise ToolError("Servicio desconocido: %s. Validos: %s, email" % (s, ", ".join(known)))
        return self._run(jsgen.server_services(self._req(args, "device"), wanted))

    def snapshot(self, args):
        out = self._run(jsgen.snapshot())
        if not out.strip():
            return "(sin dispositivos)"
        cables = {}
        for cname, code in catalog.CABLES.items():
            cables.setdefault(str(code), cname)
        rows = []
        for line in out.split("\n"):
            f = line.split("\t")
            if f[0] == "D":
                rows.append("%s | %s | tipo %s | x=%s y=%s" % tuple(f[1:6]))
            elif f[0] == "P":
                txt = "    %s" % f[1]
                if f[2] and f[2] != "0.0.0.0":
                    txt += " ip=%s/%s %s" % (f[2], f[3], "DHCP" if f[4] == "true" else "estatica")
                if len(f) >= 8 and f[5] == "wifi":
                    txt += " (inalambrico)"
                elif len(f) >= 8:
                    txt += " --%s--> %s:%s" % (cables.get(f[5], f[5]), f[6], f[7])
                rows.append(txt)
            elif f[0] == "G":
                if not f[1] and (len(f) < 3 or f[2] in ("", "0.0.0.0")):
                    continue                              # switches: tienen DnsClient pero sin gateway ni DNS
                rows.append("    gateway=%s dns=%s" % (f[1] or "-", f[2] if len(f) > 2 and f[2] and f[2] != "0.0.0.0" else "-"))
            elif f[0] == "S":
                rows.append("    servicios: %s" % f[1])
            elif f[0] == "L":
                rows.append("    pool %s: %s - %s mascara %s router %s dns %s" % tuple(f[1:7]))
        return _clip("\n".join(rows), 60000)

    def describe(self, args):
        return _clip(self._run(jsgen.describe(self._req(args, "device"), args.get("process") or "", args.get("port") or "")))

    def class_plan(self, args):
        try:
            plan = planmod.class_plan(args.get("spec"))
        except (planmod.PlanError, KeyError, ValueError, TypeError) as exc:
            raise ToolError("spec invalida: %s" % exc)
        if args.get("build"):
            return self.build_topology({"plan": plan})
        hosts = plan["hosts"]
        lines = ["Plan de clase: %d dispositivos, %d cables, equipos %s-%s." %
                 (len(plan["devices"]), len(plan["links"]), hosts[0]["device"], hosts[-1]["device"])]
        for d in plan["devices"]:
            extra = (" (%d puertos)" % d["ports"]) if d.get("ports") else ""
            lines.append("  %s | %s | x=%d y=%d%s" % (d["name"], d["model"], d["x"], d["y"], extra))
        for l in plan["links"]:
            lines.append("  %s:%s --%s--> %s:%s" % (l["a"], l["port_a"], l["cable"], l["b"], l["port_b"]))
        lines.append("JSON del plan (para pt_build_topology):")
        lines.append(json.dumps(plan, ensure_ascii=False))
        return _clip("\n".join(lines), 60000)

    def routed_plan(self, args):
        try:
            plan = planmod.routed_plan(args.get("spec"))
        except (planmod.PlanError, KeyError, ValueError, TypeError) as exc:
            raise ToolError("spec invalida: %s" % exc)
        if args.get("build"):
            return self.build_topology({"plan": plan})
        lines = ["Plan con routers: %d dispositivos, %d cables." % (len(plan["devices"]), len(plan["links"]))]
        for r in plan["routers"]:
            lines.append("  %s: %s" % (r["device"], ", ".join("%s=%s" % (i["port"], i["ip"]) for i in r["interfaces"])))
        lines.append("  equipos: " + ", ".join("%s(%s)" % (h["device"], h.get("ip") or h.get("expect_ip") or "dhcp")
                                               for h in plan["hosts"]))
        lines.append("JSON del plan (para pt_build_topology):")
        lines.append(json.dumps(plan, ensure_ascii=False))
        return _clip("\n".join(lines), 60000)

    def http_get(self, args):
        dev, url = self._req(args, "device"), str(self._req(args, "url")).strip()
        if "://" not in url:
            url = "http://" + url
        wait = max(1, min(int(args.get("wait_seconds") or 15), 60))
        if self._run(jsgen.http_get(dev, url)).strip().lower() != "true":
            raise ToolError("El navegador de %s no acepto la URL %s" % (dev, url))
        deadline = time.time() + wait
        while True:
            time.sleep(1.0)
            out = self._run(jsgen.http_last(dev))
            head, _, body = out.partition("\n")
            if head != "LEN=0":
                return _clip("OK %s desde %s (%s caracteres):\n%s" % (url, dev, head[4:], body))
            if time.time() >= deadline:
                raise ToolError("Sin respuesta de %s desde %s en %d s (servidor apagado, sin ruta, HTTP desactivado "
                                "o el nombre no se resuelve por DNS)." % (url, dev, wait))

    def _dhcp_in_order(self, device, port, wait=75):
        """Activa DHCP y espera a que el equipo tenga IP antes de seguir (asi el orden de peticion = orden de IPs)."""
        self._run(jsgen.set_ip(device, port, None, None, None, True))
        self._run(jsgen.send_only(device, "ipconfig /renew"))
        deadline, last_renew = time.time() + wait, time.time()
        while True:
            ip = self._run(jsgen.port_ip(device, port)).strip()
            if ip not in ("", "0.0.0.0"):
                return ip
            if time.time() >= deadline:
                # Se le quita el DHCP: si se quedara pidiendo, cogeria mas tarde la IP que le toca al siguiente.
                self._run(jsgen.dhcp_off(device, port))
                raise ToolError("%s no recibio IP por DHCP en %d s (se le ha desactivado el DHCP)" % (device, wait))
            time.sleep(1.0)
            if time.time() - last_renew > 8:              # el primer intento falla si el puerto del switch aun no reenvia
                self._run(jsgen.send_only(device, "ipconfig /renew"))
                last_renew = time.time()

    def clear_workspace(self, args):
        if args.get("confirm") is not True:
            raise ToolError("Operacion destructiva: vuelve a llamar con confirm=true")
        return self._run(jsgen.clear_workspace())

    # ---- constructor de topologias -------------------------------------
    def build_topology(self, args):
        plan = args.get("plan")
        if isinstance(plan, str):
            try:
                plan = json.loads(plan)
            except ValueError as exc:
                raise ToolError("El plan no es JSON valido: %s" % exc)
        errors = planmod.validate_plan(plan)
        if errors:
            raise ToolError("Plan invalido:\n- " + "\n- ".join(errors))
        devices = [dict(d) for d in plan["devices"]]
        positions = planmod.auto_layout(devices, plan.get("links", []))
        for d in devices:
            if d.get("x") is None or d.get("y") is None:
                d["x"], d["y"] = positions[d["name"]]
        if args.get("dry_run"):
            return ("Plan valido: %d dispositivos, %d enlaces, %d hosts, %d servidores, %d routers, %d switches.\n"
                    "Posiciones: %s" % (len(devices), len(plan.get("links", [])), len(plan.get("hosts", [])),
                                        len(plan.get("servers", [])), len(plan.get("routers", [])),
                                        len(plan.get("switches", [])),
                                        ", ".join("%s(%d,%d)" % (d["name"], d["x"], d["y"]) for d in devices)))
        # Antes de crear nada: si algun nombre del plan ya existe en el archivo se aborta. Si no, los equipos no se
        # crean y los pasos siguientes (cables, IP, DHCP) acabarian actuando sobre los equipos antiguos del mismo nombre.
        existing = set(line.split("\t")[0] for line in self._run(jsgen.list_devices()).split("\n") if line.strip())
        clash = sorted(d["name"] for d in devices if d["name"] in existing)
        if clash:
            raise ToolError("Ya existen en el archivo equipos con estos nombres: %s. No se ha creado nada. Cambia los nombres del plan "
                            "(en pt_routed_plan usa host_names='site' u otro lan_block) o borra los antiguos." % ", ".join(clash))
        report, ok, bad = [], [0], [0]

        def step(label, fn):
            try:
                detail = fn()
                ok[0] += 1
                first = str(detail).strip().splitlines()[0] if str(detail).strip() else ""
                report.append("OK  %s%s" % (label, (": " + first) if first else ""))
            except ToolError as exc:
                bad[0] += 1
                report.append("ERR %s: %s" % (label, str(exc).splitlines()[0]))

        for d in devices:
            step("crear %s (%s)" % (d["name"], d["model"]),
                 lambda d=d: self.add_device({"name": d["name"], "model": d["model"], "x": d["x"], "y": d["y"],
                                              "ports": d.get("ports")}))
        ports_for = {}      # dispositivo -> {vecino: puerto real}

        def do_link(l):
            out = self.connect({"device1": l["a"], "device2": l["b"], "cable": l.get("cable") or "auto",
                                "port1": l.get("port_a") or "", "port2": l.get("port_b") or ""})
            m = re.match(r"OK .*:(\S+) <-> .*:(\S+)\s*$", out.strip().split("\n")[0])
            if m:
                ports_for.setdefault(l["a"], {})[l["b"]] = m.group(1)
                ports_for.setdefault(l["b"], {})[l["a"]] = m.group(2)
            return out

        for l in plan.get("links", []):
            step("cable %s <-> %s" % (l["a"], l["b"]), lambda l=l: do_link(l))
        # Si el DHCP lo da un router o un servidor del plan, los clientes se activan AL FINAL y de uno en uno (en el
        # orden del plan): si no, piden IP por su cuenta en cualquier orden y el nombre deja de coincidir con la IP.
        # Ademas, recien cableado el puerto del switch aun no reenvia y un unico 'ipconfig /renew' acaba en
        # "DHCP request failed" (Practica 2B, 19 equipos sin IP): _dhcp_in_order reintenta hasta que llega.
        plan_dhcp = (any(r.get("dhcp_pools") for r in plan.get("routers", []))
                     or any(isinstance(s.get("dhcp"), dict) for s in plan.get("servers", [])))
        deferred = [h for h in plan.get("hosts", []) if h.get("dhcp")] if plan_dhcp else []
        for h in plan.get("hosts", []):
            if h in deferred:
                continue
            step("IP %s" % h["device"], lambda h=h: self.set_ip(
                {"device": h["device"], "ip": h.get("ip"), "mask": h.get("mask", "255.255.255.0"),
                 "gateway": h.get("gateway"), "dns": h.get("dns"), "port": h.get("port"),
                 "dhcp": bool(h.get("dhcp"))}))
        for srv in plan.get("servers", []):
            if srv.get("ip"):
                step("IP servidor %s" % srv["device"], lambda srv=srv: self.set_ip(
                    {"device": srv["device"], "ip": srv["ip"], "mask": srv.get("mask", "255.255.255.0"),
                     "gateway": srv.get("gateway"), "dns": srv.get("dns_server"), "port": srv.get("port")}))
            if isinstance(srv.get("dhcp"), dict):
                dh = srv["dhcp"]
                # Sin "pool": los planes llevan nombres de ejemplo ("LAN") y crear un pool nuevo dejaria serverPool repartiendo
                # en la misma red. Un pool adicional (otra red, con ip helper) se pide aparte con pt_dhcp_server.
                step("DHCP en %s" % srv["device"], lambda srv=srv, dh=dh: self.dhcp_server(
                    {"device": srv["device"], "gateway": dh.get("gateway"), "dns": dh.get("dns"),
                     "start_ip": dh["start_ip"], "mask": dh["mask"], "max_users": dh.get("max_users"),
                     "tftp": dh.get("tftp")}))
            if isinstance(srv.get("dns"), dict) and srv["dns"].get("records"):
                step("DNS en %s" % srv["device"], lambda srv=srv: self.dns_server(
                    {"device": srv["device"], "records": srv["dns"]["records"]}))
            if isinstance(srv.get("services"), list):
                step("servicios de %s" % srv["device"], lambda srv=srv: self.server_services(
                    {"device": srv["device"], "services": srv["services"]}))
        def resolved(spec):
            try:
                return planmod.resolve_ports(spec, ports_for.get(spec["device"], {}))
            except planmod.PlanError as exc:
                raise ToolError(str(exc))

        for r in plan.get("routers", []):
            step("config router %s" % r["device"],
                 lambda r=r: self.router_config({"device": r["device"], "spec": resolved(r), "save": bool(r.get("save"))}))
        for sw in plan.get("switches", []):
            step("config switch %s" % sw["device"],
                 lambda sw=sw: self.switch_config({"device": sw["device"], "spec": resolved(sw)}))
        for c in plan.get("cli", []):
            step("cli %s" % c["device"], lambda c=c: self.cli({"device": c["device"], "commands": c["commands"]}))
        for h in deferred:
            def dhcp_step(h=h):
                ip = self._dhcp_in_order(h["device"], h.get("port") or "FastEthernet0")
                if h.get("expect_ip") and ip != h["expect_ip"] and re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
                    raise ToolError("recibio %s y se esperaba %s (nombre e IP no coinciden)" % (ip, h["expect_ip"]))
                return ip
            step("DHCP %s" % h["device"], dhcp_step)
        for n in plan.get("notes", []):
            step("nota %s" % n.get("text"), lambda n=n: self.add_note(n))
        report.append("")
        report.append("Resumen: %d pasos correctos, %d con error." % (ok[0], bad[0]))
        if bad[0]:
            report.append("Revisa los ERR; puedes repetir solo esos pasos con las herramientas sueltas.")
        return "\n".join(report)
