# Ingenieria inversa: diagrama de clases de un programa ya hecho (Java por defecto, y los demas lenguajes que entiende
# staruml_compare). Crea paquetes, clases, interfaces y enumeraciones con atributos y metodos (visibilidad, static,
# abstract), herencia, interfaces implementadas, asociaciones que salen de los campos y, si se pide, dependencias.
# Acomoda las cajas por niveles de herencia sin encimarlas y rutea las lineas para que no crucen otras cajas.
import base64
import math
import os
import re
import time

import staruml_compare as C
import staruml_mdj as M
from staruml_mdj import MdjError, ref

SIMBOLO = {'public': '+', 'private': '-', 'protected': '#', 'package': '~', 'internal': '~'}
_DIRS_PRUEBAS = {'test', 'tests', '__tests__', 'androidTest', 'testFixtures'}
# PedidoTest.java, PedidoIT.java, test_pedido.py, pedido.spec.ts... (una clase llamada solo Test si entra)
_ARCH_PRUEBAS = re.compile(r'.(Test|Tests|IT)\.(java|kt|cs)$|^test_.*\.py$|_test\.(py|go)$|\.(test|spec)\.(ts|tsx|js|jsx)$')
_NO_CLASES = set(C._PRIMITIVOS) | {'List', 'Set', 'Map'}
VISTA_DE = {'UMLClass': 'UMLClassView', 'UMLInterface': 'UMLInterfaceView', 'UMLEnumeration': 'UMLEnumerationView'}
VISTA_RELACION = {'UMLGeneralization': 'UMLGeneralizationView', 'UMLInterfaceRealization': 'UMLInterfaceRealizationView',
                  'UMLDependency': 'UMLDependencyView'}


# ---------------------------------------------------------------------------
# Lectura del programa
# ---------------------------------------------------------------------------

def leer_programa(ruta, lenguaje='java', incluir_pruebas=False):
    """Clases del programa por nombre calificado (paquete.Nombre). A diferencia de escanear_codigo no se pierden las
    que se llaman igual en paquetes distintos. Sin incluir_pruebas se omiten las carpetas y archivos de pruebas."""
    ruta = os.path.abspath(os.path.expanduser(ruta))
    if lenguaje != 'auto' and lenguaje not in C._EXTENSIONES:
        raise MdjError(f'Lenguaje no soportado: {lenguaje}. Validos: auto, {", ".join(C._EXTENSIONES)}')
    exts = tuple(C._LENGUAJE_DE) if lenguaje == 'auto' else C._EXTENSIONES[lenguaje]
    if os.path.isfile(ruta):
        archivos = [ruta]
    elif os.path.isdir(ruta):
        archivos = []
        for raiz, dirs, files in os.walk(ruta):
            dirs[:] = sorted(d for d in dirs if d not in C._NO_ESCANEAR and not d.endswith('.egg-info')
                             and (incluir_pruebas or d not in _DIRS_PRUEBAS))
            for f in sorted(files):
                if f.lower().endswith(exts) and not f.endswith(('.min.js', '.d.ts')) and (incluir_pruebas or not _ARCH_PRUEBAS.search(f)):
                    archivos.append(os.path.join(raiz, f))
    else:
        raise MdjError(f'La ruta de codigo no existe: {ruta}')
    clases, repetidas = {}, []
    for a in archivos:
        for nom, info in C.CodeParser.parse_archivo(a, lenguaje).items():
            q = f'{info["paquete"]}.{nom}' if info.get('paquete') else nom
            if q in clases:
                repetidas.append(q)
                continue
            clases[q] = info
    return clases, repetidas


class _Resolutor:
    """Nombre de tipo del codigo -> clase del programa (nombre calificado), prefiriendo la del mismo paquete."""

    def __init__(self, clases):
        self.clases = clases
        self.por_nombre = {}
        for q, info in clases.items():
            self.por_nombre.setdefault(info['nombre'], []).append(q)

    def __call__(self, nombre, paquete):
        if nombre in self.clases:
            return nombre
        cands = self.por_nombre.get(nombre.split('.')[-1], [])
        if len(cands) > 1:
            cands = [q for q in cands if self.clases[q].get('paquete') == paquete] or sorted(cands)
        return cands[0] if cands else None

    def en_tipo(self, tipo, paquete):
        """Clases del programa que aparecen en un tipo (normalizado), en orden: List<Pedido> -> [Pedido]."""
        out = []
        for n in re.findall(r'[^\W\d][\w$.]*', tipo or ''):
            q = self(n, paquete) if n not in _NO_CLASES else None
            if q and q not in out:
                out.append(q)
        return out


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

def _nuevo_id(estado=[int(time.time() * 1000) - 900000]):
    estado[0] += 3
    return base64.b64encode(b'\x00' * 4 + estado[0].to_bytes(6, 'big') + os.urandom(4)).decode()


def proyecto_nuevo(nombre):
    """Proyecto vacio de StarUML (Project > UMLModel)."""
    pid, mid = _nuevo_id(), _nuevo_id()
    return {'_type': 'Project', '_id': pid, 'name': nombre,
            'ownedElements': [{'_type': 'UMLModel', '_id': mid, '_parent': {'$ref': pid}, 'name': 'Model'}]}


def _es_accesor(m, campos):
    n = m['nombre']
    for pre in ('get', 'set', 'is'):
        if n.startswith(pre) and len(n) > len(pre) and n[len(pre)].isupper() and (n[len(pre)].lower() + n[len(pre) + 1:]) in campos:
            return True
    return False


def _tipo(doc_tipo, original, resolver, paquete, elems):
    """Tipo de un atributo o parametro: referencia a la clase del programa si es exactamente una, si no el texto."""
    if doc_tipo and doc_tipo not in ('Object',) and re.fullmatch(r'[^\W\d][\w$.]*', doc_tipo):
        q = resolver(doc_tipo, paquete) if doc_tipo not in _NO_CLASES else None
        if q in elems:
            return ref(elems[q]['_id'])
    texto = (original or doc_tipo or '').strip()
    return '' if texto in ('Object', 'var') else texto


