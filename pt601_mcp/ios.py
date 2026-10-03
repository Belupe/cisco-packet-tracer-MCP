"""Generadores de comandos IOS (routers y switches) a partir de descripciones declarativas.

Devuelven listas de comandos listas para la consola: empiezan en `enable` y terminan en `end`.
"""
import ipaddress


class ConfigError(ValueError):
    pass


def check_ip(value, what="IP"):
    try:
        return str(ipaddress.IPv4Address(str(value).strip()))
    except ValueError:
        raise ConfigError("%s invalida: %r" % (what, value))


def check_mask(value):
    try:
        return str(ipaddress.IPv4Network("0.0.0.0/%s" % str(value).strip()).netmask)
    except ValueError:
        raise ConfigError("Mascara invalida: %r (usa 255.255.255.0)" % (value,))


def wildcard(mask):
    return str(ipaddress.IPv4Address(int(ipaddress.IPv4Address(check_mask(mask))) ^ 0xFFFFFFFF))


def network_of(ip, mask):
    return str(ipaddress.IPv4Network("%s/%s" % (check_ip(ip), check_mask(mask)), strict=False).network_address)


def _wrap(lines):
    return ["enable", "configure terminal"] + lines + ["end"]


def _port_list(value):
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def _ospf_networks(entries):
    out = []
    for n in entries:
        wc = n.get("wildcard") or (wildcard(n["mask"]) if n.get("mask") else None)
        if not wc:
            raise ConfigError("OSPF/EIGRP: cada red necesita 'wildcard' o 'mask'")
        out.append((check_ip(n["network"], "red"), check_ip(wc, "wildcard"), n))
    return out


def wildcard(mask):
    return ".".join(str(255 - int(p)) for p in check_mask(mask).split("."))


def ipsec_vpn(spec):
    """VPN IPsec sitio a sitio (comprobada en un 2811 de PT 6.0.1; el Router-PT-Empty NO tiene crypto ni Tunnel).
    spec = {"wan_port": "FastEthernet0/0", "peer": "200.1.3.2", "key": "clase123",
            "local": [{"network": "172.16.10.0", "mask": "255.255.255.0"}], "remote": [...],
            "acl": 110, "map": "VPN", "transform": "TS"}"""
    peer = check_ip(spec["peer"], "peer")
    key = str(spec.get("key") or "").strip()
    if not key or " " in key:
        raise ConfigError("La VPN necesita una clave compartida ('key') sin espacios")
    local, remote = spec.get("local") or [], spec.get("remote") or []
    if not local or not remote:
        raise ConfigError("La VPN necesita las redes 'local' y 'remote'")
    acl, name, ts = int(spec.get("acl") or 110), str(spec.get("map") or "VPN"), str(spec.get("transform") or "TS")
    if not 100 <= acl <= 199:
        raise ConfigError("La ACL de la VPN debe ser extendida (100-199)")
    lines = ["crypto isakmp policy 10", "encryption aes", "authentication pre-share", "group 2", "exit",
             "crypto isakmp key %s address %s" % (key, peer),
             "crypto ipsec transform-set %s esp-aes esp-sha-hmac" % ts]
    for a in local:
        for b in remote:
            lines.append("access-list %d permit ip %s %s %s %s" % (
                acl, check_ip(a["network"], "red local"), wildcard(a["mask"]),
                check_ip(b["network"], "red remota"), wildcard(b["mask"])))
    lines += ["crypto map %s 10 ipsec-isakmp" % name, "set peer %s" % peer, "set transform-set %s" % ts,
              "match address %d" % acl, "exit", "interface %s" % spec["wan_port"], "crypto map %s" % name, "exit"]
    return lines


