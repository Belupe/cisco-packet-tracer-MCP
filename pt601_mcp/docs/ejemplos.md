# Ejemplos

## 1. Prompt en lenguaje natural
> «Haz un mapa de red con un switch, 3 PCs y 2 portátiles. Un servidor DHCP con IP estática 192.168.1.2 que
> reparta del 192.168.1.100 al 199, gateway 192.168.1.1 y DNS 192.168.1.3, y un servidor DNS 192.168.1.3 con
> `www.local` → 192.168.1.3. Los PCs y portátiles por DHCP. Al final haz un ping desde PC1 al servidor DNS.»

Claude debería: `pt_status` → `pt_build_topology` (con el plan de abajo) → `pt_ping`.

## 2. Plan JSON equivalente (`pt_build_topology`)
```json
{
  "devices": [
    {"name": "SW1", "model": "2960-24TT"},
    {"name": "PC1", "model": "PC-PT"}, {"name": "PC2", "model": "PC-PT"}, {"name": "PC3", "model": "PC-PT"},
    {"name": "LAP1", "model": "Laptop-PT"}, {"name": "LAP2", "model": "Laptop-PT"},
    {"name": "SRV-DHCP", "model": "Server-PT"}, {"name": "SRV-DNS", "model": "Server-PT"}
  ],
  "links": [
    {"a": "SW1", "b": "PC1"}, {"a": "SW1", "b": "PC2"}, {"a": "SW1", "b": "PC3"},
    {"a": "SW1", "b": "LAP1"}, {"a": "SW1", "b": "LAP2"},
    {"a": "SW1", "b": "SRV-DHCP"}, {"a": "SW1", "b": "SRV-DNS"}
  ],
  "servers": [
    {"device": "SRV-DHCP", "ip": "192.168.1.2", "mask": "255.255.255.0", "gateway": "192.168.1.1",
     "dhcp": {"pool": "LAN", "gateway": "192.168.1.1", "dns": "192.168.1.3",
              "start_ip": "192.168.1.100", "mask": "255.255.255.0", "max_users": 100}},
    {"device": "SRV-DNS", "ip": "192.168.1.3", "mask": "255.255.255.0", "gateway": "192.168.1.1",
     "dns": {"records": [{"name": "www.local", "ip": "192.168.1.3"}]}}
  ],
  "hosts": [
    {"device": "PC1", "dhcp": true}, {"device": "PC2", "dhcp": true}, {"device": "PC3", "dhcp": true},
    {"device": "LAP1", "dhcp": true}, {"device": "LAP2", "dhcp": true}
  ]
}
```
- Sin `x`/`y` se autoposiciona por niveles (routers arriba, switches, servidores/APs, equipos finales).
- Sin `port_a`/`port_b` se eligen puertos libres.
- Usa `dry_run: true` para validar sin tocar Packet Tracer.
- Si un paso falla, el resto continúa y el informe lo marca con `ERR`.

## 3. Red con router, VLANs y OSPF
```json
{
  "devices": [
    {"name": "R1", "model": "2911"}, {"name": "R2", "model": "2911"},
    {"name": "SW1", "model": "2960-24TT"}, {"name": "SW2", "model": "2960-24TT"},
    {"name": "PC1", "model": "PC-PT"}, {"name": "PC2", "model": "PC-PT"}
  ],
  "links": [
    {"a": "R1", "b": "R2"}, {"a": "R1", "b": "SW1"}, {"a": "R2", "b": "SW2"},
    {"a": "SW1", "b": "PC1"}, {"a": "SW2", "b": "PC2"}
  ],
  "routers": [
    {"device": "R1", "hostname": "R1",
     "interfaces": [{"port": "@R2", "ip": "10.0.0.1", "mask": "255.255.255.252"},
                    {"port": "@SW1", "ip": "192.168.1.1", "mask": "255.255.255.0"}],
     "ospf": {"process": 1, "networks": [{"network": "10.0.0.0", "mask": "255.255.255.252", "area": 0},
                                         {"network": "192.168.1.0", "mask": "255.255.255.0", "area": 0}]}},
    {"device": "R2", "hostname": "R2",
     "interfaces": [{"port": "@R1", "ip": "10.0.0.2", "mask": "255.255.255.252"},
                    {"port": "@SW2", "ip": "192.168.2.1", "mask": "255.255.255.0"}],
     "ospf": {"process": 1, "networks": [{"network": "10.0.0.0", "mask": "255.255.255.252", "area": 0},
                                         {"network": "192.168.2.0", "mask": "255.255.255.0", "area": 0}]}}
  ],
  "hosts": [
    {"device": "PC1", "ip": "192.168.1.10", "mask": "255.255.255.0", "gateway": "192.168.1.1"},
    {"device": "PC2", "ip": "192.168.2.10", "mask": "255.255.255.0", "gateway": "192.168.2.1"}
  ]
}
```
Después: `pt_ping` de `PC1` a `192.168.2.10` (OSPF tarda unos segundos en converger).

> `"port": "@R2"` significa «el puerto de este dispositivo que está cableado con R2». El constructor lo resuelve con los
> puertos que realmente eligió al cablear, así no hace falta saber cuáles son. También vale en `switches[].access_ports`,
> `trunk_ports` y en `ospf.passive`. Si prefieres fijarlos tú, usa `port_a`/`port_b` en `links`.

## 4. Diagnóstico paso a paso
1. `pt_list_devices` y `pt_list_ports R1`
2. `pt_cli` con `["show ip interface brief", "show ip route"]`
3. `pt_ping` desde un PC y, si falla, `pt_read_output` para ver el resultado completo
