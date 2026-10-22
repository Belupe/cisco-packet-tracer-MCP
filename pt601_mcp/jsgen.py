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


def _move(x, y):
    """Coloca `d` de modo que getXCoordinate/getYCoordinate devuelvan (x, y). En la 6.0.1 real moveToLocation
    recibe la esquina del icono y los getters devuelven su centro (servidor +16,+26; switch +25,+12): se mide el
    desfase tras un primer movimiento y se corrige. Asi las coordenadas de pt_snapshot sirven tal cual para colocar.
    OJO: solo vale para un equipo ya asentado. Uno recien creado se recoloca solo (x menos medio icono) cuando
    termina el script que lo creo, asi que add_device lo deja aproximado y tools lo ajusta en una segunda llamada."""
    return ("d.moveToLocation(%d, %d); d.moveToLocation(%d - (d.getXCoordinate() - %d), %d - (d.getYCoordinate() - %d));"
            % (int(x), int(y), int(x), int(x), int(y), int(y)))


def status():
    return wrap('var aw = ipc.appWindow(); return aw.getVersion() + "|" + net.getDeviceCount() + "|" + aw.isRealtimeMode();')


def realtime():
    """Vuelve al modo Tiempo real (comprobado en la 6.0.1: getRSSwitch().showRealtimeMode())."""
    return wrap('var aw = ipc.appWindow(); aw.getRSSwitch().showRealtimeMode(); return String(aw.isRealtimeMode());')


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
    return wrap(get_dev("d", name) + ' ' + _move(x, y) +
                ' return "OK " + d.getXCoordinate() + "," + d.getYCoordinate();')


# 6.0.1 real: cada equipo tiene una posicion FISICA (<COORD_SETTINGS>). Los que ya venian en un .pkt estan lejos
# (p. ej. 1918,1918) y los creados por IPC nacen en 0,0. Un cable de cobre entre equipos tan separados se crea pero
# queda SIN SENAL (los dos puertos caidos); la fibra si funciona. moveToLocInPhysicalWS devuelve false: no se puede
# acercar el equipo por IPC, asi que se avisa.
_FAR = (
    ' function physXY(d) { var x = String(d.serializeToXml()); var mx = /<X_COORD>([^<]*)</.exec(x); var my = /<Y_COORD>([^<]*)</.exec(x);'
    ' return [mx ? parseFloat(mx[1]) : 0, my ? parseFloat(my[1]) : 0]; }'
    ' function farWarn(a, b, code) { if (code == 8103) { return ""; } var p = physXY(a); var r = physXY(b);'
    ' var dist = Math.sqrt((p[0] - r[0]) * (p[0] - r[0]) + (p[1] - r[1]) * (p[1] - r[1]));'
    ' if (dist <= 100) { return ""; }'
    ' return "\\nAVISO: los dos equipos estan a " + Math.round(dist) + " m en el espacio fisico de PT (uno venia en el archivo y el otro es nuevo):'
    ' un cable de cobre queda SIN SENAL. Usa fibra (modulos PT-...-NM-1FFE + cable fiber) o crea toda la red en un archivo nuevo."; }'
)


def add_link(d1, p1, d2, p2, code):
    return wrap(
        get_dev("a", d1) + get_dev("b", d2) + _FAR +
        ' var ok = lw.createLink(%s, %s, %s, %s, %d);'
        ' return String(ok) + (ok ? farWarn(a, b, %d) : "");' % (q(d1), q(p1), q(d2), q(p2), int(code), int(code)))


def remove_link(name, port):
    return wrap(
        get_dev("d", name) +
        ' var p = d.getPort(%s); if (!p) { return "ERROR: no existe el puerto " + %s; }'
        ' if (!p.getLink()) { return "ERROR: el puerto " + %s + " de " + %s + " no tiene cable"; }'
        ' return String(lw.deleteLink(%s, %s));' % (q(port), q(port), q(port), q(name), q(name), q(port)))


def remove_module(name, slot):
    """Quita el modulo de una ranura (firma real de la 6.0.1: removeModule("<ranura>"), con el equipo apagado)."""
    return wrap(
        get_dev("d", name) +
        ' var n0 = d.getPortCount(); d.setPower(false); var r = d.removeModule(%s); d.setPower(true);'
        # Sin skipBoot el equipo arranca en tiempo real (minutos) y mientras tanto sus puertos no dan servicio.
        ' try { d.skipBoot(); } catch (e9) {}'
        ' if (!r) { return "ERROR: PT no quito el modulo de la ranura " + %s + " de " + %s; }'
        ' return "OK puertos: " + n0 + " -> " + d.getPortCount();' % (q(int(slot)), q(int(slot)), q(name)))


def add_module(name, slot, mtype, model, count=1):
    """Anade `count` modulos en ranuras seguidas desde `slot` a un equipo que ya existe, con UN solo apagado y encendido
    (firma real: addModule("<ranura>", tipo, modelo), apagado). Si una ranura falla, para ahi y lo dice."""
    return wrap(
        get_dev("d", name) +
        ' var before = {}; for (var i = 0; i < d.getPortCount(); i++) { before[d.getPortAt(i).getName()] = 1; }'
        ' d.setPower(false); var bad = -1;'
        ' for (var s = %d; s < %d; s++) { if (!d.addModule(String(s), %d, %s)) { bad = s; break; } }'
        ' d.setPower(true); try { d.skipBoot(); } catch (e9) {}'
        ' var neu = []; for (var j = 0; j < d.getPortCount(); j++) { var n = d.getPortAt(j).getName(); if (!before[n]) { neu.push(n); } }'
        ' if (bad >= 0) { return "ERROR: PT no acepto el modulo " + %s + " en la ranura " + bad + " de " + %s'
        ' + " (ranura ocupada o modelo de otro tipo de equipo). Puertos nuevos antes del fallo: " + (neu.join(", ") || "ninguno"); }'
        ' return "OK puerto" + (neu.length > 1 ? "s nuevos: " : " nuevo: ") + neu.join(", ");'
        % (int(slot), int(slot) + int(count), int(mtype), q(model), q(model), q(name)))


