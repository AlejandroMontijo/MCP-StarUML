# mdj_robustez_generar: diagrama de analisis (robustez) con la disposicion del curso.
import os

import pytest

from staruml_mcp import robustez as RB
from apoyo import M, ok, tool, ids_integros


def _caso(**extra):
    return dict(
        actores=[{'nombre': 'Asesor'}],
        pantallas=[{'nombre': 'PantallaCliente', 'nota': 'F1: identificar o registrar al cliente.'},
                   {'nombre': 'PantallaPedido', 'nota': 'F2: armar el pedido con sus productos.'},
                   {'nombre': 'PantallaConfirmacion'}],
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


def _diagrama(vacio, nombre='Analisis'):
    return ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='clases', nombre=nombre, dentro_de='Analisis'))['diagrama']


def _cajas(doc, d):
    return {doc.name_of(v['model']['$ref']): v for v in d['ownedViews']
            if isinstance(v.get('model'), dict) and v['_type'] in ('UMLClassView', 'UMLActorView')}


def _lineas(doc, d, tipos=('UMLAssociationView', 'UMLGeneralizationView')):
    """[(vista, nombre de la caja de tail, nombre de la de head, puntos)]."""
    por_id = {v['_id']: doc.name_of(v['model']['$ref']) for v in d['ownedViews'] if isinstance(v.get('model'), dict)}
    res = []
    for v in d['ownedViews']:
        if v['_type'] in tipos:
            pts = [tuple(float(n) for n in q.split(':')) for q in v['points'].split(';')]
            res.append((v, por_id[v['tail']['$ref']], por_id[v['head']['$ref']], pts))
    return res


