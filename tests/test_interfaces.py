"""Pruebas offline de las herramientas de puertos, capturas de ventanas y servicios de servidor. Sin Packet Tracer."""
import base64
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pt601_mcp.tools as tools_mod                       # noqa: E402
from pt601_mcp import jsgen, winui                         # noqa: E402
from pt601_mcp.mcpproto import McpServer, serve            # noqa: E402
from pt601_mcp.tools import ToolError, Tools               # noqa: E402
from test_pt601 import FakeBridge                          # noqa: E402

# PNG minimo de 1x1 (cabecera real: firma + IHDR con ancho y alto).
PNG_1x1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def es3_ok(test, js):
    for bad in ("let ", "const ", "=>", "JSON."):
        test.assertNotIn(bad, js)


def port_row(name, link=None, **vals):
    row = [name] + [vals.get(f, "") for f in jsgen.PORT_FIELDS]
    return "\t".join(row + (list(link) if link else []))


class ScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = tools_mod.CAPTURES_DIR
        tools_mod.CAPTURES_DIR = self.tmp

    def tearDown(self):
        tools_mod.CAPTURES_DIR = self.orig
        shutil.rmtree(self.tmp)

    def test_saves_png_and_returns_image(self):
        fb = FakeBridge([base64.b64encode(PNG_1x1).decode()])
        out = Tools(fb).call("pt_screenshot", {"filename": "mapa1"})
        path = os.path.join(self.tmp, "mapa1.png")
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), PNG_1x1)
        self.assertIn("1x1", str(out))
        self.assertEqual(out.images, [PNG_1x1])
        self.assertIn('getWorkspaceImage("PNG")', fb.sent[0])
        es3_ok(self, fb.sent[0])

    def test_filename_cannot_escape_captures_dir(self):
        fb = FakeBridge([base64.b64encode(PNG_1x1).decode()])
        Tools(fb).call("pt_screenshot", {"filename": "..\\..\\evil name.exe"})
        self.assertEqual(os.listdir(self.tmp), ["evil_name.exe.png"])

    def test_rejects_non_png(self):
        fb = FakeBridge([base64.b64encode(b"GIF89a....").decode()])
        with self.assertRaises(ToolError):
            Tools(fb).call("pt_screenshot", {})
        self.assertEqual(os.listdir(self.tmp), [])

    def test_mcp_sends_image_content(self):
        server = McpServer(Tools(FakeBridge([base64.b64encode(PNG_1x1).decode()])))
        fout = io.StringIO()
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "pt_screenshot", "arguments": {}}}
        serve(server, io.StringIO(json.dumps(msg) + "\n"), fout)
        content = json.loads(fout.getvalue())["result"]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[1]["type"], "image")
        self.assertEqual(base64.b64decode(content[1]["data"]), PNG_1x1)


class InspectPortsTests(unittest.TestCase):
    def test_router_port_with_cable_but_shut_down_is_flagged(self):
        rows = "\n".join([
            port_row("FastEthernet0/0", ("8100", "S1", "FastEthernet0/1"), getPower="false", isPortUp="false",
                     isProtocolUp="false", getLightStatus="0", getMacAddress="0090.0CA0.3E95", getIpAddress="0.0.0.0",
                     getBandwidth="100000", isBandwidthAutoNegotiate="true", isFullDuplex="false", getMtu="1500",
                     getDelay="100", isCdpEnable="true", getNatMode="0"),
            port_row("FastEthernet1/0", getPower="false", isPortUp="false", getLightStatus="0"),
        ])
        fb = FakeBridge([rows])
        out = Tools(fb).call("pt_inspect_ports", {"device": "R1"})
        self.assertIn("FastEthernet0/0: APAGADO", out)
        self.assertIn("cable straight -> S1:FastEthernet0/1", out)
        self.assertIn("mac 0090.0CA0.3E95", out)
        self.assertIn("FastEthernet1/0: APAGADO", out)
        self.assertIn("sin cable", out)
        self.assertIn("AVISOS:", out)
        self.assertIn("no shutdown", out)
        self.assertEqual(out.count("\n  "), 1)        # solo el puerto con cable es anomalo
        es3_ok(self, fb.sent[0])

    def test_switch_and_pc_ports(self):
        rows = "\n".join([
            port_row("FastEthernet1/1", ("8100", "PC1", "FastEthernet0"), getPower="true", isPortUp="true",
                     isProtocolUp="true", getLightStatus="2", isFullDuplex="true", getAdminOpMode="3", getAccessVlan="10"),
            port_row("FastEthernet0/1", ("8101", "S2", "FastEthernet0/1"), getPower="true", isPortUp="false",
                     isProtocolUp="false", getLightStatus="0", isFullDuplex="false", getAdminOpMode="2", getNativeVlanId="99"),
        ])
        out = Tools(FakeBridge([rows])).call("pt_inspect_ports", {"device": "S1"})
        self.assertIn("luz verde", out)
        self.assertIn("modo access, vlan 10", out)
        self.assertIn("modo trunk (nativa 99)", out)
        self.assertIn("FastEthernet0/1: tiene cable pero la linea esta caida", out)
        self.assertNotIn("half", out)                  # el puerto caido no ensena un duplex sin negociar

    def test_generated_js_has_no_raw_newlines_or_tabs(self):
        # Un "\n" real dentro de una cadena JS da "SyntaxError: Parse error" en PT (fallo visto el 2026-10-22).
        for js in (jsgen.inspect_ports("S1", False), jsgen.workspace_image("PNG")):
            self.assertNotIn("\n", js)
            self.assertNotIn("\t", js)

    def test_only_linked_is_passed_and_avoids_hanging_methods(self):
        js = jsgen.inspect_ports("R1", True)
        self.assertIn("if (true && !lk) { continue; }", js)
        self.assertNotIn("getOtherPort", js)
        self.assertNotIn("getPortSecurity", js)
        out = Tools(FakeBridge([""])).call("pt_inspect_ports", {"device": "R1", "only_linked": True})
        self.assertIn("no tiene puertos con cable", out)


