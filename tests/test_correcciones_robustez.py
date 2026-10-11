# mdj_robustez_generar al reusar asociaciones que ya existen: solo cambia lo que se pide de forma explicita, nunca
# pone valores por defecto encima de los que tenian, y dice que reuso y que cambio. Antes reescribia multiplicidad,
# rol y navegabilidad de cada asociacion reusada con '' y 'hacia', y cambiaba en silencio lo que se ve en los otros
# diagramas (en una copia del modelo real: 33 de 34 asociaciones reusadas y las pantallas perdian la navegabilidad
# hacia el control).
import copy
import json
import os

import pytest

import staruml_robustez as RB
from apoyo import M, ok, tool, ids_integros


def _caso(**extra):
    return dict(
        actores=[{'nombre': 'Asesor'}],
        pantallas=[{'nombre': 'PantallaCliente', 'nota': 'F1: identificar o registrar al cliente.'},
                   {'nombre': 'PantallaPedido'}],
        control={'nombre': 'ControlPedido'},
        entidades=[{'nombre': 'Cliente', 'atributos': ['nombre', 'telefono']},
                   {'nombre': 'Pedido', 'atributos': ['folio', 'total']},
                   {'nombre': 'LineaPedido', 'atributos': ['cantidad'], 'depende_de': 'Pedido'},
                   {'nombre': 'Producto', 'atributos': ['clave', 'precio']}],
        asociaciones=[{'desde': 'Cliente', 'hasta': 'Pedido', 'mult_desde': '1', 'mult_hacia': '0..*'},
                      {'desde': 'Pedido', 'hasta': 'LineaPedido', 'mult_desde': '1', 'mult_hacia': '1..*'},
                      {'desde': 'LineaPedido', 'hasta': 'Producto', 'mult_desde': '0..*', 'mult_hacia': '1',
                       'rol_hacia': 'producto'}],
        **extra)


def _minimo(caso):
    """El mismo caso sin atributos, multiplicidades, roles ni navegabilidad: solo que va con que."""
    c = copy.deepcopy(caso)
    for e in c['entidades']:
        e.pop('atributos', None)
    c['asociaciones'] = [{'desde': a['desde'], 'hasta': a['hasta']} for a in c['asociaciones']]
    return c


def _diagrama(archivo, nombre, dentro_de='Analisis'):
    r = ok(tool('mdj_diagrama_crear', archivo=archivo, tipo='clases', nombre=nombre, dentro_de=dentro_de))
    return r['diagrama']


def _asociaciones(doc):
    return {i: json.dumps(o, ensure_ascii=False) for i, o in doc.ids.items()
            if o and o.get('_type') == 'UMLAssociation'}


def _sin_diagrama(doc, diagrama_id):
    """El documento como texto sin el diagrama indicado."""
    d = copy.deepcopy(doc.d)

    def quitar(o):
        if isinstance(o, dict):
            if isinstance(o.get('ownedElements'), list):
                o['ownedElements'] = [x for x in o['ownedElements'] if x.get('_id') != diagrama_id]
            for v in o.values():
                quitar(v)
        elif isinstance(o, list):
            for v in o:
                quitar(v)
    quitar(d)
    return json.dumps(d, ensure_ascii=False)


def _textos(doc, dg):
    """{(nombre de tail, nombre de head): textos visibles de multiplicidades y roles} de las asociaciones."""
    res = {}
    for v in dg['ownedViews']:
        if v['_type'] != 'UMLAssociationView':
            continue
        n = lambda lado: doc.name_of(doc.ids[v[lado]['$ref']]['model']['$ref'])
        subs = {s['_id']: s for s in v['subViews']}
        res[(n('tail'), n('head'))] = sorted(
            subs[v[k]['$ref']]['text'] for k in ('tailMultiplicityLabel', 'tailRoleNameLabel',
                                                 'headMultiplicityLabel', 'headRoleNameLabel')
            if subs[v[k]['$ref']].get('visible') is not False and subs[v[k]['$ref']].get('text'))
    return res


def _asoc(doc, a, b):
    return [o for o in doc.ids.values() if o and o.get('_type') == 'UMLAssociation'
            and {doc.name_of(o['end1']['reference']['$ref']), doc.name_of(o['end2']['reference']['$ref'])} == {a, b}]


# ---------------------------------------------------------------------------
# Lo que no se pide no se toca
# ---------------------------------------------------------------------------

