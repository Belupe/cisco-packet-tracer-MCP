# reglas.md — Convenciones del usuario (nombres, IPs, VLANs, puertos…)

> **Este archivo manda.** Cuando un asistente (Claude en VS Code, Claude Code…) cree o modifique algo en Packet Tracer,
> tiene que **leerlo antes** y aplicarlo por encima de cualquier valor por defecto de la documentación o del MCP.
>
> **Para el asistente:**
> 1. Lee este archivo entero antes de proponer nombres, IPs, VLANs o posiciones.
> 2. Aplica solo lo que esté escrito aquí. Donde ponga **PENDIENTE**, no hay regla: **pregunta al usuario** (una pregunta corta)
>    y propón anotar la respuesta en la sección 10. No inventes convenciones.
> 3. Si una petición contradice una regla, avisa antes de construir y deja que el usuario decida.
> 4. Antes de construir una red grande, enseña el plan con nombres e IPs (`pt_build_topology` con `dry_run: true`).
>
> **Para el usuario:** sustituye cada `PENDIENTE` por tu regla. Las filas en cursiva marcadas «ejemplo» son solo ilustrativas:
> bórralas o cámbialas. Lo que no rellenes, el asistente te lo preguntará.

---

## 1. Nombres de los equipos
Patrón general: **PENDIENTE** — por ejemplo `<TIPO>-<SEDE>-<NN>` (*ejemplo*, no es una regla).

| Tipo de equipo | Prefijo / patrón | Ejemplo de nombre | Notas |
|---|---|---|---|
| Router | PENDIENTE | PENDIENTE | |
| Switch | PENDIENTE | PENDIENTE | |
| Switch multicapa | PENDIENTE | PENDIENTE | |
| PC | PENDIENTE | PENDIENTE | |
| Portátil | PENDIENTE | PENDIENTE | |
| Servidor DHCP | PENDIENTE | PENDIENTE | |
| Servidor DNS | PENDIENTE | PENDIENTE | |
| Otros servidores (web, ftp…) | PENDIENTE | PENDIENTE | |
| Punto de acceso | PENDIENTE | PENDIENTE | |
| Impresora / otros | PENDIENTE | PENDIENTE | |

Reglas de formato:
- Mayúsculas / minúsculas: **PENDIENTE**
- Separador (`-`, `_`, nada): **PENDIENTE**
- Numeración (empieza en 1 o 01, por sede, global…): **PENDIENTE**
- Hostname IOS de routers/switches = nombre del equipo en el mapa: **PENDIENTE** (sí / no)
- Nombre de la sede / ciudad / planta en el nombre: **PENDIENTE**
- Evitar espacios y tildes: **PENDIENTE** (recomendado: sí; la 6.0.1 los admite, pero complican scripts y consola)
- Los nombres **deben ser únicos** (restricción técnica de la 6.0.1: los duplicados se apilan invisibles y no se pueden cablear).

## 2. Direccionamiento IP
- Bloque base: **PENDIENTE** (por ejemplo una red privada 10.x.x.x o 192.168.x.x)
- Tamaño de subred por LAN / VLAN: **PENDIENTE** (por ejemplo /24)
- Reparto por sede / VLAN: **PENDIENTE**

| Sede / VLAN | Red | Gateway | Rango DHCP | Servidores | Notas |
|---|---|---|---|---|---|
| PENDIENTE | PENDIENTE | PENDIENTE | PENDIENTE | PENDIENTE | |

- Gateway de cada LAN: **PENDIENTE** (por ejemplo la primera dirección usable)
- Direcciones reservadas (routers, servidores, impresoras…): **PENDIENTE**
- Enlaces router–router: **PENDIENTE** (por ejemplo /30)
- Máscara en formato `255.255.255.0` (el MCP la valida así; no uses `/24` en los parámetros).
- Equipos finales por DHCP o estáticos: **PENDIENTE**
- Loopbacks / direcciones de gestión: **PENDIENTE**

## 3. VLANs
| ID | Nombre | Uso | Red |
|---|---|---|---|
| PENDIENTE | PENDIENTE | PENDIENTE | PENDIENTE |

- VLAN de gestión / nativa: **PENDIENTE**
- Convención de nombres de VLAN: **PENDIENTE**

