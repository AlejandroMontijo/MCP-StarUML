# Motor generico para todos los diagramas y simbolos de StarUML (UML 2.5 y las extensiones: BPMN, SysML, C4, ERD,
# flowchart, DFD, wireframe, mindmap, AWS y GCP). Se apoya en dos tablas que salen del StarUML instalado:
#  - datos/metamodelo.json (herramientas/extraer_metamodelo.py): tipos, herencia, atributos, vistas por diagrama y
#    la paleta de cada diagrama.
#  - plantillas_vistas.json (herramientas/generar_referencia.py + extraer_plantillas.py): lo que StarUML crea al dibujar
#    cada simbolo de cada paleta y al crear cada tipo de diagrama, con los ids cambiados por marcadores.
# Dibujar un simbolo es instanciar su plantilla: ids nuevos, marcadores resueltos (@dueno, @diagrama, @cola, @cabeza),
# geometria movida al lugar pedido y el nombre puesto. Asi el archivo queda como si el simbolo se hubiera dibujado en
# StarUML, y Doc.save() sigue rechazando cualquier cambio que deje ids o referencias rotas.
import copy
import json
import math
import os
import re
import unicodedata

from . import mdj as M
from .mdj import MdjError, ref

HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE = {}

# nombres cortos de diagrama (los tres primeros los resuelve mdj.crear_diagrama como siempre)
ALIAS_DIAGRAMA = {
    'clases': 'UMLClassDiagram', 'casos_de_uso': 'UMLUseCaseDiagram', 'secuencia': 'UMLSequenceDiagram',
    'paquetes': 'UMLPackageDiagram', 'objetos': 'UMLObjectDiagram', 'estructura_compuesta': 'UMLCompositeStructureDiagram',
    'componentes': 'UMLComponentDiagram', 'despliegue': 'UMLDeploymentDiagram', 'comunicacion': 'UMLCommunicationDiagram',
    'tiempos': 'UMLTimingDiagram', 'vista_general_interaccion': 'UMLInteractionOverviewDiagram',
    'estados': 'UMLStatechartDiagram', 'actividades': 'UMLActivityDiagram', 'flujo_informacion': 'UMLInformationFlowDiagram',
    'perfil': 'UMLProfileDiagram', 'erd': 'ERDDiagram', 'flowchart': 'FCFlowchartDiagram', 'dfd': 'DFDDiagram',
    'bpmn': 'BPMNDiagram', 'c4': 'C4Diagram', 'wireframe': 'WFWireframeDiagram', 'mindmap': 'MMMindmapDiagram',
    'aws': 'AWSDiagram', 'gcp': 'GCPDiagram', 'sysml_requisitos': 'SysMLRequirementDiagram',
    'sysml_bloques': 'SysMLBlockDefinitionDiagram', 'sysml_bloque_interno': 'SysMLInternalBlockDiagram',
    'sysml_parametrico': 'SysMLParametricDiagram',
}


# ---------------------------------------------------------------------------
# Tablas
# ---------------------------------------------------------------------------

def _tabla(nombre):
    if nombre not in _CACHE:
        ruta = os.path.join(HERE, 'datos', nombre)
        if not os.path.exists(ruta):
            raise MdjError(f'Falta {nombre}; se genera con los scripts de herramientas/')
        with open(ruta, encoding='utf-8') as f:
            _CACHE[nombre] = json.load(f)
    return _CACHE[nombre]


def metamodelo():
    return _tabla('metamodelo.json')


def plantillas():
    return _tabla('plantillas_vistas.json')


def tipo(t):
    return metamodelo()['tipos'].get(t)


def ancestros(t):
    while t:
        yield t
        t = (tipo(t) or {}).get('super')


def es_subtipo(t, base):
    return base in ancestros(t)


def es_abstracto(t):
    """El metamodelo de StarUML no marca los tipos abstractos: lo es el que tiene subtipos, no tiene vista propia y
    StarUML nunca crea en ninguna plantilla (UMLClassifier, UMLModelElement...)."""
    if 'concretos' not in _CACHE:
        usados = set()

        def walk(o):
            if isinstance(o, dict):
                if isinstance(o.get('_type'), str):
                    usados.add(o['_type'])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        pl = plantillas()
        walk(pl['plantillas'])
        walk(pl.get('diagramas', {}))
        con_hijos = {d.get('super') for d in metamodelo()['tipos'].values()}
        _CACHE['concretos'] = usados
        _CACHE['con_hijos'] = con_hijos
    info = tipo(t) or {}
    return t in _CACHE['con_hijos'] and not info.get('view') and t not in _CACHE['concretos']


def es_linea(t):
    return es_subtipo(t, 'EdgeView')


def atributos(t):
    """Atributos del tipo y de sus ancestros, del propio al mas general."""
    vistos, res = set(), []
    for a in ancestros(t):
        for at in (tipo(a) or {}).get('attributes', []):
            if at['name'] not in vistos:
                vistos.add(at['name'])
                res.append(at)
    return res


def atributo(t, nombre):
    return next((a for a in atributos(t) if a['name'] == nombre), None)


def tipo_diagrama(nombre):
    """'despliegue', 'UMLDeploymentDiagram' o 'DeploymentDiagram' -> 'UMLDeploymentDiagram'."""
    if nombre in ALIAS_DIAGRAMA:
        return ALIAS_DIAGRAMA[nombre]
    t = metamodelo()['tipos']
    for c in (nombre, 'UML' + nombre, nombre + 'Diagram', 'UML' + nombre + 'Diagram'):
        if c in t and es_subtipo(c, 'Diagram') and not t[c].get('abstract'):
            return c
    raise MdjError(f'Tipo de diagrama desconocido: {nombre}. Validos: {", ".join(sorted(ALIAS_DIAGRAMA))} '
                   f'o el tipo de StarUML (p. ej. UMLDeploymentDiagram); mdj_catalogo los lista')


