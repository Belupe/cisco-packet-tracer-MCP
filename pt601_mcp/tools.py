"""Herramientas MCP para Packet Tracer 6.0.1 (traducen llamadas a JavaScript del puente)."""
import time

from . import catalog, jsgen
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
             _obj({"name": S, "model": S, "x": I, "y": I}, ["name", "model"]), self.add_device),
            ("pt_remove_device", "Borra un dispositivo por nombre (todas las copias).",
             _obj({"name": S}, ["name"]), self.remove_device),
            ("pt_move_device", "Mueve un dispositivo a (x, y).",
             _obj({"name": S, "x": I, "y": I}, ["name", "x", "y"]), self.move_device),
            ("pt_add_link",
             "Conecta dos puertos. cable: straight|cross|roll|fiber|serial|console|auto (por defecto auto). "
             "Ej.: port1='GigabitEthernet0/0', port2='FastEthernet0/1'.",
             _obj({"device1": S, "port1": S, "device2": S, "port2": S, "cable": S},
                  ["device1", "port1", "device2", "port2"]), self.add_link),
            ("pt_set_ip",
             "Configura IP en un PC/servidor/laptop (por defecto puerto FastEthernet0). dhcp=true activa cliente DHCP.",
             _obj({"device": S, "ip": S, "mask": S, "gateway": S, "port": S, "dhcp": B}, ["device"]), self.set_ip),
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
        out = self._run(jsgen.add_device(name, model, dtype, x, y, dtype in catalog.BOOTING_TYPES))
        note = "" if verified else " (modelo sin verificar en 6.0.1)"
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

    def set_ip(self, args):
        dev = self._req(args, "device")
        dhcp = bool(args.get("dhcp"))
        if not dhcp:
            self._req(args, "ip")
            self._req(args, "mask")
        return self._run(jsgen.set_ip(dev, args.get("port") or "FastEthernet0", args.get("ip"),
                                      args.get("mask"), args.get("gateway"), dhcp))

    def cli(self, args):
        commands = args.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ToolError("commands debe ser una lista no vacia de textos")
        out = self._run(jsgen.cli(self._req(args, "device"), [str(c) for c in commands],
                                  args.get("answer_initial_dialog", True)))
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
