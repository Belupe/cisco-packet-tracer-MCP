// Script Module para Packet Tracer 6.0.1 (Qt Script, estilo ES3).
// Pegar en la pestana "Script Engine" de un New PT Script Module y marcar todos los
// Security Privileges. Abre el panel, consulta cada 250 ms y ejecuta el codigo que
// llega del servidor MCP local. Si el servidor no estaba arrancado, reintenta solo.

var URL = "http://127.0.0.1:54321/";
var WV = null;
var TIMER = null;
var BUSY = false;
var IDLE_TICKS = 0;

function main() {
    WV = webViewManager.createWebView("PT-MCP local", URL, 560, 440);
    WV.show();
    TIMER = setInterval(tick, 250);
    dprint("PT-MCP: panel abierto (" + URL + ")");
}

function cleanUp() {
    try { if (TIMER !== null) { clearInterval(TIMER); } } catch (e) {}
    try { if (WV) { webViewManager.closeWebView(WV.getWebViewId()); } } catch (e2) {}
}

function tick() {
    if (BUSY || !WV) { return; }
    BUSY = true;
    try {
        var got = WV.evaluateJavaScript("typeof __take === 'function' ? __take() : '#nopage'");
        if (got == "#nopage") {
            // La pagina no cargo (servidor aun no arrancado): reintentar cada ~3 s.
            IDLE_TICKS++;
            if (IDLE_TICKS % 12 == 0) { WV.setUrl(URL); }
        } else if (got && got.length > 0) {
            IDLE_TICKS = 0;
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
