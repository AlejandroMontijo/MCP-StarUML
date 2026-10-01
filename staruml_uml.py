# Motor generico para todos los diagramas y simbolos de StarUML (UML 2.5 y las extensiones: BPMN, SysML, C4, ERD,
# flowchart, DFD, wireframe, mindmap, AWS y GCP). Se apoya en dos tablas que salen del StarUML instalado:
#  - staruml_metamodelo.json (herramientas/extraer_metamodelo.py): tipos, herencia, atributos, vistas por diagrama y
#    la paleta de cada diagrama.
#  - plantillas_vistas.json (herramientas/generar_referencia.py + extraer_plantillas.py): lo que StarUML crea al dibujar
#    cada simbolo de cada paleta y al crear cada tipo de diagrama, con los ids cambiados por marcadores.
# Dibujar un simbolo es instanciar su plantilla: ids nuevos, marcadores resueltos (@dueno, @diagrama, @cola, @cabeza),
# geometria movida al lugar pedido y el nombre puesto. Asi el archivo queda como si el simbolo se hubiera dibujado en
# StarUML, y Doc.save() sigue rechazando cualquier cambio que deje ids o referencias rotas.
import copy
import json
import os
import re
import unicodedata

import staruml_mdj as M
from staruml_mdj import MdjError, ref

HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE = {}

# nombres cortos de diagrama (los tres primeros los resuelve staruml_mdj.crear_diagrama como siempre)
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
        ruta = os.path.join(HERE, nombre)
        if not os.path.exists(ruta):
            raise MdjError(f'Falta {nombre}; se genera con los scripts de herramientas/')
        with open(ruta, encoding='utf-8') as f:
            _CACHE[nombre] = json.load(f)
    return _CACHE[nombre]