class AddModulesTests(unittest.TestCase):
    def test_switch_accepts_the_modules_of_its_physical_tab_and_catalog_lists_them(self):
        fb = FakeBridge(["Switch-PT-Empty", "OK puerto nuevo: GigabitEthernet6/1"])
        Tools(fb).call("pt_add_module", {"device": "S1", "slot": 6, "kind": "gigabit"})
        self.assertIn('"PT-SWITCH-NM-1CGE"', fb.sent[1])
        text = Tools(FakeBridge([])).call("pt_catalog", {})
        for m in ("PT-SWITCH-NM-1CE", "PT-SWITCH-NM-1FGE", "PT-ROUTER-NM-1AM"):
            self.assertIn(m, text)

    def test_count_adds_consecutive_slots_with_one_power_cycle(self):
        fb = FakeBridge(["Switch-PT-Empty", "OK puertos nuevos: FastEthernet4/1, FastEthernet5/1, FastEthernet6/1"])
        out = Tools(fb).call("pt_add_module", {"device": "S1", "slot": 4, "count": 3})
        js = fb.sent[1]
        self.assertIn('for (var s = 4; s < 7; s++) { if (!d.addModule(String(s), 4, "PT-SWITCH-NM-1CFE"))', js)
        self.assertEqual(js.count("d.setPower(false)"), 1)
        self.assertLess(js.index("addModule"), js.index("skipBoot"))
        self.assertIn("FastEthernet6/1", out)
        es3_ok(self, js)
        for bad in (0, 11, True, "3"):
            with self.assertRaises(ToolError):
                Tools(FakeBridge(["Switch-PT-Empty"])).call("pt_add_module", {"device": "S1", "slot": 4, "count": bad})


class InteractiveCliTests(unittest.TestCase):
    def test_one_line_at_a_time_waiting_for_each_answer_and_no_wake_enter(self):
        orig = tools_mod.time.sleep
        tools_mod.time.sleep = lambda s: None
        try:
            # por linea: longitud, envio, y lecturas hasta que la salida se repite dos veces
            fb = FakeBridge(["100", "enviado", "", "Username:", "Username:", "Username:",
                             "120", "enviado", "alumno\nPassword:", "alumno\nPassword:", "alumno\nPassword:"])
            out = Tools(fb).call("pt_cli", {"device": "PC1", "commands": ["ftp 10.0.0.2", "alumno"], "interactive": True})
        finally:
            tools_mod.time.sleep = orig
        sends = [js for js in fb.sent if "enterCommand" in js]
        self.assertEqual(len(sends), 2)
        self.assertIn('cl.enterCommand("ftp 10.0.0.2")', sends[0])
        self.assertNotIn('enterCommand("")', "".join(fb.sent))         # nada de Enter para despertar
        self.assertLess(fb.sent.index(sends[0]), fb.sent.index(sends[1]) - 3)   # espero respuesta antes de la siguiente
        self.assertIn("Password:", out)


class InteractiveWaitTests(unittest.TestCase):
    def test_slow_answer_is_awaited_until_the_prompt_comes_back(self):
        # ipconfig /renew: primero solo el eco (estable un rato), luego la IP y el prompt PC>.
        orig = tools_mod.time.sleep
        tools_mod.time.sleep = lambda s: None
        try:
            echo, done = "ipconfig /renew\n", "ipconfig /renew\n\nIP Address......: 10.0.0.40\n\nPC>"
            fb = FakeBridge(["100", "enviado", echo, echo, echo, echo, done, done, done])
            out = Tools(fb).call("pt_cli", {"device": "LAP2", "commands": ["ipconfig /renew"], "interactive": True})
        finally:
            tools_mod.time.sleep = orig
        self.assertIn("10.0.0.40", out)


