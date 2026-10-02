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