def _clave(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', s)


def plantilla_simbolo(tipo_dg, simbolo):
    """Plantilla de un simbolo de la paleta del diagrama: por etiqueta ('Node'), por tipo ('UMLNode') o 'Etiqueta|tipo'."""
    pl = plantillas()['plantillas'].get(tipo_dg, {})
    if simbolo in pl:
        return simbolo, pl[simbolo]
    k = _clave(simbolo)
    hits = [c for c in pl if _clave(c.split('|')[0]) == k] or [c for c in pl if _clave(c.split('|')[1]) == k]
    if len(hits) == 1:
        return hits[0], pl[hits[0]]
    if len(hits) > 1:
        raise MdjError(f'"{simbolo}" es ambiguo en {tipo_dg}: {", ".join(hits)}')
    nd = [o for o in plantillas().get('no_dibujables', []) if o['diagrama'] == tipo_dg
          and _clave(simbolo) in (_clave(o['simbolo'].split('|')[0]), _clave(o['simbolo'].split('|')[1]))]
    if nd:
        raise MdjError(f'{nd[0]["simbolo"]} no tiene plantilla en {tipo_dg}: {nd[0]["motivo"]}')
    raise MdjError(f'{tipo_dg} no tiene el simbolo "{simbolo}". Su paleta: ' + ', '.join(c.split('|')[0] for c in pl))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

def catalogo(diagrama=None):
    """Sin diagrama: los tipos de diagrama con su origen y cuantos simbolos tienen. Con diagrama: su paleta."""
    pal = metamodelo().get('paletas', {})
    pl = plantillas()
    inv = {v: k for k, v in ALIAS_DIAGRAMA.items()}
    if not diagrama:
        res = []
        for t in sorted(pal):
            res.append({'tipo': t, 'alias': inv.get(t), 'origen': (tipo(t) or {}).get('origen'),
                        'simbolos': len(pl['plantillas'].get(t, {})), 'se_puede_crear': t in pl.get('diagramas', {})})
        return {'staruml': metamodelo().get('staruml'), 'diagramas': res}
    t = tipo_diagrama(diagrama)
    simbolos = []
    for c, p in pl['plantillas'].get(t, {}).items():
        label, ident = c.split('|')
        e = {'simbolo': label, 'tipo': ident, 'forma': p['forma'], 'vista': p['vista']}
        if p['forma'] == 'line':
            e['conecta'] = [p.get('cola'), p.get('cabeza')]
        elif p.get('cabeza'):
            e['va_sobre'] = p['cabeza']
        simbolos.append(e)
    nd = [{'simbolo': o['simbolo'].split('|')[0], 'motivo': o['motivo']} for o in pl.get('no_dibujables', [])
          if o['diagrama'] == t]
    comunes = [{'simbolo': 'Note', 'tipo': 'UMLNoteView', 'forma': 'node', 'vista': 'UMLNoteView',
                'nota': 'paleta comun: va en cualquier diagrama; nombre = su texto'},
               {'simbolo': 'Note Link', 'tipo': 'UMLNoteLinkView', 'forma': 'line', 'vista': 'UMLNoteLinkView',
                'conecta': ['UMLNoteView', 'View'], 'nota': 'paleta comun: de una nota a lo que comenta'}]
    return {'tipo': t, 'alias': inv.get(t), 'simbolos': simbolos, 'comunes': comunes, 'sin_plantilla': nd}


# ---------------------------------------------------------------------------
# Instanciar plantillas
# ---------------------------------------------------------------------------

def _resolver_externo(doc, info, rid):
    if rid in doc.ids and doc.ids[rid] is not None:
        return rid
    if info and info.get('tipo'):
        c = [o for o in doc.ids.values() if o and o.get('_type') == info['tipo'] and o.get('name') == info.get('nombre')]
        if len(c) == 1:
            return c[0]['_id']
    return None


def _desplazar(o, dx, dy):
    """Mueve toda la geometria (cajas, subvistas y puntos de lineas)."""
    if isinstance(o, dict):
        for k in ('left', 'top'):
            if isinstance(o.get(k), (int, float)):
                o[k] = round(o[k] + (dx if k == 'left' else dy), 2)
        if isinstance(o.get('points'), str) and o['points']:
            pts = []
            for p in o['points'].split(';'):
                x, y = p.split(':')
                pts.append(f'{round(float(x) + dx)}:{round(float(y) + dy)}')
            o['points'] = ';'.join(pts)
        for v in o.values():
            _desplazar(v, dx, dy)
    elif isinstance(o, list):
        for v in o:
            _desplazar(v, dx, dy)


def cadena(doc, inicio):
    """@dueno = inicio y @dueno2, @dueno3... sus ancestros, como los guarda extraer_plantillas.py."""
    res, n, i = {}, 1, inicio
    while i:
        res['@dueno' if n == 1 else f'@dueno{n}'] = i
        n, i = n + 1, doc.parent.get(i)
    return res


def _seguir(doc, base, pasos):
    """Sigue una ruta desde un elemento: 'campo' 'indice' baja a un hijo, '>campo' sigue una referencia y '..' sube
    al padre (@dueno/regions/0 -> la primera region del dueno; @cola/>tail/>model -> el elemento de donde sale la
    linea sobre la que va el simbolo)."""
    o = doc.get(base)
    while pasos:
        paso, pasos = pasos[0], pasos[1:]
        if paso == '..':
            o = doc.get(doc.parent[o['_id']])
        elif paso.startswith('>'):
            r = o.get(paso[1:])
            if not (isinstance(r, dict) and r.get('$ref') in doc.ids):
                raise MdjError(f'{o.get("name") or o["_type"]} no tiene {paso[1:]}')
            o = doc.get(r['$ref'])
        else:
            v = o.get(paso)
            if isinstance(v, list):
                if not pasos or not pasos[0].isdigit() or int(pasos[0]) >= len(v):
                    raise MdjError(f'{o.get("name") or o["_type"]} no tiene {paso}[{pasos[0] if pasos else "?"}]')
                o, pasos = v[int(pasos[0])], pasos[1:]
            elif isinstance(v, dict):
                o = v
            else:
                raise MdjError(f'{o.get("name") or o["_type"]} no tiene {paso}')
    return o['_id']


def instanciar(doc, p, marcadores, dx=0, dy=0):
    """Copia los objetos de la plantilla p al documento. marcadores resuelve @dueno, @diagrama, @cola, @cabeza...
    Devuelve ({'@n': id_nuevo}, avisos)."""
    nuevos, avisos = {}, []
    externos = p.get('externos', {})

    def resolver(r):
        if r in nuevos:
            return nuevos[r]
        if r in marcadores:
            return marcadores[r]
        if '/' in r:
            return _seguir(doc, resolver(r.split('/')[0]), r.split('/')[1:])
        if r.startswith('@ext:'):
            rid = _resolver_externo(doc, externos.get(r), r[5:])
            if rid is None:
                avisos.append(f'referencia a {externos.get(r, {}).get("tipo")} "{externos.get(r, {}).get("nombre")}" '
                              f'que no esta en el archivo: se omitio')
            return rid
        raise MdjError(f'La plantilla necesita {r} y no se dio')

    def renum(o):
        if isinstance(o, dict):
            if isinstance(o.get('_id'), str) and o['_id'].startswith('@'):
                nuevos[o['_id']] = doc.new_id()
            for v in o.values():
                renum(v)
        elif isinstance(o, list):
            for v in o:
                renum(v)

    def fix(o):
        if isinstance(o, dict):
            for k in list(o):
                v = o[k]
                if k == '_id' and v in nuevos:
                    o[k] = nuevos[v]
                elif isinstance(v, dict) and set(v) == {'$ref'}:
                    rid = resolver(v['$ref'])
                    if rid is None:
                        del o[k]
                    else:
                        o[k] = ref(rid)
                elif isinstance(v, list) and v and all(isinstance(x, dict) and set(x) == {'$ref'} for x in v):
                    o[k] = [ref(r) for r in (resolver(x['$ref']) for x in v) if r]
                else:
                    fix(v)
        elif isinstance(o, list):
            for v in o:
                fix(v)

    objetos = copy.deepcopy(p['objetos'])
    for e in objetos:
        renum(e['objeto'])
    # cada objeto va en un campo que su contenedor tiene (si el diagrama esta donde StarUML no lo pondria, p. ej. un
    # diagrama de secuencia suelto en el modelo, la lifeline no tendria interaccion donde guardarse)
    tipos_nuevos = {e['objeto']['_id']: e['objeto']['_type'] for e in objetos}
    for e in objetos:
        if e['padre'].startswith('@ext:'):
            continue
        pid = resolver(e['padre'])
        pt = tipos_nuevos.get(e['padre']) or (doc.ids.get(pid) or {}).get('_type')
        if pt in metamodelo()['tipos'] and atributo(pt, e['campo']) is None:
            raise MdjError(f'{e["objeto"]["_type"]} iria en {doc.name_of(pid)} ({pt}), que no tiene el campo '
                           f'{e["campo"]}. El diagrama no esta donde StarUML lo pondria: crealo con mdj_diagrama_crear')
    for e in objetos:
        fix(e['objeto'])
        if dx or dy:
            _desplazar(e['objeto'], dx, dy)
        padre = doc.get(resolver(e['padre']))
        e['objeto']['_parent'] = ref(padre['_id'])
        if e['lista']:
            padre.setdefault(e['campo'], []).append(e['objeto'])
        else:
            padre[e['campo']] = e['objeto']
    doc.reindex()
    return nuevos, avisos


def _renombrar(doc, nuevos, p, nombre):
    """Pone el nombre al elemento principal y a las etiquetas de sus vistas que mostraban el nombre de la plantilla.
    Si es una linea que crea otro elemento con nombre por omision (la clase de una clase asociacion, el objeto de un
    objeto de enlace), ese toma el nombre: en UML son el mismo elemento y es el nombre que StarUML muestra. Si el
    elemento principal de esa linea no tiene nombre en StarUML (el enlace de la clase asociacion o del objeto de
    enlace), solo lo lleva el otro."""
    mid = nuevos.get(p.get('modelo'))
    if not mid or not nombre:
        return
    cambiar = [doc.get(mid)]
    if p['forma'] == 'line':
        otros = [doc.ids[i] for i in nuevos.values() if doc.ids.get(i) is not None and i != mid
                 and not doc.ids[i].get('_type', '').endswith('View')
                 and re.fullmatch(r'[A-Za-z]+\d+', str(doc.ids[i].get('name') or ''))
                 and (es_subtipo(doc.ids[i]['_type'], 'UMLClassifier') or es_subtipo(doc.ids[i]['_type'], 'UMLInstance'))]
        raiz = next((e['objeto'] for e in p['objetos'] if e['objeto'].get('_id') == p.get('modelo')), {})
        cambiar = otros if otros and 'name' not in raiz else cambiar + otros
    for el in cambiar:
        viejo = el.get('name')
        el['name'] = nombre
        if not viejo:
            continue
        for i in nuevos.values():
            o = doc.ids.get(i)
            if o and o.get('_type', '').endswith('View') and isinstance(o.get('text'), str) and viejo in o['text']:
                o['text'] = o['text'].replace(viejo, nombre)


# simbolos cuyo nombre StarUML no dibuja: nodos de control, pseudoestados, contencion, extremos de mensaje, marcas de
# tiempo y varios de wireframe, flowchart y BPMN (comprobado exportando cada simbolo de cada paleta con StarUML 6.3.1).
# El nombre queda solo en el modelo y dibujar lo avisa.
SIN_NOMBRE_VISIBLE = {
    'UMLInitialNode', 'UMLActivityFinalNode', 'UMLFlowFinalNode', 'UMLDecisionNode', 'UMLMergeNode', 'UMLForkNode',
    'UMLJoinNode', 'UMLInterruptibleActivityRegion', 'UMLInitialState', 'UMLFinalState', 'UMLChoice', 'UMLJunction',
    'UMLFork', 'UMLJoin', 'UMLDeepHistory', 'UMLShallowHistory', 'UMLEntryPoint', 'UMLExitPoint', 'UMLTerminate',
    'UMLContainment', 'UMLEndpoint', 'UMLGate', 'UMLTimeSegment', 'UMLTimeTick', 'BPMNGroup', 'BPMNMessageLink',
    'BPMNAssociation', 'BPMNConversationLink', 'BPMNDataAssociation',
    'FCCollate', 'FCOr', 'FCSort', 'FCSummingJunction', 'MMEdge', 'WFAvatar', 'WFFrame', 'WFDesktopFrame',
    'WFMobileFrame', 'WFWebFrame', 'WFImage', 'WFPanel', 'WFSeparator', 'WFSlider', 'WFSwitch', 'WFTabList'}


def _sin_llaves(texto):
    t = str(texto).strip()
    return t[1:-1].strip() if t.startswith('{') and t.endswith('}') else t


def _interaccion_llamada(doc, nombre, excluir):
    """La interaccion con ese nombre, si hay exactamente una (fuera de las de excluir)."""
    c = [o for o in doc.ids.values() if o and o.get('_type') == 'UMLInteraction' and o.get('name') == nombre
         and o['_id'] not in excluir]
    return c[0] if len(c) == 1 else None


def _textos_nuevos(doc, nuevos, viejo, nuevo):
    """Cambia el texto de las etiquetas recien creadas (StarUML las recalcula al abrir; asi el archivo ya coincide)."""
    for i in nuevos.values():
        o = doc.ids.get(i)
        if o and o.get('_type', '').endswith('View') and isinstance(o.get('text'), str) and o['text'] == viejo:
            o['text'] = nuevo
            if o.get('visible') is False:
                o['visible'] = True


def _etiqueta_de(doc, nuevos, campo, texto):
    """Pone el texto en la etiqueta (nameLabel, descriptionLabel...) de las vistas nuevas que la tienen."""
    for i in nuevos.values():
        o = doc.ids.get(i)
        lab = doc.ids.get((o or {}).get(campo, {}).get('$ref')) if _es_ref((o or {}).get(campo)) else None
        if lab is not None:
            lab['text'] = texto
            if lab.get('visible') is False:
                lab['visible'] = True


def _quitar(doc, o):
    """Saca el objeto de la lista de su padre (por identidad: otro objeto podria ser igual)."""
    padre = doc.ids.get(doc.parent.get(o['_id']))
    for v in (padre or {}).values():
        if isinstance(v, list):
            i = next((k for k, x in enumerate(v) if x is o), None)
            if i is not None:
                del v[i]
                break


def _nombre_visible(doc, nuevos, p, clave, nombre, dg):
    """Pone el texto donde StarUML lo muestra cuando no es el nombre del elemento: el rango {min..max} de las
    restricciones de tiempo y duracion, el {invariante}, el texto de una anotacion BPMN, la descripcion de una
    relacion C4, la interaccion a la que se refiere un uso de interaccion (ref X) o la que muestra una accion de la
    vista general de interaccion. Devuelve avisos de lo que no se vera."""
    if nombre is None or nombre == '':
        return []
    etiqueta, ident = clave.split('|')
    mid = nuevos.get(p.get('modelo'))
    m = doc.ids.get(mid) if mid else None
    if p['vista'] == 'UMLFrameView' and m is None:
        mod = doc.ids.get(doc.parent.get(dg['_id'])) if p.get('modelo') == '@dueno' else None
        return [f'{etiqueta} muestra el nombre del elemento al que pertenece el diagrama'
                + (f' ({mod.get("name") or mod["_type"]})' if mod else '') + f', no "{nombre}"']
    if ident in SIN_NOMBRE_VISIBLE or m is None:
        return [f'StarUML no muestra el nombre de {etiqueta}: "{nombre}" queda solo en el modelo']
    t, avisos = m['_type'], []
    if es_subtipo(t, 'UMLIntervalConstraint'):
        texto = _sin_llaves(nombre)
        if '..' in texto:
            m['min'], m['max'] = (x.strip() for x in texto.split('..', 1))
        else:
            m['min'] = m['max'] = texto
            avisos.append(f'StarUML muestra {etiqueta} como {{min..max}}: quedo {{{texto}..{texto}}}; para un rango '
                          f'usa "a..b"')
        _textos_nuevos(doc, nuevos, '{min..max}', f'{{{m["min"]}..{m["max"]}}}')
    elif es_subtipo(t, 'UMLStateInvariant'):
        m['invariant'] = _sin_llaves(nombre)
        _textos_nuevos(doc, nuevos, '{}', f'{{{m["invariant"]}}}')
    elif es_subtipo(t, 'BPMNTextAnnotation'):
        m['text'] = nombre
    elif es_subtipo(t, 'C4Relationship'):
        m['description'] = nombre
        _etiqueta_de(doc, nuevos, 'descriptionLabel', nombre)
    elif es_subtipo(t, 'UMLInteractionUse') and not _es_ref(m.get('refersTo')):
        # StarUML muestra "ref" y el nombre de la interaccion a la que se refiere: la que ya se llama asi o una nueva
        propias = {i for i in cadena(doc, dg['_id']).values()}
        inter = _interaccion_llamada(doc, nombre, propias)
        if inter is None:
            dueno = doc.ids.get(doc.parent.get(dg['_parent']['$ref'])) or doc.ids.get(dg['_parent']['$ref'])
            if dueno is None or campo_para(dueno['_type'], 'UMLInteraction') is None:
                return [f'{etiqueta} muestra el nombre de la interaccion a la que se refiere (refersTo), que no tiene']
            inter = crear_elemento(doc, 'UMLInteraction', nombre, dueno['_id'])
            avisos.append(f'se creo la interaccion "{nombre}" (vacia) para que {etiqueta} la muestre: ref {nombre}')
        m['refersTo'] = ref(inter['_id'])
        _etiqueta_de(doc, nuevos, 'nameLabel', inter['name'])
    elif es_subtipo(t, 'UMLAction') and _es_ref(m.get('target')):
        # vista general de interaccion: la accion muestra la interaccion de su uso de interaccion o de su diagrama
        destino = doc.ids.get(m['target']['$ref'])
        nueva = None
        if destino is not None and es_subtipo(destino['_type'], 'UMLInteractionUse') and _es_ref(destino.get('refersTo')):
            nueva = doc.ids.get(destino['refersTo']['$ref'])
        elif destino is not None and es_subtipo(destino['_type'], 'Diagram'):
            nueva = doc.ids.get(doc.parent.get(destino['_id']))
        if nueva is None or nueva['_id'] not in nuevos.values():
            return avisos
        propias = set(cadena(doc, dg['_id']).values()) | {nueva['_id']}
        inter = _interaccion_llamada(doc, nombre, propias)
        sd = next((x for x in (inter or {}).get('ownedElements', []) if x.get('_type') == 'UMLSequenceDiagram'), None)
        if inter is not None and es_subtipo(destino['_type'], 'UMLInteractionUse'):
            destino['refersTo'] = ref(inter['_id'])
            _quitar(doc, nueva)
        elif inter is not None and sd is not None:
            m['target'] = ref(sd['_id'])
            _quitar(doc, nueva)
        else:
            nueva['name'] = nombre
            for x in nueva.get('ownedElements', []):
                if es_subtipo(x.get('_type', ''), 'Diagram'):
                    x['name'] = nombre
        _etiqueta_de(doc, nuevos, 'nameLabel', nombre)
        doc.reindex()
    return avisos


# ---------------------------------------------------------------------------
# Diagramas y simbolos
# ---------------------------------------------------------------------------

CONTENEDORES = ('UMLModel', 'UMLPackage', 'UMLSubsystem')


def _contenedor(doc, dentro_de, dueno=None):
    """(elemento, aviso) donde se crea un diagrama. Si el nombre lo comparten varios elementos (un caso de uso y un
    paquete que se llaman igual), gana el del tipo que StarUML exige para ese diagrama o, si no exige ninguno, el
    paquete o modelo; el aviso dice cual se eligio y como pedir el otro."""
    try:
        return doc.find(dentro_de), None
    except MdjError as e:
        if 'ambiguo' not in str(e):
            raise
    cands = [o for o in doc.ids.values() if o and o.get('name') == dentro_de and not o['_type'].endswith('View')]
    preferidos = [o for o in cands if dueno and dueno != 'UMLPackage' and es_subtipo(o['_type'], dueno)] or \
        [o for o in cands if o['_type'] in CONTENEDORES]
    if len(preferidos) != 1:
        opts = ', '.join(f"{c['_type']}:{c['_id']}" for c in cands[:6])
        raise MdjError(f'"{dentro_de}" es ambiguo ({opts}). Usa el id o Tipo:Nombre.')
    elegido = preferidos[0]
    otros = sorted({c['_type'] for c in cands if c is not elegido})
    return elegido, (f'"{dentro_de}" lo comparten varios elementos; se uso el {elegido["_type"]}. '
                     f'Para otro, indica Tipo:Nombre ({", ".join(t + ":" + dentro_de for t in otros)}).')


def crear_diagrama(doc, tipo_dg, nombre, dentro_de=None, por_defecto=False):
    """Cualquier diagrama de StarUML, con lo que StarUML crea junto con el (interaccion, maquina de estados, marco...)."""
    t = tipo_diagrama(tipo_dg)
    if t in ('UMLClassDiagram', 'UMLUseCaseDiagram', 'UMLSequenceDiagram'):
        alias = {v: k for k, v in ALIAS_DIAGRAMA.items()}[t]
        return M.crear_diagrama(doc, alias, nombre, dentro_de, por_defecto), []
    p = plantillas().get('diagramas', {}).get(t)
    if not p:
        raise MdjError(f'No hay plantilla para crear {t}')
    dueno = p.get('dueno')
    padre, aviso_padre = _contenedor(doc, dentro_de, dueno) if dentro_de else (M.modelo_raiz(doc), None)
    if dueno and dueno != 'UMLPackage' and not es_subtipo(padre['_type'], dueno):
        # StarUML solo admite este diagrama dentro de un elemento de cierto tipo (bloque interno -> SysMLBlock)
        padre = crear_elemento(doc, dueno, nombre, padre['_id'])
    nuevos, avisos = instanciar(doc, p, cadena(doc, padre['_id']))
    if aviso_padre:
        avisos = [aviso_padre] + list(avisos)
    dg = doc.get(nuevos[p['principal']])
    dg['name'] = nombre
    # los contenedores que StarUML crea con el diagrama (interaccion, actividad, maquina de estados...) toman su nombre
    i = dg['_parent']['$ref']
    while i in nuevos.values():
        o = doc.get(i)
        o['name'] = nombre
        i = o['_parent']['$ref']
    for v in dg.get('ownedViews', []):
        for s in [v] + v.get('subViews', []):
            if s.get('_type') == 'LabelView' and s.get('text') == p.get('nombre_diagrama'):
                s['text'] = nombre
    if por_defecto:
        for o in doc.diagrams():
            o.pop('defaultDiagram', None)
        dg['defaultDiagram'] = True
    doc.reindex()
    return dg, avisos


def _caja_libre(dg, ancho=150, alto=90):
    """Primer lugar libre a la derecha de lo dibujado (filas de 1200 px)."""
    cajas = [v for v in dg.get('ownedViews', []) if all(isinstance(v.get(k), (int, float)) for k in ('left', 'top', 'width', 'height'))
             and v.get('_type') not in ('UMLFrameView',)]
    if not cajas:
        return 40, 60
    fila = max(v['top'] for v in cajas)
    en_fila = [v for v in cajas if v['top'] >= fila - 10]
    x = max(v['left'] + v['width'] for v in en_fila) + 50
    if x + ancho > 1200:
        return 40, max(v['top'] + v['height'] for v in cajas) + 60
    return x, fila


def _vista(doc, dg, spec):
    if spec is None:
        return None
    if isinstance(spec, dict):
        spec = spec.get('$ref')
    o = doc.ids.get(spec)
    if o and o.get('_type', '').endswith('View'):
        return o
    return doc.view_in(dg, spec)


def _extremo(v):
    """Caja de un extremo de linea; si el extremo es otra linea (la de una clase asociacion), un punto en su centro."""
    if _es_caja(v):
        return v
    if v is not None and isinstance(v.get('points'), str):
        cx, cy = _centro_linea(v)
        return {'_id': v['_id'], 'left': cx, 'top': cy, 'width': 0, 'height': 0}
    return None


def _figura(v):
    """La parte dibujada de una caja sin su nombre, cuando el nombre va abajo: la bola de una interfaz o el icono de
    robustez (la franja inferior es el nombre) o el circulo de un evento (el nombre va en una etiqueta debajo).
    None si el nombre no va abajo."""
    if not _es_caja(v):
        return None
    if v.get('stereotypeDisplay') == 'icon':
        nc = next((x for x in v.get('subViews', []) if x.get('_type') == 'UMLNameCompartmentView'), None)
        alto = nc.get('height', 25) if nc and isinstance(nc.get('height'), (int, float)) else 25
        return {'_id': v['_id'], 'left': v['left'], 'top': v['top'], 'width': v['width'],
                'height': max(8, v['height'] - alto)}
    abajo = [x for x in v.get('subViews', []) if x.get('_type') == 'NodeLabelView' and x.get('visible') is not False
             and isinstance(x.get('top'), (int, float)) and x['top'] >= v['top'] + v['height'] - 2]
    return dict(v) if abajo else None


def _zona_nombre(v):
    """Rectangulo (x0, y0, x1, y1) del nombre que StarUML pone debajo de una figura (evento, compuerta, objeto de
    datos...), con el ancho del texto que lleva; None si el nombre no va abajo."""
    if not _es_caja(v) or v.get('stereotypeDisplay') == 'icon':
        return None
    labs = [x for x in v.get('subViews', []) if x.get('_type') == 'NodeLabelView' and x.get('visible') is not False
            and _es_caja(x) and x['top'] >= v['top'] + v['height'] - 2]
    if not labs:
        return None
    cx = v['left'] + v['width'] / 2
    ancho = max(M.ancho13(x['text']) if isinstance(x.get('text'), str) and x['text'] else x['width'] for x in labs)
    return (cx - ancho / 2 - 4, v['top'] + v['height'], cx + ancho / 2 + 4, max(x['top'] + x['height'] for x in labs) + 4)


def _nombre_abajo(p, nombre):
    """(ancho, alto) que ocupa el nombre de un icono que lo lleva debajo (evento o compuerta BPMN...), para
    reservarlo al acomodar; None si el simbolo no es un icono con el nombre abajo."""
    v = next((e['objeto'] for e in p['objetos'] if e['objeto'].get('_id') == p['principal']), None)
    z = _zona_nombre(v) if v is not None else None
    if z is None or (round(v['width']), round(v['height'])) != _tam_natural(p, nombre):
        return None
    return round(M.ancho13(nombre or '') + 16), round(z[3] - v['top'] - v['height'] + 6)


def _ruta_lateral(t, h, medios):
    """Como M.ruta, pero si un extremo lleva el nombre abajo y la linea le llega desde abajo, entra por un costado a
    la altura de la figura, lo bastante afuera para no tocar el nombre, y baja por ese costado hasta pasar el nombre
    (asi no lo cruza ni regresa en diagonal por debajo de la figura)."""
    medios = [tuple(m) for m in medios or ()]
    ft, fh = _figura(t), _figura(h)
    if ft is None and fh is None:
        return M.ruta(t, h, medios)
    caja_t, caja_h = ft or t, fh or h

    def en_zona(pt, zona, fig):
        x0 = min(zona[0], fig['left']) - 6 if zona else fig['left'] - 6
        x1 = max(zona[2], fig['left'] + fig['width']) + 6 if zona else fig['left'] + fig['width'] + 6
        y1 = (zona[3] if zona else fig['top'] + fig['height']) + 4
        return x0 <= pt[0] <= x1 and fig['top'] <= pt[1] <= y1

    def lateral(fig, zona, otro_pt):
        cx, cy = fig['left'] + fig['width'] / 2, fig['top'] + fig['height'] / 2
        if otro_pt[1] <= fig['top'] + fig['height']:
            return None
        sep = max(30, round((zona[2] - zona[0]) / 2 - fig['width'] / 2) + 12) if zona else 30
        lado = fig['left'] + fig['width'] + sep if otro_pt[0] >= cx else fig['left'] - sep
        return (round(lado), round(cy))
    if ft is not None:
        zona = _zona_nombre(t)
        while medios and en_zona(medios[0], zona, ft):
            medios.pop(0)
        lejos = medios[0] if medios else M.centro(h)
        m = lateral(ft, zona, lejos)
        if m and not medios and _es_caja(caja_h) and caja_h['top'] - 20 > (zona[3] if zona else m[1]) + 8:
            # el otro extremo esta mas abajo: baja por el costado y entra a el desde arriba
            y_mid = round(caja_h['top'] - 20)
            medios = [m, (m[0], y_mid), (round(caja_h['left'] + caja_h['width'] / 2), y_mid)]
        elif m:
            medios = [m, (m[0], round(lejos[1]))] + medios
    if fh is not None:
        zona = _zona_nombre(h)
        while medios and en_zona(medios[-1], zona, fh):
            medios.pop()
        lejos = medios[-1] if medios else M.centro(t)
        m = lateral(fh, zona, lejos)
        if m:
            medios = medios + ([(m[0], round(lejos[1]))] if not medios or medios[-1][0] != m[0] else []) + [m]
    return M.ruta(caja_t, caja_h, _sin_colineales(medios))


def _sin_colineales(pts):
    """Quita puntos repetidos y los intermedios de tramos en la misma recta horizontal o vertical (tambien los que
    harian ir y regresar sobre la misma linea)."""
    res = []
    for q in pts:
        q = (round(q[0]), round(q[1]))
        if res and q == res[-1]:
            continue
        if len(res) >= 2 and (res[-2][0] == res[-1][0] == q[0] or res[-2][1] == res[-1][1] == q[1]):
            res[-1] = q
            continue
        res.append(q)
    return res


def _rutear(doc, nuevos, principal, medios=()):
    """Rehace los puntos de las lineas nuevas que unen dos cajas (o una caja y otra linea), la principal con sus
    puntos intermedios."""
    for i in nuevos.values():
        o = doc.ids.get(i)
        if not o or not es_linea(o.get('_type', '')):
            continue
        t = _extremo(doc.ids.get((o.get('tail') or {}).get('$ref')))
        h = _extremo(doc.ids.get((o.get('head') or {}).get('$ref')))
        if t is not None and h is not None and (t.get('width') or h.get('width')):
            o['points'] = _ruta_lateral(t, h, medios if o is principal else ())


# palabra clave que StarUML escribe sobre cada relacion, para medir su etiqueta
PALABRA_CLAVE = {'UMLDeployment': 'deploy', 'UMLExtend': 'extend', 'UMLInclude': 'include', 'UMLTemplateBinding': 'bind',
                 'UMLManifestation': 'manifest', 'UMLInformationFlow': 'flow', 'UMLAbstraction': 'abstraction',
                 'SysMLConform': 'conform', 'SysMLExpose': 'expose', 'SysMLCopy': 'copy', 'SysMLDeriveReqt': 'deriveReqt',
                 'SysMLSatisfy': 'satisfy', 'SysMLVerify': 'verify', 'SysMLRefine': 'refine', 'SysMLTrace': 'trace',
                 # una realizacion (de interfaz o de componente) es una abstraccion, pero StarUML no le pone palabra
                 'UMLRealization': None}


def _separar_nombre(doc, v, nombre):
    """StarUML pone el nombre y el estereotipo de una linea a 15 y 30 px, perpendiculares a ella: en una linea casi
    vertical el texto queda montado encima. Ahi se alejan segun su ancho (el estereotipo, mas alla del nombre)."""
    if not isinstance(v.get('points'), str):
        return
    pts = [tuple(map(float, p.split(':'))) for p in v['points'].split(';')]
    # el tramo mas largo decide la orientacion
    dx, dy = max(((abs(b[0] - a[0]), abs(b[1] - a[1])) for a, b in zip(pts, pts[1:])), key=lambda d: d[0] + d[1],
                 default=(0, 0))
    if dy <= dx:
        return
    m = doc.ids.get((v.get('model') or {}).get('$ref')) if isinstance(v.get('model'), dict) else None
    clave = next((PALABRA_CLAVE[a] for a in ancestros(m['_type']) if a in PALABRA_CLAVE), None) if m else None
    if m and isinstance(m.get('stereotype'), dict):
        clave = doc.name_of(m['stereotype']['$ref'])
    nombre = nombre or (m.get('name') if m else None)
    ancho_n = M.ancho13('+' + nombre) if nombre else 0
    lab = doc.ids.get((v.get('nameLabel') or {}).get('$ref'))
    if lab is None and m and nombre and m.get('description') == nombre:
        # una relacion C4 muestra la descripcion en lugar del nombre
        lab = doc.ids.get((v.get('descriptionLabel') or {}).get('$ref'))
    if lab and nombre:
        lab['distance'] = max(lab.get('distance') or 15, round(ancho_n / 2 + 10))
    est = doc.ids.get((v.get('stereotypeLabel') or {}).get('$ref'))
    if est and clave:
        ancho_e = M.ancho13(f'<<{clave}>>')
        lab_alpha = (lab or {}).get('alpha')
        if lab and nombre and est.get('alpha') == lab_alpha:
            est['distance'] = round(ancho_n + ancho_e / 2 + 18)
        else:
            est['distance'] = max(est.get('distance') or 15, round(ancho_e / 2 + 10))


# ---------------------------------------------------------------------------
# Donde dibuja StarUML las etiquetas (se calcula igual que StarUML para que no queden sobre lineas, cajas u otros
# textos)
# ---------------------------------------------------------------------------

def _rect(v):
    return (v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height'])


def _centro_r(r):
    return ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)


def _junction_r(r, p):
    """Punto del borde de r en la recta de su centro hacia p (Coord.junction)."""
    return M.junction({'left': r[0], 'top': r[1], 'width': r[2] - r[0], 'height': r[3] - r[1]}, p)


def _extremo_staruml(v):
    """(rectangulo, es_linea) de un extremo como lo usa StarUML: la caja de la vista o, si el extremo es otra linea,
    el rectangulo de su tramo de en medio."""
    if _es_caja(v):
        return _rect(v), False
    if v is not None and isinstance(v.get('points'), str):
        pts = [tuple(map(float, p.split(':'))) for p in v['points'].split(';')]
        i = (len(pts) - 1) // 2
        a, b = pts[i], pts[min(i + 1, len(pts) - 1)]
        return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])), True
    return None, False


