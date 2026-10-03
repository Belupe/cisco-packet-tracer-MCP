# Referencia de herramientas

Todas devuelven texto. Un error se devuelve como `isError` con un mensaje en español.

## Estado y consulta
| Herramienta | Parámetros | Qué hace |
|---|---|---|
| `pt_status` | — | Estado del puente, versión de PT y nº de dispositivos |
| `pt_catalog` | — | Modelos disponibles (con marca "verificado en 6.0.1") y tipos de cable |
| `pt_list_devices` | — | Nombre, modelo, tipo, encendido y nº de puertos |
| `pt_list_ports` | `device` | Puertos del dispositivo y si están libres o conectados |
| `pt_rename_device` | `name`, `new_name` | Cambia el nombre; falla si el nuevo ya existe |
| `pt_snapshot` | — | Lee la red entera del archivo abierto: posición (x, y), IP/máscara/DHCP, cables con puertos y tipo, servicios y pool DHCP de los servidores |
| `pt_describe` | `device`, `process?`, `port?` | Introspección: lista los métodos de un dispositivo, proceso (`DhcpServer`) o puerto |
| `pt_read_output` | `device`, `tail_chars?` | Final de la consola |

## Construcción
| Herramienta | Parámetros | Notas |
|---|---|---|
| `pt_add_device` | `name`, `model`, `x?`, `y?` | Falla si el nombre existe. Routers/switches se encienden al instante (`skipBoot`) |
| `pt_remove_device` | `name` | Borra todas las copias del nombre |
| `pt_move_device` | `name`, `x`, `y` | |
| `pt_add_link` | `device1`, `port1`, `device2`, `port2`, `cable?` | Puertos explícitos (p. ej. `GigabitEthernet0/0`) |
| `pt_connect` | `device1`, `device2`, `cable?`, `port1?`, `port2?` | **Elige puertos libres solo** (Fa antes que Gi, ignora consola/serie/wireless) |
| `pt_build_topology` | `plan`, `dry_run?` | Construye toda la red desde un plan JSON (ver `ejemplos.md`). En `interfaces`/`ports` usa `"@VECINO"` para «el puerto cableado con VECINO» |
| `pt_clear_workspace` | `confirm` | Borra todo. Exige `confirm: true` |

Cables: `auto` (por defecto, PT elige recto/cruzado), `straight`, `cross`, `roll`, `fiber`, `serial`, `console`.
Para `serial`/`console` hay que indicar los puertos.

## Configuración
| Herramienta | Parámetros | Notas |
|---|---|---|
| `pt_set_ip` | `device`, `ip`, `mask`, `gateway?`, `port?`, `dhcp?` | Para PC/servidor/portátil. Puerto por defecto `FastEthernet0` |
| `pt_cli` | `device`, `commands[]`, `answer_initial_dialog?` | Comandos tal cual; devuelve la salida nueva. Responde `no` al diálogo inicial del router |
| `pt_config` | `device`, `config`, `save?` | Texto IOS multilínea; añade `enable`/`configure terminal`/`end`. `save` = `write memory` |
| `pt_router_config` | `device`, `spec`, `save?` | Ver esquema abajo |
| `pt_switch_config` | `device`, `spec`, `save?` | Ver esquema abajo |
| `pt_dhcp_server` | `device`, `start_ip`, `mask`, `pool?`, `gateway?`, `dns?`, `max_users?`, `tftp?` | Servicio DHCP de un Server-PT |
| `pt_dns_server` | `device`, `records[{name, ip}]` | Servicio DNS de un Server-PT |
| `pt_server_services` | `device`, `services[]` | Deja encendidos SOLO esos servicios (`dhcp`, `dns`, `http`, `https`, `tftp`, `ftp`, `smtp`, `pop3`, `ntp`, `syslog`, `email`) y apaga el resto. En planes: `"services": ["dhcp"]` dentro de `servers[]` |

