# Plan de Mejora — MCP StarUML

> Resultado de una campaña de pruebas en busca de bugs sobre `main` (commit `6c118c2`, 2026-09-29) y de la revisión del plan v2.0 propuesto anteriormente. **Cada hallazgo de este documento se reprodujo**; ninguno es especulativo.

> **Estado:** ✅ Fases 0, 1 y 2 completadas, y la Fase 3 en parte. Los 56 bugs están corregidos y cubiertos por la suite `tests/` (119 pruebas en verde en Python 3.9 y 3.11), que además se ejecuta sobre el caso de uso real del equipo cuando está en `pruebas/`. Ver §9.

---

## 1. Resumen ejecutivo

- **56 casos dirigidos → 56 bugs confirmados** con reproducción y evidencia. Dos pruebas estaban mal planteadas y se corrigieron antes de contarlas.
- **Lo que funciona bien**
  - El flujo completo por stdio pasó **46/46 verificaciones**: crear clases, vistas, asociaciones, notas y secuencias, y luego renombrar, mover, editar, borrar y comparar con `diff`.
  - Un fuzzer de **827 operaciones de edición aleatorias** no encontró roturas de integridad fuera de las ya identificadas. El fuzzer tiene control positivo: sí detecta B01/B02 cuando se activan sus disparadores.
  - El rendimiento es correcto: con un modelo de 27 000 ids (7.9 MB), toda herramienta responde en ≤ 2.1 s.
- **Lo grave**, en tres bloques:
  1. **Integridad y pérdida de datos.** Se puede guardar un `.mdj` con `_id` duplicados, con `NaN` (StarUML ya no lo abre) o con referencias colgantes. También se pueden perder notas, atributos y código del usuario sin aviso. La validación ocurre *después* de escribir.
  2. **Portabilidad.** La protección "StarUML abierto", el CLI, Chrome y el redimensionado (`sips`) solo funcionan en macOS. En Windows, además, la E/S por stdio corrompe los acentos y **los guarda así** en el `.mdj`. El README documenta la instalación en Windows.
  3. **Sincronización con código.** Los parsers por regex fallan en patrones comunes: genéricos en `implements`, herencia en C#, propiedades `{ get; set; }`, `async` y campos opcionales en TS. Los generadores producen Java que no compila y Python que no se puede importar.
- **Sobre el plan v2.0.** La dirección que propone (pruebas → robustez → expansión) es buena, pero parte de "0 bugs conocidos", y **ninguno de los 5 arreglos que da por hechos está en el repositorio**.
  - Se conservan 1.1–1.4, 2.3 y 2.5, con ajustes.
  - Se posponen las expansiones de lenguajes.
  - Se descartan 3.4 (LSP) y 3.5 (el header Content-Length rompe MCP). Ver §4.

| Severidad | Casos | Criterio |
|---|---|---|
| 🔴 Crítica | 11 | Corrompe el `.mdj`, pierde datos del usuario o desactiva una protección |
| 🟠 Alta | 16 | La herramienta revienta o queda inservible en un escenario común |
| 🟡 Media | 21 | Resultado incorrecto o engañoso |
| ⚪ Baja | 8 | Protocolo, mensajes de error, bordes poco frecuentes |

---

## 2. Cómo se probó

- **Fixture sintética** con la estructura que guarda StarUML: `Project` → `UMLProfile` (`boundary`/`control`/`entity`) + `UMLModel` → paquete con actor, diagrama de clases vacío y colaboración → interacción → diagrama de secuencia con marco. No contiene datos de ningún proyecto real.
- **E2E por protocolo MCP**: JSON-RPC por stdio, llamando las 30 herramientas como lo haría un cliente.
- **56 casos dirigidos.** Cada caso afirma el comportamiento *correcto*; si falla, el bug queda confirmado.
- **Fuzzer de integridad**: 6 semillas × 140 operaciones. Después de cada escritura exige 0 `_id` duplicados, 0 referencias colgantes, 0 `_parent` incoherentes y JSON estricto.
- **Compilación real** del código generado: `javac`, `tsc --strict` y `python`.
- **Plataforma**:
  - proceso de StarUML simulado en Linux;
  - `staruml` en el `PATH`;
  - Chromium real;
  - stdio con `PYTHONIOENCODING=cp1252`, que es lo que hace Python en Windows cuando stdin/stdout son tuberías, como en MCP.
- **Rendimiento**: modelo de 3 000 clases, 400 vistas y 1 000 asociaciones, más una secuencia de 150 mensajes.
- **Análisis estático**: `ruff` (reglas F y B) y `mypy`.
- **Límites.** El entorno de prueba (Linux) no tiene el CLI de StarUML, así que no se probó la exportación real ni `svg_revisar` con un SVG auténtico; en su lugar se usaron dobles de prueba.

---

## 3. Hallazgos

### 🔴 Críticos (11)

