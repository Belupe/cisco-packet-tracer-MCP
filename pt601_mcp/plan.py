"""Plan declarativo de topologia: validacion, autoposicionado y pasos de construccion.

Esquema (todo opcional salvo `devices`):
{
  "devices": [{"name": "SW1", "model": "2960-24TT", "x": 300, "y": 250}],
  "links":   [{"a": "SW1", "b": "PC1", "cable": "auto", "port_a": "", "port_b": ""}],
  "hosts":   [{"device": "PC1", "ip": "192.168.1.10", "mask": "255.255.255.0", "gateway": "192.168.1.1"},
              {"device": "PC2", "dhcp": true}],
  "servers": [{"device": "SRV1", "ip": "192.168.1.2", "mask": "255.255.255.0", "gateway": "192.168.1.1",
               "dhcp": {"pool": "LAN", "gateway": "192.168.1.1", "dns": "192.168.1.3",
                        "start_ip": "192.168.1.100", "mask": "255.255.255.0", "max_users": 100},
               "dns": {"records": [{"name": "www.local", "ip": "192.168.1.4"}]}}],
  "routers":  [{"device": "R1", "hostname": "R1", "interfaces": [...], "static_routes": [...], "ospf": {...}}],
  "switches": [{"device": "SW1", "hostname": "SW1", "vlans": [...], "access_ports": [...], "trunk_ports": [...]}],
  "cli":     [{"device": "R1", "commands": ["enable", "configure terminal", "..."]}]
}
"""
from . import catalog, ios

END_DEVICE_KINDS = ("pc", "laptop", "printer", "tablet", "pda", "wireless_end_device", "wired_end_device", "tv", "ip_phone")
TIER_BY_KIND = {"cloud": 0, "router": 0, "wireless_router": 0, "multilayer_switch": 1, "switch": 1,
                "hub": 1, "bridge": 1, "repeater": 1, "accesspoint": 2, "server": 2}


class PlanError(ValueError):
    pass


def _kind(model):
    canon, dtype, _ = catalog.resolve_model(model)
    for kind, code in catalog.DEVICE_TYPES.items():
        if code == dtype:
            return kind
    return "pc"


def validate_plan(plan):
    """Devuelve la lista de problemas (vacia si el plan es valido)."""
    errors = []
    if not isinstance(plan, dict) or not plan.get("devices"):
        return ["El plan necesita una lista 'devices' no vacia"]
    names = []
    for i, d in enumerate(plan["devices"]):
        name = str(d.get("name", "")).strip()
        if not name:
            errors.append("devices[%d]: falta 'name'" % i)
            continue
        if name in names:
            errors.append("Nombre de dispositivo repetido: %s" % name)
        names.append(name)
        try:
            catalog.resolve_model(d.get("model", ""))
        except catalog.CatalogError as exc:
            errors.append("%s: %s" % (name, str(exc).split(". Modelos")[0]))
    known = set(names)
    for i, l in enumerate(plan.get("links", [])):
        for end in ("a", "b"):
            if l.get(end) not in known:
                errors.append("links[%d]: '%s' no esta en devices (%s)" % (i, end, l.get(end)))
        try:
            catalog.cable_code(l.get("cable") or "auto")
        except catalog.CatalogError as exc:
            errors.append("links[%d]: %s" % (i, exc))
    for section in ("hosts", "servers", "routers", "switches", "cli"):
        for i, item in enumerate(plan.get(section, [])):
            if item.get("device") not in known:
                errors.append("%s[%d]: el dispositivo %r no esta en devices" % (section, i, item.get("device")))
    for item in plan.get("hosts", []) + plan.get("servers", []):
        if "ip" not in item:
            continue
        try:
            if item.get("ip"):
                ios.check_ip(item["ip"], "%s: ip" % item.get("device"))
                ios.check_mask(item.get("mask", "255.255.255.0"))
            if item.get("gateway"):
                ios.check_ip(item["gateway"], "%s: gateway" % item.get("device"))
        except ios.ConfigError as exc:
            errors.append(str(exc))
    for r in plan.get("routers", []):
        try:
            ios.router_config(r)
        except (ios.ConfigError, KeyError, ValueError) as exc:
            errors.append("routers[%s]: %s" % (r.get("device"), exc))
    for s in plan.get("switches", []):
        try:
            ios.switch_config(s)
        except (ios.ConfigError, KeyError, ValueError) as exc:
            errors.append("switches[%s]: %s" % (s.get("device"), exc))
    for srv in plan.get("servers", []):
        dh = srv.get("dhcp")
        if isinstance(dh, dict):
            try:
                for key in ("start_ip", "mask"):
                    if key not in dh:
                        raise ios.ConfigError("servers[%s].dhcp: falta '%s'" % (srv.get("device"), key))
                ios.check_ip(dh["start_ip"], "dhcp.start_ip")
                ios.check_mask(dh["mask"])
                for opt in ("gateway", "dns"):
                    if dh.get(opt):
                        ios.check_ip(dh[opt], "dhcp." + opt)
            except ios.ConfigError as exc:
                errors.append(str(exc))
        dns = srv.get("dns")
        if isinstance(dns, dict):
            for rec in dns.get("records", []):
                try:
                    ios.check_ip(rec["ip"], "dns record %s" % rec.get("name"))
                except (ios.ConfigError, KeyError) as exc:
                    errors.append("servers[%s].dns: %s" % (srv.get("device"), exc))
    return errors


