# reglas.md — Convenciones del usuario (nombres, IPs, VLANs, puertos…)

> **Este archivo manda.** Cuando un asistente (Claude en VS Code, Claude Code…) cree o modifique algo en Packet Tracer,
> tiene que **leerlo antes** y aplicarlo por encima de cualquier valor por defecto de la documentación o del MCP.
>
> **Para el asistente:**
> 1. Lee este archivo entero antes de proponer nombres, IPs, VLANs o posiciones.
> 2. Aplica lo que esté escrito aquí. Donde ponga **PENDIENTE** no hay regla todavía: si el dato hace falta para construir, pregunta
>    (una pregunta corta); no inventes convenciones.
> 3. **Aprende y anota sin pedir permiso** (decisión del usuario, 2026-10-03): cuando deduzcas una costumbre de un trabajo suyo
>    (`pt_snapshot`) o él te la explique, escríbela aquí directamente y dile qué has anotado. Él la corrige si quiere otra redacción.
>    Indica entre paréntesis de qué práctica sale cada regla.
> 4. Si una petición o un enunciado contradice una regla, avisa antes de construir y deja que el usuario decida.
> 5. Antes de construir una red grande, enseña el plan con nombres e IPs (`pt_build_topology` con `dry_run: true`).

Trabajos analizados hasta ahora (2026-10-03): **Práctica 1A — «Ejercicio 1»** (HTTP + DNS, 4 sedes, 172.26.1.x), **Práctica 1B — «Ejercicio 2»**
(HTTP + DNS, 4 sedes), **Práctica 1C — «Ejercicio 3»**
(3 HTTP + DNS, 4 sedes) y **Práctica 2 — «Ejercicio 4 DHCP»**. Una regla marcada **(2 de 2)** se vio en la P1C y la P2; la **P1B la cumple
también** salvo donde se diga lo contrario (son las excepciones de la sección 12). La **P1A** las cumple igualmente: nombre = último octeto,
desde la `.10`, sede de abajo primero, portátiles antes que PCs, `Fa0/1` de subida, cruzado entre switches, máscara de clase, gateway `.1`,
DNS del servidor en todos los equipos y servicios de fábrica. Con cuatro trabajos, estas reglas se dan por firmes.

---

## 1. Nombres de los equipos
**Regla principal: un equipo final se llama como el último octeto de su IP.** El equipo con `192.168.1.10` se llama `10`;
el de `172.26.1.28` se llama `28`. Sin prefijo, sin ceros delante. (Explicado por el usuario; **2 de 2**.)

| Tipo de equipo | Prefijo / patrón | Ejemplo de nombre | Notas |
|---|---|---|---|
| Router | PENDIENTE | PENDIENTE | |
| Switch de sede | `SW-<Sede>` | `SW-Madrid`, `SW-Cadiz`, `SW-Usera`, `SW-Arguelles` | Sede con mayúscula inicial y sin tilde (2 de 2) |
| Switch de servidores | el nombre que dé el enunciado | `SW-ServidorDHCP` (P2), `SW-ServerMadrid` (P1C) | Sin espacios aunque el enunciado ponga `SW- ServerMadrid` |
| Switch multicapa | PENDIENTE | PENDIENTE | |
| PC | último octeto de la IP | `11`, `12`, `13` | |
| Portátil | último octeto de la IP | `10`, `14` | |
| Servidor DHCP | `Server DHCP` | `Server DHCP` | Con espacio (P2) |
| Servidor DNS | `DNS` | `DNS` | Solo el servicio (P1B, P1C) |
| Servidores HTTP | `HTTP` si hay uno; `HTTP-<n>` si hay varios | `HTTP` (P1B); `HTTP-1`, `HTTP-2`, `HTTP-3` (P1C) | El enunciado dice `HTTP1`; en el mapa va con guion |
| Otros servidores (ftp, correo…) | PENDIENTE (previsible: el nombre del servicio) | PENDIENTE | |
| Punto de acceso | PENDIENTE | PENDIENTE | |
| Impresora / otros | PENDIENTE | PENDIENTE | |

Reglas de formato:
- El enunciado puede escribir los nombres en mayúsculas (`SW-MADRID`); en el mapa se ponen como `SW-Madrid`.
- Separador: guion (`SW-Madrid`).
- **Nunca nombres `CopyNN` / `CopySW-…`**: son los que pone Packet Tracer al copiar y pegar un equipo; no son una convención.
  Si el asistente duplica algo, lo renombra según estas reglas.