### `spec` de `pt_router_config`
```json
{
  "hostname": "R1",
  "interfaces": [
    {"port": "GigabitEthernet0/0", "ip": "192.168.1.1", "mask": "255.255.255.0", "description": "LAN"},
    {"port": "GigabitEthernet0/1"},
    {"port": "GigabitEthernet0/1.10", "vlan": 10, "ip": "192.168.10.1", "mask": "255.255.255.0", "ip_helper": "192.168.1.2"}
  ],
  "static_routes": [{"network": "172.16.0.0", "mask": "255.255.0.0", "next_hop": "10.0.0.2"}],
  "default_route": "10.0.0.2",
  "ospf": {"process": 1, "router_id": "1.1.1.1", "networks": [{"network": "192.168.1.0", "mask": "255.255.255.0", "area": 0}],
           "passive": ["GigabitEthernet0/1"], "default_originate": false},
  "eigrp": {"as_number": 100, "networks": [{"network": "192.168.1.0", "wildcard": "0.0.0.255"}]},
  "rip": {"networks": ["192.168.1.0"]},
  "dhcp_pools": [{"name": "LAN", "network": "192.168.1.0", "mask": "255.255.255.0", "gateway": "192.168.1.1",
                  "dns": ["8.8.8.8"], "excluded": [{"start": "192.168.1.1", "end": "192.168.1.99"}]}],
  "extra": ["banner motd #Solo personal autorizado#"]
}
```
Las máscaras se validan; las redes OSPF/EIGRP aceptan `mask` (el wildcard se calcula) o `wildcard`.

### `spec` de `pt_switch_config`
```json
{
  "hostname": "SW1",
  "vlans": [{"id": 10, "name": "ventas"}, {"id": 20, "name": "it"}],
  "access_ports": [{"ports": "FastEthernet0/2-10", "vlan": 10}, {"ports": ["FastEthernet0/11"], "vlan": 20}],
  "trunk_ports": ["GigabitEthernet0/1"],
  "trunk_allowed_vlans": [10, 20],
  "svi": {"vlan": 99, "ip": "192.168.99.2", "mask": "255.255.255.0", "gateway": "192.168.99.1"},
  "extra": []
}
```

## Pruebas de conectividad
| Herramienta | Parámetros | Notas |
|---|---|---|
| `pt_ping` | `device`, `target`, `wait_seconds?` | Espera a las estadísticas. Los primeros paquetes pueden perderse (ARP/STP) |

## Avanzado
| Herramienta | Parámetros | Notas |
|---|---|---|
| `pt_eval` | `code` | JavaScript (Qt Script, estilo ES3: sin `let`/`const`/flechas/`JSON`) que se ejecuta dentro de PT. Devuelve `String(resultado)` |

## Particularidades de la 6.0.1 (ya manejadas)
- `lw.addDevice(tipo, modelo)` solo admite dos argumentos; la posición se aplica con `moveToLocation`.
- `setName` no impide nombres duplicados por IPC; las herramientas lo comprueban antes.
- `createLink` exige el tipo de cable como entero (8100 recto, 8101 cruzado, 8107 auto…).
- Los routers nuevos piden `Continue with configuration dialog? [yes/no]:`; `pt_cli` responde `no` y Enter.
- `ping` desde un PC devuelve el control antes de terminar; `pt_ping` espera a `Ping statistics`.
- Un error de IPC dentro de un script se captura con `try/catch` **solo si la ventana Debug del módulo está cerrada**.

## Modelos verificados en 6.0.1.0011
`2911`, `2960-24TT`, `PC-PT`, `Switch-PT-Empty`, `Router-PT-Empty`, `Server-PT`, `Laptop-PT`, `AccessPoint-PT`, `AccessPoint-PT-A`.
El resto de modelos del catálogo salen de las imágenes y la ayuda de la instalación y se marcan "sin verificar".