## 4. Puertos y cableado
- Puertos para equipos finales (acceso): **PENDIENTE** (por ejemplo desde `FastEthernet0/1` en orden)
- Puertos de enlace entre switches / hacia el router (uplinks, troncales): **PENDIENTE**
- Puerto del router hacia cada LAN: **PENDIENTE**
- Tipo de cable por defecto: **PENDIENTE** (el MCP usa `auto` y reintenta recto/cruzado si PT lo rechaza)
- Dejar puertos libres para ampliar: **PENDIENTE**
- Nº de puertos de los `Switch-PT-Empty` (1–10; por defecto 10): **PENDIENTE**

## 5. Servidores (DHCP, DNS, otros)
- IPs estáticas de los servidores: **PENDIENTE**
- Rango y tamaño del pool DHCP (la 6.0.1 solo admite IP inicial y final; la máscara del pool no se puede cambiar): **PENDIENTE**
- Dominio / sufijo DNS: **PENDIENTE** (por ejemplo `empresa.local`)
- Registros DNS que siempre se crean (el servicio DNS aún no está validado en la 6.0.1): **PENDIENTE**
- Servidor DHCP en cada sede o centralizado: **PENDIENTE**

## 6. Seguridad y credenciales (solo laboratorio)
> Usa únicamente contraseñas de práctica; estas reglas se guardan en el repositorio.

- `enable secret`: **PENDIENTE**
- Usuario y contraseña de consola / SSH: **PENDIENTE**
- Banner (`banner motd`): **PENDIENTE**
- Guardar la configuración (`write memory`) al terminar: **PENDIENTE**

## 7. Posición en el mapa (layout): esquema exacto de clase
> El mapa **debe seguir el esquema de organización que se usa en clase**, tal cual. El asistente no puede improvisar otra disposición:
> si algo no está descrito aquí, pregunta antes de construir y pasa `x`/`y` explícitos en el plan.

Descripción del esquema (texto o dibujo ASCII): **PENDIENTE**

```
PENDIENTE — dibuja aquí el esquema de clase, por ejemplo:

        [ router ]
            |
        [ switch ]
         /  |  \
      [PC][PC][PC]
```

- Imagen o apuntes del esquema (ruta dentro del repositorio, p. ej. `documentación/esquemas/clase.png`): **PENDIENTE**
- Qué va arriba / abajo / a los lados (routers, switches, servidores, equipos finales): **PENDIENTE**
- Orden de los equipos de izquierda a derecha (por nombre, por sede, por VLAN…): **PENDIENTE**
- Posición de cada tipo de switch (núcleo / distribución / acceso) y de qué cuelga cada uno: **PENDIENTE**
- Coordenadas de referencia (x, y) de cada nivel o fila: **PENDIENTE**
- Separación entre equipos (el MCP usa por defecto 130 px en horizontal y 150 px en vertical): **PENDIENTE**
- Cómo se agrupan varias sedes o ciudades en el mapa: **PENDIENTE**
- Enlaces y puertos que deben verse de una forma concreta (por ejemplo, uplinks en un lado): **PENDIENTE**

## 8. Notas y documentación en el mapa
- Añadir notas con IPs / VLANs al mapa: **PENDIENTE**
- Formato de la documentación que debe entregar el asistente al terminar (tabla de equipos, IPs, VLANs…): **PENDIENTE**

## 9. Valores por defecto actuales del MCP (referencia, **no vinculantes**)
Lo que ocurre si este archivo no dice otra cosa. Salen de los ejemplos de `pt601_mcp/docs/ejemplos.md` y del código; el código no
impone gateways ni rangos concretos:
- Máscara por defecto de hosts y servidores: `255.255.255.0`; puerto de PCs/servidores: `FastEthernet0`.
- Ejemplos de la documentación: gateway `.1`, servidores en `.2` y `.3`, DHCP desde `.100`.
- `max_users` del DHCP por defecto: 50 (se traduce a IP final); pool de la 6.0.1: `serverPool`.
- Posiciones: por niveles (routers/nubes → switches → servidores/AP → equipos finales), 130 px × 150 px.
- Nombres de las pruebas del repositorio: prefijo `T-` (`T-R1`, `T-S1`…); no es una convención del usuario.

## 10. Excepciones y anotaciones del usuario
Aquí se apuntan las decisiones nuevas (fecha · regla · motivo). Un asistente puede añadir líneas **solo con permiso del usuario**.

| Fecha | Regla o excepción | Motivo |
|---|---|---|
| | | |