def _puntos_staruml(doc, v):
    """Puntos de una linea como quedan al abrir el archivo en StarUML (EdgeView.reducePoints y recalcOblique): se
    quitan los intermedios que caen dentro de la caja de un extremo y cada extremo va al borde de su caja, en la recta
    hacia el punto vecino (en las rectilineas y los lazos, en la direccion del vecino)."""
    pts = [tuple(map(float, p.split(':'))) for p in v['points'].split(';')]
    if len(pts) < 2:
        return pts
    t = doc.ids.get((v.get('tail') or {}).get('$ref'))
    h = doc.ids.get((v.get('head') or {}).get('$ref'))
    (rt, lt), (rh, lh) = _extremo_staruml(t), _extremo_staruml(h)

    def dentro(p, r):
        return r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]
    if rt is not None and not lt:
        i = 1
        while i < len(pts) - 1:
            if dentro(pts[i], rt):
                del pts[1:i + 1]
                i = 1
            else:
                i += 1
    if rh is not None and not lh:
        i = 1
        while i < len(pts) - 1:
            if dentro(pts[i], rh):
                del pts[i:len(pts) - 1]
            else:
                i += 1
    recto = v.get('lineStyle') in (0, 2) or (t is not None and t is h)

    def borde(r, vecino):
        r = (r[0] - 1, r[1] - 1, r[2] + 1, r[3] + 1)
        if recto and r[0] <= vecino[0] <= r[2]:
            return (vecino[0], r[1] if vecino[1] < r[1] else r[3])
        if recto and r[1] <= vecino[1] <= r[3]:
            return (r[0] if vecino[0] < r[0] else r[2], vecino[1])
        return _junction_r(r, vecino)
    if rt is not None:
        pts[0] = _centro_r(rt)
    if rh is not None:
        pts[-1] = _centro_r(rh)
    if rt is not None and not lt:
        pts[0] = borde(rt, pts[1])
    if rh is not None and not lh:
        pts[-1] = borde(rh, pts[-2])
    return [(round(x), round(y)) for x, y in pts]


def _lejos_de_linea(t, h, alpha, d):
    """Coord.getPointAwayLine de StarUML."""
    a, b = t[0] - h[0], t[1] - h[1]
    th = math.atan(abs(b) / (abs(a) + 0.000001))
    if a > 0:
        th = math.pi - th if b > 0 else th + math.pi
    elif b < 0:
        th = 2 * math.pi - th
    return math.floor(d * math.cos(th + alpha)), math.floor(-d * math.sin(th + alpha))


def _ancla(pts, posicion):
    """(p1, p2) de los que StarUML mide una etiqueta de linea: la cabeza, la cola o el centro (EP_HEAD 0, EP_MIDDLE
    1, EP_TAIL 2). En el centro, con un numero par de puntos es la mitad del tramo de en medio; con uno impar, el
    punto de en medio."""
    if posicion == 0:
        return pts[-1], pts[-2]
    if posicion == 2:
        return pts[0], pts[1]
    n = len(pts)
    i = n // 2 - (1 if n % 2 == 0 else 0)
    p1, p2 = pts[i], pts[i + 1]
    if n % 2 == 0:
        p1 = (math.floor((p1[0] + p2[0]) / 2), math.floor((p1[1] + p2[1]) / 2))
    return p1, p2


def _caja_texto(cx, cy, texto):
    w = M.ancho13(texto)
    return (cx - w / 2, cy - 7, cx + w / 2, cy + 7)


def _textos_de_linea(doc, v):
    """[(subvista de etiqueta, texto que mostrara StarUML)] del nombre y el estereotipo de una linea."""
    m = doc.ids.get((v.get('model') or {}).get('$ref')) if isinstance(v.get('model'), dict) else None
    if not m:
        return []
    res = []
    lab = doc.ids.get((v.get('nameLabel') or {}).get('$ref'))
    if lab is not None and m.get('name'):
        res.append((lab, '+' + m['name']))
    clave = next((PALABRA_CLAVE[a] for a in ancestros(m['_type']) if a in PALABRA_CLAVE), None)
    if isinstance(m.get('stereotype'), dict):
        clave = doc.name_of(m['stereotype']['$ref'])
    est = doc.ids.get((v.get('stereotypeLabel') or {}).get('$ref'))
    if est is not None and clave:
        res.append((est, f'\u00ab{clave}\u00bb'))
    return [(lab_, t) for lab_, t in res if isinstance(lab_.get('alpha'), (int, float))
            and isinstance(lab_.get('distance'), (int, float))]


# vistas que son zonas (marcos, carriles, regiones...): solo su borde estorba a un texto
_ZONAS = ('Frame', 'Fragment', 'Operand', 'InteractionUse', 'Continuation', 'Swimlane', 'Partition', 'Lane', 'Pool',
          'Group', 'Zone', 'Region', 'Timing')


def _es_zona(v):
    return any(z in v.get('_type', '') for z in _ZONAS)


# lineas que StarUML no dibuja por sus puntos (un mensaje de tiempos va de un segmento de tiempo al otro): no se sabe
# donde quedan ni ellas ni sus textos, asi que ni se acomodan ni estorban
_DIBUJO_PROPIO = ('UMLTimingMessageView',)


def _por_sus_puntos(v):
    return es_linea(v.get('_type', '')) and isinstance(v.get('points'), str) and v['_type'] not in _DIBUJO_PROPIO


def _acomodar_etiquetas(doc, dg, lineas, bordes):
    """Las etiquetas de las lineas dadas (nombre y estereotipo) y de los puertos o pines dados (su nombre) que
    StarUML pondria sobre una linea, una caja u otro texto se mueven (alpha y distance) al lugar libre mas cercano.
    Se calcula donde las dibuja StarUML: no usa left/top sino la linea (o la caja) y alpha y distance."""
    from . import programa as P
    cajas = [v for v in dg.get('ownedViews', []) if _es_caja(v) and v.get('visible') is not False]
    rects = {id(v): _rect(v) for v in cajas}
    segs = []  # (p, q, vista de la que es el borde o None si es una linea)
    for v in dg.get('ownedViews', []):
        if _por_sus_puntos(v) and v.get('visible') is not False:
            pts = _puntos_staruml(doc, v)
            segs += [(p, q, None) for p, q in zip(pts, pts[1:])]
    # una caja con otras adentro (paquete, sistema, nodo, carril...) estorba con su borde y con su nombre (arriba);
    # las demas, completas
    llenos = []
    for v in cajas:
        r = rects[id(v)]
        segs += [(p, q, v) for p, q in (((r[0], r[1]), (r[2], r[1])), ((r[2], r[1]), (r[2], r[3])),
                                         ((r[2], r[3]), (r[0], r[3])), ((r[0], r[3]), (r[0], r[1])))]
        con_algo = any(w is not v and _contiene(r, rects[id(w)]) for w in cajas)
        if con_algo and not _es_zona(v):
            llenos.append((v, (r[0], r[1], r[2], r[1] + 35)))
        elif not _es_zona(v):
            llenos.append((v, r))
        z = _zona_nombre(v)
        if z:
            llenos.append((v, z))
    textos = []
    ids_lineas = {id(v) for v in lineas}
    # los textos que no se mueven tambien estorban
    for v in dg.get('ownedViews', []):
        if _por_sus_puntos(v) and id(v) not in ids_lineas:
            pts = _puntos_staruml(doc, v)
            if len(pts) > 1:
                for lab, t in _textos_de_linea(doc, v):
                    p1, p2 = _ancla(pts, lab.get('edgePosition', 1))
                    dx, dy = _lejos_de_linea(p1, p2, lab['alpha'], lab['distance'])
                    textos.append(_caja_texto(p1[0] + dx, p1[1] + dy, t))
    ids_bordes = {id(v) for v in bordes}
    for v in cajas:
        lab = doc.ids.get((v.get('nameLabel') or {}).get('$ref'))
        m = doc.ids.get((v.get('model') or {}).get('$ref')) if isinstance(v.get('model'), dict) else None
        if id(v) not in ids_bordes and lab is not None and m and m.get('name') and lab.get('visible') is not False \
                and isinstance(lab.get('alpha'), (int, float)) and isinstance(lab.get('distance'), (int, float)) \
                and any(x in v['_type'] for x in ('PortView', 'PinView', 'ExpansionNodeView', 'ConnectionPoint')):
            cx, cy = _centro_r(rects[id(v)])
            dx, dy = _lejos_de_linea((cx, cy), (cx, cy), lab['alpha'], lab['distance'])
            textos.append(_caja_texto(cx + dx, cy + dy, m['name']))

    def choques(r, propia=None):
        e = (r[0] - 2, r[1] - 2, r[2] + 2, r[3] + 2)
        n = sum(1 for p, q, de in segs if (de is None or de is not propia) and P._cruza(p, q, e, 0))
        n += sum(1 for v, w in llenos if v is not propia and e[0] < w[2] and w[0] < e[2] and e[1] < w[3] and w[1] < e[3])
        return n + sum(1 for w in textos if e[0] < w[2] and w[0] < e[2] and e[1] < w[3] and w[1] < e[3])

    for v in bordes:
        lab = doc.ids.get((v.get('nameLabel') or {}).get('$ref'))
        m = doc.ids.get((v.get('model') or {}).get('$ref')) if isinstance(v.get('model'), dict) else None
        if lab is None or not m or not m.get('name') or not isinstance(lab.get('alpha'), (int, float)):
            continue
        cx, cy = _centro_r(rects[id(v)])
        w = M.ancho13(m['name'])
        # su caja y las que la contienen no estorban con todo su rectangulo (el nombre puede ir adentro)
        duenos = [c for c in cajas if c is v or _contiene(rects[id(c)], (cx, cy, cx, cy))]
        quitar = [x for x in llenos if x[0] in duenos and x[1] == rects[id(x[0])]]
        for x in quitar:
            llenos.remove(x)
        # de la caja donde va, solo estorba su nombre (arriba)
        nombres = [(c, (r_[0], r_[1], r_[2], r_[1] + 25)) for c, r_ in quitar if c is not v]
        llenos.extend(nombres)
        lados = [lab['alpha'], math.pi / 4, -3 * math.pi / 4, -math.pi / 4, 3 * math.pi / 4, math.pi / 2,
                 -math.pi / 2, 0, math.pi]
        cands = []
        for k, a in enumerate(lados):
            for d in ((lab['distance'], 30) if abs(math.sin(a)) > 0.5 else (round(w / 2) + 14, round(w / 2) + 24)):
                dx, dy = _lejos_de_linea((cx, cy), (cx, cy), a, d)
                r = _caja_texto(cx + dx, cy + dy, m['name'])
                cands.append((choques(r, v), k, a, d, r))
        for x in nombres:
            llenos.remove(x)
        llenos.extend(quitar)
        mejor = min(cands, key=lambda c: c[:2])
        _, _, a, d, r = mejor
        lab['alpha'], lab['distance'] = a, d
        lab['left'], lab['top'] = round(r[0], 2), round(r[1] - 0.5, 2)
        textos.append(r)
    for v in lineas:
        if not _por_sus_puntos(v):
            continue
        pts = _puntos_staruml(doc, v)
        if len(pts) < 2:
            continue
        for lab, t in _textos_de_linea(doc, v):
            pos = lab.get('edgePosition', 1)
            p1, p2 = _ancla(pts, pos)
            a0, d0 = lab['alpha'], lab['distance']
            # donde iba o del otro lado; si no, lo mas cerca de la linea: de lado, en diagonal o a lo largo
            lados = [a0, -a0] if a0 else [a0, math.pi]
            pares = [(a, d0) for a in lados] + [
                (a, d) for d in range(15, 104, 8)
                for a in lados + [math.pi / 4, -math.pi / 4, 3 * math.pi / 4, -3 * math.pi / 4, 0, math.pi]]
            cands = []
            for a, d in pares:
                dx, dy = _lejos_de_linea(p1, p2, a, d)
                r = _caja_texto(p1[0] + dx, p1[1] + dy, t)
                cands.append((choques(r), len(cands), a, d, r))
            _, _, a, d, r = min(cands, key=lambda c: c[:2])
            lab['alpha'], lab['distance'] = a, d
            textos.append(r)


def _acomodar_lo_que_crea(doc, nuevos, v):
    """Las cajas que crea una linea (la clase de una clase asociacion, el nodo de una asociacion n-aria) quedan
    donde estaban en la referencia: se ponen a un lado del centro de la linea y se rehacen sus lineas."""
    if not isinstance(v.get('points'), str):
        return
    dg_id = (v.get('_parent') or {}).get('$ref')
    cajas = [doc.ids[i] for i in nuevos.values() if doc.ids.get(i) is not None and doc.ids[i] is not v
             and _es_caja(doc.ids[i]) and (doc.ids[i].get('_parent') or {}).get('$ref') == dg_id]
    if not cajas:
        return
    cx, cy = _centro_linea(v)
    pts = [tuple(map(float, p.split(':'))) for p in v['points'].split(';')]
    vertical = abs(pts[-1][1] - pts[0][1]) > abs(pts[-1][0] - pts[0][0])
    dg = doc.ids.get(dg_id) or {}
    propias = {id(c) for c in cajas}
    otras_cajas = [o for o in dg.get('ownedViews', []) if _es_caja(o) and id(o) not in propias
                   and not o.get('_type', '').endswith('FrameView')]

    from . import programa as P
    propias_l = {id(doc.ids[i]) for i in nuevos.values() if doc.ids.get(i) is not None}
    tramos = [(a, b) for o in dg.get('ownedViews', []) if es_linea(o.get('_type', '')) and id(o) not in propias_l
              and isinstance(o.get('points'), str)
              for a, b in zip(P._puntos(o), P._puntos(o)[1:])]
    tramos += list(zip(P._puntos(v), P._puntos(v)[1:]))  # tampoco sobre su propia linea

    def choca(x, y, w, h):
        if any(P._cruza(a, b, (x, y, x + w, y + h), 8) for a, b in tramos):
            return True
        return any(x < o['left'] + o['width'] + 15 and o['left'] < x + w + 15 and
                   y < o['top'] + o['height'] + 15 and o['top'] < y + h + 15 for o in otras_cajas)
    for c in cajas:
        w, h = c['width'], c['height']
        # a un lado del centro de la linea; si ahi hay otra caja, el lugar libre mas cercano alrededor
        base = (cx + 60, cy - h / 2) if vertical else (cx - w / 2, cy + 50)
        lugares = [base] + sorted(((cx + dx, cy + dy) for dx in range(-400, 401, 40) for dy in range(-300, 301, 30)),
                                  key=lambda q: abs(q[0] + w / 2 - cx) + abs(q[1] + h / 2 - cy))
        x, y = next(((x, y) for x, y in lugares if not choca(x, y, w, h)), base)
        _desplazar(c, round(x - c['left']), round(y - c['top']))
        otras_cajas.append(c)
    # la linea principal ya tiene sus puntos: solo las demas (el enlace punteado de la clase asociacion)
    otras = {k: i for k, i in nuevos.items() if doc.ids.get(i) is not v}
    _rutear(doc, otras, None, ())


def _es_caja(v):
    return v is not None and all(isinstance(v.get(k), (int, float)) for k in ('left', 'top', 'width', 'height'))


def _ajustar(v, tipo_vista, otro=None):
    """La vista donde StarUML engancha el simbolo: la dada o, si la plantilla espera otro tipo, una subvista suya de
    ese tipo (un mensaje se engancha a la linea punteada de la lifeline, no a la caja). Si no tiene ninguna de ese
    tipo pero si del tipo del otro extremo de la plantilla, esa: la plantilla del mensaje llega a un endpoint, y entre
    dos lifelines llega a la linea punteada de la de destino (en la caja, StarUML lo corta en su borde y no muestra la
    activacion)."""
    if v is None or not tipo_vista or v['_type'] == tipo_vista:
        return v
    for t in (tipo_vista, otro):
        if not t:
            continue
        if v['_type'] == t:
            return v
        pila = list(v.get('subViews', []))
        while pila:
            s = pila.pop(0)
            if s.get('_type') == t:
                return s
            pila.extend(s.get('subViews', []))
    return v


def _todas_las_vistas(dg):
    res = []

    def walk(v):
        res.append(v)
        for s in v.get('subViews', []):
            walk(s)
    for v in dg.get('ownedViews', []):
        walk(v)
    return res


def necesita(p):
    """(usa_cola, usa_cabeza): si la plantilla apunta a la vista de origen / destino (o a la vista sobre la que va)."""
    m = _marcas([e['objeto'] for e in p['objetos']]) | {e['padre'] for e in p['objetos']}
    return bool(m & {'@cola', '@cola_m'}), bool(m & {'@cabeza', '@cabeza_m'})