def auto_layout(devices, links, origin=(80, 60), dx=130, dy=150):
    """Posiciona por niveles: routers/nubes arriba, switches debajo, servidores/APs y finales abajo."""
    tiers = {}
    for d in devices:
        kind = _kind(d["model"])
        tier = TIER_BY_KIND.get(kind, 3 if kind in END_DEVICE_KINDS else 2)
        tiers.setdefault(tier, []).append(d["name"])
    order = {}
    for n, tier in sorted(((n, t) for t, ns in tiers.items() for n in ns), key=lambda p: (p[1], p[0])):
        order[n] = len(order)
    neighbours = {}
    for l in links:
        neighbours.setdefault(l["a"], []).append(l["b"])
        neighbours.setdefault(l["b"], []).append(l["a"])
    tier_of = {n: t for t, ns in tiers.items() for n in ns}
    # orden dentro de cada nivel: por la posicion media de sus vecinos del nivel superior
    placed = {}
    width = max((len(ns) for ns in tiers.values()), default=1) * dx
    for tier in sorted(tiers):
        def key(n):
            ups = [placed[m][0] for m in neighbours.get(n, []) if m in placed and tier_of[m] < tier]
            return (sum(ups) / len(ups) if ups else float("inf"), n)
        ns = sorted(tiers[tier], key=key) if tier else sorted(tiers[tier])
        span = len(ns) * dx
        x0 = origin[0] + (width - span) / 2.0
        for i, n in enumerate(ns):
            placed[n] = (int(x0 + i * dx + dx / 2), origin[1] + tier * dy)
    return placed


def class_mask(ip):
    """Mascara por clase, como se usa en clase: 10.x -> /8, 172.26.x -> /16, 192.168.x -> /24."""
    first = int(str(ip).split(".")[0])
    return "255.0.0.0" if first < 128 else ("255.255.0.0" if first < 192 else "255.255.255.0")


# Medidas del esquema de clase (reglas.md, seccion 7). Son las coordenadas que devuelve pt_snapshot.
CLASS_LAYOUT = {"server_x": 40, "server_dy": 130, "server_switch_x": 195, "site_x": 455, "site_y0": 110,
                "site_dy": 290, "row_up": 88, "row_down": 85, "host_x0": 140, "host_dx": 145,
                "note_dx": -12, "note_dy": -48}       # nota justo encima del servidor (asi la coloco el usuario)


