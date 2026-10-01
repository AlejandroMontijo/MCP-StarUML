# MCP StarUML

Servidor de Protocolo de Contexto de Modelo (**MCP** - Model Context Protocol) para interactuar, inspeccionar, editar, renderizar y sincronizar archivos `.mdj` de **StarUML** directamente desde asistentes de IA (Claude Code, Claude Desktop, Cursor, Antigravity, etc.) sin necesidad de abrir la aplicación gráfica.

Desarrollado en Python puro (3.9+), sin dependencias externas pesadas, comunicándose mediante el protocolo estándar MCP (JSON-RPC 2.0 por `stdio`).

---

## Características Principales

- **Inspección Visual en Tiempo Real:** Renderiza y entrega diagramas directamente en el chat en formato PNG de alta fidelidad para visión multimodal de la IA.
- **Sincronización Bidireccional con Código:** Compara diagramas (Clases y Secuencias) contra bases de código en **Java, Python, TypeScript/JavaScript, C#, Kotlin y Go**, calculando el porcentaje de alineación (atributos, tipos, métodos, asociaciones con su multiplicidad y flujo de llamadas) y reportando discrepancias.
- **Generación de Código:** Genera esqueletos limpios y tipados a partir del diseño de clases y asociaciones.
- **Ingeniería Inversa:** Importa clases, atributos y métodos desde código fuente hacia paquetes y diagramas del `.mdj`.
- **Diagrama de un Programa Ya Hecho:** Dibuja el diagrama de clases completo de un programa (Java por defecto) con sus paquetes, herencia, interfaces, enumeraciones y asociaciones, acomodado por niveles y sin líneas que crucen cajas; crea el `.mdj` si no existe.
- **Edición Segura y Confiable:** Respaldos automáticos antes de escribir, prevención de sobreescritura si la aplicación está abierta y validación de integridad referencial.
- **Generador Inteligente de Secuencias:** Construye diagramas de secuencia completos con lifelines, ordenación automática, activación con pila de llamadas y cálculo de separación para evitar solapamiento de textos.
- **Todos los Diagramas y Símbolos de StarUML:** Crea, dibuja, lee y valida los 28 tipos de diagrama que trae StarUML: los de UML 2.5 (clases, paquetes, objetos, estructura compuesta, componentes, despliegue, perfil, casos de uso, actividades, estados, secuencia, comunicación, tiempos, vista general de interacción y flujo de información) y los de sus extensiones (ERD, flowchart, DFD, BPMN, C4, SysML, wireframe, mapa mental, AWS y Google Cloud), con cada uno de los 419 símbolos de sus paletas. Cada símbolo se instancia desde una plantilla que dibujó el propio StarUML, así el archivo queda como si se hubiera hecho a mano en la aplicación. `uml_catalogo.md` los describe uno por uno.
- **Diagramas Completos de una Vez:** `mdj_diagrama_generar` acomoda por capas cualquier diagrama a partir de listas de elementos y relaciones, anida contenedores (nodos, estados compuestos, particiones) y rutea las líneas sin cruzar cajas.

---

## Instalación y Configuración

### 1. Claude Code (CLI)

```bash
claude mcp add staruml -- python3 "/ruta/absoluta/a/MCP-StarUML/server.py"
```

Para asociar el servidor únicamente al proyecto actual:
```bash
claude mcp add staruml --scope project -- python3 "/ruta/absoluta/a/MCP-StarUML/server.py"
```

Verifica la conexión con:
```bash
claude mcp list
```

### 2. Claude Desktop