| ID | Herramienta | Qué pasa (evidencia) | Dónde |
|---|---|---|---|
| B01 | `mdj_atributos` | Si se repite un nombre que ya existe (`["usuario","usuario","hash"]`), se reutiliza el mismo objeto dos veces y se guardan **2 `_id` duplicados** (el atributo y su vista). | `staruml_mdj.py:628` |
| B02 | `mdj_secuencia_generar` | Si se piden dos lifelines del mismo tipo y ese tipo ya tenía lifeline, la **misma lifeline entra dos veces** en `participants` (`_id` duplicado) y las dos claves apuntan al mismo objeto. | `staruml_mdj.py:1055-1076` |
| B11 | todas las de edición | Un `NaN` en un argumento numérico pasa la validación y se escribe literal (`"left": NaN`). `JSON.parse`, el parser de StarUML/Electron, **ya no puede abrir el archivo**. | `server.py:588`, `staruml_mdj.py:209` |
| B12 | `mdj_borrar` | No revisa las referencias dentro de listas (p. ej. `constrainedElements`) y **guarda el archivo con referencias colgantes**. La validación posterior lo reporta, pero el archivo ya se escribió. | `staruml_mdj.py:989-1003` |
| B03 | `mdj_secuencia_generar` | **Borra en silencio** las notas y cualquier otra vista del diagrama de secuencia que no sea el marco. | `staruml_mdj.py:1174, 1236` |
| C23 | `staruml_codigo_a_diagrama` | Sobre una clase existente, **reemplaza** la lista de atributos por lo que detectó el parser (`[nombre, email, direccion]` → `[nombre]`) y no informa qué quitó. Sumado a C11–C16, esto borra atributos válidos. | `staruml_compare.py:993-997` |
| C07 | `staruml_diagrama_a_codigo` | **Sobrescribe archivos de código existentes sin aviso** y está anotada `readOnlyHint: true`, así que un cliente que auto-aprueba lecturas la ejecuta sin preguntar. | `staruml_compare.py:810-814`, `server.py:221` |
| C08 | `staruml_diagrama_a_codigo` | **Path traversal**: una clase llamada `../fuera` escribe `fuera.java` fuera de `carpeta_salida`. | `staruml_compare.py:798, 812` |
| P01 | protección de escritura | En Linux no detecta StarUML abierto (solo reconoce `StarUML.app/Contents/MacOS/StarUML`), y **la escritura procede** con la aplicación abierta. | `staruml_mdj.py:57-67` |
| P02 | protección de escritura | Si `ps` no existe (Windows), la detección devuelve `False`: la verificación **falla "abierta"**. | `staruml_mdj.py:59-62` |
| P05 | stdio en Windows | Con la codificación por defecto de Windows (cp1252), los acentos llegan como mojibake y **se guardan así**: `"Sesión del usuario"` → `"SesiÃ³n del usuario"`. | `server.py:522, 583` |

### 🟠 Altos (16)

| ID | Herramienta | Qué pasa (evidencia) | Dónde |
|---|---|---|---|
| B04 | `mdj_nota` | `KeyError: 'ownedViews'` en un diagrama vacío, que es como StarUML guarda un diagrama recién creado. | `staruml_mdj.py:665, 671` |
| B05 | `mdj_secuencia_generar` | `KeyError: 'ownedViews'` si el diagrama de secuencia no tiene vistas. | `staruml_mdj.py:1174` |
| B13 | `mdj_validar` | Una clase control (o una clase con métodos o atributos) sin `name` hace reventar `reglas_oose` con `KeyError: 'name'`. | `staruml_mdj.py:413, 415, 420` |
| B14 | `mdj_secuencia_generar` | Llama a `reglas_oose` **después** de guardar: si esa función falla, la respuesta es de error aunque el archivo ya se modificó. | `server.py:465-466` |
| B18 | anotaciones MCP | `svg_recortar`, `staruml_ver_visual` y `staruml_diagrama_a_codigo` escriben archivos y están marcadas `readOnlyHint: true`. | `server.py:163, 185, 221` |
| C02 | comparar y generar código | Un atributo o parámetro tipado con referencia a una clase (`"type": {"$ref": …}`, el formato normal de StarUML) produce `AttributeError: 'dict' object has no attribute 'strip'`. | `staruml_compare.py:18` |
| C03 | generador Java | No compila: aparece `List<item>` y `return null;` en métodos que devuelven `double` (`javac`: 4 errores). | `staruml_compare.py:845, 884` |
| C04 | generador Python | No se puede importar: `Optional[String]` da `NameError`, `-> void` también, y `Optional[List<item>]` da `SyntaxError`. | `staruml_compare.py:909-923` |
| C06 | `staruml_diagrama_a_codigo` | Sin `carpeta_salida` descarta el código generado y solo devuelve nombres de archivo. | `staruml_compare.py:816-822` |
| C11 | parser Java | `class X implements Comparable<X>`, `interface R extends JpaRepository<P, Long>` o `implements java.io.Serializable` → la **clase no se detecta**. | `staruml_compare.py:226-234` |
| C12 | parser C# | `class Cliente : Entidad` no se detecta, y las propiedades `{ get; set; }` no cuentan como atributos (`Entidad` sale con `[]`). | `staruml_compare.py:226-268` |
| P03 | exportar / `ver_visual` | `staruml_cli()` y `chrome_bin()` solo buscan rutas de macOS: ignoran el `PATH` (el README dice que lo usan) y las rutas de Windows/Linux. | `staruml_mdj.py:41-54` |
| P04 | `svg_recortar` / `ver_visual` | Aun con Chrome encontrado, revientan en otros sistemas por `sips` (exclusivo de macOS): `FileNotFoundError: 'sips'`. `pkill` tampoco existe en Windows. | `staruml_render.py:220, 225` |
| P06 | stdio en Windows | Un `.mdj` con un carácter fuera de cp1252 (p. ej. `→`) hace fallar con `-32603 'charmap' codec can't encode` **cualquier respuesta que incluya ese texto** (p. ej. `mdj_modelo`). | `server.py:522` |
| P07 | `staruml_ver_visual` | La caché global usa solo el **nombre** del diagrama: sirve la imagen de **otro proyecto** que tenga un diagrama con el mismo nombre. | `staruml_render.py:245-259` |
| P08 | `staruml_ver_visual` | Si la exportación no produce el SVG esperado, toma el SVG más reciente de la caché, aunque sea de otro diagrama. | `staruml_render.py:263-267` |

