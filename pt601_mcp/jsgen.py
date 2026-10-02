"""Generadores de JavaScript para el Script Engine de PT 6.0.1 (Qt Script ~ES3).

Reglas: sin let/const/flechas/JSON; el resultado es siempre TEXTO (el motor hace
String(resultado)). Los valores de usuario entran SIEMPRE por `q()` (literal de
cadena JSON, que es JavaScript valido y escapa comillas, saltos y unicode).
"""
import json

PRE = ("var lw = ipc.appWindow().getActiveWorkspace().getLogicalWorkspace();"
       " var net = ipc.network();")


def q(value):
    return json.dumps(str(value))


def wrap(body):
    return "(function () { %s %s })()" % (PRE, body)


def get_dev(var, name):
    return ('var %s = null; try { %s = net.getDevice(%s); } catch (e) { %s = null; }'
            ' if (!%s) { return "ERROR: no existe el dispositivo " + %s; }'
            % (var, var, q(name), var, var, q(name)))


def status():
    return wrap('return ipc.appWindow().getVersion() + "|" + net.getDeviceCount();')


def list_devices():
    return wrap(
        'var o = []; for (var i = 0; i < net.getDeviceCount(); i++) {'
        ' var d = net.getDeviceAt(i);'
        ' o.push([d.getName(), d.getModel(), d.getType(), d.getPower(), d.getPortCount()].join("\\t")); }'
        ' return o.join("\\n");')


def add_device(name, model, dtype, x, y, skip_boot, modules=None):
    """`modules` = (modelo_modulo, tipo_modulo, n_ranuras) para los modelos Empty (sin puertos)."""
    move = ("d.moveToLocation(%d, %d);" % (int(x), int(y))) if x is not None and y is not None else ""
    boot = "try { d.skipBoot(); } catch (e2) {}" if skip_boot else ""
    mods = ""
    if modules:
        mmodel, mtype, count = modules
        # Se apaga, se llena ranura a ranura (la firma de 3 argumentos es la unica valida en la 6.0.1) y se enciende.
        mods = ('d.setPower(false); var nm = 0;'
                ' for (var s = 0; s < %d; s++) { if (d.addModule(String(s), %d, %s)) { nm++; } }'
                ' d.setPower(true);'
                ' if (nm != %d) { return "ERROR: solo se pudieron poner " + nm + " de %d modulos en " + %s; }'
                % (int(count), int(mtype), q(mmodel), int(count), int(count), q(name)))
    boot = mods + " " + boot
    return wrap(
        'var ex = null; try { ex = net.getDevice(%s); } catch (e) { ex = null; }'
        ' if (ex) { return "ERROR: ya existe un dispositivo llamado " + %s; }'
        ' var auto = lw.addDevice(%d, %s);'
        ' if (!auto) { return "ERROR: PT no creo el dispositivo (modelo " + %s + ")"; }'
        ' var d = net.getDevice(auto);'
        ' if (auto != %s) { d.setName(%s); }'
        ' %s %s'
        ' return "OK " + auto + " -> " + %s;'
        % (q(name), q(name), dtype, q(model), q(model), q(name), q(name), move, boot, q(name)))


def remove_device(name):
    return wrap(
        'var n = 0; while (n < 10 && lw.removeDevice(%s)) { n++; } return String(n);' % q(name))


def move_device(name, x, y):
    return wrap(get_dev("d", name) + ' d.moveToLocation(%d, %d); return "OK";' % (int(x), int(y)))


def add_link(d1, p1, d2, p2, code):
    return wrap(
        get_dev("a", d1) + get_dev("b", d2) +
        ' return String(lw.createLink(%s, %s, %s, %s, %d));' % (q(d1), q(p1), q(d2), q(p2), int(code)))


def set_ip(name, port, ip, mask, gateway, dhcp):
    parts = [get_dev("d", name),
             'var p = d.getPort(%s); if (!p) { return "ERROR: no existe el puerto " + %s; }' % (q(port), q(port))]
    if dhcp:
        parts.append('p.setDhcpClientFlag(true);')
    else:
        parts.append('p.setIpSubnetMask(%s, %s);' % (q(ip), q(mask)))
        if gateway:
            parts.append('p.setDefaultGateway(%s);' % q(gateway))
    parts.append('return p.getIpAddress() + " / " + p.getSubnetMask();')
    return wrap(" ".join(parts))


def cli(name, commands, answer_dialog):
    cmds = ", ".join(q(c) for c in commands)
    dialog = ('if (pr.indexOf("[yes/no]") >= 0) { cl.enterCommand("no"); cl.enterCommand(""); }'
              if answer_dialog else "")
    return wrap(
        get_dev("d", name) +
        ' var cl = d.getCommandLine(); if (!cl) { return "ERROR: sin consola"; }'
        ' var before = String(cl.getOutput()).length; var pr = String(cl.getPrompt());'
        ' %s var cmds = [%s]; for (var i = 0; i < cmds.length; i++) { cl.enterCommand(cmds[i]); }'
        ' var o = String(cl.getOutput()); var neu = o.length >= before ? o.substring(before) : o;'
        ' return "PROMPT=" + cl.getPrompt() + "\\n" + neu;' % (dialog, cmds))