- Los equipos finales con IP por DHCP se llaman igual (por el número que les corresponde), ver sección 2.
- Hostname IOS de los switches: **no se cambia** (se queda `Switch`); solo se pone el nombre en el mapa. Los switches no llevan
  ninguna configuración por consola en las prácticas sin VLAN (Práctica 2). Routers: **PENDIENTE**.
- Los nombres **deben ser únicos** (restricción técnica de la 6.0.1: los duplicados se apilan invisibles y no se pueden cablear).

## 2. Direccionamiento IP
- **La red la marca el enunciado** con las IPs de los servidores, y la **máscara es la de la clase de esa red**:
  `192.168.1.x` → `255.255.255.0` (P2); `172.26.1.x` → `255.255.0.0` (P1C). Todos los equipos usan los mismos tres primeros octetos que los servidores.
- **Los equipos finales empiezan SIEMPRE en la `.10` y suben de uno en uno** (`.10`, `.11`, `.12`…), sin saltos entre sedes. (2 de 2.)
- Las direcciones por debajo de la `.10` son para infraestructura: gateway `.1` y servidores (`.2`, `.3`, `.4`, `.5`… las que dé el enunciado).
- **Gateway: la `.1` de la red** (`192.168.1.1`, `172.26.1.1`), aunque no haya router; se pone en equipos finales **y en servidores**. (2 de 2.)
- **DNS:** si el enunciado menciona un servidor DNS, aunque no se configure el servicio (aún no se ha visto en clase), su IP se pone en el campo
  **DNS Server de la configuración IP estática** (no en el servicio DNS) de **todos** los equipos finales y de **todos** los servidores,
  incluido el propio DNS (P1C: `172.26.1.2`; P1B: `192.168.1.3`). Si no hay servidor DNS, se deja vacío (P2).
- Si el enunciado da otra red (p. ej. «rango desde 192.168.0.10» con el servidor en 192.168.1.3), es una incoherencia: avisar y,
  salvo que el usuario diga otra cosa, usar la red del servidor.

| Sede / VLAN | Red | Gateway | Rango DHCP | Servidores | Notas |
|---|---|---|---|---|---|
| Todas (una sola LAN) | 192.168.1.0 / 255.255.255.0 | 192.168.1.1 | desde .10 | DHCP en .3 | Práctica 2 |
| Todas (una sola LAN) | 172.26.1.0 / 255.255.0.0 | 172.26.1.1 | — (estáticas .10–.28) | DNS .2, HTTP-1 .3, HTTP-2 .4, HTTP-3 .5 | Práctica 1C |
| Todas (una sola LAN) | 192.168.1.0 / 255.255.255.0 | 192.168.1.1 | — (estáticas .20–.38) | HTTP .2, DNS .3 | Práctica 1B (empieza en .20: ver sección 12) |

**Orden en que se reparten los números** (2 de 2). P2: Cádiz portátil 10, PCs 11–13; Madrid portátiles 14–17, PCs 18–20.
P1C: Centro 10–14, Vallecas 15–20, Arguelles 21–24, Usera 25–28 (en cada una, portátiles primero):
1. Se empieza por la sede de **abajo** del mapa y se sigue hacia la de arriba.
2. Dentro de cada sede, primero los **portátiles** y después los **PCs**.
3. Dentro de cada fila, el número **más bajo a la derecha** y el más alto a la izquierda.

- Equipos finales por DHCP o estáticos: lo dice cada enunciado. Estáticos: IP = `192.168.1.<nombre>`.
- **Qué se configura en un equipo final** (PC o portátil, puerto `FastEthernet0`), y nada más:
  - Estático: IP `<red>.<nombre>`, máscara de la clase, gateway `.1`, DNS = IP del servidor DNS si lo hay.
  - DHCP: solo marcar DHCP; IP, máscara y gateway los entrega el servidor.
  - No se cambia nada más (ni módulos, ni IPv6, ni inalámbrico). PCs = `PC-PT`, portátiles = `Laptop-PT`, tal como salen.
- Enlaces router–router: **PENDIENTE**
- Máscara en formato `255.255.255.0` (el MCP la valida así; no uses `/24` en los parámetros).
- Loopbacks / direcciones de gestión: **PENDIENTE**