def class_plan(spec):
    """Genera un plan completo con las convenciones de clase (reglas.md) a partir de lo que dice un enunciado.

    spec = {"server_switch": "SW-ServerMadrid",
            "servers": [{"name": "HTTP", "ip": "172.26.1.3"}, {"name": "DNS", "ip": "172.26.1.2"}],
            "sites": [{"name": "SW-Goya", "pcs": 3, "laptops": 2}, ...],        # en el orden del enunciado
            "hosts_dhcp": false, "first_host": 10, "notes": true}
    Con "hosts_dhcp": true los equipos conservan el nombre de fabrica (PC0, Laptop0...; "first_pc"/"first_laptop" si el
    archivo ya tiene equipos) y no se numeran por IP.
    Opcionales: "mask", "gateway", "dns" (por defecto la IP del servidor llamado DNS, si lo hay) y, por servidor,
    "services": [...] y "dhcp": {...} SOLO si el enunciado pide configurar ese servicio.
    """
    if not isinstance(spec, dict):
        raise PlanError("spec debe ser un objeto")
    servers, sites = spec.get("servers") or [], spec.get("sites") or []
    if not servers or not sites:
        raise PlanError("spec necesita 'servers' y 'sites' (al menos uno de cada)")
    sw_name = str(spec.get("server_switch") or "").replace(" ", "")
    if not sw_name:
        raise PlanError("spec necesita 'server_switch' (el nombre que da el enunciado, p. ej. SW-ServerMadrid)")
    try:
        for s in servers:
            ios.check_ip(s["ip"], "servidor %s" % s.get("name"))
    except (KeyError, ios.ConfigError) as exc:
        raise PlanError("servidor sin IP valida: %s" % exc)
    prefix = servers[0]["ip"].rsplit(".", 1)[0]
    mask = spec.get("mask") or class_mask(servers[0]["ip"])
    gateway = spec.get("gateway") or prefix + ".1"
    dns = spec.get("dns")
    if dns is None:
        dns = next((s["ip"] for s in servers if str(s.get("name", "")).upper().startswith("DNS")), "")
    L = CLASS_LAYOUT
    dhcp = bool(spec.get("hosts_dhcp"))
    # Con DHCP los equipos NO se renombran (regla del usuario, 2026-10-06): se quedan con el nombre que les da PT
    # al crearlos (PC0, PC1..., Laptop0...). Solo con IP estatica el nombre es el ultimo octeto.
    auto_n = {"PC": int(spec.get("first_pc") or 0), "Laptop": int(spec.get("first_laptop") or 0)}
    devices, links, hosts, plan_servers, notes = [], [], [], [], []

    site_ys = [L["site_y0"] + i * L["site_dy"] for i in range(len(sites))]
    sw_y = int(sum(site_ys) / len(site_ys))
    devices.append({"name": sw_name, "model": "Switch-PT-Empty", "x": L["server_switch_x"], "y": sw_y,
                    "ports": len(servers) + len(sites)})
    y0 = sw_y - (len(servers) - 1) * L["server_dy"] // 2
    for i, s in enumerate(servers):                      # servidores: columna a la izquierda, primeros puertos
        name, y = str(s["name"]), y0 + i * L["server_dy"]
        devices.append({"name": name, "model": "Server-PT", "x": L["server_x"], "y": y})
        links.append({"a": sw_name, "port_a": "FastEthernet%d/1" % i, "b": name, "port_b": "FastEthernet0",
                      "cable": "straight"})
        entry = {"device": name, "ip": s["ip"], "mask": mask, "gateway": gateway}
        if dns:
            entry["dns_server"] = dns
        for key in ("services", "dhcp", "dns"):          # solo si el enunciado configura el servicio
            if key in s:
                entry[key] = s[key]
        plan_servers.append(entry)
        if spec.get("notes", True):
            notes.append({"text": s["ip"], "x": L["server_x"] + L["note_dx"], "y": y + L["note_dy"]})

    # Numeracion: sede de abajo primero; en cada sede portatiles y luego PCs; el mas bajo a la derecha.
    number = int(spec.get("first_host") or 10)
    numbers = {}
    for si in range(len(sites) - 1, -1, -1):
        for kind in ("laptops", "pcs"):
            count = int(sites[si].get(kind) or 0)
            for col in range(count - 1, -1, -1):
                numbers[(si, kind, col)] = number
                number += 1
    if number - 1 > 254:
        raise PlanError("Demasiados equipos para un solo ultimo octeto (%d)" % (number - 1))

    for si, site in enumerate(sites):
        sname, sy = str(site["name"]).replace(" ", ""), site_ys[si]
        pcs, laps = int(site.get("pcs") or 0), int(site.get("laptops") or 0)
        devices.append({"name": sname, "model": "Switch-PT-Empty", "x": L["site_x"], "y": sy, "ports": 1 + pcs + laps})
        links.append({"a": sw_name, "port_a": "FastEthernet%d/1" % (len(servers) + si), "b": sname,
                      "port_b": "FastEthernet0/1", "cable": "cross"})
        port = 1
        for kind, model, count, y in (("pcs", "PC-PT", pcs, sy - L["row_up"]),
                                      ("laptops", "Laptop-PT", laps, sy + L["row_down"])):
            for col in range(count):                     # de izquierda a derecha: puertos seguidos
                n = numbers[(si, kind, col)]
                hname = str(n)
                if dhcp:                                 # nombre de fabrica, en el orden en que se crean
                    base = model.split("-")[0]
                    hname = "%s%d" % (base, auto_n[base])
                    auto_n[base] += 1
                devices.append({"name": hname, "model": model, "x": L["site_x"] + L["host_x0"] + col * L["host_dx"], "y": y})
                links.append({"a": sname, "port_a": "FastEthernet%d/1" % port, "b": hname, "port_b": "FastEthernet0",
                              "cable": "straight"})
                port += 1
                host = {"device": hname, "dhcp": True} if dhcp else \
                    {"device": hname, "ip": "%s.%d" % (prefix, n), "mask": mask, "gateway": gateway}
                if dns and not dhcp:
                    host["dns"] = dns
                hosts.append(host)
    if not dhcp:
        hosts.sort(key=lambda h: int(h["device"]))
    plan = {"devices": devices, "links": links, "hosts": hosts, "servers": plan_servers}
    if notes:
        plan["notes"] = notes
    return plan


