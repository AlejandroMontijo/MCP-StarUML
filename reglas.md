# Reglas y Convenciones de Modelado StarUML (.mdj)

Convenciones y estándares de buenas prácticas de análisis, diseño y arquitectura para proyectos StarUML (`.mdj`). El servidor MCP las aplica automáticamente para garantizar la integridad referencial, consistencia visual y cumplimiento de patrones de ingeniería de software (UML y OOSE).

## Archivo

- El `.mdj` es JSON. Se lee y se guarda con Python, siempre así:
  `json.dump(d, f, ensure_ascii=False, indent='\t')`. Con eso el archivo queda igual
  que como lo guarda StarUML.
- Antes de escribir se hace un respaldo (carpeta `respaldos/` del MCP, o la que diga
  `STARUML_MCP_BACKUP_DIR`) y se compara byte por byte con el original.
- Antes de escribir se valida el modelo en memoria: si el cambio dejaría ids duplicados,
  referencias colgantes, `_parent` incoherentes o números NaN/infinito, no se escribe nada.
- **Si la aplicación de StarUML está abierta (o no se puede comprobar), no se escribe.** Si tiene cargada una
  versión vieja y alguien guarda desde ahí, pisa los cambios. Se pide cerrarla (sin
  guardar) o se usa `forzar` solo si se sabe que no tiene ese archivo abierto.
- Para probar un cambio sin tocar el original, las herramientas de edición aceptan
  `salida` (otro archivo).
- Borrar una vista no borra el elemento: quedan relaciones fantasma. `mdj_borrar`
  quita el elemento, lo que contiene, sus relaciones y todas sus vistas.
- IDs con el formato de StarUML: 4 bytes cero + 6 bytes de timestamp en ms + 4
  aleatorios, en base64 (20 caracteres).
- Estereotipos de robustez como referencia (`$ref`) al estereotipo del perfil
  (`boundary`, `control`, `entity`). Si van como texto, StarUML dibuja una caja tachada.
- El diagrama que abre al cargar es el que tiene `defaultDiagram: true`.

## Diagramas de clases

- StarUML recalcula el primer y el último punto de cada línea: quedan donde la recta
  del centro de la caja hacia el punto vecino cruza el borde. Para que un tramo salga
  recto, el punto vecino tiene que alinearse con el centro de la caja.
  `mdj_linea_ruta` calcula esos extremos igual que StarUML.
- Si una línea tiene puntos puestos a mano por el equipo, no se recalculan: se mueven
  solo sus etiquetas (`mdj_linea_etiqueta`, con `alpha` y `distance`).
- Nada de espaciados idénticos ni alineaciones perfectas repetidas: se ve hecho por
  máquina. Variar un poco posiciones y separaciones.
- Notas: cada renglón de Arial 11 ocupa 11 px. `mdj_nota` calcula el alto solo.
- Revisar siempre con `svg_revisar` después de exportar: líneas que cruzan notas o
  cajas, líneas sobre etiquetas, etiquetas encimadas y texto que se sale de las notas.

## Robustez (OOSE)

- Un solo control por caso de uso.
- actor -> boundary; boundary <-> control; control -> entity; entity -> entity solo si
  existe la asociación; boundary -> actor externo (p. ej. un servicio de correo).
- Control -> actor no es válido: se pone una boundary en medio.
- Una boundary no habla con otra boundary ni con una entity.
- Boundary y control sin atributos ni métodos. En análisis ninguna clase lleva métodos.
- Una sola notación (la de íconos) en todo el proyecto. `mdj_validar` avisa de las vistas de
  robustez que no la usan, de los estereotipos guardados como texto y de las cajas encimadas.
- Cada caso de uso se analiza en un paquete con su mismo nombre (sin importar acentos ni mayúsculas).
  Si el modelo sigue esa convención, `mdj_validar` avisa cuando el paquete no tiene control o
  boundaries, cuando un actor del caso de uso no tiene boundary en el paquete, cuando una boundary
  atiende a un actor que no participa en el caso de uso (la herencia entre actores cuenta) y qué
  casos de uso aún no tienen paquete.

## Diagramas de secuencia

- Cada mensaje: `UMLMessage` + `UMLSeqMessageView` con 3 `EdgeLabelView` (nombre
  visible; estereotipo y propiedades ocultos) y 1 `UMLActivationView`. head = linePart
  del destino, tail = linePart del origen, points `"xo:y;xt:y"`.