### 🟡 Medios (21)

| ID | Área | Qué pasa (evidencia) | Dónde |
|---|---|---|---|
| B08 | `mdj_renombrar` | Con un elemento sin nombre (lifeline), concatena el nombre nuevo a la etiqueta: `": Pantalla Autenticación"` → `": Pantalla Autenticaciónui"`. | `server.py:285` |
| B09 | `mdj_vista_agregar` | Crea una `UMLClassView` para una `UMLInterface`, cuando debería ser `UMLInterfaceView`. | `staruml_mdj.py:761` |
| B10 | `mdj_asociacion_crear` | Una asociación reflexiva queda como línea de longitud cero (`775:149;775:149`). | `staruml_mdj.py:554-558` |
| B16 | rutas relativas | `salida`, `carpeta_salida` y `carpeta` se resuelven contra el CWD del proceso del servidor, que depende del cliente, y no contra el `.mdj`. | `staruml_mdj.py:198`, `staruml_compare.py:811` |
| C01 | normalización | Pasa a minúsculas el tipo genérico: `List<Cliente>` → `List<cliente>`, `Item[]` → `List<item>`. También convierte `Set` en `List`, y un `Map` cuyo valor es una lista se degrada a `List` (`Map<String, List<Item>>` → `List<item>`). | `staruml_compare.py:18, 36-40` |
| C05 | generador TS | Omite métodos y asociaciones: `Pedido.ts` sale sin `calcularTotal` y con `items?: string`. | `staruml_compare.py:927-953` |
| C09 | generadores | Los nombres con espacios producen identificadores inválidos (`public class Orden de Compra`), y a un rol explícito se le agrega "s" (`sesioness`). | `staruml_compare.py:855-859` |
| C10 | comparar / generar | Un extremo marcado `notNavigable` se trata como navegable (`e2.get('navigable', True)` devuelve el texto, que es verdadero) y genera un campo que no debería existir. El caso sin especificar se resuelve de forma asimétrica: solo hacia el extremo 2. | `staruml_compare.py:144` |
| C13 | parser Java | Las variables locales salen como atributos (`suma`), y `return f()`, `new Item()` y `throw new X()` salen como métodos. | `staruml_compare.py:262-290` |
| C14 | parser Java/TS | Un `//` dentro de un String (una URL) se toma como comentario y se pierde el atributo siguiente (`puerto`). | `staruml_compare.py:217, 428` |
| C15 | parser Python | No controla la indentación: las funciones y constantes de módulo pasan a la clase, `try:`/`else:` salen como atributos y `-> mod.Tipo` hace que se pierda el método. `indent_clase` está declarado y no se usa. | `staruml_compare.py:352-421` |
| C16 | parser TS | No detecta campos `?:`, `readonly` o `static`, ni métodos `async` o de interfaz. `if (…) {` sale como método y las claves de objetos literales como atributos. | `staruml_compare.py:463, 470` |
| C17 | escaneo | `lenguaje="java"` parsea `.ts` y `.cs` con el parser de Java. Los `.js` se ignoran en carpetas (el README dice que se soportan). No excluye `.venv`, `obj` ni `dist`, y `os.walk` no poda carpetas. | `staruml_compare.py:189-200, 512-519` |
| C19 | métrica de secuencias | Los replies cuentan como verificados y los mensajes a actores como fallos: sin ningún método implementado da 16.7 %, y con todo implementado da 83.3 %. | `staruml_compare.py:736` |
| C20 | métrica de clases | Exige los actores como clases en el código, lo que baja el porcentaje (74.7 %) aunque el dominio esté completo. | `staruml_compare.py:75-77` |
| C21 | métrica de clases | No verifica la multiplicidad: una asociación `0..*` implementada como campo simple queda como "verificada". `es_coleccion` se calcula y no se usa. | `staruml_compare.py:624-633` |
| C22 | normalización | No normaliza acentos: `"Sesión"` en UML no empareja con `class Sesion`. En modelos en español esto afecta casi todo. | `staruml_compare.py:44-52` |
| C24 | importador | No importa métodos ni tipos, aunque la descripción dice "clases, atributos y métodos" (queda `monto: ''`, sin `calcularIva`). | `staruml_compare.py:993-997` |
| C25 | importador | Coloca las vistas en una rejilla fija que se encima con las existentes, y oculta los atributos importados (`suppressAttributes`). | `staruml_compare.py:1003-1015` |
| P09 | `ver_visual` / exportar | Con el **id** de un diagrama que comparte nombre con otro, falla: reenvía el nombre y `exportar` lo declara ambiguo. | `staruml_render.py:262` |
| P10 | `svg_revisar` | Revienta si un `<text>` no trae `text-anchor` o `font-weight`: el parser de atributos no tiene valores por defecto. | `staruml_render.py:97-104` |