**Renombrar o renumerar equipos que ya existen** (consejo del usuario):
- Dos equipos no pueden llamarse igual (la ventana de PT da error; por el MCP se quedarían duplicados invisibles). Al cambiar una serie de
  números hay que elegir el orden para que el nombre nuevo **nunca coincida con uno que todavía esté en uso**:
  si los números **bajan** (20–38 → 10–27), empezar por el **más bajo**; si **suben**, empezar por el **más alto**.
- Al renombrar se cambia también la IP, para que nombre e IP sigan coincidiendo. Herramienta: `pt_rename_device` (comprueba duplicados) + `pt_set_ip`.
- Si sobra un equipo, se borra, se quita su módulo del switch (puertos justos) y se renumera el resto sin dejar huecos.

## 3. VLANs
| ID | Nombre | Uso | Red |
|---|---|---|---|
| PENDIENTE | PENDIENTE | PENDIENTE | PENDIENTE |

- VLAN de gestión / nativa: **PENDIENTE**
- Convención de nombres de VLAN: **PENDIENTE**

## 4. Puertos y cableado
Los switches son `Switch-PT-Empty` con módulos `PT-SWITCH-NM-1CFE` (un puerto `FastEthernet<n>/1` por ranura). (Práctica 2.)

- **Cómo se monta un `Switch-PT-Empty`:** se le añaden módulos `PT-SWITCH-NM-1CFE` (FastEthernet de cobre) en ranuras consecutivas
  empezando por la 0, sin huecos, y se deja encendido. Todos los módulos son de ese mismo tipo (ni fibra ni Gigabit).
- **Nº de puertos: los justos**, uno por cable (sin puertos de sobra). Ej.: `SW-Madrid` con 7 equipos = 8 puertos; `SW-Cadiz` con 4 = 5;
  `SW-ServidorDHCP` = 3. En el plan: `ports` = nº de equipos + nº de enlaces a otros switches/servidor.
- **Switch de sede (2 de 2):** `FastEthernet0/1` es el enlace hacia el switch del servidor. Después, los equipos en el orden en que se ven
  en el mapa: primero la fila de PCs de izquierda a derecha, luego la fila de portátiles de izquierda a derecha
  (`SW-Madrid`: Fa1/1→20, Fa2/1→19, Fa3/1→18, Fa4/1→17, Fa5/1→16, Fa6/1→15, Fa7/1→14).
- **Switch de servidores:** los switches de sede ocupan puertos seguidos **de arriba abajo según el mapa**, y los servidores también
  de arriba abajo (2 de 2). Lo que cambia entre prácticas es qué bloque va primero:
  - P1C (varios servidores): **primero los servidores** (Fa0/1→HTTP-1, Fa1/1→HTTP-2, Fa2/1→HTTP-3, Fa3/1→DNS) y luego las sedes
    (Fa4/1→SW-Usera, Fa5/1→SW-Arguelles, Fa6/1→SW-Vallecas, Fa7/1→SW-Centro).
  - P2 (un servidor): primero las sedes (Fa0/1→SW-Madrid, Fa1/1→SW-Cadiz) y al final el servidor (Fa2/1).
  - P1B: también **primero los servidores** (Fa0/1→HTTP, Fa1/1→DNS) y luego el enlace hacia las sedes (Fa2/1).
  - P1A: también servidores primero (Fa0/1→HTTP, Fa1/1→DNS) y luego las sedes.
  - **Regla (3 de 4): servidores primero y después los enlaces a switches de sede, de arriba abajo.** La P2 queda como excepción.
- **Cables (2 de 2):** switch ↔ switch **cruzado** (línea discontinua); switch ↔ PC/portátil/servidor **recto**. Pasar siempre `cable` explícito
  en el plan (`cross` / `straight`), no `auto`.
- Puerto del router hacia cada LAN: **PENDIENTE**

## 5. Servidores (DHCP, DNS, otros)
- **Un servidor por servicio** (3 de 3).
- **Los servicios solo se tocan si el enunciado pide configurar ese servicio** (aclarado por el usuario, 2026-10-03):
  - Si el enunciado pide algo del servicio (p. ej. «Servidor-DHCP: Rango IP desde…»), se configura y **se apagan todos los demás servicios**
    de ese servidor, como en la P2.
  - Si el enunciado solo dice «Asignar al HTTP/DNS la IP = …», **el servidor se deja de fábrica**: no se enciende ni se apaga nada y no se
    crean registros DNS (P1B y P1C: HTTP, HTTPS, FTP, TFTP, correo, NTP y Syslog encendidos de fábrica; DNS apagado y sin registros).
  - «Demostrar que podemos conectarnos al Servidor Web» (P1B) se hace con el HTTP de fábrica y la **IP** del servidor, sin tocar el DNS.
