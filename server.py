#!/usr/bin/env python3
# Servidor MCP para StarUML (.mdj). Sin dependencias: JSON-RPC 2.0 por stdio.
#   claude mcp add staruml -- python3 "/ruta/a/MCP StarUML/server.py"
import base64
import json
import math
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import staruml_mdj as M          # noqa: E402
import staruml_render as R       # noqa: E402
import staruml_compare as C      # noqa: E402

VERSION = '1.0.0'
PROTOCOLOS = ('2025-06-18', '2025-03-26', '2024-11-05')
AQUI = os.path.dirname(os.path.abspath(__file__))

INSTRUCCIONES = (
    'Herramientas para leer, validar, editar, exportar, visualizar en tiempo real y sincronizar con codigo '
    'archivos .mdj de StarUML sin abrir la aplicacion. '
    'Las de edicion respaldan antes de escribir, no escriben si StarUML esta abierto y validan al terminar. '
    'Llama a staruml_reglas para ver las convenciones (UML, OOSE, secuencias, lineas y codigo). '
    'Flujo tipico: mdj_resumen -> mdj_modelo / mdj_secuencia -> staruml_ver_visual -> staruml_comparar_codigo -> editar -> mdj_validar.')


S = lambda **kw: {'type': 'string', **kw}
N = lambda **kw: {'type': 'number', **kw}
B = lambda **kw: {'type': 'boolean', **kw}
ARCHIVO = S(description='Ruta del archivo .mdj')
SALIDA = S(description='Opcional: escribir en este otro archivo en lugar de sobrescribir el original')
FORZAR = B(description='Escribir aunque StarUML este abierto (solo si no tiene este archivo cargado)')
PUNTOS = {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'number'}, 'minItems': 2, 'maxItems': 2},
          'description': 'Puntos intermedios [[x,y],...]. Los extremos se calculan como StarUML.'}


def obj(props, req=()):
    return {'type': 'object', 'properties': props, 'required': list(req), 'additionalProperties': False}


def ro(title):
    return {'title': title, 'readOnlyHint': True, 'openWorldHint': False}


def rw(title, destructive=False):
    return {'title': title, 'readOnlyHint': False, 'destructiveHint': destructive, 'idempotentHint': False, 'openWorldHint': False}


TOOLS = []


def tool(name, desc, schema, ann):
    def deco(fn):
        TOOLS.append({'name': name, 'description': desc, 'inputSchema': schema, 'annotations': ann, 'fn': fn})
        return fn
    return deco


def escribir(doc, a, extra=None):
    bk = doc.save(a.get('salida'), backup=True, force=bool(a.get('forzar')))
    v = M.validar(doc, oose=False)
    res = {'guardado_en': doc.path, 'respaldo': bk,
           'validacion': {k: v[k] for k in ('ids', 'n_duplicados', 'n_colgantes', 'n_parent_mismatch')}}
    if extra:
        res.update(extra)
    return res


# ---------------------------------------------------------------------------
# Estado y reglas
# ---------------------------------------------------------------------------

@tool('staruml_estado', 'Dice si la aplicacion de StarUML esta abierta (no se debe escribir el .mdj si lo esta), '
      'y donde estan el CLI de StarUML, Chrome y la carpeta de respaldos.', obj({}), ro('Estado de StarUML'))
def t_estado(a):
    return {'staruml_abierto': M.staruml_gui_abierto(), 'cli_staruml': M.staruml_cli(), 'chrome': M.chrome_bin(),
            'carpeta_respaldos': M.BACKUP_DIR, 'version_mcp': VERSION}


@tool('staruml_reglas', 'Devuelve las convenciones de trabajo: formato del archivo, respaldo, lineas en diagramas de clases, '
      'reglas de robustez (OOSE) y reglas de los diagramas de secuencia. Leer antes de editar.', obj({}), ro('Reglas de trabajo'))
