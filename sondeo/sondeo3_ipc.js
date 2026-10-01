// Sondeo 3 (PT 6.0.1, Qt Script, estilo ES3): como se crean dispositivos y cables.
// Parte 1 (siempre): inspecciona _parser y las firmas de addDevice/createLink.
// Parte 2 (DO_WRITE_TEST = true): prueba variantes de addDevice y borra lo que cree.
//   Recomendado en un archivo NUEVO (File > New), no en tus laboratorios.

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

function str(label, fn) {
    try { log(label + " -> " + fn()); }
    catch (e) { log(label + " -> ERROR: " + e); }
}

function main() {
    log("### Sondeo 3 IPC PT 6.0.1 ###");
    var lw = ipc.appWindow().getActiveWorkspace().getLogicalWorkspace();

    str("typeof lw.addDevice", function () { return typeof lw.addDevice; });
    str("lw.addDevice.toString()", function () { return String(lw.addDevice); });
    str("lw.createLink.toString()", function () { return String(lw.createLink); });
    str("typeof lw._parser", function () { return typeof lw._parser; });
    members("lw._parser", lw._parser);
    str("lw._parser.toString()", function () { return String(lw._parser); });
    members("ipc._parser", ipc._parser);
    str("ipc._parser.toString()", function () { return String(ipc._parser); });
    str("lw.getState()", function () { return lw.getState(); });
    str("lw.getComponentItemsCount()", function () { return lw.getComponentItemsCount(); });
    str("lw.getCanvasItemIds()", function () { return lw.getCanvasItemIds(); });

    if (DO_WRITE_TEST) {
        log("--- Variantes de addDevice ---");
        var variants = [
            [0, "2911", 100, 100],
            [0, "2911", 100.0, 100.0],
            ["router", "2911", 100, 100],
            [0, "Router-PT-Empty", 100, 100],
            [0, "Router-PT", 100, 100],
            [1, "2960-24TT", 250, 100],
            [1, "Switch-PT-Empty", 250, 100],
            [8, "PC-PT", 400, 100]
        ];
        var i, v, r, ok = [];
        for (i = 0; i < variants.length; i++) {
            v = variants[i];
            try {
                r = lw.addDevice(v[0], v[1], v[2], v[3]);
                log("OK addDevice(" + v.join(",") + ") -> " + r);
                ok.push(r);
            } catch (e) {
                log("FALLA addDevice(" + v.join(",") + ")");
            }
        }
        log("Creados: " + ok.join(" | "));
        if (ok.length >= 2) {
            str("createLink(" + ok[0] + "," + ok[1] + ")", function () {
                var d1 = ipc.network().getDevice(ok[0]);
                var d2 = ipc.network().getDevice(ok[1]);
                return lw.createLink(ok[0], d1.getPortAt(0).getName(), ok[1], d2.getPortAt(0).getName(), 8100);
            });
        }
        for (i = 0; i < ok.length; i++) {
            str("removeDevice(" + ok[i] + ")", function () { return lw.removeDevice(ok[i]); });
        }
    }
    log("### Fin del sondeo 3 ###");
}

function cleanUp() {}
