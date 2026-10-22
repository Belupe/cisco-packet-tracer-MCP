"""Catalogo de dispositivos y cables para Packet Tracer 6.0.1.

`verified=True`: el modelo se ha visto funcionar en una 6.0.1.0011 real.
El resto sale de la ayuda local / imagenes de la instalacion y esta sin probar.
Tipos (DeviceType) segun la API IPC; en la 6.0.1 se confirmo: router 0, switch 1,
AP 7, PC 8, server 9, laptop 17.
"""

DEVICE_TYPES = {
    "router": 0, "switch": 1, "cloud": 2, "bridge": 3, "hub": 4, "repeater": 5,
    "splitter": 6, "accesspoint": 7, "pc": 8, "server": 9, "printer": 10,
    "wireless_router": 11, "ip_phone": 12, "dsl_modem": 13, "cable_modem": 14,
    "multilayer_switch": 16, "laptop": 17, "tablet": 18, "pda": 19,
    "wireless_end_device": 20, "wired_end_device": 21, "tv": 22,
}

# modelo -> (tipo, verificado)
_MODELS = {
    # routers
    "2911": ("router", True), "1841": ("router", False), "1941": ("router", False),
    "2620XM": ("router", False), "2621XM": ("router", False), "2811": ("router", True),
    "2901": ("router", False), "Router-PT": ("router", False),
    "Router-PT-Empty": ("router", True),
    # switches
    "2960-24TT": ("switch", True), "2950-24": ("switch", False),
    "2950T-24": ("switch", False), "Switch-PT": ("switch", False),
    "Switch-PT-Empty": ("switch", True), "3560-24PS": ("multilayer_switch", False),
    # finales y otros
    "PC-PT": ("pc", True), "Server-PT": ("server", True), "Laptop-PT": ("laptop", True),
    "AccessPoint-PT": ("accesspoint", True), "AccessPoint-PT-A": ("accesspoint", True),
    "Printer-PT": ("printer", False), "Hub-PT": ("hub", False),
    "Repeater-PT": ("repeater", False), "Bridge-PT": ("bridge", False),
    "Cloud-PT": ("cloud", False), "Linksys-WRT300N": ("wireless_router", False),
    "7960": ("ip_phone", False), "DSL-Modem-PT": ("dsl_modem", False),
    "Cable-Modem-PT": ("cable_modem", False), "TabletPC-PT": ("tablet", False),
    "Pda-PT": ("pda", False), "WirelessEndDevice-PT": ("wireless_end_device", False),
    "WiredEndDevice-PT": ("wired_end_device", False), "TV-PT": ("tv", False),
}

_BY_UPPER = {m.upper(): m for m in _MODELS}

# Tipos que arrancan con IOS y necesitan skipBoot() para estar listos al instante.
BOOTING_TYPES = (0, 1, 16)

# Modelos "Empty" nacen SIN puertos: hay que apagarlos y meterles modulos. Firma comprobada en una
# 6.0.1.0011 real: device.addModule("<ranura>", 4, "PT-SWITCH-NM-1CFE") -> true (4 = tipo de modulo,
# que PT confirma en el evento moduleAdded). Cada modulo 1CFE aporta 1 FastEthernet<ranura>/1.
# Con 2 argumentos (ranura, modelo) PT responde 'Invalid arguments' y, con la ventana Debug abierta, se cuelga.
# Router-PT-Empty (comprobado igual): tipo de modulo 3, 10 ranuras, puertos "<Tipo><ranura>/0". Modelos que acepta:
# PT-ROUTER-NM-1CFE (FastEthernet cobre), -1CGE (GigabitEthernet), -1S (Serial), -1FFE / -1FGE (fibra),
# -1CE (Ethernet), -1SS (Serial), -1AM (Modem). Por defecto se le ponen 2 FastEthernet; pide los que hagan falta con `ports`.
EMPTY_MODULES = {
    "Switch-PT-Empty": {"module": "PT-SWITCH-NM-1CFE", "type": 4, "slots": 10, "default": 10},
    "Router-PT-Empty": {"module": "PT-ROUTER-NM-1CFE", "type": 3, "slots": 10, "default": 2},
}


# Modulos sueltos comprobados en la 6.0.1 real: modelo de equipo -> (tipo de modulo, {alias: modelo de modulo}).
# Lista completa de la pestana Physical (2026-10-22). Switch: 1CE, 1CFE, 1CGE, 1FFE, 1FGE (todos instalados por API: Ethernet7/1,
# GigabitEthernet6/1...). Router: 1AM, 1CE, 1CFE, 1CGE, 1FFE, 1FGE, 1S, 1SS (1SS sin instalar por API).
MODULES = {
    "Switch-PT-Empty": (4, {"fastethernet": "PT-SWITCH-NM-1CFE", "fiber": "PT-SWITCH-NM-1FFE",
                            "gigabit": "PT-SWITCH-NM-1CGE", "gigabit-fiber": "PT-SWITCH-NM-1FGE", "ethernet": "PT-SWITCH-NM-1CE"}),
    "Router-PT-Empty": (3, {"fastethernet": "PT-ROUTER-NM-1CFE", "fiber": "PT-ROUTER-NM-1FFE",
                            "gigabit": "PT-ROUTER-NM-1CGE", "gigabit-fiber": "PT-ROUTER-NM-1FGE",
                            "serial": "PT-ROUTER-NM-1S", "ethernet": "PT-ROUTER-NM-1CE", "modem": "PT-ROUTER-NM-1AM"}),
}


def empty_module_spec(model):
    """Datos para poblar un modelo Empty, o None si el modelo trae sus propios puertos."""
    return EMPTY_MODULES.get(model)

CABLES = {
    "straight": 8100, "cross": 8101, "crossover": 8101, "roll": 8102,
    "fiber": 8103, "phone": 8104, "cable": 8105, "serial": 8106, "auto": 8107,
    "console": 8108, "wireless": 8109, "coaxial": 8110, "usb": 8113,
}


class CatalogError(ValueError):
    pass


def resolve_model(model):
    """Devuelve (modelo_canonico, device_type, verificado)."""
    key = str(model).strip().upper()
    if key not in _BY_UPPER:
        raise CatalogError(
            "Modelo desconocido: %r. Modelos: %s" % (model, ", ".join(sorted(_MODELS))))
    canon = _BY_UPPER[key]
    kind, verified = _MODELS[canon]
    return canon, DEVICE_TYPES[kind], verified


def cable_code(name):
    if isinstance(name, int):
        return name
    key = str(name).strip().lower()
    if key.isdigit():
        return int(key)
    if key not in CABLES:
        raise CatalogError("Cable desconocido: %r. Opciones: %s" % (name, ", ".join(sorted(CABLES))))
    return CABLES[key]


def catalog_text():
    lines = ["modelo | tipo | verificado en 6.0.1"]
    for m in sorted(_MODELS):
        kind, ok = _MODELS[m]
        lines.append("%s | %s (%d) | %s" % (m, kind, DEVICE_TYPES[kind], "si" if ok else "no"))
    lines.append("")
    lines.append("cables: " + ", ".join("%s=%d" % kv for kv in sorted(CABLES.items(), key=lambda kv: kv[1])))
    lines.append("")
    lines.append("modulos (pt_add_module kind=...):")
    for model in sorted(MODULES):
        lines.append("  %s: %s" % (model, ", ".join("%s=%s" % kv for kv in sorted(MODULES[model][1].items()))))
    return "\n".join(lines)