Agrega la configuración en tu archivo `claude_desktop_config.json`:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "staruml": {
      "command": "python3",
      "args": ["/ruta/absoluta/a/MCP-StarUML/server.py"]
    }
  }
}
```

### Requisitos del Sistema

- **Python 3.9** o superior.
- **StarUML** instalado, necesario para la exportación por CLI. Se busca en `STARUML_MCP_STARUML_BIN`, en las rutas típicas de macOS (`~/Applications`, `/Applications`), Windows (`Program Files`, `%LOCALAPPDATA%\Programs`) y Linux (`/opt/StarUML`), y en el `PATH` (`staruml`).
- **Google Chrome, Chromium o Edge** (opcional, para rasterizar y recortar PNG). Se busca en `STARUML_MCP_CHROME_BIN`, en las rutas típicas y en el `PATH`.
- Funciona en **macOS, Linux y Windows** (la entrada y salida del protocolo es siempre UTF-8).

### Variables de Entorno (opcionales)

| Variable | Default | Uso |
|---|---|---|
| `STARUML_MCP_BACKUP_DIR` | `<carpeta del servidor>/respaldos` | Carpeta de respaldos. |
| `STARUML_MCP_BACKUP_KEEP` | `100` | Respaldos que se conservan por archivo (`0` = todos). |
| `STARUML_MCP_STARUML_BIN` | — | Ruta del ejecutable de StarUML. |
| `STARUML_MCP_CHROME_BIN` | — | Ruta de Chrome/Chromium/Edge. |
| `STARUML_MCP_EXPORT_TIMEOUT` | `150` | Segundos máximos de una exportación por CLI. |
| `STARUML_MCP_CHROME_TIMEOUT` | `30` | Segundos máximos de un rasterizado con Chrome. |
| `STARUML_MCP_LOG_LEVEL` | `WARNING` | Nivel de la bitácora por `stderr` (`DEBUG`, `INFO`, `WARNING`, `ERROR`). En `DEBUG` registra cada herramienta con sus argumentos y los comandos externos; en `INFO`, tiempos y respaldos. |
| `STARUML_MCP_ALLOWED_DIRS` | — | Carpetas permitidas, separadas por `:` (`;` en Windows). Si se define, ninguna ruta de lectura o escritura puede quedar fuera. |

Las rutas relativas de `salida`, `carpeta`, `carpeta_salida` y `ruta_codigo` se resuelven desde la carpeta del `.mdj`.

---

## Catálogo de Herramientas (39)

### Inspección Visual y Renderizado
| Herramienta | Descripción |
|---|---|
| `staruml_ver_visual` | Renderiza un diagrama a PNG de alta resolución y lo entrega en el protocolo MCP para inspección visual directa. |
| `staruml_exportar` | Exporta diagramas a SVG, PNG, JPEG o PDF mediante el CLI de StarUML. |
| `svg_revisar` | Detecta problemas de layout en SVG: líneas sobre cajas/notas/etiquetas, textos encimados y desbordes. |
| `svg_recortar` | Recorta una región específica o redimensiona un SVG a PNG con Chrome headless. |

### Sincronización e Integración con Código
| Herramienta | Descripción |
|---|---|
| `staruml_comparar_codigo` | Compara un diagrama (Clases o Secuencia) contra código fuente (Java, Python, TS/JS, C#, Kotlin, Go). Devuelve métrica de sincronización (%) y elementos faltantes. |
| `staruml_diagrama_a_codigo` | Genera esqueletos de código limpios y tipados (Java, Python, TypeScript, C#) a partir de las clases y relaciones de un diagrama. No reemplaza archivos existentes salvo con `sobrescribir: true`. |
| `staruml_programa_a_diagrama` | Dibuja el diagrama de clases de un programa ya hecho (Java por defecto; también Python, TS/JS, C#, Kotlin y Go): paquetes del programa, clases, interfaces y enumeraciones con atributos y métodos (visibilidad, `static`, `abstract`), herencia, `implements` y asociaciones desde los campos (rol, multiplicidad y navegabilidad en ambos sentidos). Acomodo por niveles sin encimar cajas ni cruzar líneas; un diagrama para todo el programa o uno por paquete (cada uno con las clases de otros paquetes con que se relaciona, compactas); con más de 60 clases en varios paquetes elige por paquete solo; crea el `.mdj` si no existe. |
| `staruml_codigo_a_diagrama` | Importa clases, interfaces, enumeraciones, atributos y métodos desde código fuente (los mismos lenguajes que la comparación) hacia el modelo y diagrama `.mdj`. Por defecto solo agrega; con `modo: "sincronizar"` deja exactamente los atributos del código y reporta los quitados. |

### Lectura, Consulta y Diagnóstico
| Herramienta | Descripción |
|---|---|
| `staruml_estado` | Informa si StarUML está en ejecución y la ubicación del CLI, Chrome y respaldos. |
| `staruml_reglas` | Devuelve las reglas y convenciones de modelado y arquitectura (`reglas.md`). |
| `mdj_resumen` | Lista diagramas del archivo, vistas, diagrama por defecto y conteo por estereotipo. |
| `mdj_modelo` | Extrae clases, atributos, métodos, documentación y asociaciones con roles y multiplicidades. |
| `mdj_secuencia` | Extrae la secuencia ordenada de mensajes, lifelines, tipos y respuestas (replies). |
| `mdj_catalogo` | Tipos de diagrama que soporta StarUML con su nombre corto y, para uno, su paleta símbolo por símbolo (forma, vista, qué conecta cada línea y sobre qué va cada símbolo que se pone encima de otro). |
| `mdj_comportamiento` | Lee un diagrama de estados (estados, compuestos, actividades entry/do/exit y transiciones con disparador, guarda y efecto) o de actividades (acciones, nodos de control, particiones y flujos con guarda). |
| `mdj_geometria` | Coordenadas, dimensiones e identificadores de vistas de cajas y líneas de un diagrama de cualquier tipo. |
| `mdj_buscar` | Búsqueda flexible de elementos por nombre, texto o tipo UML (`UMLClass`, `UMLAssociation`, etc.). |
| `mdj_validar` | Valida integridad estructural (IDs duplicados, referencias rotas) y reglas OOSE/robustez, notación de íconos, estereotipos guardados como texto, cajas encimadas, coherencia entre cada caso de uso y su paquete de análisis, y reglas de diagramas de estados y de actividades. Revisa además el metamodelo de StarUML: tipos desconocidos, elementos en campos que no los admiten, vistas que el diagrama no admite y líneas sin extremos válidos; y las líneas que atraviesan un contenedor que encapsula (salen de algo anidado hacia afuera sin pasar por un puerto). |
| `mdj_diff` | Calcula diferencias semánticas y estructurales entre dos archivos `.mdj`. |

### Edición Segura del Modelo
| Herramienta | Descripción |
|---|---|
| `mdj_respaldar` | Crea una copia de respaldo verificada byte por byte. |
| `mdj_clase_crear` | Crea clases con estereotipo (`boundary`, `control`, `entity`) o actores (`estereotipo: "actor"`), con atributos y documentación. |
| `mdj_paquete_crear` | Crea un paquete dentro del modelo o de otro paquete. |
| `mdj_diagrama_crear` | Crea un diagrama vacío de cualquiera de los 28 tipos (`despliegue`, `componentes`, `estados`, `bpmn`, `erd`...) con lo que StarUML crea junto con él (interacción y marco, máquina de estados y región, actividad, modelo de datos), opcionalmente como el que abre por defecto. |
| `mdj_dibujar` | Dibuja un símbolo de la paleta como lo haría StarUML: el elemento de modelo y su vista. Cajas en `x, y` (o en el primer lugar libre), las que van encima de otra con `sobre` (puerto, pin, región) y las líneas con `desde` y `hasta`. |
| `mdj_diagrama_generar` | Dibuja un diagrama completo de cualquier tipo a partir de listas de elementos (con `dentro` para anidar y `sobre` para pegar puertos, pines o restricciones a una caja o a una línea) y relaciones: acomodo por capas, carriles contiguos (swimlanes, pools y lanes) con el flujo en un solo sentido, `disposicion: "secuencia"` para lifelines y mensajes, contenedores del tamaño de su contenido, marcos que envuelven el diagrama y líneas sin cruces. Avisa cuando una línea sale de un elemento anidado hacia afuera de un contenedor que encapsula (componente, clase, bloque, actividad estructurada). |
| `mdj_elemento_crear` | Crea un elemento de cualquier tipo de StarUML sin dibujarlo, validado contra el metamodelo (contenedor y propiedades). |
| `mdj_relacion_crear` | Crea una relación de cualquier tipo (dirigida o con extremos) entre dos elementos sin dibujarla. |
| `mdj_renombrar` | Renombra un elemento y sincroniza automáticamente las etiquetas de todas sus vistas. |
| `mdj_documentacion` | Actualiza la documentación o especificación de responsabilidades de un elemento. |
| `mdj_atributos` | Sincroniza la lista exacta de atributos y actualiza su compartimento visual. |
| `mdj_asociacion_crear` | Crea asociaciones con multiplicidades, roles, navegabilidad y trazado de ruta visual opcional. |
| `mdj_asociacion_editar` | Modifica multiplicidades, roles, extremos o navegabilidad de una asociación existente. |
| `mdj_borrar` | Borrado en cascada: elimina el elemento, sus elementos contenidos, relaciones y vistas asociadas (y lo quita de las listas de referencias, como `constrainedElements`). |
| `mdj_vista_agregar` | Dibuja un elemento existente en un diagrama: clases y actores en notación estándar o icónica, y cualquier otro elemento o relación con el símbolo de su tipo en la paleta del diagrama. |
| `mdj_vista_mover` | Ajusta coordenadas y dimensiones de una vista de caja en un diagrama. |
| `mdj_linea_ruta` | Define los puntos de quiebre de una línea calculando los extremos de conexión con las cajas. |
| `mdj_linea_etiqueta` | Ajusta la posición de etiquetas de multiplicidad, rol o nombre (alpha y distance). |
| `mdj_nota` | Crea o edita notas explicativas con cálculo automático de dimensiones según el texto. |
| `mdj_secuencia_generar` | Genera o regenera por completo un diagrama de secuencia a partir de especificación de lifelines y mensajes (incluidos auto-mensajes). |

---

## Seguridad al Escribir

Para prevenir corrupción accidental de archivos:

1. **Detección de Proceso Activo:** Las herramientas de escritura se niegan a modificar el archivo si la aplicación de StarUML está abierta (macOS, Linux o Windows) o si no se puede comprobar, evitando sobreescrituras accidentales desde la interfaz gráfica. (Se puede omitir conscientemente mediante `forzar: true`).
2. **Respaldo Automático Previo:** Todo guardado genera un respaldo en la carpeta `respaldos/` (configurable mediante la variable de entorno `STARUML_MCP_BACKUP_DIR`) verificado byte a byte.
3. **Formato Nativo:** Mantiene el formato idéntico al de StarUML (`ensure_ascii=False`, indentación por tabuladores, saltos de línea `\n` también en Windows).
4. **Validación Previa:** Antes de escribir se revisa la integridad del modelo en memoria. Si el cambio dejaría ids duplicados, referencias colgantes, `_parent` incoherentes o números NaN/infinito, no se escribe nada.
5. **Simulación con Archivo Alternativo:** Con el parámetro opcional `salida: "otro_archivo.mdj"`, los cambios se escriben en una copia sin alterar el archivo original.
6. **Sin Pérdidas Silenciosas:** `staruml_codigo_a_diagrama` solo agrega atributos salvo con `modo: "sincronizar"`, `staruml_diagrama_a_codigo` no reemplaza archivos existentes salvo con `sobrescribir: true`, y `mdj_secuencia_generar` conserva las notas del diagrama. Lo que se omite, quita o descarta se reporta en la respuesta.

---

## Ejemplos de Uso

### 1. Visualizar un Diagrama en el Chat
```json
{
  "archivo": "ruta/al/modelo.mdj",
  "diagrama": "DiagramaPrincipal",
  "salida": "renders/diagrama.png",
  "max_lado": 1600
}
```

### 2. Comparar Diagrama contra Código Fuente
```json
{
  "archivo": "ruta/al/modelo.mdj",
  "diagrama": "DiagramaClases",
  "ruta_codigo": "src/main/java/com/miempresa/modelo",
  "lenguaje": "java"
}
```

### 3. Diagrama de Clases de un Programa Java Ya Hecho
```json
{
  "archivo": "ruta/al/proyecto.mdj",
  "ruta_codigo": "ruta/al/programa",
  "omitir_accesores": true
}
```
Crea (o completa) el `.mdj` con un paquete del mismo nombre que la carpeta del programa, sus paquetes Java anidados y el diagrama "Diagrama de clases". Los campos cuyo tipo es otra clase del programa se dibujan como asociaciones (colecciones con `0..*`); las constantes `static` quedan como atributos. Las carpetas y clases de pruebas se omiten salvo con `incluir_pruebas`. Si el programa tiene más de 60 clases repartidas en varios paquetes, hace un diagrama por paquete; en cada uno, las clases de otros paquetes con las que se relaciona aparecen compactas, con "(from paquete)". `"diagrama_por"` fuerza uno u otro modo; para rehacerlo después de cambiar el código, `"reemplazar": true`.

### 4. Generar Esqueletos de Código desde el Modelo
```json
{
  "archivo": "ruta/al/modelo.mdj",
  "diagrama": "DiagramaClases",
  "lenguaje": "typescript",
  "carpeta_salida": "src/models"
}
```

### 5. Generar un Diagrama de Secuencia
```json
{
  "archivo": "ruta/al/modelo.mdj",
  "diagrama": "SecuenciaAutenticacion",
  "lifelines": [
    {"clave": "usr", "tipo": "Usuario"},
    {"clave": "ui", "tipo": "LoginBoundary"},
    {"clave": "ctrl", "tipo": "AuthControl"},
    {"clave": "repo", "tipo": "UsuarioRepository"}
  ],
  "mensajes": [
    {"de": "usr", "a": "ui", "nombre": "ingresarCredenciales(user, pass)"},
    {"de": "ui", "a": "ctrl", "nombre": "autenticar(user, pass)"},
    {"de": "ctrl", "a": "repo", "nombre": "buscarPorUsuario(user)"},
    {"de": "repo", "a": "ctrl", "nombre": "datosUsuario", "reply": true},
    {"de": "ctrl", "a": "ui", "nombre": "mostrarSesionIniciada()"}
  ]
}
```

### 6. Generar un Diagrama de Despliegue
```json
{
  "archivo": "ruta/al/modelo.mdj",
  "diagrama": "Arquitectura",
  "elementos": [
    {"simbolo": "Node", "nombre": "Servidor web"},
    {"simbolo": "Node", "nombre": "Tomcat", "dentro": "Servidor web"},
    {"simbolo": "Artifact", "nombre": "tienda.war", "dentro": "Tomcat"},
    {"simbolo": "Node", "nombre": "Servidor BD"},
    {"simbolo": "Node", "nombre": "Navegador"}
  ],
  "relaciones": [
    {"simbolo": "Communication Path", "desde": "Navegador", "hasta": "Servidor web", "nombre": "HTTPS"},
    {"simbolo": "Communication Path", "desde": "Servidor web", "hasta": "Servidor BD", "nombre": "JDBC"}
  ]
}
```
El diagrama se crea antes con `mdj_diagrama_crear` (`"tipo": "despliegue"`). Los nombres de símbolo son los de la paleta de StarUML; `mdj_catalogo` con `"diagrama": "despliegue"` los lista.

---

## Estructura del Repositorio

- `server.py`: Servidor central MCP (protocolo JSON-RPC 2.0 y registro de herramientas).
- `staruml_mdj.py`: Motor de lectura, manipulación del árbol JSON, validación y edición segura del formato `.mdj`.
- `staruml_render.py`: Módulo de exportación CLI, rasterizado de alta calidad e inspección de SVG.
- `staruml_compare.py`: Motor de sincronización, escaneo de código fuente (Java, Python, TypeScript/JavaScript, C#, Kotlin, Go) e ingeniería inversa.
- `staruml_programa.py`: Diagrama de clases de un programa completo: modelo, acomodo por capas y ruteo de líneas.
- `staruml_uml.py`: Motor genérico para todos los diagramas y símbolos: instancia plantillas, crea elementos y relaciones validados contra el metamodelo, genera diagramas completos y valida.
- `staruml_metamodelo.json`: Tabla derivada del metamodelo y de las paletas del StarUML instalado (tipos, herencia, atributos, vistas por diagrama).
- `plantillas_vistas.json`: Lo que StarUML crea al dibujar cada símbolo de cada paleta y al crear cada tipo de diagrama.
- `uml_catalogo.md`: Catálogo de diagramas y símbolos con la sección de la especificación UML 2.5.1 de cada uno (generado).
- `herramientas/`: Scripts que regeneran las tablas y el catálogo desde el StarUML instalado (ver abajo).
- `reglas.md`: Manual de convenciones de arquitectura, buenas prácticas OOSE y lineamientos de modelado.
- `tests/`: Suite de pruebas (pytest) con modelos `.mdj` sintéticos. `tests/galeria.py` describe un diagrama de cada uno de los 28 tipos con todos los símbolos de su paleta (sirve de ejemplo de cómo pedir cada tipo a `mdj_diagrama_generar`).
- `PLAN_DE_MEJORA.md`: Hallazgos de las pruebas y estado del plan de mejora.

---

## Pruebas

```bash
python -m pip install pytest
python -m pytest tests -q
```

- Sin StarUML ni Chrome las pruebas que los necesitan se omiten solas; la exportación se prueba con un CLI de StarUML simulado (`tests/staruml_falso.py`).
- Si están `javac`, `tsc` y `dotnet`, se compila de verdad el código generado; el de Python siempre se importa.
- **Con StarUML instalado**, `tests/test_staruml_real.py` exporta con el CLI verdadero: una secuencia generada con
  auto-mensajes y todos los diagramas del modelo real, revisando cada SVG con `svg_revisar`. También lee los
  diagramas de estados y de actividades que hayas dibujado en StarUML y guardado en `pruebas/`. Si existe la carpeta
  `pruebas/`, deja los SVG, PNG e informes en `pruebas/verificacion_staruml/` para revisarlos a ojo.
- **Modelo real propio:** copia tu `.mdj` a `pruebas/` (carpeta ignorada por git) o define `STARUML_MCP_MODELO_REAL`; `tests/test_modelo_real.py` lo usa automáticamente (siempre sobre copias).
- La integración continua (`.github/workflows/pruebas.yml`) corre la suite en macOS, Linux y Windows con Python 3.9 y 3.12.

---

## Regenerar las Tablas desde StarUML

Las tablas versionadas salen del StarUML instalado. Para actualizarlas con otra versión de StarUML (cerrada):

```bash
python herramientas/extraer_metamodelo.py     # staruml_metamodelo.json, desde resources/app.asar
python herramientas/generar_referencia.py     # StarUML dibuja cada símbolo de cada paleta (pruebas/referencia/)
python herramientas/extraer_plantillas.py     # plantillas_vistas.json
python herramientas/generar_catalogo.py       # uml_catalogo.md
```

`generar_referencia.py` instala en la carpeta de extensiones de usuario de StarUML una extensión pequeña (`herramientas/staruml_extension/mcp-referencia`) y la corre con `StarUML exec`; con `--quitar-extension` la borra al terminar. La especificación UML 2.5.1 de la OMG no se incluye en el repositorio; `uml_catalogo.md` cita sus secciones.
