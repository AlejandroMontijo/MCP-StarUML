# mdj_robustez_generar: diagrama de analisis (robustez) con la disposicion del curso.
import pytest

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


def _diagrama(vacio):
    return ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='clases', nombre='Analisis', dentro_de='Analisis'))['diagrama']


def test_disposicion_del_analisis(vacio):
    dg = _diagrama(vacio)
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama=dg, paquete='Analisis', **_caso()))
    assert r['oose'] == {'problemas': [], 'avisos': []}
    assert r['lineas_que_cruzan_cajas'] == []
    # actor-pantalla (3) + pantalla-control (3) + entre entidades (3); control-entidad no por defecto
    assert r['asociaciones'] == 9
    doc = M.Doc(vacio)
    d = doc.diagram('Analisis')
    caja = {doc.name_of(v['model']['$ref']): v for v in d['ownedViews']
            if isinstance(v.get('model'), dict) and v['_type'] in ('UMLClassView', 'UMLActorView')}
    # actor | pantallas en columna | control | entidades
    assert caja['Asesor']['left'] < caja['PantallaCliente']['left'] < caja['ControlPedido']['left'] < \
        min(caja[n]['left'] for n in ('Cliente', 'Pedido', 'LineaPedido', 'Producto'))
    assert caja['PantallaCliente']['left'] == caja['PantallaPedido']['left'] == caja['PantallaConfirmacion']['left']
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


def test_el_generador_generico_manda_a_robustez(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='clases', nombre='X'))['diagrama']
    r = tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=[{'simbolo': 'Entity', 'nombre': 'E'}])
    assert 'error' in r and 'mdj_robustez_generar' in r['error']
