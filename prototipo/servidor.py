"""Servidor puente local (prototipo) para Packet Tracer 6.0.1.

Solo biblioteca estandar de Python 3.8+. Escucha SOLO en 127.0.0.1.
  GET  /        pagina del panel (la abre el Script Module en un web view)
  GET  /next    long-poll: entrega el siguiente codigo a ejecutar (204 si no hay)
  POST /result  el panel devuelve el resultado (?id=N, cuerpo = texto)
  POST /run     encola codigo JavaScript y espera el resultado (cuerpo = codigo)
  GET  /ping    comprobacion

Prototipo SIN token: antes de usarlo en serio hay que anadir autenticacion
(ver NOTAS.md, seccion de seguridad).
"""
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 54321
HOST = "127.0.0.1"
HERE = os.path.dirname(os.path.abspath(__file__))

cond = threading.Condition()
queue = []          # [(id, code)]
results = {}        # id -> texto
next_id = [1]
last_poll = [0.0]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _host_ok(self):
        host = self.headers.get("Host", "")
        return host in ("127.0.0.1:%d" % PORT, "localhost:%d" % PORT)

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403)
        path = self.path.split("?")[0]
        if path == "/":
            with open(os.path.join(HERE, "interface.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/ping":
            ago = time.time() - last_poll[0]
            return self._send(200, ("ok last_poll_ago=%.1f" % ago).encode())
        if path == "/next":
            last_poll[0] = time.time()
            with cond:
                if not queue:
                    cond.wait(timeout=2.0)
                if queue:
                    cid, code = queue.pop(0)
                    return self._send(200, ("%d\n%s" % (cid, code)).encode("utf-8"))
            return self._send(204)
        self._send(404)

    def do_POST(self):
        if not self._host_ok():
            return self._send(403)
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1024 * 1024:
            return self._send(413)
        body = self.rfile.read(length).decode("utf-8", "replace")
        path, _, query = self.path.partition("?")
        if path == "/result":
            cid = int(dict(p.split("=") for p in query.split("&"))["id"])
            with cond:
                results[cid] = body
                cond.notify_all()
            return self._send(200)
        if path == "/run":
            with cond:
                cid = next_id[0]
                next_id[0] += 1
                queue.append((cid, body))
                cond.notify_all()
                deadline = time.time() + 30
                while cid not in results and time.time() < deadline:
                    cond.wait(timeout=0.5)
                res = results.pop(cid, None)
            if res is None:
                return self._send(504, b"timeout: Packet Tracer no respondio")
            return self._send(200, res.encode("utf-8"))
        self._send(404)


if __name__ == "__main__":
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Puente en http://%s:%d  (Ctrl+C para parar)" % (HOST, PORT))
    srv.serve_forever()
