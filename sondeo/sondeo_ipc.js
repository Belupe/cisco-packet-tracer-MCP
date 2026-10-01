// Sondeo de la API IPC de Packet Tracer 6.0.1 (Qt Script, ECMAScript antiguo).
// Solo lectura: no modifica la red. Estilo ES3: sin let/const/flechas/JSON.
//
// Uso: Extensions > Scripting > New PT Script Module > pestaña "Script Engine",
// pegar este archivo, marcar todos los Security Privileges, Start,
// y abrir el Debug Dialog (botón Debug). La salida sale por dprint().

var OUT = [];

function log(s) { OUT.push(s); dprint(s); }

function listMembers(label, obj) {
    var names = [];
    var k;
    try {
        for (k in obj) { names.push(k); }
    } catch (e) {
        log("[" + label + "] error al enumerar: " + e);
        return;
    }
    names.sort();
    log("== " + label + " (" + names.length + ") ==");
    log(names.join(", "));
}

function tryCall(label, fn) {
    try {
        var r = fn();
        log(label + " -> " + r);
        return r;
    } catch (e) {
        log(label + " -> ERROR: " + e);
        return null;
    }
}

function main() {
    log("### Sondeo IPC PT 6.0.1 ###");
    listMembers("ipc", ipc);

    var net = tryCall("ipc.network()", function () { return ipc.network(); });
    if (net) {
        listMembers("network", net);
        var n = tryCall("network.getDeviceCount()", function () { return net.getDeviceCount(); });
        if (n !== null) {
            var i, d, names = [];
            for (i = 0; i < n; i++) {
                d = net.getDeviceAt(i);
                names.push(d.getName() + " [" + d.getModel() + " / tipo " + d.getType() + "]");
                if (i == 0) {
                    listMembers("device(0)", d);
                    tryCall("device(0).getPortCount()", function () { return d.getPortCount(); });
                    tryCall("device(0).getPortAt(0)", function () {
                        var p = d.getPortAt(0);
                        listMembers("port(0)", p);
                        return p.getName();
                    });
                }
            }
            log("Dispositivos en el workspace: " + names.join(" | "));
        }
    }
    tryCall("ipc.appWindow()", function () {
        var w = ipc.appWindow();
        listMembers("appWindow", w);
        return w;
    });
    tryCall("ipc.simulation()", function () {
        var s = ipc.simulation();
        listMembers("simulation", s);
        return s;
    });
    log("### Fin del sondeo ###");
}

function cleanUp() {}
