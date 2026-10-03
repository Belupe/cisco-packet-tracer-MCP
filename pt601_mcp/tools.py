"""Herramientas MCP para Packet Tracer 6.0.1 (traducen llamadas a JavaScript del puente)."""
import time

import ipaddress
import json
import re

from . import catalog, ios, jsgen, plan as planmod
from .bridge import BridgeError


class ToolError(Exception):
    """Error pensado para que lo lea el usuario / el modelo."""


MAX_OUT = 6000


def _clip(text, limit=MAX_OUT):
    text = str(text)
    return text if len(text) <= limit else "...[recortado]...\n" + text[-limit:]


def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


S = {"type": "string"}
I = {"type": "integer"}
B = {"type": "boolean"}


class Tools:
    def __init__(self, bridge, js_timeout=25.0):
        self.bridge = bridge
        self.js_timeout = js_timeout
        self.registry = [
            ("pt_status", "Estado del puente y de Packet Tracer (version, numero de dispositivos).",
             _obj({}), self.status),
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
            ("pt_remove_link", "Quita el cable conectado a un puerto de un dispositivo.",
             _obj({"device": S, "port": S}, ["device", "port"]), self.remove_link),
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
             "responde solo 'no' al dialogo inicial. Ej.: ['enable','configure terminal','hostname R1'].",
             _obj({"device": S, "commands": {"type": "array", "items": S}, "answer_initial_dialog": B},
                  ["device", "commands"]), self.cli),
            ("pt_read_output", "Lee el final de la consola de un dispositivo.",
             _obj({"device": S, "tail_chars": I}, ["device"]), self.read_output),
            ("pt_ping",
             "Ejecuta ping desde un dispositivo y espera el resultado (los primeros paquetes pueden perderse por ARP/STP).",
             _obj({"device": S, "target": S, "wait_seconds": I}, ["device", "target"]), self.ping),
            ("pt_list_ports", "Lista los puertos de un dispositivo y si estan libres o conectados.",
             _obj({"device": S}, ["device"]), self.list_ports),
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
             _obj({"device": S, "spec": {"type": "object"}}, ["device", "spec"]), self.router_config),
            ("pt_switch_config",
             "Configura un switch desde una descripcion: hostname, vlans, access_ports, trunk_ports, svi, extra.",
             _obj({"device": S, "spec": {"type": "object"}}, ["device", "spec"]), self.switch_config),
            ("pt_dhcp_server",
             "Activa el servicio DHCP de un Server-PT y crea un pool (IP estatica del servidor: usa pt_set_ip).",
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
            ver, count = self._run(jsgen.status()).split("|")
            lines.append("Packet Tracer %s | %s dispositivos" % (ver, count))
        else:
            lines.append("PT no esta conectado: arranca el Script Module y deja abierta la ventana 'PT-MCP local'.")
        return "\n".join(lines)

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
            ports = spec["slots"] if ports is None else ports
            if isinstance(ports, bool) or not isinstance(ports, int) or not 1 <= ports <= spec["slots"]:
                raise ToolError("'ports' debe ser un entero entre 1 y %d para %s" % (spec["slots"], model))
            modules = (spec["module"], spec["type"], ports)
        out = self._run(jsgen.add_device(name, model, dtype, x, y, dtype in catalog.BOOTING_TYPES, modules))
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
        if out.strip().lower() != "true":
            raise ToolError("PT rechazo el cable %s %s <-> %s %s. Causas habituales: puerto ya ocupado, "
                            "nombre de puerto incorrecto o tipo de cable incompatible." % (d1, p1, d2, p2))
        return "OK cable %s:%s <-> %s:%s (codigo %d)" % (d1, p1, d2, p2, code)

    def remove_link(self, args):
        dev, port = self._req(args, "device"), self._req(args, "port")
        out = self._run(jsgen.remove_link(dev, port))
        if out.strip().lower() != "true":
            raise ToolError("PT no quito el cable de %s %s" % (dev, port))
        return "OK cable quitado de %s:%s" % (dev, port)

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

    def cli(self, args):
        commands = args.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ToolError("commands debe ser una lista no vacia de textos")
        timeout = max(self.js_timeout, 10 + 1.0 * len(commands))
        out = self._run(jsgen.cli(self._req(args, "device"), [str(c) for c in commands],
                                  args.get("answer_initial_dialog", True)), timeout)
        return _clip(out)

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

    def eval(self, args):
        return _clip(self._run(self._req(args, "code")))

    # ---- herramientas de alto nivel ------------------------------------
    def list_ports(self, args):
        out = self._run(jsgen.list_ports(self._req(args, "device")))
        rows = ["puerto | estado | up"]
        rows += [" | ".join(line.split("\t")) for line in out.split("\n") if line.strip()]
        return "\n".join(rows)

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
        # La 6.0.1 no tiene "maximo de usuarios": el pool se define por IP inicial y final. pool y tftp no se pueden
        # fijar por IPC (el pool por defecto se llama serverPool).
        try:
            users = int(args.get("max_users") or 50)
            net = ipaddress.ip_network("%s/%s" % (start, mask), strict=False)
            end = ipaddress.ip_address(int(ipaddress.ip_address(start)) + users - 1)
        except ValueError as exc:
            raise ToolError("max_users o rango invalido: %s" % exc)
        if users < 1 or end not in net:
            raise ToolError("El rango %s + %d usuarios se sale de la red %s" % (start, users, net))
        return self._run(jsgen.dhcp_server(self._req(args, "device"), gw, dns, start, str(end), mask))

    def dns_server(self, args):
        records = args.get("records")
        if not isinstance(records, list) or not records:
            raise ToolError("records debe ser una lista [{name, ip}]")
        try:
            clean = [{"name": str(r["name"]).strip(), "ip": ios.check_ip(r["ip"], "registro %s" % r.get("name"))} for r in records]
        except (KeyError, ios.ConfigError) as exc:
            raise ToolError("registro invalido: %s" % exc)
        return self._run(jsgen.dns_server(self._req(args, "device"), clean))

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
                if len(f) >= 8:
                    txt += " --%s--> %s:%s" % (cables.get(f[5], f[5]), f[6], f[7])
                rows.append(txt)
            elif f[0] == "S":
                rows.append("    servicios: %s" % f[1])
            elif f[0] == "L":
                rows.append("    pool %s: %s - %s mascara %s router %s dns %s" % tuple(f[1:7]))
        return _clip("\n".join(rows), 60000)

    def describe(self, args):
        return _clip(self._run(jsgen.describe(self._req(args, "device"), args.get("process") or "", args.get("port") or "")))

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
            m = re.match(r"OK .*:(\S+) <-> .*:(\S+)\s*$", out.strip())
            if m:
                ports_for.setdefault(l["a"], {})[l["b"]] = m.group(1)
                ports_for.setdefault(l["b"], {})[l["a"]] = m.group(2)
            return out

        for l in plan.get("links", []):
            step("cable %s <-> %s" % (l["a"], l["b"]), lambda l=l: do_link(l))
        for h in plan.get("hosts", []):
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
                step("DHCP en %s" % srv["device"], lambda srv=srv, dh=dh: self.dhcp_server(
                    {"device": srv["device"], "pool": dh.get("pool"), "gateway": dh.get("gateway"), "dns": dh.get("dns"),
                     "start_ip": dh["start_ip"], "mask": dh["mask"], "max_users": dh.get("max_users"),
                     "tftp": dh.get("tftp")}))
            if isinstance(srv.get("dns"), dict) and srv["dns"].get("records"):
                step("DNS en %s" % srv["device"], lambda srv=srv: self.dns_server(
                    {"device": srv["device"], "records": srv["dns"]["records"]}))
            if isinstance(srv.get("services"), list):
                step("servicios de %s" % srv["device"], lambda srv=srv: self.server_services(
                    {"device": srv["device"], "services": srv["services"]}))
        # En la 6.0.1 activar el cliente DHCP no pide la IP si el servidor aun no existia o no habia cable:
        # una vez cableado y con el pool listo, se fuerza con ipconfig /renew (comprobado en PT real).
        if any(isinstance(s.get("dhcp"), dict) for s in plan.get("servers", [])):
            for h in plan.get("hosts", []):
                if h.get("dhcp"):
                    step("DHCP renovar %s" % h["device"],
                         lambda h=h: self._run(jsgen.send_only(h["device"], "ipconfig /renew")) or "pedido")
        def resolved(spec):
            try:
                return planmod.resolve_ports(spec, ports_for.get(spec["device"], {}))
            except planmod.PlanError as exc:
                raise ToolError(str(exc))

        for r in plan.get("routers", []):
            step("config router %s" % r["device"],
                 lambda r=r: self.router_config({"device": r["device"], "spec": resolved(r)}))
        for sw in plan.get("switches", []):
            step("config switch %s" % sw["device"],
                 lambda sw=sw: self.switch_config({"device": sw["device"], "spec": resolved(sw)}))
        for c in plan.get("cli", []):
            step("cli %s" % c["device"], lambda c=c: self.cli({"device": c["device"], "commands": c["commands"]}))
        report.append("")
        report.append("Resumen: %d pasos correctos, %d con error." % (ok[0], bad[0]))
        if bad[0]:
            report.append("Revisa los ERR; puedes repetir solo esos pasos con las herramientas sueltas.")
        return "\n".join(report)
