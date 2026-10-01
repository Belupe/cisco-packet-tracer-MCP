// Script Module PT 6.0.1 (Qt Script, estilo ES3): abre el panel y ejecuta el
// codigo que llega del servidor local. Pegar en Script Engine y marcar todos
// los Security Privileges. El Script Engine pregunta al panel cada 250 ms.

var WV = null;
var TIMER = null;
var BUSY = false;

function main() {
    WV = webViewManager.createWebView("PT-MCP local", "http://127.0.0.1:54321/", 560, 440);
    WV.show();
    TIMER = setInterval(tick, 250);
    dprint("PT-MCP: panel abierto");
}

function cleanUp() {
    try { if (TIMER !== null) { clearInterval(TIMER); } } catch (e) {}
    try { if (WV) { webViewManager.closeWebView(WV.getWebViewId()); } } catch (e2) {}
}

function tick() {
    if (BUSY || !WV) { return; }
    BUSY = true;
    try {
        var got = WV.evaluateJavaScript("typeof __take === 'function' ? __take() : ''");
        if (got && got.length > 0) {
            var i = got.indexOf(":");
            var id = got.substring(0, i);
            var code = decodeURIComponent(got.substring(i + 1));
            var res;
            try { res = String(eval(code)); }
            catch (e) { res = "ERROR: " + e; }
            WV.evaluateJavaScript("__result(" + id + ", \"" + encodeURIComponent(res) + "\")");
        }
    } catch (e3) {
        dprint("PT-MCP tick ERROR: " + e3);
    }
    BUSY = false;
}