class SetPortTests(unittest.TestCase):
    def test_api_fields_use_checked_setters_and_report_readback(self):
        fb = FakeBridge(["setDescription\tENLACE\nsetPower\ttrue\nsetBandwidthAutoNegotiate\tfalse\nsetBandwidth\t10000\n"
                         "setDuplexAutoNegotiate\tfalse\nsetFullDuplex\ttrue\nsetMtu\t1400\nsetMacAddress\t0011.2233.4455"])
        out = Tools(fb).call("pt_set_port", {"device": "R1", "port": "FastEthernet0/0", "description": "ENLACE",
                                             "power": True, "speed": "10", "duplex": "full", "mtu": 1400,
                                             "mac": "0011.2233.4455"})
        js = fb.sent[0]
        for piece in ('p.setDescription("ENLACE")', "p.setPower(true)", "p.setBandwidthAutoNegotiate(false)",
                      "p.setBandwidth(10000)", "p.setFullDuplex(true)", "p.setMtu(1400)", 'p.setMacAddress("0011.2233.4455")'):
            self.assertIn(piece, js)
        self.assertNotIn("\n", js)
        es3_ok(self, js)
        self.assertEqual(len(fb.sent), 1)                 # sin campos de IOS no se toca la consola
        self.assertIn("setBandwidth -> 10000", out)

    def test_switch_mode_and_vlan_go_through_ios_not_api(self):
        # setAdminOpMode no aplica el troncal en la 6.0.1 (solo cambia el running-config): el modo va por IOS.
        fb = FakeBridge(["PROMPT=Switch#\nSwitch(config-if)#switchport mode trunk"])
        out = Tools(fb).call("pt_set_port", {"device": "S1", "port": "FastEthernet0/1", "mode": "trunk",
                                             "native_vlan": 99, "allowed_vlans": [10, 20]})
        js = fb.sent[0]
        self.assertNotIn("setAdminOpMode", js)
        for cmd in ("interface FastEthernet0/1", "switchport mode trunk", "switchport trunk native vlan 99",
                    "switchport trunk allowed vlan 10,20"):
            self.assertIn(cmd, js)
        self.assertIn("aceptados", out)

    def test_port_security_forces_access_and_validates(self):
        cmds = __import__("pt601_mcp.ios", fromlist=["port_config"]).port_config(
            "Fa1/1", {"port_security": {"maximum": 2, "violation": "restrict", "sticky": True, "macs": ["0001.0001.0001"]}})
        self.assertIn("switchport mode access", cmds)
        self.assertLess(cmds.index("switchport mode access"), cmds.index("switchport port-security"))
        self.assertIn("switchport port-security mac-address 0001.0001.0001", cmds)
        for bad in ({"port_security": {"violation": "boom"}}, {"vlan": 5000}, {"mode": "dynamic"},
                    {"mac": "00:11:22:33:44:55"}, {"speed": "50"}, {"power": "si"}):
            with self.assertRaises(ToolError):
                Tools(FakeBridge([])).call("pt_set_port", dict({"device": "S1", "port": "Fa1/1"}, **bad))

    def test_rejected_ios_is_reported_and_dry_run_touches_nothing(self):
        fb = FakeBridge(["PROMPT=Router(config-if)#\n% Invalid input detected at '^' marker."])
        out = Tools(fb).call("pt_set_port", {"device": "R1", "port": "Serial0/0", "clock_rate": 64000})
        self.assertIn("RECHAZADOS", out)
        fb2 = FakeBridge([])
        plan = Tools(fb2).call("pt_set_port", {"device": "R1", "port": "Fa0/0", "ospf": {"cost": 5, "md5_key": "clave"},
                                              "cdp": False, "dry_run": True})
        self.assertEqual(fb2.sent, [])
        self.assertIn("IOS ip ospf cost 5", plan)
        self.assertIn("IOS ip ospf message-digest-key 1 md5 clave", plan)
        self.assertIn("API setCdpEnable(false)", plan)

    def test_nothing_to_change_and_save(self):
        with self.assertRaises(ToolError):
            Tools(FakeBridge([])).call("pt_set_port", {"device": "R1", "port": "Fa0/0"})
        fb = FakeBridge(["setPower\ttrue", "PROMPT=Router#\n[OK]"])
        Tools(fb).call("pt_set_port", {"device": "R1", "port": "Fa0/0", "power": True, "save": True})
        self.assertIn('"write memory"', fb.sent[1])