def set_ip(name, port, ip, mask, gateway, dhcp, dns=None):
    parts = [get_dev("d", name),
             'var p = d.getPort(%s); if (!p) { return "ERROR: no existe el puerto " + %s; }' % (q(port), q(port))]
    if dhcp:
        parts.append('p.setDhcpClientFlag(true);')
    else:
        parts.append('p.setIpSubnetMask(%s, %s);' % (q(ip), q(mask)))
        if gateway:
            # 6.0.1 real: el del puerto solo cambia <PORT_GATEWAY>; el que se ve en "IP Configuration" es el del
            # dispositivo (<GATEWAY>), que tienen PC/portatil/servidor. Se ponen los dos.
            parts.append('p.setDefaultGateway(%s);' % q(gateway))
            parts.append('if (typeof d.setDefaultGateway == "function") { d.setDefaultGateway(%s); }' % q(gateway))
        if dns:
            parts.append('var dc = (typeof d.getProcess == "function") ? d.getProcess("DnsClient") : null;'
                         ' if (!dc) { return "ERROR: " + %s + " no admite servidor DNS (sin DnsClient)"; }'
                         ' dc.setServerIp(%s);' % (q(name), q(dns)))
    parts.append('return p.getIpAddress() + " / " + p.getSubnetMask();')
    return wrap(" ".join(parts))


def rename_device(name, new_name):
    return wrap(
        get_dev("d", name) +
        ' var ex = null; try { ex = net.getDevice(%s); } catch (e) { ex = null; }'
        ' if (ex) { return "ERROR: ya existe un dispositivo llamado " + %s; }'
        ' d.setName(%s); return "OK " + %s + " -> " + d.getName();'
        % (q(new_name), q(new_name), q(new_name), q(name)))


def cli(name, commands, answer_dialog):
    cmds = ", ".join(q(c) for c in commands)
    dialog = ('if (pr.indexOf("[yes/no]") >= 0) { cl.enterCommand("no"); cl.enterCommand(""); }'
              if answer_dialog else "")
    return wrap(
        get_dev("d", name) +
        ' var cl = d.getCommandLine(); if (!cl) { return "ERROR: sin consola"; }'
        # La salida nueva se localiza por una marca (el final de lo que habia antes) y no por longitud: PT recorta el
        # historial de la consola cuando crece, y entonces devolvia paginas de salida vieja.
        ' var o0 = String(cl.getOutput()); var mark = o0.substring(Math.max(0, o0.length - 160)); var pr = String(cl.getPrompt());'
        # 6.0.1 real: una consola sin usar esta en modo "logout" con prompt vacio ("Press RETURN to get started")
        # y se traga el primer comando. Se la despierta con un Enter.
        ' if (pr == "" || String(cl.getMode()) == "logout") { cl.enterCommand(""); pr = String(cl.getPrompt()); }'
        # Si la consola se quedo dentro de "configure terminal" (alguien la dejo asi), se sale antes de empezar:
        # "enable" ahi da error y lo demas caeria en el modo equivocado.
        ' if (pr.indexOf("(config") >= 0) { cl.enterCommand("end"); pr = String(cl.getPrompt()); }'
        ' %s var cmds = [%s]; for (var i = 0; i < cmds.length; i++) { cl.enterCommand(cmds[i]); }'
        ' var o = String(cl.getOutput()); var at = mark ? o.lastIndexOf(mark) : -1;'
        ' var neu = at >= 0 ? o.substring(at + mark.length) : o.substring(Math.max(0, o.length - 4000));'
        ' return "PROMPT=" + cl.getPrompt() + "\\n" + neu;' % (dialog, cmds))


def running_config(name):
    """Configuracion en ejecucion de un router/switch sacada de serializeToXml (<RUNNINGCONFIG>): entera y sin
    el --More-- de la consola (la 6.0.1 no admite 'terminal length 0')."""
    return wrap(
        get_dev("d", name) +
        ' var x = String(d.serializeToXml()); var a = x.indexOf("<RUNNINGCONFIG>"); var b = x.indexOf("</RUNNINGCONFIG>");'
        ' if (a < 0 || b < 0) { return "ERROR: " + %s + " no tiene configuracion IOS (no es router ni switch)"; }'
        ' var ls = x.substring(a + 15, b).replace(/<\\/?LINE>/g, "").split("\\n"); var o = [];'
        ' for (var i = 0; i < ls.length; i++) { var s = ls[i].replace(/^\\s+|\\s+$/g, "");'
        ' s = s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");'
        ' if (s && s != "!") { o.push((/^(ip address|duplex|speed|switchport|login|no shutdown|shutdown|encapsulation|description) ?/.test(s) ? " " : "") + s); } }'
        ' return o.join("\\n");' % q(name))