def test_regenerar_sin_valores_no_cambia_las_asociaciones_ni_los_otros_diagramas(vacio):
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis'), paquete='Analisis',
            **_caso()))
    # como queda un modelo trabajado a mano: pantalla <-> control en los dos sentidos y un extremo 'notNavigable'
    doc = M.Doc(vacio)
    for o in _asoc(doc, 'PantallaCliente', 'ControlPedido') + _asoc(doc, 'PantallaPedido', 'ControlPedido'):
        o['end1']['navigable'] = 'navigable'
    _asoc(doc, 'Cliente', 'Pedido')[0]['end1']['navigable'] = 'notNavigable'
    doc.save(backup=False)
    doc = M.Doc(vacio)
    antes, textos_antes = _asociaciones(doc), _textos(doc, doc.diagram('Analisis'))
    dg2 = _diagrama(vacio, 'Analisis 2')
    resto_antes = _sin_diagrama(M.Doc(vacio), dg2)

    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg2, paquete='Analisis', **_minimo(_caso())))
    doc = M.Doc(vacio)
    assert _asociaciones(doc) == antes
    # fuera del diagrama nuevo el archivo queda igual (tambien las vistas del primero)
    assert _sin_diagrama(doc, dg2) == resto_antes
    assert r['asociaciones_reusadas'] == r['asociaciones'] == 7 and r['asociaciones_cambiadas'] == 0
    assert len(r['reusadas']) == 7 and all(x['cambios'] == [] for x in r['reusadas'])
    assert {x['id'] for x in r['reusadas']} <= set(antes)
    # el diagrama nuevo muestra lo que tiene el modelo, sin encimar etiquetas
    assert _textos(doc, doc.diagram('Analisis 2')) == textos_antes
    assert r['etiquetas_que_chocan'] == [] and r['lineas_que_cruzan_cajas'] == []
    assert ids_integros(vacio)


def test_valores_iguales_a_los_del_modelo_no_cambian_nada(vacio):
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis'), paquete='Analisis',
            **_caso()))
    antes = _asociaciones(M.Doc(vacio))
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis 2'), paquete='Analisis',
                **_caso()))
    assert _asociaciones(M.Doc(vacio)) == antes
    assert r['asociaciones_cambiadas'] == 0


def test_vacios_explicitos_no_borran_lo_que_habia(vacio):
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis'), paquete='Analisis',
            **_caso()))
    antes = _asociaciones(M.Doc(vacio))
    caso = _minimo(_caso())
    caso['asociaciones'] = [dict(a, mult_desde='', mult_hacia='', rol_desde='', rol_hacia='')
                            for a in caso['asociaciones']]
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis 2'), paquete='Analisis',
                **caso))
    assert _asociaciones(M.Doc(vacio)) == antes and r['asociaciones_cambiadas'] == 0


# ---------------------------------------------------------------------------
# Lo que se pide se cambia y se reporta
# ---------------------------------------------------------------------------

def test_cambio_explicito_se_aplica_y_se_reporta(vacio):
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis'), paquete='Analisis',
            **_caso()))
    caso = _caso()
    caso['asociaciones'][0].update(mult_hacia='1..*', navegable='ambos')
    caso['asociaciones'][2].update(mult_desde='', rol_hacia='')
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis 2'), paquete='Analisis',
                **caso))
    assert r['asociaciones_reusadas'] == 7 and r['asociaciones_cambiadas'] == 1
    cambiada = [x for x in r['reusadas'] if x['cambios']]
    assert [x['asociacion'] for x in cambiada] == ['Cliente - Pedido']
    assert cambiada[0]['cambios'] == [
        {'extremo': 'Cliente', 'que': 'navegable', 'antes': False, 'despues': True},
        {'extremo': 'Pedido', 'que': 'multiplicidad', 'antes': '0..*', 'despues': '1..*'}]
    assert cambiada[0]['se_ve_en'] == ['Analisis']
    doc = M.Doc(vacio)
    a = _asoc(doc, 'Cliente', 'Pedido')[0]
    assert a['end2']['multiplicity'] == '1..*' and a['end1']['navigable'] == a['end2']['navigable'] == 'navigable'
    # el otro diagrama muestra el cambio (es la misma asociacion)
    assert '1..*' in _textos(doc, doc.diagram('Analisis'))[('Cliente', 'Pedido')]
    # los vacios no borraron la multiplicidad ni el rol de LineaPedido - Producto
    lp = _asoc(doc, 'LineaPedido', 'Producto')[0]
    assert lp['end1']['multiplicity'] == '0..*' and lp['end2']['name'] == 'producto'
    assert ids_integros(vacio)