SERVER_XML = """<HTTP_SERVER>
   <ENABLED>1</ENABLED>
   <USERNAME>admin</USERNAME>
   <PASSWORD>cisco</PASSWORD>
  </HTTP_SERVER>
<DNS_SERVER>
   <ENABLED>1</ENABLED>
   <NAMESERVER-DATABASE><RESOURCE-RECORD><TYPE>A-REC</TYPE><NAME>barriosmadrid.es</NAME><TTL>86400</TTL><IPADDRESS>192.168.1.3</IPADDRESS></RESOURCE-RECORD></NAMESERVER-DATABASE>
  </DNS_SERVER>
<DHCP_SERVER>
   <ENABLED>0</ENABLED>
   <POOLS>
    <POOL>
     <NAME>serverPool</NAME><NETWORK>0.0.0.0</NETWORK><MASK>0.0.0.0</MASK><DEFAULT_ROUTER>0.0.0.0</DEFAULT_ROUTER>
     <TFTP_ADDRESS>0.0.0.0</TFTP_ADDRESS><START_IP>0.0.0.0</START_IP><END_IP>0.0.2.0</END_IP><DNS_SERVER>0.0.0.0</DNS_SERVER>
     <MAX_USERS>512</MAX_USERS><DHCP_POOL_LEASES/>
    </POOL>
   </POOLS>
   <DHCP_RESERVATIONS/>
  </DHCP_SERVER>
<TFTP_SERVER>
   <ENABLED>1</ENABLED>
  </TFTP_SERVER>
<FTP_SERVER>
   <ENABLED>1</ENABLED>
   <USER_ACCOUNT_MNGR>
    <ACCOUNT><USERNAME>cisco</USERNAME><PASSWORD>cisco</PASSWORD><PERMISSIONS>RWDNL</PERMISSIONS></ACCOUNT>
    <ACCOUNT><USERNAME>pepe</USERNAME><PASSWORD>1234</PASSWORD><PERMISSIONS>RL</PERMISSIONS></ACCOUNT>
   </USER_ACCOUNT_MNGR>
  </FTP_SERVER>
<NTP_SERVER>
   <ENABLED>1</ENABLED><ENABLED_SERVER_AUTHENTICATE>0</ENABLED_SERVER_AUTHENTICATE><KEY>0</KEY><MD5PASSWORD></MD5PASSWORD>
  </NTP_SERVER>
<SYSLOG_SERVER>
   <ENABLED>1</ENABLED>
  </SYSLOG_SERVER>
<ACS_SERVER>
   <ENABLED>0</ENABLED><USERS/><ACS_CLIENTS/><RADIUS_SETTINGS><AUTH_PORT>1645</AUTH_PORT></RADIUS_SETTINGS>
  </ACS_SERVER>
<EMAIL_SERVER>
   <SMTP_ENABLED>1</SMTP_ENABLED><SMTP_DOMAIN>barriosmadrid.es</SMTP_DOMAIN><POP3_ENABLED>1</POP3_ENABLED><FORWARD_MAIL>0</FORWARD_MAIL>
   <NO_OF_USERS>1</NO_OF_USERS><USER0>ana</USER0><PASSWORD0>1234</PASSWORD0><NO_OF_MAILS0>0</NO_OF_MAILS0>
  </EMAIL_SERVER>"""