def _cruces(lineas):
    """Veces que se cortan tramos de lineas distintas (sin contar los extremos)."""
    def lado(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return (v > 1e-9) - (v < -1e-9)
    n = 0
    for i, pa in enumerate(lineas):
        for pb in lineas[i + 1:]:
            n += sum(lado(p, q, r) * lado(p, q, s) < 0 and lado(r, s, p) * lado(r, s, q) < 0
                     for p, q in zip(pa, pa[1:]) for r, s in zip(pb, pb[1:]))
    return n


def _en_borde(p, v):
    """'v' si el punto esta en el borde de arriba o de abajo de la caja, 'h' si en el izquierdo o el derecho."""
    x0, y0, x1, y1 = v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height']
    if x0 <= p[0] <= x1 and p[1] in (y0, y1):
        return 'v'
    if y0 <= p[1] <= y1 and p[0] in (x0, x1):
        return 'h'
    return None


def test_disposicion_del_analisis(vacio):
    dg = _diagrama(vacio)
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', **_caso()))
    assert r['oose'] == {'problemas': [], 'avisos': []}
    assert r['lineas_que_cruzan_cajas'] == []
    # actor-pantalla (3) + pantalla-control (3) + entre entidades (3); control-entidad no por defecto
    assert r['asociaciones'] == 9
    doc = M.Doc(vacio)
    d = doc.diagram('Analisis')
    caja = _cajas(doc, d)
    # actor | pantallas en columna | control | entidades
    assert caja['Asesor']['left'] < caja['PantallaCliente']['left'] < caja['ControlPedido']['left'] < \
        min(caja[n]['left'] for n in ('Cliente', 'Pedido', 'LineaPedido', 'Producto'))
    # la columna de pantallas va centrada (no alineada a la izquierda): StarUML dibuja el icono de la boundary en el
    # centro de su caja y asi los iconos quedan en una vertical aunque los nombres midan distinto
    centros = {round(caja[n]['left'] + caja[n]['width'] / 2) for n in ('PantallaCliente', 'PantallaPedido',
                                                                       'PantallaConfirmacion')}
    assert max(centros) - min(centros) <= 1
    assert caja['PantallaCliente']['top'] < caja['PantallaPedido']['top'] < caja['PantallaConfirmacion']['top']
    # el dominio por capas segun la navegabilidad
    assert caja['Cliente']['top'] < caja['Pedido']['top'] < caja['LineaPedido']['top'] < caja['Producto']['top']
    # notas de las pantallas que la tienen, sin encimarse con las cajas
    notas = [v for v in d['ownedViews'] if v['_type'] == 'UMLNoteView']
    assert len(notas) == 2
    for nt in notas:
        for v in caja.values():
            assert not (nt['left'] < v['left'] + v['width'] and v['left'] < nt['left'] + nt['width'] and
                        nt['top'] < v['top'] + v['height'] and v['top'] < nt['top'] + nt['height'])
    # atributos solo en las entidades y flechas de navegacion en el dominio
    assert [a['name'] for a in doc.find('Pedido')['attributes']] == ['folio', 'total']
    assert not doc.find('PantallaCliente').get('attributes')
    asoc = next(o for o in doc.ids.values() if o and o.get('_type') == 'UMLAssociation'
                and doc.name_of(o['end1']['reference']['$ref']) == 'Cliente')
    assert asoc['end2']['multiplicity'] == '0..*' and asoc['end2'].get('navigable') in (True, 'navigable')
    assert ids_integros(vacio)


def test_lineas_del_control_opcionales(vacio):
    dg = _diagrama(vacio)
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', lineas_control=True, **_caso()))
    assert r['asociaciones'] == 9 + 3  # el control no se une a LineaPedido (depende de Pedido)
    assert r['oose'] == {'problemas': [], 'avisos': []}


def test_errores(vacio):
    dg = _diagrama(vacio)
    caso = _caso()
    caso['asociaciones'] = caso['asociaciones'] + [{'desde': 'PantallaCliente', 'hasta': 'Cliente'}]
    r = tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', **caso)
    assert 'error' in r and 'no es una entidad' in r['error']
    caso = _caso()
    caso['entidades'][2]['depende_de'] = 'NoExiste'
    assert 'error' in tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', **caso)
    caso = _caso()
    caso['entidades'].append({'nombre': 'Cliente'})
    r = tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', **caso)
    assert 'error' in r and 'repetidos' in r['error']


def _sin_asociacion_al_padre(c):
    c['asociaciones'] = [a for a in c['asociaciones'] if 'LineaPedido' not in (a['desde'], a['hasta'])]


def _depende_de_dependiente(c):
    c['entidades'][3]['depende_de'] = 'LineaPedido'


@pytest.mark.parametrize('cambio, mensaje', [
    (_sin_asociacion_al_padre, 'no hay una asociacion entre las dos'),
    (_depende_de_dependiente, 'tambien es dependiente'),
    (lambda c: c.update(generalizaciones=[{'hijo': 'Pedido', 'padre': 'Cliente'},
                                          {'hijo': 'Cliente', 'padre': 'Pedido'}]), 'ciclo'),
    (lambda c: c.update(generalizaciones=[{'hijo': 'Pedido', 'padre': 'PantallaPedido'}]), 'no es una entidad'),
    (lambda c: c.update(generalizaciones=[{'hijo': 'Pedido', 'padre': 'Pedido'}]), 'hacia si misma'),
    (lambda c: c['actores'][0].update(pantallas=['PantallaQueNoEsta']), 'no esta en la lista'),
    (lambda c: c.update(asociaciones=['Cliente-Pedido']), 'debe ser un objeto'),
])
def test_entradas_invalidas(vacio, cambio, mensaje):
    _diagrama(vacio)
    caso = _caso()
    cambio(caso)
    with pytest.raises(M.MdjError, match=mensaje):
        RB.generar_robustez(M.Doc(vacio), 'Analisis', 'Analisis', **caso)


def test_no_dibuja_dos_veces_ni_fuera_de_un_diagrama_de_clases(vacio):
    dg = _diagrama(vacio)
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', **_caso()))
    r = tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', **_caso())
    assert 'error' in r and 'ya esta dibujado' in r['error']
    r = tool('mdj_robustez_generar', archivo=vacio, diagrama='cu_1_FB', paquete='Analisis', **_caso())
    assert 'error' in r and 'diagrama de clases' in r['error']


def test_el_generador_generico_manda_a_robustez(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='clases', nombre='X'))['diagrama']
    r = tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=[{'simbolo': 'Entity', 'nombre': 'E'}])
    assert 'error' in r and 'mdj_robustez_generar' in r['error']