### ⚪ Bajos (8)

| ID | Qué pasa | Dónde |
|---|---|---|
| B06 | `mdj_linea_ruta` da `KeyError` en un diagrama sin vistas en lugar de "No encontré esa línea". | `server.py:411` |
| B07 | Un `.mdj` con JSON inválido responde "Error inesperado: JSONDecodeError" en vez de un `MdjError` claro. | `staruml_mdj.py:79-80` |
| B15 | Las `opciones` de `mdj_secuencia_generar` no se validan: con `espaciado: [36, 29]` sale un `ValueError` genérico. | `staruml_mdj.py:1028-1030` |
| B17 | El README dice que `mdj_clase_crear` "crea clases o actores", pero solo crea `UMLClass`. Tampoco hay forma de crear actores, paquetes ni diagramas. | `server.py:251-262` |
| C18 | `record` aparece en el patrón de Java, pero nunca se detecta. | `staruml_compare.py:226-232` |
| J01 | Un batch JSON-RPC se responde mensaje por mensaje y no como un arreglo (el protocolo 2025-03-26 anunciado sí admite batch). | `server.py:592` |
| J02 | Las solicitudes inválidas (un número, `[]`, un `method` que no es texto) no reciben `-32600`: se ignoran o dan `-32603`. | `server.py:526-594` |
| J03 | Una notificación `tools/call` sin `id` con argumentos inválidos recibe una respuesta con `id: null`. | `server.py:551-553` |

### Otras observaciones medidas

- **Respaldos sin rotación**: esta sola campaña de pruebas generó **1 192 respaldos (178 MB)**. Cada escritura copia el archivo completo. `staruml_mdj.py:220-233`.
- **Tamaño de respuesta**: en el modelo grande, `mdj_modelo` devuelve **1 MB (~256 000 tokens)**, más de lo que cabe en el contexto de cualquier cliente. No tiene paginación, y `indent=1` la infla un 42 % frente a JSON compacto.
- **`mdj_modelo` es O(asociaciones × vistas)**: llama a `views_of` por cada asociación (2.1 s en el modelo grande). `staruml_mdj.py:287`.
- **Código muerto que delata funciones a medio hacer** (según `ruff`):
  - `es_coleccion`: la verificación de multiplicidad que documenta CLAUDE.md;
  - `indent_clase`: el parser de Python;
  - `tiene_cuerpo`;
  - `llamadas`: se extraen y ningún comparador las usa, así que el "flujo de llamadas en secuencias" que documenta CLAUDE.md no existe.

---

## 4. Revisión del plan v2.0