class ServerTests(unittest.TestCase):
    def test_server_read_summarizes_every_service_from_the_xml(self):
        fb = FakeBridge([SERVER_XML])
        out = Tools(fb).call("pt_server_read", {"device": "SRV1"})
        for piece in ("HTTP: encendido (usuario admin)", "DNS: encendido, 1 registro(s)",
                      "barriosmadrid.es A-REC ttl=86400 ipaddress=192.168.1.3", "DHCP: apagado, 1 pool(s)",
                      "serverPool: 0.0.0.0 - 0.0.2.0", "FTP: encendido, cuentas: cisco/cisco (RWDNL), pepe/1234 (RL)",
                      "NTP: encendido, autenticacion no", "AAA: apagado, 0 usuario(s)",
                      "EMAIL: SMTP encendido, POP3 encendido, dominio barriosmadrid.es, cuentas: ana/1234"):
            self.assertIn(piece, out)
        self.assertIn("serializeToXml", fb.sent[0])
        es3_ok(self, fb.sent[0])

    def test_ftp_uses_three_argument_signature_and_validates_permissions(self):
        fb = FakeBridge(["luis\tcreado\ncisco\tya existia"])
        out = Tools(fb).call("pt_server_ftp", {"device": "SRV1", "users": [
            {"name": "luis", "password": "1234", "permissions": "lr"}, {"name": "cisco", "password": "cisco"}]})
        self.assertIn('["luis", "1234", "RL"]', fb.sent[0])            # en el orden de PT
        self.assertIn('["cisco", "cisco", "RWDNL"]', fb.sent[0])
        # addFtpUser devuelve undefined aunque cree la cuenta: el resultado se decide mirando si existe despues.
        self.assertIn("m.addFtpUser(U[i][0], U[i][1], U[i][2]);", fb.sent[0])
        self.assertIn('(m.isExistingUser(U[i][0]) ? "creado"', fb.sent[0])
        self.assertNotIn("(m.addFtpUser(", fb.sent[0])
        self.assertIn("luis: creado", out)
        self.assertIn("cisco: ya existia", out)
        for bad in ([{"name": "x", "password": "1", "permissions": "RX"}], [{"name": "a b", "password": "1"}],
                    [{"name": "x"}], [], "x"):
            with self.assertRaises(ToolError):
                Tools(FakeBridge([])).call("pt_server_ftp", {"device": "SRV1", "users": bad})

    def test_accounts_can_be_removed_and_checked_afterwards(self):
        fb = FakeBridge(["alumno\tborrada\nnadie\tno existia"])
        out = Tools(fb).call("pt_server_ftp", {"device": "SRV1", "remove": ["alumno", "nadie"]})
        self.assertIn("m.removeFtpUser(R[j]);", fb.sent[0])
        self.assertIn('(m.isExistingUser(R[j]) ? "PT no la borro" : "borrada")', fb.sent[0])
        self.assertIn('var U = []', fb.sent[0])                   # solo borrar: sin cuentas nuevas
        self.assertIn("alumno: borrada", out)
        fb = FakeBridge(["luis\tborrada"])
        out = Tools(fb).call("pt_server_email", {"device": "SRV1", "remove": ["luis"]})
        self.assertIn("em.deleteUser(R[j]);", fb.sent[0])
        self.assertNotIn("setServerDomainName", fb.sent[0])
        self.assertIn("luis: borrada", out)
        with self.assertRaises(ToolError):
            Tools(FakeBridge([])).call("pt_server_ftp", {"device": "SRV1", "remove": ["con espacio"]})
        with self.assertRaises(ToolError):
            Tools(FakeBridge([])).call("pt_server_ftp", {"device": "SRV1"})

    def test_email_domain_and_users(self):
        fb = FakeBridge(["dominio\tbarriosmadrid.es\nana\tya existia\nluis\tcreado"])
        out = Tools(fb).call("pt_server_email", {"device": "SRV1", "domain": "barriosmadrid.es", "users": [
            {"name": "ana", "password": "1234"}, {"name": "luis", "password": "abcd"}]})
        js = fb.sent[0]
        self.assertIn('setServerDomainName("barriosmadrid.es")', js)
        self.assertIn("em.addUser(U[i][0], U[i][1]);", js)
        self.assertIn('(em.getEmailUser(U[i][0]) ? "creado"', js)
        self.assertNotIn("\n", js)
        es3_ok(self, js)
        self.assertIn("dominio: barriosmadrid.es", out)
        with self.assertRaises(ToolError):
            Tools(FakeBridge([])).call("pt_server_email", {"device": "SRV1"})
        with self.assertRaises(ToolError):
            Tools(FakeBridge([])).call("pt_server_email", {"device": "SRV1", "domain": "sin punto"})


class DhcpAdminTests(unittest.TestCase):
    def test_remove_pool_and_exclusions_use_checked_signatures_and_warn(self):
        fb = FakeBridge(["pool\tpool2\tquitado\nexclusion\t10.0.0.1-10.0.0.9\tanadida\n"
                         "POOLS\tserverPool 10.0.0.10-10.0.0.50/255.255.255.0\nEXCLUSIONES\t10.0.0.1-10.0.0.9"])
        out = Tools(fb).call("pt_dhcp_admin", {"device": "SRV1", "remove_pools": ["pool2"],
                                               "exclude": [{"start": "10.0.0.1", "end": "10.0.0.9"}]})
        js = fb.sent[0]
        self.assertIn('var RP = ["pool2"]', js)
        self.assertIn('var EX = [["10.0.0.1", "10.0.0.9"]]', js)
        for call in ("dh.removePool(RP[a])", "dh.addExcludedAddress(EX[c][0], EX[c][1])",
                     "dh.removeExcludedAddress(UX[b][0], UX[b][1])", "dh.getExcludedAddressAt(i)"):
            self.assertIn(call, js)
        self.assertNotIn("\n", js)
        es3_ok(self, js)
        self.assertIn("pool pool2: quitado", out)
        self.assertIn("Exclusiones: 10.0.0.1-10.0.0.9", out)
        self.assertIn("ni se guardan en el .pkt", out)          # aviso: la 6.0.1 no las guarda ni las ensena

    def test_validation(self):
        for bad in ({"remove_pools": ["serverPool"]}, {"remove_pools": ["con espacio"]},
                    {"exclude": [{"start": "10.0.0.9", "end": "10.0.0.1"}]}, {"exclude": [{"start": "x"}]},
                    {"unexclude": ["10.0.0.1"]}):
            with self.assertRaises(ToolError):
                Tools(FakeBridge([])).call("pt_dhcp_admin", dict({"device": "SRV1"}, **bad))
        out = Tools(FakeBridge(["POOLS\tserverPool 10.0.0.1-10.0.0.9/255.255.255.0\nEXCLUSIONES\t"])).call(
            "pt_dhcp_admin", {"device": "SRV1"})
        self.assertIn("Exclusiones: ninguna", out)
        self.assertNotIn("AVISO", out)