def http_get(name, url):
    """Navegador del equipo (proceso HttpClient): go(url) lanza la peticion; la pagina llega despues."""
    return wrap(
        get_dev("d", name) +
        ' var h = (typeof d.getProcess == "function") ? d.getProcess("HttpClient") : null;'
        ' if (!h) { return "ERROR: " + %s + " no tiene navegador (HttpClient)"; }'
        ' return String(h.go(%s));' % (q(name), q(url)))


def http_last(name):
    return wrap(get_dev("d", name) + ' return "LEN=" + String(d.getProcess("HttpClient").getLastPageContent()).length + "\\n"'
                ' + String(d.getProcess("HttpClient").getLastPageContent());')


def dhcp_off(name, port):
    return wrap(get_dev("d", name) + ' var p = d.getPort(%s); if (p) { p.setDhcpClientFlag(false); } return "OK";' % q(port))


_ROUTER_READY = (
    # Deja la consola de un router en modo privilegiado: sale de --More--, la despierta, sale de (config) y hace enable.
    ' function ready(cl) { var out = String(cl.getOutput()); if (out.substring(Math.max(0, out.length - 12)).indexOf("More") >= 0) { cl.enterCommand("q"); }'
    ' var pr = String(cl.getPrompt()); if (pr == "" || String(cl.getMode()) == "logout") { cl.enterCommand(""); pr = String(cl.getPrompt()); }'
    ' if (pr.indexOf("(config") >= 0) { cl.enterCommand("end"); pr = String(cl.getPrompt()); }'
    ' if (pr.indexOf("#") < 0) { cl.enterCommand("enable"); } }'
)


def routing_audit(save):
    """Revisa las tablas de TODOS los routers: saca las redes de las interfaces de todos ellos y pregunta a cada router
    por cada red con 'show ip route <red>' (salida corta, sin --More--). Lineas: router<TAB>conocidas<TAB>total<TAB>
    defecto<TAB>guardado<TAB>redes que faltan."""
    return wrap(
        _ROUTER_READY +
        ' function toInt(a) { var p = String(a).split("."); return ((parseInt(p[0], 10) * 256 + parseInt(p[1], 10)) * 256 + parseInt(p[2], 10)) * 256 + parseInt(p[3], 10); }'
        ' function toIp(n) { function md(v) { return v - Math.floor(v / 256) * 256; } return [md(Math.floor(n / 16777216)), md(Math.floor(n / 65536)), md(Math.floor(n / 256)), md(n)].join("."); }'
        ' var routers = []; var nets = []; var seen = {};'
        ' for (var i = 0; i < net.getDeviceCount(); i++) { var d = net.getDeviceAt(i); if (d.getType() != 0) { continue; } routers.push(d);'
        ' for (var j = 0; j < d.getPortCount(); j++) { var p = d.getPortAt(j); var ip = String(p.getIpAddress()); var mk = String(p.getSubnetMask());'
        ' if (!ip || ip == "0.0.0.0" || !mk || mk == "0.0.0.0") { continue; }'
        ' var a = toInt(ip); var m = toInt(mk); var size = 4294967296 - m; var nw = toIp(Math.floor(a / size) * size);'
        ' if (!seen[nw]) { seen[nw] = 1; nets.push(nw); } } }'
        ' var o = ["REDES\\t" + nets.join(",")];'
        ' for (var r = 0; r < routers.length; r++) { var cl = routers[r].getCommandLine(); ready(cl); var miss = [];'
        ' for (var k = 0; k < nets.length; k++) { var n0 = String(cl.getOutput()).length; cl.enterCommand("show ip route " + nets[k]);'
        ' if (String(cl.getOutput()).substring(n0).indexOf("not in table") >= 0) { miss.push(nets[k]); } }'
        ' var n1 = String(cl.getOutput()).length; cl.enterCommand("show ip route 0.0.0.0");'
        ' var def = String(cl.getOutput()).substring(n1).indexOf("not in table") < 0; var saved = "";'
        ' if (%s) { var n2 = String(cl.getOutput()).length; cl.enterCommand("write memory"); saved = String(cl.getOutput()).substring(n2).indexOf("[OK]") >= 0 ? "si" : "NO"; }'
        ' o.push([routers[r].getName(), nets.length - miss.length, nets.length, def ? "si" : "no", saved, miss.join(",")].join("\\t")); }'
        ' return o.join("\\n");' % ("true" if save else "false"))


def host_ips(names):
    """IP del primer puerto con direccion de cada equipo: lineas nombre<TAB>ip (ip vacia si no existe o no tiene)."""
    arr = "[" + ", ".join(q(n) for n in names) + "]"
    return wrap('var ns = %s; var o = []; for (var i = 0; i < ns.length; i++) { var d = null; try { d = net.getDevice(ns[i]); } catch (e) {}'
                ' var ip = ""; if (d) { for (var j = 0; j < d.getPortCount() && !ip; j++) { var p = d.getPortAt(j);'
                ' if (typeof p.getIpAddress == "function") { var a = String(p.getIpAddress()); if (a && a != "0.0.0.0") { ip = a; } } } }'
                ' o.push(ns[i] + "\\t" + ip); } return o.join("\\n");' % arr)


def ping_launch(pairs):
    """Lanza a la vez un ping por cada (origen, ip destino); devuelve origen<TAB>longitud de consola previa."""
    arr = "[" + ", ".join("[%s, %s]" % (q(a), q(ip)) for a, ip in pairs) + "]"
    return wrap('var ps = %s; var o = []; for (var i = 0; i < ps.length; i++) { var cl = net.getDevice(ps[i][0]).getCommandLine();'
                ' var n = String(cl.getOutput()).length; cl.enterCommand("ping " + ps[i][1]); o.push(ps[i][0] + "\\t" + n); }'
                ' return o.join("\\n");' % arr)