| Propuesta | Veredicto | Motivo / ajuste |
|---|---|---|
| "Estado actual: 0 bugs, 5 arreglos hechos" | ❌ Corregir | Los arreglos **no están en `main`** (el único commit remoto es `6c118c2`). Siguen presentes: records (C18), propiedades C# (C12), `Set` → `List` (`staruml_compare.py:36`) y la fuga de descriptor (`staruml_render.py:88`). Si existen en una copia local, hay que subirlos; si no, se rehacen en la Fase 2. |
| 1.1 Suite pytest | ✅ Tomar, ampliada | Le falta lo más importante: pruebas de **edición e integridad**, que es donde están los críticos. Hay que sumar los 56 casos como regresión, el fuzzer como prueba de propiedades y un invariante tras cada herramienta de escritura. La meta debe ser "cada bug corregido tiene su test", no solo un porcentaje de cobertura. Esto choca con la política de no subir `pruebas/` (ver §8). |
| 1.2 Logging estructurado | ✅ Tomar (prioridad baja) | Hay que validar el nivel: `logging.basicConfig(level='DEBUGG')` lanza `ValueError` y el servidor no arrancaría. |
| 1.3 Variables de entorno | ✅ Tomar, ampliada | Corrección: el respaldo por defecto es `<carpeta del servidor>/respaldos`, no `./respaldos`. Más útiles que los timeouts son `STARUML_MCP_STARUML_BIN` y `STARUML_MCP_CHROME_BIN` (resuelven P03) y `STARUML_MCP_BACKUP_KEEP` (rotación). |
| 1.4 Sandbox de rutas | ✅ Tomar, corregida | El código propuesto tiene dos bugs: `startswith` sin separador (`/proy` permitiría `/proy-otro`) y `split(':')` rompe las rutas de Windows (`C:\…`). Hay que usar `os.pathsep` y `os.path.commonpath` y aplicarlo a **todas** las rutas de entrada y salida. No sustituye sanitizar los nombres de archivo (C08). |
| 2.1 Generador C# | ⏸️ Posponer | Los tres generadores actuales producen código que no compila o no importa (C03–C05). Primero hay que arreglarlos. |
| 2.2 Parser Kotlin | ⏸️ Posponer | Otro parser por regex heredaría los fallos estructurales de C11–C18. Primero va la refactorización de la Fase 2. |
| 2.3 Auto-mensajes | ✅ Tomar (media) | Es una funcionalidad válida; hoy se rechazan de forma explícita. |
| 2.4 Comparar casos de uso con código | 🔁 Reformular | "Cada caso de uso tiene su control y cada actor su boundary" es consistencia **modelo↔modelo** y corresponde a `mdj_validar`, no a una comparación con código. Cruzar include/extend con llamadas en el código daría una precisión baja. |
| 2.5 OOSE extendida | ✅ Tomar, acotada | "Nombre vacío en cualquier elemento" daría mucho ruido, porque los extremos de asociación, las lifelines y las vistas no llevan nombre: hay que limitarlo a clases, actores y diagramas. Antes hay que arreglar B13. |
| 3.1 / 3.2 Estados y actividades | ⏸️ Largo plazo | Sin cambios. |
| 3.3 Parser Go | ⏸️ Largo plazo | Mismo motivo que 2.2. |
| 3.4 LSP para `.mdj` | ❌ Descartar | El `.mdj` se edita en la interfaz gráfica de StarUML, no en un editor de texto, y la validación ya llega a los asistentes vía MCP. |
| 3.5 Header Content-Length | ❌ Descartar | El transporte stdio de MCP usa **JSON delimitado por saltos de línea**. Content-Length es propio del LSP y agregarlo rompería Claude Code, Claude Desktop y Cursor. |
| — | ➕ Agregar | Integridad de datos, portabilidad real, anotaciones MCP, seguridad de rutas, métricas de comparación, tamaño de respuestas, rotación de respaldos y documentación desalineada (todo lo de §3). |

---

## 5. Plan unificado

### Fase 0: detener la pérdida de datos (bloqueante, 1–2 sesiones) — ✅ completada

| # | Tarea | Cierra | Criterio de aceptación |
|---|---|---|---|
| 0.1 ✅ | **Guardado transaccional.** `Doc.save()` valida en memoria antes de escribir y se niega si el cambio introduce duplicados, colgantes o `_parent` incoherentes que no había al cargar. Usar `json.dump(..., allow_nan=False)` y rechazar `NaN`/`Infinity` en la entrada (`json.loads(line, parse_constant=…)`, capturando `ValueError`). | B11; convierte B01, B02 y B12 en errores limpios | El fuzzer con los disparadores activos no produce ningún archivo inválido. |
| 0.2 ✅ | **Corregir las causas raíz.** `set_atributos` rechaza nombres repetidos. `generar_secuencia` asigna una lifeline por *clave* y nunca agrega dos veces el mismo objeto. `borrar` recorre también las referencias dentro de listas. | B01, B02, B12 | Test de regresión por caso. |
| 0.3 ✅ | **Nada se pierde en silencio.** `mdj_secuencia_generar` conserva las notas o las reporta en `vistas_descartadas`. El importador trabaja en modo aditivo por defecto, con un `modo: "sincronizar"` explícito que informa `atributos_quitados`. El generador no sobrescribe sin `sobrescribir: true` y sanea los nombres de archivo, verificando con `os.path.commonpath` que el destino queda dentro de `carpeta_salida`. | B03, C23, C07, C08 | Tests de las cuatro situaciones. |
| 0.4 ✅ | **Anotaciones MCP correctas.** Las herramientas que escriben llevan `readOnlyHint: false`, y el generador además `destructiveHint` cuando puede sobrescribir. | B18 | Test que recorre `TOOLS`: si una herramienta tiene un parámetro de salida, no puede ser read-only. |
| 0.5 ✅ | **stdio en UTF-8 explícito**: al inicio de `main()`, `sys.stdin.reconfigure(encoding='utf-8')` y `sys.stdout.reconfigure(encoding='utf-8', newline='\n')`. | P05, P06 | El E2E pasa con `PYTHONIOENCODING=cp1252`. |
| 0.6 ✅ | **La protección "StarUML abierto" falla cerrada.** Detección para macOS, Linux (`/opt/StarUML/staruml`, AppImage) y Windows (`tasklist`). Si no se puede determinar, no se escribe salvo con `forzar`. | P01, P02 | Tests con un proceso simulado y con `ps` ausente. |

