"""Pruebas offline (sin Packet Tracer). Ejecutar:  python3 -m unittest discover -s tests -v"""
import io
import json
import os
import re
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pt601_mcp import catalog, jsgen                      # noqa: E402
from pt601_mcp.bridge import Bridge, BridgeError           # noqa: E402
from pt601_mcp.mcpproto import McpServer, serve            # noqa: E402
from pt601_mcp.tools import ToolError, Tools               # noqa: E402


def http(url, method="GET", body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class FakePanel(threading.Thread):
    """Imita el panel: obtiene el token de '/', hace polling y responde con `responder(code)`."""

    def __init__(self, base, responder):
        super().__init__(daemon=True)
        self.base, self.responder, self.stop = base, responder, False
        _, page = http(base + "/")
        self.token = re.search(r'var TOKEN = "([^"]+)"', page).group(1)

    def run(self):
        while not self.stop:
            try:
                code, text = http("%s/next?t=%s" % (self.base, self.token))
                if code == 200:
                    cid, js = text.split("\n", 1)
                    http("%s/result?id=%s&t=%s" % (self.base, cid, self.token), "POST",
                         self.responder(js).encode())
            except (OSError, urllib.error.URLError):
                return      # el servidor se apago al terminar la prueba


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge(port=0)
        self.bridge.start()
        self.base = "http://127.0.0.1:%d" % self.bridge.port

    def tearDown(self):
        self.bridge.stop()

    def test_token_injected_and_required(self):
        code, page = http(self.base + "/")
        self.assertEqual(code, 200)
        self.assertNotIn("__TOKEN__", page)
        self.assertIn(self.bridge.token, page)
        self.assertEqual(http(self.base + "/next")[0], 401)
        self.assertEqual(http(self.base + "/next?t=mal")[0], 401)
        self.assertEqual(http(self.base + "/result?id=1", "POST", b"x")[0], 401)
        self.assertEqual(self.bridge.unauthorized, 3)

    def test_ping_leaks_only_fingerprint(self):
        _, text = http(self.base + "/ping")
        self.assertNotIn(self.bridge.token, text)
        self.assertIn(self.bridge.fingerprint(), text)

    def test_host_header_checked(self):
        self.assertEqual(http(self.base + "/ping", headers={"Host": "evil.com:%d" % self.bridge.port})[0], 403)

    def test_no_run_endpoint(self):
        self.assertEqual(http(self.base + "/run", "POST", b"1+1")[0], 404)

    def test_oversize_body_rejected(self):
        url = "%s/result?id=1&t=%s" % (self.base, self.bridge.token)
        try:
            code = http(url, "POST", b"x" * (1024 * 1024 + 1))[0]
        except (urllib.error.URLError, ConnectionError, OSError):
            return      # el servidor corto la conexion sin leer el cuerpo: tambien es rechazo
        self.assertEqual(code, 413)
        self.assertNotIn(1, self.bridge._results)

    def test_run_js_roundtrip_with_fake_panel(self):
        panel = FakePanel(self.base, lambda js: "eco:" + js[:12])
        panel.start()
        try:
            for _ in range(50):
                if self.bridge.connected():
                    break
                threading.Event().wait(0.1)
            self.assertEqual(self.bridge.run_js("1+1+1+1+1+1+1", timeout=5), "eco:1+1+1+1+1+1+")
        finally:
            panel.stop = True

    def test_panel_reloads_itself_on_401(self):
        # Si el servidor se reinicia, el panel debe recargarse solo para recibir el token nuevo.
        html = self.bridge.panel_html()
        i = html.index("x.status == 401")
        self.assertIn("location.reload()", html[i:i + 400])

    def test_port_is_exclusive(self):
        # En Windows dos instancias podian escuchar en el mismo puerto y PT hablaba con la vieja.
        other = Bridge(port=self.bridge.port)
        with self.assertRaises(OSError):
            other.start()

    def test_run_js_before_any_connection_fails_fast(self):
        with self.assertRaises(BridgeError):
            self.bridge.run_js("1")


class FakeBridge:
    def __init__(self, replies):
        self.replies, self.sent = list(replies), []

    def run_js(self, code, timeout=25.0):
        self.sent.append(code)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def status(self):
        return {"port": 1, "pt_connected": True, "last_poll_ago": 0.1, "unauthorized_attempts": 0}


class ToolTests(unittest.TestCase):
    def test_add_device_validates_and_builds_two_arg_call(self):
        fb = FakeBridge(["OK Router0 -> R1", "OK 10,20"])
        out = Tools(fb).call("pt_add_device", {"name": "R1", "model": "2911", "x": 10, "y": 20})
        self.assertIn("OK", out)
        js = fb.sent[0]
        self.assertIn("lw.addDevice(0, \"2911\")", js)          # solo tipo y modelo en la 6.0.1
        self.assertIn("d.moveToLocation(10, 20)", js)
        # 6.0.1 real: moveToLocation usa la esquina del icono y getXCoordinate el centro, y un equipo recien creado
        # se recoloca solo al acabar el script: el ajuste fino va en una SEGUNDA llamada.
        self.assertNotIn("getXCoordinate", js)
        self.assertEqual(len(fb.sent), 2)
        self.assertIn("d.moveToLocation(10 - (d.getXCoordinate() - 10), 20 - (d.getYCoordinate() - 20))", fb.sent[1])
        self.assertIn("skipBoot", js)
        self.assertIn("ya existe", js)                          # guarda contra duplicados

    def test_switch_pt_empty_gets_modules_with_three_arg_addmodule(self):
        # Switch-PT-Empty nace sin puertos. En la 6.0.1 real: addModule("<ranura>", 4, modelo) -> true;
        # con 2 argumentos da 'Invalid arguments' y cuelga el motor si Debug esta abierta.
        fb = FakeBridge(["OK Switch0 -> SW1", "OK Switch1 -> SW2"])
        t = Tools(fb)
        out = t.call("pt_add_device", {"name": "SW1", "model": "Switch-PT-Empty"})
        js = fb.sent[0]
        self.assertIn('d.addModule(String(s), 4, "PT-SWITCH-NM-1CFE")', js)
        self.assertIn("s < 10", js)                       # 10 ranuras por defecto
        self.assertLess(js.index("setPower(false)"), js.index("addModule"))
        self.assertLess(js.index("addModule"), js.index("setPower(true)"))
        self.assertIn("10 puertos", out)
        t.call("pt_add_device", {"name": "SW2", "model": "Switch-PT-Empty", "ports": 5})
        self.assertIn("s < 5", fb.sent[1])
        for bad in (0, 11, "5", True):
            with self.assertRaises(ToolError):
                t.call("pt_add_device", {"name": "SW3", "model": "Switch-PT-Empty", "ports": bad})

    def test_connect_auto_falls_back_when_pt_rejects_8107(self):
        # En la 6.0.1 real, 8107 (auto) lo rechaza PT en los puertos de modulo del Switch-PT-Empty; 8100 si.
        fb = FakeBridge(["OK A:FastEthernet0/1 <-> B:FastEthernet0"])
        Tools(fb).call("pt_connect", {"device1": "A", "device2": "B"})
        js = fb.sent[0]
        self.assertIn("var codes = [8107];", js)
        self.assertIn("if (8107 == 8107)", js)
        self.assertIn("[8107, 8100, 8101]", js)            # equipos distintos: recto antes que cruzado
        self.assertIn("[8107, 8101, 8100]", js)            # equipos iguales: cruzado antes que recto
        self.assertIn("codes[k]", js)
        fb2 = FakeBridge(["OK A:x <-> B:y"])
        Tools(fb2).call("pt_connect", {"device1": "A", "device2": "B", "cable": "straight"})
        self.assertIn("var codes = [8100];", fb2.sent[0])   # un cable explicito no cambia de tipo
        self.assertIn("if (8100 == 8107)", fb2.sent[0])

    def test_models_with_own_ports_get_no_modules(self):
        fb = FakeBridge(["OK S -> S1"])
        Tools(fb).call("pt_add_device", {"name": "S1", "model": "2960-24TT"})
        self.assertNotIn("addModule", fb.sent[0])

    def test_unknown_model_and_missing_name(self):
        t = Tools(FakeBridge([]))
        with self.assertRaises(ToolError):
            t.call("pt_add_device", {"name": "X", "model": "NoExiste"})
        with self.assertRaises(ToolError):
            t.call("pt_add_device", {"model": "2911"})

    def test_model_case_insensitive_and_unverified_note(self):
        fb = FakeBridge(["OK A -> B"])
        self.assertIn("sin verificar", Tools(fb).call("pt_add_device", {"name": "B", "model": "1841"}))
        self.assertEqual(catalog.resolve_model("pc-pt")[:2], ("PC-PT", 8))

    def test_remote_error_becomes_tool_error(self):
        with self.assertRaises(ToolError):
            Tools(FakeBridge(["ERROR: ya existe un dispositivo llamado R1"])).call(
                "pt_add_device", {"name": "R1", "model": "2911"})
        with self.assertRaises(ToolError):
            Tools(FakeBridge([BridgeError("sin respuesta")])).call("pt_list_devices", {})

    def test_link_uses_numeric_cable_and_reports_false(self):
        fb = FakeBridge(["true", "false"])
        t = Tools(fb)
        self.assertIn("8100", t.call("pt_add_link", {"device1": "A", "port1": "Gi0/0", "device2": "B",
                                                      "port2": "Fa0/1", "cable": "straight"}))
        self.assertIn(", 8100)", fb.sent[0])
        with self.assertRaises(ToolError):
            t.call("pt_add_link", {"device1": "A", "port1": "x", "device2": "B", "port2": "y"})
        self.assertIn(", 8107)", fb.sent[1])                     # auto por defecto

    def test_user_values_are_escaped(self):
        evil = 'R1"); ipc.appWindow().exit(); ("'
        js = jsgen.add_device(evil, "2911", 0, None, None, False)
        self.assertNotIn('R1"); ipc', js)
        self.assertIn(json.dumps(evil), js)
        self.assertIn("\\u00f1", jsgen.q("ñ"))

    def test_set_ip_sets_device_gateway_and_dns_client(self):
        # 6.0.1 real: p.setDefaultGateway solo cambia PORT_GATEWAY; el visible es d.setDefaultGateway.
        # El DNS de la configuracion IP es el proceso DnsClient (setServerIp).
        fb = FakeBridge(["192.168.1.10 / 255.255.255.0"])
        Tools(fb).call("pt_set_ip", {"device": "10", "ip": "192.168.1.10", "mask": "255.255.255.0",
                                     "gateway": "192.168.1.1", "dns": "192.168.1.3"})
        js = fb.sent[0]
        self.assertIn('p.setDefaultGateway("192.168.1.1")', js)
        self.assertIn('d.setDefaultGateway("192.168.1.1")', js)
        self.assertIn('d.getProcess("DnsClient")', js)
        self.assertIn('dc.setServerIp("192.168.1.3")', js)
        with self.assertRaises(ToolError):
            Tools(FakeBridge([])).call("pt_set_ip", {"device": "10", "ip": "192.168.1.10", "mask": "255.255.255.0",
                                                     "dns": "no-es-ip"})

    def test_links_warn_when_devices_are_physically_far(self):
        # 6.0.1 real: cobre entre un equipo del archivo (1918,1918) y uno nuevo (0,0) = cable sin senal.
        fb = FakeBridge(["true\nAVISO: los dos equipos estan a 2713 m", "OK A:FastEthernet2/1 <-> B:FastEthernet0/0\nAVISO: lejos"])
        t = Tools(fb)
        out = t.call("pt_add_link", {"device1": "A", "port1": "FastEthernet2/1", "device2": "B",
                                     "port2": "FastEthernet0/0", "cable": "straight"})
        self.assertIn("OK cable", out)
        self.assertIn("AVISO", out)
        self.assertIn("farWarn(a, b, 8100)", fb.sent[0])
        self.assertIn("X_COORD", fb.sent[0])
        self.assertIn("AVISO", t.call("pt_connect", {"device1": "A", "device2": "B", "cable": "straight"}))
        self.assertIn("farWarn(a, b, codes[k])", fb.sent[1])
        self.assertIn("code == 8103", fb.sent[1])          # con fibra no se avisa

    def test_add_module_and_wifi_snapshot(self):
        fb = FakeBridge(["Router-PT-Empty", "OK puerto nuevo: FastEthernet2/0"])
        out = Tools(fb).call("pt_add_module", {"device": "R1", "slot": 2, "kind": "fiber"})
        self.assertIn("FastEthernet2/0", out)
        self.assertIn('for (var s = 2; s < 3; s++) { if (!d.addModule(String(s), 3, "PT-ROUTER-NM-1FFE"))', fb.sent[1])
        self.assertLess(fb.sent[1].index("addModule"), fb.sent[1].index("skipBoot"))   # si no, arranca en tiempo real
        with self.assertRaises(ToolError):
            Tools(FakeBridge(["Switch-PT-Empty"])).call("pt_add_module", {"device": "S", "slot": 1, "kind": "serial"})
        with self.assertRaises(ToolError):
            Tools(FakeBridge(["PC-PT"])).call("pt_add_module", {"device": "PC", "slot": 0})
        fb2 = FakeBridge(["OK puertos: 8 -> 7"])
        Tools(fb2).call("pt_remove_module", {"device": "S", "slot": 6})
        self.assertIn("skipBoot", fb2.sent[0])
        snap = Tools(FakeBridge(["D\tLaptop0\tLaptop-PT\t17\t364\t509\nP\tWireless0\t192.168.40.4\t255.255.255.0\ttrue\twifi\t\t"]))
        out = snap.call("pt_snapshot", {})
        self.assertIn("Wireless0 ip=192.168.40.4/255.255.255.0 DHCP (inalambrico)", out)
        self.assertIn('typeof lk.getPort1 != "function"', snap.bridge.sent[0])

    def test_http_get_polls_until_page_arrives(self):
        fb = FakeBridge(["true", "LEN=0\n", "LEN=62\n<html> Hello, world! </html>"])
        t = Tools(fb)
        import pt601_mcp.tools as tools_mod
        real_sleep, tools_mod.time.sleep = tools_mod.time.sleep, lambda s: None
        try:
            out = t.call("pt_http_get", {"device": "10", "url": "clase.com"})
            self.assertIn("Hello, world!", out)
            self.assertIn('h.go("http://clase.com")', fb.sent[0])
            self.assertIn('d.getProcess("HttpClient")', fb.sent[0])
            with self.assertRaises(ToolError):
                class Silent(FakeBridge):               # el servidor nunca contesta
                    def run_js(self, code, timeout=25.0):
                        return "true" if "h.go(" in code else "LEN=0\n"
                Tools(Silent([])).call("pt_http_get", {"device": "10", "url": "x.com", "wait_seconds": 1})
        finally:
            tools_mod.time.sleep = real_sleep

    def test_routing_audit_reports_missing_networks_and_saves(self):
        raw = "\n".join(["REDES\t192.168.40.0,192.168.50.64,10.0.0.0",
                          "Router0\t3\t3\tsi\tsi\t",
                          "R-Este\t2\t3\tsi\tsi\t192.168.50.64",
                          "R-ISP\t0\t3\tno\tsi\t192.168.40.0,192.168.50.64,10.0.0.0"])
        fb = FakeBridge([raw])
        out = Tools(fb).call("pt_routing_audit", {"save": True})
        self.assertIn("Router0: conoce 3 de 3 redes", out)
        self.assertIn("las alcanza por la ruta por defecto", out)
        self.assertIn("INALCANZABLES", out)
        self.assertIn("1 router(es) con redes inalcanzables", out)
        js = fb.sent[0]
        self.assertIn('cl.enterCommand("show ip route " + nets[k])', js)   # una red cada vez: sin --More--
        self.assertIn('cl.enterCommand("write memory")', js)
        self.assertIn("if (true)", js)
        self.assertIn("if (false)", Tools(FakeBridge([raw])).bridge.sent and "" or jsgen.routing_audit(False))
        for bad in ("let ", "const ", "=>"):
            self.assertNotIn(bad, js)

    def test_ping_matrix_round_robin_and_report(self):
        import pt601_mcp.tools as tools_mod
        rounds = Tools._rounds(["A", "B", "C", "D", "E"])
        seen = set()
        for r in rounds:
            names = [x for pair in r for x in pair]
            self.assertEqual(len(names), len(set(names)))          # nadie hace dos ping a la vez
            seen.update(frozenset(p) for p in r)
        self.assertEqual(len(seen), 10)                            # 5 equipos = 10 parejas, todas

        class Net(FakeBridge):
            ips = {"A": "10.0.0.1", "B": "10.0.0.2", "C": "10.0.0.3"}

            def run_js(self, code, timeout=25.0):
                self.sent.append(code)
                if "var ns = " in code:
                    return "\n".join("%s\t%s" % kv for kv in self.ips.items())
                if 'enterCommand("ping "' in code:
                    self.last = re.findall(r'\["(\w+)", "([\d.]+)"\]', code)
                    return "\n".join("%s\t100" % a for a, _ip in self.last)
                # C no llega a 10.0.0.1 ni A a 10.0.0.3; el resto responde
                return "\n".join("%s\t%d" % (a, 0 if {a, ip} == {"C", "10.0.0.1"} or {a, ip} == {"A", "10.0.0.3"} else 4)
                                  for a, ip in self.last)
        real_sleep, tools_mod.time.sleep = tools_mod.time.sleep, lambda s: None
        try:
            out = Tools(Net([])).call("pt_ping_matrix", {"devices": ["A", "B", "C"]})
        finally:
            tools_mod.time.sleep = real_sleep
        self.assertIn("2 de 3 parejas", out)
        self.assertIn("FALLAN", out)
        self.assertTrue("A (10.0.0.1) <-> C (10.0.0.3)" in out or "C (10.0.0.3) <-> A (10.0.0.1)" in out)
        with self.assertRaises(ToolError):
            Tools(FakeBridge([])).call("pt_ping_matrix", {"devices": ["A"]})

    def test_traceroute_waits_for_trace_complete(self):
        import pt601_mcp.tools as tools_mod
        fb = FakeBridge(["50", "enviado", "tracert 8.8.8.8\n 1 ...", "tracert 8.8.8.8\n 1 1 ms 192.168.40.1\nTrace complete."])
        real_sleep, tools_mod.time.sleep = tools_mod.time.sleep, lambda s: None
        try:
            out = Tools(fb).call("pt_traceroute", {"device": "PC0", "target": "8.8.8.8"})
        finally:
            tools_mod.time.sleep = real_sleep
        self.assertIn("Trace complete", out)
        self.assertIn('cl.enterCommand("tracert 8.8.8.8")', fb.sent[1])

    def test_status_warns_in_simulation_mode_and_realtime_tool(self):
        # Caso real: en modo Simulacion los ping se quedaban colgados y las rutas no llegaban.
        out = Tools(FakeBridge(["6.0.1.0011|49|false"])).call("pt_status", {})
        self.assertIn("SIMULACION", out)
        self.assertNotIn("SIMULACION", Tools(FakeBridge(["6.0.1.0011|49|true"])).call("pt_status", {}))
        self.assertNotIn("SIMULACION", Tools(FakeBridge(["6.0.1.0011|49"])).call("pt_status", {}))
        fb = FakeBridge(["true"])
        self.assertIn("Tiempo real", Tools(fb).call("pt_realtime", {}))
        self.assertIn("getRSSwitch().showRealtimeMode()", fb.sent[0])
        with self.assertRaises(ToolError):
            Tools(FakeBridge(["false"])).call("pt_realtime", {})

    def test_cli_finds_new_output_by_marker_not_by_length(self):
        # PT recorta el historial de la consola: por longitud se devolvian paginas de salida vieja.
        fb = FakeBridge(["PROMPT=Router#\n"])
        Tools(fb).call("pt_cli", {"device": "R1", "commands": ["show ip route"]})
        js = fb.sent[0]
        self.assertIn("o.lastIndexOf(mark)", js)
        self.assertNotIn("o.length >= before", js)

    def test_cli_leaves_config_mode_before_starting(self):
        fb = FakeBridge(["PROMPT=Router#\n"])
        Tools(fb).call("pt_cli", {"device": "R1", "commands": ["enable"]})
        js = fb.sent[0]
        self.assertIn('pr.indexOf("(config") >= 0', js)
        self.assertLess(js.index('cl.enterCommand("end")'), js.index('var cmds = ["enable"]'))

    def test_cli_wakes_idle_console_before_first_command(self):
        # 6.0.1 real: consola sin usar = modo "logout", prompt vacio; el primer comando se perdia.
        fb = FakeBridge(["PROMPT=Router#\n"])
        Tools(fb).call("pt_cli", {"device": "R1", "commands": ["enable"]})
        js = fb.sent[0]
        self.assertIn('String(cl.getMode()) == "logout"', js)
        self.assertLess(js.index('cl.enterCommand("")'), js.index('var cmds = ["enable"]'))

    def test_running_config_comes_from_xml(self):
        fb = FakeBridge(["hostname Router\ninterface FastEthernet0/0\n ip address 192.168.1.2 255.255.255.0"])
        out = Tools(fb).call("pt_running_config", {"device": "router firewall"})
        self.assertIn("ip address 192.168.1.2", out)
        self.assertIn('x.indexOf("<RUNNINGCONFIG>")', fb.sent[0])
        self.assertNotIn("enterCommand", fb.sent[0])       # sin consola: no hay --More--
        self.assertNotIn("\n", fb.sent[0])

    def test_router_pt_empty_gets_router_modules(self):
        # 6.0.1 real: Router-PT-Empty usa tipo de modulo 3 y PT-ROUTER-NM-1CFE (puertos FastEthernet<n>/0).
        fb = FakeBridge(["OK Router0 -> R1", "OK Router0 -> R2"])
        t = Tools(fb)
        out = t.call("pt_add_device", {"name": "R1", "model": "Router-PT-Empty"})
        self.assertIn('d.addModule(String(s), 3, "PT-ROUTER-NM-1CFE")', fb.sent[0])
        self.assertIn("s < 2", fb.sent[0])                # 2 puertos por defecto en el router
        self.assertIn("2 puertos", out)
        t.call("pt_add_device", {"name": "R2", "model": "Router-PT-Empty", "ports": 4})
        self.assertIn("s < 4", fb.sent[1])

    def test_dns_server_warns_records_do_not_resolve(self):
        fb = FakeBridge(["OK 1 registro(s) DNS anotados. AVISO"])
        Tools(fb).call("pt_dns_server", {"device": "DNS", "records": [{"name": "www.clase.com", "ip": "172.26.1.3"}]})
        self.assertIn("AVISO", fb.sent[0])
        self.assertLess(fb.sent[0].index('"DnsServer"'), fb.sent[0].index('"DnsServerMain"'))

    def test_notes_use_real_addnote_signature(self):
        # 6.0.1 real: addNote(x, y, tamano, texto) devuelve el id; removeCanvasItem(id) la borra.
        fb = FakeBridge(["OK {abc} en 129,106", "{abc}\t129\t106", "true"])
        t = Tools(fb)
        self.assertIn("{abc}", t.call("pt_add_note", {"text": "192.168.1.3", "x": 100, "y": 100}))
        self.assertIn('lw.addNote(100, 100, 10, "192.168.1.3")', fb.sent[0])
        self.assertIn("{abc} | 129 | 106", t.call("pt_list_notes", {}))
        self.assertNotIn("\n", fb.sent[1])                # el JS no puede llevar saltos ni tabuladores reales
        self.assertNotIn("\t", fb.sent[1])
        t.call("pt_remove_note", {"id": "{abc}"})
        self.assertIn('lw.removeCanvasItem("{abc}")', fb.sent[2])
        with self.assertRaises(ToolError):
            Tools(FakeBridge([])).call("pt_add_note", {"text": "x", "x": 1, "y": 1, "size": 500})

    def test_remove_link_and_module_use_real_signatures(self):
        fb = FakeBridge(["true", "OK puertos: 8 -> 7"])
        t = Tools(fb)
        self.assertIn("OK", t.call("pt_remove_link", {"device": "SW-A", "port": "FastEthernet2/1"}))
        self.assertIn('lw.deleteLink("SW-A", "FastEthernet2/1")', fb.sent[0])
        t.call("pt_remove_module", {"device": "SW-A", "slot": 6})
        self.assertIn('d.removeModule("6")', fb.sent[1])
        self.assertLess(fb.sent[1].index("d.setPower(false)"), fb.sent[1].index("d.removeModule"))
        with self.assertRaises(ToolError):
            Tools(FakeBridge(["false"])).call("pt_remove_link", {"device": "SW-A", "port": "FastEthernet2/1"})
        with self.assertRaises(ToolError):
            Tools(FakeBridge([])).call("pt_remove_module", {"device": "SW-A", "slot": "6"})

    def test_rename_checks_duplicates_first(self):
        fb = FakeBridge(["OK 20 -> 10"])
        self.assertIn("OK", Tools(fb).call("pt_rename_device", {"name": "20", "new_name": "10"}))
        js = fb.sent[0]
        self.assertLess(js.index('ya existe un dispositivo llamado'), js.index('d.setName("10")'))
        with self.assertRaises(ToolError):
            Tools(FakeBridge(["ERROR: ya existe un dispositivo llamado 10"])).call(
                "pt_rename_device", {"name": "20", "new_name": "10"})

    def test_server_services_uses_real_setter_names(self):
        # 6.0.1 real: el setter cambia segun el proceso (setEnable / setEnabled / setHttpsEnable).
        fb = FakeBridge(["OK encendidos: dhcp | apagados: dns,http"])
        Tools(fb).call("pt_server_services", {"device": "Server DHCP", "services": ["DHCP"]})
        js = fb.sent[0]
        self.assertIn('["dhcp", "DhcpServer", "setEnable", "isEnable", true]', js)
        self.assertIn('["tftp", "TftpServer", "setEnabled", "isEnabled", false]', js)
        self.assertIn('["https", "HttpsServer", "setHttpsEnable", "isHttpsEnabled", false]', js)
        with self.assertRaises(ToolError):
            Tools(FakeBridge([])).call("pt_server_services", {"device": "S", "services": ["telnet"]})
        fb2 = FakeBridge(["OK"])
        Tools(fb2).call("pt_server_services", {"device": "S", "services": ["email"]})
        self.assertIn('["smtp", "SmtpServer", "setEnable", "isEnabled", true]', fb2.sent[0])

    def test_snapshot_formats_positions_ips_links_and_services(self):
        raw = "\n".join([
            "D\tServer DHCP\tServer-PT\t9\t65\t357",
            "P\tFastEthernet0\t192.168.1.3\t255.255.255.0\tfalse\t8100\tSW-ServidorDHCP\tFastEthernet2/1",
            "G\t192.168.1.1\t0.0.0.0",
            "S\tdhcp=true dns=false",
            "L\tserverPool\t192.168.1.3\t192.168.1.255\t255.255.255.0\t192.168.1.1\t0.0.0.0",
            "D\tSW-Madrid\tSwitch-PT-Empty\t1\t388\t166",
            "P\tFastEthernet0/1\t\t\t\t8101\tSW-ServidorDHCP\tFastEthernet0/1",
            "G\t\t0.0.0.0",
            "D\tCopy10\tLaptop-PT\t17\t1313\t558",
            "P\tFastEthernet0\t192.168.1.5\t255.255.255.0\ttrue\t8100\tCopySW-Cadiz\tFastEthernet4/1"] * 40)
        fb = FakeBridge([raw])
        out = Tools(fb).call("pt_snapshot", {})
        self.assertIn("Server DHCP | Server-PT | tipo 9 | x=65 y=357", out)
        self.assertIn("FastEthernet0 ip=192.168.1.3/255.255.255.0 estatica --straight--> SW-ServidorDHCP:FastEthernet2/1", out)
        self.assertIn("FastEthernet0/1 --cross--> SW-ServidorDHCP:FastEthernet0/1", out)
        self.assertIn("ip=192.168.1.5/255.255.255.0 DHCP", out)
        self.assertIn("servicios: dhcp=true dns=false", out)
        self.assertIn("gateway=192.168.1.1 dns=-", out)
        self.assertNotIn("gateway=- dns=-", out)          # los switches no ensenan esa linea
        self.assertIn('d.getProcess("DnsClient")', fb.sent[0])
        self.assertIn("pool serverPool: 192.168.1.3 - 192.168.1.255", out)
        self.assertNotIn("recortado", out)          # una red de clase entera no debe recortarse
        for bad in ("let ", "const ", "=>", "JSON."):
            self.assertNotIn(bad, fb.sent[0])

    def test_list_devices_formats_rows(self):
        out = Tools(FakeBridge(["R1\t2911\t0\ttrue\t3\nS1\t2960-24TT\t1\ttrue\t26"])).call("pt_list_devices", {})
        self.assertIn("R1 | 2911 | 0 | true | 3", out)

    def test_ping_waits_for_statistics(self):
        fb = FakeBridge(["120", "enviado", "Pinging...\nRequest timed out.",
                         "Ping statistics for 1.1.1.1:\n Packets: Sent = 4, Received = 4"])
        import pt601_mcp.tools as tools_mod
        orig = tools_mod.time.sleep
        tools_mod.time.sleep = lambda s: None
        try:
            out = Tools(fb).call("pt_ping", {"device": "PC1", "target": "1.1.1.1", "wait_seconds": 5})
        finally:
            tools_mod.time.sleep = orig
        self.assertIn("Received = 4", out)

    def test_cli_answers_initial_dialog_only_when_asked(self):
        js = jsgen.cli("R1", ["enable"], True)
        self.assertIn("[yes/no]", js)
        self.assertNotIn("[yes/no]", jsgen.cli("R1", ["enable"], False))


class ProtocolTests(unittest.TestCase):
    def roundtrip(self, messages, replies=()):
        server = McpServer(Tools(FakeBridge(replies)))
        fin = io.StringIO("\n".join(json.dumps(m) for m in messages) + "\n")
        fout = io.StringIO()
        serve(server, fin, fout)
        return [json.loads(line) for line in fout.getvalue().splitlines()]

    def test_initialize_list_call(self):
        out = self.roundtrip([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "pt_catalog", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "nope"},
        ])
        self.assertEqual(len(out), 4)                       # la notificacion no responde
        self.assertEqual(out[0]["result"]["protocolVersion"], "2025-03-26")
        names = [t["name"] for t in out[1]["result"]["tools"]]
        self.assertIn("pt_add_device", names)
        self.assertIn("pt_ping", names)
        self.assertFalse(out[2]["result"]["isError"])
        self.assertIn("2911", out[2]["result"]["content"][0]["text"])
        self.assertEqual(out[3]["error"]["code"], -32601)

    def test_tool_error_is_not_protocol_error(self):
        out = self.roundtrip([{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "pt_add_device", "arguments": {"name": "x", "model": "zzz"}}}])
        self.assertTrue(out[0]["result"]["isError"])

    def test_bad_json_does_not_crash(self):
        server = McpServer(Tools(FakeBridge([])))
        fout = io.StringIO()
        serve(server, io.StringIO("esto no es json\n"), fout)
        self.assertEqual(json.loads(fout.getvalue())["error"]["code"], -32700)

    def test_all_schemas_are_valid_json(self):
        for tool in Tools(FakeBridge([])).listing():
            json.dumps(tool)
            self.assertEqual(tool["inputSchema"]["type"], "object")


if __name__ == "__main__":
    unittest.main()
