# MCP StarUML

Servidor MCP para trabajar archivos `.mdj` de StarUML desde Claude Code sin abrir la
aplicación: leer el modelo, validarlo, editarlo con seguridad, generar diagramas de
secuencia, exportar y revisar cómo se ven.

Está hecho en Python puro (3.9 o más nuevo) y no necesita instalar nada: habla el
protocolo MCP (JSON-RPC por stdio) directamente.

## Instalar en Claude Code

```bash
claude mcp add staruml -- python3 "/Users/alejandromontijo/Desktop/Diseño de sofware /MCP StarUML/server.py"
```

Para que quede solo en este proyecto, se agrega `--scope project` (crea `.mcp.json`).
Con `claude mcp list` se revisa que esté conectado. Después de agregarlo hay que abrir
una sesión nueva de Claude Code.

Requisitos:

- `python3`.
- StarUML en `~/Applications` o `/Applications`, solo para exportar.
- Google Chrome, solo para `svg_recortar`.

## Herramientas

| Herramienta | Qué hace |
|---|---|
| `staruml_estado` | Dice si StarUML está abierto y dónde están el CLI, Chrome y los respaldos. |
| `staruml_reglas` | Devuelve las reglas de trabajo (`reglas.md`). |
| `mdj_resumen` | Diagramas del archivo y cuántas clases hay por estereotipo. |
| `mdj_modelo` | Clases, atributos, documentación, asociaciones con multiplicidades y roles. |
| `mdj_secuencia` | Mensajes numerados de un diagrama de secuencia. |
| `mdj_geometria` | Cajas y líneas de un diagrama con coordenadas e ids de vista. |
| `mdj_buscar` | Busca elementos por nombre o tipo y da sus ids. |
| `mdj_validar` | Ids duplicados, referencias colgantes, `_parent` y reglas OOSE. |
| `mdj_diff` | Diferencias a nivel modelo entre dos `.mdj`. |
| `staruml_exportar` | Exporta a SVG/PNG/PDF con el CLI de StarUML. |
| `svg_revisar` | Busca en el SVG líneas sobre notas, cajas o etiquetas, textos encimados y etiquetas sobre activaciones. |
| `svg_recortar` | Recorta una zona del SVG a PNG y la devuelve para verla. |
| `mdj_respaldar` | Copia de respaldo verificada byte por byte. |
| `mdj_clase_crear` | Crea una clase con estereotipo, atributos y documentación. |
| `mdj_renombrar` | Cambia el nombre de un elemento y el de sus vistas. |
| `mdj_documentacion` | Pone el campo Documentation. |
| `mdj_atributos` | Deja la lista de atributos exacta y rehace su compartimento. |
| `mdj_asociacion_crear` | Crea una asociación y, si se pide, la dibuja con su ruta. |
| `mdj_asociacion_editar` | Cambia multiplicidad, rol, navegabilidad o extremo. |
| `mdj_borrar` | Borra un elemento con sus relaciones y todas sus vistas. |
| `mdj_vista_agregar` | Dibuja una clase o actor existente en un diagrama. |
| `mdj_vista_mover` | Mueve o cambia el tamaño de una vista. |
| `mdj_linea_ruta` | Pone la ruta de una línea y calcula sus extremos como StarUML. |
| `mdj_linea_etiqueta` | Mueve una etiqueta de una línea sin tocar sus puntos. |
| `mdj_nota` | Crea o edita una nota; calcula su alto con el texto. |
| `mdj_secuencia_generar` | Rehace un diagrama de secuencia completo a partir de lifelines y mensajes. |
| `staruml_ver_visual` | Visualiza un diagrama como imagen PNG de alta resolución devuelta directamente en MCP. |
| `staruml_comparar_codigo` | Compara un diagrama UML contra código (Java, Python, TS, C#), calculando porcentaje de sincronización y discrepancias. |
| `staruml_diagrama_a_codigo` | Genera esqueletos de código fuente limpios (Java, Python, TS) a partir de las clases de un diagrama. |
| `staruml_codigo_a_diagrama` | Importa clases, atributos y métodos desde código fuente hacia el modelo y diagrama .mdj. |


## Seguridad al escribir

Todas las herramientas de edición:

1. Se niegan a escribir si la aplicación de StarUML está abierta. Si tiene cargada una
   versión vieja y alguien guarda, pisa los cambios. Solo con `forzar: true` escriben
   igual.
2. Hacen un respaldo antes de escribir, en `respaldos/` dentro de esta carpeta (o donde
   diga la variable `STARUML_MCP_BACKUP_DIR`), y comprueban que quedó idéntico.
3. Guardan con el mismo formato que StarUML (`ensure_ascii=False`, tabuladores).
4. Validan el archivo al terminar y regresan el resultado.

Con `salida` escriben en otro archivo y el original no se toca, para probar un cambio
antes de aplicarlo.

## Ejemplo: generar una secuencia

```json
{
  "archivo": "UML actualizado/Modelo.mdj",
  "diagrama": "cu_1_FB",
  "lifelines": [
    {"clave": "asesor", "tipo": "Asesor de Renta"},
    {"clave": "bc", "tipo": "BC_RegistroSolicitudRenta"},
    {"clave": "ctrl", "tipo": "ControlContratacionRenta"},
    {"clave": "cliente", "tipo": "Cliente"}
  ],
  "mensajes": [
    {"de": "asesor", "a": "bc", "nombre": "ingresarRFC(rfc)", "flujo": "F1"},
    {"de": "bc", "a": "ctrl", "nombre": "buscarCliente(rfc)", "flujo": "F1"},
    {"de": "ctrl", "a": "cliente", "nombre": "buscarCliente(rfc)", "flujo": "F1"},
    {"de": "cliente", "a": "ctrl", "nombre": "clienteEncontrado", "reply": true, "flujo": "F1"},
    {"de": "ctrl", "a": "bc", "nombre": "mostrarDatosCliente(cliente)", "flujo": "F1"}
  ]
}
```

## Ejemplo: ver diagrama de manera visual

```json
{
  "archivo": "pruebas/proyecto_reconstruido.mdj",
  "diagrama": "cu_1_FB",
  "salida": "renders/cu_1_FB.png",
  "max_lado": 1600
}
```
Devuelve directamente en el chat el bloque de imagen PNG de alta fidelidad y la metadata de resolución y elementos para que el asistente pueda ver el diseño con visión multimodal.

## Ejemplo: comparar diagrama con código fuente

```json
{
  "archivo": "pruebas/proyecto_reconstruido.mdj",
  "diagrama": "cu_1",
  "ruta_codigo": "src/main/java/com/empresa/modelo",
  "lenguaje": "java"
}
```
Analiza las clases, atributos, tipos, métodos, multiplicidades y llamadas, reportando:
- Porcentaje de sincronización / alineación.
- Clases y métodos que faltan por implementar en el código.
- Inconsistencias de tipos de datos o relaciones no mapeadas.

## Pruebas


```bash
python3 "MCP StarUML/pruebas/probar_servidor.py" "ruta/al/modelo.mdj" cu_1 cu_1_FB
```

Arranca el servidor, habla MCP por stdio y usa todas las herramientas. Las de escritura
trabajan sobre copias temporales, así que el archivo que se pasa solo se lee. Al final
rehace la secuencia desde su propia especificación y revisa que quede sin problemas.

## Archivos

- `server.py`: el servidor MCP (protocolo y definición de herramientas).
- `staruml_mdj.py`: leer, validar y editar el `.mdj`.
- `staruml_render.py`: exportar, revisar el SVG, recortar a PNG y visualización de alta resolución.
- `staruml_compare.py`: comparador de diagramas contra código (Java, Python, TypeScript, C#) y generador de esqueletos.
- `reglas.md`: reglas de trabajo (convenciones OOSE, secuencias, líneas y código).