# simbolos de la paleta comun de StarUML (Annotations): se dibujan en cualquier diagrama y no tienen plantilla
SIMBOLOS_COMUNES = {'note': 'Note', 'nota': 'Note', 'umlnote': 'Note', 'umlnoteview': 'Note',
                    'notelink': 'Note Link', 'enlacedenota': 'Note Link', 'umlnotelink': 'Note Link',
                    'umlnotelinkview': 'Note Link'}


def _dibujar_comun(doc, dg, comun, texto, x, y, ancho, alto, desde, hasta, medios):
    """Nota (con su texto) o enlace de nota (de la nota a lo que comenta) en cualquier diagrama."""
    if comun == 'Note':
        texto = texto or ''
        ancho = ancho or max(120, min(320, round(M.ancho13(texto) * 11 / 13) + 30))
        if x is None or y is None:
            x, y = _caja_libre(dg, ancho, alto or 60)
        v = M.nota(doc, dg, texto, x, y, ancho, alto)
    else:
        if desde is None or hasta is None:
            raise MdjError('Note Link es una linea: indica desde (la nota) y hasta (lo que comenta)')
        vc, vh = _vista(doc, dg, desde), _vista(doc, dg, hasta)
        for k, w in (('desde', vc), ('hasta', vh)):
            if w is None or not _es_caja(w):
                raise MdjError(f'Note Link: "{desde if k == "desde" else hasta}" ({k}) no esta dibujado en {dg.get("name")}')
        if 'UMLNoteView' not in (vc['_type'], vh['_type']):
            raise MdjError('Note Link une una nota con lo que comenta: desde o hasta debe ser una nota')
        if vh['_type'] == 'UMLNoteView' and vc['_type'] != 'UMLNoteView':
            vc, vh = vh, vc  # la nota siempre como cola
        v = {'_type': 'UMLNoteLinkView', '_id': doc.new_id(), '_parent': ref(dg['_id']), 'font': 'Arial;13;0',
             'parentStyle': False, 'head': ref(vh['_id']), 'tail': ref(vc['_id']), 'lineStyle': 1,
             'points': M.ruta(vc, vh, medios)}
        dg.setdefault('ownedViews', []).append(v)
    doc.reindex()
    return {'simbolo': comun, 'vista': v['_id'], 'vista_tipo': v['_type'], 'elemento': None, 'elemento_tipo': None,
            'avisos': []}


def dibujar(doc, diagrama, simbolo, nombre=None, x=None, y=None, ancho=None, alto=None, desde=None, hasta=None,
            sobre=None, medios=()):
    """Dibuja un simbolo de la paleta como lo haria StarUML: crea el elemento de modelo y su vista.
    Cajas: en (x, y) o en el primer lugar libre; 'sobre' es la vista o elemento donde va (puerto sobre componente,
    estado dentro de region, pin sobre accion, lifeline dentro del marco de tiempos...). Lineas: 'desde' y 'hasta'.
    Note (nombre = su texto) y Note Link son de la paleta comun: van en cualquier diagrama."""
    dg = doc.diagram(diagrama)
    comun = SIMBOLOS_COMUNES.get(_clave(simbolo))
    if comun and _clave(simbolo) not in {_clave(c.split('|')[0]) for c in plantillas()['plantillas'].get(dg['_type'], {})}:
        return _dibujar_comun(doc, dg, comun, nombre, x, y, ancho, alto, desde, hasta, medios)
    clave, p = plantilla_simbolo(dg['_type'], simbolo)
    y_pedida = y
    marc = dict(cadena(doc, dg['_parent']['$ref']), **{'@diagrama': dg['_id']})
    vc = vh = None
    usa_cola, usa_cabeza = necesita(p)
    etiqueta = clave.split('|')[0]
    if p['forma'] == 'line':
        # un mensaje encontrado no tiene origen y uno perdido no tiene destino: se pide solo lo que la plantilla usa
        falta = [n for n, usa, v in (('desde', usa_cola, desde), ('hasta', usa_cabeza, hasta)) if usa and v is None]
        if falta:
            raise MdjError(f'{etiqueta} es una linea: indica {" y ".join(falta)}')
        vc = _ajustar(_vista(doc, dg, desde), p.get('cola'), p.get('cabeza')) if usa_cola else None
        vh = _ajustar(_vista(doc, dg, hasta), p.get('cabeza'), p.get('cola')) if usa_cabeza else None
    elif usa_cola or usa_cabeza:
        if sobre is None:
            raise MdjError(f'{etiqueta} va sobre otra vista ({p.get("cabeza") or p.get("cola")}): indica "sobre"')
        vc = vh = _ajustar(_vista(doc, dg, sobre), p.get('cabeza') or p.get('cola'))
    for k, v in (('@cola', vc), ('@cabeza', vh)):
        if v is not None:
            marc[k] = v['_id']
            if isinstance(v.get('model'), dict):
                marc[k + '_m'] = v['model']['$ref']
    # la plantilla puede colgar elementos del modelo de la vista sobre la que se dibujo (puerto -> componente)
    x0, y0 = p['origen']
    if p['forma'] == 'line':
        # todo lo que la linea crea (clase asociacion, nodo n-ario, puntos de mensajes...) se mueve con su origen
        if _es_caja(vc) and _es_caja(vh):
            x, y = map(float, M.ruta(vc, vh, medios).split(';')[0].split(':'))
        elif _es_caja(vc) or _es_caja(vh):
            x, y = M.centro(vc if _es_caja(vc) else vh)
        else:
            x, y = x0, y0
        dx, dy = x - x0, y - y0
    else:
        if x is None or y is None:
            if vh is not None and all(isinstance(vh.get(k), (int, float)) for k in ('left', 'top', 'width', 'height')):
                x, y = vh['left'] + 20, vh['top'] + 30
            else:
                x, y = _caja_libre(dg, ancho or 150, alto or 90)
        dx, dy = x - x0, y - y0
    nuevos, avisos = instanciar(doc, p, marc, dx, dy)
    _renombrar(doc, nuevos, p, nombre)
    avisos += _nombre_visible(doc, nuevos, p, clave, nombre, dg)
    v = doc.get(nuevos[p['principal']])
    linea = v
    if p['forma'] == 'line':
        linea = doc.get(nuevos[_id_linea(p)])
        if vc is not None:
            linea['tail'] = ref(vc['_id'])
        if vh is not None:
            linea['head'] = ref(vh['_id'])
        _rutear(doc, nuevos, linea, medios)
        if v.get('_type') == 'UMLSeqMessageView' and (vc is not None or vh is not None):
            # un mensaje de secuencia es horizontal: a la altura pedida (y) o debajo del ultimo del diagrama
            _mensaje_en(doc, v, round(y_pedida) if y_pedida is not None else _debajo_de_los_mensajes(dg, v))
        _acomodar_lo_que_crea(doc, nuevos, linea)
        _separar_nombre(doc, linea, nombre if linea is v else None)
    else:
        if ancho is not None:
            v['width'] = ancho
        if alto is not None:
            v['height'] = alto
    doc.reindex()
    m = v.get('model', {}).get('$ref') if isinstance(v.get('model'), dict) else None
    r = {'simbolo': clave.split('|')[0], 'vista': v['_id'], 'vista_tipo': v['_type'], 'elemento': m,
         'elemento_tipo': doc.ids[m]['_type'] if m in doc.ids and doc.ids[m] else None, 'avisos': avisos}
    if linea is not v:
        r['linea'] = linea['_id']
    return r


def _id_linea(p):
    """Id (en la plantilla) de la linea que va de un extremo al otro. Casi siempre es la vista principal; en la clase
    asociacion y el objeto de enlace la principal es el enlace punteado de su caja a esa linea, que no se toca."""
    for e in p['objetos']:
        o = e['objeto']
        if (o.get('tail') or {}).get('$ref') == '@cola' and (o.get('head') or {}).get('$ref') == '@cabeza':
            return o['_id']
    return p['principal']


def _marcas(o):
    res = set()
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, dict) and set(v) == {'$ref'} and isinstance(v['$ref'], str) and v['$ref'].startswith('@'):
                res.add(v['$ref'])
            else:
                res |= _marcas(v)
    elif isinstance(o, list):
        for v in o:
            res |= _marcas(v)
    return res


def _ids_plantilla(o):
    res = set()
    if isinstance(o, dict):
        if isinstance(o.get('_id'), str):
            res.add(o['_id'])
        for v in o.values():
            res |= _ids_plantilla(v)
    elif isinstance(o, list):
        for v in o:
            res |= _ids_plantilla(v)
    return res


def _emparejar(t, o, mapa):
    """Empareja por campo (y por posicion en listas) los objetos de una plantilla con los de un elemento real."""
    if isinstance(t, dict) and isinstance(o, dict):
        if isinstance(t.get('_id'), str) and isinstance(o.get('_id'), str):
            mapa[t['_id']] = o['_id']
        for k, v in t.items():
            if isinstance(v, (dict, list)) and k in o and not (isinstance(v, dict) and set(v) == {'$ref'}):
                _emparejar(v, o[k], mapa)
    elif isinstance(t, list) and isinstance(o, list):
        for a, b in zip(t, o):
            _emparejar(a, b, mapa)


def _es_ref(v):
    return isinstance(v, dict) and set(v) == {'$ref'}


def extremos_de(el):
    """Elementos de los extremos de una relacion: (source, target) o (end1, end2); None si no es relacion."""
    if _es_ref(el.get('source')) or _es_ref(el.get('target')):
        return (el.get('source') or {}).get('$ref'), (el.get('target') or {}).get('$ref')
    e1, e2 = el.get('end1'), el.get('end2')
    if isinstance(e1, dict) and isinstance(e2, dict):
        return (e1.get('reference') or {}).get('$ref'), (e2.get('reference') or {}).get('$ref')
    return None


def _modelo_de_vista(doc, v):
    """Elemento que representa una vista; una subvista sin modelo (la linea punteada de una lifeline) cuenta como la
    vista que la contiene."""
    while v is not None:
        if _es_ref(v.get('model')):
            return v['model']['$ref']
        pid = doc.parent.get(v['_id'])
        v = doc.ids.get(pid) if pid and (doc.ids.get(pid) or {}).get('_type', '').endswith('View') else None
    return None


def _campo_en_padre(doc, el):
    padre = doc.ids.get(doc.parent.get(el['_id'])) or {}
    return next((k for k, v in padre.items() if v is el or (isinstance(v, list) and any(x is el for x in v))), None)


def _vista_del_modelo(doc, dg, mid, que):
    """La vista de un elemento en el diagrama, para usarla como extremo o como base de otra vista."""
    vs = [v for _, v in doc.views_of(mid, dg)]
    if not vs:
        raise MdjError(f'{doc.name_of(mid)} no esta dibujado en {dg.get("name")}: dibujalo primero (o indica {que})')
    if len(vs) > 1:
        raise MdjError(f'{doc.name_of(mid)} tiene {len(vs)} vistas en {dg.get("name")}: indica {que} con el id de una')
    return vs[0]


# lo que no distingue a un simbolo de otro del mismo tipo
_NO_DISTINGUE = {'_id', '_parent', '_type', 'name', 'ownedElements', 'documentation', 'source', 'target', 'tags'}


def _parecido(el, raiz, claves, tipos_pl, doc):
    """Que tanto se parece el elemento a lo que crea la plantilla en lo que distingue a los simbolos de un mismo tipo:
    kind, messageSort, regiones de un estado, a que apunta (target de una accion), extremos de una asociacion..."""
    s = 0
    for k in claves:
        tv, ev = raiz.get(k), el.get(k)
        if isinstance(tv, list) or isinstance(ev, list):
            tn, en = len(tv or []), len(ev or [])
            s += (1 + (tn == en)) if tn and en else (-2 if tn else (-1 if en else 0))
        elif _es_ref(tv) or _es_ref(ev):
            if _es_ref(tv) and _es_ref(ev):
                t_pl = tipos_pl.get(tv['$ref'])
                t_el = (doc.ids.get(ev['$ref']) or {}).get('_type')
                s += 1 if not t_pl or not t_el else (2 if es_subtipo(t_el, t_pl) else -3)
            else:
                s -= 2 if _es_ref(tv) else 1
        elif isinstance(tv, dict) or isinstance(ev, dict):
            for kk, vv in (tv or {}).items():
                if not kk.startswith('_') and not isinstance(vv, (dict, list)):
                    s += 1 if (ev or {}).get(kk) == vv else -1
        elif tv is not None or ev is not None:
            s += 2 if tv == ev else -2
    return s


def _tipos_plantilla(p):
    res = {}

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get('_id'), str) and isinstance(o.get('_type'), str):
                res[o['_id']] = o['_type']
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk([e['objeto'] for e in p['objetos']])
    return res


def vista_de(doc, diagrama, elemento, x=None, y=None, ancho=None, alto=None, desde=None, hasta=None, medios=()):
    """Dibuja en el diagrama un elemento que ya existe (cualquier tipo con simbolo en la paleta del diagrama):
    se usan solo las vistas de la plantilla de su tipo, apuntando al elemento existente. Entre los simbolos de su tipo
    se elige el que corresponde al elemento (Simple State o Composite State, Transition o Self Transition, Message o
    Async Message...). Una relacion se dibuja entre las vistas de sus extremos: desde y hasta son opcionales y, si se
    dan, deben ser vistas de esos extremos. Lo que va sobre otra vista (puerto, pin, invariante...) va sobre la vista
    de su dueno."""
    dg = doc.diagram(diagrama)
    el = doc.find(elemento)
    if doc.views_of(el['_id'], dg):
        raise MdjError(f'{el.get("name") or el["_type"]} ya tiene vista en {dg.get("name")}')
    nombre_el = el.get('name') or el['_type']
    ext = extremos_de(el)
    a_si_mismo = bool(ext and ext[0] and ext[0] == ext[1])
    campo_el = _campo_en_padre(doc, el)
    vistas_el = {v['_type'] for _, v in doc.views_of(el['_id'])}
    cands = []
    for orden, (clave, p) in enumerate(plantillas()['plantillas'].get(dg['_type'], {}).items()):
        raiz_e = next((e for e in p['objetos'] if e['objeto'].get('_id') == p.get('modelo')), None)
        if not raiz_e or raiz_e['objeto']['_type'] != el['_type']:
            continue
        raiz = raiz_e['objeto']
        # el elemento de la plantilla y el existente se recorren juntos: sus partes (extremos de una relacion...)
        # quedan apuntando a las del existente
        mapa = {}
        _emparejar(raiz, el, mapa)
        vistas = [e for e in p['objetos'] if es_subtipo(e['objeto']['_type'], 'View')]
        internos = set().union(*(_ids_plantilla(e['objeto']) for e in vistas)) if vistas else set()
        sueltas = {m for e in vistas for m in _marcas(e['objeto'])} - internos - set(mapa)
        sueltas = {m for m in sueltas if not m.startswith(('@diagrama', '@dueno', '@cola', '@cabeza', '@ext:'))}
        if vistas and not sueltas:
            cands.append({'clave': clave, 'p': p, 'raiz': raiz, 'padre': raiz_e['padre'], 'campo': raiz_e['campo'],
                          'mapa': mapa, 'vistas': vistas, 'orden': orden})
    if not cands:
        raise MdjError(f'{dg["_type"]} no tiene un simbolo para dibujar un {el["_type"]} existente')
    claves = set().union(*(set(c['raiz']) for c in cands)) - _NO_DISTINGUE
    viables, motivos = [], []
    for c in cands:
        p, etiqueta = c['p'], c['clave'].split('|')[0]
        uc, uh = necesita(p)
        # una referencia que el simbolo usa y el elemento no tiene (la accion de una vista general de interaccion
        # apunta a una interaccion; un estado submaquina, a su maquina)
        falta = [k for k, tv in c['raiz'].items() if k != '_parent' and _es_ref(tv) and not _es_ref(el.get(k))]
        if falta:
            motivos.append(f'{etiqueta} necesita {", ".join(falta)}')
            continue
        auto = p['forma'] != 'line' and uc and uh
        if auto != a_si_mismo:
            motivos.append(f'{etiqueta} es para relaciones de un elemento consigo mismo' if auto else
                           f'{etiqueta}: {nombre_el} va de un elemento a si mismo')
            continue
        puntos = _parecido(el, c['raiz'], claves, _tipos_plantilla(p), doc)
        puntos += 3 if c['campo'] == campo_el else 0
        puntos += 4 if p['vista'] in vistas_el else 0
        viables.append((-puntos, c['clave'].split('|')[1] != el['_type'], c['orden'], c))
    if not viables:
        raise MdjError(f'{dg["_type"]} no tiene un simbolo para {nombre_el} ({el["_type"]}): ' + '; '.join(motivos))
    c = min(viables, key=lambda t: t[:3])[3]
    clave, p, mapa = c['clave'], dict(c['p'], objetos=c['vistas']), c['mapa']
    marc = dict(cadena(doc, dg['_parent']['$ref']), **{'@diagrama': dg['_id']}, **mapa)
    uc, uh = necesita(c['p'])
    vc = vh = None
    if p['forma'] == 'line':
        for que, usa, dado, tipo_v, i in (('desde', uc, desde, p.get('cola'), 0), ('hasta', uh, hasta, p.get('cabeza'), 1)):
            if not usa:
                continue
            # el extremo que corresponde: el elemento de origen o destino; si la linea va sobre otra linea (mensaje
            # de comunicacion sobre su conector), el elemento de esa linea
            esperado = (el.get('connector') or {}).get('$ref') if tipo_v and es_linea(tipo_v) else (ext[i] if ext else None)
            if dado is not None:
                v = _vista(doc, dg, dado)
                if v is None:
                    raise MdjError(f'{que}: {dado} no esta en {dg.get("name")}')
                if esperado and _modelo_de_vista(doc, v) != esperado:
                    raise MdjError(f'{que} debe ser la vista de {doc.name_of(esperado)} en {dg.get("name")}: '
                                   f'{nombre_el} {"sale de" if i == 0 else "llega a"} {doc.name_of(esperado)}, no de '
                                   f'{doc.name_of(_modelo_de_vista(doc, v))}')
            elif esperado:
                v = _vista_del_modelo(doc, dg, esperado, que)
            else:
                raise MdjError(f'{el["_type"]} se dibuja como linea: indica {que}')
            v = _ajustar(v, tipo_v, p.get('cabeza') if i == 0 else p.get('cola'))
            if i == 0:
                vc = v
            else:
                vh = v
        dx = dy = 0
    else:
        if uc or uh:
            # va sobre la vista de su dueno (puerto sobre su componente, pin sobre su accion), del elemento al que
            # apunta (invariante sobre su lifeline) o del elemento con el que se relaciona consigo mismo
            sobre = desde if desde is not None else hasta
            if sobre is not None:
                base = _vista(doc, dg, sobre)
            else:
                mid = ext[0] if a_si_mismo else None
                if mid is None and c['padre'].startswith(('@cola_m', '@cabeza_m')):
                    mid = doc.parent.get(el['_id'])
                if mid is None:
                    mid = next((el[k]['$ref'] for k, tv in c['raiz'].items()
                                if _es_ref(tv) and tv['$ref'] in ('@cola_m', '@cabeza_m') and _es_ref(el.get(k))), None)
                if mid is not None:
                    base = _vista_del_modelo(doc, dg, mid, 'desde (la vista sobre la que va)')
                else:
                    tipo_b = p.get('cabeza') or p.get('cola')
                    bases = [v for v in _todas_las_vistas(dg) if v.get('_type') == tipo_b]
                    if len(bases) != 1:
                        raise MdjError(f'{clave.split("|")[0]} va sobre un {tipo_b}: indica desde con esa vista')
                    base = bases[0]
            vc = vh = _ajustar(base, p.get('cabeza') or p.get('cola'))
            if (x is None or y is None) and _es_caja(vh):
                x, y = vh['left'] + 20, vh['top'] + 30
        if x is None or y is None:
            x, y = _caja_libre(dg, ancho or 150, alto or 90)
        dx, dy = x - p['origen'][0], y - p['origen'][1]
    for k, v in (('@cola', vc), ('@cabeza', vh)):
        if v is not None:
            marc[k] = v['_id']
            if isinstance(v.get('model'), dict):
                marc[k + '_m'] = v['model']['$ref']
    nuevos, avisos = instanciar(doc, p, marc, dx, dy)
    v = doc.get(nuevos[p['principal']])
    viejo = p.get('nombre')
    if viejo and el.get('name'):
        for i in nuevos.values():
            o = doc.ids.get(i)
            if o and isinstance(o.get('text'), str) and viejo in o['text']:
                o['text'] = o['text'].replace(viejo, el['name'])
    if p['forma'] == 'line':
        linea = doc.get(nuevos[_id_linea(p)])
        if vc is not None:
            linea['tail'] = ref(vc['_id'])
        if vh is not None:
            linea['head'] = ref(vh['_id'])
        _rutear(doc, nuevos, linea, medios)
        if v.get('_type') == 'UMLSeqMessageView':
            # debajo del ultimo mensaje del diagrama (o a la altura pedida)
            _mensaje_en(doc, v, round(y) if y is not None else _debajo_de_los_mensajes(dg, v))
    if ancho is not None and p['forma'] != 'line':
        v['width'] = ancho
    if alto is not None and p['forma'] != 'line':
        v['height'] = alto
    doc.reindex()
    return {'simbolo': clave.split('|')[0], 'vista': v['_id'], 'vista_tipo': v['_type'], 'avisos': avisos}