def ping_collect(marks):
    """Para cada (origen, longitud previa): paquetes recibidos, o -1 si el ping aun no ha terminado."""
    arr = "[" + ", ".join("[%s, %d]" % (q(a), int(n)) for a, n in marks) + "]"
    return wrap('var ms = %s; var o = []; for (var i = 0; i < ms.length; i++) { var out = String(net.getDevice(ms[i][0]).getCommandLine().getOutput());'
                ' var s = out.length >= ms[i][1] ? out.substring(ms[i][1]) : out; var r = -1;'
                ' if (s.indexOf("could not find host") >= 0) { r = 0; }'
                ' var m = /Received = (\\d+)/.exec(s); if (m) { r = parseInt(m[1], 10); }'
                ' o.push(ms[i][0] + "\\t" + r); } return o.join("\\n");' % arr)


def port_ip(name, port):
    return wrap(get_dev("d", name) + ' var p = d.getPort(%s); return p ? String(p.getIpAddress()) : "";' % q(port))


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
        get_dev("a", d1) + get_dev("b", d2) + _CONNECT_HELPERS + _FAR +
        ' var ca = %s; var cb = %s;'
        ' if (ca.length == 0) { return "ERROR: " + %s + " no tiene puertos Ethernet libres"; }'
        ' if (cb.length == 0) { return "ERROR: " + %s + " no tiene puertos Ethernet libres"; }'
        # 8107 (auto) lo rechaza PT en los puertos de modulo de los modelos Empty (comprobado en la 6.0.1 real,
        # con 8100 si funciona): si falla, se prueba el cable que toca (cruzado entre equipos iguales, recto si no).
        ' var codes = [%d]; if (%d == 8107) { codes = (a.getType() == b.getType()) ? [8107, 8101, 8100] : [8107, 8100, 8101]; }'
        ' for (var i = 0; i < ca.length && i < 3; i++) { for (var j = 0; j < cb.length && j < 3; j++) {'
        ' for (var k = 0; k < codes.length; k++) {'
        ' if (lw.createLink(%s, ca[i], %s, cb[j], codes[k])) { return "OK " + %s + ":" + ca[i] + " <-> " + %s + ":" + cb[j] + farWarn(a, b, codes[k]); } } } }'
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


def dhcp_server(name, gateway, dns, start_ip, end_ip, mask, network, pool_name="serverPool"):
    """DHCP de un Server-PT en la 6.0.1 real (comprobado el 2026-10-22): proceso "DhcpServer"; pool por defecto "serverPool";
    addPool("<nombre>") crea otro; el pool tiene setNetworkMask(red, mascara) -CON DOS ARGUMENTOS: con uno da 'Invalid
    arguments'- y setStartIp/setEndIp/setDefaultRouter/setDnsServerIp. setNetworkMask pone el rango a la red entera, asi que va
    ANTES que el inicio y el final. El pool se busca por nombre recorriendo getPoolAt (la firma de getPool no esta comprobada)."""
    sets = ["pool.setNetworkMask(%s, %s);" % (q(network), q(mask)),
            "pool.setStartIp(%s);" % q(start_ip), "pool.setEndIp(%s);" % q(end_ip)]
    if gateway:
        sets.append("pool.setDefaultRouter(%s);" % q(gateway))
    if dns:
        sets.append("pool.setDnsServerIp(%s);" % q(dns))
    return wrap(
        get_dev("d", name) +
        ' var proc = null; try { proc = d.getProcess("DhcpServer"); } catch (e0) { proc = null; }'
        ' if (!proc) { return "ERROR: " + %s + " no tiene el servicio DhcpServer (es un Server-PT?)"; }'
        ' function find(n) { for (var i = 0; i < proc.getPoolCount(); i++) { if (String(proc.getPoolAt(i).getDhcpPoolName()) == n) { return proc.getPoolAt(i); } } return null; }'
        ' var pool = find(%s); var created = false; if (!pool) { proc.addPool(%s); pool = find(%s); created = true; }'
        ' if (!pool) { return "ERROR: PT no creo el pool " + %s; }'
        ' proc.setEnable(true);'
        ' %s'
        ' return "OK pool " + pool.getDhcpPoolName() + (created ? " (nuevo)" : "") + ": red " + pool.getNetworkAddress() + " mascara " + pool.getSubnetMask()'
        ' + ", " + pool.getStartIp() + " - " + pool.getEndIp() + " router " + pool.getDefaultRouter() + " dns " + pool.getDnsServerIp();'
        % (q(name), q(pool_name), q(pool_name), q(pool_name), q(pool_name), " ".join(sets)))