def test_navegable_explicito_respeta_not_navigable_si_ya_no_navega(vacio):
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis'), paquete='Analisis',
            **_caso()))
    doc = M.Doc(vacio)
    _asoc(doc, 'Cliente', 'Pedido')[0]['end1']['navigable'] = 'notNavigable'
    doc.save(backup=False)
    antes = _asociaciones(M.Doc(vacio))
    caso = _minimo(_caso())
    caso['asociaciones'][0]['navegable'] = 'hacia'  # ya es asi: Cliente no navega (notNavigable) y Pedido si
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis 2'), paquete='Analisis',
                **caso))
    assert _asociaciones(M.Doc(vacio)) == antes and r['asociaciones_cambiadas'] == 0


# ---------------------------------------------------------------------------
# Escoger bien entre varias asociaciones del mismo par
# ---------------------------------------------------------------------------

def _raiz_nodo(vacio):
    """Raiz - Nodo dos veces (con rol 'principal' la primera y 'secundario' la segunda, en ese orden en el archivo) y
    Nodo - Nodo reflexiva con roles padre e hijos."""
    dg = _diagrama(vacio, 'Analisis')
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', actores=[{'nombre': 'U'}],
            pantallas=[{'nombre': 'P'}], control={'nombre': 'Ctl'},
            entidades=[{'nombre': 'Raiz', 'atributos': ['a']}, {'nombre': 'Nodo', 'atributos': ['a', 'b']}],
            asociaciones=[{'desde': 'Raiz', 'hasta': 'Nodo', 'mult_desde': '1', 'mult_hacia': '0..1',
                           'rol_hacia': 'principal'},
                          {'desde': 'Raiz', 'hasta': 'Nodo', 'mult_desde': '1', 'mult_hacia': '0..*',
                           'rol_hacia': 'secundario'},
                          {'desde': 'Nodo', 'hasta': 'Nodo', 'mult_desde': '0..1', 'mult_hacia': '0..*',
                           'rol_desde': 'padre', 'rol_hacia': 'hijos'}]))


def test_la_que_pide_un_rol_escoge_primero_y_la_reflexiva_se_lee_de_cualquier_lado(vacio):
    _raiz_nodo(vacio)
    antes = _asociaciones(M.Doc(vacio))
    # la primera no pide rol (podria tomar la de 'principal', que esta primero en el archivo) y la segunda pide
    # 'principal'; la reflexiva se describe desde el otro extremo
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis 2'), paquete='Analisis',
                actores=[{'nombre': 'U'}], pantallas=[{'nombre': 'P'}], control={'nombre': 'Ctl'},
                entidades=[{'nombre': 'Raiz'}, {'nombre': 'Nodo'}],
                asociaciones=[{'desde': 'Raiz', 'hasta': 'Nodo'},
                              {'desde': 'Raiz', 'hasta': 'Nodo', 'rol_hacia': 'principal'},
                              {'desde': 'Nodo', 'hasta': 'Nodo', 'rol_desde': 'hijos', 'rol_hacia': 'padre',
                               'mult_desde': '0..*', 'mult_hacia': '0..1'}]))
    assert _asociaciones(M.Doc(vacio)) == antes
    assert r['asociaciones_reusadas'] == 5 and r['asociaciones_cambiadas'] == 0
    assert r['etiquetas_que_chocan'] == [] and r['lineas_que_cruzan_cajas'] == []


def test_rol_distinto_en_la_unica_que_hay_se_cambia_y_se_reporta(vacio):
    _raiz_nodo(vacio)
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis 2'), paquete='Analisis',
                actores=[{'nombre': 'U'}], pantallas=[{'nombre': 'P'}], control={'nombre': 'Ctl'},
                entidades=[{'nombre': 'Raiz'}, {'nombre': 'Nodo'}],
                asociaciones=[{'desde': 'Nodo', 'hasta': 'Nodo', 'rol_desde': 'jefe'}]))
    cambios = [c for x in r['reusadas'] for c in x['cambios']]
    assert cambios == [{'extremo': 'Nodo (desde)', 'que': 'rol', 'antes': 'padre', 'despues': 'jefe'}]
    refl = [o for o in _asoc(M.Doc(vacio), 'Nodo', 'Nodo') if o['end1']['reference'] == o['end2']['reference']]
    assert refl[0]['end1']['name'] == 'jefe' and refl[0]['end2']['name'] == 'hijos'


# ---------------------------------------------------------------------------
# Actores de otro paquete y entradas invalidas
# ---------------------------------------------------------------------------

