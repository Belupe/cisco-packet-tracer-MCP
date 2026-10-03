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
        fb = FakeBridge(["OK Router0 -> R1"])
        out = Tools(fb).call("pt_add_device", {"name": "R1", "model": "2911", "x": 10, "y": 20})
        self.assertIn("OK", out)
        js = fb.sent[0]
        self.assertIn("lw.addDevice(0, \"2911\")", js)          # solo tipo y modelo en la 6.0.1
        self.assertIn("d.moveToLocation(10, 20)", js)
        # 6.0.1 real: moveToLocation usa la esquina del icono y getXCoordinate el centro; se corrige el desfase.
        self.assertIn("d.moveToLocation(10 - (d.getXCoordinate() - 10), 20 - (d.getYCoordinate() - 20))", js)
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
            "S\tdhcp=true dns=false",
            "L\tserverPool\t192.168.1.3\t192.168.1.255\t255.255.255.0\t192.168.1.1\t0.0.0.0",
            "D\tSW-Madrid\tSwitch-PT-Empty\t1\t388\t166",
            "P\tFastEthernet0/1\t\t\t\t8101\tSW-ServidorDHCP\tFastEthernet0/1",
            "D\tCopy10\tLaptop-PT\t17\t1313\t558",
            "P\tFastEthernet0\t192.168.1.5\t255.255.255.0\ttrue\t8100\tCopySW-Cadiz\tFastEthernet4/1"] * 40)
        fb = FakeBridge([raw])
        out = Tools(fb).call("pt_snapshot", {})
        self.assertIn("Server DHCP | Server-PT | tipo 9 | x=65 y=357", out)
        self.assertIn("FastEthernet0 ip=192.168.1.3/255.255.255.0 estatica --straight--> SW-ServidorDHCP:FastEthernet2/1", out)
        self.assertIn("FastEthernet0/1 --cross--> SW-ServidorDHCP:FastEthernet0/1", out)
        self.assertIn("ip=192.168.1.5/255.255.255.0 DHCP", out)
        self.assertIn("servicios: dhcp=true dns=false", out)
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