def router_config(spec):
    lines = []
    if spec.get("hostname"):
        lines.append("hostname %s" % spec["hostname"])
    for itf in spec.get("interfaces", []):
        port = itf["port"]
        lines.append("interface %s" % port)
        if "." in port:
            if "vlan" not in itf:
                raise ConfigError("La subinterfaz %s necesita 'vlan' (dot1Q)" % port)
            lines.append("encapsulation dot1Q %d" % int(itf["vlan"]))
        if itf.get("description"):
            lines.append("description %s" % itf["description"])
        if itf.get("ip"):
            lines.append("ip address %s %s" % (check_ip(itf["ip"]), check_mask(itf["mask"])))
        if itf.get("ip_helper"):
            lines.append("ip helper-address %s" % check_ip(itf["ip_helper"], "ip-helper"))
        lines.append("shutdown" if itf.get("shutdown") else "no shutdown")
        lines.append("exit")
    for r in spec.get("static_routes", []):
        lines.append("ip route %s %s %s" % (check_ip(r["network"]), check_mask(r["mask"]), check_ip(r["next_hop"], "next hop")))
    if spec.get("default_route"):
        lines.append("ip route 0.0.0.0 0.0.0.0 %s" % check_ip(spec["default_route"], "ruta por defecto"))
    ospf = spec.get("ospf")
    if ospf:
        lines.append("router ospf %d" % int(ospf.get("process", 1)))
        if ospf.get("router_id"):
            lines.append("router-id %s" % check_ip(ospf["router_id"], "router-id"))
        for net, wc, n in _ospf_networks(ospf.get("networks", [])):
            lines.append("network %s %s area %s" % (net, wc, n.get("area", 0)))
        for p in _port_list(ospf.get("passive")):
            lines.append("passive-interface %s" % p)
        if ospf.get("default_originate"):
            lines.append("default-information originate")
        lines.append("exit")
    eigrp = spec.get("eigrp")
    if eigrp:
        lines.append("router eigrp %d" % int(eigrp.get("as_number", 1)))
        for net, wc, _ in _ospf_networks(eigrp.get("networks", [])):
            lines.append("network %s %s" % (net, wc))
        lines.append("no auto-summary")
        lines.append("exit")
    rip = spec.get("rip")
    if rip:
        lines += ["router rip", "version 2", "no auto-summary"]
        for net in rip.get("networks", []):
            lines.append("network %s" % check_ip(net, "red RIP"))
        lines.append("exit")
    for acl in spec.get("acls", []):
        number = int(acl["number"])
        if not (1 <= number <= 199):
            raise ConfigError("ACL %d: numero fuera de rango (1-99 estandar, 100-199 extendida)" % number)
        rules = [str(r).strip() for r in acl.get("rules", []) if str(r).strip()]
        if not rules:
            raise ConfigError("ACL %d sin reglas" % number)
        for rule in rules:
            if rule.split()[0] not in ("permit", "deny", "remark"):
                raise ConfigError("ACL %d: la regla debe empezar por permit, deny o remark: %r" % (number, rule))
            lines.append("access-list %d %s" % (number, rule))
        for ap in acl.get("apply", []):
            direction = str(ap.get("direction", "in")).lower()
            if direction not in ("in", "out"):
                raise ConfigError("ACL %d: direction debe ser in u out" % number)
            lines += ["interface %s" % ap["port"], "ip access-group %d %s" % (number, direction), "exit"]
    for pool in spec.get("dhcp_pools", []):
        for ex in pool.get("excluded", []):
            start = check_ip(ex["start"], "excluida")
            lines.append("ip dhcp excluded-address %s%s" % (start, (" " + check_ip(ex["end"], "excluida")) if ex.get("end") else ""))
        lines.append("ip dhcp pool %s" % pool["name"])
        lines.append("network %s %s" % (check_ip(pool["network"], "red"), check_mask(pool["mask"])))
        if pool.get("gateway"):
            lines.append("default-router %s" % check_ip(pool["gateway"], "gateway"))
        if pool.get("dns"):
            lines.append("dns-server %s" % " ".join(check_ip(d, "dns") for d in _port_list(pool["dns"])))
        if pool.get("domain"):
            lines.append("domain-name %s" % pool["domain"])
        lines.append("exit")
    lines += [str(x) for x in spec.get("extra", [])]
    return _wrap(lines)


def _interfaces(ports):
    """Una linea 'interface ...' por puerto, o 'interface range' si es un rango 'Fa0/2-10'."""
    out = []
    for p in _port_list(ports):
        if "-" in p and p.rsplit("-", 1)[1].strip().isdigit() and "/" in p:
            head, last = p.rsplit("-", 1)
            out.append("interface range %s - %s" % (head.strip(), last.strip()))
        else:
            out.append("interface %s" % p)
    return out


def switch_config(spec):
    lines = []
    if spec.get("hostname"):
        lines.append("hostname %s" % spec["hostname"])
    for v in spec.get("vlans", []):
        lines.append("vlan %d" % int(v["id"]))
        if v.get("name"):
            lines.append("name %s" % v["name"])
        lines.append("exit")
    for grp in spec.get("access_ports", []):
        for itf in _interfaces(grp["ports"]):
            lines += [itf, "switchport mode access", "switchport access vlan %d" % int(grp["vlan"]), "exit"]
    for itf_name in _interfaces(spec.get("trunk_ports")):
        lines += [itf_name, "switchport mode trunk"]
        allowed = spec.get("trunk_allowed_vlans")
        if allowed:
            lines.append("switchport trunk allowed vlan %s" % ",".join(str(int(a)) for a in allowed))
        lines.append("exit")
    svi = spec.get("svi")
    if svi:
        lines += ["interface vlan %d" % int(svi["vlan"]),
                  "ip address %s %s" % (check_ip(svi["ip"]), check_mask(svi["mask"])), "no shutdown", "exit"]
        if svi.get("gateway"):
            lines.append("ip default-gateway %s" % check_ip(svi["gateway"], "gateway"))
    lines += [str(x) for x in spec.get("extra", [])]
    return _wrap(lines)
