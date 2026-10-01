// Sondeo 4 (PT 6.0.1, Qt Script, estilo ES3): que canal de comunicacion con el
// exterior existe (archivos del Script Engine / web view). Solo lectura.
// Uso: igual que los anteriores (Start + Debug). No necesita DO_WRITE_TEST.

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

function main() {
    log("### Sondeo 4: canal con el exterior ###");
    var GLOBAL = this;
    members("globales del Script Engine", GLOBAL);

    var cand = ["systemFileManager", "_ScriptModule", "_IpcBase", "$se", "$putData", "$getData",
                "XMLHttpRequest", "include", "exec", "Process", "QProcess", "System", "File", "Dir"];
    var i;
    for (i = 0; i < cand.length; i++) {
        log("typeof " + cand[i] + " = " + (function (n) {
            try { return typeof GLOBAL[n]; } catch (e) { return "ERROR " + e; }
        })(cand[i]));
    }
    if (typeof systemFileManager != "undefined") { members("systemFileManager", systemFileManager); }
    if (typeof _ScriptModule != "undefined") { members("_ScriptModule", _ScriptModule); }
    try { members("ipc.appWindow().getWebViewManager()", ipc.appWindow().getWebViewManager()); }
    catch (e) { log("getWebViewManager: " + e); }
    log("### Fin del sondeo 4 ###");
}

function cleanUp() {}