def construir(doc, clases, raiz_nombre, op):
    """Crea el paquete raiz con los paquetes, clasificadores y relaciones del programa. Devuelve lo creado."""
    modelo = M.modelo_raiz(doc)
    raiz = {'_type': 'UMLPackage', '_id': doc.new_id(), '_parent': ref(modelo['_id']), 'name': raiz_nombre}
    modelo.setdefault('ownedElements', []).append(raiz)
    paquetes = {'': raiz}

    def paquete(nombre):
        if nombre not in paquetes:
            padre_nom, _, hoja = nombre.rpartition('.')
            padre = paquete(padre_nom)
            pk = {'_type': 'UMLPackage', '_id': doc.new_id(), '_parent': ref(padre['_id']), 'name': hoja}
            padre.setdefault('ownedElements', []).append(pk)
            paquetes[nombre] = pk
        return paquetes[nombre]

    elems = {}
    for q in sorted(clases):
        info = clases[q]
        tipo = {'interface': 'UMLInterface', 'enum': 'UMLEnumeration'}.get(info.get('tipo_decl'), 'UMLClass')
        pk = paquete(info.get('paquete') or '')
        el = {'_type': tipo, '_id': doc.new_id(), '_parent': ref(pk['_id']), 'name': info['nombre']}
        if info.get('abstracta'):
            el['isAbstract'] = True
        pk.setdefault('ownedElements', []).append(el)
        elems[q] = el
    resolver = _Resolutor(clases)

    candidatas = []  # asociaciones que salen de campos: (origen, destino, rol, multiplicidad)
    for q, info in clases.items():
        el, pkq = elems[q], info.get('paquete') or ''
        if el['_type'] == 'UMLEnumeration' and info.get('literales'):
            el['literals'] = [{'_type': 'UMLEnumerationLiteral', '_id': doc.new_id(), '_parent': ref(el['_id']), 'name': l}
                              for l in info['literales']]
        attrs = []
        for a in info.get('atributos', []):
            # los campos de instancia son asociaciones; las constantes y campos static (en una interfaz de Java
            # todos lo son) quedan como atributos
            estatico = a.get('estatico') or (info.get('tipo_decl') == 'interface' and info.get('lenguaje') == 'java')
            destinos = resolver.en_tipo(a.get('tipo'), pkq) if op['asociaciones'] and not estatico else []
            if destinos:
                candidatas.append((q, destinos[-1], a['nombre'], '0..*' if C._es_coleccion_tipo(a['tipo']) else '1'))
                continue
            if not op['atributos'] or (op['solo_publicos'] and a.get('visibilidad') != 'public'):
                continue
            at = {'_type': 'UMLAttribute', '_id': doc.new_id(), '_parent': ref(el['_id']), 'name': a['nombre']}
            if a.get('visibilidad', 'public') != 'public':
                at['visibility'] = 'package' if a['visibilidad'] == 'internal' else a['visibilidad']
            if estatico:
                at['isStatic'] = True
            if a.get('final'):
                at['isReadOnly'] = True
            t = _tipo(a.get('tipo'), a.get('tipo_original'), resolver, pkq, elems)
            if t:
                at['type'] = t
            attrs.append(at)
        if attrs:
            el['attributes'] = attrs
        if op['metodos']:
            campos = {a['nombre'] for a in info.get('atributos', [])}
            ops = []
            for m in info.get('metodos', []):
                if (op['solo_publicos'] and m.get('visibilidad') not in ('public', None)) or \
                        (op['omitir_accesores'] and _es_accesor(m, campos)):
                    continue
                o = {'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': ref(el['_id']), 'name': m['nombre']}
                vis = m.get('visibilidad', 'public')
                if vis not in ('public', None):
                    o['visibility'] = 'package' if vis == 'internal' else vis
                if m.get('estatico'):
                    o['isStatic'] = True
                if m.get('abstracto'):
                    o['isAbstract'] = True
                params = []
                for p in m.get('parametros', []):
                    pa = {'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': ref(o['_id']), 'name': p['nombre']}
                    t = _tipo(p.get('tipo'), p.get('tipo_original'), resolver, pkq, elems)
                    if t:
                        pa['type'] = t
                    params.append(pa)
                if m.get('retorno') not in ('void', None):
                    pa = {'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': ref(o['_id']), 'direction': 'return'}
                    t = _tipo(m.get('retorno'), m.get('retorno_original'), resolver, pkq, elems)
                    if t:
                        pa['type'] = t
                    params.append(pa)
                if params:
                    o['parameters'] = params
                ops.append(o)
            if ops:
                el['operations'] = ops
    doc.reindex()

    relaciones, externas = [], {}

    def relacion(tipo, origen, destino):
        r = {'_type': tipo, '_id': doc.new_id(), '_parent': ref(elems[origen]['_id']),
             'source': ref(elems[origen]['_id']), 'target': ref(elems[destino]['_id'])}
        elems[origen].setdefault('ownedElements', []).append(r)
        relaciones.append((r, origen, destino))

    for q, info in clases.items():
        es_interfaz = elems[q]['_type'] == 'UMLInterface'
        for base in info.get('superclases', []) + info.get('interfaces', []):
            t = resolver(base, info.get('paquete') or '')
            if not t or t == q:
                externas.setdefault(info['nombre'], []).append(base)
                continue
            destino_interfaz = elems[t]['_type'] == 'UMLInterface'
            relacion('UMLInterfaceRealization' if destino_interfaz and not es_interfaz else 'UMLGeneralization', q, t)

    # un campo en cada sentido entre dos clases: una sola asociacion navegable en ambos sentidos
    por_par = {}
    for c in candidatas:
        por_par.setdefault((c[0], c[1]), []).append(c)
    hechas = set()
    for (a, b), lista in por_par.items():
        if (a, b) in hechas:
            continue
        inversa = por_par.get((b, a), [])
        if a != b and len(lista) == 1 and len(inversa) == 1:
            _, _, rol_b, mult_b = lista[0]
            _, _, rol_a, mult_a = inversa[0]
            asoc = M.asociacion_crear(doc, elems[a], elems[b], m1=mult_a, m2=mult_b, rol1=rol_a, rol2=rol_b, navegable='ambos')
            relaciones.append((asoc, a, b))
            hechas.update({(a, b), (b, a)})
            continue
        for _, _, rol, mult in lista:
            asoc = M.asociacion_crear(doc, elems[a], elems[b], m2=mult, rol2=rol, navegable='hacia')
            relaciones.append((asoc, a, b))
        hechas.add((a, b))

    if op['dependencias']:
        unidos = {frozenset((o, d)) for _, o, d in relaciones}
        for q, info in clases.items():
            usados = []
            for m in info.get('metodos', []):
                for t in [m.get('retorno')] + [p.get('tipo') for p in m.get('parametros', [])]:
                    usados += [d for d in resolver.en_tipo(t, info.get('paquete') or '') if d != q and d not in usados]
            for d in usados:
                if frozenset((q, d)) not in unidos:
                    relacion('UMLDependency', q, d)
                    unidos.add(frozenset((q, d)))
    doc.reindex()
    return {'raiz': raiz, 'paquetes': paquetes, 'elementos': elems, 'relaciones': relaciones, 'herencia_externa': externas}