def dhcp_admin(name, remove_pools, exclude, unexclude):
    """Pools y exclusiones del DHCP de un Server-PT (firmas comprobadas el 2026-10-22): removePool("<nombre>"),
    addExcludedAddress(ini, fin), removeExcludedAddress(ini, fin), getExcludedAddressCount/At(i) -> {first, second}.
    Todas devuelven undefined: se comprueba despues. Al final lista pools y exclusiones."""
    rp = ", ".join(q(p) for p in remove_pools)
    ex = ", ".join("[%s, %s]" % (q(a), q(b)) for a, b in exclude)
    ux = ", ".join("[%s, %s]" % (q(a), q(b)) for a, b in unexclude)
    return wrap(
        get_dev("d", name) +
        ' var dh = null; try { dh = d.getProcess("DhcpServer"); } catch (e0) { dh = null; }'
        ' if (!dh) { return "ERROR: " + %s + " no tiene el servicio DhcpServer (es un Server-PT?)"; }'
        ' function pools() { var r = []; for (var i = 0; i < dh.getPoolCount(); i++) { r.push(String(dh.getPoolAt(i).getDhcpPoolName())); } return r; }'
        ' function excl() { var r = []; for (var i = 0; i < dh.getExcludedAddressCount(); i++) { var e = dh.getExcludedAddressAt(i);'
        ' r.push(e.first + "-" + e.second); } return r; }'
        ' function has(list, v) { for (var i = 0; i < list.length; i++) { if (list[i] == v) { return true; } } return false; }'
        ' var o = []; var RP = [%s]; var EX = [%s]; var UX = [%s];'
        ' for (var a = 0; a < RP.length; a++) { if (!has(pools(), RP[a])) { o.push("pool\\t" + RP[a] + "\\tno existia"); continue; }'
        ' dh.removePool(RP[a]); o.push("pool\\t" + RP[a] + "\\t" + (has(pools(), RP[a]) ? "PT no lo quito" : "quitado")); }'
        ' for (var b = 0; b < UX.length; b++) { var k = UX[b][0] + "-" + UX[b][1]; if (!has(excl(), k)) { o.push("exclusion\\t" + k + "\\tno existia"); continue; }'
        ' dh.removeExcludedAddress(UX[b][0], UX[b][1]); o.push("exclusion\\t" + k + "\\t" + (has(excl(), k) ? "PT no la quito" : "quitada")); }'
        ' for (var c = 0; c < EX.length; c++) { var k2 = EX[c][0] + "-" + EX[c][1]; if (has(excl(), k2)) { o.push("exclusion\\t" + k2 + "\\tya existia"); continue; }'
        ' dh.addExcludedAddress(EX[c][0], EX[c][1]); o.push("exclusion\\t" + k2 + "\\t" + (has(excl(), k2) ? "anadida" : "PT no la anadio")); }'
        ' var ps = []; for (var i = 0; i < dh.getPoolCount(); i++) { var p = dh.getPoolAt(i);'
        ' ps.push(p.getDhcpPoolName() + " " + p.getStartIp() + "-" + p.getEndIp() + "/" + p.getSubnetMask()); }'
        ' o.push("POOLS\\t" + ps.join(", ")); o.push("EXCLUSIONES\\t" + excl().join(", "));'
        ' return o.join("\\n");' % (q(name), rp, ex, ux))


def dns_server(name, records):
    pairs = "[" + ", ".join("[%s, %s]" % (q(r["name"]), q(r["ip"])) for r in records) + "]"
    body = (get_dev("d", name) + _PROC_FINDER % ('["DnsServer","DnsServerMain","DNSServerMain"]', "DNS", q(name)) +
            ' try { if (typeof proc.setEnable == "function") { proc.setEnable(true); log.push("setEnable"); } } catch (e1) { log.push("setEnable fallo"); }'
            ' var recs = %s; var okn = 0; var bad = [];'
            ' for (var i = 0; i < recs.length; i++) { var done = false;' % pairs +
            _attempt("addIpAddress", "proc.addIpAddress(recs[i][0], recs[i][1])") +
            _attempt("addRecord", "proc.addRecord(recs[i][0], recs[i][1])") +
            ' if (done) { okn++; } else { bad.push(recs[i][0]); } }'
            ' if (bad.length > 0) { return "ERROR: registros no creados: " + bad.join(", ") + ". Miembros del proceso: " + members.join(", "); }'
            # 6.0.1 real (2026-10-03): addIpAddress(nombre, ip) devuelve true y getEntryCount sube, pero un PC NO resuelve
            # ese nombre (nslookup: Non-existent domain). Hasta saber como se crean los registros de verdad, se avisa.
            ' return "OK " + okn + " registro(s) DNS anotados. AVISO: en la 6.0.1 los registros creados por el MCP no se resuelven'
            ' desde los PCs (limitacion sin resolver); crealos a mano en Services > DNS del servidor.";')
    return wrap(body)


# Servicios de Server-PT en la 6.0.1 real: clave -> (proceso, setter, getter). OJO: el setter cambia de nombre segun
# el proceso (setEnable / setEnabled / setHttpsEnable); todos reciben un booleano (comprobado en PT real).
SERVER_SERVICES = (
    ("dhcp", "DhcpServer", "setEnable", "isEnable"),
    ("dns", "DnsServer", "setEnable", "isEnabled"),
    ("http", "HttpServer", "setEnable", "isEnabled"),
    ("https", "HttpsServer", "setHttpsEnable", "isHttpsEnabled"),
    ("tftp", "TftpServer", "setEnabled", "isEnabled"),
    ("ftp", "FtpServer", "setEnabled", "isEnabled"),
    ("smtp", "SmtpServer", "setEnable", "isEnabled"),
    ("pop3", "Pop3Server", "setEnable", "isEnabled"),
    ("ntp", "NtpServer", "setEnabled", "isEnabled"),
    ("syslog", "SyslogServer", "setEnable", "isEnabled"),
)