- En el servidor DHCP (P2) solo queda encendido DHCP
  (HTTP, HTTPS, DNS, TFTP, FTP, correo, NTP y Syslog apagados). Herramienta: `pt_server_services` (`services: ["dhcp"]`), o
  `"services": ["dhcp"]` en `servers[]` del plan.
- Los servidores cuelgan **todos del mismo switch de servidores** (`SW-ServidorDHCP`, `SW-ServerMadrid`), nunca del switch de una sede. (2 de 2.)
- **Orden de los servidores:** el del enunciado, de arriba abajo en el mapa, y en ese mismo orden en los puertos de su switch
  (P1B: HTTP, DNS; P1C: HTTP-1, HTTP-2, HTTP-3, DNS; P1A tras la corrección: HTTP, DNS).
- IPs de los servidores: las que dé el enunciado (P1C: DNS `.2`, HTTP-1 `.3`, HTTP-2 `.4`, HTTP-3 `.5`), con gateway `.1` y DNS como en la sección 2.
- IP estática del servidor DHCP: `192.168.1.3`, máscara `255.255.255.0`.
- Pool DHCP (`serverPool`): gateway `192.168.1.1`, sin DNS (`0.0.0.0`), **inicio en `.10`** (los equipos empiezan siempre en la 10).
  *Nota:* en el archivo de la Práctica 2 el pool empezaba en `.3` y los equipos recibieron `.4`–`.14`; no es la costumbre, es el valor
  que quedó en ese ejercicio.
- La 6.0.1 solo admite IP inicial y final del pool; la máscara no se puede cambiar.
- Para que con DHCP el nombre coincida con la IP, pedir la IP (`ipconfig /renew`) **en orden de nombre** (10, 11, 12…): PT reparte
  las direcciones por orden de petición. *(Hipótesis del asistente a partir de los datos de la Práctica 2; sin comprobar aún.)*
- Dominio / sufijo DNS: **PENDIENTE** · Registros DNS que siempre se crean: **PENDIENTE** (se verá en la práctica de DNS).

## 6. Seguridad y credenciales (solo laboratorio)
> Usa únicamente contraseñas de práctica; estas reglas se guardan en el repositorio.

- `enable secret`: **PENDIENTE**
- Usuario y contraseña de consola / SSH: **PENDIENTE**
- Banner (`banner motd`): **PENDIENTE**
- Guardar la configuración (`write memory`) al terminar: **PENDIENTE**

## 7. Posición en el mapa (layout): esquema exacto de clase
> El mapa **debe seguir el esquema de organización que se usa en clase**, tal cual. El asistente no puede improvisar otra disposición:
> pasa siempre `x`/`y` explícitos en el plan calculados con este esquema (el `auto_layout` del MCP todavía no lo sigue).

El esquema es **el mismo en las dos prácticas** (2 de 2); solo cambia el tamaño. Dibujo de la Práctica 2 (coordenadas reales del `.pkt`):

```
                                  [PC] [PC] [PC]                 fila de PCs (arriba del switch)
                          [SW-Madrid]
                         /         [Port][Port][Port][Port]      fila de portátiles (debajo del switch)
 192.168.1.3            /
[Server DHCP]──[SW-ServidorDHCP]
                        \         [PC] [PC] [PC]
                         \[SW-Cadiz]
                                   [Port]
```

- **De izquierda a derecha:** servidor → su switch → switches de sede → equipos finales.
- **Servidor y su switch** a la misma altura, centrados en vertical entre las sedes: servidor `x≈65`, switch `x≈220`, `y≈355`.
- **Switches de sede** en una columna (`x≈385`), una sede encima de otra, separadas ~360 px en vertical
  (`SW-Madrid` `y≈165`, `SW-Cadiz` `y≈525`). La primera sede del enunciado va arriba.
- **Equipos de cada sede**, a la derecha de su switch, en dos filas:
  - **PCs en la fila de arriba**, ~75–120 px por encima del switch; el primero ~115 px a la derecha del switch y ~95 px entre uno y otro
    (Madrid: `y≈94`, `x≈506, 591, 696`; Cádiz: `y≈405`, `x≈501, 579, 674`).
  - **Portátiles en la fila de abajo**, ~50–85 px por debajo del switch; el primero ~65 px a la derecha del switch y ~90 px entre uno y otro
    (Madrid: `y≈252`, `x≈454, 543, 636, 726`; Cádiz: `y≈577`, `x≈534`).
