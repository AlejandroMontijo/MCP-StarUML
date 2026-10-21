# MCP StarUML

Servidor MCP (Model Context Protocol) para leer, validar, editar, dibujar y exportar archivos `.mdj` de
[StarUML](https://staruml.io) sin abrir la aplicación. Está hecho en Python, sin dependencias, y se comunica por
JSON-RPC 2.0 sobre `stdio`.

Con él se puede:

- Consultar el modelo: diagramas, clases, atributos, métodos, asociaciones, mensajes de secuencia, estados y actividades.
- Validar la integridad del archivo, las reglas de robustez (boundary, control, entity) y que las secuencias
  cuadren con el modelo de clases.
- Editar sin romper el archivo: clases, atributos, asociaciones, vistas, líneas, notas y documentación.
- Crear y dibujar diagramas de los 28 tipos que trae StarUML (UML 2.5, SysML, BPMN, ERD, C4, diagrama de flujo, DFD) con
  los símbolos de sus paletas.
- Generar diagramas completos: secuencia, robustez y cualquier otro tipo a partir de listas de elementos y relaciones.
- Exportar a SVG, PNG, JPEG o PDF con el CLI de StarUML y revisar el resultado (líneas que cruzan cajas, textos
  encimados).
- Pasar de código a diagrama y de diagrama a código (Java, Python, TypeScript/JavaScript, C#, Kotlin y Go), y comparar
  los dos.

## Requisitos

- **Python 3.9** o superior.
- **StarUML**, para exportar y ver diagramas. Se busca en `STARUML_MCP_STARUML_BIN`, en las rutas de instalación de
  macOS (`~/Applications`, `/Applications`), Windows (`Program Files`, `%LOCALAPPDATA%\Programs`) y Linux
  (`/opt/StarUML`), y como `staruml` en el `PATH`.
- **Chrome, Chromium o Edge** (opcional), para convertir SVG a PNG y recortar zonas.
- Funciona en macOS, Linux y Windows.

## Instalación

1. Descarga el repositorio:

   ```bash
   git clone https://github.com/AlejandroMontijo/MCP-StarUML.git
   ```

2. Registra el servidor en tu cliente MCP. La mayoría usa un archivo de configuración con este formato:

   ```json
   {
     "mcpServers": {
       "staruml": {
         "command": "python3",
         "args": ["/ruta/a/MCP-StarUML/server.py"]
       }
     }
   }
   ```

   En Windows usa `python` en lugar de `python3` y la ruta con `\\`. También se puede arrancar como módulo:
   `python3 -m staruml_mcp` desde la carpeta del repositorio.

## Herramientas

En la columna **Tipo**:

- **lectura**: no escribe nada.
- **agrega**: solo agrega al modelo.
- **cambia**: puede reemplazar o quitar algo que ya existe, o sobrescribir un archivo.

### Consultar y validar

| Herramienta | Tipo | Qué hace |
|---|---|---|
| `staruml_estado` | lectura | Dice si StarUML está abierto y dónde están su CLI, Chrome y la carpeta de respaldos. `staruml_abierto` es `null` si no se pudo revisar. |
| `staruml_reglas` | lectura | Devuelve las convenciones de trabajo de [`docs/reglas.md`](docs/reglas.md). |
| `mdj_resumen` | lectura | Lista los diagramas (tipo, nombre, id, cuántas vistas, cuál abre por defecto) y cuenta las clases por estereotipo. |
| `mdj_modelo` | lectura | Clases y actores con estereotipo, atributos, métodos y documentación; asociaciones con multiplicidades, roles y navegabilidad; generalizaciones y dependencias. |
| `mdj_secuencia` | lectura | Mensajes numerados de un diagrama de secuencia y el orden de sus lifelines. |
| `mdj_comportamiento` | lectura | Estados y transiciones de un diagrama de estados, o nodos y flujos de uno de actividades. |
| `mdj_catalogo` | lectura | Tipos de diagrama de StarUML y los símbolos de cada paleta, con lo que necesita cada uno. |
| `mdj_geometria` | lectura | Posición y tamaño de las cajas y puntos de las líneas de un diagrama. |
| `mdj_buscar` | lectura | Busca elementos por nombre y/o tipo. |
| `mdj_validar` | lectura | Integridad (ids duplicados, referencias colgantes, `_parent` incoherente, metamodelo) y, con `oose`, reglas de robustez. Por omisión ninguna clase de análisis lleva métodos; con `metodos: "control_getset"` el control puede tenerlos y cada entity solo `getX`/`setX`/`isX` de sus atributos, y con `metodos: "control_entidad"` el control y las entity pueden tenerlos sin exigir get/set (por ejemplo, `guardarX` o `consultarX`). Las boundary y los actores, nunca. Las reglas de mensajes de OOSE se aplican solo a las secuencias de análisis (lifelines de actores y clases de robustez); una secuencia de diseño, con interfaz, fachada u objetos de negocio, no las sigue. |
| `mdj_secuencia_revisar` | lectura | Revisa que las secuencias cuadren con el modelo de clases: que cada lifeline tenga un tipo que exista, que cada mensaje tenga una relación en el modelo (y no vaya contra la navegación), que los mensajes al control sean operaciones suyas con sus parámetros (con `metodos: "todos"`, los de cualquier clase con operaciones; si el control no tiene operaciones, solo da un aviso), operaciones que nadie llama (no los constructores ni los métodos de clase), argumentos que no salen de ningún lado (un argumento que es un tipo, como `buscarCuenta(Long)`, no se revisa) y replies que no regresan a quien llamó o llegan cuando esa llamada ya terminó. Con `clases`, también lo que falta dibujado en ese diagrama y lo que no sale en ninguna secuencia. No repite lo que ya revisa `mdj_validar`. |
| `mdj_diff` | lectura | Diferencias de modelo entre dos `.mdj`: elementos agregados y quitados, cambios de nombre, de atributos y de relaciones. |

### Exportar y ver

| Herramienta | Tipo | Qué hace |
|---|---|---|
| `staruml_exportar` | cambia | Exporta a SVG, PNG, JPEG o PDF con el CLI de StarUML. Elige el diagrama por id, así que funciona con nombres repetidos o con caracteres raros; el archivo lleva el nombre del diagrama (los repetidos, `nombre__id`). Sobrescribe archivos con el mismo nombre. |
| `staruml_ver_visual` | cambia | Exporta un diagrama y lo devuelve como imagen PNG. Guarda una caché en la carpeta temporal y, si se pide, una copia en `salida` (debe ser `.png`; nunca reemplaza otro tipo de archivo). |
| `svg_revisar` | lectura | Revisa un SVG exportado: líneas que cruzan cajas, notas o textos, etiquetas encimadas y textos que se salen. |
| `svg_recortar` | cambia | Recorta una zona de un SVG a PNG con Chrome. La `salida` debe ser `.png` y la zona debe caer dentro del SVG. |

### Código

| Herramienta | Tipo | Qué hace |
|---|---|---|
| `staruml_comparar_codigo` | lectura | Compara un diagrama de clases o de secuencia contra el código y da el porcentaje de coincidencia con lo que falta o sobra: clases, atributos con su tipo, métodos, herencia, asociaciones con su multiplicidad (las que van a una clase que no está en el diagrama no se exigen, como en el código de `staruml_diagrama_a_codigo`) y llamadas. |
| `staruml_diagrama_a_codigo` | cambia | Genera esqueletos de clases en Java, Python, TypeScript o C# con atributos, métodos, herencia y asociaciones (solo hacia clases del mismo diagrama), conservando los tipos del modelo. No reemplaza archivos que ya existan salvo con `sobrescribir: true`. |
| `staruml_codigo_a_diagrama` | cambia | Importa clases, atributos con su tipo y métodos desde el código a un paquete del `.mdj`. Solo agrega lo que falta; con `modo: "sincronizar"` también pone el tipo del código en los atributos que ya existen y reporta lo que el código ya no tiene, sin quitarlo. |
| `staruml_programa_a_diagrama` | cambia | Dibuja el diagrama de clases de un programa ya hecho. Si es grande y tiene varios paquetes, hace un diagrama por paquete. |

### Editar el modelo

| Herramienta | Tipo | Qué hace |
|---|---|---|
| `mdj_respaldar` | agrega | Copia el `.mdj` a la carpeta de respaldos (o a otra) y confirma que quedó idéntico. |
| `mdj_clase_crear` | agrega | Crea una clase (boundary, control, entity o sin estereotipo) o un actor, con atributos y documentación. Falla si ya hay uno con ese nombre en el paquete. |
| `mdj_paquete_crear` | agrega | Crea un paquete. Falla si ya hay uno con ese nombre en el mismo lugar. |
| `mdj_elemento_crear` | agrega | Crea un elemento de cualquier tipo de StarUML sin dibujarlo (nodo, componente, estado, acción, requisito, entidad ERD...). |
| `mdj_relacion_crear` | agrega | Crea una relación de cualquier tipo entre dos elementos sin dibujarla. |
| `mdj_asociacion_crear` | agrega | Crea una asociación entre clases, actores o interfaces, con multiplicidades, roles y navegabilidad. |
| `mdj_asociacion_editar` | cambia | Cambia multiplicidad, rol, navegabilidad o la clase de un extremo de una asociación. |
| `mdj_atributos` | cambia | Deja los atributos de una clase exactamente como se indican (conserva los que ya estaban y quita los que sobran). |
| `mdj_documentacion` | cambia | Pone el texto de documentación de un elemento. |
| `mdj_renombrar` | cambia | Cambia el nombre de un elemento y el texto en todas sus vistas. |
| `mdj_borrar` | cambia | Borra un elemento con lo que contiene, sus relaciones y todas sus vistas, también atributos y operaciones. |

### Dibujar

| Herramienta | Tipo | Qué hace |
|---|---|---|
| `mdj_diagrama_crear` | cambia | Crea un diagrama vacío de cualquier tipo, como lo crea StarUML. Con `por_defecto` le quita esa marca al anterior. |
| `mdj_dibujar` | agrega | Dibuja un símbolo de la paleta de StarUML. Solo los símbolos que en `mdj_catalogo` traen `va_sobre` (puerto, pin, invariante, auto-mensaje...) se ponen `sobre` otro. Note y Note Link van en cualquier diagrama. |
| `mdj_vista_agregar` | agrega | Dibuja en un diagrama un elemento que ya existe; una relación solo entre las vistas de sus extremos. Una clase copia el estilo de otra vista del mismo estereotipo (también si muestra las operaciones) con sus propios atributos y operaciones, y queda del alto con que StarUML la dibuja. |
| `mdj_vista_mover` | cambia | Mueve o cambia el tamaño de una vista; lo que no se indica queda igual. |
| `mdj_linea_ruta` | cambia | Pone los puntos intermedios de una línea y calcula sus extremos igual que StarUML. |
| `mdj_linea_etiqueta` | cambia | Mueve una etiqueta de una línea (multiplicidad, rol o nombre) sin tocar la línea. |
| `mdj_nota` | cambia | Crea una nota o edita una existente; el alto se calcula según el texto. |
| `mdj_diagrama_generar` | agrega | Dibuja un diagrama completo de cualquier tipo a partir de listas de elementos y relaciones, con acomodo por capas o de secuencia. Las líneas se rutean para no cruzar cajas; las que no lo logran se listan en `lineas_que_cruzan_cajas`. Las que llegan por arriba a un actor, un artefacto o una interfaz de bola entran sobre su dibujo. |
| `mdj_secuencia_generar` | cambia | Rehace un diagrama de secuencia desde la lista de lifelines y mensajes: activaciones, espaciado y separación según el texto de los mensajes. Cada clave tiene su propia lifeline aunque se repita el tipo. Con `metodos` la revisión OOSE de la respuesta usa el mismo criterio que `mdj_validar`. |
| `mdj_robustez_generar` | cambia | Dibuja el diagrama de análisis (robustez) de un caso de uso: actores a la izquierda (uno `secundario`, como un servicio de correo, recibe la flecha), pantallas en columna con su nota debajo, un control y el modelo de dominio por capas con su herencia. Reusa los elementos y asociaciones que ya existen; en una asociación reusada solo cambia lo que se pide. Si se le pasan atributos de una entidad que ya existe, la deja con esos. Cada caja (pantallas, control y entidades) se mide con lo que muestra su vista: si copia el estilo de una que muestra las operaciones, también con las suyas. Acepta `metodos` como `mdj_validar`. |

## Seguridad al escribir

1. **StarUML abierto:** las herramientas que escriben el `.mdj` se niegan si la aplicación de StarUML está abierta o si
   no se puede comprobar. Se puede pasar `forzar: true` cuando se sabe que StarUML no tiene ese archivo cargado.
2. **Respaldo:** antes de cada guardado se copia el archivo a `respaldos/` y se compara byte por byte.
3. **Formato de StarUML:** se guarda igual que StarUML (UTF-8, tabuladores, saltos `\n`), así que el archivo abre sin
   cambios de formato.
4. **Revisión antes de escribir:** si el cambio dejaría ids duplicados, referencias colgantes, `_parent` incoherentes o
   números no válidos, no se escribe nada.
5. **Otro archivo:** con `salida: "otro.mdj"` los cambios van a una copia y el original no se toca. La salida debe ser
   `.mdj` y no reemplaza archivos que no lo sean.
6. **Nada se pierde en silencio:** lo que una herramienta omite, quita o no pudo hacer se reporta en la respuesta.

## Variables de entorno (opcionales)

| Variable | Por omisión | Uso |
|---|---|---|
| `STARUML_MCP_BACKUP_DIR` | `respaldos/` del repositorio | Carpeta de respaldos. |
| `STARUML_MCP_BACKUP_KEEP` | `100` | Respaldos que se conservan por archivo (`0` = todos). |
| `STARUML_MCP_STARUML_BIN` | — | Ruta del ejecutable de StarUML. |
| `STARUML_MCP_CHROME_BIN` | — | Ruta de Chrome, Chromium o Edge. |
| `STARUML_MCP_EXPORT_TIMEOUT` | `150` | Segundos máximos de una exportación (acepta decimales). |
| `STARUML_MCP_CHROME_TIMEOUT` | `30` | Segundos máximos de una conversión con Chrome. |
| `STARUML_MCP_LOG_LEVEL` | `WARNING` | Detalle de la bitácora por `stderr`: `DEBUG`, `INFO`, `WARNING` o `ERROR`. |
| `STARUML_MCP_ALLOWED_DIRS` | — | Carpetas permitidas, separadas por `:` (`;` en Windows). Si se define, ninguna ruta puede quedar fuera. |

Las rutas relativas de `salida`, `carpeta`, `carpeta_salida` y `ruta_codigo` se toman desde la carpeta del `.mdj`.

## Ejemplos

Ver un diagrama (`staruml_ver_visual`):

```json
{"archivo": "proyecto.mdj", "diagrama": "cu_1", "salida": "cu_1.png", "max_lado": 1600}
```

Generar un diagrama de secuencia (`mdj_secuencia_generar`):

```json
{
  "archivo": "proyecto.mdj",
  "diagrama": "cu_1_FB",
  "lifelines": [
    {"clave": "asesor", "tipo": "Asesor"},
    {"clave": "pantalla", "tipo": "BC_Registro"},
    {"clave": "control", "tipo": "ControlRegistro"},
    {"clave": "cliente", "tipo": "Cliente"}
  ],
  "mensajes": [
    {"de": "asesor", "a": "pantalla", "nombre": "buscarCliente(rfc)"},
    {"de": "pantalla", "a": "control", "nombre": "buscarCliente(rfc)"},
    {"de": "control", "a": "cliente", "nombre": "consultarCliente(rfc)"},
    {"de": "cliente", "a": "control", "nombre": "cliente", "reply": true},
    {"de": "control", "a": "pantalla", "nombre": "mostrarCliente(cliente)"}
  ]
}
```

Diagrama de clases de un programa ya hecho (`staruml_programa_a_diagrama`):

```json
{"archivo": "proyecto.mdj", "ruta_codigo": "src/main/java", "omitir_accesores": true}
```

## Estructura

```text
server.py              Arranca el servidor (lo que se registra en el cliente MCP)
staruml_mcp/
  servidor.py          Protocolo JSON-RPC y definición de las herramientas
  mdj.py               Lectura, edición, validación y guardado seguro del .mdj
  uml.py               Los 28 tipos de diagrama: crear, dibujar, generar y validar
  robustez.py          Diagrama de robustez
  coherencia.py        Revisión de las secuencias contra el modelo de clases
  render.py            Exportación con el CLI de StarUML, revisión de SVG y recortes
  codigo.py            Lectura y generación de código, y comparación con el diagrama
  programa.py          Diagrama de clases de un programa ya hecho
  datos/               Metamodelo y plantillas de vistas tomados de StarUML
docs/
  reglas.md            Convenciones de modelado (la herramienta staruml_reglas las devuelve)
  catalogo.md          Cada tipo de diagrama con su notación y sus símbolos
herramientas/          Scripts para regenerar las tablas de datos/ desde un StarUML instalado
tests/                 Pruebas (pytest): python3 -m pytest tests
.github/workflows/     CI: ruff y pytest en macOS, Linux y Windows (Python 3.9 y 3.12)
```

## Regenerar las tablas desde StarUML

Las tablas de `staruml_mcp/datos/` salen del StarUML instalado. Para actualizarlas con otra versión:

```bash
python3 herramientas/extraer_metamodelo.py      # tipos, atributos y paletas
python3 herramientas/generar_referencia.py      # StarUML dibuja cada símbolo de cada paleta (salidas/referencia/)
python3 herramientas/extraer_plantillas.py      # plantillas de vistas a partir de ese dibujo
python3 herramientas/generar_catalogo.py        # vuelve a escribir docs/catalogo.md
```