# ---------------------------------------------------------------------------
# Lineas del dominio: rectilineas, sin cruces evitables, lazos y etiquetas
# ---------------------------------------------------------------------------

def test_lineas_del_dominio_entran_derechas_a_la_caja(vacio):
    # en oblicua StarUML apunta el ultimo tramo al centro de la caja y la linea se quiebra junto a ella si su puerto no
    # esta en el centro; rectilinea la baja en perpendicular al borde desde el punto vecino
    dg = _diagrama(vacio)
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', **_caso()))
    doc = M.Doc(vacio)
    d = doc.diagram('Analisis')
    caja = _cajas(doc, d)
    entidades = {'Cliente', 'Pedido', 'LineaPedido', 'Producto'}
    dominio = [x for x in _lineas(doc, d) if x[1] in entidades]
    assert len(dominio) == 3
    for v, t, h, pts in dominio:
        assert v['lineStyle'] == 0, (t, h)
        assert all(p[0] == q[0] or p[1] == q[1] for p, q in zip(pts, pts[1:])), (t, h, pts)
        for p, q, n in ((pts[0], pts[1], t), (pts[-1], pts[-2], h)):
            assert _en_borde(p, caja[n]) == ('v' if p[0] == q[0] else 'h'), (t, h, pts)
    # actor -> pantalla y pantalla -> control siguen siendo rectas oblicuas
    assert all(v['lineStyle'] == 1 for v, t, h, _ in _lineas(doc, d) if t not in entidades)


def test_orden_de_los_carriles():
    # dos lineas que salen de la misma caja hacia la derecha (sus puertos en el orden de a donde van): la que va mas
    # lejos va arriba, si no su tramo horizontal cruza el vertical de la otra; sin importar en que orden se pidieron
    lejos = {'sube_a': [120], 'baja_a': [300]}
    cerca = {'sube_a': [100], 'baja_a': [200]}
    assert RB._orden_canal([lejos, cerca]) == [lejos, cerca]
    assert RB._orden_canal([cerca, lejos]) == [lejos, cerca]
    # hacia la izquierda, igual
    lejos = {'sube_a': [280], 'baja_a': [100]}
    cerca = {'sube_a': [300], 'baja_a': [200]}
    assert RB._orden_canal([cerca, lejos]) == [lejos, cerca]
    # una de una fila que sale y vuelve a la de abajo (dos tramos que bajan) va debajo de la que pasa sobre ella
    fila = {'sube_a': [], 'baja_a': [140, 180]}
    larga = {'sube_a': [100], 'baja_a': [300]}
    assert RB._orden_canal([fila, larga]) == [larga, fila]
    # la que pasa de lado a lado por el tramo de otra no pone condicion; un cruce inevitable (ciclo) no se atora
    paso = {'sube_a': [150], 'baja_a': [150]}
    a = {'sube_a': [100], 'baja_a': [200]}
    b = {'sube_a': [220], 'baja_a': [150]}
    orden = RB._orden_canal([a, b, paso])
    assert len(orden) == 3 and {id(x) for x in orden} == {id(a), id(b), id(paso)}


@pytest.mark.parametrize('orden', [[0, 1, 2, 3, 4, 5], [5, 4, 3, 2, 1, 0], [2, 5, 0, 3, 1, 4]])
def test_lineas_de_una_entidad_a_sus_vecinas_no_se_cruzan(vacio, orden):
    # antes los carriles se repartian en el orden de las asociaciones y estas lineas se cruzaban de 6 a 8 veces
    hijos = ['Uno', 'Dos', 'Tres', 'Cuatro', 'Cinco', 'Seis']
    dg = _diagrama(vacio)
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', actores=[{'nombre': 'U'}],
                pantallas=[{'nombre': 'P'}], control={'nombre': 'Ctl'},
                entidades=[{'nombre': 'Padre', 'atributos': ['a', 'b', 'c']}] +
                          [{'nombre': h, 'atributos': ['x', 'y', 'z'][:i % 3]} for i, h in enumerate(hijos)],
                asociaciones=[{'desde': 'Padre', 'hasta': hijos[i], 'mult_desde': '1', 'mult_hacia': '0..*'}
                              for i in orden]))
    assert r['lineas_que_cruzan_cajas'] == [] and r['etiquetas_que_chocan'] == []
    doc = M.Doc(vacio)
    assert _cruces([pts for _, t, _, pts in _lineas(doc, doc.diagram('Analisis')) if t == 'Padre']) == 0