# ---------------------------------------------------------------------------
# Generar un diagrama completo (cualquier tipo): acomodo por capas, anidamiento y lineas ruteadas
# ---------------------------------------------------------------------------

PAD_X, PAD_ARRIBA, PAD_ABAJO = 20, 50, 20


def _tam_natural(p, nombre):
    """Tamano para acomodar: el de la plantilla; si es una caja con texto, al menos lo que mide el nombre.
    Los iconos (eventos, pseudoestados, decisiones...) se quedan de su tamano."""
    v = next(e['objeto'] for e in p['objetos'] if e['objeto'].get('_id') == p['principal'])
    w, h = v.get('width') or 40, v.get('height') or 40
    texto = nombre or ''
    modelo = next((e['objeto'] for e in p['objetos'] if e['objeto'].get('_id') == p.get('modelo')), {})
    sub = next((e['objeto'] for e in p['objetos'] if isinstance(modelo.get('submachine'), dict)
                and e['objeto'].get('_id') == modelo['submachine'].get('$ref')), None)
    if sub and sub.get('name'):
        # un estado submaquina muestra "nombre: maquina"
        texto = f'{texto}: {sub["name"]}'
    if w >= 40 and (h >= 25 or w >= 2 * h):  # caja con texto (una tarea BPMN es ancha y baja); no un icono
        # StarUML escribe los nombres en negritas (~15% mas anchas que Arial normal)
        w = max(w, round(M.ancho13(texto) * 1.15 + 44), 120)
        h = max(h, 60)
    if v.get('_type') == 'C4PersonView':
        # StarUML dibuja la cabeza (un tercio del ancho) arriba de la caja y la alarga hasta que caben sus textos
        h = max(h, round(w / 3) + 75)
    if v.get('_type') == 'SysMLViewView':
        # debajo del nombre StarUML escribe /viewpoint y /stakeholder, y la alarga hasta 76
        h = max(h, 76)
    return round(w), round(h)


def anidar(doc, hijo_v, padre_v):
    """Mete la vista hijo dentro de la vista padre (containerView) y su elemento dentro del elemento padre, en el
    campo que el metamodelo indica (subestado en la region del estado compuesto, nodo dentro de nodo, accion en su
    particion...). Si el padre no puede contener al hijo, el anidamiento queda solo visual."""
    hijo_v['containerView'] = ref(padre_v['_id'])
    cont = padre_v.setdefault('containedViews', [])
    if not any(r.get('$ref') == hijo_v['_id'] for r in cont):
        cont.append(ref(hijo_v['_id']))
    hm, pm = (doc.ids.get((v.get('model') or {}).get('$ref')) for v in (hijo_v, padre_v))
    if not hm or not pm or hm is pm:
        return
    destino, campo = pm, None
    viejo = doc.ids[doc.parent[hm['_id']]]
    if pm.get('regions') and es_subtipo(hm['_type'], 'UMLVertex'):
        destino, campo = pm['regions'][0], 'vertices'
    else:
        # como StarUML al cambiar de contenedor: el mismo campo que tenia (nodes, attributes...) si el nuevo dueno lo
        # tiene; si no, el que le corresponde
        actual = _campo_en_padre(doc, hm)
        at = atributo(pm['_type'], actual) if actual else None
        if not (at and at['kind'] == 'objs' and es_subtipo(hm['_type'], at['type'])):
            at = campo_para(pm['_type'], hm['_type'])
        campo = at['name'] if at and at['kind'] == 'objs' else None
    if not campo or viejo is destino:
        return
    for k, v in viejo.items():
        if isinstance(v, list) and hm in v:
            v.remove(hm)
            break
    destino.setdefault(campo, []).append(hm)
    hm['_parent'] = ref(destino['_id'])
    doc.reindex()


def _invierte_capas(tipo_dg, simbolo):
    try:
        _, p = plantilla_simbolo(tipo_dg, simbolo)
    except MdjError:
        return False
    m = next((e['objeto'] for e in p['objetos'] if e['objeto'].get('_id') == p.get('modelo')), None)
    return bool(m) and es_subtipo(m['_type'], 'UMLGeneralization')


# contenedores que encapsulan: lo de adentro se comunica hacia afuera por el contenedor o por un puerto o pin suyo.
# En los demas (paquete, sujeto, carril, pool, region interrumpible, estado compuesto, nodo, marco de diagrama) cruzar
# el borde es lo normal en UML.
ENCAPSULAN = ('UMLComponent', 'UMLClass', 'UMLCollaboration', 'UMLStructuredActivityNode')


def encapsula(tipo_modelo):
    return any(es_subtipo(tipo_modelo, t) for t in ENCAPSULAN)


def _de_borde(p):
    """Puertos, pines, nodos de expansion, puntos de entrada y salida: van sobre el borde de su contenedor."""
    v = next((e['objeto'] for e in p['objetos'] if e['objeto'].get('_id') == p['principal']), {})
    return ((v.get('width') or 99) <= 30 and (v.get('height') or 99) <= 30) or \
        any(x in p['vista'] for x in ('PortView', 'PinView', 'ExpansionNodeView'))


CARRILES = ('UMLSwimlaneView', 'BPMNLaneView', 'BPMNPoolView')
CABECERA = 30  # ancho (o alto) del encabezado de un carril


def _es_carril(p):
    return p['vista'] in CARRILES


def _carril_vertical(p):
    v = next((e['objeto'] for e in p['objetos'] if e['objeto'].get('_id') == p['principal']), {})
    return v.get('isVertical', p['vista'] == 'UMLSwimlaneView')


def _capas_flujo(nodos, aristas):
    """Capa de cada nodo por el camino mas largo siguiendo el flujo; las aristas que cierran un ciclo no cuentan."""
    sucs = {n: [] for n in nodos}
    for a, b in aristas:
        if a in sucs and b in sucs and a != b:
            sucs[a].append(b)
    estado, orden, quitar = {}, [], set()

    def visitar(n):
        estado[n] = 1
        for m in sucs[n]:
            if estado.get(m) == 1:
                quitar.add((n, m))
            elif m not in estado:
                visitar(m)
        estado[n] = 2
        orden.append(n)
    for n in nodos:
        if n not in estado:
            visitar(n)
    capa = {n: 0 for n in nodos}
    for n in reversed(orden):
        for m in sucs[n]:
            if (n, m) not in quitar:
                capa[m] = max(capa[m], capa[n] + 1)
    # las fuentes (sin nada antes) bajan junto a lo que tienen despues: lineas cortas
    preds = {n for a, b in aristas if a in sucs and b in sucs and a != b for n in [b]}
    for n in nodos:
        siguientes = [m for m in sucs[n] if (n, m) not in quitar]
        if n not in preds and siguientes:
            capa[n] = max(0, min(capa[m] for m in siguientes) - 1)
    return capa


def _muestra_atributos(p):
    v = next((e['objeto'] for e in p['objetos'] if e['objeto'].get('_id') == p['principal']), {})
    return bool(v.get('attributeCompartment')) and not v.get('suppressAttributes')


def _tipo_modelo(el):
    p = el['_p']
    m = next((e['objeto'] for e in p['objetos'] if e['objeto'].get('_id') == p.get('modelo')), None)
    return m['_type'] if m else ''


def _es_lifeline(p):
    return 'Lifeline' in p['vista']


def _contiene(r, w):
    return r[0] <= w[0] and r[1] <= w[1] and w[2] <= r[2] and w[3] <= r[3]


def _encima(segs, otros):
    """Tramos horizontales o verticales que corren encima de otro (a menos de 12 px y compartiendo mas de 8 px)."""
    n = 0
    for p, q in segs:
        for a, b in otros:
            for k in (0, 1):  # k = 0: verticales (misma x); k = 1: horizontales (misma y)
                if p[k] == q[k] and a[k] == b[k] and abs(p[k] - a[k]) < 12:
                    lo, hi = sorted((p[1 - k], q[1 - k]))
                    lo2, hi2 = sorted((a[1 - k], b[1 - k]))
                    if min(hi, hi2) - max(lo, lo2) > 8:
                        n += 1
    return n


def _ruta_libre(t, h, obstaculos, otras_lineas=(), iconos=(False, False)):
    """La mejor ruta de una linea entre los rectangulos t y h que no cruce los obstaculos: recta, en L, en Z por un
    canal vertical u horizontal libre junto a lo que estorba, o saliendo por arriba o abajo y luego por un canal. Un
    extremo que es icono (actor: la caja es mas ancha que el dibujo) solo se toca por arriba o por abajo: por un
    costado la linea quedaria en el aire. Devuelve (cruces, puntos)."""
    from . import programa as P
    ct, ch = _centro_r(t), _centro_r(h)

    def fuera_x(x, r):
        return x < r[0] - 10 or x > r[2] + 10

    def fuera_y(y, r):
        return y < r[1] - 10 or y > r[3] + 10
    lo_x, lo_y = min(t[0], h[0]), min(t[1], h[1])
    hi_x, hi_y = max(t[2], h[2]), max(t[3], h[3])
    junto_x = [t, h] + [o for o in obstaculos if o[3] >= lo_y - 40 and o[1] <= hi_y + 40]
    junto_y = [t, h] + [o for o in obstaculos if o[2] >= lo_x - 40 and o[0] <= hi_x + 40]
    xs = sorted({x for o in junto_x for x in (o[0] - 25, o[0] - 40, o[2] + 25, o[2] + 40)})
    ys = sorted({y for o in junto_y for y in (o[1] - 25, o[1] - 40, o[3] + 25, o[3] + 40)})
    cands = [[]]
    if fuera_x(ct[0], h) and fuera_y(ch[1], t):
        cands.append([(ct[0], ch[1])])
    if fuera_x(ch[0], t) and fuera_y(ct[1], h):
        cands.append([(ch[0], ct[1])])
    cands += [[(x, ct[1]), (x, ch[1])] for x in xs if fuera_x(x, t) and fuera_x(x, h)]
    cands += [[(ct[0], y), (ch[0], y)] for y in ys if fuera_y(y, t) and fuera_y(y, h)]
    # si no hay: sale vertical, corre por un canal y entra horizontal (o al reves)
    xs3 = sorted({x for o in junto_x for x in (o[0] - 25, o[2] + 25)})
    ys3 = sorted({y for o in junto_y for y in (o[1] - 25, o[3] + 25)})
    tres = [[(ct[0], y), (x, y), (x, ch[1])] for y in ys3 for x in xs3 if fuera_y(y, t) and fuera_x(x, h)]
    tres += [[(x, ct[1]), (x, y), (ch[0], y)] for y in ys3 for x in xs3 if fuera_x(x, t) and fuera_y(y, h)]
    dentro_t = (t[0] + 2, t[1] + 2, t[2] - 2, t[3] - 2)
    dentro_h = (h[0] + 2, h[1] + 2, h[2] - 2, h[3] - 2)

    def de_costado(p, r):
        return abs(p[0] - r[0]) < 1 or abs(p[0] - r[2]) < 1
    mejor = None
    for grupo in (cands, tres):
        for medios in grupo:
            pts = [_junction_r(t, medios[0] if medios else ch)] + medios + \
                [_junction_r(h, medios[-1] if medios else ct)]
            if (iconos[0] and de_costado(pts[0], t)) or (iconos[1] and de_costado(pts[-1], h)):
                continue
            pts = [(round(x), round(y)) for x, y in pts]
            tramos = list(zip(pts, pts[1:]))
            # a menos de 8 px de una caja la linea ya parece montada en su borde
            cruces = sum(1 for p, q in tramos for o in obstaculos if P._cruza(p, q, o, 8))
            # sin volver a pasar por sus extremos
            cruces += sum(1 for i, (p, q) in enumerate(tramos) if (i > 0 and P._cruza(p, q, dentro_t, 0))
                          or (i < len(tramos) - 1 and P._cruza(p, q, dentro_h, 0)))
            largo = sum(abs(q[0] - p[0]) + abs(q[1] - p[1]) for p, q in tramos)
            clave = (cruces, _encima(tramos, otras_lineas), largo + 150 * len(medios))
            if mejor is None or clave < mejor[0]:
                mejor = (clave, pts)
        if mejor and mejor[0][0] == 0:
            break
    return (mejor[0][0], mejor[1]) if mejor else (1, None)


def _nombre_arriba(doc, v):
    """Rectangulo del nombre (y el estereotipo) que StarUML escribe centrado arriba de una caja con otras adentro
    (paquete, nodo, sistema, estado compuesto...): una linea que entra o sale de ella puede cruzar esa franja a un
    lado del texto. Si no se sabe que texto lleva, la franja completa."""
    r = _rect(v)
    nc = doc.ids.get((v.get('nameCompartment') or {}).get('$ref')) or {}
    textos = [x['text'] for x in nc.get('subViews', []) if x.get('visible') is not False
              and isinstance(x.get('text'), str) and x['text'].strip()]
    if not textos:
        return r[0], r[1], r[2], r[1] + 35
    # en negritas (~15% mas anchas) y con holgura por el icono que algunas llevan a un lado
    w = max(M.ancho13(t) for t in textos) * 1.15 + 24
    cx = (r[0] + r[2]) / 2
    return max(r[0], cx - w / 2), r[1], min(r[2], cx + w / 2), r[1] + 35


def _sin_cruces(doc, v, va, vb, otras):
    """Si la linea v cruza alguna de las cajas otras (o un nombre: el de un contenedor o el que va debajo de un
    extremo), o le llega por un costado a un icono, la cambia por la ruta libre mas corta que haya."""
    from . import programa as P
    if va is vb or not _es_caja(va) or not _es_caja(vb):
        return
    obst = [z for z in (_zona_nombre(va), _zona_nombre(vb)) if z] + list(otras)
    actual = [tuple(p) for p in P._puntos(v)]
    # un icono (actor, artefacto...) es mas angosto que su caja: si la linea le llega por un costado, queda en el aire
    iconos = tuple(x.get('stereotypeDisplay') == 'icon' or x.get('_type') == 'UMLActorView' for x in (va, vb))
    dibujo = _puntos_staruml(doc, v)
    de_costado = any(ic and (abs(p[0] - r[0]) <= 1 or abs(p[0] - r[2]) <= 1) and r[1] + 1 < p[1] < r[3] - 1
                     for ic, p, r in ((iconos[0], dibujo[0], _rect(va)), (iconos[1], dibujo[-1], _rect(vb))))
    if not de_costado and not sum(1 for p, q in zip(actual, actual[1:]) for o in obst if P._cruza(p, q, o, 0)):
        return
    dg = doc.ids.get((v.get('_parent') or {}).get('$ref')) or {}
    lineas = [x for x in dg.get('ownedViews', []) if x is not v and isinstance(x.get('points'), str)]
    otras_l = [s for x in lineas for s in zip(P._puntos(x), P._puntos(x)[1:])]
    # tampoco encima del borde de un carril, de un marco o de lo que contiene a un extremo
    for x in dg.get('ownedViews', []):
        if _es_caja(x) and (_es_zona(x) or any(y is not x and _contiene(_rect(x), _rect(y)) for y in (va, vb))):
            r = _rect(x)
            otras_l += [((r[0], r[1]), (r[2], r[1])), ((r[2], r[1]), (r[2], r[3])), ((r[0], r[3]), (r[2], r[3])),
                        ((r[0], r[1]), (r[0], r[3]))]
    cruces, pts = _ruta_libre(_rect(va), _rect(vb), obst, otras_l, iconos)
    if cruces == 0:
        v['points'] = ';'.join(f'{x}:{y}' for x, y in pts)


