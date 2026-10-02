"""Puente HTTP local entre el servidor MCP y el panel del Script Module de PT.

Seguridad (inspirada en el repo de referencia):
- Escucha SOLO en 127.0.0.1.
- Token aleatorio: /next y /result lo exigen (comparacion en tiempo constante).
  El token solo viaja dentro de la pagina "/" que sirve este mismo servidor, y
  una web ajena no puede leerla (politica de mismo origen).
- Cabecera Host validada (defensa contra DNS rebinding).
- No existe endpoint /run: el codigo solo se encola desde dentro del proceso.
- Cuerpos limitados a 1 MB.
"""
import hashlib
import hmac
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_BODY = 1024 * 1024


class BridgeError(Exception):
    pass


class Bridge:
    def __init__(self, host="127.0.0.1", port=54321, token=None, panel_path=None):
        self.host = host
        self.port = port
        self.token = token or secrets.token_urlsafe(32)
        self.panel_path = panel_path or os.path.join(HERE, "extension", "interface.html")
        self._cond = threading.Condition()
        self._queue = []
        self._results = {}
        self._next_id = 1
        self.last_poll = 0.0
        self.unauthorized = 0
        self._server = None
        self._thread = None

    # ---- ciclo de vida -------------------------------------------------
    def start(self):
        bridge = self

        class Handler(BaseHandler):
            pass

        Handler.bridge = bridge
        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    # ---- API para las herramientas -------------------------------------
    def fingerprint(self):
        return hashlib.sha256(self.token.encode()).hexdigest()[:16]

    def connected(self, within=15.0):
        return self.last_poll > 0 and (time.time() - self.last_poll) < within

    def status(self):
        ago = None if self.last_poll == 0 else round(time.time() - self.last_poll, 1)
        return {"port": self.port, "pt_connected": self.connected(),
                "last_poll_ago": ago, "unauthorized_attempts": self.unauthorized}

    def run_js(self, code, timeout=25.0):
        if self.last_poll == 0:
            raise BridgeError(
                "Packet Tracer aun no se ha conectado al puente. Abre PT, arranca el Script Module "
                "(Start) y comprueba que la ventana 'PT-MCP local' esta abierta.")
        with self._cond:
            cid = self._next_id
            self._next_id += 1
            self._queue.append((cid, code))
            self._cond.notify_all()
            deadline = time.time() + timeout
            while cid not in self._results and time.time() < deadline:
                self._cond.wait(timeout=0.25)
            if cid in self._results:
                return self._results.pop(cid)
            self._queue = [(i, c) for (i, c) in self._queue if i != cid]
        raise BridgeError("Packet Tracer no respondio en %.0f s (panel cerrado o PT ocupado)." % timeout)

    # ---- usado por el handler ------------------------------------------
    def take_next(self, wait=2.0):
        self.last_poll = time.time()
        with self._cond:
            if not self._queue:
                self._cond.wait(timeout=wait)
            if self._queue:
                return self._queue.pop(0)
        return None

    def put_result(self, cid, text):
        with self._cond:
            self._results[cid] = text
            self._cond.notify_all()

    def token_ok(self, supplied):
        return supplied is not None and hmac.compare_digest(str(supplied), self.token)

    def panel_html(self):
        with open(self.panel_path, "r", encoding="utf-8") as f:
            return f.read().replace("__TOKEN__", self.token)


class BaseHandler(BaseHTTPRequestHandler):
    bridge = None

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if code != 204:
            self.wfile.write(body)

    def _host_ok(self):
        host = self.headers.get("Host", "")
        port = self.bridge.port
        return host in ("127.0.0.1:%d" % port, "localhost:%d" % port, "[::1]:%d" % port)

    def _auth(self, query):
        if self.bridge.token_ok((query.get("t") or [None])[0]):
            return True
        self.bridge.unauthorized += 1
        self._send(401, "token invalido")
        return False

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, "host no permitido")
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/":
            return self._send(200, self.bridge.panel_html(), "text/html; charset=utf-8")
        if url.path == "/ping":
            return self._send(200, "ok fp=%s" % self.bridge.fingerprint())
        if url.path == "/next":
            if not self._auth(query):
                return
            item = self.bridge.take_next()
            if item is None:
                return self._send(204)
            return self._send(200, "%d\n%s" % item)
        self._send(404, "no encontrado")

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, "host no permitido")
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path != "/result":
            return self._send(404, "no encontrado")
        if not self._auth(query):
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_BODY:
            return self._send(413, "demasiado grande")
        body = self.rfile.read(length).decode("utf-8", "replace")
        try:
            cid = int((query.get("id") or ["x"])[0])
        except ValueError:
            return self._send(400, "id invalido")
        self.bridge.put_result(cid, body)
        self._send(200, "ok")