def test_lineas_del_dominio_no_se_cruzan_si_el_orden_de_las_filas_lo_evita(vacio):
    # el orden por baricentro dejaba un cruce entre Factura-Producto y Linea-Almacen; ahora se queda con el orden de
    # menos cruces y luego intercambia cajas vecinas mientras eso quite cruces
    asociaciones = [('Categoria', '*', 'Direccion', '*'), ('Categoria', '1..*', 'Factura', '1'),
                    ('Categoria', '', 'Linea', '1..*'), ('Cliente', '1..*', 'Almacen', '1'),
                    ('Direccion', '0..1', 'Cliente', ''), ('Factura', '0..1', 'Direccion', '1'),
                    ('Factura', '0..1', 'Producto', '1'), ('Linea', '1', 'Almacen', '0..1'), ('Linea', '*', 'Factura', '*')]
    dg = _diagrama(vacio)
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', actores=[{'nombre': 'Usuario'}],
                pantallas=[{'nombre': 'Pantalla'}], control={'nombre': 'Control'},
                entidades=[{'nombre': n} for n in ('Categoria', 'Factura', 'Direccion', 'Linea', 'Producto', 'Cliente',
                                                   'Almacen')],
                asociaciones=[{'desde': a, 'hasta': b, 'mult_desde': ma, 'mult_hacia': mb}
                              for a, ma, b, mb in asociaciones]))
    assert r['lineas_que_cruzan_cajas'] == [] and r['etiquetas_que_chocan'] == []
    doc = M.Doc(vacio)
    assert _cruces([pts for *_, pts in _lineas(doc, doc.diagram('Analisis'))]) == 0


def test_lazo_por_abajo_conserva_su_ancho(vacio):
    # con lineas por arriba el lazo va por abajo. StarUML dibuja los lazos rectilineos, pero si el archivo dice
    # oblicuo primero los calcula asi y por abajo los angosta: las etiquetas de sus dos extremos se enciman
    dg = _diagrama(vacio)
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', actores=[{'nombre': 'U'}],
                pantallas=[{'nombre': 'P'}], control={'nombre': 'Ctl'},
                entidades=[{'nombre': 'Raiz', 'atributos': ['a']}, {'nombre': 'Nodo', 'atributos': ['a', 'b']}],
                asociaciones=[{'desde': 'Raiz', 'hasta': 'Nodo', 'mult_desde': '1', 'mult_hacia': '0..*'},
                              {'desde': 'Raiz', 'hasta': 'Nodo', 'mult_desde': '1', 'mult_hacia': '0..1',
                               'rol_hacia': 'principal'},
                              {'desde': 'Nodo', 'hasta': 'Nodo', 'mult_desde': '0..1', 'mult_hacia': '0..*',
                               'rol_desde': 'padre', 'rol_hacia': 'hijos'}]))
    assert r['etiquetas_que_chocan'] == [] and r['lineas_que_cruzan_cajas'] == []
    doc = M.Doc(vacio)
    d = doc.diagram('Analisis')
    nodo = _cajas(doc, d)['Nodo']
    v, _, _, pts = next(x for x in _lineas(doc, d) if x[1] == x[2] == 'Nodo')
    assert v['lineStyle'] == 0 and len(pts) == 4
    abajo = nodo['top'] + nodo['height']
    assert pts[0][1] == pts[-1][1] == abajo and pts[1][1] == pts[2][1] > abajo
    assert pts[0][0] == pts[1][0] and pts[2][0] == pts[3][0]
    # las cuatro etiquetas (dos multiplicidades y dos roles) sin encimarse
    subs = {s['_id']: s for s in v['subViews']}
    rects = []
    for k in ('tailMultiplicityLabel', 'tailRoleNameLabel', 'headMultiplicityLabel', 'headRoleNameLabel'):
        lab = subs[v[k]['$ref']]
        cx, cy = RB._centro_etiqueta(v, lab)
        w = RB._ancho_etiqueta(lab['text'])
        rects.append((cx - w / 2, cy - 5.5, cx + w / 2, cy + 5.5))
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert not (a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]), (a, b)