- Numeración dentro de la fila: el más alto a la izquierda, el más bajo a la derecha (sección 2).
- Si hay que repetir el montaje (dos versiones del mismo ejercicio), la segunda va a la derecha, desplazada ~775 px en `x`, con la misma forma.
- **Varios servidores (P1C):** en columna a la izquierda (`x≈30`), uno debajo de otro cada ~125 px, en el orden del enunciado
  (HTTP-1 `y≈355`, HTTP-2 `486`, HTTP-3 `611`, DNS `733`). Su switch a la derecha (`x≈195`), a la altura del centro de esa columna (`y≈546`).
- **Más de dos sedes (P1C, 4 sedes):** misma columna de switches de sede (`x≈455`), en el orden del enunciado de arriba abajo, separadas
  ~240–290 px (`SW-Usera 110`, `SW-Arguelles 401`, `SW-Vallecas 640`, `SW-Centro 934`). El mapa crece hacia abajo; es normal que no quepa en pantalla.
- **Medidas de la P1C** (más holgadas que en la P2; usar estas en redes grandes): fila de PCs ~88 px por encima del switch y fila de portátiles
  ~47–100 px por debajo; el primer equipo ~140 px a la derecha del switch y ~145 px entre uno y otro; PCs y portátiles alineados en las mismas columnas
  (`x≈595, 745, 885, 975`).
- **P1B** (misma forma): servidores `x≈30` (`HTTP y≈430`, `DNS y≈563`), su switch `x≈154, y≈498`; columna de sedes `x≈545` separadas ~250 px
  (`95, 345, 597, 840`); filas de PCs ~70 px por encima y de portátiles ~70 px por debajo; ~125 px entre equipos.
- **P1A** (misma forma, más separada): servidores `x≈50` (`DNS y≈405`, `HTTP y≈710`), su switch `x≈436, y≈585`; columna de sedes `x≈850`
  separadas ~315 px (`120, 433, 746, 1067`); PCs ~100 px por encima y portátiles ~80–100 px por debajo; ~100–150 px entre equipos.
- **Medidas para construir** (referencia sacada de las prácticas 1B, 1C y 2): servidores `x≈30` cada ~130 px; switch de servidores ~150 px a su derecha y centrado
  en vertical; switches de sede ~300 px más a la derecha, cada ~260 px; filas de equipos a ±80 px del switch; primer equipo ~130 px a la derecha
  del switch y ~130 px entre equipos.
- Con routers o VLAN: **PENDIENTE** (se completará con las siguientes prácticas).

## 8. Notas y documentación en el mapa
- **Nota de texto con la IP del servidor encima de él** (`192.168.1.3` sobre `Server DHCP`). El MCP aún no sabe crear notas
  (`lw.addNote`, firma sin comprobar en la 6.0.1): pendiente de implementar.
- Lo que pide el enunciado como «identificación de los equipos» (nombre, IP, máscara, gateway): formato de entrega **PENDIENTE**.

## 9. Valores por defecto actuales del MCP (referencia, **no vinculantes**)
Lo que ocurre si este archivo no dice otra cosa. Salen de los ejemplos de `pt601_mcp/docs/ejemplos.md` y del código; el código no
impone gateways ni rangos concretos:
- Máscara por defecto de hosts y servidores: `255.255.255.0`; puerto de PCs/servidores: `FastEthernet0`.
- Ejemplos de la documentación: gateway `.1`, servidores en `.2` y `.3`, DHCP desde `.100`.
- `max_users` del DHCP por defecto: 50 (se traduce a IP final); pool de la 6.0.1: `serverPool`.
- Posiciones: por niveles (routers/nubes → switches → servidores/AP → equipos finales), 130 px × 150 px. **No sigue el esquema de clase.**
- `Switch-PT-Empty`: 10 puertos si no se indica `ports` (la regla de la sección 4 pide los justos).
- Nombres de las pruebas del repositorio: prefijo `T-` (`T-R1`, `T-S1`…); no es una convención del usuario.

## 11. Cómo se leen los enunciados de clase
Los enunciados son un **esquema de puntos y subpuntos**, y la jerarquía dice cómo se monta la red. (Práctica 2, explicado por el usuario.)