class PngAndLocateTests(unittest.TestCase):
    def test_png_roundtrip_and_rgba_and_filters(self):
        rows = [bytes((x * 7 + y * 3) % 256 for x in range(3 * 5)) for y in range(4)]
        w, h, back = winui.decode_png(winui.encode_png(5, 4, rows))
        self.assertEqual((w, h, back), (5, 4, rows))
        self.assertEqual(winui.decode_png(PNG_1x1)[:2], (1, 1))     # RGBA de 1x1
        self.assertEqual(len(winui.decode_png(winui.encode_png(5, 4, rows), max_rows=2)[2]), 2)
        with self.assertRaises(winui.WinUiError):
            winui.decode_png(b"GIF89a")

    def test_locate_finds_the_map_offset_inside_a_bigger_image(self):
        import random
        rnd = random.Random(1)
        small = [bytes(rnd.randrange(256) for _ in range(3 * 40)) for _ in range(30)]
        big = [bytes(3 * 100) for _ in range(80)]
        big = [bytearray(r) for r in big]
        for y in range(30):                                  # el mapa pegado en (9, 21) de la "ventana"
            big[y + 21][9 * 3:(9 + 40) * 3] = small[y]
        big = [bytes(r) for r in big]
        self.assertEqual(winui.locate(big, small, 10, 5), [(9, 21)])
        self.assertTrue(winui.distinctive(small, 10, 5))
        self.assertFalse(winui.distinctive([bytes(3 * 40)] * 30, 10, 5))


class TrimBlackTests(unittest.TestCase):
    def test_black_frame_lines_are_removed_but_black_content_is_kept(self):
        K, W = b"\x00\x00\x00", b"\xff\xff\xff"
        rows = [K + W + K + W + K,          # contenido con negro en medio
                K + W + W + W + K,
                K + K + K + K + K]          # fila de abajo negra (borde)
        out = winui.trim_black(rows)
        self.assertEqual(out, [W + K + W, W + W + W])
        # Columna del borde con la franja del titulo en color (caso real de PT: 31 de 663 filas no son negras).
        T = b"\xea\xf7\xf9"
        rows = [T + W * 3] + [K + W * 3 for _ in range(19)]
        self.assertEqual(winui.trim_black(rows), [W * 3] * 20)


class DesktopAppCloseTests(unittest.TestCase):
    def test_finds_the_x_box_of_an_open_app_and_nothing_on_the_plain_desktop(self):
        B, F, D, G, BG = winui.APP_BAR, winui.BOX_FILL, winui.BOX_BORDER, b"\x65\x65\x65", b"\xf8\xf8\xf8"
        # Barra como la de IP Configuration (fila real 54): azul, caja [borde, fondo, X, fondo, borde], azul suelto, fondo.
        bar = B * 200 + D + F * 12 + G + F * 12 + D + B + BG * 40
        rows = [BG * 270] * 40 + [bar] * 25 + [BG * 270] * 20
        self.assertEqual(winui.desktop_app_close(rows), (213, 52))
        self.assertIsNone(winui.desktop_app_close([BG * 270] * 85))