def test_navegable_desde_y_depende_de_deciden_quien_va_arriba(vacio):
    dg = _diagrama(vacio)
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', actores=[{'nombre': 'U'}],
                pantallas=[{'nombre': 'P'}], control={'nombre': 'Ctl'}, lineas_control=True,
                entidades=[{'nombre': 'Orden', 'atributos': ['folio']},
                           {'nombre': 'Renglon', 'atributos': ['cantidad'], 'depende_de': 'Orden'},
                           {'nombre': 'Almacen', 'atributos': ['clave']},
                           {'nombre': 'Existencia', 'atributos': ['cantidad']}],
                asociaciones=[{'desde': 'Renglon', 'hasta': 'Orden', 'mult_desde': '1..*', 'mult_hacia': '1'},
                              {'desde': 'Almacen', 'hasta': 'Existencia', 'mult_desde': '1', 'mult_hacia': '0..*',
                               'navegable': 'desde'}]))
    assert r['etiquetas_que_chocan'] == [] and r['lineas_que_cruzan_cajas'] == []
    doc = M.Doc(vacio)
    d = doc.diagram('Analisis')
    caja = _cajas(doc, d)
    # la dependiente debajo de la entidad de la que depende, aunque la asociacion vaya de ella hacia la otra
    assert caja['Orden']['top'] < caja['Renglon']['top']
    # navegable 'desde': la flecha va de hasta a desde y el que navega (hasta) queda arriba
    assert caja['Existencia']['top'] < caja['Almacen']['top']
    asoc = next(o for o in doc.ids.values() if o and o.get('_type') == 'UMLAssociation'
                and doc.name_of(o['end1']['reference']['$ref']) == 'Almacen')
    assert asoc['end1'].get('multiplicity') == '1' and asoc['end2'].get('multiplicity') == '0..*'
    assert asoc['end1'].get('navigable') and not asoc['end2'].get('navigable')
    # cada multiplicidad junto a su caja: '1' junto a Almacen y '0..*' junto a Existencia
    v = next(x[0] for x in _lineas(doc, d) if {x[1], x[2]} == {'Almacen', 'Existencia'})
    subs = {s['_id']: s for s in v['subViews']}
    for lado, texto, n in (('tail', '1', 'Almacen'), ('head', '0..*', 'Existencia')):
        if doc.name_of(doc.ids[v[lado]['$ref']]['model']['$ref']) != n:
            lado = 'head' if lado == 'tail' else 'tail'
        lab = subs[v[lado + 'MultiplicityLabel']['$ref']]
        assert lab['text'] == texto
        cy = RB._centro_etiqueta(v, lab)[1]
        c = caja[n]
        assert min(abs(cy - c['top']), abs(cy - c['top'] - c['height'])) < 25
    # el control no se une a la dependiente
    assert not [x for x in _lineas(doc, d) if 'Ctl' in (x[1], x[2]) and 'Renglon' in (x[1], x[2])]