# ---------------------------------------------------------------------------
# Tamano y vistas de los clasificadores
# ---------------------------------------------------------------------------

def _texto_tipo(doc, t):
    if isinstance(t, dict):
        return doc.name_of(t.get('$ref'))
    return t or ''


def textos(doc, el):
    """Lineas que StarUML muestra en cada compartimento."""
    attrs = []
    for a in el.get('attributes', []):
        t = _texto_tipo(doc, a.get('type'))
        attrs.append(f'{SIMBOLO.get(a.get("visibility", "public"), "+")}{a.get("name", "")}' + (f': {t}' if t else ''))
    ops = []
    for o in el.get('operations', []):
        ps = [p for p in o.get('parameters', []) if p.get('direction') != 'return']
        ret = next((p for p in o.get('parameters', []) if p.get('direction') == 'return'), None)
        firma = ', '.join(p.get('name', '') + (f': {_texto_tipo(doc, p.get("type"))}' if p.get('type') else '') for p in ps)
        rt = _texto_tipo(doc, ret.get('type')) if ret else ''
        ops.append(f'{SIMBOLO.get(o.get("visibility", "public"), "+")}{o.get("name", "")}({firma})' + (f': {rt}' if rt else ''))
    lits = [l.get('name', '') for l in el.get('literals', [])]
    return attrs, ops, lits


def medir(doc, el, op):
    """(ancho, alto) de la caja: generosos, porque StarUML agranda una caja chica pero no achica una grande."""
    attrs, ops, lits = textos(doc, el)
    estereotipo = {'UMLInterface': '«interface»', 'UMLEnumeration': '«enumeration»'}.get(el['_type'])
    lineas = attrs + ops + lits + ([estereotipo] if estereotipo else [])
    ancho = max([M.ancho13(el.get('name', '')) * 1.12] + [M.ancho13(t) for t in lineas]) + 26
    alto = 27 + (15 if estereotipo else 0)
    for items, visible in _compartimentos(el, attrs, ops, lits, op):
        if visible:
            alto += 15 * len(items) + 10
    return max(110, round(ancho)), round(alto)


def _compartimentos(el, attrs, ops, lits, op):
    """[(items, visible)] en el orden de StarUML: literales (enumeraciones), atributos, operaciones."""
    t = el['_type']
    out = []
    if t == 'UMLEnumeration':
        out.append((lits, True))
    out.append((attrs, bool(attrs) or (t == 'UMLClass' and op['atributos'])))
    out.append((ops, bool(ops) or (t == 'UMLClass' and op['metodos'])))
    return out


