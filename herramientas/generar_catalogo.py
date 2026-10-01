# Escribe uml_catalogo.md: por cada diagrama, para que sirve, su notacion, la seccion de la especificacion UML 2.5.1
# (OMG, formal/17-12-05) donde se define y la paleta real de StarUML con lo que el servidor sabe dibujar.
# Las descripciones son propias; la paleta y las plantillas salen de staruml_metamodelo.json y plantillas_vistas.json,
# asi que el catalogo siempre coincide con lo que la herramienta hace.
#
# Uso: python herramientas/generar_catalogo.py
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

import staruml_uml as U  # noqa: E402

SPEC = 'https://www.omg.org/spec/UML/2.5.1/PDF'

# (titulo, familia, seccion de la especificacion, descripcion)
DIAGRAMAS = {
    'UMLClassDiagram': ('Clases', 'UML estructura', '9 Classification, 10 Simple Classifiers, 11.5 Associations',
                        'Clases, interfaces, tipos de datos, enumeraciones y senales con sus atributos y operaciones, y las '
                        'relaciones entre ellos: asociacion (con agregacion o composicion), generalizacion, realizacion de '
                        'interfaz, dependencia y clase asociacion. Es el diagrama del modelo de dominio y del diseno.'),
    'UMLPackageDiagram': ('Paquetes', 'UML estructura', '12.2 Packages',
                          'Paquetes, modelos y subsistemas y las dependencias, importaciones y fusiones entre ellos. Sirve '
                          'para mostrar la organizacion en capas o modulos de un sistema.'),
    'UMLObjectDiagram': ('Objetos', 'UML estructura', '9.8 Instances',
                         'Instancias (especificaciones de instancia) con valores en sus slots y los enlaces entre ellas: una '
                         'foto del sistema en un momento dado.'),
    'UMLCompositeStructureDiagram': ('Estructura compuesta', 'UML estructura', '11.2 Structured Classifiers, 11.3 Encapsulated '
                                     'Classifiers, 11.7 Collaborations',
                                     'La estructura interna de un clasificador: partes, puertos y conectores; y las '
                                     'colaboraciones con los roles que intervienen.'),
    'UMLComponentDiagram': ('Componentes', 'UML estructura', '11.6 Components',
                            'Componentes con sus interfaces provistas (lollipop) y requeridas (socket), puertos, '
                            'artefactos que los manifiestan y las dependencias y conectores de ensamble entre ellos.'),
    'UMLDeploymentDiagram': ('Despliegue', 'UML estructura', '19 Deployments',
                             'La arquitectura fisica: nodos, dispositivos y entornos de ejecucion (anidables), las rutas de '
                             'comunicacion entre ellos, los artefactos desplegados en cada nodo (despliegue) y los '
                             'componentes que cada artefacto manifiesta.'),
    'UMLProfileDiagram': ('Perfil', 'UML estructura', '12.3 Profiles',
                          'Perfiles con sus estereotipos, las metaclases que extienden (extension) y las importaciones de '
                          'metaclases. Sirve para definir vocabularios propios sobre UML.'),
    'UMLUseCaseDiagram': ('Casos de uso', 'UML comportamiento', '18 Use Cases',
                          'Actores, casos de uso y el sujeto (sistema) que los contiene, con asociaciones, include, extend '
                          '(con puntos de extension) y generalizaciones.'),
    'UMLActivityDiagram': ('Actividades', 'UML comportamiento', '15 Activities, 16 Actions',
                           'Flujos de acciones con nodos inicial y final, decisiones y fusiones, bifurcaciones y uniones, '
                           'nodos de objeto, pines, particiones (carriles), regiones interrumpibles y de expansion, y flujos '
                           'de control y de objetos.'),
    'UMLStatechartDiagram': ('Estados', 'UML comportamiento', '14 State Machines',
                             'Maquinas de estados: estados simples y compuestos (con regiones), pseudoestados (inicial, '
                             'historia, eleccion, union, bifurcacion, punto de entrada y salida, terminacion), estados '
                             'finales y transiciones con disparador, guarda y efecto.'),
    'UMLSequenceDiagram': ('Secuencia', 'UML interaccion', '17.8 Sequence Diagrams',
                           'Lifelines y los mensajes entre ellas en orden temporal (sincronos, asincronos, respuestas, '
                           'creacion y destruccion), activaciones, fragmentos combinados (alt, opt, loop, par...), usos de '
                           'interaccion, invariantes de estado y restricciones de tiempo y duracion.'),
    'UMLCommunicationDiagram': ('Comunicacion', 'UML interaccion', '17.9 Communication Diagrams',
                                'La misma interaccion que una secuencia pero ordenada por enlaces: lifelines unidas por '
                                'conectores con los mensajes numerados encima.'),
    'UMLTimingDiagram': ('Tiempos', 'UML interaccion', '17.11 Timing Diagrams',
                         'Lifelines en un eje de tiempo con sus estados o condiciones, segmentos de tiempo, marcas, '
                         'mensajes entre segmentos y restricciones de tiempo y duracion.'),
    'UMLInteractionOverviewDiagram': ('Vista general de interaccion', 'UML interaccion', '17.10 Interaction Overview Diagrams',
                                      'Un diagrama de actividades cuyos nodos son interacciones o usos de interaccion: '
                                      'muestra el flujo de control entre escenarios.'),
    'UMLInformationFlowDiagram': ('Flujo de informacion', 'UML', '20 Information Flows',
                                  'Elementos de informacion y los flujos de informacion entre clasificadores, a un nivel '
                                  'mas abstracto que los mensajes.'),
    'ERDDiagram': ('Entidad-relacion (ERD)', 'StarUML', 'no es UML',
                   'Entidades con sus columnas (llave primaria, foranea, tipo) y las relaciones entre ellas con su '
                   'cardinalidad (pata de gallo).'),
    'FCFlowchartDiagram': ('Diagrama de flujo', 'StarUML', 'no es UML',
                           'Notacion clasica de diagramas de flujo: terminador, proceso, decision, datos, documento, base '
                           'de datos, conectores y flujos.'),
    'DFDDiagram': ('Flujo de datos (DFD)', 'StarUML', 'no es UML',
                   'Entidades externas, procesos, almacenes de datos y los flujos de datos entre ellos.'),
    'BPMNDiagram': ('BPMN', 'StarUML', 'no es UML (BPMN 2.0, OMG)',
                    'Procesos de negocio: eventos, tareas, subprocesos, compuertas, objetos y almacenes de datos, '
                    'carriles y pools, flujos de secuencia y de mensajes, coreografias y conversaciones.'),
    'C4Diagram': ('C4', 'StarUML', 'no es UML (modelo C4)',
                  'Personas, sistemas de software, contenedores y componentes con sus relaciones, en los niveles de '
                  'contexto, contenedores y componentes del modelo C4.'),
    'SysMLRequirementDiagram': ('SysML requisitos', 'StarUML', 'no es UML (SysML 1.x, OMG)',
                                'Requisitos y sus relaciones de derivacion, satisfaccion, verificacion, refinamiento, '
                                'copia y traza.'),
    'SysMLBlockDefinitionDiagram': ('SysML definicion de bloques', 'StarUML', 'no es UML (SysML 1.x, OMG)',
                                    'Bloques, bloques de interfaz, bloques de restriccion y tipos de valor con sus '
                                    'propiedades y relaciones.'),
    'SysMLInternalBlockDiagram': ('SysML bloque interno', 'StarUML', 'no es UML (SysML 1.x, OMG)',
                                  'La estructura interna de un bloque: partes, referencias, valores, puertos y conectores.'),
    'SysMLParametricDiagram': ('SysML parametrico', 'StarUML', 'no es UML (SysML 1.x, OMG)',
                               'Propiedades de restriccion y sus parametros conectados a valores del sistema.'),
    'WFWireframeDiagram': ('Wireframe', 'StarUML', 'no es UML',
                           'Bocetos de pantallas: marcos de ventana, botones, campos, listas, tablas y otros controles.'),
    'MMMindmapDiagram': ('Mapa mental', 'StarUML', 'no es UML', 'Nodos de un mapa mental y sus ramas.'),
    'AWSDiagram': ('AWS', 'StarUML', 'no es UML', 'Arquitectura en Amazon Web Services: grupos, servicios, recursos y flechas.'),
    'GCPDiagram': ('Google Cloud', 'StarUML', 'no es UML', 'Arquitectura en Google Cloud: zonas, productos, servicios y rutas.'),
}