def test_generalizaciones_y_actor_secundario(vacio):
    # aun no estan en el esquema de la herramienta: se prueban con la funcion
    _diagrama(vacio)
    doc = M.Doc(vacio)
    r = RB.generar_robustez(
        doc, 'Analisis', 'Analisis',
        actores=[{'nombre': 'Asesor'}, {'nombre': 'Servicio de Correo', 'secundario': True,
                                        'pantallas': ['PantallaAviso']}],
        pantallas=[{'nombre': 'PantallaCliente'}, {'nombre': 'PantallaAviso'}], control={'nombre': 'Ctl'},
        entidades=[{'nombre': 'Cliente', 'atributos': ['nombre']}, {'nombre': 'ClienteEmpresa', 'atributos': ['rfc']},
                   {'nombre': 'ClienteParticular'}, {'nombre': 'Solicitud', 'atributos': ['folio']}],
        asociaciones=[{'desde': 'Cliente', 'hasta': 'Solicitud', 'mult_desde': '1', 'mult_hacia': '0..*'}],
        generalizaciones=[{'hijo': 'ClienteEmpresa', 'padre': 'Cliente'},
                          {'hijo': 'ClienteParticular', 'padre': 'Cliente'}])
    doc.save(backup=False)
    assert r['generalizaciones'] == 2 and r['lineas_que_cruzan_cajas'] == [] and r['etiquetas_que_chocan'] == []
    doc = M.Doc(vacio)
    d = doc.diagram('Analisis')
    caja = _cajas(doc, d)
    assert caja['Cliente']['top'] < min(caja['ClienteEmpresa']['top'], caja['ClienteParticular']['top'])
    gens = _lineas(doc, d, ('UMLGeneralizationView',))
    assert sorted((t, h) for _, t, h, _ in gens) == [('ClienteEmpresa', 'Cliente'), ('ClienteParticular', 'Cliente')]
    assert all(v['lineStyle'] == 0 for v, _, _, _ in gens)
    # el sistema le avisa al actor secundario: la flecha va de la pantalla hacia el
    assert [(t, h) for _, t, h, _ in _lineas(doc, d, ('UMLAssociationView',)) if 'Servicio de Correo' in (t, h)] == \
        [('PantallaAviso', 'Servicio de Correo')]
    assert ids_integros(vacio)


def test_regenerar_en_otro_diagrama_reusa_las_asociaciones(vacio):
    cuenta = lambda: sum(1 for o in M.Doc(vacio).ids.values() if o and o.get('_type') == 'UMLAssociation')
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio), paquete='Analisis', **_caso()))
    antes = cuenta()
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=_diagrama(vacio, 'Analisis 2'), paquete='Analisis',
                **_caso()))
    assert r['asociaciones_reusadas'] == r['asociaciones'] == 9
    assert cuenta() == antes
    assert ids_integros(vacio)


# ---------------------------------------------------------------------------
# Notas
# ---------------------------------------------------------------------------

def test_notas_con_las_medidas_que_usa_staruml():
    # una nota corta se ajusta a su texto; una palabra que no cabe ensancha la nota (StarUML la ensancha igual)
    t, w, h = RB._medidas_nota('Asigna el anaquel.')
    assert t == 'Asigna el anaquel.' and w < RB.ANCHO_NOTA and h >= 11 + 2 + 10
    url = 'https://servidor.ejemplo/una/ruta/bastante/larga/del/documento/de/consulta'
    t, w, _ = RB._medidas_nota('Ver ' + url)
    assert w >= RB._ancho11(url) + 20
    # con varios parrafos StarUML dibuja cada uno partido al ancho menos 11 pero baja al siguiente lo que mide partido
    # al ancho menos 1: el ancho elegido da los mismos renglones en los dos casos y el alto alcanza para todo
    texto = ('Primera linea de la nota.\nSegunda linea, que es bastante mas larga que la primera y que tendra que '
             'partirse en varios renglones para caber en el ancho de la nota.\n\nUltima.')
    t, w, h = RB._medidas_nota(texto)
    parrafos = t.split('\n')
    assert t.split() == texto.split()
    for p in parrafos[:-1]:
        assert RB._renglones(p, w - 11) == RB._renglones(p, w - 1), (p, w)
    assert h >= sum(RB._renglones(p, w - 20) * 11 + 2 for p in parrafos) + 10


def test_nota_con_varios_parrafos_en_el_diagrama(vacio):
    dg = _diagrama(vacio)
    caso = _caso()
    caso['pantallas'][0]['nota'] = ('Junta las pantallas de busqueda y alta del cliente.\nTodas sirven para lo mismo: '
                                    'buscar al cliente o darlo de alta y capturar sus datos de contacto completos.\n'
                                    '\nSin apartar nada.')
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', **caso))
    assert r['lineas_que_cruzan_cajas'] == []
    doc = M.Doc(vacio)
    nota = next(v for v in doc.diagram('Analisis')['ownedViews'] if v['_type'] == 'UMLNoteView'
                and v['text'].startswith('Junta'))
    for p in nota['text'].split('\n')[:-1]:
        assert RB._renglones(p, nota['width'] - 11) == RB._renglones(p, nota['width'] - 1)