**Cómo quedó la Fase 0.**
- **Comportamientos nuevos visibles para quien usa el MCP:**
  - una escritura que empeoraría el `.mdj` se rechaza con un error que dice por qué;
  - `mdj_atributos` y `mdj_clase_crear` rechazan nombres repetidos;
  - `mdj_secuencia_generar` devuelve `vistas_conservadas` y `vistas_descartadas`;
  - `mdj_borrar` devuelve `referencias_quitadas`;
  - `staruml_codigo_a_diagrama` acepta `modo` y devuelve `atributos_agregados` y `atributos_quitados`;
  - `staruml_diagrama_a_codigo` acepta `sobrescribir` y devuelve `escritos`, `omitidos_por_existir` y `omitidos_por_nombre_invalido`;
  - si no se puede comprobar si StarUML está abierto, hace falta `forzar: true`.
- **Encontrado al corregir:** en Windows el `.mdj` se escribía con saltos `\r\n`; ahora siempre usa `\n`, como StarUML.
- **Verificación:**
  - E2E 46/46;
  - 30 pruebas nuevas de los comportamientos y sus bordes;
  - fuzzer normal (827 operaciones) sin fallos;
  - fuzzer con los disparadores de corrupción activos (475 operaciones): 31 rechazos limpios y ningún archivo inválido;
  - en el modelo de 27 000 ids, la validación previa agrega ~0.1–0.3 s por escritura.

### Fase 1: red de seguridad y robustez (2–3 sesiones)
Incorpora los puntos 1.1–1.4 del plan v2.0, ajustados.

| # | Tarea | Cierra |
|---|---|---|
| 1.1 ✅ | **Suite pytest versionada**: fixture generada por código, los 56 casos de este informe como regresión, un invariante de integridad tras cada herramienta de escritura, el fuzzer con semilla fija (unas 200 operaciones) y pruebas del protocolo por stdio. Criterio: `pytest -q` corre en menos de 30 s sin StarUML ni Chrome. | — |
| 1.2 ✅ | **CI en GitHub Actions**: matriz Ubuntu/macOS/Windows × Python 3.9/3.12, con `ruff check --select F,B` como gate. Con la matriz de Windows se habrían detectado P05 y P06 desde el principio. | — |
| 1.3 ✅ | **Datos mínimos pero válidos no deben tumbar herramientas**: `.get('ownedViews', [])` en todos los accesos; resolver los tipos `{"$ref"}` al nombre de la clase; `o.get('name')` en `reglas_oose`; ejecutar `reglas_oose` antes de guardar; convertir el JSON inválido en `MdjError`; validar las `opciones`. | B04–B07, B13–B15, C02 |
| 1.4 ✅ | **Render portable**: `shutil.which`, rutas de Windows/Linux y las variables `STARUML_MCP_STARUML_BIN`/`STARUML_MCP_CHROME_BIN`. Redimensionar sin `sips` (tamaño de ventana y factor de escala de Chrome). Usar `pkill` solo donde exista. | P03, P04 |
| 1.5 ✅ | **Caché de renders correcta**: la clave debe ser hash(ruta absoluta del `.mdj` + id del diagrama + mtime), sin fallback al "SVG más reciente", y `ver_visual` debe pasar el **id** a `exportar`. | P07–P09 |
| 1.6 ◐ | **Configuración y logging** (v2.0 §1.2–1.3): timeouts, binarios, rotación de respaldos con `STARUML_MCP_BACKUP_KEEP` y nivel de log validado. | respaldos |
| 1.7 ✅ | **Sandbox de rutas** (v2.0 §1.4, corregido). Las rutas relativas se resuelven contra la carpeta del `.mdj`. | B16 |
| 1.8 ✅ | **Protocolo y tamaño de respuesta**: batch según la versión negociada, `-32600` para solicitudes inválidas y ninguna respuesta a notificaciones. JSON compacto, y paginación (`limite`, `desde`) en `mdj_modelo`, `mdj_buscar` y `mdj_geometria`. | J01–J03 |

### Fase 2: sincronización con código confiable (3–4 sesiones)

| # | Tarea | Cierra |
|---|---|---|
| 2.1 ✅ | **Parsers nuevos**: Python con `ast` (biblioteca estándar, sin dependencias nuevas). Java, C# y TS con un tokenizador que respete strings y comentarios, extrayendo miembros solo a profundidad 1 de llaves. Cabeceras con genéricos, bases con `:` en C#, `record`, propiedades C#, `readonly`/`static`/`async`/`?` en TS y métodos de interfaz. | C11–C16, C18 |
| 2.2 ✅ | **Escaneo**: filtrar extensiones según `lenguaje`, incluir `.js`/`.jsx`/`.mjs` y podar `dirs[:]` (`.venv`, `venv`, `dist`, `obj`, `bin`, `out`, `.tox`). | C17 |
| 2.3 ✅ | **Normalización**: conservar las mayúsculas del tipo genérico y distinguir `Set`/`Map` de `List`; normalizar acentos con `unicodedata` al emparejar nombres. | C01, C22 |
| 2.4 ✅ | **Métricas honestas**: excluir replies y mensajes a actores del denominador; no exigir actores como clases; verificar colección vs. escalar según la multiplicidad; respetar la navegabilidad (`== 'navigable'`, en ambos extremos); usar `llamadas` para verificar el flujo emisor→receptor. | C10, C19–C21 |
| 2.5 ✅ | **Generadores que compilan**: identificadores válidos (sin espacios ni acentos), roles sin la "s" duplicada, `extends`/`implements`, paquete configurable, TS con métodos y asociaciones, y devolver el código cuando no hay `carpeta_salida`. Criterio: `javac`, `tsc --strict` e `import` de Python pasan en CI sobre la fixture. | C03–C06, C09 |
| 2.6 ✅ | **Importador útil**: traer tipos y métodos, colocar las vistas en un hueco libre y dejar los atributos visibles. | C24, C25 |

