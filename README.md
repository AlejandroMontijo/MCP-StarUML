# MCP StarUML

Servidor de Protocolo de Contexto de Modelo (**MCP** - Model Context Protocol) para interactuar, inspeccionar, editar, renderizar y sincronizar archivos `.mdj` de **StarUML** directamente desde asistentes de IA (Claude Code, Claude Desktop, Cursor, Antigravity, etc.) sin necesidad de abrir la aplicación gráfica.

Desarrollado en Python puro (3.9+), sin dependencias externas pesadas, comunicándose mediante el protocolo estándar MCP (JSON-RPC 2.0 por `stdio`).

---

## Características Principales

- **Inspección Visual en Tiempo Real:** Renderiza y entrega diagramas directamente en el chat en formato PNG de alta fidelidad para visión multimodal de la IA.
- **Sincronización Bidireccional con Código:** Compara diagramas (Clases y Secuencias) contra bases de código en **Java, Python, TypeScript/JavaScript y C#**, calculando el porcentaje de alineación y reportando discrepancias.
- **Generación de Código:** Genera esqueletos limpios y tipados a partir del diseño de clases y asociaciones.
- **Ingeniería Inversa:** Importa clases, atributos y métodos desde código fuente hacia paquetes y diagramas del `.mdj`.
- **Edición Segura y Confiable:** Respaldos automáticos antes de escribir, prevención de sobreescritura si la aplicación está abierta y validación de integridad referencial.
- **Generador Inteligente de Secuencias:** Construye diagramas de secuencia completos con lifelines, ordenación automática, activación con pila de llamadas y cálculo de separación para evitar solapamiento de textos.

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
- **StarUML** instalado (macOS en `~/Applications` o `/Applications`, o comando `staruml` disponible en `PATH`), necesario para la exportación por CLI.
- **Google Chrome** (opcional, para rasterizado y recorte PNG de alta fidelidad).

---

## Catálogo de Herramientas (30)

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
| `staruml_comparar_codigo` | Compara un diagrama (Clases o Secuencia) contra código fuente (Java, Python, TS, C#). Devuelve métrica de sincronización (%) y elementos faltantes. |
| `staruml_diagrama_a_codigo` | Genera esqueletos de código limpios y tipados a partir de las clases y relaciones de un diagrama. No reemplaza archivos existentes salvo con `sobrescribir: true`. |
| `staruml_codigo_a_diagrama` | Importa clases y atributos desde archivos de código fuente hacia el modelo y diagrama `.mdj`. Por defecto solo agrega; con `modo: "sincronizar"` deja exactamente los atributos del código y reporta los quitados. |

### Lectura, Consulta y Diagnóstico
| Herramienta | Descripción |
|---|---|
| `staruml_estado` | Informa si StarUML está en ejecución y la ubicación del CLI, Chrome y respaldos. |
| `staruml_reglas` | Devuelve las reglas y convenciones de modelado y arquitectura (`reglas.md`). |
| `mdj_resumen` | Lista diagramas del archivo, vistas, diagrama por defecto y conteo por estereotipo. |
| `mdj_modelo` | Extrae clases, atributos, métodos, documentación y asociaciones con roles y multiplicidades. |
| `mdj_secuencia` | Extrae la secuencia ordenada de mensajes, lifelines, tipos y respuestas (replies). |
| `mdj_geometria` | Coordenadas, dimensiones e identificadores de vistas de cajas y líneas de un diagrama. |
| `mdj_buscar` | Búsqueda flexible de elementos por nombre, texto o tipo UML (`UMLClass`, `UMLAssociation`, etc.). |
| `mdj_validar` | Valida integridad estructural (IDs duplicados, referencias rotas) y reglas OOSE/robustez. |
| `mdj_diff` | Calcula diferencias semánticas y estructurales entre dos archivos `.mdj`. |

### Edición Segura del Modelo
| Herramienta | Descripción |
|---|---|
| `mdj_respaldar` | Crea una copia de respaldo verificada byte por byte. |
| `mdj_clase_crear` | Crea clases o actores con estereotipo (`boundary`, `control`, `entity`), atributos y documentación. |
| `mdj_renombrar` | Renombra un elemento y sincroniza automáticamente las etiquetas de todas sus vistas. |
| `mdj_documentacion` | Actualiza la documentación o especificación de responsabilidades de un elemento. |
| `mdj_atributos` | Sincroniza la lista exacta de atributos y actualiza su compartimento visual. |
| `mdj_asociacion_crear` | Crea asociaciones con multiplicidades, roles, navegabilidad y trazado de ruta visual opcional. |
| `mdj_asociacion_editar` | Modifica multiplicidades, roles, extremos o navegabilidad de una asociación existente. |
| `mdj_borrar` | Borrado en cascada: elimina el elemento, sus elementos contenidos, relaciones y vistas asociadas. |
| `mdj_vista_agregar` | Dibuja la vista de una clase o actor existente en un diagrama en notación estándar o icónica. |
| `mdj_vista_mover` | Ajusta coordenadas y dimensiones de una vista de caja en un diagrama. |
| `mdj_linea_ruta` | Define los puntos de quiebre de una línea calculando los extremos de conexión con las cajas. |
| `mdj_linea_etiqueta` | Ajusta la posición de etiquetas de multiplicidad, rol o nombre (alpha y distance). |
| `mdj_nota` | Crea o edita notas explicativas con cálculo automático de dimensiones según el texto. |
| `mdj_secuencia_generar` | Genera o regenera por completo un diagrama de secuencia a partir de especificación de lifelines y mensajes. |

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

### 3. Generar Esqueletos de Código desde el Modelo
```json
{
  "archivo": "ruta/al/modelo.mdj",
  "diagrama": "DiagramaClases",
  "lenguaje": "typescript",
  "carpeta_salida": "src/models"
}
```

### 4. Generar un Diagrama de Secuencia
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

---

## Estructura del Repositorio

- `server.py`: Servidor central MCP (protocolo JSON-RPC 2.0 y registro de herramientas).
- `staruml_mdj.py`: Motor de lectura, manipulación del árbol JSON, validación y edición segura del formato `.mdj`.
- `staruml_render.py`: Módulo de exportación CLI, rasterizado de alta calidad e inspección de SVG.
- `staruml_compare.py`: Motor de sincronización, escaneo de código fuente (Java, Python, TypeScript, C#) e ingeniería inversa.
- `reglas.md`: Manual de convenciones de arquitectura, buenas prácticas OOSE y lineamientos de modelado.
