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
- Boundary y control sin atributos ni métodos. En análisis ninguna clase lleva métodos: `mdj_validar`
  lo revisa en las clases con estereotipo de robustez (boundary, control, entity) y en los actores; las
  clases de diseño, sin esos estereotipos, sí llevan métodos.
- Una sola notación (la de íconos) en todo el proyecto. `mdj_validar` avisa de las vistas de
  robustez que no la usan, de los estereotipos guardados como texto y de las cajas encimadas.
- Cada caso de uso se analiza en un paquete con su mismo nombre (sin importar acentos ni mayúsculas).
  Si el modelo sigue esa convención, `mdj_validar` avisa cuando el paquete no tiene control o
  boundaries, cuando un actor del caso de uso no tiene boundary en el paquete, cuando una boundary
  atiende a un actor que no participa en el caso de uso (la herencia entre actores cuenta) y qué
  casos de uso aún no tienen paquete.
- Disposición del diagrama de análisis (`mdj_robustez_generar` la hace sola): actor a la izquierda,
  las pantallas (boundary) en columna con su nota debajo o al lado, el control a su derecha y a la
  derecha el modelo de dominio, por capas según la navegabilidad. Actor → pantalla y pantalla →
  control son rectas con flecha; entre entidades, flecha de navegación, multiplicidad y rol en cada
  asociación. Las líneas control → entidad no se dibujan (con `lineas_control` sí).
- La dirección de cada asociación decide quién va arriba: escribirla en el sentido de la navegación
  (Cliente → Pedido, no Pedido → Cliente) evita ciclos que mandan una entidad al fondo con líneas largas.
- No usar `mdj_diagrama_generar` con Boundary, Control o Entity: sus íconos se estiran si se les da
  tamaño, no muestran los atributos y la paleta de clases no trae actor (la herramienta lo rechaza).

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

## Cualquier diagrama: componentes, despliegue y los demás

- Los 28 tipos de diagrama de StarUML y los símbolos de sus paletas están en
  `uml_catalogo.md` (y en `mdj_catalogo`). Un símbolo se dibuja con `mdj_dibujar` por
  su nombre en la paleta (`Node`, `Artifact`, `Deployment`...), y el archivo queda como
  si se hubiera dibujado en StarUML: se copia lo que StarUML crea para ese símbolo.
- Cada diagrama vive donde StarUML lo pone: estados dentro de su máquina de estados
  (los estados en su región), actividades dentro de su actividad, secuencia,
  comunicación y tiempos dentro de colaboración > interacción, bloque interno de SysML
  dentro de un bloque. `mdj_diagrama_crear` crea esos contenedores.
- Anidar es contener también en el modelo: un artefacto dibujado dentro de un nodo es
  del nodo, un subestado está en la región de su estado compuesto, una acción dentro de
  una partición está en la partición. `mdj_diagrama_generar` lo hace con `dentro`.
- Despliegue: los nodos y entornos de ejecución se anidan (servidor > contenedor), los
  artefactos van en el nodo donde se despliegan o se unen con `Deployment`, y los nodos
  se comunican con `Communication Path`, con el protocolo como nombre.
- Componentes: las interfaces provistas son `Interface Realization` del componente a la
  interfaz y las requeridas `Dependency`; los puertos van sobre el componente (`sobre`).
- Lo de adentro de un contenedor que encapsula (componente, clase o bloque con partes,
  actividad estructurada, región de expansión) se comunica hacia afuera por el
  contenedor o por un puerto o pin suyo, no con una línea directa que atraviese el
  borde. `mdj_diagrama_generar` y `mdj_validar` lo avisan. En los demás contenedores
  (sujeto de casos de uso, carril, pool, paquete, estado compuesto, nodo, marco) cruzar
  el borde es lo normal.
- Carriles (swimlanes, pools, lanes): contiguos y del mismo largo, con el flujo en un
  solo sentido (hacia abajo en verticales, hacia la derecha en horizontales). Lo que
  pertenece a un carril va `dentro` de él, también los nodos de objeto y almacenes.
- `mdj_validar` revisa el metamodelo de StarUML en todos los diagramas: tipos que
  StarUML no conoce, elementos en campos que no existen, vistas que el diagrama no
  admite y líneas sin extremos válidos.

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
- `staruml_programa_a_diagrama`: dibuja el diagrama de clases de un programa ya hecho.
  - Modelo: un paquete del programa con sus paquetes (anidados como en Java), clases,
    interfaces, enumeraciones y records; atributos y métodos con visibilidad, `static` y
    `abstract`; tipos del programa como referencias y los demás como se escribieron.
  - Relaciones: `extends` es generalización, `implements` es realización de interfaz y cada
    campo de instancia cuyo tipo es otra clase del programa es una asociación con el campo
    como rol (colecciones y `Map` con `0..*`, un solo objeto con `1`). Si dos clases se
    referencian una a otra con un campo cada una, queda una sola asociación navegable en
    ambos sentidos. Las constantes `static` quedan como atributos. Con `dependencias`, los
    tipos de parámetros y retornos que no estén ya relacionados dan dependencias.
  - Acomodo: la clase base arriba de sus derivadas y el dueño del campo arriba de la clase
    referida (mientras no alargue el diagrama de más); filas de hasta 7 cajas; cada línea
    que salta filas pasa por un hueco reservado y corre por el canal libre entre filas, así
    que ninguna cruza una caja. El resultado reporta `lineas_que_cruzan_cajas` (vacío).
  - Un diagrama para todo el programa o uno por paquete; sin indicarlo, por paquete cuando hay más de
    60 clases en varios paquetes. En cada diagrama por paquete, las clases de otros paquetes que se
    relacionan con las suyas aparecen compactas (solo nombre y "(from paquete)") con esas relaciones.
  - El diagrama coincide al 100 % con el programa en `staruml_comparar_codigo`.
- `staruml_codigo_a_diagrama`: extrae clases desde código existente y las incorpora al
  paquete del `.mdj` con su correspondiente vista.

