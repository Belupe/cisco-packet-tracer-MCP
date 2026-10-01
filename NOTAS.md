# Notas del proyecto

## Versión objetivo
**Cisco Packet Tracer 6.0.1.0011** (confirmada por el usuario en Help → About).

Evidencia en `documentación/`: IOS 15, routers 1941/2901/2911 y HSRP (`whatsNew.htm`),
Script Modules `.pts` desde la 5.3.3 (`scriptModules.htm`), IPC por TCP puerto 39000 (`ipc.htm`).

## Objetivo
Equivalente local de https://github.com/Mats2208/MCP-Packet-Tracer adaptado a la 6.0.1:
servidor MCP en Python + puente HTTP en 127.0.0.1 (con token) + extensión `.pts`
que ejecuta el JavaScript dentro de Packet Tracer.

## Restricciones de la 6.0.1
- Script Engine = Qt Script (ECMAScript antiguo): sin `let`/`const`/funciones flecha; `JSON` no garantizado.
- Catálogo de dispositivos y cables limitado a lo que existe en la 6.0.1.
- Pendiente: referencia de la API IPC (archivos `.pki`), necesaria para no inventar métodos.

## Hallazgos del árbol de instalación (pt_arbol.txt)
- 1500 archivos / 97 carpetas. **No hay archivos `.pki`**: la referencia de la API IPC no viene instalada.
- El catálogo de dispositivos va compilado en `PacketTracer6.exe`; no hay lista en disco.
- Qt 4 (`QtScript4.dll`): confirma Qt Script antiguo.
- `extensions/IpcLog` (ExApp) registra llamadas IPC: útil para descubrir la API.
- `extensions/scriptTemplates/*.ptst` son plantillas de Script Module (cifradas).
- `templates/*.ptd` solo 4 plantillas: 1841+WIC-2T, 2621XM+NM-2FE2W+2×WIC-2T, 2811+NM-ESW-161+2×WIC-2T, PC inalámbrico.
- Dispositivos vistos en `art/`: routers 1841, 1941, 2620XM, 2621XM, 2811, 2901, 2911; switches 2950, 2950T, 2960-24TT, 3560;
  Linksys WRT300N, hub, repeater, bridge, cloud, DSL/cable modem, AP, server, PC, laptop, PDA, tablet, impresora, TV, teléfono IP 7960, teléfono analógico, HomeVoIP, splitter coaxial.
- `saves/` trae 49 ejemplos `.pkt/.pka` (cifrados).

## Siguiente paso
Ejecutar `sondeo/sondeo_ipc.js` en PT 6.0.1 y volcar la salida para conocer la API real.
