# cisco-packet-tracer-MCP
Servidor MCP local para controlar **Cisco Packet Tracer 6.0.1** desde Claude: crear y cablear equipos, configurar IP, IOS y
servicios de servidor, hacer ping y sacar capturas de las ventanas, sin mover el ratón.

**Instalación y uso:** [`pt601_mcp/README.md`](pt601_mcp/README.md) (Python portátil, registrar el servidor en Claude y cargar el
módulo en Packet Tracer).

- Resolver una práctica: deja el enunciado en [`Ejercicios/`](Ejercicios/README.md) y pídeselo al asistente
- Referencia de herramientas: [`pt601_mcp/docs/herramientas.md`](pt601_mcp/docs/herramientas.md)
- Ejemplos de planes: [`pt601_mcp/docs/ejemplos.md`](pt601_mcp/docs/ejemplos.md)
- Cómo funciona por dentro: [`GUIA_COMPLETA.md`](GUIA_COMPLETA.md)
- Skill para el asistente: [`skill/SKILL.md`](skill/SKILL.md)

Opcional: crea un `reglas.md` en la raíz con tus convenciones (nombres, IPs, VLANs, puertos, posiciones); el asistente lo lee antes de
construir. Es un archivo personal: está en `.gitignore`.