def server_services(name, enabled):
    """Deja encendidos SOLO los servicios de `enabled` (claves de SERVER_SERVICES) y apaga el resto."""
    rows = ", ".join("[%s, %s, %s, %s, %s]" % (q(k), q(p), q(s), q(g), "true" if k in enabled else "false")
                     for k, p, s, g in SERVER_SERVICES)
    return wrap(
        get_dev("d", name) +
        ' if (typeof d.getProcess != "function" || !d.getProcess("DhcpServer")) { return "ERROR: " + %s + " no es un Server-PT"; }'
        ' var sv = [%s]; var on = []; var off = [];'
        ' for (var i = 0; i < sv.length; i++) { var pr = d.getProcess(sv[i][1]); if (!pr) { continue; }'
        ' pr[sv[i][2]](sv[i][4]); if (pr[sv[i][3]]()) { on.push(sv[i][0]); } else { off.push(sv[i][0]); } }'
        ' return "OK encendidos: " + (on.length ? on.join(",") : "ninguno") + " | apagados: " + off.join(",");'
        % (q(name), rows))


def snapshot():
    """Vuelca la red entera en lineas de texto con tabuladores (para aprender de un .pkt ya hecho):
    D nombre modelo tipo x y | P puerto ip mascara dhcp cable vecino puerto_vecino | S servicios | L pool DHCP."""
    services = ", ".join("[%s, %s, %s]" % (q(k), q(p), q(g)) for k, p, _s, g in SERVER_SERVICES)
    return wrap(
        'function g(o, m) { return (o && typeof o[m] == "function") ? o[m]() : ""; }'
        ' var sv = [%s]; var o = [];'
        ' for (var i = 0; i < net.getDeviceCount(); i++) { var d = net.getDeviceAt(i);'
        ' o.push(["D", d.getName(), d.getModel(), d.getType(), d.getXCoordinate(), d.getYCoordinate()].join("\\t"));'
        ' for (var j = 0; j < d.getPortCount(); j++) { var p = d.getPortAt(j); var lk = g(p, "getLink"); var ip = g(p, "getIpAddress");'
        ' if (!lk && (!ip || ip == "0.0.0.0")) { continue; }'
        ' var row = ["P", p.getName(), ip, g(p, "getSubnetMask"), g(p, "isDhcpClientOn")];'
        # Un puerto inalambrico devuelve un objeto "Antenna" (sin getPort1): no es un cable.
        ' if (lk && typeof lk.getPort1 != "function") { row.push("wifi", "", ""); lk = null; }'
        ' if (lk) { var a = lk.getPort1(); var b = lk.getPort2(); var me = a.getOwnerDevice().getName() == d.getName() && a.getName() == p.getName();'
        ' var ot = me ? b : a; row.push(lk.getConnectionType(), ot.getOwnerDevice().getName(), ot.getName()); }'
        ' o.push(row.join("\\t")); }'
        # Gateway (el del dispositivo, el que se ve en IP Configuration) y DNS de la configuracion IP.
        ' var dc = (typeof d.getProcess == "function") ? d.getProcess("DnsClient") : null;'
        ' if (dc) { var gm = /<GATEWAY>([^<]*)</.exec(String(d.serializeToXml()));'
        ' o.push(["G", gm ? gm[1] : "", dc.getServerIp()].join("\\t")); }'
        ' if (d.getType() == 9 && typeof d.getProcess == "function") { var st = [];'
        ' for (var k = 0; k < sv.length; k++) { var pr = d.getProcess(sv[k][1]); if (pr) { st.push(sv[k][0] + "=" + pr[sv[k][2]]()); } }'
        ' o.push("S\\t" + st.join(" ")); var dh = d.getProcess("DhcpServer");'
        ' for (var n = 0; dh && n < dh.getPoolCount(); n++) { var pl = dh.getPoolAt(n);'
        ' o.push(["L", pl.getDhcpPoolName(), pl.getStartIp(), pl.getEndIp(), pl.getSubnetMask(), pl.getDefaultRouter(), pl.getDnsServerIp()].join("\\t")); } } }'
        ' return o.join("\\n");' % services)


def add_note(x, y, text, size):
    """Nota de texto en el mapa. Firma real de la 6.0.1: addNote(x, y, tamano_letra, texto) -> id del elemento."""
    return wrap('var id = lw.addNote(%d, %d, %d, %s); if (!id) { return "ERROR: PT no creo la nota"; }'
                ' return "OK " + id + " en " + lw.getCanvasItemX(id) + "," + lw.getCanvasItemY(id);'
                % (int(x), int(y), int(size), q(text)))


def list_notes():
    return wrap('var ids = String(lw.getCanvasItemIds()); if (!ids) { return ""; } var a = ids.split(","); var o = [];'
                ' for (var i = 0; i < a.length; i++) { o.push(a[i] + "\\t" + lw.getCanvasItemX(a[i]) + "\\t" + lw.getCanvasItemY(a[i])); }'
                ' return o.join("\\n");')


def remove_note(note_id):
    return wrap('return String(lw.removeCanvasItem(%s));' % q(note_id))


def clear_workspace():
    return wrap(
        'var names = []; for (var i = 0; i < net.getDeviceCount(); i++) { names.push(net.getDeviceAt(i).getName()); }'
        ' var n = 0; for (var j = 0; j < names.length; j++) { var guard = 0; while (guard < 10 && lw.removeDevice(names[j])) { n++; guard++; } }'
        ' return String(n) + " borrados, quedan " + net.getDeviceCount();')


