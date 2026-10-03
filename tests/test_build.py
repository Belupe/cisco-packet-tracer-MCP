"""Pruebas del constructor de topologias, IOS y herramientas de alto nivel (sin Packet Tracer)."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pt601_mcp import ios, plan as planmod                 # noqa: E402
from pt601_mcp.tools import ToolError, Tools               # noqa: E402


class ScriptBridge:
    """Puente simulado que responde segun el contenido del JavaScript recibido."""

    def __init__(self, fail_on=None):
        self.sent, self.fail_on = [], fail_on

    def status(self):
        return {"port": 1, "pt_connected": True, "last_poll_ago": 0, "unauthorized_attempts": 0}

    def run_js(self, code, timeout=25.0):
        self.sent.append(code)
        if self.fail_on and self.fail_on in code:
            return "ERROR: fallo simulado"
        if "lw.addDevice(" in code:
            name = re.search(r'" -> "|return "OK " \+ auto \+ " -> " \+ ("[^"]*")', code)
            return "OK Auto0 -> %s" % (name.group(1).strip('"') if name and name.group(1) else "x")
        if "freePorts(a)" in code or "createLink" in code:
            return "OK a:FastEthernet0/1 <-> b:FastEthernet0"
        if "setDhcpClientFlag" in code or "setIpSubnetMask" in code:
            return "192.168.1.10 / 255.255.255.0"
        if "getProcess(\"DhcpServer\")" in code:
            return "OK pool serverPool: 192.168.1.100 - 192.168.1.199"
        if "addIpAddress" in code:
            return "OK 2 registro(s) DNS"
        if "enterCommand" in code:
            return "PROMPT=R1#\n"
        return "OK"


class ClassPlanTests(unittest.TestCase):
    """Convenciones de clase (reglas.md) comprobadas contra el trabajo real del usuario: Practica 1A corregida."""

    SPEC = {"server_switch": "SW- ServerMadrid",
            "servers": [{"name": "HTTP", "ip": "172.26.1.3"}, {"name": "DNS", "ip": "172.26.1.2"}],
            "sites": [{"name": "SW-Goya", "pcs": 3, "laptops": 2}, {"name": "SW-SOL", "pcs": 3, "laptops": 2},
                      {"name": "SW-GranVia", "pcs": 2, "laptops": 4}, {"name": "SW-Moncloa", "pcs": 3, "laptops": 3}]}

    def setUp(self):
        self.plan = planmod.class_plan(self.SPEC)
        self.dev = {d["name"]: d for d in self.plan["devices"]}
        self.link = {(l["a"], l["port_a"]): l for l in self.plan["links"]}

    def test_names_are_last_octet_from_10_bottom_site_first(self):
        hosts = {h["device"]: h for h in self.plan["hosts"]}
        self.assertEqual(sorted(int(n) for n in hosts), list(range(10, 32)))
        self.assertEqual(hosts["10"], {"device": "10", "ip": "172.26.1.10", "mask": "255.255.0.0",
                                       "gateway": "172.26.1.1", "dns": "172.26.1.2"})
        # Moncloa (abajo): portatiles 10-12 y PCs 13-15; Goya (arriba): portatiles 27-28 y PCs 29-31
        self.assertEqual(self.link[("SW-Moncloa", "FastEthernet6/1")]["b"], "10")
        self.assertEqual(self.link[("SW-Moncloa", "FastEthernet1/1")]["b"], "15")
        self.assertEqual([self.link[("SW-Goya", "FastEthernet%d/1" % i)]["b"] for i in range(1, 6)],
                         ["31", "30", "29", "28", "27"])
        self.assertEqual(self.dev["31"]["model"], "PC-PT")
        self.assertEqual(self.dev["27"]["model"], "Laptop-PT")
        self.assertLess(self.dev["31"]["x"], self.dev["29"]["x"])       # el mas bajo a la derecha
        self.assertLess(self.dev["31"]["y"], self.dev["SW-Goya"]["y"])  # PCs arriba
        self.assertGreater(self.dev["27"]["y"], self.dev["SW-Goya"]["y"])  # portatiles abajo

    def test_switches_have_exact_ports_and_server_switch_order(self):
        self.assertNotIn("SW- ServerMadrid", self.dev)                  # sin el espacio del enunciado
        self.assertEqual(self.dev["SW-ServerMadrid"]["ports"], 6)
        self.assertEqual(self.dev["SW-Goya"]["ports"], 6)
        self.assertEqual(self.dev["SW-GranVia"]["ports"], 7)
        order = [self.link[("SW-ServerMadrid", "FastEthernet%d/1" % i)] for i in range(6)]
        self.assertEqual([l["b"] for l in order], ["HTTP", "DNS", "SW-Goya", "SW-SOL", "SW-GranVia", "SW-Moncloa"])
        self.assertEqual([l["cable"] for l in order], ["straight"] * 2 + ["cross"] * 4)
        self.assertEqual(order[2]["port_b"], "FastEthernet0/1")         # subida de la sede

    def test_servers_keep_factory_services_unless_asked_and_layout_goes_left_to_right(self):
        srv = {s["device"]: s for s in self.plan["servers"]}
        self.assertEqual(srv["HTTP"], {"device": "HTTP", "ip": "172.26.1.3", "mask": "255.255.0.0",
                                       "gateway": "172.26.1.1", "dns_server": "172.26.1.2"})
        self.assertLess(self.dev["HTTP"]["y"], self.dev["DNS"]["y"])    # orden del enunciado, de arriba abajo
        self.assertLess(self.dev["HTTP"]["x"], self.dev["SW-ServerMadrid"]["x"])
        self.assertLess(self.dev["SW-ServerMadrid"]["x"], self.dev["SW-Goya"]["x"])
        self.assertEqual(self.dev["SW-Goya"]["x"], self.dev["SW-Moncloa"]["x"])
        self.assertEqual([n["text"] for n in self.plan["notes"]], ["172.26.1.3", "172.26.1.2"])
        self.assertEqual(planmod.validate_plan(self.plan), [])

    def test_dhcp_practice_like_practica_2(self):
        plan = planmod.class_plan({
            "server_switch": "SW-ServidorDHCP", "hosts_dhcp": True,
            "servers": [{"name": "Server DHCP", "ip": "192.168.1.3", "services": ["dhcp"],
                         "dhcp": {"start_ip": "192.168.1.10", "mask": "255.255.255.0", "gateway": "192.168.1.1"}}],
            "sites": [{"name": "SW-Madrid", "pcs": 3, "laptops": 4}, {"name": "SW-Cadiz", "pcs": 3, "laptops": 1}]})
        self.assertEqual([h["device"] for h in plan["hosts"]], [str(n) for n in range(10, 21)])  # renovar en orden
        self.assertTrue(all(h == {"device": h["device"], "dhcp": True} for h in plan["hosts"]))
        self.assertEqual(plan["servers"][0]["services"], ["dhcp"])
        self.assertEqual(plan["servers"][0]["mask"], "255.255.255.0")
        self.assertNotIn("dns_server", plan["servers"][0])
        self.assertEqual(planmod.validate_plan(plan), [])

    def test_tool_previews_and_builds(self):
        out = Tools(ScriptBridge()).call("pt_class_plan", {"spec": self.SPEC})
        self.assertIn("equipos 10-31", out)
        self.assertIn("SW-ServerMadrid:FastEthernet2/1 --cross--> SW-Goya:FastEthernet0/1", out)
        bridge = ScriptBridge()
        report = Tools(bridge).call("pt_class_plan", {"spec": self.SPEC, "build": True})
        self.assertIn("0 con error", report)
        self.assertTrue(any('lw.addNote(' in c and '"172.26.1.3"' in c for c in bridge.sent))
        with self.assertRaises(ToolError):
            Tools(ScriptBridge()).call("pt_class_plan", {"spec": {"servers": []}})


USER_SCENARIO = {
    "devices": [
        {"name": "SW1", "model": "2960-24TT"},
        {"name": "PC1", "model": "PC-PT"}, {"name": "PC2", "model": "PC-PT"}, {"name": "PC3", "model": "PC-PT"},
        {"name": "LAP1", "model": "Laptop-PT"}, {"name": "LAP2", "model": "Laptop-PT"},
        {"name": "SRV-DHCP", "model": "Server-PT"}, {"name": "SRV-DNS", "model": "Server-PT"},
    ],
    "links": [{"a": "SW1", "b": n} for n in ("PC1", "PC2", "PC3", "LAP1", "LAP2", "SRV-DHCP", "SRV-DNS")],
    "servers": [
        {"device": "SRV-DHCP", "ip": "192.168.1.2", "mask": "255.255.255.0", "gateway": "192.168.1.1",
         "dhcp": {"pool": "LAN", "gateway": "192.168.1.1", "dns": "192.168.1.3", "start_ip": "192.168.1.100",
                  "mask": "255.255.255.0", "max_users": 100}},
        {"device": "SRV-DNS", "ip": "192.168.1.3", "mask": "255.255.255.0", "gateway": "192.168.1.1",
         "dns": {"records": [{"name": "www.local", "ip": "192.168.1.3"}, {"name": "dhcp.local", "ip": "192.168.1.2"}]}},
    ],
    "hosts": [{"device": n, "dhcp": True} for n in ("PC1", "PC2", "PC3", "LAP1", "LAP2")],
}


class IosTests(unittest.TestCase):
    def test_router_full(self):
        cmds = ios.router_config({
            "hostname": "R1",
            "interfaces": [{"port": "GigabitEthernet0/0", "ip": "10.0.0.1", "mask": "255.255.255.252"},
                           {"port": "GigabitEthernet0/1"},
                           {"port": "GigabitEthernet0/1.10", "vlan": 10, "ip": "192.168.10.1", "mask": "255.255.255.0"}],
            "static_routes": [{"network": "172.16.0.0", "mask": "255.255.0.0", "next_hop": "10.0.0.2"}],
            "default_route": "10.0.0.2",
            "ospf": {"process": 1, "networks": [{"network": "10.0.0.0", "mask": "255.255.255.252", "area": 0}],
                     "passive": "GigabitEthernet0/1"},
            "eigrp": {"as_number": 100, "networks": [{"network": "192.168.10.0", "wildcard": "0.0.0.255"}]},
            "rip": {"networks": ["10.0.0.0"]},
            "dhcp_pools": [{"name": "V10", "network": "192.168.10.0", "mask": "255.255.255.0",
                            "gateway": "192.168.10.1", "dns": ["8.8.8.8", "1.1.1.1"],
                            "excluded": [{"start": "192.168.10.1", "end": "192.168.10.9"}]}],
        })
        self.assertEqual(cmds[:2], ["enable", "configure terminal"])
        self.assertEqual(cmds[-1], "end")
        for expected in ("hostname R1", "encapsulation dot1Q 10", "network 10.0.0.0 0.0.0.3 area 0",
                         "passive-interface GigabitEthernet0/1", "router eigrp 100", "version 2",
                         "ip route 172.16.0.0 255.255.0.0 10.0.0.2", "ip route 0.0.0.0 0.0.0.0 10.0.0.2",
                         "ip dhcp excluded-address 192.168.10.1 192.168.10.9", "dns-server 8.8.8.8 1.1.1.1"):
            self.assertIn(expected, cmds)

    def test_subinterface_requires_vlan_and_bad_values_rejected(self):
        with self.assertRaises(ios.ConfigError):
            ios.router_config({"interfaces": [{"port": "Gi0/0.5", "ip": "1.1.1.1", "mask": "255.255.255.0"}]})
        with self.assertRaises(ios.ConfigError):
            ios.router_config({"interfaces": [{"port": "Gi0/0", "ip": "300.1.1.1", "mask": "255.255.255.0"}]})
        with self.assertRaises(ios.ConfigError):
            ios.router_config({"interfaces": [{"port": "Gi0/0", "ip": "10.0.0.1", "mask": "255.0.255.0"}]})

    def test_switch_config(self):
        cmds = ios.switch_config({"vlans": [{"id": 10, "name": "ventas"}, {"id": 20}],
                                  "access_ports": [{"ports": "FastEthernet0/2-10", "vlan": 10},
                                                   {"ports": ["FastEthernet0/11"], "vlan": 20}],
                                  "trunk_ports": ["GigabitEthernet0/1"], "trunk_allowed_vlans": [10, 20],
                                  "svi": {"vlan": 99, "ip": "192.168.99.2", "mask": "255.255.255.0",
                                          "gateway": "192.168.99.1"}})
        for expected in ("vlan 10", "name ventas", "interface range FastEthernet0/2 - 10",
                         "switchport access vlan 10", "interface FastEthernet0/11", "switchport mode trunk",
                         "switchport trunk allowed vlan 10,20", "interface vlan 99", "ip default-gateway 192.168.99.1"):
            self.assertIn(expected, cmds)


class PlanTests(unittest.TestCase):
    def test_user_scenario_is_valid(self):
        self.assertEqual(planmod.validate_plan(USER_SCENARIO), [])

    def test_validation_catches_mistakes(self):
        bad = {"devices": [{"name": "A", "model": "2911"}, {"name": "A", "model": "NoExiste"}],
               "links": [{"a": "A", "b": "Z"}], "hosts": [{"device": "A", "ip": "999.1.1.1"}]}
        text = "\n".join(planmod.validate_plan(bad))
        self.assertIn("repetido", text)
        self.assertIn("desconocido", text.lower())
        self.assertIn("'b' no esta en devices", text)
        self.assertIn("invalida", text)
        self.assertTrue(planmod.validate_plan({}))

    def test_layout_tiers_and_no_overlap(self):
        pos = planmod.auto_layout(USER_SCENARIO["devices"], USER_SCENARIO["links"])
        self.assertEqual(len(set(pos.values())), len(pos))           # nadie encima de nadie
        self.assertLess(pos["SW1"][1], pos["PC1"][1])                # switch sobre los PCs
        self.assertEqual(pos["PC1"][1], pos["LAP2"][1])              # finales en la misma fila


class BuildTests(unittest.TestCase):
    def test_user_scenario_builds_in_order(self):
        sb = ScriptBridge()
        report = Tools(sb).call("pt_build_topology", {"plan": USER_SCENARIO})
        self.assertIn("Resumen: ", report)
        self.assertNotIn("ERR", report)
        labels = [ln for ln in report.splitlines() if ln.startswith("OK")]
        self.assertEqual(len([l for l in labels if "crear" in l]), 8)
        self.assertEqual(len([l for l in labels if "cable" in l]), 7)
        idx = {k: next(i for i, l in enumerate(labels) if k in l) for k in ("crear SW1", "cable SW1", "IP servidor SRV-DHCP", "DHCP en", "DNS en")}
        self.assertLess(idx["crear SW1"], idx["cable SW1"])
        self.assertLess(idx["IP servidor SRV-DHCP"], idx["DHCP en"])
        joined = "\n".join(sb.sent)
        self.assertIn('getProcess("DhcpServer")', joined)
        self.assertNotIn("addNewPool", joined)               # no existe en la 6.0.1
        self.assertIn("setDhcpClientFlag(true)", joined)
        self.assertEqual(len([l for l in labels if "DHCP renovar" in l]), 5)   # 3 PCs + 2 portatiles
        self.assertIn('enterCommand("ipconfig /renew")', joined)
        self.assertLess(idx["DHCP en"], next(i for i, l in enumerate(labels) if "DHCP renovar" in l))

    def test_dhcp_server_uses_real_601_api(self):
        # Comprobado en una 6.0.1.0011 real: proceso "DhcpServer", pool por defecto con setStartIp/setEndIp/
        # setDefaultRouter/setDnsServerIp. setNetworkMask("...") da 'Invalid arguments' y cuelga el motor.
        sb = ScriptBridge()
        Tools(sb).call("pt_dhcp_server", {"device": "S", "start_ip": "192.168.1.100", "mask": "255.255.255.0",
                                           "gateway": "192.168.1.1", "dns": "192.168.1.3", "max_users": 100})
        js = sb.sent[0]
        self.assertIn('getProcess("DhcpServer")', js)
        self.assertIn('pool.setStartIp("192.168.1.100")', js)
        self.assertIn('pool.setEndIp("192.168.1.199")', js)       # inicio + 100 usuarios - 1
        self.assertIn('pool.setDefaultRouter("192.168.1.1")', js)
        self.assertIn('pool.setDnsServerIp("192.168.1.3")', js)
        self.assertNotIn("setNetworkMask", js)
        self.assertNotIn("addNewPool", js)
        with self.assertRaises(ToolError):                         # se sale de la /24
            Tools(sb).call("pt_dhcp_server", {"device": "S", "start_ip": "192.168.1.200", "mask": "255.255.255.0",
                                               "max_users": 100})

    def test_dry_run_does_not_touch_pt(self):
        sb = ScriptBridge()
        out = Tools(sb).call("pt_build_topology", {"plan": USER_SCENARIO, "dry_run": True})
        self.assertIn("Plan valido: 8 dispositivos", out)
        self.assertEqual(sb.sent, [])

    def test_invalid_plan_is_rejected_before_any_call(self):
        sb = ScriptBridge()
        with self.assertRaises(ToolError):
            Tools(sb).call("pt_build_topology", {"plan": {"devices": [{"name": "X", "model": "zzz"}]}})
        self.assertEqual(sb.sent, [])

    def test_errors_do_not_stop_the_build(self):
        sb = ScriptBridge(fail_on="DhcpServer")
        report = Tools(sb).call("pt_build_topology", {"plan": USER_SCENARIO})
        self.assertIn("ERR DHCP en SRV-DHCP", report)
        self.assertIn("OK  DNS en SRV-DNS", report)                  # continua con el resto
        self.assertIn("1 con error", report)

    def test_plan_as_json_string(self):
        import json
        out = Tools(ScriptBridge()).call("pt_build_topology", {"plan": json.dumps(USER_SCENARIO), "dry_run": True})
        self.assertIn("Plan valido", out)


class NeighbourPortTests(unittest.TestCase):
    PLAN = {"devices": [{"name": "R1", "model": "2911"}, {"name": "SW1", "model": "2960-24TT"}],
            "links": [{"a": "R1", "b": "SW1"}],
            "routers": [{"device": "R1", "interfaces": [{"port": "@SW1", "ip": "192.168.1.1", "mask": "255.255.255.0"}]}],
            "switches": [{"device": "SW1", "trunk_ports": ["@R1"]}]}

    def test_at_neighbour_resolves_to_real_ports(self):
        sb = ScriptBridge()
        report = Tools(sb).call("pt_build_topology", {"plan": self.PLAN})
        self.assertNotIn("ERR", report)
        cfg = [c for c in sb.sent if "ip address" in c][0]
        self.assertIn('"interface FastEthernet0/1"', cfg)          # puerto de R1 hacia SW1 (segun el puente simulado)
        sw = [c for c in sb.sent if "switchport mode trunk" in c][0]
        self.assertIn('"interface FastEthernet0"', sw)             # puerto de SW1 hacia R1

    def test_unresolvable_neighbour_reports_error(self):
        plan = dict(self.PLAN, routers=[{"device": "R1", "interfaces": [{"port": "@NOEXISTE", "ip": "1.1.1.1", "mask": "255.255.255.0"}]}])
        report = Tools(ScriptBridge()).call("pt_build_topology", {"plan": plan})
        self.assertIn("ERR config router R1", report)
        self.assertIn("NOEXISTE", report)

    def test_resolve_ports_recursive(self):
        out = planmod.resolve_ports({"a": ["@X", {"b": "@Y"}], "c": "tal cual"}, {"X": "Fa0/1", "Y": "Gi0/0"})
        self.assertEqual(out, {"a": ["Fa0/1", {"b": "Gi0/0"}], "c": "tal cual"})


class HighLevelToolTests(unittest.TestCase):
    def test_connect_uses_auto_port_selection(self):
        sb = ScriptBridge()
        Tools(sb).call("pt_connect", {"device1": "R1", "device2": "SW1"})
        self.assertIn("freePorts(a)", sb.sent[0])
        self.assertIn("var codes = [8107];", sb.sent[0])      # auto por defecto (con respaldo recto/cruzado)
        with self.assertRaises(ToolError):
            Tools(sb).call("pt_connect", {"device1": "R1", "device2": "R2", "cable": "serial"})

    def test_config_strips_mode_commands_and_can_save(self):
        sb = ScriptBridge()
        Tools(sb).call("pt_config", {"device": "R1", "config": "enable\nconf t\nhostname X\nend", "save": True})
        js = sb.sent[0]
        self.assertIn('"hostname X"', js)
        self.assertIn('"write memory"', js)
        self.assertEqual(js.count('"configure terminal"'), 1)

    def test_clear_requires_confirmation(self):
        with self.assertRaises(ToolError):
            Tools(ScriptBridge()).call("pt_clear_workspace", {})
        self.assertIn("OK", Tools(ScriptBridge()).call("pt_clear_workspace", {"confirm": True}))

    def test_dhcp_and_dns_validate_inputs(self):
        t = Tools(ScriptBridge())
        with self.assertRaises(ToolError):
            t.call("pt_dhcp_server", {"device": "S", "start_ip": "10.0.0.x", "mask": "255.255.255.0"})
        with self.assertRaises(ToolError):
            t.call("pt_dns_server", {"device": "S", "records": [{"name": "a", "ip": "bad"}]})
        self.assertIn("OK", t.call("pt_dns_server", {"device": "S", "records": [{"name": "a", "ip": "10.0.0.5"}]}))

    def test_describe_builds_for_process(self):
        sb = ScriptBridge()
        Tools(sb).call("pt_describe", {"device": "S", "process": "DhcpServerMain"})
        self.assertIn("getProcess", sb.sent[0])


if __name__ == "__main__":
    unittest.main()