FORMA = {'rect': 'caja', 'point': 'caja', 'line': 'linea'}


def main():
    mm = U.metamodelo()
    pl = U.plantillas()
    inv = {v: k for k, v in U.ALIAS_DIAGRAMA.items()}
    out = ['# Catalogo de diagramas y simbolos', '',
           f'Generado con `herramientas/generar_catalogo.py` a partir de StarUML {mm.get("staruml")}. Las descripciones '
           f'son propias. Las secciones citadas son de la especificacion [OMG UML 2.5.1]({SPEC}), que no se incluye '
           'en el repositorio.', '',
           'Cada simbolo listado se puede dibujar con `mdj_dibujar` (por su etiqueta de paleta) y cada diagrama se puede '
           'crear con `mdj_diagrama_crear` (por su nombre corto o su tipo de StarUML). `mdj_catalogo` da la misma '
           'informacion en JSON. En las lineas, el ejemplo es el par de vistas con que StarUML la dibujo en la referencia; '
           'cualquier otro par que StarUML acepte tambien sirve.', '', '| Diagrama | Nombre corto | Tipo StarUML | Familia | Especificacion | Simbolos |',
           '|---|---|---|---|---|---|']
    orden = [t for t in DIAGRAMAS if t in mm.get('paletas', {})] + sorted(set(mm.get('paletas', {})) - set(DIAGRAMAS))
    for t in orden:
        titulo, familia, sec, _ = DIAGRAMAS.get(t, (t, '', '', ''))
        n = len(pl['plantillas'].get(t, {}))
        out.append(f'| {titulo} | `{inv.get(t, "")}` | `{t}` | {familia} | {sec} | {n} |')
    for t in orden:
        titulo, familia, sec, desc = DIAGRAMAS.get(t, (t, '', '', ''))
        out += ['', f'## {titulo}', '', f'`{t}` (nombre corto `{inv.get(t, "")}`). Especificacion: {sec}.', '', desc, '',
                '| Simbolo | Forma | Elemento | Vista | Notas |', '|---|---|---|---|---|']
        for c, p in pl['plantillas'].get(t, {}).items():
            label, ident = c.split('|')
            notas = ''
            usa_cola, usa_cabeza = U.necesita(p)
            if p['forma'] == 'line':
                notas = 'ejemplo: ' + ' → '.join(x for x in ((p.get('cola') if usa_cola else '(sin origen)'),
                                                             (p.get('cabeza') if usa_cabeza else '(sin destino)')))
            elif usa_cola or usa_cabeza:
                notas = f'va sobre {p.get("cabeza") or p.get("cola")}'
            out.append(f'| {label} | {FORMA.get(p["forma"], p["forma"])} | `{ident}` | `{p["vista"]}` | {notas} |')
        nd = [o for o in pl.get('no_dibujables', []) if o['diagrama'] == t]
        if nd:
            out += ['', 'Sin plantilla (StarUML no los dibuja sin interaccion del usuario en este diagrama):', '']
            out += [f'- {o["simbolo"].split("|")[0]}: {o["motivo"]}' for o in nd]
    with open(os.path.join(RAIZ, 'uml_catalogo.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out) + '\n')
    print(f'uml_catalogo.md: {len(orden)} diagramas')


if __name__ == '__main__':
    main()
