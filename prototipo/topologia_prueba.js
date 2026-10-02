// Topologia de prueba para PT 6.0.1 (Qt Script, estilo ES3). Se manda con:
//   powershell -ExecutionPolicy Bypass -File .\pt.ps1 -File .\topologia_prueba.js -TimeoutSec 90
//
//   T-R1 (2911) Gi0/0 --- Fa0/1 T-S1 (2960-24TT) Fa0/2 --- T-PC1 (192.168.1.10)
//                                              Fa0/3 --- T-PC2 (192.168.1.11)
// Red 192.168.1.0/24, gateway 192.168.1.1 (en el router).
// Antes de crear, borra dispositivos que se llamen T-R1, T-S1, T-PC1 o T-PC2.
// Devuelve un informe de texto con OK/ERR por paso.
(function () {
    var out = [];
    function say(s) { out.push(s); }
    var lw = ipc.appWindow().getActiveWorkspace().getLogicalWorkspace();
    var net = ipc.network();

    function step(label, fn) {
        try {
            var r = fn();
            say("OK  " + label + (r === undefined ? "" : " -> " + r));
            return r;
        } catch (e) {
            say("ERR " + label + ": " + e);
            return null;
        }
    }

    function addDev(name, type, model, x, y) {
        try { if (net.getDevice(name)) { lw.removeDevice(name); } } catch (e0) {}
        var auto = lw.addDevice(type, model);   // 6.0.1: solo tipo y modelo
        var d = net.getDevice(auto);
        d.setName(name);
        d.moveToLocation(x, y);
        if (type == 0 || type == 1) { try { d.skipBoot(); } catch (e1) {} }
        return auto + " -> " + name;
    }

    function setPcIp(name, ip, mask, gw) {
        var p = net.getDevice(name).getPort("FastEthernet0");
        p.setIpSubnetMask(ip, mask);
        p.setDefaultGateway(gw);
        return p.getIpAddress() + " / " + p.getSubnetMask();
    }

    function cli(name, cmds) {
        var cl = net.getDevice(name).getCommandLine();
        var i;
        for (i = 0; i < cmds.length; i++) { cl.enterCommand(cmds[i]); }
        return "prompt=[" + cl.getPrompt() + "]";
    }

    step("crear T-R1 (2911)",       function () { return addDev("T-R1", 0, "2911", 250, 100); });
    step("crear T-S1 (2960-24TT)",  function () { return addDev("T-S1", 1, "2960-24TT", 250, 250); });
    step("crear T-PC1 (PC-PT)",     function () { return addDev("T-PC1", 8, "PC-PT", 150, 400); });
    step("crear T-PC2 (PC-PT)",     function () { return addDev("T-PC2", 8, "PC-PT", 350, 400); });

    step("cable R1-S1",  function () { return lw.createLink("T-R1", "GigabitEthernet0/0", "T-S1", "FastEthernet0/1", 8100); });
    step("cable S1-PC1", function () { return lw.createLink("T-S1", "FastEthernet0/2", "T-PC1", "FastEthernet0", 8100); });
    step("cable S1-PC2", function () { return lw.createLink("T-S1", "FastEthernet0/3", "T-PC2", "FastEthernet0", 8100); });

    step("IP T-PC1", function () { return setPcIp("T-PC1", "192.168.1.10", "255.255.255.0", "192.168.1.1"); });
    step("IP T-PC2", function () { return setPcIp("T-PC2", "192.168.1.11", "255.255.255.0", "192.168.1.1"); });

    step("config router por consola", function () {
        return cli("T-R1", ["no", "", "enable", "configure terminal", "hostname R1",
                            "interface GigabitEthernet0/0", "ip address 192.168.1.1 255.255.255.0",
                            "no shutdown", "end"]);
    });
    step("lee IP del router", function () {
        var p = net.getDevice("T-R1").getPort("GigabitEthernet0/0");
        return p.getIpAddress() + " / " + p.getSubnetMask() + " up=" + p.isPortUp();
    });
    step("show ip interface brief", function () {
        var cl = net.getDevice("T-R1").getCommandLine();
        cl.enterCommand("show ip interface brief");
        var o = String(cl.getOutput());
        return "\n" + o.substring(Math.max(0, o.length - 500));
    });
    return out.join("\n");
})()