def output_length(name):
    return wrap(get_dev("d", name) +
                ' var cl = d.getCommandLine(); if (!cl) { return "ERROR: sin consola"; }'
                ' return String(String(cl.getOutput()).length);')


def read_output(name, start, tail):
    if start is not None:
        tail_js = ('var s = %d; if (o.length < s) { s = 0; } return o.substring(s);' % int(start))
    else:
        tail_js = 'return o.substring(Math.max(0, o.length - %d));' % int(tail)
    return wrap(get_dev("d", name) +
                ' var cl = d.getCommandLine(); if (!cl) { return "ERROR: sin consola"; }'
                ' var o = String(cl.getOutput()); %s' % tail_js)


def send_only(name, command):
    return wrap(get_dev("d", name) +
                ' var cl = d.getCommandLine(); if (!cl) { return "ERROR: sin consola"; }'
                ' cl.enterCommand(%s); return "enviado";' % q(command))


# ---------------------------------------------------------------------------
# Nuevas piezas: puertos, cableado automatico, introspeccion, servicios, limpieza
# ---------------------------------------------------------------------------

def list_ports(name):
    return wrap(
        get_dev("d", name) +
        ' var o = []; for (var i = 0; i < d.getPortCount(); i++) { var p = d.getPortAt(i);'
        ' var l = null; try { l = p.getLink(); } catch (e1) {}'
        ' var up = ""; try { up = p.isPortUp(); } catch (e2) {}'
        ' o.push([p.getName(), l ? "conectado" : "libre", up].join("\\t")); } return o.join("\\n");')


_CONNECT_HELPERS = (
    ' var SKIP = ["Console","Aux","Serial","Wireless","Vlan","Loopback","USB","Modem","Async","Rs232","Coaxial","Cellular"];'
    ' function skipPort(n) { for (var k = 0; k < SKIP.length; k++) { if (n.indexOf(SKIP[k]) == 0) { return true; } } return false; }'
    ' function pref(n) { if (n.indexOf("FastEthernet") == 0) { return 1; } if (n.indexOf("GigabitEthernet") == 0) { return 2; }'
    ' if (n.indexOf("Ethernet") == 0) { return 0; } return 3; }'
    ' function freePorts(d) { var c = []; for (var i = 0; i < d.getPortCount(); i++) { var p = d.getPortAt(i); var n = String(p.getName());'
    ' if (skipPort(n)) { continue; } var l = null; try { l = p.getLink(); } catch (e) {} if (l) { continue; }'
    ' c.push({ n: n, s: pref(n) * 1000 + i }); }'
    ' c.sort(function (a, b) { return a.s - b.s; }); var r = []; for (var j = 0; j < c.length; j++) { r.push(c[j].n); } return r; }'
)


def connect_auto(d1, d2, code, port1, port2):
    forced1 = ("[%s]" % q(port1)) if port1 else "freePorts(a)"
    forced2 = ("[%s]" % q(port2)) if port2 else "freePorts(b)"
    return wrap(
        get_dev("a", d1) + get_dev("b", d2) + _CONNECT_HELPERS +
        ' var ca = %s; var cb = %s;'
        ' if (ca.length == 0) { return "ERROR: " + %s + " no tiene puertos Ethernet libres"; }'
        ' if (cb.length == 0) { return "ERROR: " + %s + " no tiene puertos Ethernet libres"; }'
        # 8107 (auto) lo rechaza PT en los puertos de modulo de los modelos Empty (comprobado en la 6.0.1 real,
        # con 8100 si funciona): si falla, se prueba el cable que toca (cruzado entre equipos iguales, recto si no).
        ' var codes = [%d]; if (%d == 8107) { codes = (a.getType() == b.getType()) ? [8107, 8101, 8100] : [8107, 8100, 8101]; }'
        ' for (var i = 0; i < ca.length && i < 3; i++) { for (var j = 0; j < cb.length && j < 3; j++) {'
        ' for (var k = 0; k < codes.length; k++) {'
        ' if (lw.createLink(%s, ca[i], %s, cb[j], codes[k])) { return "OK " + %s + ":" + ca[i] + " <-> " + %s + ":" + cb[j]; } } } }'
        ' return "ERROR: PT rechazo el cable " + %s + " <-> " + %s + " (puertos probados: " + ca.slice(0, 3).join(",") + " / " + cb.slice(0, 3).join(",") + ")";'
        % (forced1, forced2, q(d1), q(d2), int(code), int(code), q(d1), q(d2), q(d1), q(d2), q(d1), q(d2)))


