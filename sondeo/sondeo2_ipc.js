// Sondeo 2 de la API IPC de Packet Tracer 6.0.1 (Qt Script, estilo ES3).
// Busca: version, workspace, creacion de dispositivos/cables y terminal CLI.
//
// Parte 1 (siempre): solo lectura.
// Parte 2 (opcional): prueba de escritura. Poner DO_WRITE_TEST = true SOLO
//   en un archivo NUEVO y vacio (File > New). Anade un router, un switch y un cable.

var DO_WRITE_TEST = false;

function log(s) { dprint(s); }

function members(label, obj) {
    var names = [];
    var k;
    try { for (k in obj) { names.push(k); } }
    catch (e) { log("[" + label + "] error: " + e); return; }
    names.sort();
    log("== " + label + " (" + names.length + ") ==");
    log(names.join(", "));
}

function tryCall(label, fn) {
    try { var r = fn(); log(label + " -> " + r); return r; }
    catch (e) { log(label + " -> ERROR: " + e); return null; }
}

function main() {
    log("### Sondeo 2 IPC PT 6.0.1 ###");
    var win = ipc.appWindow();
    tryCall("appWindow.getVersion()", function () { return win.getVersion(); });
    tryCall("appWindow.getBasePath()", function () { return win.getBasePath(); });
    tryCall("appWindow.isLogicalMode()", function () { return win.isLogicalMode(); });

    var ws = tryCall("appWindow.getActiveWorkspace()", function () { return win.getActiveWorkspace(); });
    if (ws) {
        members("activeWorkspace", ws);
        var lw = tryCall("workspace.getLogicalWorkspace()", function () { return ws.getLogicalWorkspace(); });
        if (lw) { members("logicalWorkspace", lw); }
    }
    tryCall("appWindow.getActiveFile()", function () { return win.getActiveFile(); });
    tryCall("appWindow.getNetworkComponentBox()", function () {
        var b = win.getNetworkComponentBox();
        members("networkComponentBox", b);
        return b;
    });

    // Terminal CLI y otros miembros del primer dispositivo con consola
    var net = ipc.network();
    var n = net.getDeviceCount();
    var i, d, done = false;
    for (i = 0; i < n && !done; i++) {
        d = net.getDeviceAt(i);
        if (d.getType() == 0) {
            done = true;
            log("Dispositivo de prueba: " + d.getName() + " modelo " + d.getModel());
            tryCall("getHostName()", function () { return d.getHostName(); });
            tryCall("getPower()", function () { return d.getPower(); });
            var cl = tryCall("getCommandLine()", function () { return d.getCommandLine(); });
            if (cl) {
                members("commandLine", cl);
                tryCall("commandLine.getPrompt()", function () { return cl.getPrompt(); });
                tryCall("commandLine.getMode()", function () { return cl.getMode(); });
            }
            var port = d.getPortAt(0);
            tryCall("port.getIpAddress()", function () { return port.getIpAddress(); });
            tryCall("port.getSubnetMask()", function () { return port.getSubnetMask(); });
            tryCall("port.getLink()", function () {
                var l = port.getLink();
                if (l) { members("link", l); }
                return l;
            });
            tryCall("device.getType()", function () { return d.getType(); });
        }
    }
    tryCall("ipc.commandLog()", function () {
        var c = ipc.commandLog();
        members("commandLog", c);
        return c;
    });

    if (DO_WRITE_TEST) {
        log("--- Prueba de escritura ---");
        var lw2 = ipc.appWindow().getActiveWorkspace().getLogicalWorkspace();
        var r1 = tryCall("addDevice(0,'2911',100,100)", function () { return lw2.addDevice(0, "2911", 100, 100); });
        var r2 = tryCall("addDevice(1,'2960-24TT',250,100)", function () { return lw2.addDevice(1, "2960-24TT", 250, 100); });
        tryCall("createLink", function () {
            return lw2.createLink(r1, "GigabitEthernet0/0", r2, "FastEthernet0/1", 8100);
        });
        members("logicalWorkspace tras escribir", lw2);
    }
    log("### Fin del sondeo 2 ###");
}

function cleanUp() {}
