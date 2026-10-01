// Script Module PT 6.0.1 (Qt Script, estilo ES3): abre el panel y ejecuta el
// codigo que llega del servidor local. Pegar en Script Engine y marcar todos
// los Security Privileges.

var WV = null;

function main() {
    WV = webViewManager.createWebView("PT-MCP local", "http://127.0.0.1:54321/", 560, 440);
    WV.show();
    dprint("PT-MCP: panel abierto");
}

function cleanUp() {
    try { if (WV) { WV.close(); } } catch (e) {}
}

// Lo llama el panel con $se("runCode", webViewId, id, codigo).
function runCode(wvId, id, code) {
    var res;
    try {
        res = String(eval(code));
    } catch (e) {
        res = "ERROR: " + e;
    }
    var wv = webViewManager.getWebView(wvId);
    $wvca(wv, "onResult", id, res);
}