def workspace_image(fmt):
    """Imagen del mapa. En la 6.0.1 getWorkspaceImage(fmt) devuelve un Array de bytes CON SIGNO (un PNG empieza por
    -119,80,78...). Se pasa a base64 aqui dentro: ocupa 1/4 que el texto con comas y cabe mas en el limite de 1 MB del puente."""
    return wrap(
        'var b = lw.getWorkspaceImage(%s); if (!b || !b.length) { return "ERROR: PT no devolvio la imagen del mapa"; }'
        ' var A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"; var n = b.length; var s = [];'
        ' for (var i = 0; i < n; i += 3) { var c0 = b[i] & 255; var c1 = i + 1 < n ? b[i + 1] & 255 : 0; var c2 = i + 2 < n ? b[i + 2] & 255 : 0;'
        ' s.push(A.charAt(c0 >> 2) + A.charAt(((c0 & 3) << 4) | (c1 >> 4))'
        ' + (i + 1 < n ? A.charAt(((c1 & 15) << 2) | (c2 >> 6)) : "=") + (i + 2 < n ? A.charAt(c2 & 63) : "=")); }'
        ' return s.join("");' % q(fmt))


# Campos de puerto que se leen (todos comprobados en la 6.0.1 el 2026-10-22; cada tipo de equipo tiene solo una parte,
# por eso se pregunta typeof antes de llamar). NO usar getOtherPort ni getPortSecurity: una prueba con ellos colgo el motor.
PORT_FIELDS = ["getPower", "isPortUp", "isProtocolUp", "getLightStatus", "getMacAddress", "getIpAddress", "getSubnetMask",
               "isDhcpClientOn", "getBandwidth", "isBandwidthAutoNegotiate", "isFullDuplex", "isDuplexAutoNegotiate",
               "getMtu", "getDelay", "getDescription", "isCdpEnable", "getNatMode", "getAclInID", "getAclOutID",
               "getAdminOpMode", "getAccessVlan", "getNativeVlanId"]


def inspect_ports(name, only_linked):
    """Una linea por puerto: nombre, los PORT_FIELDS ("" si el puerto no tiene ese metodo) y, si hay cable,
    tipo de cable, equipo y puerto del otro extremo."""
    fields = ", ".join(q(f) for f in PORT_FIELDS)
    return wrap(
        get_dev("d", name) +
        ' function g(o, m) { if (typeof o[m] != "function") { return ""; } try { return String(o[m]()); } catch (e) { return "?"; } }'
        ' var F = [%s]; var o = [];'
        ' for (var i = 0; i < d.getPortCount(); i++) { var p = d.getPortAt(i); var lk = null; try { lk = p.getLink(); } catch (e1) { lk = null; }'
        ' if (lk && typeof lk.getPort1 != "function") { lk = null; }'
        ' if (%s && !lk) { continue; }'
        ' var row = [p.getName()]; for (var k = 0; k < F.length; k++) { row.push(g(p, F[k])); }'
        ' if (lk) { var a = lk.getPort1(); var b = lk.getPort2();'
        ' var me = a.getOwnerDevice().getName() == d.getName() && a.getName() == p.getName(); var ot = me ? b : a;'
        ' row.push(lk.getConnectionType(), ot.getOwnerDevice().getName(), ot.getName()); }'
        ' o.push(row.join("\\t")); }'
        ' return o.join("\\n");' % (fields, "true" if only_linked else "false"))


def set_port(name, port, ops):
    """Aplica setters de puerto comprobados en la 6.0.1 y lee el valor despues. ops = [(setter, getter, literal_js)]:
    el literal ya viene validado (entero, true/false o q(texto)). Devuelve 'setter<TAB>valor leido' por linea."""
    calls = " ".join(
        'if (typeof p.%s != "function") { o.push("%s\\tNO EXISTE en este puerto"); } else { p.%s(%s); o.push("%s\\t" + p.%s()); }'
        % (setter, setter, setter, lit, setter, getter) for setter, getter, lit in ops)
    return wrap(
        get_dev("d", name) +
        ' var p = d.getPort(%s); if (!p) { return "ERROR: " + %s + " no tiene el puerto " + %s; }'
        ' var o = []; %s return o.join("\\n");' % (q(port), q(name), q(port), calls))


def ui_info(name):
    """Para abrir la ventana de un equipo. Primera linea: 'si'/'no' (getDialog: la ventana existe, visible u oculta),
    tipo, x, y, puertos separados por comas. Despues una linea 'D nombre x y' por equipo (referencias para situar el lienzo)."""
    return wrap(
        get_dev("d", name) +
        ' var dm = ipc.appWindow().getDialogManager(); var dl = null; try { dl = dm.getDialog(%s); } catch (e1) { dl = null; }'
        ' var ps = []; for (var i = 0; i < d.getPortCount(); i++) { ps.push(d.getPortAt(i).getName()); }'
        ' var o = [[dl ? "si" : "no", d.getType(), d.getXCoordinate(), d.getYCoordinate(), ps.join(",")].join("\\t")];'
        ' for (var j = 0; j < net.getDeviceCount(); j++) { var e = net.getDeviceAt(j);'
        ' o.push(["D", e.getName(), e.getXCoordinate(), e.getYCoordinate()].join("\\t")); }'
        ' return o.join("\\n");' % q(name))


def dialog_visible(name, visible):
    """Ensena u oculta la ventana de un equipo SIN destruirla (cerrarla con la X la destruye y luego hay que reabrirla con un clic)."""
    return wrap(
        'var dl = null; try { dl = ipc.appWindow().getDialogManager().getDialog(%s); } catch (e) { dl = null; }'
        ' if (!dl) { return "no"; } dl.setVisible(%s); return "si";' % (q(name), "true" if visible else "false"))


