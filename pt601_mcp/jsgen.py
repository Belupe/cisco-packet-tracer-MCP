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


def add_device(name, model, dtype, x, y, skip_boot):
    move = ("d.moveToLocation(%d, %d);" % (int(x), int(y))) if x is not None and y is not None else ""
    boot = "try { d.skipBoot(); } catch (e2) {}" if skip_boot else ""
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