### Fase 3: capacidades nuevas (bajo demanda)
Re-priorizadas desde el plan v2.0 y los hallazgos.

1. **Herramientas para crear actores, paquetes y diagramas** (B17). Sin ellas no se puede construir un proyecto desde cero.
2. **Pulido de vistas**: `UMLInterfaceView` (B09), asociación reflexiva con lazo (B10), renombrar sin concatenar (B08) y un `svg_revisar` tolerante a atributos faltantes (P10).
3. **Auto-mensajes en secuencias** (v2.0 §2.3).
4. **OOSE extendida y acotada** (v2.0 §2.5), más la **consistencia casos de uso ↔ robustez** (v2.0 §2.4 reformulado) dentro de `mdj_validar`.
5. **Generador C#** (v2.0 §2.1), después de 2.5.
6. **Diagramas de estados y de actividades** (v2.0 §3.1–3.2).
7. **Parsers Kotlin y Go** (v2.0 §2.2, §3.3), después de 2.1.

**Descartado:** Content-Length (rompe MCP) y LSP para `.mdj` (no tiene caso de uso).

---

## 6. Orden recomendado

| # | Tarea | Fase | Depende de |
|---|---|---|---|
| 1 | ✅ 0.1 Guardado transaccional + rechazo de NaN | F0 | — |
| 2 | ✅ 0.2 Causas raíz B01, B02, B12 | F0 | — |
| 3 | ✅ 0.3 Nada se pierde en silencio | F0 | — |
| 4 | ✅ 0.4 Anotaciones + 0.5 UTF-8 + 0.6 protección fail-closed | F0 | — |
| 5 | 1.1 pytest + 1.2 CI (tres sistemas operativos) | F1 | F0 (o en paralelo, empezando por las regresiones) |
| 6 | 1.3 Crashes con datos mínimos | F1 | 1.1 |
| 7 | 1.4 + 1.5 Render portable y caché | F1 | 1.2 |
| 8 | 1.6 – 1.8 Configuración, sandbox, protocolo, paginación | F1 | 1.1 |
| 9 | 2.1 – 2.3 Parsers, escaneo, normalización | F2 | 1.1 |
| 10 | 2.4 – 2.6 Métricas, generadores, importador | F2 | 2.1 |
| 11 | Fase 3 según prioridad | F3 | F2 |

**Meta al cerrar F0 + F1:** 0 críticos, 0 altos, CI en verde en tres sistemas operativos y cada bug de este informe cubierto por un test.

---

## 7. Documentación a alinear (acompaña a cada fase)

- **README**:
  - "o comando `staruml` disponible en PATH" no es cierto hoy (P03);
  - JavaScript no se escanea en carpetas (C17);
  - `mdj_clase_crear` no crea actores (B17);
  - ~~el importador no trae métodos (C24)~~ (corregido en el README con la Fase 0);
  - ~~"Validación posterior" debería pasar a "validación previa"~~ (hecho con la Fase 0);
  - el soporte de Windows/Linux necesita una nota hasta completar 1.4.
- **CLAUDE.md**: dice que se comparan "multiplicidades de asociaciones y flujo de llamadas en secuencias", y hoy no se hace ninguna de las dos (C21 y `llamadas` sin usar).
- **Descripciones de herramientas**: `staruml_codigo_a_diagrama` dice "(Java, Python, TS)" pero su enum incluye `csharp`, y `forzar` significa cosas distintas en `staruml_ver_visual` y en las herramientas de edición.

---

## 8. Decisiones pendientes

1. **¿Dónde están los 5 arreglos del plan v2.0?** No están en ninguna rama remota. Si viven en una copia local, conviene subirlos antes de empezar para no rehacer trabajo.
2. **¿Se versiona una carpeta `tests/`?** CLAUDE.md prohíbe subir `pruebas/`, que contiene un modelo de un proyecto particular. La propuesta es un `tests/` separado, **solo con fixtures sintéticas y genéricas**, y actualizar CLAUDE.md para reflejarlo.
3. **¿El render en Windows/Linux es un objetivo?** Si no lo es, hay que documentar "solo macOS" y, aun así, aplicar 0.5 y 0.6, porque afectan la integridad de los datos en cualquier plataforma.

---

## Anexo A: reproducciones mínimas (críticos)