def _lado_de_borde(doc, els, rels, vistas, padre_de, existente):
    """Puertos y pines en el lado (derecho o izquierdo) de su caja que mira a lo que conectan, ya con todo
    acomodado. Si se conectan con algo de adentro (delegacion), a su altura y del lado desde donde el conector llega
    horizontal sin cruzar otra caja de adentro; si solo van hacia afuera, del lado donde esta lo que conectan."""
    from . import programa as P
    por_dueno, a_la_izquierda = {}, set()
    for c in els:
        dueno = padre_de(c)
        if not _de_borde(c['_p']) or c.get('sobre') is None or dueno is None or c.get('x') is not None:
            continue
        vb, vd = vistas.get(c['_k']), vistas.get(dueno['_k'])
        if not _es_caja(vb) or not _es_caja(vd):
            continue
        por_dueno.setdefault(dueno['_k'], []).append(c)
        otros = []
        for rel in rels:
            for a_, b_ in (('desde', 'hasta'), ('hasta', 'desde')):
                if str(rel.get(a_)) == c['_k'] and rel.get(b_) is not None:
                    o = vistas.get(str(rel[b_])) or existente(str(rel[b_]))
                    if _es_caja(o) and o is not vb:
                        otros.append(o)
        if not otros:
            continue
        rd = P._caja(vd)
        cx, cy = M.centro(vb)
        lados = {'der': rd[2], 'izq': rd[0]}
        actual = 'der' if abs(cx - rd[2]) <= abs(cx - rd[0]) else 'izq'
        otro_lado = 'izq' if actual == 'der' else 'der'
        adentro = [o for o in otros if o is not vd and _contiene(rd, P._caja(o))]
        if adentro:
            ro = P._caja(adentro[0])
            y = (ro[1] + ro[3]) / 2
            # las otras cajas de adentro (sin contar las que contienen a la de destino)
            resto = [P._caja(x) for x in vistas.values() if x is not vb and x is not vd and x is not adentro[0]
                     and _es_caja(x) and _contiene(rd, P._caja(x)) and not _contiene(P._caja(x), ro)]

            def libre(lado):
                x1 = ro[0] if lado == 'izq' else ro[2]
                return not any(P._cruza((lados[lado], y), (x1, y), r_, 2) for r_ in resto)
            lado = actual if libre(actual) or not libre(otro_lado) else otro_lado
            if lado == 'izq' and actual == 'der':
                a_la_izquierda.add(dueno['_k'])
        else:
            mx = sum(M.centro(o)[0] for o in otros) / len(otros)
            lado = 'izq' if mx < rd[0] else ('der' if mx > rd[2] else actual)
            y = cy
        dx, dy = round(lados[lado] - vb['width'] / 2 - vb['left']), round(y - vb['height'] / 2 - vb['top'])
        if dx or dy:
            _desplazar(vb, dx, dy)
    # medir() deja a la derecha de lo de adentro el espacio para los nombres de los puertos: si todos quedaron a la
    # izquierda, lo de adentro se corre a la derecha y el espacio queda de su lado
    for k in a_la_izquierda:
        vd = vistas[k]
        rd = P._caja(vd)
        propios = [vistas[c['_k']] for c in por_dueno[k]]
        if any(abs(M.centro(x)[0] - rd[2]) < abs(M.centro(x)[0] - rd[0]) for x in propios):
            continue
        adentro = [x for x in vistas.values() if x is not vd and _es_caja(x) and _contiene(rd, P._caja(x))
                   and not any(x is y_ for y_ in propios)]
        reserva = max(round(M.ancho13(c.get('nombre') or '')) + 16 for c in por_dueno[k])
        if adentro and max(P._caja(x)[2] for x in adentro) + reserva <= rd[2] - 10:
            for x in adentro:
                _desplazar(x, reserva, 0)