def describe(name, process, port):
    pick = "var obj = d; var label = \"dispositivo\";"
    if process:
        pick = ('var obj = null; try { obj = d.getProcess(%s); } catch (e) { obj = null; }'
                ' if (!obj) { return "ERROR: el dispositivo no tiene el proceso " + %s; } var label = "proceso " + %s;'
                % (q(process), q(process), q(process)))
    elif port:
        pick = ('var obj = d.getPort(%s); if (!obj) { return "ERROR: no existe el puerto " + %s; } var label = "puerto " + %s;'
                % (q(port), q(port), q(port)))
    return wrap(
        get_dev("d", name) + " " + pick +
        ' var k = []; for (var m in obj) { k.push(m); } k.sort();'
        ' return label + " (" + k.length + " miembros): " + k.join(", ");')


_PROC_FINDER = (
    ' var proc = null; var cands = %s;'
    ' for (var ci = 0; ci < cands.length && !proc; ci++) { try { proc = d.getProcess(cands[ci]); } catch (e0) { proc = null; } }'
    ' if (!proc) { return "ERROR: no encontre el servicio %s en " + %s + " (prueba pt_describe con process=...)"; }'
    ' var members = []; for (var mk in proc) { members.push(mk); } members.sort();'
    ' var log = [];'
)


def _attempt(label, expr):
    return (' if (!done) { try { %s; done = true; log.push(%s); } catch (e) { log.push(%s + " fallo"); } }'
            % (expr, q(label), q(label)))


def dhcp_server(name, gateway, dns, start_ip, end_ip, mask):
    """DHCP de un Server-PT en la 6.0.1 real: el proceso se llama "DhcpServer" (no DhcpServerMain) y trae un pool
    por defecto ("serverPool") con setStartIp/setEndIp/setDefaultRouter/setDnsServerIp. No existe addNewPool y
    setNetworkMask("255.255.255.0") da 'Invalid arguments' (y con Debug abierta cuelga el motor): no se llama; se
    comprueba que la mascara pedida coincida con la del pool."""
    sets = ["pool.setStartIp(%s);" % q(start_ip), "pool.setEndIp(%s);" % q(end_ip)]
    if gateway:
        sets.append("pool.setDefaultRouter(%s);" % q(gateway))
    if dns:
        sets.append("pool.setDnsServerIp(%s);" % q(dns))
    return wrap(
        get_dev("d", name) +
        ' var proc = null; try { proc = d.getProcess("DhcpServer"); } catch (e0) { proc = null; }'
        ' if (!proc) { return "ERROR: " + %s + " no tiene el servicio DhcpServer (es un Server-PT?)"; }'
        ' if (proc.getPoolCount() < 1) { return "ERROR: el servicio DHCP de " + %s + " no tiene ningun pool"; }'
        ' proc.setEnable(true);'
        ' var pool = proc.getPoolAt(0);'
        ' if (String(pool.getSubnetMask()) != %s) { return "ERROR: la 6.0.1 no permite cambiar la mascara del pool (es " + pool.getSubnetMask() + ", pedida " + %s + ")"; }'
        ' %s'
        ' return "OK pool " + pool.getDhcpPoolName() + ": " + pool.getStartIp() + " - " + pool.getEndIp() + " mascara " + pool.getSubnetMask()'
        ' + " router " + pool.getDefaultRouter() + " dns " + pool.getDnsServerIp();'
        % (q(name), q(name), q(mask), q(mask), " ".join(sets)))


def dns_server(name, records):
    pairs = "[" + ", ".join("[%s, %s]" % (q(r["name"]), q(r["ip"])) for r in records) + "]"
    body = (get_dev("d", name) + _PROC_FINDER % ('["DnsServerMain","DNSServerMain","DnsServer"]', "DNS", q(name)) +
            ' try { if (typeof proc.setEnable == "function") { proc.setEnable(true); log.push("setEnable"); } } catch (e1) { log.push("setEnable fallo"); }'
            ' var recs = %s; var okn = 0; var bad = [];'
            ' for (var i = 0; i < recs.length; i++) { var done = false;' % pairs +
            _attempt("addIpAddress", "proc.addIpAddress(recs[i][0], recs[i][1])") +
            _attempt("addRecord", "proc.addRecord(recs[i][0], recs[i][1])") +
            ' if (done) { okn++; } else { bad.push(recs[i][0]); } }'
            ' if (bad.length > 0) { return "ERROR: registros no creados: " + bad.join(", ") + ". Miembros del proceso: " + members.join(", "); }'
            ' return "OK " + okn + " registro(s) DNS";')
    return wrap(body)


def clear_workspace():
    return wrap(
        'var names = []; for (var i = 0; i < net.getDeviceCount(); i++) { names.push(net.getDeviceAt(i).getName()); }'
        ' var n = 0; for (var j = 0; j < names.length; j++) { var guard = 0; while (guard < 10 && lw.removeDevice(names[j])) { n++; guard++; } }'
        ' return String(n) + " borrados, quedan " + net.getDeviceCount();')