def vista_clasificador(doc, dg, el, x, y, ancho, alto, op):
    """Vista de clase, interfaz o enumeracion en notacion de etiqueta, con todos sus compartimentos."""
    attrs, ops, lits = textos(doc, el)
    vid, ncid = doc.new_id(), doc.new_id()
    labs = [doc.new_id() for _ in range(4)]
    estereotipo = {'UMLInterface': '«interface»', 'UMLEnumeration': '«enumeration»'}.get(el['_type'])
    alto_nombre = 27 + (15 if estereotipo else 0)
    et = {'_type': 'LabelView', '_id': labs[0], '_parent': ref(ncid), 'font': 'Arial;13;0', 'parentStyle': True,
          'left': x + 5, 'top': y + 5, 'width': ancho - 9, 'height': 13}
    if estereotipo:
        et['text'] = estereotipo
    else:
        et['visible'] = False
    nc = {'_type': 'UMLNameCompartmentView', '_id': ncid, '_parent': ref(vid), 'model': ref(el['_id']),
          'subViews': [et,
                       {'_type': 'LabelView', '_id': labs[1], '_parent': ref(ncid), 'font': 'Arial;13;3' if el.get('isAbstract') else 'Arial;13;1',
                        'parentStyle': True, 'left': x + 5, 'top': y + alto_nombre - 20, 'width': ancho - 9, 'height': 13,
                        'text': el.get('name', '')},
                       {'_type': 'LabelView', '_id': labs[2], '_parent': ref(ncid), 'visible': False, 'font': 'Arial;13;0',
                        'parentStyle': True, 'left': x, 'top': y, 'height': 13},
                       {'_type': 'LabelView', '_id': labs[3], '_parent': ref(ncid), 'visible': False, 'font': 'Arial;13;0',
                        'parentStyle': True, 'left': x, 'top': y, 'height': 13, 'horizontalAlignment': 1}],
          'font': 'Arial;13;0', 'parentStyle': True, 'left': x, 'top': y, 'width': ancho, 'height': alto_nombre,
          'stereotypeLabel': ref(labs[0]), 'nameLabel': ref(labs[1]), 'namespaceLabel': ref(labs[2]), 'propertyLabel': ref(labs[3])}

    def compartimento(tipo, tipo_item, modelos, items, visible, top):
        cid = doc.new_id()
        c = {'_type': tipo, '_id': cid, '_parent': ref(vid), 'model': ref(el['_id'])}
        if not visible:
            c['visible'] = False
        subs = [{'_type': tipo_item, '_id': doc.new_id(), '_parent': ref(cid), 'model': ref(m['_id']), 'font': 'Arial;13;0',
                 'parentStyle': True, 'left': x + 5, 'top': top + 5 + 15 * i, 'width': ancho - 9, 'height': 13,
                 'text': t, 'horizontalAlignment': 0} for i, (m, t) in enumerate(zip(modelos, items))] if visible else []
        if subs:
            c['subViews'] = subs
        c.update({'font': 'Arial;13;0', 'parentStyle': True, 'left': x, 'top': top, 'width': ancho,
                  'height': 15 * len(items) + 10 if visible else 10})
        return c

    subs, top, campos = [nc], y + alto_nombre, {}
    for (items, visible), (clave, tipo, tipo_item, modelos) in zip(
            _compartimentos(el, attrs, ops, lits, op),
            ([('enumerationLiteralCompartment', 'UMLEnumerationLiteralCompartmentView', 'UMLEnumerationLiteralView', el.get('literals', []))]
             if el['_type'] == 'UMLEnumeration' else []) +
            [('attributeCompartment', 'UMLAttributeCompartmentView', 'UMLAttributeView', el.get('attributes', [])),
             ('operationCompartment', 'UMLOperationCompartmentView', 'UMLOperationView', el.get('operations', []))]):
        c = compartimento(tipo, tipo_item, modelos, items, visible, top)
        subs.append(c)
        campos[clave] = c
        if visible:
            top += c['height']
    for clave, tipo in (('receptionCompartment', 'UMLReceptionCompartmentView'),
                        ('templateParameterCompartment', 'UMLTemplateParameterCompartmentView')):
        c = compartimento(tipo, None, [], [], False, y)
        subs.append(c)
        campos[clave] = c
    v = {'_type': VISTA_DE[el['_type']], '_id': vid, '_parent': ref(dg['_id']), 'model': ref(el['_id']), 'subViews': subs,
         'font': 'Arial;13;0', 'parentStyle': False, 'containerChangeable': True,
         'left': x, 'top': y, 'width': ancho, 'height': alto, 'stereotypeDisplay': 'label', 'nameCompartment': ref(ncid)}
    if campos['attributeCompartment'].get('visible', True) is False:
        v['suppressAttributes'] = True
    if campos['operationCompartment'].get('visible', True) is False:
        v['suppressOperations'] = True
    v.update({k: ref(c['_id']) for k, c in campos.items()})
    dg.setdefault('ownedViews', []).append(v)
    return v


def vista_relacion(doc, dg, rel, tail_v, head_v, medios=()):
    """Linea de generalizacion, realizacion de interfaz o dependencia (misma estructura que guarda StarUML)."""
    vid = doc.new_id()
    puntos = M.ruta(tail_v, head_v, medios)
    P = [tuple(float(n) for n in p.split(':')) for p in puntos.split(';')]
    mx, my = (P[0][0] + P[-1][0]) / 2, (P[0][1] + P[-1][1]) / 2
    subs = []
    for alpha, dist, visible, dy in ((1.5707963267948966, 15, False, -15), (1.5707963267948966, 30, None, -30),
                                     (-1.5707963267948966, 15, False, 15)):
        subs.append({'_type': 'EdgeLabelView', '_id': doc.new_id(), '_parent': ref(vid), 'model': ref(rel['_id']),
                     'visible': visible, 'font': 'Arial;13;0', 'parentStyle': False, 'left': round(mx), 'top': round(my + dy),
                     'height': 13, 'alpha': alpha, 'distance': dist, 'hostEdge': ref(vid), 'edgePosition': 1})
    v = {'_type': VISTA_RELACION[rel['_type']], '_id': vid, '_parent': ref(dg['_id']), 'model': ref(rel['_id']), 'subViews': subs,
         'font': 'Arial;13;0', 'parentStyle': False, 'head': ref(head_v['_id']), 'tail': ref(tail_v['_id']),
         'lineStyle': 1, 'points': puntos, 'showVisibility': True,
         'nameLabel': ref(subs[0]['_id']), 'stereotypeLabel': ref(subs[1]['_id']), 'propertyLabel': ref(subs[2]['_id'])}
    dg.setdefault('ownedViews', []).append(v)
    return v


# ---------------------------------------------------------------------------
# Acomodo por capas (Sugiyama) y ruteo ortogonal
# ---------------------------------------------------------------------------

SEP_X, SEP_X_HUECO, SEP_HUECOS, SEP_Y, MARGEN, ANCHO_BANDA, ANCHO_HUECO, MAX_POR_CAPA, CARRIL = 60, 22, 8, 120, 60, 2600, 2, 7, 9