```python
# B01: _id duplicado con mdj_atributos
import staruml_mdj as M
doc = M.Doc('modelo.mdj')
c = doc.find('UMLClass:Cuenta')                      # entity que ya tiene "usuario"
M.set_atributos(doc, c, ['usuario', 'usuario', 'hash'])
doc.save(backup=False)
M.validar(M.Doc('modelo.mdj'), oose=False)['n_duplicados']   # -> 2
```

```jsonc
// B02: mdj_secuencia_generar cuando "Cuenta" ya tiene lifeline en la interaccion -> n_duplicados = 1
{"lifelines": [{"clave": "ctrl", "tipo": "Control"}, {"clave": "c1", "tipo": "Cuenta"}, {"clave": "c2", "tipo": "Cuenta"}],
 "mensajes": [{"de": "ctrl", "a": "c1", "nombre": "leer()"}, {"de": "ctrl", "a": "c2", "nombre": "copiar()"}]}
```

```text
# B11: linea enviada por stdio (Python acepta NaN; el .mdj queda con "left": NaN y JSON.parse falla)
{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"mdj_vista_mover",
 "arguments":{"archivo":"modelo.mdj","diagrama":"cu_1","elemento":"<id de vista>","x":NaN}}}
```

```python
# B12: UMLConstraint con constrainedElements=[{"$ref": id_de_Sesion}], luego mdj_borrar "Sesión"
# -> el archivo se guarda con n_colgantes = 1 (".../constrainedElements[0]")
```

```python
# C08: clase llamada "../fuera" en el diagrama
# staruml_diagrama_a_codigo(carpeta_salida="out/src") -> crea "out/fuera.java"
```

```python
# C23: UML Cliente [nombre, email, direccion] + Cliente.java que solo declara "nombre"
# staruml_codigo_a_diagrama -> Cliente queda con [nombre]; la respuesta no menciona lo quitado
```

```bash
# P05: comportamiento de Windows (stdio en cp1252)
PYTHONIOENCODING=cp1252 python3 server.py
# mdj_documentacion(texto="Sesión del usuario") -> se guarda "SesiÃ³n del usuario"
```

---

## 9. Estado de avance

**Hecho**
- **Fase 0:** guardado transaccional, causas raíz de corrupción, nada se pierde en silencio, anotaciones MCP, stdio UTF-8 y protección "StarUML abierto" que bloquea si no puede verificar.
- **Fase 1:**
  - suite `tests/` (pytest) y CI en tres sistemas operativos;
  - diagramas sin vistas, JSON inválido, clases sin nombre y validación de opciones;
  - render portable (sin `sips` ni `perl`), caché por proyecto + id y exportación sin ambigüedad de homónimos;
  - rotación de respaldos (`STARUML_MCP_BACKUP_KEEP`), timeouts y rutas de binarios por variables de entorno;
  - carpetas permitidas (`STARUML_MCP_ALLOWED_DIRS`) y rutas relativas resueltas desde el `.mdj`;
  - JSON-RPC conforme (lotes, `-32600`, notificaciones sin respuesta) y `mdj_modelo` paginado.
- **Fase 2:**
  - parsers nuevos: `ast` para Python y un limpiador más primer nivel de llaves para Java, C# y TS/JS;
  - escaneo por lenguaje y sin carpetas de dependencias;
  - normalización con acentos y genéricos;
  - métricas honestas (actores, replies, multiplicidad, navegabilidad y flujo de llamadas);
  - generadores que compilan (`javac`, `tsc --strict`, `import`) y vuelven al 100 % al compararse;
  - importador con tipos y métodos, colocación sin encimar y modos `agregar`/`sincronizar`.
- **Fase 3 (parcial):**
  - `mdj_paquete_crear`, `mdj_diagrama_crear` y actores en `mdj_clase_crear`;
  - `UMLInterfaceView`, asociación reflexiva con lazo y renombrar sin concatenar;
  - `svg_revisar` tolerante;
  - avisos de notación, estereotipos como texto y cajas encimadas.

**Hallazgos adicionales que aparecieron al construir la suite (corregidos)**
- `ps` recortaba la línea de comando a 80 columnas sin terminal. Con StarUML en una ruta larga (p. ej. `~/Applications` y un usuario de nombre largo) la protección dejaba de reconocerlo. Se usa `ps -ww`.
- Chrome headless (`--headless=new`) deja 87 px sin pintar al pie de la ventana: el contenido cercano al borde inferior salía cortado, también en el código original. Ahora se renderiza con margen y se corta el PNG a la medida exacta.
- Las referencias adelantadas de Python (`List["Pedido"]`) quedaban con comillas en el tipo.
- Con el modelo real, los identificadores `BC_*` perdían el guion bajo al generar código, y las asociaciones hacia actores generaban campos de clases inexistentes.

**Pendiente (mejoras, no bugs)**
- Logging estructurado (plan v2.0 §1.2).
- Auto-mensajes en secuencias.
- Generador C#.
- Parsers Kotlin y Go.
- Consistencia casos de uso ↔ robustez en `mdj_validar`.
- Diagramas de estados y de actividades.
- La exportación real con StarUML y `svg_revisar` sobre SVG auténtico solo se probaron con dobles; conviene una corrida en una máquina con StarUML.
