# Contexto del Proyecto: MCP StarUML (Guía para Claude Code)

Este documento proporciona el contexto completo del repositorio, arquitectura, historial de cambios recientes, decisiones de diseño y convenciones para sesiones de trabajo con Claude Code.

---

## 1. Visión General del Proyecto

**MCP StarUML** es un servidor Model Context Protocol (**MCP**) autónomo desarrollado en Python 3.9+ (sin frameworks pesados, basado en JSON-RPC 2.0 por `stdio`) que permite a asistentes de IA interactuar con proyectos StarUML (`.mdj`) sin abrir la interfaz gráfica:
- **Inspección visual:** Exporta diagramas a imágenes PNG de alta fidelidad y las entrega directamente en el protocolo MCP (`staruml_ver_visual`).
- **Sincronización con código:** Compara diagramas de clases y de secuencia contra código fuente (**Java, Python, TypeScript/JavaScript, C#, Kotlin y Go**), calculando porcentaje de alineación y reportando discrepancias (`staruml_comparar_codigo`).
- **Ingeniería inversa y generación:** Genera esqueletos de código limpios a partir del modelo (`staruml_diagrama_a_codigo`) e importa código fuente a diagramas `.mdj` (`staruml_codigo_a_diagrama`).
- **Edición segura:** Respaldos automáticos verificados byte a byte, prevención de sobreescritura si StarUML tiene el archivo abierto, y validación estricta de reglas OOSE (Boundary-Control-Entity).

---

## 2. Estructura de Archivos del Repositorio

Desde el 2026-10-11 el código vive en el paquete `staruml_mcp/` y la documentación en `docs/`:

```text
MCP StarUML/
├── server.py              # Punto de entrada: python3 server.py (o python3 -m staruml_mcp)
├── staruml_mcp/
│   ├── servidor.py        # Protocolo JSON-RPC y registro de las 41 herramientas (@tool + esquema + anotaciones)
│   ├── mdj.py             # Lectura, manipulación JSON, validación (reglas_oose) y guardado seguro del .mdj
│   ├── uml.py             # Motor genérico: los 28 tipos de diagrama y sus símbolos desde plantillas y metamodelo
│   ├── robustez.py        # Diagrama de análisis (robustez) con la disposición del curso (mdj_robustez_generar)
│   ├── coherencia.py      # Revisión de secuencias contra el modelo de clases (mdj_secuencia_revisar)
│   ├── render.py          # Exportación con el CLI de StarUML, revisión de SVG y recorte a PNG (Chrome)
│   ├── codigo.py          # Parsers de código, generadores y comparación diagrama <-> código
│   ├── programa.py        # Diagrama de clases de un programa ya hecho (acomodo por capas y ruteo sin cruces)
│   └── datos/             # metamodelo.json y plantillas_vistas.json (generados desde StarUML)
├── docs/
│   ├── reglas.md          # Convenciones de modelado; la herramienta staruml_reglas lo devuelve
│   └── catalogo.md        # Catálogo de diagramas y símbolos con secciones de UML 2.5.1 (generado)
├── herramientas/          # Scripts que regeneran datos/ y docs/catalogo.md, y la extensión de StarUML que dibuja la referencia
├── README.md              # Uso: instalación, herramientas, seguridad, variables de entorno
├── CLAUDE.md              # Este archivo
└── .gitignore             # Ignora scratch/, pruebas/, respaldos/, salidas/ y referencias/
```

Imports entre módulos: relativos dentro del paquete (`from . import mdj as M`); desde fuera,
`from staruml_mcp import mdj as M`. Los respaldos van a `respaldos/` en la raíz (o `STARUML_MCP_BACKUP_DIR`).

> **Sin `tests/` ni CI:** el dueño del repo decidió (2026-10-11) no versionar pruebas ni integración continua.
> Las pruebas se hacen con scripts temporales fuera del repositorio (ver la sección 5). `pruebas/`, `respaldos/` y
> `salidas/` son carpetas locales e ignoradas.

---

## 3. Resumen de lo Realizado en la Sesión Anterior

1. **Reconstrucción y Verificación Completa del Modelo:**
   - Se reconstruyó desde la plantilla inicial el caso de uso *"Gestionar contratación y orden de entrega"*.
   - **Diagrama de Clases (`cu_1`):** 27 clases/actores (6 boundary, 1 control, 18 entity, 2 actores), 50 asociaciones, 92 atributos y 6 notas de especificación.
   - **Diagrama de Secuencia Básico (`cu_1_FB`):** 25 lifelines y 66 mensajes cubriendo los flujos F1 a F5.
   - Se configuró `defaultDiagram: true` en `cu_1_FB` para que StarUML lo abra directamente.
   - Puntuación de comparación contra el modelo de referencia: **20/20 (100.0% match)** con **0 violaciones OOSE**.

2. **Generación de los Flujos Alternativos (`cu_1_FA`):**
   - Se creó el diagrama de secuencia para los flujos alternativos en la interacción `flujos alternativos` del `.mdj`:
     - **FA1:** Búsqueda de cliente no registrado y captura de datos.
     - **FA2:** Evaluación técnica negativa y selección de equipo alternativo (CAT 336).
     - **FA3:** Unidad no disponible en periodo y selección de unidad/fechas alternativas.
     - **FA4:** Cancelación de la solicitud antes de formalizar.
     - **FA5:** Rechazo de la propuesta final en F5 (sin generación de contrato ni orden de entrega).
   - Métricas de `cu_1_FA`: **14 lifelines**, **40 mensajes**, activaciones anidadas correctas y 0 errores OOSE.

3. **Nuevas Capacidades de Inspección Visual y Sincronización:**
   - Creación de `staruml_compare.py` (hoy `staruml_mcp/codigo.py`): parser políglota (Java, Python, TypeScript, C#) para comparar entidades, métodos, atributos, multiplicidades de asociaciones y flujo de llamadas en secuencias.
   - Creación de `staruml_ver_visual`: genera y entrega imágenes PNG de alta resolución en tiempo real vía MCP.
   - Creación de herramientas de generación de esqueletos e importación de código hacia el `.mdj`.

4. **Reglas de Git y Limpieza:**
   - **Prohibido mencionar "Figma"** en los commits, código o documentación.
   - **Prohibido subir la carpeta `pruebas/`** al repositorio remoto (ya fue desindexada con `git rm -r --cached`).
   - El `README.md` y `reglas.md` fueron reescritos para ser **100% genéricos y agnósticos** de cualquier proyecto o curso particular.

---

## 3b. Campaña de pruebas y plan de mejora (2026-09-29)

- `PLAN_DE_MEJORA.md` (retirado del repo el 2026-10-11) documentaba 56 bugs confirmados y su corrección; en ese momento `tests/` los cubría con regresiones.
- El guardado es transaccional: `Doc.save()` rechaza un cambio que agregue ids duplicados, referencias colgantes, `_parent` incoherente o NaN.
- Nada se pierde en silencio: el importador de código es aditivo por defecto (`modo: "sincronizar"` explícito), el generador no sobrescribe sin `sobrescribir: true` y la regeneración de secuencias conserva las notas.
- La detección de "StarUML abierto" cubre macOS, Linux y Windows y bloquea si no puede verificar (`forzar: true` para omitirla).
- Render portable: StarUML y Chrome se buscan en rutas típicas, `PATH` y `STARUML_MCP_STARUML_BIN` / `STARUML_MCP_CHROME_BIN`; sin `sips` ni `perl`.
- Fase 3 completa: bitácora por `stderr` (`STARUML_MCP_LOG_LEVEL`), coherencia caso de uso ↔ paquete de robustez, generador C#, parsers de Kotlin y Go, auto-mensajes en `mdj_secuencia_generar`, y lectura (`mdj_comportamiento`) y validación de diagramas de estados y de actividades.
- La geometría de los auto-mensajes sigue la forma estándar de UML; falta confirmarla abriendo el archivo en StarUML.
- `staruml_programa_a_diagrama` (v2.1.0) dibuja el diagrama de clases de un programa Java completo. Las vistas de enumeración y de realización de interfaz siguen el metamodelo de StarUML pero solo se confirman con `tests/test_staruml_real.py` en una máquina con StarUML. La regla "en análisis no se ponen métodos" de `reglas_oose` aplica solo a boundary, control, entity y actores, así que esas clases de diseño no se marcan.

## 3c. Todos los diagramas y simbolos de StarUML (2026-10-01, v2.2.0)

- Fuentes: el metamodelo y las paletas (`toolbox/*.json`) salen del `resources/app.asar` de StarUML 6.3.1
  (`herramientas/extraer_metamodelo.py`). Las plantillas las dibuja el propio StarUML: la extension
  `herramientas/staruml_extension/mcp-referencia` corre con `StarUML exec semilla.mdj -c mcp:dibujar-todo`
  (`herramientas/generar_referencia.py`) y `herramientas/extraer_plantillas.py` saca cada simbolo de
  `salidas/referencia/referencia.mdj` (antes `pruebas/referencia/`). La especificacion OMG UML 2.5.1 no se versiona; `docs/catalogo.md` cita sus secciones.
- 28 tipos de diagrama y 419 simbolos con plantilla. Sin plantilla: Interface Realization en SysML BDD y Constraint
  Parameter en SysML parametrico (StarUML los rechaza en un dibujo generico).
- Marcadores de plantilla: `@n` (objetos propios), `@diagrama`, `@dueno` / `@dueno2...` (contenedor del diagrama y sus
  ancestros), `@cola` / `@cabeza` (+ `_m` para su elemento), rutas como `@dueno/regions/0` o `@cabeza/>tail/>model`
  ('>' sigue una referencia, '..' sube) y `@ext:` (se resuelve por tipo y nombre, p. ej. estereotipos del perfil).
- Detalles de StarUML 6.3.1 descubiertos al generar la referencia: `exec` se cae (codigo 127) si recibe `-a`, asi que la
  extension lee `plan.json` junto al `.mdj`; los dialogos de confirmacion bloquean la ventana oculta (la extension los
  contesta y aplica antes el perfil estandar); el simbolo Frame abre un selector de elemento (se crea por la fabrica);
  una contencion de un elemento en si mismo lo saca del arbol y StarUML ya no lo guarda.
- El metamodelo de StarUML no marca tipos abstractos ni exige el tipo declarado de cada campo (guarda manejadores de
  excepcion en `Activity.edges`); `uml.es_abstracto` lo infiere y `validar_metamodelo` solo exige que el campo exista.
- Galeria (`tests/galeria.py`, `tests/test_galeria.py`): un diagrama de cada tipo con todos los simbolos de su paleta,
  construido con `mdj_diagrama_generar`. Con StarUML, `test_staruml_dibuja_la_galeria` exporta los 28 y no deja pasar de
  `MAX_OBSERVACIONES_GALERIA` (13) observaciones de `svg_revisar`; las que quedan son etiquetas de lineas sobre nombres de
  contenedores (sujeto, paquete), sobre una activacion o sobre la etiqueta de un puerto, y lineas largas entre elementos
  anidados de raices distintas (no se rutean, van rectas).
- `mdj_diagrama_generar`: carriles en bandas (`_capas_flujo`, camino mas largo), disposicion `secuencia`, `sobre` hacia
  lineas, claves de relaciones y vistas existentes (`@marco`), marcos que envuelven todo al final, entrada lateral a
  figuras con el nombre abajo (`_ruta_lateral`) y aviso de lineas que atraviesan contenedores que encapsulan
  (`ENCAPSULAN`); `mdj_validar` hace la misma revision en cualquier diagrama (`lineas_que_salen`).
- `svg_revisar` respeta `dominant-baseline` (StarUML usa `central` y `text-before-edge`), mide los textos girados con su
  matriz y no cuenta como linea el dibujo propio de una figura sin nada adentro.
- Auto-mensajes en secuencias: StarUML ignora el left/top de la etiqueta y la pone con alpha/distance desde el tramo
  vertical del lazo. `generar_secuencia` usa alpha +pi/2 y distancia de medio ancho: queda a la derecha del lazo, sin
  tapar la activacion (`test_staruml_dibuja_los_auto_mensajes` ya pasa).

## 3d. Retro de las pruebas con casos reales (2026-10-01)

Hallazgos al generar a mano casos completos (pedido en linea, ferreteria CU-01) y como quedaron resueltos en la
herramienta, para que quien la use obtenga el diagrama correcto a la primera:

- Robustez con `mdj_diagrama_generar`: los iconos de boundary/control/entity se estiran si se les da tamano, no
  muestran atributos, la paleta de clases no trae actor y el ruteo generico deja flechas sueltas. Ahora el generador
  lo rechaza y remite a `mdj_robustez_generar` (staruml_mcp/robustez.py).
- `mdj_robustez_generar` sigue la convencion del curso (ejemplo que dio el usuario): actor | pantallas en columna con
  nota | control | modelo de dominio por capas segun la navegabilidad, rutas de programa.py (sin cruces), flechas
  de navegacion por defecto y sin lineas control-entidad salvo `lineas_control`. Las notas buscan el primer lugar que
  no toque las diagonales. Las etiquetas de los extremos en tramos verticales se separan de la linea.
- La direccion de las asociaciones importa: un ciclo (Pedido -> Cliente con Cliente -> Solicitud -> ... -> Pedido)
  manda entidades al fondo con lineas largas; escribirlas en el sentido de la navegacion (Cliente -> Pedido).
- Una entidad con muchas asociaciones (Producto) junta sus multiplicidades: el ruteo reparte puertos, pero las
  etiquetas de lineas que corren juntas por el mismo canal todavia pueden tocarse (unas pocas observaciones de
  svg_revisar; pendiente en programa.rutas).
- Clase asociacion en `mdj_diagrama_generar`: su caja se coloca en el primer lugar libre de cajas y lineas (tambien
  la suya) y esas relaciones se dibujan al final.
- `mdj_validar` (metamodelo) admitia solo las vistas de la paleta del diagrama: las de la paleta comun (notas, texto,
  figuras) van en cualquier diagrama (`uml.COMUNES`).

## 3e. Auditoría, reorganización y revisión de secuencias (2026-10-11)

- Auditoría completa con reproducciones en StarUML real: se corrigieron más de 40 fallas. Entre ellas: ids duplicados
  en `mdj_secuencia_generar` con dos lifelines del mismo tipo; `svg_recortar`/`staruml_ver_visual` que podían pisar el
  `.mdj` (`salida` solo `.png`); `mdj_borrar` de atributos y operaciones; extremos de asociación que aceptaban diagramas;
  caché de `ver_visual` por ruta, contenido e id; exportar por id con nombres repetidos o raros; importador que solo
  agrega y busca la clase solo en el paquete; mensajes de `UMLMessage` en la interacción; bucles de contención en
  `mdj_diagrama_generar`; parsers por indentación (Python), sin `;` (TypeScript) y clases parciales (C#).
- Anotaciones MCP revisadas en las 41 herramientas: `readOnlyHint` solo si no escribe nada y `destructiveHint` si
  reemplaza, quita o sobrescribe algo.
- `mdj_robustez_generar`: al reusar una asociación solo cambia lo que se pide (antes la pisaba con valores por omisión);
  acepta `actores[].secundario` y `generalizaciones`.
- `mdj_validar` acepta `metodos: "control_getset"` (el control con métodos y cada entity solo get/set/is de sus atributos).
- Tipos en la ida y vuelta código <-> modelo: se conservan char, short, byte, float, Long, BigDecimal y fechas
  (`Date` en C# es `DateOnly`); un tipo deducido de un valor no pisa uno declarado.
- `mdj_clase_crear` y `mdj_paquete_crear` no duplican nombres en el mismo contenedor.
- Nueva herramienta `mdj_secuencia_revisar` (coherencia.py, solo lectura): lifelines contra el modelo, relación y
  navegación para cada mensaje, métodos del control con su número de argumentos, argumentos sin origen, replies que
  regresan a quien llamó (también en fragmentos alt/par) y clases del diagrama que no salen en ninguna secuencia.
- Pendientes conocidos: `depende_de` en robustez exige repetir la asociación aunque exista en el modelo; la revisión OOSE
  interna de robustez usa la regla de métodos por omisión; `mdj_diagrama_crear` de tipos que no son de clases da
  "ambiguo" si un caso de uso y un paquete se llaman igual; `mdj_dibujar` no ofrece la nota fuera de la paleta de clases
  (usar `mdj_nota`); las líneas del modelo de dominio pueden cruzarse entre sí (no sobre cajas).

## 4. Convenciones y Reglas Inquebrantables

1. **Reglas de Git:**
   - Mensajes de commit claros, concisos y sin mencionar herramientas externas no relacionadas.
   - **Claude no figura como autor ni coautor:** nada de líneas `Co-Authored-By` ni `Claude-Session` en los commits; el autor es el dueño del repositorio.
   - Mantener `pruebas/`, `respaldos/` y `salidas/` fuera del control de versiones. No se versionan `tests/` ni CI (decisión del dueño, 2026-10-11).
   - Los cambios entran por pull request a `main`; si cambia una herramienta, se actualiza su fila del README.
2. **Seguridad en `.mdj`:**
   - Antes de escribir en un `.mdj`, verificar que StarUML no esté corriendo con ese archivo abierto para evitar que sobreescriba cambios (usar `forzar: true` solo si se sabe seguro).
   - Siempre respaldar antes de guardar (`doc.save(backup=True)`).
   - Indentación por tabuladores y `ensure_ascii=False` para mantener paridad byte a byte con StarUML.
3. **Reglas de Robustez OOSE (Jacobson):**
   - Exactamente **1 clase control** por caso de uso.
   - Actores solo interactúan con Boundary.
   - Boundary solo interactúa con Actores y Control (nunca boundary con boundary ni boundary con entity).
   - Control interactúa con Boundary y Entity.
   - Entity solo interactúa con Entity si existe asociación explícita.
   - Boundary y Control **sin atributos ni métodos** en fase de análisis (la regla de métodos aplica a las clases de robustez y actores; las de diseño sí llevan métodos).

---

## 5. Comandos de Verificación Local

No hay suite versionada. Antes de proponer un cambio:

```bash
# 1. Errores de sintaxis, nombres sin definir e imports sin usar
ruff check --select F,E9 .

# 2. Que el servidor arranque y publique sus herramientas (respuesta JSON en una sola línea)
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"x","version":"1"}}}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | python3 server.py

# 3. Probar la herramienta cambiada con un script temporal (fuera del repo) que arranque server.py por stdio,
#    trabaje sobre una COPIA de un .mdj, revise mdj_validar (0 duplicados, 0 colgantes) y, si dibuja algo,
#    lo exporte con staruml_exportar y lo pase por svg_revisar.
```