SERVER_XML_SECTIONS = ("HTTP_SERVER", "HTTPS_SERVER", "DNS_SERVER", "DHCP_SERVER", "TFTP_SERVER", "FTP_SERVER", "NTP_SERVER",
                       "SYSLOG_SERVER", "ACS_SERVER", "EMAIL_SERVER")


def server_xml(name):
    """Las secciones de servicios del XML de un Server-PT (lo que se ve en Config > SERVICES), seguidas.
    Ojo: <DNS_SERVER> aparece tambien DENTRO de un pool DHCP (su IP de DNS); se busca la primera apertura con hijos."""
    tags = ", ".join(q(t) for t in SERVER_XML_SECTIONS)
    return wrap(
        get_dev("d", name) +
        ' if (d.getType() != 9) { return "ERROR: " + %s + " no es un servidor (Server-PT)"; }'
        ' var x = String(d.serializeToXml()); var T = [%s]; var o = [];'
        ' for (var i = 0; i < T.length; i++) { var a = x.indexOf("<" + T[i] + ">\\n"); if (a < 0) { a = x.indexOf("<" + T[i] + ">"); }'
        ' var b = x.indexOf("</" + T[i] + ">", a); if (a >= 0 && b > a) { o.push(x.substring(a, b + T[i].length + 3)); } }'
        ' return o.join("\\n");' % (q(name), tags))


def ftp_users(name, users, remove=()):
    """users = [(usuario, clave, permisos)]. Firmas comprobadas: addFtpUser(usuario, clave, "RWDNL") y removeFtpUser(usuario)
    (las dos devuelven undefined: se mira isExistingUser despues). Si ya existe, no se toca."""
    rows = ", ".join("[%s, %s, %s]" % (q(u), q(p), q(perm)) for u, p, perm in users)
    rem = ", ".join(q(u) for u in remove)
    return wrap(
        get_dev("d", name) +
        ' var f = d.getProcess("FtpServer"); if (!f) { return "ERROR: " + %s + " no tiene servidor FTP"; }'
        ' var m = f.getFtpUserAccountManager(); var U = [%s]; var o = []; var R = [%s];'
        ' for (var j = 0; j < R.length; j++) { if (!m.isExistingUser(R[j])) { o.push(R[j] + "\\tno existia"); continue; }'
        ' m.removeFtpUser(R[j]); o.push(R[j] + "\\t" + (m.isExistingUser(R[j]) ? "PT no la borro" : "borrada")); }'
        ' for (var i = 0; i < U.length; i++) { if (m.isExistingUser(U[i][0])) { o.push(U[i][0] + "\\tya existia"); continue; }'
        # addFtpUser devuelve undefined aunque cree la cuenta (comprobado): se mira si existe despues.
        ' m.addFtpUser(U[i][0], U[i][1], U[i][2]); o.push(U[i][0] + "\\t" + (m.isExistingUser(U[i][0]) ? "creado" : "PT lo rechazo")); }'
        ' return o.join("\\n");' % (q(name), rows, rem))


def email_setup(name, domain, users, remove=()):
    """Dominio (SmtpServer.setServerDomainName) y cuentas (EmailServer.addUser(usuario, clave), deleteUser(usuario)),
    comprobados en la 6.0.1. getEmailUser(nombre) da null si la cuenta no existe."""
    rows = ", ".join("[%s, %s]" % (q(u), q(p)) for u, p in users)
    rem = ", ".join(q(u) for u in remove)
    dom = (' d.getProcess("SmtpServer").setServerDomainName(%s); o.push("dominio\\t" + d.getProcess("SmtpServer").getServerDomainName());'
           % q(domain)) if domain else ""
    return wrap(
        get_dev("d", name) +
        ' var em = d.getProcess("EmailServer"); if (!em || !d.getProcess("SmtpServer")) { return "ERROR: " + %s + " no tiene servidor de correo"; }'
        ' var o = [];%s var U = [%s]; var R = [%s];'
        ' for (var j = 0; j < R.length; j++) { if (!em.getEmailUser(R[j])) { o.push(R[j] + "\\tno existia"); continue; }'
        ' em.deleteUser(R[j]); o.push(R[j] + "\\t" + (em.getEmailUser(R[j]) ? "PT no la borro" : "borrada")); }'
        ' for (var i = 0; i < U.length; i++) { var had = null; try { had = em.getEmailUser(U[i][0]); } catch (e) { had = null; }'
        ' if (had) { o.push(U[i][0] + "\\tya existia"); continue; }'
        ' em.addUser(U[i][0], U[i][1]); o.push(U[i][0] + "\\t" + (em.getEmailUser(U[i][0]) ? "creado" : "PT lo rechazo")); }'
        ' return o.join("\\n");' % (q(name), dom, rows, rem))


def open_dialogs():
    """Nombres de los equipos cuya ventana existe (visible u oculta)."""
    return wrap(
        'var dm = ipc.appWindow().getDialogManager(); var o = [];'
        ' for (var i = 0; i < net.getDeviceCount(); i++) { var n = net.getDeviceAt(i).getName(); var dl = null;'
        ' try { dl = dm.getDialog(n); } catch (e) { dl = null; } if (dl) { o.push(n); } }'
        ' return o.join(",");')


def hide_all_dialogs():
    return wrap(
        'var dm = ipc.appWindow().getDialogManager(); var o = [];'
        ' for (var i = 0; i < net.getDeviceCount(); i++) { var n = net.getDeviceAt(i).getName(); var dl = null;'
        ' try { dl = dm.getDialog(n); } catch (e) { dl = null; } if (dl) { dl.setVisible(false); o.push(n); } }'
        ' return o.join(",");')