class FakeUi:
    """Ventanas falsas: el mapa aparece en la ventana principal con desfase (9, 111); clic -> la ventana se abre."""
    WinUiError = winui.WinUiError
    decode_png = staticmethod(winui.decode_png)
    desktop_app_close = staticmethod(lambda rows: (480, 54) if rows == ["APP"] else None)
    encode_png = staticmethod(winui.encode_png)
    locate = staticmethod(winui.locate)
    distinctive = staticmethod(winui.distinctive)

    def __init__(self, map_rows, opened=False):
        self.map_rows, self.log, self.opened = map_rows, [], opened

    def main_window(self):
        return "MAIN", 1

    def capture(self, hwnd, full=False):
        if hwnd == "MAIN":
            assert full, "para situar el lienzo hace falta la captura entera (las coordenadas de clic son de GetWindowRect)"
            rows = [bytearray(3 * 300) for _ in range(300)]
            for y, r in enumerate(self.map_rows):
                rows[y + 111][9 * 3:9 * 3 + len(r)] = r
            return 300, 300, [bytes(r) for r in rows]
        if full and getattr(self, "app_open", False):
            return 1, 1, ["APP"]                       # hay una aplicacion abierta en el Desktop
        return 1, 1, [b"\x00\x00\x00"]

    def device_window(self, name):
        return ("WIN-" + name, True) if self.opened else (None, False)

    def click(self, hwnd, x, y):
        self.log.append(("click", hwnd, x, y))
        if hwnd == "MAIN":
            self.opened = True
        elif (x, y) == (480, 54):
            self.app_open = False                       # la X de la aplicacion
        elif y >= 140:
            self.app_open = True                        # un icono del Desktop abre su aplicacion

    def key(self, hwnd, vk):
        self.log.append(("key", hwnd, vk))