ROUTED_LAYOUT = {"col_dx": 430, "core_dy": 0, "router_dy": 130, "switch_dy": 260, "row_dy": 105, "host_dx": 115}


def routed_plan(spec):
    """Red con routers generada con las convenciones aprendidas: un Router-PT-Empty y un Switch-PT-Empty por sede,
    todos los routers unidos por un switch central (red de transito), una subred por sede y encaminamiento.

    spec = {"lan_block": "192.168.50.0", "prefix": 26,            # la /24 se trocea en subredes /prefix, una por sede
            "transit": "10.0.0.0",                                  # red /24 de transito: router k = .k+1
            "routing": "ospf" | "static" | "rip",
            "core": "SW-Core", "origin": [x, y],
            "host_names": "octet" | "site",                         # "site" = <Sede>-<octeto>, si el octeto ya esta usado
            "sites": [{"name": "Madrid", "pcs": 2, "laptops": 1, "dhcp": true,
                       "servers": [{"name": "DNS"}, {"name": "HTTP", "services": ["http"]}]}]}
    En cada subred: gateway = primera direccion, servidores desde la +2, equipos desde la +10 (nombre = ultimo octeto,
    que no se repite entre subredes de la misma /24). Cables rectos; puertos justos; Fa0/0 del router = transito.
    """
    import ipaddress
    if not isinstance(spec, dict) or not spec.get("sites"):
        raise PlanError("spec necesita 'sites' (al menos una sede)")
    sites = spec["sites"]
    prefix = int(spec.get("prefix") or 24)
    try:
        block = ipaddress.ip_network("%s/24" % spec.get("lan_block", "192.168.50.0"), strict=False)
        transit = ipaddress.ip_network("%s/24" % spec.get("transit", "10.0.0.0"), strict=False)
        subnets = list(block.subnets(new_prefix=prefix)) if prefix > 24 else None
    except ValueError as exc:
        raise PlanError("red invalida: %s" % exc)
    if subnets is None:                                              # una /24 entera por sede: 192.168.50.0, .51.0...
        subnets = [ipaddress.ip_network("%s/24" % ipaddress.ip_address(int(block.network_address) + 256 * i))
                   for i in range(len(sites))]
    if len(sites) > len(subnets):
        raise PlanError("Con /%d solo caben %d sedes en %s" % (prefix, len(subnets), block))
    routing = str(spec.get("routing") or "ospf").lower()
    if routing not in ("ospf", "static", "rip"):
        raise PlanError("routing debe ser ospf, static o rip")
    host_names = str(spec.get("host_names") or ("octet" if prefix > 24 else "site")).lower()
    if host_names not in ("octet", "site"):
        raise PlanError("host_names debe ser octet o site")
    core = str(spec.get("core") or "SW-Core")
    ox, oy = (spec.get("origin") or [100, 80])[:2]
    L = ROUTED_LAYOUT
    tmask = str(transit.netmask)
    dns_ip = ""
    info = []                                                        # datos calculados por sede
    for i, site in enumerate(sites):
        net = subnets[i]
        base = int(net.network_address)
        servers = site.get("servers") or []
        n_hosts = int(site.get("pcs") or 0) + int(site.get("laptops") or 0)
        if 10 + n_hosts > net.num_addresses - 1 or 2 + len(servers) > 10:
            raise PlanError("La sede %s no cabe en %s" % (site.get("name"), net))
        entry = {"site": site, "net": net, "mask": str(net.netmask), "gw": str(ipaddress.ip_address(base + 1)),
                 "transit_ip": str(ipaddress.ip_address(int(transit.network_address) + i + 1)),
                 "router": "R-%s" % site["name"], "switch": "SW-%s" % site["name"],
                 "servers": [(str(s["name"]), str(ipaddress.ip_address(base + 2 + k)), s) for k, s in enumerate(servers)]}
        for name, ip, _s in entry["servers"]:
            if name.upper().startswith("DNS") and not dns_ip:
                dns_ip = ip
        info.append(entry)

    devices = [{"name": core, "model": "Switch-PT-Empty", "x": ox + (len(sites) - 1) * L["col_dx"] // 2, "y": oy,
                "ports": len(sites)}]
    links, hosts, plan_servers, routers, cli, notes = [], [], [], [], [], []
    for i, e in enumerate(info):
        site, net = e["site"], e["net"]
        cx = ox + i * L["col_dx"]
        pcs, laps = int(site.get("pcs") or 0), int(site.get("laptops") or 0)
        devices.append({"name": e["router"], "model": "Router-PT-Empty", "x": cx, "y": oy + L["router_dy"], "ports": 2})
        devices.append({"name": e["switch"], "model": "Switch-PT-Empty", "x": cx, "y": oy + L["switch_dy"],
                        "ports": 1 + len(e["servers"]) + pcs + laps})
        links.append({"a": core, "port_a": "FastEthernet%d/1" % i, "b": e["router"], "port_b": "FastEthernet0/0", "cable": "straight"})
        links.append({"a": e["router"], "port_a": "FastEthernet1/0", "b": e["switch"], "port_b": "FastEthernet0/1", "cable": "straight"})
        notes.append({"text": "%s/%d" % (net.network_address, net.prefixlen), "x": cx + 45, "y": oy + L["switch_dy"] - 30})
        port, row = 1, 1
        base = int(net.network_address)

        def place(name, model, col, count, row_i):
            x = cx + int((col - (count - 1) / 2.0) * L["host_dx"])
            devices.append({"name": name, "model": model, "x": x, "y": oy + L["switch_dy"] + row_i * L["row_dy"]})

        if e["servers"]:
            for k, (name, ip, s) in enumerate(e["servers"]):
                place(name, "Server-PT", k, len(e["servers"]), row)
                links.append({"a": e["switch"], "port_a": "FastEthernet%d/1" % port, "b": name, "port_b": "FastEthernet0", "cable": "straight"})
                port += 1
                srv = {"device": name, "ip": ip, "mask": e["mask"], "gateway": e["gw"]}
                if dns_ip:
                    srv["dns_server"] = dns_ip
                for key in ("services", "dhcp", "dns"):
                    if key in s:
                        srv[key] = s[key]
                plan_servers.append(srv)
            row += 1
        # numeracion: portatiles primero y el mas bajo a la derecha, como en clase
        number = 10
        nums = {}
        for kind, count in (("laptops", laps), ("pcs", pcs)):
            for col in range(count - 1, -1, -1):
                nums[(kind, col)] = number
                number += 1
        for kind, model, count in (("pcs", "PC-PT", pcs), ("laptops", "Laptop-PT", laps)):
            for col in range(count):
                octet = (base & 255) + nums[(kind, col)]
                name = str(octet) if host_names == "octet" else "%s-%d" % (site["name"], octet)
                place(name, model, col, count, row)
                links.append({"a": e["switch"], "port_a": "FastEthernet%d/1" % port, "b": name, "port_b": "FastEthernet0", "cable": "straight"})
                port += 1
                ip = str(ipaddress.ip_address(base + nums[(kind, col)]))
                host = {"device": name, "dhcp": True, "expect_ip": ip} if site.get("dhcp") else \
                    {"device": name, "ip": ip, "mask": e["mask"], "gateway": e["gw"]}
                if dns_ip and not site.get("dhcp"):
                    host["dns"] = dns_ip
                hosts.append((base + nums[(kind, col)], host))
            if count:
                row += 1
        r = {"device": e["router"], "save": True, "interfaces": [
            {"port": "FastEthernet0/0", "ip": e["transit_ip"], "mask": tmask},
            {"port": "FastEthernet1/0", "ip": e["gw"], "mask": e["mask"]}]}
        if routing == "ospf":
            r["ospf"] = {"process": 1, "networks": [
                {"network": str(transit.network_address), "mask": tmask, "area": 0},
                {"network": str(net.network_address), "mask": e["mask"], "area": 0}]}
        elif routing == "rip":
            r["rip"] = {"networks": [str(transit.network_address), str(net.network_address)]}
        else:
            r["static_routes"] = [{"network": str(o["net"].network_address), "mask": o["mask"], "next_hop": o["transit_ip"]}
                                  for o in info if o is not e]
        if site.get("dhcp"):
            pool = {"name": str(site["name"]).upper(), "network": str(net.network_address), "mask": e["mask"], "gateway": e["gw"],
                    "excluded": [{"start": e["gw"], "end": str(ipaddress.ip_address(base + 9))}]}
            if dns_ip:
                pool["dns"] = [dns_ip]
            r["dhcp_pools"] = [pool]
        routers.append(r)
    hosts.sort(key=lambda p: p[0])                                   # DHCP: pedir en orden para que nombre = IP
    plan = {"devices": devices, "links": links, "hosts": [h for _n, h in hosts], "servers": plan_servers,
            "routers": routers}
    if spec.get("notes", True):
        plan["notes"] = notes
    return plan


def resolve_ports(obj, neighbour_ports):
    """Sustituye '@VECINO' por el puerto real que conecta con ese vecino (recursivo).

    neighbour_ports: {vecino: puerto} del dispositivo que se esta configurando.
    """
    if isinstance(obj, str) and obj.startswith("@"):
        who = obj[1:]
        if who not in neighbour_ports:
            raise PlanError("No hay un enlace con %r para resolver %r (revisa 'links')" % (who, obj))
        return neighbour_ports[who]
    if isinstance(obj, list):
        return [resolve_ports(o, neighbour_ports) for o in obj]
    if isinstance(obj, dict):
        return {k: resolve_ports(v, neighbour_ports) for k, v in obj.items()}
    return obj