def t_reglas(a):
    with open(os.path.join(AQUI, 'reglas.md'), encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

@tool('mdj_resumen', 'Lista los diagramas del .mdj (tipo, nombre, id, ruta, cuantas vistas, cual abre por defecto) '
      'y cuenta las clases por estereotipo.', obj({'archivo': ARCHIVO}, ['archivo']), ro('Resumen del .mdj'))
def t_resumen(a):
    return M.resumen(M.Doc(a['archivo']))


@tool('mdj_modelo', 'Clases y actores con estereotipo, atributos, metodos y documentacion; asociaciones con '
      'multiplicidades, roles y navegabilidad; generalizaciones y dependencias. Se puede filtrar por texto o paquete.',
      obj({'archivo': ARCHIVO, 'filtro': S(description='Texto que debe aparecer en el nombre'),
           'paquete': S(description='Nombre o id del paquete')}, ['archivo']), ro('Modelo'))
def t_modelo(a):
    return M.modelo(M.Doc(a['archivo']), a.get('filtro'), a.get('paquete'))


@tool('mdj_secuencia', 'Mensajes numerados de un diagrama de secuencia (origen, destino, tipo de cada lado, reply) y el orden '
      'de las lifelines.', obj({'archivo': ARCHIVO, 'diagrama': S(description='Nombre o id del diagrama de secuencia')},
                               ['archivo', 'diagrama']), ro('Secuencia'))
def t_secuencia(a):
    return M.secuencia(M.Doc(a['archivo']), a['diagrama'])


@tool('mdj_geometria', 'Cajas (posicion y tamano) y lineas (puntos) de un diagrama, con el id de cada vista.',
      obj({'archivo': ARCHIVO, 'diagrama': S()}, ['archivo', 'diagrama']), ro('Geometria'))
def t_geometria(a):
    return M.geometria(M.Doc(a['archivo']), a['diagrama'])


@tool('mdj_buscar', 'Busca elementos del modelo por texto en el nombre y/o por tipo (UMLClass, UMLAssociation, UMLActor...). '
      'Devuelve ids para usarlos en otras herramientas.',
      obj({'archivo': ARCHIVO, 'texto': S(), 'tipo': S(), 'limite': N()}, ['archivo']), ro('Buscar'))
def t_buscar(a):
    return M.buscar(M.Doc(a['archivo']), a.get('texto'), a.get('tipo'), int(a.get('limite') or 60))


@tool('mdj_validar', 'Integridad (ids duplicados, referencias colgantes, _parent que no coincide) y, si oose=true, reglas de '
      'robustez: metodos o atributos donde no van, mas de un control, asociaciones prohibidas, mensajes no validos, '
      'entity->entity sin asociacion, consultas sin reply, vistas de mensaje incompletas y llamadas sin activacion.',
      obj({'archivo': ARCHIVO, 'oose': B(description='Revisar tambien reglas OOSE (default true)')}, ['archivo']),
      ro('Validar'))
def t_validar(a):
    return M.validar(M.Doc(a['archivo']), oose=a.get('oose', True) is not False)


@tool('mdj_diff', 'Diferencias a nivel modelo entre dos .mdj: elementos quitados y agregados, cambios de nombre, '
      'multiplicidad, navegabilidad, documentacion y extremos de asociaciones, y cambios en el numero de vistas.',
      obj({'archivo_a': S(), 'archivo_b': S()}, ['archivo_a', 'archivo_b']), ro('Comparar'))
def t_diff(a):
    return M.diff(M.Doc(a['archivo_a']), M.Doc(a['archivo_b']))


# ---------------------------------------------------------------------------
# Exportar y revisar
# ---------------------------------------------------------------------------

@tool('staruml_exportar', 'Exporta diagramas con el CLI de StarUML (svg por defecto). diagrama = nombre o id; omitido o '
      '"todos" exporta todos. Tiene limite de tiempo.',
      obj({'archivo': ARCHIVO, 'carpeta': S(description='Carpeta de salida'), 'diagrama': S(),
           'formato': S(enum=['svg', 'png', 'jpeg', 'pdf'])}, ['archivo', 'carpeta']), rw('Exportar'))
def t_exportar(a):
    return R.exportar(a['archivo'], a['carpeta'], a.get('diagrama'), a.get('formato') or 'svg')


@tool('svg_revisar', 'Revisa un SVG exportado contra el .mdj: lineas que cruzan notas o cajas, lineas sobre etiquetas, '
      'etiquetas encimadas, texto fuera de las notas y etiquetas sobre activaciones (secuencias).',
      obj({'svg': S(), 'archivo': ARCHIVO, 'diagrama': S()}, ['svg', 'archivo', 'diagrama']), ro('Revisar SVG'))
def t_svg_revisar(a):
    return R.revisar_svg(a['svg'], a['archivo'], a['diagrama'])


@tool('svg_recortar', 'Recorta una zona de un SVG a PNG con Chrome headless y devuelve la imagen para verla. '
      'x, y, ancho y alto en pixeles del SVG; sin ancho/alto toma todo. max_lado reduce la imagen (default 1600).',
      obj({'svg': S(), 'x': N(), 'y': N(), 'ancho': N(), 'alto': N(), 'salida': S(description='Guardar el PNG aqui'),
           'max_lado': N(), 'devolver_imagen': B(description='default true')}, ['svg']), rw('Recortar SVG'))
def t_svg_recortar(a):
    r = R.recortar(a['svg'], a.get('x') or 0, a.get('y') or 0, a.get('ancho'), a.get('alto'), a.get('salida'),
                   a.get('max_lado', 1600))
    info = {'salida': r['salida'], 'region': r['region'], 'tamano_svg': r['tamano_svg']}
    content = [{'type': 'text', 'text': json.dumps(info, ensure_ascii=False)}]
    if a.get('devolver_imagen', True) is not False:
        content.append({'type': 'image', 'mimeType': 'image/png', 'data': base64.b64encode(r['png']).decode()})
    return {'__content__': content}


# ---------------------------------------------------------------------------
# Visualizacion e integracion con codigo
# ---------------------------------------------------------------------------

@tool('staruml_ver_visual', 'Visualiza un diagrama como imagen PNG de alta resolucion. '
      'Devuelve la imagen y sus metadatos directamente para que el asistente y el usuario puedan ver e inspeccionar '
      'visualmente el diseno.',
      obj({'archivo': ARCHIVO, 'diagrama': S(description='Nombre o id del diagrama a visualizar'),
           'salida': S(description='Ruta opcional para guardar el archivo PNG generado'),
           'max_lado': N(description='Lado maximo en pixeles (default 1600 para balance optimo)'),
           'forzar': B(description='Forzar re-exportacion aunque exista cache')},
          ['archivo', 'diagrama']), rw('Ver diagrama visual'))
def t_ver_visual(a):
    r = R.ver_visual(a['archivo'], a['diagrama'], salida=a.get('salida'),
                     max_lado=a.get('max_lado', 1600), forzar=bool(a.get('forzar')))
    info = {
        'diagrama': r['diagrama'],
        'tipo': r['tipo'],
        'tamano_original_px': r['tamano_original'],
        'vistas_totales': r['vistas'],
        'elementos_destacados': r['elementos'],
        'guardado_en': r['salida']
    }
    content = [
        {'type': 'text', 'text': json.dumps(info, ensure_ascii=False, indent=2)},
        {'type': 'image', 'mimeType': 'image/png', 'data': base64.b64encode(r['png']).decode()}
    ]
    return {'__content__': content}


@tool('staruml_comparar_codigo', 'Compara exhaustivamente un diagrama UML (de clases o de secuencia) contra codigo fuente '
      '(Java, Python, TypeScript, C#). Analiza clases, atributos, metodos, tipos, '
      'asociaciones y llamadas de secuencia, calculando el porcentaje de alineacion y reportando discrepancias.',
      obj({'archivo': ARCHIVO, 'diagrama': S(description='Nombre o id del diagrama de clases o secuencia'),
           'ruta_codigo': S(description='Carpeta o archivo de codigo fuente a comparar'),
           'lenguaje': S(enum=['auto', 'java', 'python', 'typescript', 'csharp'], description='Lenguaje (default auto)')},
          ['archivo', 'diagrama', 'ruta_codigo']), ro('Comparar con codigo'))
def t_comparar_codigo(a):
    doc = M.Doc(a['archivo'])
    return C.comparar_diagrama_con_codigo(doc, a['diagrama'], a['ruta_codigo'], a.get('lenguaje', 'auto'))


@tool('staruml_diagrama_a_codigo', 'Genera esqueletos de codigo limpios y tipados (Java, Python, TypeScript) listos para '
      'implementar a partir de las clases, atributos, metodos y asociaciones de un diagrama de clases del .mdj. '
      'No reemplaza archivos que ya existen en carpeta_salida salvo con sobrescribir=true.',
      obj({'archivo': ARCHIVO, 'diagrama': S(description='Nombre o id del diagrama de clases'),
           'lenguaje': S(enum=['java', 'python', 'typescript'], description='Lenguaje de destino (default java)'),
           'carpeta_salida': S(description='Carpeta donde se guardaran los archivos de codigo generados'),
           'sobrescribir': B(description='Reemplazar los archivos que ya existan (default false: se omiten y se reportan)')},
          ['archivo', 'diagrama']), rw('Generar codigo', destructive=True))
def t_diagrama_a_codigo(a):
    doc = M.Doc(a['archivo'])
    return C.generar_codigo_desde_diagrama(doc, a['diagrama'], a.get('lenguaje', 'java'), a.get('carpeta_salida'),
                                           bool(a.get('sobrescribir')))


@tool('staruml_codigo_a_diagrama', 'Importa clases, atributos y metodos desde archivos de codigo fuente (Java, Python, TS) '
      'y los crea dentro de un paquete y diagrama de clases del .mdj.',
      obj({'archivo': ARCHIVO, 'ruta_codigo': S(description='Carpeta o archivo de codigo fuente a importar'),
           'paquete': S(description='Nombre o id del paquete destino en el .mdj'),
           'diagrama': S(description='Opcional: nombre del diagrama de clases donde agregarlas visualmente'),
           'lenguaje': S(enum=['auto', 'java', 'python', 'typescript', 'csharp']),
           'modo': S(enum=['agregar', 'sincronizar'], description='agregar (default): solo agrega los atributos que falten; '
                                                                 'sincronizar: deja exactamente los del codigo y reporta los quitados'),
           'salida': SALIDA, 'forzar': FORZAR},
          ['archivo', 'ruta_codigo', 'paquete']), rw('Importar codigo a diagrama', destructive=True))
def t_codigo_a_diagrama(a):
    doc = M.Doc(a['archivo'])
    info = C.importar_codigo_a_diagrama(doc, a['ruta_codigo'], a['paquete'], a.get('diagrama'), a.get('lenguaje', 'auto'),
                                        a.get('modo') or 'agregar')
    return escribir(doc, a, info)


# ---------------------------------------------------------------------------
# Edicion
# ---------------------------------------------------------------------------

@tool('mdj_respaldar', 'Copia el .mdj a la carpeta de respaldos (o a la indicada) y confirma que quedo identico.',
      obj({'archivo': ARCHIVO, 'carpeta': S()}, ['archivo']), rw('Respaldar'))
def t_respaldar(a):
    return {'respaldo': M.backup_file(os.path.abspath(os.path.expanduser(a['archivo'])), a.get('carpeta'))}


@tool('mdj_clase_crear', 'Crea una clase en un paquete, con estereotipo (boundary, control, entity o ninguno), atributos '
      '(solo para entity) y documentacion. Para dibujarla usa mdj_vista_agregar.',
      obj({'archivo': ARCHIVO, 'paquete': S(), 'nombre': S(), 'estereotipo': S(enum=['boundary', 'control', 'entity', 'ninguno']),
           'atributos': {'type': 'array', 'items': {'type': 'string'}}, 'documentacion': S(), 'salida': SALIDA, 'forzar': FORZAR},
          ['archivo', 'paquete', 'nombre']), rw('Crear clase'))
def t_clase_crear(a):
    doc = M.Doc(a['archivo'])
    pk = doc.find(a['paquete'], types=('UMLPackage', 'UMLModel', 'UMLSubsystem'))
    est = a.get('estereotipo') or 'ninguno'
    if est in ('boundary', 'control') and a.get('atributos'):
        raise M.MdjError('Boundary y control van sin atributos')
    c = {'_type': 'UMLClass', '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': a['nombre']}
    if a.get('documentacion'):
        c['documentation'] = a['documentacion']
    if est != 'ninguno':
        c['stereotype'] = M.ref(doc.stereotype_id(est))
    pk.setdefault('ownedElements', []).append(c)
    doc.reindex()
    if a.get('atributos'):
        M.set_atributos(doc, c, a['atributos'])
    return escribir(doc, a, {'clase': c['_id']})


@tool('mdj_renombrar', 'Cambia el nombre de un elemento (id, nombre o Tipo:Nombre) y el texto de su nombre en todas sus vistas.',
      obj({'archivo': ARCHIVO, 'elemento': S(), 'nuevo_nombre': S(), 'salida': SALIDA, 'forzar': FORZAR},
          ['archivo', 'elemento', 'nuevo_nombre']), rw('Renombrar'))
def t_renombrar(a):
    doc = M.Doc(a['archivo'])
    el = doc.find(a['elemento'])
    viejo = el.get('name')
    el['name'] = a['nuevo_nombre']
    n = 0
    for dg, v in doc.views_of(el['_id']):
        lab = M._name_label(v)
        if lab is not None and lab.get('text', '').endswith(viejo or ''):
            lab['text'] = lab['text'][: len(lab['text']) - len(viejo or '')] + a['nuevo_nombre']; n += 1
    return escribir(doc, a, {'antes': viejo, 'despues': a['nuevo_nombre'], 'vistas_actualizadas': n})


@tool('mdj_documentacion', 'Pone el texto de Documentation de un elemento (responsabilidad de la clase, por ejemplo).',
      obj({'archivo': ARCHIVO, 'elemento': S(), 'texto': S(), 'salida': SALIDA, 'forzar': FORZAR},
          ['archivo', 'elemento', 'texto']), rw('Documentacion'))
def t_documentacion(a):
    doc = M.Doc(a['archivo'])
    el = doc.find(a['elemento'])
    el['documentation'] = a['texto']
    return escribir(doc, a)


@tool('mdj_atributos', 'Deja la lista de atributos de una clase exactamente como se indica (conserva los ids de los que ya '
      'existian, crea los nuevos, quita los que sobran) y rehace el compartimento de atributos en todas sus vistas.',
      obj({'archivo': ARCHIVO, 'clase': S(), 'atributos': {'type': 'array', 'items': {'type': 'string'}},
           'salida': SALIDA, 'forzar': FORZAR}, ['archivo', 'clase', 'atributos']), rw('Atributos'))
def t_atributos(a):
    doc = M.Doc(a['archivo'])
    c = doc.find(a['clase'], types=('UMLClass',))
    if doc.kind(c) in ('boundary', 'control') and a['atributos']:
        raise M.MdjError('Boundary y control van sin atributos')
    quitados = M.set_atributos(doc, c, a['atributos'])
    return escribir(doc, a, {'quitados': quitados})


@tool('mdj_asociacion_crear', 'Crea una asociacion entre dos clases o actores, con multiplicidades, roles y navegabilidad '
      '("hacia" = flecha al segundo, "ambos", "ninguno", "desde"). Si se da diagrama, tambien la dibuja entre sus vistas '
      'con los puntos intermedios indicados.',
      obj({'archivo': ARCHIVO, 'desde': S(), 'hacia': S(), 'mult_desde': S(), 'mult_hacia': S(), 'rol_desde': S(),
           'rol_hacia': S(), 'navegable': S(enum=['hacia', 'ambos', 'ninguno', 'desde']), 'duenio': S(),
           'diagrama': S(), 'puntos': PUNTOS, 'salida': SALIDA, 'forzar': FORZAR}, ['archivo', 'desde', 'hacia']),
      rw('Crear asociacion'))
def t_asoc_crear(a):
    doc = M.Doc(a['archivo'])
    x, y = doc.find(a['desde']), doc.find(a['hacia'])
    ka, kb = doc.kind(x), doc.kind(y)
    avisos = []
    if {ka, kb} == {'boundary', 'entity'} or ka == kb == 'boundary' or {ka, kb} == {'control', 'actor'}:
        avisos.append(f'Ojo: {ka}--{kb} no es valido en OOSE')
    du = doc.find(a['duenio']) if a.get('duenio') else x
    asoc = M.asociacion_crear(doc, x, y, a.get('mult_desde', ''), a.get('mult_hacia', ''), a.get('rol_desde', ''),
                              a.get('rol_hacia', ''), a.get('navegable') or 'hacia', du)
    extra = {'asociacion': asoc['_id'], 'avisos': avisos}
    if a.get('diagrama'):
        dg = doc.diagram(a['diagrama'])
        av = M.vista_asociacion(doc, dg, asoc, doc.view_in(dg, x['_id']), doc.view_in(dg, y['_id']), a.get('puntos') or ())
        extra.update({'vista': av['_id'], 'puntos': av['points']})
    return escribir(doc, a, extra)


@tool('mdj_asociacion_editar', 'Cambia multiplicidad, rol, navegabilidad o la clase de un extremo (1 o 2) de una asociacion '
      'existente, y actualiza las etiquetas en sus vistas. Cadena vacia borra la multiplicidad o el rol.',
      obj({'archivo': ARCHIVO, 'asociacion': S(description='id de la asociacion'), 'extremo': N(enum=[1, 2]),
           'mult': S(), 'rol': S(), 'navegable': B(), 'clase': S(description='mover el extremo a esta clase'),
           'duenio': S(description='mover la asociacion a este dueno'), 'salida': SALIDA, 'forzar': FORZAR},
          ['archivo', 'asociacion', 'extremo']), rw('Editar asociacion'))
def t_asoc_editar(a):
    doc = M.Doc(a['archivo'])
    asoc = doc.get(a['asociacion'])
    if asoc['_type'] != 'UMLAssociation':
        raise M.MdjError('Ese id no es una asociacion')
    quitadas = M.asociacion_editar(doc, asoc, int(a['extremo']), a.get('mult'), a.get('rol'), a.get('navegable'),
                                   doc.find(a['clase']) if a.get('clase') else None)
    if a.get('duenio'):
        nuevo = doc.find(a['duenio'])
        viejo = doc.get(doc.parent[asoc['_id']])
        viejo['ownedElements'] = [e for e in viejo.get('ownedElements', []) if e['_id'] != asoc['_id']]
        if not viejo['ownedElements']:
            del viejo['ownedElements']
        nuevo.setdefault('ownedElements', []).append(asoc)
        asoc['_parent'] = M.ref(nuevo['_id'])
        doc.reindex()
    return escribir(doc, a, {'vistas_quitadas_en': quitadas} if quitadas else None)


@tool('mdj_borrar', 'Borra un elemento con todo lo que contiene, las relaciones que lo tocan y todas sus vistas en todos los '
      'diagramas (asi no quedan relaciones fantasma).',
      obj({'archivo': ARCHIVO, 'elemento': S(), 'salida': SALIDA, 'forzar': FORZAR}, ['archivo', 'elemento']),
      rw('Borrar', destructive=True))
def t_borrar(a):
    doc = M.Doc(a['archivo'])
    el = doc.find(a['elemento'])
    info = M.borrar(doc, el)
    return escribir(doc, a, info)


@tool('mdj_vista_agregar', 'Dibuja una clase o actor que ya existe en un diagrama de clases, en notacion de iconos. Copia el '
      'estilo de otra vista del mismo estereotipo si la hay.',
      obj({'archivo': ARCHIVO, 'diagrama': S(), 'elemento': S(), 'x': N(), 'y': N(), 'ancho': N(), 'alto': N(),
           'salida': SALIDA, 'forzar': FORZAR}, ['archivo', 'diagrama', 'elemento', 'x', 'y']), rw('Agregar vista'))
def t_vista_agregar(a):
    doc = M.Doc(a['archivo'])
    dg = doc.diagram(a['diagrama'])
    el = doc.find(a['elemento'])
    if doc.views_of(el['_id'], dg):
        raise M.MdjError(f'{el.get("name")} ya tiene vista en {dg.get("name")}')
    v = M.vista_nueva(doc, dg, el, a['x'], a['y'], a.get('ancho'), a.get('alto'))
    return escribir(doc, a, {'vista': v['_id']})


@tool('mdj_vista_mover', 'Mueve y/o cambia el tamano de la vista de un elemento (o de una vista por su id) dentro de un '
      'diagrama. Las lineas se reacomodan solas en StarUML; si tienen puntos intermedios, revisalas con mdj_linea_ruta.',
      obj({'archivo': ARCHIVO, 'diagrama': S(), 'elemento': S(description='id de vista, id o nombre del elemento'),
           'x': N(), 'y': N(), 'ancho': N(), 'alto': N(), 'salida': SALIDA, 'forzar': FORZAR},
          ['archivo', 'diagrama', 'elemento']), rw('Mover vista'))
def t_vista_mover(a):
    doc = M.Doc(a['archivo'])
    dg = doc.diagram(a['diagrama'])
    v = doc.view_in(dg, a['elemento'])
    M.mover_vista(v, a.get('x'), a.get('y'), a.get('ancho'), a.get('alto'))
    m = v.get('model')
    if isinstance(m, dict) and doc.ids.get(m['$ref']) and doc.kind(doc.ids[m['$ref']]) == 'entity':
        M.rehacer_atributos_vista(doc, v, doc.ids[m['$ref']])
    return escribir(doc, a, {'vista': v['_id'], 'x': v['left'], 'y': v['top'], 'ancho': v['width'], 'alto': v['height']})


@tool('mdj_linea_ruta', 'Pone los puntos intermedios de una linea (vista de asociacion u otra) y calcula sus extremos igual que '
      'StarUML. Para tramos rectos, el primer/ultimo punto intermedio debe alinearse con el centro de su caja.',
      obj({'archivo': ARCHIVO, 'diagrama': S(), 'linea': S(description='id de la vista de la linea o id del modelo'),
           'puntos': PUNTOS, 'salida': SALIDA, 'forzar': FORZAR}, ['archivo', 'diagrama', 'linea']), rw('Ruta de linea'))
def t_linea_ruta(a):
    doc = M.Doc(a['archivo'])
    dg = doc.diagram(a['diagrama'])
    v = [x for x in dg['ownedViews'] if x['_id'] == a['linea'] or x.get('model', {}).get('$ref') == a['linea']]
    if not v:
        raise M.MdjError('No encontre esa linea en el diagrama')
    pts = M.linea_ruta(doc, dg, v[0], a.get('puntos') or ())
    return escribir(doc, a, {'puntos': pts})


@tool('mdj_linea_etiqueta', 'Mueve una etiqueta de una linea (multiplicidad, rol o nombre) cambiando su alpha (angulo en '
      'radianes respecto a la linea) y distance, sin tocar los puntos de la linea. Util cuando la etiqueta cae sobre la linea.',
      obj({'archivo': ARCHIVO, 'linea': S(description='id de la vista de la linea'),
           'etiqueta': S(enum=['tailMultiplicityLabel', 'headMultiplicityLabel', 'tailRoleNameLabel', 'headRoleNameLabel', 'nameLabel']),
           'alpha': N(), 'distancia': N(), 'salida': SALIDA, 'forzar': FORZAR}, ['archivo', 'linea', 'etiqueta']),
      rw('Mover etiqueta'))
def t_linea_etiqueta(a):
    doc = M.Doc(a['archivo'])
    v = doc.get(a['linea'])
    if a['etiqueta'] not in v:
        raise M.MdjError('Esa linea no tiene esa etiqueta')
    l = doc.get(v[a['etiqueta']]['$ref'])
    if a.get('alpha') is not None:
        l['alpha'] = a['alpha']
    if a.get('distancia') is not None:
        l['distance'] = a['distancia']
    return escribir(doc, a, {'alpha': l.get('alpha'), 'distance': l.get('distance')})


@tool('mdj_nota', 'Crea una nota en un diagrama o edita una existente (vista). Si no se da alto, se calcula con el texto '
      '(cada renglon de Arial 11 ocupa 11 px).',
      obj({'archivo': ARCHIVO, 'diagrama': S(), 'texto': S(), 'x': N(), 'y': N(), 'ancho': N(), 'alto': N(),
           'vista': S(description='id de una nota existente para editarla'), 'salida': SALIDA, 'forzar': FORZAR},
          ['archivo', 'diagrama', 'texto', 'x', 'y', 'ancho']), rw('Nota'))
def t_nota(a):
    doc = M.Doc(a['archivo'])
    dg = doc.diagram(a['diagrama'])
    nv = M.nota(doc, dg, a['texto'], a['x'], a['y'], a['ancho'], a.get('alto'), a.get('vista'))
    return escribir(doc, a, {'vista': nv['_id'], 'alto': nv['height']})


@tool('mdj_secuencia_generar', 'Rehace por completo un diagrama de secuencia a partir de la lista de lifelines y mensajes, '
      'con las reglas de trabajo: vistas completas, espaciado 29-36 / 50-56 / extra entre flujos, activaciones con pila de '
      'llamadas, separacion de lifelines segun el ancho de las etiquetas y ninguna etiqueta sobre activaciones. Reusa roles '
      'y lifelines existentes del mismo tipo y conserva el marco.',
      obj({'archivo': ARCHIVO, 'diagrama': S(),
           'lifelines': {'type': 'array', 'description': 'En orden de izquierda a derecha',
                         'items': obj({'clave': S(), 'tipo': S(description='Nombre o id de la clase/actor')}, ['clave', 'tipo'])},
           'mensajes': {'type': 'array', 'items': obj({'de': S(), 'a': S(), 'nombre': S(), 'reply': B(),
                                                       'flujo': S(description='Etiqueta del flujo (F1, F2...): al cambiar se deja espacio extra')},
                                                      ['de', 'a', 'nombre'])},
           'opciones': {'type': 'object', 'description': 'y_inicio, espaciado [a,b], espaciado_izq_der [a,b], extra_flujo [a,b], '
                                                         'semilla, margen_etiqueta, separacion_minima'},
           'salida': SALIDA, 'forzar': FORZAR}, ['archivo', 'diagrama', 'lifelines', 'mensajes']), rw('Generar secuencia', True))
def t_sec_generar(a):
    doc = M.Doc(a['archivo'])
    info = M.generar_secuencia(doc, a['diagrama'], a['lifelines'], a['mensajes'], a.get('opciones'))
    res = escribir(doc, a, info)
    res['oose'] = M.reglas_oose(doc)
    return res


# ---------------------------------------------------------------------------
# Revision de argumentos contra el esquema
# ---------------------------------------------------------------------------

_TIPOS = {'string': lambda v: isinstance(v, str),
          'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and (isinstance(v, int) or math.isfinite(v)),
          'boolean': lambda v: isinstance(v, bool),
          'array': lambda v: isinstance(v, list),
          'object': lambda v: isinstance(v, dict)}


def revisar_args(schema, args, ruta='argumentos'):
    if not isinstance(args, dict):
        return f'{ruta} debe ser un objeto'
    props = schema.get('properties', {})
    for r in schema.get('required', []):
        if r not in args or args[r] is None:
            return f'Falta el argumento "{r}"'
    if schema.get('additionalProperties') is False:
        extra = [k for k in args if k not in props]
        if extra:
            return f'Argumentos que no existen: {extra}. Validos: {list(props)}'
    for k, v in args.items():
        sc = props.get(k)
        if not sc or v is None:
            continue
        t = sc.get('type')
        if t and not _TIPOS[t](v):
            return f'"{k}" debe ser {t}'
        if 'enum' in sc and v not in sc['enum']:
            return f'"{k}" debe ser uno de {sc["enum"]}'
        if t == 'array' and 'items' in sc:
            it = sc['items']
            for i, x in enumerate(v):
                if it.get('type') == 'object':
                    e = revisar_args(it, x, f'{k}[{i}]')
                    if e:
                        return f'{k}[{i}]: {e}'
                elif it.get('type') and not _TIPOS[it['type']](x):
                    return f'{k}[{i}] debe ser {it["type"]}'
                elif it.get('type') == 'array' and 'items' in it:
                    if any(not _TIPOS[it['items'].get('type', 'number')](y) for y in x) or \
                            ('minItems' in it and len(x) < it['minItems']) or ('maxItems' in it and len(x) > it['maxItems']):
                        return f'{k}[{i}] no tiene la forma esperada'
    return None


# ---------------------------------------------------------------------------
# JSON-RPC por stdio
# ---------------------------------------------------------------------------

def send(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def handle(msg):
    mid = msg.get('id')
    method = msg.get('method')
    if method is None:
        return  # respuesta a algo que no pedimos
    try:
        if method == 'initialize':
            pv = (msg.get('params') or {}).get('protocolVersion')
            result = {'protocolVersion': pv if pv in PROTOCOLOS else PROTOCOLOS[0],
                      'capabilities': {'tools': {'listChanged': False}},
                      'serverInfo': {'name': 'staruml', 'title': 'StarUML (.mdj)', 'version': VERSION},
                      'instructions': INSTRUCCIONES}
        elif method == 'ping':
            result = {}
        elif method == 'tools/list':
            result = {'tools': [{k: t[k] for k in ('name', 'description', 'inputSchema', 'annotations')} for t in TOOLS]}
        elif method == 'tools/call':
            p = msg.get('params') or {}
            t = next((t for t in TOOLS if t['name'] == p.get('name')), None)
            if t is None:
                if mid is not None:
                    send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': f'Herramienta desconocida: {p.get("name")}'}})
                return
            args = p.get('arguments') or {}
            problema = revisar_args(t['inputSchema'], args)
            if problema:
                send({'jsonrpc': '2.0', 'id': mid, 'result': {'content': [{'type': 'text', 'text': f'Error: {problema}'}], 'isError': True}})
                return
            try:
                out = t['fn'](args)
                if isinstance(out, dict) and '__content__' in out:
                    result = {'content': out['__content__'], 'isError': False}
                else:
                    text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, indent=1)
                    result = {'content': [{'type': 'text', 'text': text}], 'isError': False}
            except M.MdjError as e:
                result = {'content': [{'type': 'text', 'text': f'Error: {e}'}], 'isError': True}
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                result = {'content': [{'type': 'text', 'text': f'Error inesperado: {type(e).__name__}: {e}'}], 'isError': True}
        elif method.startswith('notifications/'):
            return
        elif method in ('resources/list', 'prompts/list'):
            result = {'resources': []} if method == 'resources/list' else {'prompts': []}
        else:
            if mid is not None:
                send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'Metodo no soportado: {method}'}})
            return
        if mid is not None:
            send({'jsonrpc': '2.0', 'id': mid, 'result': result})
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        if mid is not None:
            send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32603, 'message': str(e)}})


def _constante_no_json(c):
    raise ValueError(f'{c} no es JSON valido')


def main():
    # MCP habla UTF-8. Sin esto, en Windows Python usa la pagina de codigos del sistema (cp1252) en las tuberias:
    # los acentos llegan como mojibake y se guardan asi en el .mdj
    if hasattr(sys.stdin, 'reconfigure'):  # no existe si stdin fue reemplazado (p. ej. en pruebas)
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8', newline='\n')
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            # NaN e Infinity no son JSON: si pasaran, terminarian escritos en el .mdj y StarUML ya no lo abriria
            msg = json.loads(line, parse_constant=_constante_no_json)
        except ValueError:
            send({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'JSON invalido'}})
            continue
        for m in (msg if isinstance(msg, list) else [msg]):
            if isinstance(m, dict):
                handle(m)


if __name__ == '__main__':
    main()