class UiOpenTests(unittest.TestCase):
    def setUp(self):
        import random
        rnd = random.Random(2)
        self.map_rows = [bytes(rnd.randrange(256) for _ in range(3 * 200)) for _ in range(150)]
        self.map_b64 = base64.b64encode(winui.encode_png(200, 150, self.map_rows)).decode()
        self.tmp = tempfile.mkdtemp()
        self.orig = tools_mod.CAPTURES_DIR
        tools_mod.CAPTURES_DIR = self.tmp
        self.orig_sleep = tools_mod.time.sleep
        tools_mod.time.sleep = lambda s: None

    def tearDown(self):
        tools_mod.CAPTURES_DIR = self.orig
        tools_mod.time.sleep = self.orig_sleep
        shutil.rmtree(self.tmp)

    def test_closed_window_is_opened_by_clicking_the_icon_then_tab_and_section(self):
        info = "no\t0\t100\t80\tFastEthernet0/0,FastEthernet1/0\nD\tR1\t100\t80"
        fb = FakeBridge([info, self.map_b64, info.replace("no", "si", 1)])
        ui = FakeUi(self.map_rows)
        out = Tools(fb, ui=ui).call("pt_ui_open", {"device": "R1", "section": "FastEthernet1/0"})
        clicks = [e for e in ui.log if e[0] == "click"]
        self.assertEqual(ui.log[0], ("key", "MAIN", winui.VK_ESCAPE))        # Select antes del clic
        self.assertEqual(clicks[0], ("click", "MAIN", 100 + 15 + 9, 80 + 111))
        self.assertEqual(clicks[1], ("click", "WIN-R1", 108, 43))            # pestana config (por la seccion)
        self.assertEqual(clicks[2], ("click", "WIN-R1", 82, 75 + 19 * 8))    # 9a fila: FastEthernet1/0
        self.assertIn("seccion FastEthernet1/0", str(out))
        self.assertEqual(len(out.images), 1)
        self.assertEqual(len(os.listdir(self.tmp)), 1)

    def test_already_open_window_is_shown_without_clicking_the_canvas(self):
        fb = FakeBridge(["si\t8\t500\t120\tFastEthernet0\nD\tPC1\t500\t120", "si"])
        ui = FakeUi(self.map_rows, opened=True)
        out = Tools(fb, ui=ui).call("pt_ui_open", {"device": "PC1", "app": "ip configuration"})
        self.assertIn("setVisible(true)", fb.sent[1])
        self.assertNotIn("MAIN", [e[1] for e in ui.log])
        # pestana, icono y, tras la captura, la X: una aplicacion abierta escribiria sus valores viejos al cerrarla mas tarde.
        self.assertEqual([e for e in ui.log if e[0] == "click"], [("click", "WIN-PC1", 175, 43), ("click", "WIN-PC1", 90, 145),
                                                                  ("click", "WIN-PC1", 480, 54)])
        self.assertIn("aplicacion ip configuration", str(out))
        self.assertIn("cerrada despues de la captura", str(out))
        self.assertEqual(len(out.images), 1)

    def test_open_desktop_app_is_closed_before_opening_another(self):
        fb = FakeBridge(["si\t8\t500\t120\tFastEthernet0\nD\tPC1\t500\t120", "si"])
        ui = FakeUi(self.map_rows, opened=True)
        ui.app_open = True
        Tools(fb, ui=ui).call("pt_ui_open", {"device": "PC1", "app": "command prompt"})
        self.assertEqual([e for e in ui.log if e[0] == "click"],
                         [("click", "WIN-PC1", 175, 43), ("click", "WIN-PC1", 480, 54), ("click", "WIN-PC1", 450, 145),
                          ("click", "WIN-PC1", 480, 54)])
        self.assertFalse(ui.app_open)

    def test_laptop_window_is_laid_out_like_a_pc(self):
        fb = FakeBridge(["si\t17\t300\t330\tFastEthernet0\nD\tLAP1\t300\t330", "si"])
        ui = FakeUi(self.map_rows, opened=True)
        Tools(fb, ui=ui).call("pt_ui_open", {"device": "LAP1", "section": "FastEthernet0"})
        self.assertEqual([e for e in ui.log if e[0] == "click"], [("click", "WIN-LAP1", 108, 43), ("click", "WIN-LAP1", 82, 75 + 19 * 6)])
        fb = FakeBridge(["si\t17\t300\t330\tFastEthernet0\nD\tLAP1\t300\t330", "si"])
        ui = FakeUi(self.map_rows, opened=True)
        Tools(fb, ui=ui).call("pt_ui_open", {"device": "LAP1", "app": "web browser"})
        self.assertIn(("click", "WIN-LAP1", 570, 145), ui.log)

    def test_server_desktop_has_its_own_layout(self):
        fb = FakeBridge(["si\t9\t500\t280\tFastEthernet0\nD\tSRV1\t500\t280", "si"])
        ui = FakeUi(self.map_rows, opened=True)
        Tools(fb, ui=ui).call("pt_ui_open", {"device": "SRV1", "app": "command prompt"})
        self.assertIn(("click", "WIN-SRV1", 212, 140), ui.log)
        with self.assertRaises(ToolError):                  # el servidor no tiene Dial-up
            Tools(FakeBridge(["si\t9\t500\t280\tFastEthernet0", "si"]), ui=FakeUi([], opened=True)).call(
                "pt_ui_open", {"device": "SRV1", "app": "dial-up"})

    def test_bad_tab_section_or_unknown_layout(self):
        info = "si\t1\t300\t200\tFastEthernet0/1,Vlan1\nD\tS1\t300\t200"
        with self.assertRaises(ToolError):
            Tools(FakeBridge([info, "si"]), ui=FakeUi([], opened=True)).call("pt_ui_open", {"device": "S1", "tab": "desktop"})
        with self.assertRaises(ToolError) as ctx:
            Tools(FakeBridge([info, "si"]), ui=FakeUi([], opened=True)).call("pt_ui_open", {"device": "S1", "section": "Vlan1"})
        self.assertIn("VLAN Database", str(ctx.exception))
        with self.assertRaises(ToolError):
            Tools(FakeBridge(["si\t3\t0\t0\t\n", "si"]), ui=FakeUi([], opened=True)).call("pt_ui_open", {"device": "H", "tab": "config"})

    def test_map_not_visible_gives_clear_error(self):
        info = "no\t0\t100\t80\tFa0/0\nD\tR1\t100\t80"
        ui = FakeUi(self.map_rows)
        ui.capture = lambda hwnd, full=False: (10, 10, [bytes(30)] * 10)                 # zoom distinto o mapa fuera de la vista
        with self.assertRaises(ToolError) as ctx:
            Tools(FakeBridge([info, self.map_b64]), ui=ui).call("pt_ui_open", {"device": "R1"})
        self.assertIn("zoom", str(ctx.exception))
        self.assertEqual([e for e in ui.log if e[0] == "click"], [])

    def test_capture_and_close(self):
        out = Tools(FakeBridge([]), ui=FakeUi([], opened=True)).call("pt_ui_capture", {"device": "PC1"})
        self.assertTrue(out.images[0].startswith(winui.PNG_SIGNATURE))
        with self.assertRaises(ToolError):
            Tools(FakeBridge([]), ui=FakeUi([])).call("pt_ui_capture", {"device": "PC1"})
        fb = FakeBridge(["si", "PC1,R1", "si", "si"])
        t = Tools(fb, ui=FakeUi([]))
        self.assertIn("ocultas: PC1", t.call("pt_ui_close", {"device": "PC1"}))
        self.assertIn("setVisible(false)", fb.sent[0])
        self.assertIn("ocultas: PC1, R1", t.call("pt_ui_close", {}))
        for js in fb.sent:
            self.assertNotIn("\n", js)
            es3_ok(self, js)

    def test_close_shuts_an_open_desktop_app_before_hiding(self):
        # Una aplicacion abierta (IP Configuration) escribe sus valores al cerrarse: hay que cerrarla mientras son los buenos.
        ui = FakeUi([], opened=True)
        ui.app_open = True
        fb = FakeBridge(["si"])
        out = Tools(fb, ui=ui).call("pt_ui_close", {"device": "PC1"})
        self.assertEqual([e for e in ui.log if e[0] == "click"], [("click", "WIN-PC1", 480, 54)])
        self.assertIn("setVisible(false)", fb.sent[0])                   # la X antes de ocultar
        self.assertIn("cerrada la aplicacion", out)


if __name__ == "__main__":
    unittest.main()