def test_actor_unico_de_otro_paquete_se_reusa(vacio):
    ok(tool('mdj_paquete_crear', archivo=vacio, nombre='Robustez'))
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'R', 'Robustez'), paquete='Robustez',
                actores=[{'nombre': 'Usuario'}], pantallas=[{'nombre': 'P'}], control={'nombre': 'Ctl'},
                entidades=[{'nombre': 'E'}]))
    assert r['actores_de_otro_paquete'] == {'Usuario': 'Analisis'}
    doc = M.Doc(vacio)
    assert len([o for o in doc.ids.values() if o and o.get('_type') == 'UMLActor' and o['name'] == 'Usuario']) == 1
    assert ids_integros(vacio)


def test_actor_repetido_en_otros_paquetes_se_crea_en_el_paquete(vacio):
    for pk in ('Robustez', 'Otro'):
        ok(tool('mdj_paquete_crear', archivo=vacio, nombre=pk))
    doc = M.Doc(vacio)
    otro = doc.find('Otro', types=('UMLPackage',))
    otro.setdefault('ownedElements', []).append({'_type': 'UMLActor', '_id': doc.new_id(),
                                                 '_parent': M.ref(otro['_id']), 'name': 'Usuario'})
    doc.save(backup=False)
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'R', 'Robustez'), paquete='Robustez',
                actores=[{'nombre': 'Usuario'}], pantallas=[{'nombre': 'P'}], control={'nombre': 'Ctl'},
                entidades=[{'nombre': 'E'}]))
    assert 'actores_de_otro_paquete' not in r
    doc = M.Doc(vacio)
    assert any(o.get('name') == 'Usuario' for o in doc.find('Robustez', types=('UMLPackage',))['ownedElements'])


@pytest.mark.parametrize('cambio, mensaje', [
    ({'navegable': 'arriba'}, 'navegable "arriba"'),
    ({'mult_desde': 1}, 'mult_desde debe ser texto'),
    ({'rol_hacia': ['x']}, 'rol_hacia debe ser texto'),
])
def test_valores_invalidos_de_una_asociacion(vacio, cambio, mensaje):
    _diagrama(vacio, 'Analisis')
    caso = _caso()
    caso['asociaciones'][0].update(cambio)
    with pytest.raises(M.MdjError, match=mensaje):
        RB.generar_robustez(M.Doc(vacio), 'Analisis', 'Analisis', **caso)


# ---------------------------------------------------------------------------
# Modelo real: el diagrama de robustez que ya tiene, regenerado en un diagrama nuevo
# ---------------------------------------------------------------------------

def _navega(e):
    return e.get('navigable') in (True, 'navigable')


def _robustez_del_modelo(doc):
    """El diagrama de clases con un control y mas pantallas y entidades dibujadas, o None."""
    mejor, n = None, 0
    for dg in doc.diagrams():
        if dg['_type'] != 'UMLClassDiagram':
            continue
        kinds = [doc.kind(doc.ids.get(v['model']['$ref'])) for v in dg.get('ownedViews', [])
                 if isinstance(v.get('model'), dict) and v['_type'] == 'UMLClassView']
        if kinds.count('control') == 1 and kinds.count('boundary') + kinds.count('entity') > n:
            mejor, n = dg, kinds.count('boundary') + kinds.count('entity')
    return mejor