def metamodelo():
    return _tabla('staruml_metamodelo.json')


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
    return {'tipo': t, 'alias': inv.get(t), 'simbolos': simbolos, 'sin_plantilla': nd}


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
    Si es una linea que crea otro elemento con nombre por omision (la clase de una clase asociacion), ese tambien
    toma el nombre: en UML son el mismo elemento."""
    mid = nuevos.get(p.get('modelo'))
    if not mid or not nombre:
        return
    cambiar = [doc.get(mid)]
    if p['forma'] == 'line':
        cambiar += [doc.ids[i] for i in nuevos.values() if doc.ids.get(i) is not None and i != mid
                    and not doc.ids[i].get('_type', '').endswith('View')
                    and re.fullmatch(r'[A-Za-z]+\d+', str(doc.ids[i].get('name') or ''))
                    and es_subtipo(doc.ids[i]['_type'], 'UMLClassifier')]
    for el in cambiar:
        viejo = el.get('name')
        el['name'] = nombre
        if not viejo:
            continue
        for i in nuevos.values():
            o = doc.ids.get(i)
            if o and o.get('_type', '').endswith('View') and isinstance(o.get('text'), str) and viejo in o['text']:
                o['text'] = o['text'].replace(viejo, nombre)


# ---------------------------------------------------------------------------
# Diagramas y simbolos
# ---------------------------------------------------------------------------

def crear_diagrama(doc, tipo_dg, nombre, dentro_de=None, por_defecto=False):
    """Cualquier diagrama de StarUML, con lo que StarUML crea junto con el (interaccion, maquina de estados, marco...)."""
    t = tipo_diagrama(tipo_dg)
    if t in ('UMLClassDiagram', 'UMLUseCaseDiagram', 'UMLSequenceDiagram'):
        alias = {v: k for k, v in ALIAS_DIAGRAMA.items()}[t]
        return M.crear_diagrama(doc, alias, nombre, dentro_de, por_defecto), []
    p = plantillas().get('diagramas', {}).get(t)
    if not p:
        raise MdjError(f'No hay plantilla para crear {t}')
    padre = doc.find(dentro_de) if dentro_de else M.modelo_raiz(doc)
    dueno = p.get('dueno')
    if dueno and dueno != 'UMLPackage' and not es_subtipo(padre['_type'], dueno):
        # StarUML solo admite este diagrama dentro de un elemento de cierto tipo (bloque interno -> SysMLBlock)
        padre = crear_elemento(doc, dueno, nombre, padre['_id'])
    nuevos, avisos = instanciar(doc, p, cadena(doc, padre['_id']))
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


def _ruta_lateral(t, h, medios):
    """Como M.ruta, pero si un extremo lleva el nombre abajo y la linea le llega desde abajo, entra por un costado a
    la altura de la figura (asi no cruza el nombre)."""
    medios = [tuple(m) for m in medios or ()]
    ft, fh = _figura(t), _figura(h)
    if ft is None and fh is None:
        return M.ruta(t, h, medios)
    caja_t, caja_h = ft or t, fh or h

    def lateral(fig, otro_pt):
        cx, cy = fig['left'] + fig['width'] / 2, fig['top'] + fig['height'] / 2
        if otro_pt[1] <= fig['top'] + fig['height']:
            return None
        lado = fig['left'] + fig['width'] + 30 if otro_pt[0] >= cx else fig['left'] - 30
        return (round(lado), round(cy))
    lejos_t = medios[0] if medios else M.centro(h)
    lejos_h = medios[-1] if medios else M.centro(t)
    if ft is not None:
        m = lateral(ft, lejos_t)
        if m:
            medios = [m, (m[0], round(lejos_t[1]))] + medios if not medios else [m] + medios
    if fh is not None:
        m = lateral(fh, lejos_h)
        if m:
            medios = medios + ([(m[0], round(lejos_h[1])), m] if len(medios) == 0 or medios[-1][0] != m[0] else [m])
    return M.ruta(caja_t, caja_h, medios)


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
                 'SysMLSatisfy': 'satisfy', 'SysMLVerify': 'verify', 'SysMLRefine': 'refine', 'SysMLTrace': 'trace'}


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

    import staruml_programa as P
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


def _ajustar(v, tipo_vista):
    """La vista donde StarUML engancha el simbolo: la dada o, si la plantilla espera otro tipo, una subvista suya de
    ese tipo (un mensaje se engancha a la linea punteada de la lifeline, no a la caja)."""
    if v is None or not tipo_vista or v['_type'] == tipo_vista:
        return v
    pila = list(v.get('subViews', []))
    while pila:
        s = pila.pop(0)
        if s.get('_type') == tipo_vista:
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


def dibujar(doc, diagrama, simbolo, nombre=None, x=None, y=None, ancho=None, alto=None, desde=None, hasta=None,
            sobre=None, medios=()):
    """Dibuja un simbolo de la paleta como lo haria StarUML: crea el elemento de modelo y su vista.
    Cajas: en (x, y) o en el primer lugar libre; 'sobre' es la vista o elemento donde va (puerto sobre componente,
    estado dentro de region, pin sobre accion, lifeline dentro del marco de tiempos...). Lineas: 'desde' y 'hasta'."""
    dg = doc.diagram(diagrama)
    clave, p = plantilla_simbolo(dg['_type'], simbolo)
    marc = dict(cadena(doc, dg['_parent']['$ref']), **{'@diagrama': dg['_id']})
    vc = vh = None
    usa_cola, usa_cabeza = necesita(p)
    etiqueta = clave.split('|')[0]
    if p['forma'] == 'line':
        # un mensaje encontrado no tiene origen y uno perdido no tiene destino: se pide solo lo que la plantilla usa
        falta = [n for n, usa, v in (('desde', usa_cola, desde), ('hasta', usa_cabeza, hasta)) if usa and v is None]
        if falta:
            raise MdjError(f'{etiqueta} es una linea: indica {" y ".join(falta)}')
        vc = _ajustar(_vista(doc, dg, desde), p.get('cola')) if usa_cola else None
        vh = _ajustar(_vista(doc, dg, hasta), p.get('cabeza')) if usa_cabeza else None
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
    v = doc.get(nuevos[p['principal']])
    if p['forma'] == 'line':
        if vc is not None:
            v['tail'] = ref(vc['_id'])
        if vh is not None:
            v['head'] = ref(vh['_id'])
        _rutear(doc, nuevos, v, medios)
        _acomodar_lo_que_crea(doc, nuevos, v)
        _separar_nombre(doc, v, nombre)
    else:
        if ancho is not None:
            v['width'] = ancho
        if alto is not None:
            v['height'] = alto
    doc.reindex()
    m = v.get('model', {}).get('$ref') if isinstance(v.get('model'), dict) else None
    return {'simbolo': clave.split('|')[0], 'vista': v['_id'], 'vista_tipo': v['_type'], 'elemento': m,
            'elemento_tipo': doc.ids[m]['_type'] if m in doc.ids and doc.ids[m] else None, 'avisos': avisos}


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


def vista_de(doc, diagrama, elemento, x=None, y=None, ancho=None, alto=None, desde=None, hasta=None, medios=()):
    """Dibuja en el diagrama un elemento que ya existe (cualquier tipo con simbolo en la paleta del diagrama):
    se usan solo las vistas de la plantilla de su tipo, apuntando al elemento existente."""
    dg = doc.diagram(diagrama)
    el = doc.find(elemento)
    if doc.views_of(el['_id'], dg):
        raise MdjError(f'{el.get("name") or el["_type"]} ya tiene vista en {dg.get("name")}')
    pl = plantillas()['plantillas'].get(dg['_type'], {})
    elegida = None
    for clave, p in pl.items():
        raiz = next((e['objeto'] for e in p['objetos'] if e['objeto'].get('_id') == p.get('modelo')), None)
        if not raiz or raiz['_type'] != el['_type']:
            continue
        # el elemento de la plantilla y el existente se recorren juntos: sus partes (extremos de una relacion...)
        # quedan apuntando a las del existente
        mapa = {}
        _emparejar(raiz, el, mapa)
        vistas = [e for e in p['objetos'] if es_subtipo(e['objeto']['_type'], 'View')]
        internos = set().union(*(_ids_plantilla(e['objeto']) for e in vistas)) if vistas else set()
        sueltas = {m for e in vistas for m in _marcas(e['objeto'])} - internos - set(mapa)
        sueltas = {m for m in sueltas if not m.startswith(('@diagrama', '@dueno', '@cola', '@cabeza', '@ext:'))}
        if vistas and not sueltas:
            elegida = (clave, dict(p, objetos=vistas), mapa)
            break
    if not elegida:
        raise MdjError(f'{dg["_type"]} no tiene un simbolo para dibujar un {el["_type"]} existente')
    clave, p, mapa = elegida
    marc = dict(cadena(doc, dg['_parent']['$ref']), **{'@diagrama': dg['_id']}, **mapa)
    vc = vh = None
    if p['forma'] == 'line':
        if desde is None or hasta is None:
            raise MdjError(f'{el["_type"]} se dibuja como linea: indica desde y hasta')
        vc, vh = _vista(doc, dg, desde), _vista(doc, dg, hasta)
        dx = dy = 0
    else:
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
        _rutear(doc, nuevos, v, medios)
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
    if w >= 40 and (h >= 25 or w >= 2 * h):  # caja con texto (una tarea BPMN es ancha y baja); no un icono
        # StarUML escribe los nombres en negritas (~15% mas anchas que Arial normal)
        w = max(w, round(M.ancho13(nombre or '') * 1.15 + 44), 120)
        h = max(h, 60)
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
    if pm.get('regions') and es_subtipo(hm['_type'], 'UMLVertex'):
        destino, campo = pm['regions'][0], 'vertices'
    else:
        at = campo_para(pm['_type'], hm['_type'])
        campo = at['name'] if at and at['kind'] == 'objs' else None
    if not campo:
        return
    viejo = doc.ids[doc.parent[hm['_id']]]
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
    return (v.get('width') or 99) <= 30 and (v.get('height') or 99) <= 30 or         any(x in p['vista'] for x in ('PortView', 'PinView', 'ExpansionNodeView'))


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
    import staruml_programa as P
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
            if rel.get(c) is not None and str(rel[c]) not in claves and str(rel[c]) not in rclaves                     and existente(str(rel[c])) is None:
                raise MdjError(f'relacion {rel["simbolo"]}: {c} "{rel[c]}" no es un elemento de la lista ni esta '
                               f'dibujado en {dg.get("name")}')

    def padre_de(el):
        r_ = el.get('dentro') if el.get('dentro') is not None else el.get('sobre')
        return claves.get(str(r_)) if r_ is not None else None

    def dentro_de(el):
        """Contenedores (por 'dentro', no 'sobre') de un elemento, del mas cercano al mas lejano."""
        res = []
        while el is not None:
            es_dentro = el.get('dentro') is not None
            el = padre_de(el)
            if el is not None and es_dentro:
                res.append(el['_k'])
        return res

    def raiz_de(el):
        while padre_de(el) is not None:
            el = padre_de(el)
        return el

    def arista(rel, miembros):
        a, b = claves.get(str(rel.get('desde'))), claves.get(str(rel.get('hasta')))
        # se sube cada extremo hasta el nivel que se esta acomodando
        while a and a['_k'] not in miembros:
            a = padre_de(a)
        while b and b['_k'] not in miembros:
            b = padre_de(b)
        if not a or not b or a is b:
            return None
        # la generalizacion va al reves y manda: la clase base arriba de sus derivadas. Las realizaciones no: StarUML
        # dibuja la interfaz como una bola con el nombre debajo, y una linea que llega desde abajo cruza el nombre;
        # con quien la provee y quien la requiere arriba, las dos llegan a la bola sin tocarlo
        if _invierte_capas(tipo_dg, rel.get('simbolo')):
            return (b['_k'], a['_k'], True)
        return (a['_k'], b['_k'], False)

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
    if disposicion == 'secuencia':
        # lifelines en fila, en el orden de la lista, tan altas como lo pidan los mensajes; lo que va pegado a una
        # lifeline (auto-mensaje, invariante) toma su turno despues de los mensajes; lo demas (fragmentos,
        # continuaciones, restricciones...) va en una fila debajo
        n_msj = sum(1 for r in rels if r['_p']['forma'] == 'line')
        pegados = [c for el in raices if _es_lifeline(el['_p']) for c in el['_sobre']
                   if c.get('x') is None or c.get('y') is None]
        alto_ll = 160 + 45 * (n_msj + len(pegados))
        x, pos = 40, {}
        for el in [e for e in raices if _es_lifeline(e['_p'])]:
            pos[el['_k']] = (x, 60)
            if not el.get('alto') and 'Seq' in el['_p']['vista']:
                el['_tam'] = (el['_tam'][0], max(el['_tam'][1], alto_ll))
            x += el['_tam'][0] + 50
        for j, c in enumerate(pegados):
            ll = padre_de(c)
            c['x'] = pos[ll['_k']][0] + ll['_tam'][0] // 2 - 7
            c['y'] = 180 + 45 * (n_msj + j)
        x, y_otros = 40, 60 + alto_ll + 40
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
    vistas = {}

    def vista_de_ref(spec):
        spec = str(spec)
        return vistas[spec] if spec in vistas else existente(spec)

    def poner_sobre(c, v, i, n, x, y, w, h, hijos=(), dueno=None):
        """Algo pegado a otra vista: en el borde derecho repartido a lo alto (puertos, pines), o en x, y si se dio."""
        borde = [cc for cc in (dueno['_sobre'] if dueno else [c]) if _de_borde(cc['_p'])]
        if c.get('x') is not None and c.get('y') is not None:
            px, py = c['x'], c['y']
        elif dueno and c['_k'] in dueno.get('_relsobre', {}):
            rx, ry = dueno['_relsobre'][c['_k']]
            px, py = x + rx, y + ry
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
        rs = dibujar(doc, dg['_id'], c['_clave'], c.get('nombre'), px, py, tw if interior else c.get('ancho'),
                     th if interior else c.get('alto'), sobre=v['_id'])
        vv = doc.get(rs['vista'])
        vistas[c['_k']] = vv
        for j, cc in enumerate(c['_sobre']):
            poner_sobre(cc, vv, j, len(c['_sobre']), vv.get('left', px), vv.get('top', py),
                        vv.get('width', 20), vv.get('height', 20), dueno=c)

    def poner(el, x, y, padre_v=None):
        r = dibujar(doc, dg['_id'], el['_clave'], el.get('nombre'), x, y, *el['_tam'])
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
            poner_sobre(el, destino, 0, 1, destino.get('left', 0), destino.get('top', 0),
                        destino.get('width', 100), destino.get('height', 100))
        else:
            medir(el)
            x = el['x'] if el.get('x') is not None else destino['left'] + PAD_X
            y = el['y'] if el.get('y') is not None else destino['top'] + PAD_ARRIBA
            poner(el, x, y, destino)
    cajas = {k: P._caja(vistas[k]) for k in miembros}
    medios_de = P.rutas(cajas, geometrias) if geometrias else {}
    sentido = {frozenset(par): par for geo in geometrias for par in list(geo['cadenas']) + geo['mismas']}
    lineas, cruzan, avisos = [], [], []
    y_msj = 180

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
        r = dibujar(doc, dg['_id'], rel['_clave'], rel.get('nombre'), desde=va and va['_id'], hasta=vb and vb['_id'],
                    medios=medios)
        v = doc.get(r['vista'])
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
            r = dibujar(doc, dg['_id'], el['_clave'], el.get('nombre'), x0 - m, y0 - m - 20,
                        x1 - x0 + 2 * m, y1 - y0 + 2 * m + 20)
            vistas[el['_k']] = doc.get(r['vista'])
            x0, y0, x1, y1 = x0 - m, y0 - m - 20, x1 + m, y1 + m
            m = 20
    doc.reindex()
    res = {'diagrama': dg.get('name'), 'id': dg['_id'], 'cajas': len(vistas) - len(lineas), 'lineas': len(lineas),
           'vistas': {k: v['_id'] for k, v in vistas.items()}, 'lineas_que_cruzan_cajas': cruzan}
    if avisos:
        res['avisos'] = avisos
    return res


def _centro_linea(v):
    pts = [tuple(map(float, p.split(':'))) for p in (v.get('points') or '0:0').split(';')]
    return round((pts[0][0] + pts[-1][0]) / 2), round((pts[0][1] + pts[-1][1]) / 2)


def _mensaje_en(doc, v, y):
    """Mensaje de secuencia a la altura y: horizontal entre las lineas punteadas de sus lifelines (o hacia un lado
    si no tiene origen o destino); su activacion, si la trae, empieza ahi."""
    if not isinstance(v.get('points'), str):
        return
    t = doc.ids.get((v.get('tail') or {}).get('$ref'))
    h = doc.ids.get((v.get('head') or {}).get('$ref'))
    xt = t['left'] + t['width'] / 2 if _es_caja(t) else None
    xh = h['left'] + h['width'] / 2 if _es_caja(h) else None
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


def campo_para(padre_tipo, hijo_tipo):
    """Campo (objs/obj) del padre donde cabe un hijo de ese tipo; ownedElements si hay varios."""
    cands = [a for a in atributos(padre_tipo) if a['kind'] in ('objs', 'obj') and es_subtipo(hijo_tipo, a['type'])]
    if not cands:
        return None
    return next((a for a in cands if a['name'] == 'ownedElements'), cands[0])


def crear_elemento(doc, t, nombre=None, dentro_de=None, campo=None, props=None):
    """Elemento de modelo de cualquier tipo, validado contra el metamodelo (sin vista)."""
    info = tipo(t)
    if not info or info['kind'] != 'class' or not es_subtipo(t, 'Model') or es_abstracto(t):
        raise MdjError(f'{t} no es un tipo de elemento de StarUML que se pueda crear')
    padre = doc.find(dentro_de) if dentro_de else M.modelo_raiz(doc)
    at = atributo(padre['_type'], campo) if campo else campo_para(padre['_type'], t)
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


def crear_relacion(doc, t, origen, destino, nombre=None, dueno=None, props=None):
    """Relacion de cualquier tipo entre dos elementos: dirigida (source/target) o con extremos (end1/end2)."""
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
    # dueno: el indicado, o el primero hacia arriba desde el origen que pueda contenerlo
    cands = [doc.find(dueno)] if dueno else []
    i = a['_id']
    while not dueno and i:
        cands.append(doc.ids[i])
        i = doc.parent.get(i)
    for c in cands:
        at = campo_para(c['_type'], t)
        if at:
            el['_parent'] = ref(c['_id'])
            if at['kind'] == 'objs':
                c.setdefault(at['name'], []).append(el)
            else:
                c[at['name']] = el
            doc.reindex()
            return el
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