- **Conservar los niveles.** Un punto en negrita es un bloque; lo que va debajo, sin negrita, son sus subpuntos. Al extraer el texto de un
  Word los niveles se pierden (todas las viñetas salen iguales): la jerarquía está en la **negrita** y en la sangría, no en el nivel de lista.
  Si hay duda, pedir captura del enunciado.
- En el título, «N nodos redes LAN» cuenta **todos los switches**, incluido el de servidores (P1C: «5 nodos» = 4 sedes + `SW-ServerMadrid`).
- **«Switch PT Empty:»** con subpuntos = todos los switches de la lista son de ese modelo (puede aparecer dos veces: sedes y servidores):
  - `SW-<SEDE> (n pc, m portátiles)` = un switch por sede con esos equipos finales colgando de él.
  - `SW-Servidor<SERVICIO>` = **switch intermedio propio del servidor**. Es la pieza clave del esquema: el servidor se conecta SOLO a ese
    switch, y de ese switch salen los enlaces a los switches de sede. Nunca conectar el servidor directamente a un switch de sede, ni las
    sedes entre sí.

    ```
    Servidor ── SW-Servidor<SERVICIO> ──┬── SW-<Sede1> ── equipos
                                        └── SW-<Sede2> ── equipos
    ```
- **«Servidor-<SERVICIO>: …»** con subpuntos = configuración de ese servidor (rango del servicio, IP propia).
- **«Asignar identificación de los equipos»** (Nombre, IP, Máscara, Gateway) = aplicar las secciones 1 y 2: nombre = último octeto, etc.
- **«Demostrar …»** = prueba que hay que enseñar al final (aquí, ver la IP recibida por DHCP en tres equipos).
- Lo que el enunciado no dice (posiciones, puertos, tipo de cable, numeración, servicios apagados) sale de este archivo.

## 12. Excepciones vistas en los trabajos (no son reglas)
Cosas de un archivo concreto que no siguen el patrón. No se imitan al construir; si hacen falta, se pregunta.

- **P1B: numeración desde la `.20`** (20–38) en vez de la `.10`: fue un olvido (confirmado por el usuario). Corregido por el asistente el
  2026-10-03: ahora va de la `.10` a la `.27`.
- **P1B: switch intermedio `sw-1`** entre `SW-ServerPlanetas` y los cuatro switches de sede (`x≈385`, a la altura del switch de servidores;
  Fa0/1 hacia servidores, Fa1/1–Fa4/1 a las sedes de arriba abajo). No está en el enunciado y no aparece en P1C ni P2, donde las sedes
  cuelgan directamente del switch de servidores. Regla: **sin switch intermedio** salvo que el enunciado lo pida.
- **P1B: `SW-Jupiter` tenía 3 portátiles** y el enunciado dice 2. Corregido: portátil sobrante borrado y su módulo quitado (puertos justos).
- **P1B, despistes de configuración** (corregidos): `35` y `36` sin IP; `33` con gateway `.3` y sin DNS; `30` con su propia IP como DNS.
- **P2: en el switch del servidor las sedes van antes que el servidor** (en P1B y P1C es al revés), y el pool DHCP empezaba en la `.3`.

- **P1A (corregido por el asistente el 2026-10-03):** el servidor `HTTP` no tenía IP (ahora `172.26.1.3`, máscara `255.255.0.0`, gateway `.1`,
  DNS `.2`); el switch de servidores se llamaba `ServerMadrid` (ahora `SW-ServerMadrid`); tenía un puerto de más (módulo quitado); sus enlaces
  a las sedes no iban de arriba abajo (ahora Fa2/1→Goya, Fa3/1→SOL, Fa4/1→GranVia, Fa5/1→Moncloa); y los servidores estaban en orden contrario
  al de sus puertos (ahora `HTTP` arriba y `DNS` abajo).

## 10. Excepciones y anotaciones del usuario
Decisiones nuevas (fecha · regla · motivo). El asistente las anota directamente y avisa al usuario.

| Fecha | Regla o excepción | Motivo |
|---|---|---|
| 2026-10-03 | El asistente anota las costumbres aprendidas sin pedir confirmación; solo informa de lo anotado | El usuario no quiere confirmar cada regla |
| 2026-10-03 | La carpeta `ejemplos/` (enunciados y trabajos de clase) no se sube a GitHub y se borra al terminar | Material de clase, solo para aprender |