def _especificacion(doc, dg, con_valores):
    """Lo que dibuja un diagrama de robustez como entrada de generar_robustez. con_valores: cada asociacion entre
    entidades con sus multiplicidades, roles y navegabilidad del modelo; si no, solo que va con que."""
    cajas = sorted(((v['top'], doc.ids[v['model']['$ref']]) for v in dg['ownedViews']
                    if v['_type'] in ('UMLClassView', 'UMLActorView') and isinstance(v.get('model'), dict)),
                   key=lambda t: t[0])
    de = {k: [el for _, el in cajas if doc.kind(el) == k] for k in ('actor', 'boundary', 'control', 'entity')}
    nombre = {el['_id']: el['name'] for _, el in cajas}
    actores = {el['name']: [] for el in de['actor']}
    entidades = [el['name'] for el in de['entity']]
    asociaciones, generalizaciones = [], []
    for v in dg['ownedViews']:
        m = doc.ids.get((v.get('model') or {}).get('$ref'))
        if v['_type'] == 'UMLGeneralizationView':
            generalizaciones.append({'hijo': nombre[m['source']['$ref']], 'padre': nombre[m['target']['$ref']]})
        if v['_type'] != 'UMLAssociationView':
            continue
        e1, e2 = m['end1'], m['end2']
        n1, n2 = nombre.get(e1['reference']['$ref']), nombre.get(e2['reference']['$ref'])
        if n1 in entidades and n2 in entidades:
            a = {'desde': n1, 'hasta': n2}
            if con_valores:
                for k, x in (('mult_desde', e1.get('multiplicity')), ('mult_hacia', e2.get('multiplicity')),
                             ('rol_desde', e1.get('name')), ('rol_hacia', e2.get('name'))):
                    if x:
                        a[k] = x
                a['navegable'] = RB.NAVEGA[(_navega(e1), _navega(e2))]
            asociaciones.append(a)
        for actor, otro in ((n1, n2), (n2, n1)):
            if actor in actores and otro in [el['name'] for el in de['boundary']]:
                actores[actor].append(otro)
    pantallas = [el['name'] for el in de['boundary']]
    return dict(actores=[{'nombre': n, 'pantallas': [p for p in pantallas if p in ps]}
                         for n, ps in actores.items() if ps],
                pantallas=[{'nombre': p} for p in pantallas], control={'nombre': de['control'][0]['name']},
                entidades=[{'nombre': e} for e in entidades], asociaciones=asociaciones,
                generalizaciones=generalizaciones)


def _regenerar(real, con_valores, lineas_control=False):
    doc = M.Doc(real)
    dg = _robustez_del_modelo(doc)
    if dg is None:
        pytest.skip('el modelo no tiene un diagrama de robustez')
    caso = _especificacion(doc, dg, con_valores)
    paquete = doc.parent[doc.find(caso['control']['nombre'], types=('UMLClass',))['_id']]
    nuevo = {'_type': 'UMLClassDiagram', '_id': doc.new_id(), '_parent': M.ref(doc.parent[dg['_id']]),
             'name': dg.get('name', '') + ' regenerado'}
    doc.ids[doc.parent[dg['_id']]]['ownedElements'].append(nuevo)
    doc.reindex()
    antes = _asociaciones(doc)
    vistas_antes = json.dumps(dg, ensure_ascii=False)
    resto_antes = _sin_diagrama(doc, nuevo['_id'])
    r = RB.generar_robustez(doc, nuevo['_id'], paquete, lineas_control=lineas_control, **caso)
    doc.save(backup=False)
    return M.Doc(real), dg, nuevo, r, antes, vistas_antes, resto_antes


@pytest.mark.parametrize('con_valores, lineas_control', [(True, False), (False, False), (False, True)])
def test_modelo_real_regenerar_su_robustez_no_cambia_sus_asociaciones(real, con_valores, lineas_control):
    doc, dg, nuevo, r, antes, vistas_antes, resto_antes = _regenerar(real, con_valores, lineas_control)
    despues = _asociaciones(doc)
    assert {i: despues.get(i) for i in antes} == antes
    assert json.dumps(doc.diagram(dg['_id']), ensure_ascii=False) == vistas_antes
    assert r['asociaciones_cambiadas'] == 0 and all(x['cambios'] == [] for x in r['reusadas'])
    if not lineas_control:
        # todo lo que dibuja ya estaba en el modelo: nada nuevo fuera del diagrama
        assert r['asociaciones_reusadas'] == r['asociaciones']
        assert _sin_diagrama(doc, nuevo['_id']) == resto_antes
    assert r['lineas_que_cruzan_cajas'] == [] and r['etiquetas_que_chocan'] == []
    assert ids_integros(real)


@pytest.fixture
def staruml(monkeypatch):
    if not M.staruml_cli():
        pytest.skip('StarUML no esta instalado (o define STARUML_MCP_STARUML_BIN)')
    monkeypatch.setenv('STARUML_MCP_EXPORT_TIMEOUT', os.environ.get('STARUML_MCP_EXPORT_TIMEOUT', '300'))


def test_modelo_real_regenerado_con_lo_que_tiene_el_modelo_se_ve_limpio_en_staruml(real, tmp_path, staruml):
    # sin valores en la entrada las etiquetas salen del modelo: se acomodan con esos textos y no se enciman
    nuevo = _regenerar(real, False)[2]
    svg = ok(tool('staruml_exportar', archivo=real, carpeta=str(tmp_path / 'svg'),
                  diagrama=nuevo['_id']))['archivos'][0]
    rev = ok(tool('svg_revisar', svg=svg, archivo=real, diagrama=nuevo['_id']))
    assert rev['n_problemas'] == 0, rev['problemas']