- Sin `messageSort` es llamada síncrona; `"reply"` es respuesta. Sin replies de una
  boundary al actor. Toda consulta a una entity lleva su reply.
- StarUML numera por el orden del arreglo `messages`. Hacia la izquierda la etiqueta
  queda abajo de la línea; hacia la derecha, arriba.
- Espaciado entre mensajes: 29 a 36 px; 50 a 56 px cuando un mensaje a la izquierda va
  seguido de uno a la derecha (si no, se enciman); 22 a 34 px extra entre flujos.
- Activaciones con pila de llamadas: una lifeline sigue activa mientras atiende (manda
  mensajes o recibe replies). Así cada mensaje sale de una caja.
- Separación entre lifelines: al menos lo que mide la etiqueta más larga que viaja entre
  ellas, más un margen. Si una etiqueta cae sobre una activación abierta, se baja el
  mensaje.
- Auto-mensaje (`de` igual a `a`): lazo de 30 × 15 px a la derecha de la activación que
  llama, activación anidada 7 px a la derecha y texto a la derecha del lazo. Se permite en
  control y entity (procesamiento interno); en una boundary es aviso (la lógica va en el
  control) y en un actor es error.
- Lifelines: height = fin - 40; linePart top = 106 y height = h - 66. El marco se ajusta
  al contenido.
- Una lifeline sin nombre con rol tipado se ve como ": Tipo".

## Diagramas de estados y de actividades

- `mdj_comportamiento` lee la máquina de estados o la actividad a la que pertenece el
  diagrama. `mdj_validar` revisa:
  - Estados: un solo estado inicial por región (la principal debe tenerlo), el inicial con
    una sola salida y sin entradas, finales sin salidas, estados inalcanzables desde el
    inicial o sin salida (las transiciones del estado compuesto cuentan para sus
    subestados), decisiones con al menos dos salidas y guardas, y transiciones ambiguas
    (mismo disparador y misma guarda desde un estado).
  - Actividades: un nodo inicial, finales sin salidas, decisiones con guardas distintas,
    fusión/bifurcación/unión con sus entradas y salidas, acciones con varias entradas
    (unión implícita: usa un nodo de fusión) o varias salidas (usa decisión o
    bifurcación), nodos inalcanzables y acciones que no llevan a un final.
  - Cajas encimadas (un subestado dentro de su estado compuesto no cuenta).
- Una actividad anidada (p. ej. la actividad *do* de un estado) se valida por separado.

## Exportar y revisar
 
- `staruml_exportar` usa el CLI (`StarUML image ... -f svg -s selector`) con límite de
  tiempo. Diagramas con el mismo nombre se sobrescriben entre sí al exportar todos; al
  exportar uno solo (por nombre o id) se resuelve la ambigüedad automáticamente.
- `svg_recortar` usa Chrome headless con un perfil propio y lo cierra al terminar;
  funciona con rutas con espacios.
- `staruml_ver_visual` genera una imagen PNG optimizada (1600 px máx.) y la devuelve
  directamente en el protocolo para inspección visual.

## Inspección y sincronización con código

- `staruml_comparar_codigo`: escanea código fuente (Java, Python, TypeScript/JavaScript,
  C#, Kotlin, Go) y
  compara contra las clases o secuencias del diagrama:
  - En clases: compara nombres, atributos, tipos de datos normalizados, métodos y
    asociaciones reflejadas como campos o colecciones (`List<T>`).
  - Kotlin: las propiedades `val`/`var` del constructor primario cuentan como atributos;
    `companion object` e `init` no. Go: los campos embebidos cuentan como herencia, los
    métodos con receptor se asignan a su tipo y `type X int` con constantes `iota` es una
    enumeración. Los archivos `_test.go` no se escanean.
  - En secuencias: verifica que las clases receptoras tengan implementado el método
    invocado y calcula el porcentaje de cobertura.
- `staruml_diagrama_a_codigo`: genera esqueletos limpios y tipados (Java, Python,
  TypeScript, C#) respetando el estándar del lenguaje: getters y setters en Java,
  dataclasses en Python, propiedades automáticas en PascalCase y `namespace` en C#.
- `staruml_codigo_a_diagrama`: extrae clases desde código existente y las incorpora al
  paquete del `.mdj` con su correspondiente vista.

