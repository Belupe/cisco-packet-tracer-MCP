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