# ---------------------------------------------------------------------------
# StarUML real: un analisis del tamano de un caso de uso completo
# ---------------------------------------------------------------------------

ATRIBUTOS = {
    'Cliente': 6, 'SolicitudRenta': 9, 'EquipoSolicitado': 3, 'RequerimientoTecnico': 5, 'EvaluacionTecnica': 4,
    'Equipo': 8, 'UnidadFisica': 5, 'OcupacionUnidad': 5, 'PeriodoSolicitado': 4, 'RequisitoRenta': 5,
    'Cotizacion': 6, 'DetalleCotizacion': 6, 'Accesorio': 5, 'DecisionCliente': 4, 'ContratacionRenta': 8,
    'OrdenEntrega': 6, 'ClienteParticular': 0, 'ClienteEmpresa': 3}
ASOCIACIONES = [
    ('Cliente', '1', 'SolicitudRenta', '0..*', ''), ('SolicitudRenta', '1', 'RequerimientoTecnico', '1..*', ''),
    ('RequerimientoTecnico', '1..*', 'EvaluacionTecnica', '0..*', ''),
    ('EvaluacionTecnica', '0..*', 'Equipo', '1', 'recomendado'), ('Equipo', '1', 'UnidadFisica', '0..*', ''),
    ('UnidadFisica', '1', 'OcupacionUnidad', '0..*', ''), ('DetalleCotizacion', '0..*', 'Accesorio', '0..1', ''),
    ('SolicitudRenta', '1', 'PeriodoSolicitado', '1', ''), ('SolicitudRenta', '1', 'RequisitoRenta', '0..*', ''),
    ('SolicitudRenta', '1', 'Cotizacion', '0..*', ''), ('SolicitudRenta', '1', 'EquipoSolicitado', '1..*', ''),
    ('Cotizacion', '1', 'DetalleCotizacion', '1..*', ''), ('Cotizacion', '1', 'DecisionCliente', '0..1', ''),
    ('Cotizacion', '1', 'ContratacionRenta', '0..1', ''), ('Cliente', '1', 'ContratacionRenta', '0..*', ''),
    ('ContratacionRenta', '0..*', 'UnidadFisica', '1', ''), ('ContratacionRenta', '0..*', 'Accesorio', '0..*', ''),
    ('ContratacionRenta', '1', 'OrdenEntrega', '1', ''), ('EquipoSolicitado', '1', 'EvaluacionTecnica', '0..1', ''),
    ('EvaluacionTecnica', '0..*', 'Equipo', '0..1', 'alternativo'), ('DetalleCotizacion', '0..*', 'Equipo', '0..1', ''),
    ('Equipo', '0..*', 'Accesorio', '0..*', '')]
PANTALLAS = ['BC_RegistroSolicitudRenta', 'BC_SeleccionEquipo', 'BC_Disponibilidad', 'BC_CotizacionRenta',
             'BC_ConfirmacionRenta', 'BC_ServicioCorreo']


@pytest.fixture
def staruml(monkeypatch):
    if not M.staruml_cli():
        pytest.skip('StarUML no esta instalado (o define STARUML_MCP_STARUML_BIN)')
    monkeypatch.setenv('STARUML_MCP_EXPORT_TIMEOUT', os.environ.get('STARUML_MCP_EXPORT_TIMEOUT', '300'))


