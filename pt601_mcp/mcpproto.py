"""Protocolo MCP minimo sobre stdio (JSON por lineas), solo biblioteca estandar."""
import json

from . import __version__
from .tools import ToolError

PROTOCOL_DEFAULT = "2024-11-05"


class McpServer:
    def __init__(self, tools, log=None):
        self.tools = tools
        self.log = log or (lambda msg: None)

    def handle(self, msg):
        """Devuelve el diccionario de respuesta, o None si era una notificacion."""
        if not isinstance(msg, dict):
            return self._error(None, -32600, "peticion invalida")
        method = msg.get("method")
        mid = msg.get("id")
        is_request = "id" in msg
        if method == "initialize":
            client = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL_DEFAULT
            return self._ok(mid, {
                "protocolVersion": client,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "packet-tracer-601", "version": __version__},
                "instructions": "Controla Cisco Packet Tracer 6.0.1 (local). Empieza con pt_status.",
            })
        if method == "ping":
            return self._ok(mid, {})
        if method == "tools/list":
            return self._ok(mid, {"tools": self.tools.listing()})
        if method == "tools/call":
            params = msg.get("params") or {}
            try:
                text = self.tools.call(params.get("name"), params.get("arguments"))
                return self._ok(mid, {"content": [{"type": "text", "text": str(text)}], "isError": False})
            except ToolError as exc:
                return self._ok(mid, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
            except Exception as exc:  # noqa: BLE001 - nunca tumbar el servidor
                self.log("error interno en %s: %r" % (params.get("name"), exc))
                return self._ok(mid, {"content": [{"type": "text", "text": "error interno: %s" % exc}],
                                      "isError": True})
        if not is_request:
            return None            # notificaciones (initialized, cancelled...)
        return self._error(mid, -32601, "metodo no soportado: %s" % method)

    @staticmethod
    def _ok(mid, result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    @staticmethod
    def _error(mid, code, message):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve(server, fin, fout, log=None):
    for line in fin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            resp = McpServer._error(None, -32700, "JSON invalido")
        else:
            resp = server.handle(msg)
        if resp is not None:
            fout.write(json.dumps(resp) + "\n")
            fout.flush()
