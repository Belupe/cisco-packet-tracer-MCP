"""Punto de entrada: arranca el puente HTTP y el servidor MCP por stdio."""
import argparse
import sys

from .bridge import Bridge
from .mcpproto import McpServer, serve
from .tools import Tools


def log(msg):
    sys.stderr.write("[pt601-mcp] %s\n" % msg)
    sys.stderr.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Servidor MCP local para Packet Tracer 6.0.1")
    parser.add_argument("--port", type=int, default=54321, help="puerto del puente (127.0.0.1)")
    args = parser.parse_args(argv)

    bridge = Bridge(port=args.port)
    try:
        bridge.start()
        log("puente en http://127.0.0.1:%d (token por sesion)" % bridge.port)
    except OSError as exc:
        log("AVISO: no pude abrir el puente en el puerto %d (%s). Las herramientas daran error "
            "hasta liberar el puerto (cierra servidor.ps1/servidor.py si siguen abiertos)." % (args.port, exc))

    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    serve(McpServer(Tools(bridge), log), sys.stdin, sys.stdout, log)
    return 0