@pytest.mark.parametrize('lineas_control', [False, True])
def test_staruml_dibuja_un_analisis_completo_sin_encimar_nada(vacio, tmp_path, staruml, lineas_control):
    # 6 boundaries con su nota, 1 control y 18 entidades con 22 asociaciones (dos entre el mismo par, con rol),
    # un lazo y una nota de varios parrafos: StarUML lo exporta y svg_revisar no encuentra lineas sobre cajas o
    # textos ni etiquetas encimadas
    notas = ['Junta las pantallas del registro: buscar al cliente o darlo de alta y capturar la obra, el periodo, '
             'las condiciones y el equipo que pide.',
             'Registra los requerimientos, compara los equipos y elige el recomendado y la alternativa.',
             'Consulta las unidades y su ocupacion.\nEscoge una libre, sin apartarla.\n\nEl periodo ya viene de antes.',
             'Muestra la cotizacion por partidas, el IVA, el total, el deposito y los requisitos.',
             'Muestra las condiciones completas y registra la decision.',
             'Conecta al sistema con el servicio de correo.']
    dg = _diagrama(vacio)
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', lineas_control=lineas_control,
                actores=[{'nombre': 'Asesor de Renta', 'pantallas': PANTALLAS[:5]},
                         {'nombre': 'Servicio de Correo', 'pantallas': PANTALLAS[5:]}],
                pantallas=[{'nombre': n, 'nota': t} for n, t in zip(PANTALLAS, notas)],
                control={'nombre': 'ControlContratacionRenta'},
                entidades=[{'nombre': n, 'atributos': [f'{n[0].lower()}{n[1:]}{i}' for i in range(k)]}
                           for n, k in ATRIBUTOS.items()],
                asociaciones=[{'desde': a, 'hasta': b, 'mult_desde': ma, 'mult_hacia': mb, 'rol_hacia': rol}
                              for a, ma, b, mb, rol in ASOCIACIONES] +
                             [{'desde': 'Equipo', 'hasta': 'Equipo', 'mult_desde': '0..1', 'mult_hacia': '0..*',
                               'rol_hacia': 'compatibles'}]))
    assert r['lineas_que_cruzan_cajas'] == [] and r['etiquetas_que_chocan'] == []
    assert r['oose'] == {'problemas': [], 'avisos': []}
    v = ok(tool('mdj_validar', archivo=vacio))
    assert (v['n_duplicados'], v['n_colgantes'], v['n_parent_mismatch']) == (0, 0, 0)
    svg = ok(tool('staruml_exportar', archivo=vacio, carpeta=str(tmp_path / 'svg'), diagrama=dg))['archivos'][0]
    rev = ok(tool('svg_revisar', svg=svg, archivo=vacio, diagrama=dg))
    assert rev['n_problemas'] == 0, rev['problemas']


def test_depende_de_usa_la_asociacion_que_ya_esta_en_el_modelo(vacio):
    """La asociacion entre la dependiente y su padre no hay que repetirla si ya existe en el modelo: se dibuja como
    esta, sin crear otra ni cambiarle nada."""
    dg = _diagrama(vacio)
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', **_caso()))
    doc = M.Doc(vacio)
    par = lambda o: {doc.name_of(o['end1']['reference']['$ref']), doc.name_of(o['end2']['reference']['$ref'])}
    antes = [o for o in doc.ids.values() if o and o.get('_type') == 'UMLAssociation' and par(o) == {'Pedido', 'LineaPedido'}]
    assert len(antes) == 1
    segundo = M.crear_diagrama(doc, 'clases', 'cu_1 sin repetir', dentro_de='Analisis')
    doc.save(backup=False)
    caso = _caso()
    caso['asociaciones'] = [a for a in caso['asociaciones'] if 'LineaPedido' not in (a['desde'], a['hasta'])]
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=segundo['_id'], paquete='Analisis', **caso))
    doc = M.Doc(vacio)
    par = lambda o: {doc.name_of(o['end1']['reference']['$ref']), doc.name_of(o['end2']['reference']['$ref'])}
    despues = [o for o in doc.ids.values() if o and o.get('_type') == 'UMLAssociation' and par(o) == {'Pedido', 'LineaPedido'}]
    assert [o['_id'] for o in despues] == [antes[0]['_id']]  # la misma, sin duplicar
    assert despues[0]['end1'] == antes[0]['end1'] and despues[0]['end2'] == antes[0]['end2']  # sin cambios
    vistas = [v for v in doc.diagram(segundo['_id'])['ownedViews'] if v['_type'] == 'UMLAssociationView'
              and v['model']['$ref'] == antes[0]['_id']]
    assert len(vistas) == 1 and r['oose']['problemas'] == []
    assert ids_integros(vacio)