def _capas(nodos, aristas):
    """Capa de cada nodo. aristas: (arriba, abajo, fija). La herencia (fija) manda: la clase base siempre arriba. Cada
    asociacion pone al dueno del campo arriba de la clase referida mientras eso no forme un ciclo ni alargue el
    diagrama mas alla de un tope de filas (~raiz de n); las que no caben quedan libres (misma fila o hacia arriba)
    y se rutean por los canales. Las clases sin ninguna restriccion se acercan a la fila de sus vecinas."""
    nodos = sorted(nodos)
    fijas = [(a, b) for a, b, f in aristas if f and a != b]
    suaves = sorted({(a, b) for a, b, f in aristas if not f and a != b})

    def niveles(restr):
        """Camino mas largo desde las raices; None si hay ciclo."""
        pred = {n: [] for n in nodos}
        for a, b in restr:
            pred[b].append(a)
        capa, pendientes = {}, list(nodos)
        while pendientes:
            listos = [n for n in pendientes if all(p in capa for p in pred[n])]
            if not listos:
                return None
            for n in listos:
                capa[n] = 1 + max((capa[p] for p in pred[n]), default=-1)
            pendientes = [n for n in pendientes if n not in capa]
        return capa
    capa = niveles(fijas) or {n: 0 for n in nodos}
    tope = max(max(capa.values()) + 1, math.ceil(math.sqrt(len(nodos))) + 2)
    restr = list(fijas)
    for a, b in suaves:
        prueba = niveles(restr + [(a, b)])
        if prueba is not None and max(prueba.values()) < tope:
            restr.append((a, b))
            capa = prueba
    # las fuentes bajan junto a lo que tienen debajo (lineas mas cortas)
    sucs = {n: [] for n in nodos}
    preds = {n: [] for n in nodos}
    for a, b in restr:
        sucs[a].append(b)
        preds[b].append(a)
    for n in sorted(nodos, key=lambda n: -capa[n]):
        if not preds[n] and sucs[n]:
            capa[n] = min(capa[s] for s in sucs[n]) - 1
    libres = [n for n in nodos if not preds[n] and not sucs[n]]
    vecinos = {n: [] for n in nodos}
    for a, b in suaves:
        vecinos[a].append((b, -1))
        vecinos[b].append((a, 1))
    for _ in range(10):
        for n in libres:
            if vecinos[n]:
                valores = sorted(capa[v] + d for v, d in vecinos[n])
                capa[n] = valores[(len(valores) - 1) // 2]
    base = min(capa.values())
    return {n: c - base for n, c in capa.items()}


def _acomodar_componente(comp, tam, aristas):
    """Posiciones de una componente conexa (desde 0,0) y la geometria de sus filas, huecos y canales, para rutear."""
    capa = _capas(comp, aristas)
    # una capa con demasiadas cajas se parte en varias: primero las que no conectan hacia abajo
    abajo = {a if capa[a] < capa[b] else b for a, b, _ in aristas if capa[a] != capa[b]}
    por_capa, nueva, desplazo = {}, {}, 0
    for n in comp:
        por_capa.setdefault(capa[n], []).append(n)
    for c in sorted(por_capa):
        lista = sorted(por_capa[c], key=lambda n: (n in abajo, n))
        for i, n in enumerate(lista):
            nueva[n] = c + desplazo + i // MAX_POR_CAPA
        desplazo += (len(lista) - 1) // MAX_POR_CAPA
    capa = nueva
    # cada relacion, de la caja de arriba a la de abajo; las que quedan en la misma fila van aparte
    pares, mismas = [], []
    for a, b, _ in aristas:
        if a == b:
            continue
        par = (a, b) if capa[a] < capa[b] else (b, a)
        if capa[a] == capa[b]:
            if par not in mismas and (b, a) not in mismas:
                mismas.append(par)
        elif par not in pares:
            pares.append(par)
    # huecos: una arista que salta capas pasa por un hueco reservado en cada capa intermedia
    ancho = {n: tam[n][0] for n in comp}
    cadenas, arriba_de, abajo_de, junto_a = {}, {n: [] for n in comp}, {n: [] for n in comp}, {n: [] for n in comp}
    for a, b in pares:
        previo, cadena = a, [a]
        for c in range(capa[a] + 1, capa[b]):
            h = ('hueco', a, b, c)
            capa[h], ancho[h] = c, ANCHO_HUECO
            arriba_de[h], abajo_de[h], junto_a[h] = [previo], [], []
            abajo_de[previo].append(h)
            cadena.append(h)
            previo = h
        abajo_de[previo].append(b)
        arriba_de[b].append(previo)
        cadena.append(b)
        cadenas[(a, b)] = cadena
    for a, b in mismas:
        junto_a[a].append(b)
        junto_a[b].append(a)
    filas = [[] for _ in range(max(capa.values()) + 1)]
    for n in sorted(capa, key=lambda n: (isinstance(n, tuple), str(n))):
        filas[capa[n]].append(n)
    # orden por baricentro (las vecinas de la misma fila tambien cuentan, para dejarlas juntas)
    for pasada in range(10):
        pos = {n: i for f in filas for i, n in enumerate(f)}
        bajando = pasada % 2 == 0
        vecinos = arriba_de if bajando else abajo_de
        for i in (range(len(filas)) if bajando else range(len(filas) - 1, -1, -1)):
            def bari(n):
                vs = [pos[v] for v in vecinos[n]] + [pos[v] for v in junto_a[n]]
                return sum(vs) / len(vs) if vs else pos[n]
            filas[i].sort(key=bari)
            for j, n in enumerate(filas[i]):
                pos[n] = j

    def sep(a, b):  # las lineas largas que pasan juntas van como un haz de paralelas
        huecos = isinstance(a, tuple) + isinstance(b, tuple)
        return SEP_HUECOS if huecos == 2 else SEP_X_HUECO if huecos else SEP_X
    # x: empaquetado inicial y luego cada fila lo mas cerca posible del centro de sus vecinas, sin encimarse
    x = {}
    for f in filas:
        cx = 0
        for i, n in enumerate(f):
            cx += sep(f[i - 1], n) if i else 0
            x[n] = cx
            cx += ancho[n]
    for pasada in range(12):
        bajando = pasada % 2 == 0
        vecinos = arriba_de if bajando else abajo_de
        for f in (filas if bajando else filas[::-1]):
            deseo = []
            for n in f:
                vs = [x[v] + ancho[v] / 2 for v in vecinos[n]]
                deseo.append(sum(vs) / len(vs) - ancho[n] / 2 if vs else x[n])
            for n, v in zip(f, _colocar(deseo, [ancho[n] for n in f], [sep(a, b) for a, b in zip(f, f[1:])])):
                x[n] = v
    minx = min(x.values())
    altos = [max([tam[n][1] for n in f if not isinstance(n, tuple)] or [0]) for f in filas]
    # cada canal entre filas lo bastante alto para que cada linea que pasa por el tenga su carril; las de una misma
    # fila usan el canal de arriba (o el de abajo en la primera fila)
    pasan = [0] * len(filas)
    for a, b in pares:
        for c in range(capa[a], capa[b]):
            pasan[c] += 1
    for a, _ in mismas:
        pasan[max(capa[a] - 1, 0)] += 1
    canales = [max(SEP_Y, 56 + CARRIL * n) for n in pasan]
    tops, y = [], 0
    for h, g in zip(altos, canales):
        tops.append(y)
        y += h + g
    posiciones = {n: (round(x[n] - minx), tops[capa[n]]) for n in comp}
    huecos = {n: x[n] - minx + ancho[n] / 2 for n in capa if isinstance(n, tuple)}
    return posiciones, {'cadenas': cadenas, 'mismas': mismas, 'capa': capa, 'tops': tops, 'altos': altos,
                        'canales': canales, 'huecos': huecos, 'ancho': max(x[n] + ancho[n] for n in capa) - minx,
                        'alto': y - canales[-1]}


def _colocar(deseo, anchos, seps):
    """Posiciones en una fila lo mas cerca posible de las deseadas (minimos cuadrados), en el orden dado y sin
    encimarse: regresion isotonica (pool-adjacent-violators) sobre deseo menos el desplazamiento minimo."""
    desplazo = [0.0]
    for w, sp in zip(anchos, seps):
        desplazo.append(desplazo[-1] + w + sp)
    bloques = []  # [suma, cuantos]
    for d, o in zip(deseo, desplazo):
        bloques.append([d - o, 1])
        while len(bloques) > 1 and bloques[-2][0] / bloques[-2][1] > bloques[-1][0] / bloques[-1][1]:
            suma, cuantos = bloques.pop()
            bloques[-1][0] += suma
            bloques[-1][1] += cuantos
    y = [suma / cuantos for suma, cuantos in bloques for _ in range(cuantos)]
    return [yi + o for yi, o in zip(y, desplazo)]


def acomodar(nodos, tam, aristas):
    """Posicion (left, top) de cada caja y la geometria para rutear. Cada componente conexa por capas, una junto a
    otra; las clases sueltas (sin relaciones) al final, en filas."""
    vecinos = {n: set() for n in nodos}
    for a, b, _ in aristas:
        vecinos[a].add(b)
        vecinos[b].add(a)
    visto, componentes, sueltas = set(), [], []
    for n in sorted(nodos, key=lambda n: (-len(vecinos[n]), n)):
        if n in visto:
            continue
        comp, pila = [], [n]
        while pila:
            m = pila.pop()
            if m not in visto:
                visto.add(m)
                comp.append(m)
                pila.extend(vecinos[m])
        if len(comp) > 1:
            componentes.append(comp)
        else:
            sueltas.append(n)
    posiciones, geometrias = {}, []
    x0, y0, alto_banda = MARGEN, MARGEN, 0
    for comp in componentes:
        miembros = set(comp)
        pos, geo = _acomodar_componente(comp, tam, [(a, b, f) for a, b, f in aristas if a in miembros])
        if x0 > MARGEN and x0 + geo['ancho'] > ANCHO_BANDA:
            x0, y0, alto_banda = MARGEN, y0 + alto_banda + SEP_Y, 0
        posiciones.update({n: (x + round(x0), y + y0) for n, (x, y) in pos.items()})
        geo['huecos'] = {h: hx + x0 for h, hx in geo['huecos'].items()}
        geo['tops'] = [t + y0 for t in geo['tops']]
        geometrias.append(geo)
        alto_banda = max(alto_banda, geo['alto'])
        x0 += geo['ancho'] + SEP_X * 2
    if sueltas:
        y0 = y0 + alto_banda + SEP_Y if posiciones else MARGEN
        x, alto = MARGEN, 0
        for n in sorted(sueltas):
            if x > MARGEN and x + tam[n][0] > ANCHO_BANDA:
                x, y0, alto = MARGEN, y0 + alto + SEP_Y // 2, 0
            posiciones[n] = (x, y0)
            x += tam[n][0] + SEP_X
            alto = max(alto, tam[n][1])
    return posiciones, geometrias


def _cruza(p, q, caja, margen=6):
    """El segmento p-q toca la caja (inflada por el margen)? Recorte de Liang-Barsky."""
    x0, y0, x1, y1 = caja[0] - margen, caja[1] - margen, caja[2] + margen, caja[3] + margen
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def _caja(v):
    return (v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height'])


def _cruces(puntos, cajas):
    return sum(1 for a, b in zip(puntos, puntos[1:]) for c in cajas if _cruza(a, b, c))


def _puntos(v):
    return [tuple(float(n) for n in p.split(':')) for p in v['points'].split(';')]


def _sin_colineales(medios):
    limpio = []
    for p in medios:
        p = (round(p[0]), round(p[1]))
        if limpio and p == limpio[-1]:
            continue
        if len(limpio) >= 2 and (limpio[-2][0] == limpio[-1][0] == p[0] or limpio[-2][1] == limpio[-1][1] == p[1]):
            limpio[-1] = p
            continue
        limpio.append(p)
    return limpio


def rutas(cajas, geometrias):
    """Puntos intermedios de cada relacion, por par (arriba, abajo) o (izquierda, derecha) si estan en la misma fila.
    Entre filas vecinas va recta si no toca otra caja; si no, sale de un puerto propio del borde, corre por su carril
    en el canal libre entre filas, cruza las filas intermedias por su hueco reservado y entra por otro puerto propio.
    Entre cajas de la misma fila sube al canal de arriba (en la primera fila baja al de abajo), corre y vuelve."""
    salida = {}
    for geo in geometrias:
        tops, altos, capa, canales = geo['tops'], geo['altos'], geo['capa'], geo['canales']
        carriles, puertos, tramos = {}, {}, []

        def puerto(n, lado, clave, hacia_x):
            puertos.setdefault((n, lado), []).append((clave, hacia_x))
        for (a, b), cadena in geo['cadenas'].items():
            xs = [geo['huecos'][h] for h in cadena[1:-1]]
            tramos.append(('capas', a, b, xs))
            puerto(a, 'abajo', (a, b), xs[0] if xs else (cajas[b][0] + cajas[b][2]) / 2)
            puerto(b, 'arriba', (a, b), xs[-1] if xs else (cajas[a][0] + cajas[a][2]) / 2)
        for a, b in geo['mismas']:
            lado = 'arriba' if capa[a] > 0 else 'abajo'
            tramos.append(('fila', a, b, lado))
            puerto(a, lado, (a, b), (cajas[b][0] + cajas[b][2]) / 2)
            puerto(b, lado, (a, b), (cajas[a][0] + cajas[a][2]) / 2)
        px = {}
        for (n, lado), lista in puertos.items():  # los puertos de un lado, repartidos en el orden de su destino
            x0, _, x1, _ = cajas[n]
            lista.sort(key=lambda t: t[1])
            for i, (clave, _) in enumerate(lista):
                px[(n, lado, clave)] = x0 + (x1 - x0) * (i + 1) / (len(lista) + 1)

        def carril(c):
            k = carriles.get(c, 0)
            carriles[c] = k + 1
            return tops[c] + altos[c] + 26 + (k * CARRIL) % max(CARRIL, canales[c] - 52)
        for tipo, a, b, extra in tramos:
            if tipo == 'fila':
                lado = extra
                ax, bx = px[(a, lado, (a, b))], px[(b, lado, (a, b))]
                if lado == 'arriba':
                    y = carril(capa[a] - 1)
                    medios = [(ax, cajas[a][1] - 8), (ax, y), (bx, y), (bx, cajas[b][1] - 8)]
                else:
                    y = carril(capa[a])
                    medios = [(ax, cajas[a][3] + 8), (ax, y), (bx, y), (bx, cajas[b][3] + 8)]
                salida[(a, b)] = _sin_colineales(medios)
                continue
            xs = extra
            ca, cb = capa[a], capa[b]
            if cb == ca + 1:
                pa = ((cajas[a][0] + cajas[a][2]) / 2, (cajas[a][1] + cajas[a][3]) / 2)
                pb = ((cajas[b][0] + cajas[b][2]) / 2, (cajas[b][1] + cajas[b][3]) / 2)
                otras = [c for n, c in cajas.items() if n not in (a, b)]
                if abs(pa[0] - pb[0]) < 60 and not _cruces([pa, pb], otras):
                    salida[(a, b)] = []
                    continue
            ax, bx = px[(a, 'abajo', (a, b))], px[(b, 'arriba', (a, b))]
            medios, actual = [(ax, cajas[a][3] + 8)], ax
            for c in range(ca, cb):
                y = carril(c)
                siguiente = xs[c - ca] if c - ca < len(xs) else bx
                medios += [(actual, y), (siguiente, y)]
                actual = siguiente
            medios.append((bx, cajas[b][1] - 8))
            salida[(a, b)] = _sin_colineales(medios)
    return salida


# ---------------------------------------------------------------------------
# Diagramas
# ---------------------------------------------------------------------------

def dibujar(doc, dg, elementos, relaciones, op):
    """Vistas de los elementos y de las relaciones entre ellos. Devuelve el resumen del diagrama."""
    ids = {el['_id'] for el in elementos}
    tam = {el['_id']: medir(doc, el, op) for el in elementos}
    rels, aristas = [], []
    for rel, _, _ in relaciones:
        if rel['_type'] == 'UMLAssociation':
            o, d = rel['end1']['reference']['$ref'], rel['end2']['reference']['$ref']
        else:
            o, d = rel['source']['$ref'], rel['target']['$ref']
        if o not in ids or d not in ids:
            continue
        rels.append((rel, o, d))
        if o != d:
            # la clase base arriba de sus derivadas; la que tiene el campo arriba de la referida
            aristas.append((d, o, True) if rel['_type'] in ('UMLGeneralization', 'UMLInterfaceRealization') else (o, d, False))
    posiciones, geometrias = acomodar(sorted(ids), tam, list(dict.fromkeys(aristas)))
    vistas = {}
    for el in elementos:
        x, y = posiciones[el['_id']]
        vistas[el['_id']] = vista_clasificador(doc, dg, el, x, y, *tam[el['_id']], op)
    cajas = {n: _caja(v) for n, v in vistas.items()}
    medios_de = rutas(cajas, geometrias)
    sentido = {frozenset(par): par for geo in geometrias for par in list(geo['cadenas']) + geo['mismas']}
    repetidas, cruzan = {}, []
    rels.sort(key=lambda r: (r[0]['_type'] not in ('UMLGeneralization', 'UMLInterfaceRealization'), r[0]['_type']))
    for rel, o, d in rels:
        par = frozenset((o, d))
        k = repetidas.get(par, 0)
        repetidas[par] = k + 1
        medios = []
        if o != d and par in sentido:
            medios = list(medios_de.get(sentido[par], []))
            if sentido[par] != (o, d):
                medios = medios[::-1]
            if k:  # otra linea entre las mismas dos cajas: corrida a un lado, si asi no cruza otra caja
                otras = [c for n, c in cajas.items() if n not in (o, d)]
                cx = (M.centro(vistas[o])[0] + M.centro(vistas[d])[0]) / 2
                cy = (M.centro(vistas[o])[1] + M.centro(vistas[d])[1]) / 2
                for dx in (16 * k, -16 * k):
                    prueba = [(x + dx, y) for x, y in medios] or [(round(cx + 3 * dx), round(cy))]
                    pts = _puntos({'points': M.ruta(vistas[o], vistas[d], prueba)})
                    if not _cruces(pts, otras):
                        medios = prueba
                        break
        if rel['_type'] == 'UMLAssociation':
            v = M.vista_asociacion(doc, dg, rel, vistas[o], vistas[d], medios)
        else:
            v = vista_relacion(doc, dg, rel, vistas[o], vistas[d], medios)
        otras = [c for n, c in cajas.items() if n not in (o, d)]
        if o != d and _cruces(_puntos(v), otras):
            cruzan.append(f'{doc.name_of(o)} - {doc.name_of(d)} ({rel["_type"]})')
    return {'diagrama': dg.get('name'), 'id': dg['_id'], 'cajas': len(vistas), 'lineas': len(rels),
            'lineas_que_cruzan_cajas': cruzan,
            'ancho': max((c[2] for c in cajas.values()), default=0) + MARGEN,
            'alto': max((c[3] for c in cajas.values()), default=0) + MARGEN}


def programa_a_diagrama(doc, ruta_codigo, lenguaje='java', paquete=None, diagrama=None, diagrama_por='programa',
                        atributos=True, metodos=True, solo_publicos=False, omitir_accesores=False, asociaciones=True,
                        dependencias=False, incluir_pruebas=False, reemplazar=False, por_defecto=False):
    """Lee el programa, crea su modelo en un paquete nuevo y dibuja su diagrama de clases (uno para todo el programa o
    uno por paquete)."""
    if diagrama_por not in ('programa', 'paquete'):
        raise MdjError('diagrama_por debe ser "programa" o "paquete"')
    clases, repetidas = leer_programa(ruta_codigo, lenguaje, incluir_pruebas)
    if not clases:
        raise MdjError(f'No se encontraron clases{" de " + lenguaje if lenguaje != "auto" else ""} en {ruta_codigo}')
    carpeta = os.path.abspath(os.path.expanduser(ruta_codigo))
    raiz_nombre = paquete or os.path.splitext(os.path.basename(carpeta.rstrip(os.sep)))[0] or 'Programa'
    modelo = M.modelo_raiz(doc)
    previo = [o for o in modelo.get('ownedElements', []) if o.get('_type') == 'UMLPackage' and o.get('name') == raiz_nombre]
    if previo:
        if not reemplazar:
            raise MdjError(f'Ya existe el paquete "{raiz_nombre}" en el modelo. Usa reemplazar=true para rehacerlo '
                           f'o indica otro nombre en "paquete".')
        for pk in previo:
            M.borrar(doc, pk)
        doc.reindex()
    op = {'atributos': atributos, 'metodos': metodos, 'solo_publicos': solo_publicos, 'omitir_accesores': omitir_accesores,
          'asociaciones': asociaciones, 'dependencias': dependencias}
    hecho = construir(doc, clases, raiz_nombre, op)
    elems, relaciones = hecho['elementos'], hecho['relaciones']
    grupos = []
    if diagrama_por == 'programa':
        grupos.append((diagrama or 'Diagrama de clases', hecho['raiz'], list(elems.values())))
    else:
        por_pk = {}
        for q, el in elems.items():
            por_pk.setdefault(clases[q].get('paquete') or '', []).append(el)
        for pk_nombre in sorted(por_pk):
            grupos.append((pk_nombre or raiz_nombre, hecho['paquetes'][pk_nombre], por_pk[pk_nombre]))
    diagramas = []
    for i, (nombre, dueno, elementos) in enumerate(grupos):
        dg = M.crear_diagrama(doc, 'clases', nombre, dentro_de=dueno['_id'], por_defecto=por_defecto and i == 0)
        diagramas.append(dibujar(doc, dg, sorted(elementos, key=lambda e: e.get('name', '')), relaciones, op))
    doc.reindex()
    cuenta = {}
    for el in elems.values():
        cuenta[el['_type']] = cuenta.get(el['_type'], 0) + 1
    rels = {}
    for rel, _, _ in relaciones:
        rels[rel['_type']] = rels.get(rel['_type'], 0) + 1
    return {'paquete': raiz_nombre, 'lenguaje': lenguaje, 'diagramas': diagramas,
            'clases': cuenta.get('UMLClass', 0), 'interfaces': cuenta.get('UMLInterface', 0),
            'enumeraciones': cuenta.get('UMLEnumeration', 0),
            'paquetes_del_programa': sorted(k for k in hecho['paquetes'] if k),
            'asociaciones': rels.get('UMLAssociation', 0), 'generalizaciones': rels.get('UMLGeneralization', 0),
            'realizaciones': rels.get('UMLInterfaceRealization', 0), 'dependencias': rels.get('UMLDependency', 0),
            'herencia_externa': hecho['herencia_externa'], 'clases_repetidas_omitidas': repetidas}