def generar_diagrama(doc, diagrama, elementos, relaciones=(), disposicion='capas'):
    """Dibuja un diagrama completo de cualquier tipo a partir de listas:
      elementos: [{simbolo, nombre?, clave?, dentro?, sobre?, x?, y?, ancho?, alto?}]
        dentro: el elemento que lo contiene (nodo dentro de nodo, subestado en su estado compuesto, accion en su
                carril); sobre: donde va pegado (puerto sobre componente, pin sobre accion, restriccion de tiempo sobre
                un mensaje). Se refieren a la clave (o nombre) de otro elemento, a la clave de una relacion, o a algo
                ya dibujado en el diagrama (p. ej. el marco de un diagrama de tiempos). x, y fijan la posicion.
      relaciones: [{simbolo, desde?, hasta?, nombre?, clave?}]
    disposicion: 'capas' acomoda por capas siguiendo las relaciones; 'secuencia' pone los elementos de primer nivel en
    fila (lifelines) y las relaciones (mensajes) en orden, cada una mas abajo.
    Avisa cuando una linea sale de un elemento anidado hacia afuera de su contenedor (atraviesa el contenedor) y cuando
    cruza cajas que no son sus extremos."""
    from . import programa as P
    if disposicion not in ('capas', 'secuencia'):
        raise MdjError('disposicion debe ser capas o secuencia')
    dg = doc.diagram(diagrama)
    tipo_dg = dg['_type']
    els, claves, rels, rclaves = [], {}, [], {}
    for i, e in enumerate(elementos):
        if 'simbolo' not in e:
            raise MdjError(f'elemento {i}: falta simbolo')
        clave, p = plantilla_simbolo(tipo_dg, e['simbolo'])
        if clave.split('|')[1] in ('UMLBoundary', 'UMLControl', 'UMLEntity'):
            # sus iconos se deforman si se les da tamano, no muestran atributos y la paleta de clases no trae actor
            raise MdjError('Para un diagrama de analisis (boundary, control, entity) usa mdj_robustez_generar: '
                           'acomoda actor, pantallas, control y entidades como se dibujan en robustez')
        k = str(e.get('clave') or e.get('nombre') or f'#{i}')
        if k in claves:
            raise MdjError(f'Hay dos elementos con la clave "{k}": usa "clave" para distinguirlos')
        el = dict(e, _k=k, _clave=clave, _p=p, _hijos=[], _sobre=[])
        claves[k] = el
        els.append(el)
    for i, r in enumerate(relaciones or ()):
        if 'simbolo' not in r:
            raise MdjError(f'relacion {i}: falta simbolo')
        clave, p = plantilla_simbolo(tipo_dg, r['simbolo'])
        k = str(r.get('clave') or f'~{i}')
        if k in claves or k in rclaves:
            raise MdjError(f'La clave "{k}" de la relacion {r["simbolo"]} ya se usa')
        rel = dict(r, _k=k, _clave=clave, _p=p, _sobre=[])
        rclaves[k] = rel
        rels.append(rel)

    def existente(spec):
        """Vista ya dibujada en el diagrama (por id de vista, id o nombre de su elemento; @marco es el marco que trae
        el diagrama, como el de un diagrama de tiempos)."""
        if spec == '@marco':
            return next((v for v in dg.get('ownedViews', []) if v.get('_type', '').endswith('FrameView')), None)
        try:
            return _vista(doc, dg, spec)
        except MdjError:
            return None

    for el in els:
        for campo in ('dentro', 'sobre'):
            r_ = el.get(campo)
            if r_ is None:
                continue
            r_ = str(r_)
            if r_ in claves:
                (claves[r_]['_hijos'] if campo == 'dentro' else claves[r_]['_sobre']).append(el)
            elif r_ in rclaves and campo == 'sobre':
                rclaves[r_]['_sobre'].append(el)
            elif existente(r_) is None:
                raise MdjError(f'{el["_k"]}: {campo} "{r_}" no es un elemento ni una relacion de la lista, ni esta '
                               f'dibujado en {dg.get("name")}')
    raices = [el for el in els if el.get('dentro') is None and el.get('sobre') is None]
    # un marco sin nada adentro envuelve el diagrama: se dibuja al final alrededor de todo
    marcos = [el for el in raices if el['_p']['vista'] == 'UMLFrameView' and not el['_hijos']
              and el.get('x') is None]
    raices = [el for el in raices if el not in marcos]
    sueltos = [el for el in els if (el.get('sobre') is not None and str(el['sobre']) not in claves
                                    and str(el['sobre']) not in rclaves)
               or (el.get('dentro') is not None and str(el['dentro']) not in claves)]
    for rel in rels:
        for c in ('desde', 'hasta'):
            if rel.get(c) is not None and str(rel[c]) not in claves and str(rel[c]) not in rclaves \
                    and existente(str(rel[c])) is None:
                raise MdjError(f'relacion {rel["simbolo"]}: {c} "{rel[c]}" no es un elemento de la lista ni esta '
                               f'dibujado en {dg.get("name")}')

    def padre_de(el):
        r_ = el.get('dentro') if el.get('dentro') is not None else el.get('sobre')
        return claves.get(str(r_)) if r_ is not None else None

    # nada puede quedar dentro (o sobre) de si mismo, ni en un ciclo de contencion: el acomodo no terminaria
    for el in els:
        cadena_k, x = [el['_k']], padre_de(el)
        while x is not None:
            if x['_k'] in cadena_k:
                ciclo = cadena_k[cadena_k.index(x['_k']):] + [x['_k']]
                raise MdjError('Ciclo de contencion (dentro/sobre): ' + ' -> '.join(ciclo))
            cadena_k.append(x['_k'])
            x = padre_de(x)

    def ancestros_el(el):
        """El elemento y sus contenedores (por dentro o sobre), del mas cercano al mas lejano."""
        res = []
        while el is not None and el not in res:
            res.append(el)
            el = padre_de(el)
        return res

    def dentro_de(el):
        """Contenedores (por 'dentro', no 'sobre') de un elemento, del mas cercano al mas lejano."""
        cad = ancestros_el(el)
        return [c['_k'] for a_, c in zip(cad, cad[1:]) if a_.get('dentro') is not None]

    def raiz_de(el):
        return ancestros_el(el)[-1]

    def arista(rel, miembros):
        a, b = claves.get(str(rel.get('desde'))), claves.get(str(rel.get('hasta')))
        # se sube cada extremo hasta el nivel que se esta acomodando
        a = next((x for x in ancestros_el(a) if x['_k'] in miembros), None) if a else None
        b = next((x for x in ancestros_el(b) if x['_k'] in miembros), None) if b else None
        if not a or not b or a is b:
            return None
        # la generalizacion va al reves y manda: la clase base arriba de sus derivadas. Las realizaciones no: StarUML
        # dibuja la interfaz como una bola con el nombre debajo, y una linea que llega desde abajo cruza el nombre;
        # con quien la provee y quien la requiere arriba, las dos llegan a la bola sin tocarlo
        if _invierte_capas(tipo_dg, rel.get('simbolo')):
            return (b['_k'], a['_k'], True)
        return (a['_k'], b['_k'], False)

    def antes_que(rel):
        """Relaciones que deben estar dibujadas antes: la que usa como extremo (mensaje sobre su conector) y aquella
        sobre la que va un extremo suyo o un contenedor de este."""
        res = []
        for c in ('desde', 'hasta'):
            r_ = rel.get(c)
            if r_ is None:
                continue
            if str(r_) in rclaves:
                res.append(str(r_))
            for x in ancestros_el(claves.get(str(r_))) if str(r_) in claves else ():
                if x.get('sobre') is not None and str(x['sobre']) in rclaves:
                    res.append(str(x['sobre']))
        return res
    # se dibujan en el orden dado, salvo que una use a otra que viene despues: esa se adelanta
    orden_rels, hechas, pend = [], set(), list(rels)
    while pend:
        sig = next((r for r in pend if all(k in hechas for k in antes_que(r))), None)
        if sig is None:
            raise MdjError('Relaciones en ciclo (cada una necesita que la otra este dibujada): ' +
                           ', '.join(f'{r["simbolo"]} "{r["_k"]}" usa {", ".join(antes_que(r))}' for r in pend))
        orden_rels.append(sig)
        hechas.add(sig['_k'])
        pend.remove(sig)
    rels = orden_rels

    def bandas(lanes, x0=0, y0=0):
        """Carriles contiguos (columnas si son verticales, filas si son horizontales) del mismo largo, con todo lo de
        adentro en capas comunes siguiendo el flujo: asi las lineas entre carriles son cortas y van en un sentido.
        Devuelve {carril: (x, y)} relativo y el tamano del conjunto."""
        vertical = _carril_vertical(lanes[0]['_p'])
        hijos = [c for ln in lanes for c in ln['_hijos']]
        miembros = {c['_k'] for c in hijos}
        for c in hijos:
            medir(c)
        aristas = [x[:2] for x in (arista(r, miembros) for r in rels) if x]
        capa = _capas_flujo([c['_k'] for c in hijos], aristas)
        n_capas = max(capa.values(), default=-1) + 1
        GAP, MARG = 50, 25
        # largo de cada capa (alto de fila si son verticales, ancho de columna si son horizontales), comun a todos
        largo = [max([0] + [(c['_tam'][1] if vertical else c['_tam'][0]) for c in hijos if capa[c['_k']] == i])
                 for i in range(n_capas)]
        inicio = [CABECERA + MARG + sum(largo[:i]) + GAP * i for i in range(n_capas)]
        total = (inicio[-1] + largo[-1] + MARG) if n_capas else CABECERA + 60
        pos, off = {}, 0
        for ln in lanes:
            ln['_rel'] = {}
            ancho = 0
            for i in range(n_capas):
                fila = [c for c in ln['_hijos'] if capa[c['_k']] == i]
                cursor = MARG
                for c in fila:
                    cw, ch = c['_tam']
                    if vertical:
                        ln['_rel'][c['_k']] = (cursor, inicio[i] + (largo[i] - ch) // 2)
                        cursor += cw + 30
                    else:
                        ln['_rel'][c['_k']] = (inicio[i] + (largo[i] - cw) // 2, cursor)
                        cursor += ch + 30
                ancho = max(ancho, cursor - 30 + MARG)
            ancho = max(ancho, round(M.ancho13(ln.get('nombre') or '')) + 40, 160)
            ln['_relsobre'] = {}
            ln['_tam'] = (ancho, total) if vertical else (total, ancho)
            pos[ln['_k']] = (x0 + off, y0) if vertical else (x0, y0 + off)
            off += ancho
        return pos, ((off, total) if vertical else (total, off))

    def medir(el):
        """Tamano de cada elemento; los contenedores se acomodan por dentro primero (posiciones relativas)."""
        w, h = _tam_natural(el['_p'], el.get('nombre'))
        el['_icono'] = None
        nombre_abajo = _nombre_abajo(el['_p'], el.get('nombre'))
        if nombre_abajo and not el['_hijos'] and not el['_sobre'] and el.get('ancho') is None and el.get('alto') is None:
            # un icono (evento, compuerta...) con el nombre debajo: el acomodo le reserva el ancho y el alto del nombre
            # y el icono se dibuja centrado arriba de ese espacio
            el['_icono'] = (w, h)
            w, h = max(w, nombre_abajo[0]), h + nombre_abajo[1]
        if el['_hijos'] and all(_es_carril(c['_p']) for c in el['_hijos']):
            # un pool con sus lanes: los lanes en bandas despues del encabezado del pool
            vert = _carril_vertical(el['_p'])
            pos, (bw, bh) = bandas(el['_hijos'], 0 if vert else CABECERA, CABECERA if vert else 0)
            el['_rel'], el['_relsobre'] = pos, {}
            el['_tam'] = (bw + (0 if vert else CABECERA), bh + (CABECERA if vert else 0))
            return el['_tam']
        borde = [c for c in el['_sobre'] if _de_borde(c['_p'])]
        interiores = [c for c in el['_sobre'] if not _de_borde(c['_p'])]
        if el['_hijos']:
            miembros = {c['_k'] for c in el['_hijos']}
            tam = {c['_k']: medir(c) for c in el['_hijos']}
            aristas = list(dict.fromkeys(x for x in (arista(r, miembros) for r in rels) if x))
            pos, _ = P.acomodar(sorted(miembros), tam, aristas)
            for c in el['_hijos']:
                if c.get('x') is not None and c.get('y') is not None:
                    pos[c['_k']] = (c['x'], c['y'])
            x0 = min(x for x, _ in pos.values())
            y0 = min(y for _, y in pos.values())
            el['_rel'] = {k: (x - x0 + PAD_X, y - y0 + PAD_ARRIBA) for k, (x, y) in pos.items()}
            w = max(w, max(el['_rel'][k][0] + tam[k][0] for k in miembros) + PAD_X)
            h = max(h, max(el['_rel'][k][1] + tam[k][1] for k in miembros) + PAD_ABAJO)
        # lo que va pegado y no es de borde (partes, lifelines de tiempos, estados de una lifeline...): adentro, en
        # columna debajo de lo anterior
        el['_relsobre'] = {}
        yy = max([PAD_ARRIBA] + [el['_rel'][c['_k']][1] + c['_tam'][1] + 20 for c in el['_hijos']])
        if interiores and _muestra_atributos(el['_p']):
            yy += 15 * len(el['_sobre']) + 10
        for c in interiores:
            cw, ch = medir(c)
            el['_relsobre'][c['_k']] = (PAD_X, yy)
            yy += ch + 20
            w = max(w, PAD_X * 2 + cw)
            h = max(h, yy)
        # con puertos en el borde derecho, espacio para sus nombres (StarUML los pone por dentro)
        if el['_hijos'] or interiores:
            w += max((round(M.ancho13(c.get('nombre') or '')) + 16 for c in borde), default=0)
        el['_tam'] = (round(el.get('ancho') or w), round(el.get('alto') or h))
        return el['_tam']

    tam = {el['_k']: medir(el) for el in raices}
    miembros = {el['_k'] for el in raices}
    previas = [v for v in dg.get('ownedViews', []) if _es_caja(v) and not v.get('_type', '').endswith('FrameView')]
    y_base = max((v['top'] + v['height'] for v in previas), default=0) + (40 if previas else 0)
    geometrias = []
    y_msj = 180
    if disposicion == 'secuencia':
        # lifelines en fila, en el orden de la lista, a la derecha de las que ya tenga el diagrama y tan altas como lo
        # pidan los mensajes, que van debajo del ultimo mensaje que ya tenga; lo que va pegado a una lifeline
        # (auto-mensaje, invariante) toma su turno despues de los mensajes; lo demas (fragmentos, continuaciones,
        # restricciones...) va en una fila debajo
        n_msj = sum(1 for r in rels if r['_p']['forma'] == 'line')
        pegados = [c for el in raices if _es_lifeline(el['_p']) for c in el['_sobre']
                   if c.get('x') is None or c.get('y') is None]
        ya_ll = [v for v in dg.get('ownedViews', []) if _es_caja(v) and 'Lifeline' in v.get('_type', '')]
        ys = [float(q.split(':')[1]) for v in dg.get('ownedViews', []) if v.get('_type') == 'UMLSeqMessageView'
              and isinstance(v.get('points'), str) for q in v['points'].split(';')]
        ys += [v['top'] + v['height'] for v in dg.get('ownedViews', []) if _es_caja(v)
               and v.get('_type') in ('UMLStateInvariantView', 'UMLContinuationView')]
        y_msj = round(max(ys)) + 45 if ys else 180
        y_ll = min((v['top'] for v in ya_ll), default=60)
        fondo = y_msj + 45 * (n_msj + len(pegados)) + 40
        alto_ll = fondo - y_ll
        x, pos = max((v['left'] + v['width'] + 50 for v in ya_ll), default=40), {}
        # dos lifelines que se mandan un mensaje quedan separadas al menos lo que mide su nombre (con el numero que
        # StarUML le pone) mas un margen: si no, el nombre queda sobre la activacion
        centro = {}
        n_ant = sum(1 for v in dg.get('ownedViews', []) if v.get('_type') == 'UMLSeqMessageView')
        separar = []
        for r in [r for r in rels if r['_p']['forma'] == 'line']:
            n_ant += 1
            if r.get('desde') is not None and r.get('hasta') is not None and str(r['desde']) != str(r['hasta']):
                separar.append((str(r['desde']), str(r['hasta']), M.ancho13(f'{n_ant} : {r.get("nombre") or ""}') + 44))

        def centro_de(k):
            if k in centro:
                return centro[k]
            v = existente(k) if k not in claves else None
            return v['left'] + v['width'] / 2 if _es_caja(v) else None
        for el in [e for e in raices if _es_lifeline(e['_p'])]:
            c = x + el['_tam'][0] / 2
            for a_, b_, sep in separar:
                otro = b_ if a_ == el['_k'] else (a_ if b_ == el['_k'] else None)
                co = centro_de(otro) if otro is not None else None
                if co is not None and co < c + 1:
                    c = max(c, co + sep)
            x = round(c - el['_tam'][0] / 2)
            centro[el['_k']] = x + el['_tam'][0] / 2
            pos[el['_k']] = (x, y_ll)
            if not el.get('alto') and 'Seq' in el['_p']['vista']:
                el['_tam'] = (el['_tam'][0], max(el['_tam'][1], alto_ll))
            x += el['_tam'][0] + 50
        # las lifelines que ya estaban se alargan hasta los mensajes nuevos
        for v in ya_ll:
            if 'Seq' in v['_type'] and v['top'] + v['height'] < fondo:
                extra = fondo - v['top'] - v['height']
                v['height'] += extra
                for sv in v.get('subViews', []):
                    if sv.get('_type') == 'UMLLinePartView' and isinstance(sv.get('height'), (int, float)):
                        sv['height'] += extra
        for j, c in enumerate(pegados):
            ll = padre_de(c)
            c['x'] = pos[ll['_k']][0] + ll['_tam'][0] // 2 - 7
            c['y'] = y_msj + 45 * (n_msj + j)
        abajo = [v['top'] + v['height'] for v in previas if 'Lifeline' not in v.get('_type', '')]
        x, y_otros = 40, max([fondo + 40] + [b + 40 for b in abajo])
        for el in [e for e in raices if not _es_lifeline(e['_p'])]:
            pos[el['_k']] = (x, y_otros)
            x += el['_tam'][0] + 40
    else:
        pos, x_carriles, y_carriles = {}, 0, 0
        for vert in (True, False):
            grupo = [el for el in raices if _es_carril(el['_p']) and _carril_vertical(el['_p']) == vert
                     and not (el['_hijos'] and all(_es_carril(c['_p']) for c in el['_hijos']))]
            if grupo:
                pb, (bw, bh) = bandas(grupo, 40 + x_carriles, 40 + y_base)
                pos.update(pb)
                x_carriles += bw + 80
                y_carriles = max(y_carriles, bh)
        # pools con lanes adentro: uno debajo de otro, junto a los carriles
        y_pool, x_extra = 40 + y_base, x_carriles
        for el in raices:
            if el['_hijos'] and _es_carril(el['_p']) and all(_es_carril(c['_p']) for c in el['_hijos']):
                pos[el['_k']] = (40 + x_carriles, y_pool)
                y_pool += el['_tam'][1] + 60
                x_extra = max(x_extra, x_carriles + el['_tam'][0] + 80)
                y_carriles = max(y_carriles, y_pool - 40 - y_base)
        # lo demas: a la derecha de carriles altos, debajo de carriles anchos
        if pos and x_extra > y_carriles:
            y_base, x_extra = y_base + y_carriles + 40, 0
        resto = {k for k in miembros if k not in pos}
        aristas = list(dict.fromkeys(x for x in (arista(r, resto) for r in rels) if x))
        pr, geometrias = P.acomodar(sorted(resto), {k: tam[k] for k in resto}, aristas) if resto else ({}, [])
        pos.update({k: (x + x_extra, y + y_base) for k, (x, y) in pr.items()})
    for el in raices:
        if el.get('x') is not None and el.get('y') is not None:
            pos[el['_k']] = (el['x'], el['y'])
    vistas, avisos, no_visibles = {}, [], []

    def vista_de_ref(spec):
        spec = str(spec)
        return vistas[spec] if spec in vistas else existente(spec)

    def dib(*args, **kw):
        """dibujar, juntando sus avisos: los de nombres que StarUML no muestra aparte de los demas (una referencia de
        la plantilla que se omitio)."""
        r = dibujar(doc, dg['_id'], *args, **kw)
        for a in r.get('avisos') or []:
            lista = avisos if a.startswith('referencia a ') else no_visibles
            if a not in lista:
                lista.append(a)
        return r

    def poner_sobre(c, v, i, n, x, y, w, h, hijos=(), dueno=None):
        """Algo pegado a otra vista: en el borde derecho repartido a lo alto (puertos, pines), o en x, y si se dio."""
        borde = [cc for cc in (dueno['_sobre'] if dueno else [c]) if _de_borde(cc['_p'])]
        if c.get('x') is not None and c.get('y') is not None:
            px, py = c['x'], c['y']
        elif dueno and c['_k'] in dueno.get('_relsobre', {}):
            rx, ry = dueno['_relsobre'][c['_k']]
            px, py = x + rx, y + ry
        elif not _es_caja(v) and isinstance(v.get('points'), str):
            px, py = _junto_a_linea(doc, v, c.get('nombre'), i)
        else:
            i, n = (borde.index(c), len(borde)) if c in borde else (i, n)
            arriba = 30 if h > 70 else (22 if h > 40 else 0)  # el nombre del contenedor va arriba
            px, py = x + w - 8, y + arriba + round((h - arriba) * (i + 1) / (n + 1)) - 8
            # si se conecta con algo de adentro (delegacion), a su altura: el conector entra horizontal
            for rel in rels:
                if str(rel.get('desde')) == c['_k']:
                    otro = rel.get('hasta')
                elif str(rel.get('hasta')) == c['_k']:
                    otro = rel.get('desde')
                else:
                    continue
                hijo = vistas.get(str(otro))
                if hijo is not None and claves.get(str(otro)) in hijos and _es_caja(hijo):
                    py = round(hijo['top'] + hijo['height'] / 2) - 8
                    break
        tw, th = c.get('_tam') or (c.get('ancho'), c.get('alto'))
        interior = not _de_borde(c['_p'])
        rs = dib(c['_clave'], c.get('nombre'), px, py, tw if interior else c.get('ancho'),
                 th if interior else c.get('alto'), sobre=v['_id'])
        vv = doc.get(rs['vista'])
        vistas[c['_k']] = vv
        for j, cc in enumerate(c['_sobre']):
            poner_sobre(cc, vv, j, len(c['_sobre']), vv.get('left', px), vv.get('top', py),
                        vv.get('width', 20), vv.get('height', 20), dueno=c)

    def poner(el, x, y, padre_v=None):
        if el.get('_icono'):
            iw, ih = el['_icono']
            r = dib(el['_clave'], el.get('nombre'), x + (el['_tam'][0] - iw) // 2, y, iw, ih)
        else:
            r = dib(el['_clave'], el.get('nombre'), x, y, *el['_tam'])
        v = doc.get(r['vista'])
        vistas[el['_k']] = v
        if padre_v is not None:
            anidar(doc, v, padre_v)
        for c in el['_hijos']:
            cx, cy = el['_rel'][c['_k']]
            poner(c, x + cx, y + cy, v)
        for i, c in enumerate(el['_sobre']):
            poner_sobre(c, v, i, len(el['_sobre']), x, y, *el['_tam'], hijos=el['_hijos'], dueno=el)

    for el in raices:
        poner(el, *pos[el['_k']])
    # lo que va dentro o sobre algo que ya estaba dibujado en el diagrama
    for el in sueltos:
        destino = existente(str(el.get('sobre') if el.get('sobre') is not None else el['dentro']))
        if el.get('sobre') is not None:
            # junto a la caja o a la linea sobre la que va (una linea no tiene left/top)
            x, y = (destino['left'], destino['top']) if _es_caja(destino) else _centro_linea(destino)
            poner_sobre(el, destino, 0, 1, x, y, destino.get('width', 1), destino.get('height', 1))
        else:
            medir(el)
            x = el['x'] if el.get('x') is not None else destino['left'] + PAD_X
            y = el['y'] if el.get('y') is not None else destino['top'] + PAD_ARRIBA
            poner(el, x, y, destino)
    if disposicion == 'capas':
        _lado_de_borde(doc, els, rels, vistas, padre_de, existente)
    cajas = {k: P._caja(vistas[k]) for k in miembros}
    medios_de = P.rutas(cajas, geometrias) if geometrias else {}
    sentido = {frozenset(par): par for geo in geometrias for par in list(geo['cadenas']) + geo['mismas']}
    # avisos y y_msj ya vienen de arriba (y_msj empieza debajo de los mensajes que ya tenia el diagrama)
    lineas, cruzan = [], []

    def crea_caja(rel):
        return any(e['padre'] == '@diagrama' and not es_linea(e['objeto']['_type']) for e in rel['_p']['objetos'])
    # las que crean una caja (clase asociacion) al final: su caja busca lugar cuando ya estan las demas lineas
    orden = rels if disposicion == 'secuencia' else sorted(rels, key=crea_caja)
    for rel in orden:
        a, b = claves.get(str(rel.get('desde'))), claves.get(str(rel.get('hasta')))
        va = vista_de_ref(rel['desde']) if rel.get('desde') is not None else None
        vb = vista_de_ref(rel['hasta']) if rel.get('hasta') is not None else None
        medios = []
        if disposicion == 'capas' and a and b and a['_k'] in miembros and b['_k'] in miembros and a is not b:
            par = frozenset((a['_k'], b['_k']))
            if par in sentido:
                medios = list(medios_de.get(sentido[par], []))
                if sentido[par] != (a['_k'], b['_k']):
                    medios = medios[::-1]
        r = dib(rel['_clave'], rel.get('nombre'), desde=va and va['_id'], hasta=vb and vb['_id'], medios=medios)
        v = doc.get(r.get('linea') or r['vista'])
        vistas[rel['_k']] = v
        lineas.append(r['vista'])
        if disposicion == 'secuencia' and v.get('_type') == 'UMLSeqMessageView':
            _mensaje_en(doc, v, y_msj)
            y_msj += 45
        for i, c in enumerate(rel['_sobre']):
            cx, cy = _centro_linea(v)
            poner_sobre(c, v, i, len(rel['_sobre']), cx, cy, 1, 1)
        # una linea de algo anidado hacia afuera de un contenedor que encapsula lo atraviesa (un puerto o pin del
        # contenedor esta en su borde: de ahi hacia adentro o hacia afuera no lo atraviesa)
        if a and b:
            ka, kb = dentro_de(a), dentro_de(b)
            for x_, kx, ky, otro in ((a, ka, kb, b), (b, kb, ka, a)):
                en_borde = {str(otro.get('sobre'))} if otro.get('sobre') is not None else set()
                fuera = [c for c in kx if c not in ky and c != otro['_k'] and c not in en_borde
                         and encapsula(_tipo_modelo(claves[c]))]
                if fuera:
                    avisos.append(f'{rel["simbolo"]} {a["_k"]} -> {b["_k"]}: {x_["_k"]} esta dentro de {fuera[-1]} y '
                                  f'{otro["_k"]} afuera, asi que la linea atraviesa {fuera[-1]}. Conviene que la relacion '
                                  f'sea de {fuera[-1]} (o que entre por un puerto suyo y se delegue hacia adentro)')
                    break
        if va is not None and vb is not None and isinstance(v.get('points'), str) and disposicion == 'capas':
            ext = {id(va), id(vb)}
            if not crea_caja(rel):
                # lo que la linea no debe cruzar: las demas cajas y sus nombres de abajo; de los contenedores de sus
                # extremos y de los carriles, solo el nombre (la linea si cruza su borde)
                suyos = {x['_k'] for e_ in (a, b) if e_ for x in ancestros_el(e_)[1:]}
                # al dueno de un puerto o pin la linea no se le mete: de el estorba toda la franja de arriba
                duenos = {padre_de(e_)['_k'] for e_ in (a, b) if e_ and e_.get('sobre') is not None and padre_de(e_)}
                obst = []
                for k, x in vistas.items():
                    if k not in claves or id(x) in ext or not _es_caja(x) or claves[k].get('sobre') is not None \
                            or claves[k] in marcos:
                        continue
                    r_ = P._caja(x)
                    if _es_carril(claves[k]['_p']):
                        obst.append((r_[0], r_[1], r_[2], r_[1] + CABECERA) if _carril_vertical(claves[k]['_p'])
                                    else (r_[0], r_[1], r_[0] + CABECERA, r_[3]))
                    elif k in suyos:
                        if not _es_zona(x):
                            obst.append((r_[0], r_[1], r_[2], r_[1] + 35) if k in duenos else _nombre_arriba(doc, x))
                    elif not _es_zona(x):
                        obst.append(r_)
                        if _zona_nombre(x):
                            obst.append(_zona_nombre(x))
                _sin_cruces(doc, v, va, vb, obst)
            anc = set(dentro_de(a) if a else []) | set(dentro_de(b) if b else [])
            otras = [P._caja(x) for k, x in vistas.items() if k in claves and id(x) not in ext and _es_caja(x)
                     and k not in anc and claves[k].get('sobre') is None and claves[k] not in marcos
                     and not _es_carril(claves[k]['_p'])]
            if P._cruces(P._puntos(v), otras):
                cruzan.append(f'{rel.get("desde")} - {rel.get("hasta")} ({rel["simbolo"]})')
    # al final, para que envuelvan tambien lo que crearon las lineas (clase asociacion, objeto de enlace...)
    propios = [v for v in dg.get('ownedViews', []) if v.get('_type', '').endswith('FrameView') and _es_caja(v)
               and v not in vistas.values()]
    todas = [P._caja(v) for v in dg.get('ownedViews', []) if _es_caja(v) and v not in propios
             and not v.get('_type', '').endswith('FrameView')]
    if todas and (marcos or propios):
        x0, y0 = min(c[0] for c in todas), min(c[1] for c in todas)
        x1, y1 = max(c[2] for c in todas), max(c[3] for c in todas)
        m = 40  # holgura para las etiquetas de las lineas que van por la orilla
        for v in propios:  # el marco que trae el diagrama (secuencia, tiempos, SysML...) envuelve lo dibujado
            nx, ny = min(v['left'], x0 - m), min(v['top'], y0 - m - 20)
            _desplazar(v, nx - v['left'], ny - v['top'])
            v['width'] = x1 + m - nx
            v['height'] = y1 + m - ny
            x0, y0, x1, y1 = nx, ny, nx + v['width'], ny + v['height']
            m = 20
        for el in marcos:
            r = dib(el['_clave'], el.get('nombre'), x0 - m, y0 - m - 20, x1 - x0 + 2 * m, y1 - y0 + 2 * m + 20)
            vistas[el['_k']] = doc.get(r['vista'])
            x0, y0, x1, y1 = x0 - m, y0 - m - 20, x1 + m, y1 + m
            m = 20
    if disposicion == 'capas':
        # al final, con todo dibujado: los nombres de las lineas y de los puertos y pines donde no estorben
        doc.reindex()
        _acomodar_etiquetas(doc, dg, [v for v in vistas.values() if isinstance(v.get('points'), str)],
                            [vistas[c['_k']] for c in els if _de_borde(c['_p']) and _es_caja(vistas.get(c['_k']))])
    doc.reindex()
    res = {'diagrama': dg.get('name'), 'id': dg['_id'], 'cajas': len(vistas) - len(lineas), 'lineas': len(lineas),
           'vistas': {k: v['_id'] for k, v in vistas.items()}, 'lineas_que_cruzan_cajas': cruzan}
    if avisos:
        res['avisos'] = avisos
    if no_visibles:
        res['nombres_no_visibles'] = no_visibles
    return res


def _centro_linea(v):
    pts = [tuple(map(float, p.split(':'))) for p in (v.get('points') or '0:0').split(';')]
    return round((pts[0][0] + pts[-1][0]) / 2), round((pts[0][1] + pts[-1][1]) / 2)


def _x_centro(doc, v):
    """x del centro de una vista; la de la linea punteada de una lifeline es la del centro de la lifeline (StarUML la
    recoloca ahi al abrir el archivo)."""
    if v is None:
        return None
    p = doc.ids.get(doc.parent.get(v['_id']))
    if p is not None and 'Lifeline' in p.get('_type', '') and _es_caja(p):
        return p['left'] + p['width'] / 2
    return v['left'] + v['width'] / 2 if _es_caja(v) else None


def _junto_a_linea(doc, v, texto, i=0):
    """Donde poner lo que va pegado a una linea (la restriccion de tiempo de un mensaje): cerca de su origen, fuera de
    la activacion, y del lado donde no va el nombre de la linea (un mensaje hacia la derecha lleva el nombre arriba;
    hacia la izquierda, abajo), para que ni su texto ni su enlace pisen ese nombre."""
    pts = [tuple(map(float, p.split(':'))) for p in (v.get('points') or '0:0').split(';')]
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    alto = 16 * i
    if len(pts) == 2 and abs(y1 - y0) < 1:
        x0 = _x_centro(doc, doc.ids.get((v.get('tail') or {}).get('$ref'))) or x0
        x1 = _x_centro(doc, doc.ids.get((v.get('head') or {}).get('$ref'))) or x1
        ancho = M.ancho13(texto or '') + 16
        derecha, izquierda = x0 + 20, x0 - 20 - ancho
        # hacia donde va el mensaje, salvo que el texto llegue a la activacion del destino: entonces del otro lado
        if x1 >= x0:
            x = derecha if derecha + ancho <= x1 - 14 or izquierda < 0 else izquierda
            return round(x), round(y0 + 8 + alto)
        x = izquierda if izquierda >= x1 + 14 else derecha
        return round(x), round(y0 - 22 - alto)
    cx, cy = _centro_linea(v)
    return cx + 12, cy + 8 + alto


def _debajo_de_los_mensajes(dg, v=None):
    """Altura para un mensaje nuevo: 45 px debajo del mas bajo del diagrama (180 si no hay)."""
    ys = [float(q.split(':')[1]) for w in dg.get('ownedViews', []) if w is not v
          and w.get('_type') == 'UMLSeqMessageView' and isinstance(w.get('points'), str)
          for q in w['points'].split(';')]
    return round(max(ys)) + 45 if ys else 180


def _mensaje_en(doc, v, y):
    """Mensaje de secuencia a la altura y: horizontal entre las lineas punteadas de sus lifelines (o hacia un lado
    si no tiene origen o destino); su activacion, si la trae, empieza ahi."""
    if not isinstance(v.get('points'), str):
        return
    t = doc.ids.get((v.get('tail') or {}).get('$ref'))
    h = doc.ids.get((v.get('head') or {}).get('$ref'))
    xt, xh = _x_centro(doc, t), _x_centro(doc, h)
    if xt is None and xh is None:
        return
    xt = xh - 120 if xt is None else xt
    xh = xt + 120 if xh is None else xh
    v['points'] = f'{round(xt)}:{y};{round(xh)}:{y}'
    for s in v.get('subViews', []):
        if s.get('_type') == 'UMLActivationView':
            s['top'] = y
            s['left'] = round(xh - (s.get('width') or 14) / 2)
            if not isinstance(s.get('height'), (int, float)) or s['height'] < 20:
                s['height'] = 29
    # la lifeline que crea un mensaje de creacion empieza a su altura (StarUML la baja ahi al abrir el archivo): se
    # guarda asi, con el mismo fondo que tenia, para que lo guardado coincida con lo que se dibuja
    m = doc.ids.get((v.get('model') or {}).get('$ref'))
    ll = doc.ids.get(doc.parent.get(h['_id'])) if h is not None else None
    if (m or {}).get('messageSort') == 'createMessage' and _es_caja(ll) and 'Lifeline' in ll.get('_type', ''):
        fondo, delta = ll['top'] + ll['height'], round(y - 20) - ll['top']
        ll['top'] += delta
        ll['height'] = max(40, fondo - ll['top'])
        # el encabezado y la linea punteada van con ella; lo demas que cuelga de la lifeline (invariantes de estado)
        # tiene su propia altura
        for sv in ll.get('subViews', []):
            if _es_caja(sv) and sv.get('_type') in ('UMLNameCompartmentView', 'UMLLinePartView'):
                sv['top'] += delta
                if sv.get('_type') == 'UMLLinePartView':
                    sv['height'] = max(1, sv['height'] - delta)


# ---------------------------------------------------------------------------
# Elementos y relaciones sin vista (guiados por el metamodelo)
# ---------------------------------------------------------------------------

def _valor(doc, at, v):
    k, t = at['kind'], at['type']
    if k == 'prim':
        ok = {'String': str, 'Boolean': bool, 'Integer': int, 'Real': (int, float)}.get(t)
        if ok and not isinstance(v, ok) or (t == 'Integer' and isinstance(v, bool)):
            raise MdjError(f'{at["name"]} debe ser {t}')
        return v
    if k == 'enum':
        lits = (tipo(t) or {}).get('literales', [])
        if lits and v not in lits:
            raise MdjError(f'{at["name"]} debe ser uno de {", ".join(lits)}')
        return v
    if k == 'ref':
        return ref(doc.find(v)['_id'])
    if k == 'refs':
        return [ref(doc.find(x)['_id']) for x in (v if isinstance(v, list) else [v])]
    if k == 'var':
        return ref(doc.find(v)['_id']) if isinstance(v, str) and (v in doc.ids or ':' in v) else v
    raise MdjError(f'{at["name"]} no se puede asignar directamente')


def _props(doc, t, props):
    res = {}
    for k, v in (props or {}).items():
        at = atributo(t, k)
        if at is None:
            raise MdjError(f'{t} no tiene el atributo {k}. Tiene: ' +
                           ', '.join(a['name'] for a in atributos(t) if a['kind'] in ('prim', 'enum', 'ref', 'refs', 'var')))
        res[k] = _valor(doc, at, v)
    return res


def _campos_staruml():
    """{tipo: {campos}} donde StarUML guarda cada tipo de elemento al dibujarlo (sale de las plantillas): mensajes en
    messages, transiciones en transitions, acciones en nodes, lifelines en participants, puertos en attributes..."""
    if 'campos' not in _CACHE:
        res = {}

        def walk(o, campo):
            if isinstance(o, dict):
                if isinstance(o.get('_type'), str) and campo:
                    res.setdefault(o['_type'], set()).add(campo)
                for k, v in o.items():
                    if k != '_parent' and isinstance(v, (dict, list)):
                        walk(v, k)
            elif isinstance(o, list):
                for v in o:
                    walk(v, campo)
        pl = plantillas()
        for p in [p for ps in pl['plantillas'].values() for p in ps.values()] + list(pl.get('diagramas', {}).values()):
            for e in p['objetos']:
                walk(e['objeto'], e['campo'])
        _CACHE['campos'] = res
    return _CACHE['campos']


def _campo_y_dudas(padre_tipo, hijo_tipo):
    """(campo, dudas): el campo de campo_para y, si la eleccion fue ambigua (varios campos propios igual de cercanos,
    como entryActivities, doActivities y exitActivities de un estado), sus nombres."""
    todos = [a for a in atributos(padre_tipo) if a['kind'] in ('objs', 'obj') and es_subtipo(hijo_tipo, a['type'])]
    if not todos:
        return None, []
    usados = _campos_staruml()
    linaje = list(ancestros(hijo_tipo))
    propios = [a for a in todos if a['name'] != 'ownedElements' and a['type'] in linaje]
    cands = todos
    for i, t in enumerate(linaje):
        if t in usados:
            # un campo declarado para un tipo mas cercano al hijo que t manda: flowProperties para un
            # SysMLFlowProperty, aunque StarUML guarde las SysMLProperty en parts, values...
            if not any(linaje.index(a['type']) < i for a in propios):
                hit = [a for a in todos if a['name'] in usados[t]]
                if len(hit) == 1:
                    return hit[0], []
                cands = hit or todos
            break
    propios = [a for a in cands if a['name'] != 'ownedElements' and a['type'] in linaje]
    dudas = []
    if propios:
        cerca = min(linaje.index(a['type']) for a in propios)
        mejores = [a for a in propios if linaje.index(a['type']) == cerca]
        if len(mejores) == 1:
            return mejores[0], []
        dudas = [a['name'] for a in mejores]
    return next((a for a in todos if a['name'] == 'ownedElements'), todos[0]), dudas


def campo_para(padre_tipo, hijo_tipo):
    """Campo (objs/obj) del padre donde va un hijo de ese tipo, como lo guarda StarUML: el que usa StarUML al dibujar
    ese tipo (o su ancestro mas cercano), salvo que otro campo este declarado para un tipo mas cercano al hijo; si
    StarUML no lo dibuja, el campo propio cuyo tipo declarado es el mas cercano al hijo (columnas, atributos,
    operaciones, literales, parametros, tags). ownedElements queda como ultimo recurso y para los casos ambiguos."""
    return _campo_y_dudas(padre_tipo, hijo_tipo)[0]


# lo que no se crea suelto: los diagramas (mdj_diagrama_crear crea tambien su interaccion, maquina de estados...),
# el proyecto y los extremos de una relacion (los crea mdj_relacion_crear junto con ella)
NO_SUELTOS = (('Diagram', 'es un diagrama: se crea con mdj_diagrama_crear'), ('Project', 'es el proyecto'),
              ('RelationshipEnd', 'es el extremo de una relacion: se crea con mdj_relacion_crear'))


def crear_elemento(doc, t, nombre=None, dentro_de=None, campo=None, props=None):
    """Elemento de modelo de cualquier tipo, validado contra el metamodelo (sin vista)."""
    info = tipo(t)
    if not info or info['kind'] != 'class' or not es_subtipo(t, 'Model') or es_abstracto(t):
        raise MdjError(f'{t} no es un tipo de elemento de StarUML que se pueda crear')
    for base, motivo in NO_SUELTOS:
        if es_subtipo(t, base):
            raise MdjError(f'{t} {motivo}')
    padre = doc.find(dentro_de) if dentro_de else M.modelo_raiz(doc)
    if campo:
        at = atributo(padre['_type'], campo)
    else:
        at, dudas = _campo_y_dudas(padre['_type'], t)
        if dudas:
            # en ownedElements quedaria en el modelo, pero StarUML no lo mostraria en ninguno de esos campos
            raise MdjError(f'Un {t} puede ir en {", ".join(dudas[:-1])} o {dudas[-1]} de {doc.name_of(padre["_id"])} '
                           f'({padre["_type"]}): indica cual con campo')
    if not at or at['kind'] not in ('objs', 'obj') or not es_subtipo(t, at['type']):
        raise MdjError(f'Un {t} no puede ir dentro de {padre["_type"]}' + (f' en {campo}' if campo else ''))
    el = {'_type': t, '_id': doc.new_id(), '_parent': ref(padre['_id'])}
    if nombre is not None:
        el['name'] = nombre
    el.update(_props(doc, t, props))
    if at['kind'] == 'objs':
        padre.setdefault(at['name'], []).append(el)
    else:
        padre[at['name']] = el
    doc.reindex()
    return el


def _dueno_de_relacion(t):
    """(desde_el_origen, campos) donde StarUML guarda una relacion de tipo t al dibujarla: las que su plantilla cuelga
    del elemento de origen (dependencias, asociaciones, despliegues...) van en el origen; las que cuelga del dueno del
    diagrama (mensajes en la interaccion, transiciones en la region, flujos en la actividad, conectores en el
    clasificador) van en el contenedor del origen. None si StarUML no dibuja ese tipo."""
    if 'dueno_rel' not in _CACHE:
        res = {}
        for ps in plantillas()['plantillas'].values():
            for p in ps.values():
                e = next((e for e in p['objetos'] if e['objeto'].get('_id') == p.get('modelo')), None)
                if e:
                    res.setdefault(e['objeto']['_type'], []).append((e['padre'].startswith('@cola_m'), e['campo']))
        _CACHE['dueno_rel'] = {k: max(set(v), key=v.count) for k, v in res.items()}
    return next((_CACHE['dueno_rel'][a] for a in ancestros(t) if a in _CACHE['dueno_rel']), None)


def crear_relacion(doc, t, origen, destino, nombre=None, dueno=None, props=None):
    """Relacion de cualquier tipo entre dos elementos: dirigida (source/target) o con extremos (end1/end2). Queda donde
    StarUML la guarda al dibujarla (un mensaje en su interaccion, una transicion en su region...)."""
    info = tipo(t)
    if not info or es_abstracto(t) or not (es_subtipo(t, 'Relationship') or atributo(t, 'source')):
        raise MdjError(f'{t} no es una relacion de StarUML')
    a, b = doc.find(origen), doc.find(destino)
    el = {'_type': t, '_id': doc.new_id()}
    if nombre is not None:
        el['name'] = nombre
    if atributo(t, 'end1') and atributo(t, 'end2'):
        # el extremo concreto es <Tipo>End del propio tipo o de su ancestro mas cercano (UMLAssociationEnd...)
        fin = next((a + 'End' for a in ancestros(t) if tipo(a + 'End') and not tipo(a + 'End').get('abstract')), None)
        if not fin:
            raise MdjError(f'No encuentro el tipo de extremo de {t}')
        for k, x in (('end1', a), ('end2', b)):
            el[k] = {'_type': fin, '_id': doc.new_id(), '_parent': ref(el['_id']), 'reference': ref(x['_id'])}
    elif atributo(t, 'source') and atributo(t, 'target'):
        el['source'], el['target'] = ref(a['_id']), ref(b['_id'])
    else:
        raise MdjError(f'No se como conectar un {t}')
    el.update(_props(doc, t, props))

    def guardar(c, at):
        el['_parent'] = ref(c['_id'])
        if at['kind'] == 'objs':
            c.setdefault(at['name'], []).append(el)
        else:
            c[at['name']] = el
        doc.reindex()
        return el
    if dueno:
        c = doc.find(dueno)
        at = campo_para(c['_type'], t)
        if not at:
            raise MdjError(f'{doc.name_of(c["_id"])} ({c["_type"]}) no puede guardar un {t}')
        return guardar(c, at)
    # sin dueno: el que usa StarUML (subiendo desde el origen o desde su contenedor hasta quien tenga ese campo)
    cadena_origen = []
    i = a['_id']
    while i and i not in cadena_origen:
        cadena_origen.append(i)
        i = doc.parent.get(i)
    regla = _dueno_de_relacion(t)
    if regla:
        desde_origen, campo = regla
        for i in cadena_origen[0 if desde_origen else 1:]:
            at = atributo(doc.ids[i]['_type'], campo)
            if at and at['kind'] in ('objs', 'obj') and es_subtipo(t, at['type']):
                return guardar(doc.ids[i], at)
    for i in cadena_origen:
        at = campo_para(doc.ids[i]['_type'], t)
        if at:
            return guardar(doc.ids[i], at)
    raise MdjError(f'Ningun contenedor de {doc.name_of(a["_id"])} puede guardar un {t}')


# ---------------------------------------------------------------------------
# Validacion contra el metamodelo
# ---------------------------------------------------------------------------

def lineas_que_salen(doc):
    """En cualquier diagrama: lineas que unen algo anidado (containerView) con algo fuera de su contenedor, y que por
    eso atraviesan el contenedor. Lo normal es que la relacion sea del contenedor o entre por un puerto suyo."""
    avisos = []
    for dg in doc.diagrams():
        def contenedores(v):
            res, vistos = [], set()
            while v is not None and v['_id'] not in vistos:
                vistos.add(v['_id'])
                c = doc.ids.get((v.get('containerView') or {}).get('$ref'))
                if c is not None:
                    res.append(c['_id'])
                v = c
            return res

        def nombre(v):
            m = v.get('model') if v else None
            return doc.name_of(m['$ref']) if isinstance(m, dict) else (v or {}).get('_type')

        for v in dg.get('ownedViews', []):
            t = v.get('_type', '')
            if not es_linea(t):
                continue
            a = doc.ids.get((v.get('tail') or {}).get('$ref'))
            b = doc.ids.get((v.get('head') or {}).get('$ref'))
            if not a or not b:
                continue
            # una subvista (linea punteada de la lifeline, etiqueta...) cuenta como su vista principal
            while a.get('_id') in doc.parent and not _es_caja(a) and doc.ids[doc.parent[a['_id']]].get('_type', '').endswith('View'):
                a = doc.ids[doc.parent[a['_id']]]
            ca, cb = contenedores(a), contenedores(b)

            def de_borde(v):
                return es_subtipo(v.get('_type', ''), 'UMLPortView') or 'Pin' in v.get('_type', '') or \
                    'ExpansionNode' in v.get('_type', '') or (_es_caja(v) and v['width'] <= 30 and v['height'] <= 30)
            for x, cx, cy, otro in ((a, ca, cb, b), (b, cb, ca, a)):
                # un puerto o pin esta en el borde de su contenedor: de ahi hacia adentro o afuera no lo atraviesa
                propios = cx[1:] if de_borde(x) else cx
                borde_otro = cy[:1] if de_borde(otro) else []
                fuera = [c for c in propios if c not in cy[len(borde_otro):] and c != otro['_id'] and c not in borde_otro
                         and encapsula((doc.ids.get((doc.ids[c].get('model') or {}).get('$ref')) or {}).get('_type', ''))]
                if fuera:
                    c = doc.ids[fuera[-1]]
                    avisos.append(f'{dg.get("name")}: {t} de {nombre(a)} a {nombre(b)} atraviesa {nombre(c)} '
                                  f'({nombre(x)} esta dentro y {nombre(otro)} afuera)')
                    break
    return avisos


# la paleta comun de StarUML (notas, texto, figuras libres, imagenes, enlaces) va en cualquier diagrama
COMUNES = {'UMLNoteView', 'UMLNoteLinkView', 'UMLTextView', 'UMLCustomTextView', 'UMLCustomNoteView', 'UMLFrameView',
           'UMLCustomFrameView', 'FreelineEdgeView', 'ImageView', 'RectangleView', 'RoundRectView', 'EllipseView',
           'HyperlinkView', 'ShapeView', 'UMLConstraintView', 'UMLConstraintLinkView'}


def _vistas_de_paleta(tipo_dg):
    """Tipos de vista que StarUML pone directamente en el diagrama al dibujar los simbolos de su paleta."""
    clave = ('vistas_paleta', tipo_dg)
    if clave not in _CACHE:
        pl = plantillas()
        ps = list(pl['plantillas'].get(tipo_dg, {}).values()) + [pl.get('diagramas', {}).get(tipo_dg) or {'objetos': []}]
        res = {e['objeto']['_type'] for p in ps for e in p['objetos']
               if e['padre'] == '@diagrama' and es_subtipo(e['objeto']['_type'], 'View')}
        # y las que trae el diagrama al crearse (el marco de tiempos, el de la vista general de interaccion...)
        for e in (pl.get('diagramas', {}).get(tipo_dg) or {'objetos': []})['objetos']:
            pila = [e['objeto']]
            while pila:
                o = pila.pop()
                if o.get('_type') == tipo_dg:
                    res |= {v['_type'] for v in o.get('ownedViews', [])}
                pila.extend(x for x in o.get('ownedElements', []) if isinstance(x, dict))
        _CACHE[clave] = res
    return _CACHE[clave]


# anotaciones que StarUML deja poner en cualquier diagrama (grupo Annotations de la paleta: nota, enlace de nota, texto,
# cuadro de texto, linea libre, hipervinculo, rectangulo, rectangulo redondeado, elipse e imagen) y la restriccion
ANOTACIONES = ('UMLNoteView', 'UMLNoteLinkView', 'UMLTextView', 'UMLTextBoxView', 'UMLConstraintView',
               'UMLCustomNoteView', 'UMLCustomTextView', 'FreelineEdgeView', 'HyperlinkView', 'RectangleView',
               'RoundRectView', 'EllipseView', 'ImageView')


def validar_metamodelo(doc):
    """Avisos de lo que StarUML no esperaria: tipos desconocidos, hijos en campos que no los admiten,
    vistas que el diagrama no admite y lineas cuyos extremos no son vistas."""
    avisos = []
    tipos = metamodelo()['tipos']

    def walk(o, padre=None, campo=None):
        if isinstance(o, dict):
            t = o.get('_type')
            if t:
                if t not in tipos:
                    avisos.append(f'tipo desconocido para StarUML: {t} ({o.get("_id")})')
                elif padre is not None and campo and t in tipos and padre.get('_type') in tipos:
                    at = atributo(padre['_type'], campo)
                    # el tipo declarado del campo no se exige: StarUML mismo guarda, p. ej., manejadores de
                    # excepcion en Activity.edges y nodos de expansion en Action.inputs
                    if at is None:
                        avisos.append(f'{padre["_type"]} no tiene el campo {campo} (contiene {t})')
                for k, v in o.items():
                    if isinstance(v, (dict, list)) and k != '_parent':
                        walk(v, o, k)
            else:
                for v in o.values():
                    walk(v, padre, campo)
        elif isinstance(o, list):
            for v in o:
                walk(v, padre, campo)
    walk(doc.d)
    for dg in doc.diagrams():
        # vistas que admite el diagrama: las del metamodelo mas las que dibuja su paleta (la lista del metamodelo
        # esta incompleta en varios diagramas, p. ej. BPMN)
        permitidas = set((tipo(dg['_type']) or {}).get('views') or []) | _vistas_de_paleta(dg['_type']) | COMUNES
        permitidas |= {t for t in ANOTACIONES if t in tipos}
        for v in dg.get('ownedViews', []):
            t = v.get('_type')
            if permitidas and t in tipos and not any(es_subtipo(t, p) for p in permitidas):
                avisos.append(f'{dg.get("name")}: {t} no esta en las vistas que admite {dg["_type"]}')
            if t in tipos and es_linea(t):
                for k in ('head', 'tail'):
                    r = v.get(k)
                    o = doc.ids.get(r.get('$ref')) if isinstance(r, dict) else None
                    if not o or not o.get('_type', '').endswith('View'):
                        avisos.append(f'{dg.get("name")}: la linea {v["_id"]} ({t}) no tiene {k} valido')
    return avisos
