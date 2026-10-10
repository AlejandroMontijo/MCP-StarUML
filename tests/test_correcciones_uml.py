# Correcciones de staruml_uml: cada relacion y cada elemento quedan en el campo donde StarUML los guarda (mensajes en
# la interaccion, transiciones en la region, columnas, atributos, literales...), un elemento dentro de si mismo o un
# ciclo de contencion es un error claro (no un ciclo sin fin), mdj_elemento_crear no crea diagramas ni extremos
# sueltos, mdj_vista_agregar usa el simbolo que corresponde al elemento y solo dibuja una relacion entre las vistas de
# sus extremos, el nombre queda donde StarUML lo muestra (o se avisa), los mensajes llegan a la linea punteada de la
# lifeline, la disposicion en secuencia no se encima con lo que ya habia, mdj_validar admite las anotaciones en
# cualquier diagrama, los nombres de los iconos no quedan bajo las lineas y el orden de las relaciones no importa.
# Al final, lo mismo con el StarUML verdadero (se omite si no esta instalado).
import os
import threading

import pytest

import staruml_uml as U
from apoyo import M, ok, tool, ids_integros


def _padre_y_campo(doc, i):
    padre = doc.ids[doc.parent[i]]
    el = doc.ids[i]
    campo = next(k for k, v in padre.items() if isinstance(v, list) and any(x is el for x in v))
    return padre['_type'], campo


def _secuencia(vacio, nombre='Cobro'):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='secuencia', nombre=nombre))['diagrama']
    a = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Lifeline', nombre='caja', x=100, y=60))
    b = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Lifeline', nombre='banco', x=400, y=60))
    return dg, a, b


# ---------------------------------------------------------------------------
# Relaciones y elementos en su campo
# ---------------------------------------------------------------------------

def test_mensaje_transicion_y_flujo_van_donde_los_guarda_staruml(vacio):
    dg, a, b = _secuencia(vacio)
    r = ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLMessage', origen=a['elemento'], destino=b['elemento'],
                nombre='cobrar()'))
    doc = M.Doc(vacio)
    assert _padre_y_campo(doc, r['relacion']) == ('UMLInteraction', 'messages')
    assert [m['nombre'] for m in ok(tool('mdj_secuencia', archivo=vacio, diagrama=dg))['mensajes']] == ['cobrar()']
    # con la interaccion como dueno, tambien en messages
    inter = doc.parent[dg]
    r2 = ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLMessage', origen=b['elemento'], destino=a['elemento'],
                 nombre='ok', dueno=inter, propiedades={'messageSort': 'reply'}))
    assert _padre_y_campo(M.Doc(vacio), r2['relacion']) == ('UMLInteraction', 'messages')
    # se dibuja entre las lifelines de sus extremos sin indicarlas
    ok(tool('mdj_vista_agregar', archivo=vacio, diagrama=dg, elemento=r['relacion']))

    de = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='estados', nombre='E'))['diagrama']
    e1 = ok(tool('mdj_dibujar', archivo=vacio, diagrama=de, simbolo='Simple State', nombre='A', x=40, y=40))
    e2 = ok(tool('mdj_dibujar', archivo=vacio, diagrama=de, simbolo='Simple State', nombre='B', x=300, y=40))
    t = ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLTransition', origen=e1['elemento'], destino=e2['elemento']))
    assert _padre_y_campo(M.Doc(vacio), t['relacion']) == ('UMLRegion', 'transitions')

    da = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='actividades', nombre='Act'))['diagrama']
    x1 = ok(tool('mdj_dibujar', archivo=vacio, diagrama=da, simbolo='Action', nombre='X', x=40, y=40))
    x2 = ok(tool('mdj_dibujar', archivo=vacio, diagrama=da, simbolo='Action', nombre='Y', x=300, y=40))
    f = ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLControlFlow', origen=x1['elemento'], destino=x2['elemento']))
    assert _padre_y_campo(M.Doc(vacio), f['relacion']) == ('UMLActivity', 'edges')
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['metamodelo'] == []
    assert ids_integros(vacio)


def test_elemento_crear_usa_el_campo_propio_del_contenedor(vacio):
    pares = {('ERDEntity', 'ERDColumn'): 'columns', ('UMLClass', 'UMLAttribute'): 'attributes',
             ('UMLClass', 'UMLOperation'): 'operations', ('UMLEnumeration', 'UMLEnumerationLiteral'): 'literals',
             ('UMLRegion', 'UMLState'): 'vertices', ('UMLStateMachine', 'UMLRegion'): 'regions',
             ('UMLInteraction', 'UMLLifeline'): 'participants', ('UMLInteraction', 'UMLMessage'): 'messages',
             ('UMLOperation', 'UMLParameter'): 'parameters', ('UMLActivity', 'UMLAction'): 'nodes',
             ('SysMLBlock', 'SysMLFlowProperty'): 'flowProperties', ('UMLPackage', 'UMLClass'): 'ownedElements'}
    for (padre, hijo), campo in pares.items():
        assert U.campo_para(padre, hijo)['name'] == campo, (padre, hijo)
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='erd', nombre='Datos'))
    e = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Datos', simbolo='Entity', nombre='Envio', x=40, y=40))
    ok(tool('mdj_elemento_crear', archivo=vacio, tipo='ERDColumn', nombre='id_envio', dentro_de=e['elemento']))
    ok(tool('mdj_elemento_crear', archivo=vacio, tipo='ERDColumn', nombre='fecha', dentro_de=e['elemento'], campo='columns'))
    ent = M.Doc(vacio).get(e['elemento'])
    assert [c['name'] for c in ent['columns']] == ['id_envio', 'fecha'] and not ent.get('ownedElements')


def test_elemento_crear_pide_campo_si_hay_varios_igual_de_validos(vacio):
    r = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='sysml_parametrico', nombre='Par'))
    bloque = M.Doc(vacio).parent[r['diagrama']]
    antes = open(vacio, encoding='utf-8').read()
    err = tool('mdj_elemento_crear', archivo=vacio, tipo='SysMLProperty', nombre='motor', dentro_de=bloque)['error']
    assert 'campo' in err and 'parts' in err and 'values' in err
    assert open(vacio, encoding='utf-8').read() == antes
    p = ok(tool('mdj_elemento_crear', archivo=vacio, tipo='SysMLProperty', nombre='motor', dentro_de=bloque, campo='parts'))
    assert _padre_y_campo(M.Doc(vacio), p['elemento']) == ('SysMLBlock', 'parts')


def test_elemento_crear_no_crea_diagramas_proyecto_ni_extremos(vacio):
    for t in ('UMLSequenceDiagram', 'UMLTimingDiagram', 'Project', 'UMLAssociationEnd', 'UMLConnectorEnd', 'UMLLinkEnd'):
        r = tool('mdj_elemento_crear', archivo=vacio, tipo=t, nombre='X')
        assert 'error' in r, t
    assert 'mdj_diagrama_crear' in tool('mdj_elemento_crear', archivo=vacio, tipo='UMLSequenceDiagram')['error']
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['metamodelo'] == []


def test_dibujar_no_mete_lifelines_en_campos_que_no_existen(vacio):
    """Un diagrama de secuencia fuera de su interaccion (armado a mano): dibujar una lifeline es error, no un archivo
    con UMLModel.participants o Project.attributes."""
    doc = M.Doc(vacio)
    modelo = M.modelo_raiz(doc)
    modelo['ownedElements'].append({'_type': 'UMLSequenceDiagram', '_id': doc.new_id(), '_parent': M.ref(modelo['_id']),
                                    'name': 'Suelta'})
    doc.reindex()
    doc.save(backup=False)
    antes = open(vacio, encoding='utf-8').read()
    r = tool('mdj_dibujar', archivo=vacio, diagrama='Suelta', simbolo='Lifeline', nombre='caja', x=60, y=60)
    assert 'error' in r and 'mdj_diagrama_crear' in r['error']
    assert open(vacio, encoding='utf-8').read() == antes
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['metamodelo'] == []


# ---------------------------------------------------------------------------
# Generar: ciclos de contencion y orden de las relaciones
# ---------------------------------------------------------------------------

def _con_limite(f, segundos=20):
    """Corre f en un hilo: si no termina en el limite (el ciclo sin fin de antes), la prueba falla en vez de colgarse."""
    res = {}

    def correr():
        try:
            res['valor'] = f()
        except Exception as e:  # noqa: BLE001
            res['error'] = e
    h = threading.Thread(target=correr, daemon=True)
    h.start()
    h.join(segundos)
    assert not h.is_alive(), 'no termino: ciclo sin fin'
    return res


@pytest.mark.parametrize('tipo, elementos, relaciones, ciclo', [
    ('componentes', [{'simbolo': 'Component', 'nombre': 'Pagos', 'dentro': 'Pagos'}, {'simbolo': 'Interface', 'nombre': 'IPago'}],
     [{'simbolo': 'Interface Realization', 'desde': 'Pagos', 'hasta': 'IPago'}], 'Pagos -> Pagos'),
    ('componentes', [{'simbolo': 'Component', 'nombre': 'A', 'dentro': 'B'}, {'simbolo': 'Component', 'nombre': 'B', 'dentro': 'A'}],
     [], 'A -> B -> A'),
    ('despliegue', [{'simbolo': 'Node', 'nombre': 'C', 'dentro': 'D'}, {'simbolo': 'Node', 'nombre': 'D', 'dentro': 'C'},
                    {'simbolo': 'Node', 'nombre': 'E'}], [{'simbolo': 'Communication Path', 'desde': 'C', 'hasta': 'E'}],
     'C -> D -> C'),
    ('componentes', [{'simbolo': 'Component', 'nombre': 'P', 'sobre': 'Q'}, {'simbolo': 'Port', 'nombre': 'Q', 'sobre': 'P'}],
     [], 'P -> Q -> P')])
def test_generar_rechaza_ciclos_de_contencion(vacio, tipo, elementos, relaciones, ciclo):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo=tipo, nombre='C'))['diagrama']
    antes = open(vacio, encoding='utf-8').read()
    res = _con_limite(lambda: tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=elementos,
                                   relaciones=relaciones))
    err = res['valor'].get('error', '')
    assert 'ciclo' in err.lower() and ciclo in err, res['valor']
    assert open(vacio, encoding='utf-8').read() == antes


def test_generar_no_depende_del_orden_de_las_relaciones(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='comunicacion', nombre='Com'))['diagrama']
    r = ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, disposicion='secuencia',
                elementos=[{'simbolo': 'Lifeline', 'nombre': 'a'}, {'simbolo': 'Lifeline', 'nombre': 'b'}],
                relaciones=[{'simbolo': 'Forward Message', 'hasta': 'c1', 'nombre': 'pedir'},
                            {'simbolo': 'Connector', 'desde': 'a', 'hasta': 'b', 'clave': 'c1'}]))
    assert r['lineas'] == 2
    doc = M.Doc(vacio)
    msj = doc.get(r['vistas']['~0'])
    assert msj['head']['$ref'] == r['vistas']['c1']  # el mensaje va sobre su conector
    err = tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=[{'simbolo': 'Lifeline', 'nombre': 'x'}],
               relaciones=[{'simbolo': 'Forward Message', 'hasta': 'c2', 'clave': 'c3'},
                           {'simbolo': 'Forward Message', 'hasta': 'c3', 'clave': 'c2'}])['error']
    assert 'ciclo' in err and 'c2' in err and 'c3' in err


# ---------------------------------------------------------------------------
# mdj_vista_agregar
# ---------------------------------------------------------------------------

def test_vista_agregar_usa_el_simbolo_del_elemento(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='estados', nombre='Envio'))['diagrama']
    a = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Simple State', nombre='Preparando', x=40, y=40))
    b = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Simple State', nombre='Enviado', x=300, y=40))
    c = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Composite State', nombre='Entregando', x=40, y=200))
    t = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Transition', desde=a['vista'], hasta=b['vista']))
    st = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Self Transition', sobre=b['vista']))
    d2 = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='estados', nombre='Resumen'))['diagrama']
    simbolo = lambda el, **k: ok(tool('mdj_vista_agregar', archivo=vacio, diagrama=d2, elemento=el, **k))['simbolo']
    assert simbolo(a['elemento'], x=40, y=40) == 'Simple State'
    assert simbolo(b['elemento'], x=300, y=40) == 'Simple State'
    assert simbolo(c['elemento'], x=40, y=200) == 'Composite State'
    assert simbolo(t['elemento']) == 'Transition'
    assert simbolo(st['elemento']) == 'Self Transition'
    # mensajes: el simbolo segun su messageSort
    ds, l1, l2 = _secuencia(vacio, 'S')
    for props, esperado in ((None, 'Message'), ({'messageSort': 'asynchCall'}, 'Async Message'),
                            ({'messageSort': 'reply'}, 'Reply Message'), ({'messageSort': 'createMessage'}, 'Create Message')):
        kw = {'propiedades': props} if props else {}
        m = ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLMessage', origen=l1['elemento'], destino=l2['elemento'], **kw))
        assert ok(tool('mdj_vista_agregar', archivo=vacio, diagrama=ds, elemento=m['relacion']))['simbolo'] == esperado
    # SysML: una parte es Part, no Constraint Property
    r = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='sysml_parametrico', nombre='Par'))
    bloque = M.Doc(vacio).parent[r['diagrama']]
    p = ok(tool('mdj_elemento_crear', archivo=vacio, tipo='SysMLProperty', nombre='motor', dentro_de=bloque, campo='parts'))
    assert ok(tool('mdj_vista_agregar', archivo=vacio, diagrama='Par', elemento=p['elemento'], x=60, y=80))['simbolo'] == 'Part'
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['metamodelo'] == []


def test_vista_agregar_dibuja_la_relacion_solo_entre_sus_extremos(vacio):
    dd = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='despliegue', nombre='Red'))['diagrama']
    n1 = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dd, simbolo='Node', nombre='Servidor web', x=40, y=40))
    n2 = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dd, simbolo='Node', nombre='Base de datos', x=400, y=40))
    n3 = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dd, simbolo='Node', nombre='Impresora', x=40, y=300))
    cp = ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLCommunicationPath', origen='Servidor web',
                 destino='Base de datos', nombre='JDBC'))
    err = tool('mdj_vista_agregar', archivo=vacio, diagrama=dd, elemento=cp['relacion'], desde=n3['vista'],
               hasta=n1['vista'])['error']
    assert 'Servidor web' in err and 'Impresora' in err
    ok(tool('mdj_vista_agregar', archivo=vacio, diagrama=dd, elemento=cp['relacion']))
    lineas = ok(tool('mdj_geometria', archivo=vacio, diagrama='Red'))['lineas']
    assert [(x['de'], x['a']) for x in lineas] == [('Servidor web', 'Base de datos')]
    v = next(x for x in M.Doc(vacio).diagram('Red')['ownedViews'] if x['_type'] == 'UMLCommunicationPathView')
    assert v['tail']['$ref'] == n1['vista'] and v['head']['$ref'] == n2['vista']


# ---------------------------------------------------------------------------
# Nombres donde StarUML los muestra; mensajes enganchados a la linea punteada
# ---------------------------------------------------------------------------

def test_el_nombre_queda_donde_staruml_lo_muestra(vacio):
    ds, l1, l2 = _secuencia(vacio, 'Seq')
    doc_ = lambda: M.Doc(vacio)
    d = ok(tool('mdj_dibujar', archivo=vacio, diagrama=ds, simbolo='Duration Constraint', nombre='{0..5s}', x=300, y=400))
    el = doc_().get(d['elemento'])
    assert (el.get('min'), el.get('max')) == ('0', '5s')
    i = ok(tool('mdj_dibujar', archivo=vacio, diagrama=ds, simbolo='State Invariant', nombre='abierto', sobre=l1['vista']))
    assert doc_().get(i['elemento']).get('invariant') == 'abierto'
    u = ok(tool('mdj_dibujar', archivo=vacio, diagrama=ds, simbolo='Interaction Use', nombre='Autenticar', x=60, y=450))
    doc = doc_()
    assert doc.get(doc.get(u['elemento'])['refersTo']['$ref'])['name'] == 'Autenticar'
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='bpmn', nombre='Proceso'))
    a = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Proceso', simbolo='Text Annotation', nombre='Maximo 2 dias', x=40, y=40))
    assert doc_().get(a['elemento']).get('text') == 'Maximo 2 dias'
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='c4', nombre='Contexto'))
    p1 = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Contexto', simbolo='Person', nombre='Cliente', x=40, y=40))
    p2 = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Contexto', simbolo='Software System', nombre='Tienda', x=400, y=40))
    rel = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Contexto', simbolo='Relationship', nombre='compra en',
                  desde=p1['vista'], hasta=p2['vista']))
    assert doc_().get(rel['elemento']).get('description') == 'compra en'
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='objetos', nombre='Objetos'))
    o1 = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Objetos', simbolo='Object', nombre='pedido1', x=40, y=40))
    o2 = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Objetos', simbolo='Object', nombre='cliente1', x=400, y=40))
    ok(tool('mdj_dibujar', archivo=vacio, diagrama='Objetos', simbolo='Link Object', nombre='envio1', desde=o1['vista'],
            hasta=o2['vista']))
    doc = doc_()
    assert any(o and o.get('_type') == 'UMLObject' and o.get('name') == 'envio1' for o in doc.ids.values())
    # lo que StarUML no muestra se avisa
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='clases', nombre='Clases'))
    f = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Clases', simbolo='Frame', nombre='Pedidos', x=20, y=300))
    assert f['avisos'] and 'Pedidos' in f['avisos'][0]
    da = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='actividades', nombre='A'))['diagrama']
    r = ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=da, elementos=[
        {'simbolo': 'Initial', 'nombre': 'inicio'}, {'simbolo': 'Action', 'nombre': 'Cobrar'}],
        relaciones=[{'simbolo': 'Control Flow', 'desde': 'inicio', 'hasta': 'Cobrar'}]))
    assert any('inicio' in x for x in r.get('nombres_no_visibles', [])) and not r.get('avisos')
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['metamodelo'] == []


def test_los_mensajes_llegan_a_la_linea_punteada_de_la_lifeline(vacio):
    """La plantilla de StarUML de un mensaje llega a un endpoint; entre lifelines debe llegar a la linea punteada de
    la de destino: en la caja StarUML corta la flecha en su borde y no muestra la activacion."""
    ds = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='secuencia', nombre='Compra'))['diagrama']
    r = ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=ds, disposicion='secuencia', elementos=[
        {'simbolo': 'Lifeline', 'nombre': 'cliente'}, {'simbolo': 'Lifeline', 'nombre': 'tienda'},
        {'simbolo': 'Lifeline', 'nombre': 'pedido'}],
        relaciones=[{'simbolo': 'Message', 'desde': 'cliente', 'hasta': 'tienda', 'nombre': 'comprar()'},
                    {'simbolo': 'Create Message', 'desde': 'tienda', 'hasta': 'pedido', 'nombre': 'new'}]))
    doc = M.Doc(vacio)
    m1, m2 = doc.get(r['vistas']['~0']), doc.get(r['vistas']['~1'])
    for m, destino in ((m1, 'tienda'), (m2, 'pedido')):
        cabeza = doc.get(m['head']['$ref'])
        assert cabeza['_type'] == 'UMLLinePartView' and doc.parent[cabeza['_id']] == r['vistas'][destino]
        assert doc.get(m['tail']['$ref'])['_type'] == 'UMLLinePartView'
    # la lifeline creada empieza a la altura del mensaje de creacion, como la dibuja StarUML, y termina con las demas
    ll = {k: doc.get(r['vistas'][k]) for k in ('tienda', 'pedido')}
    y = float(m2['points'].split(';')[0].split(':')[1])
    assert ll['pedido']['top'] == round(y - 20)
    assert ll['pedido']['top'] + ll['pedido']['height'] == ll['tienda']['top'] + ll['tienda']['height']
    # tambien al dibujar un mensaje existente con mdj_vista_agregar
    ds2, a, b = _secuencia(vacio, 'Otra')
    msj = ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLMessage', origen=a['elemento'], destino=b['elemento']))
    v = ok(tool('mdj_vista_agregar', archivo=vacio, diagrama=ds2, elemento=msj['relacion']))
    doc = M.Doc(vacio)
    assert doc.get(doc.get(v['vista'])['head']['$ref'])['_type'] == 'UMLLinePartView'


def test_dibujar_mensajes_uno_debajo_de_otro(vacio):
    """Con mdj_dibujar cada mensaje va debajo del anterior (o a la y pedida), de linea punteada a linea punteada;
    antes todos quedaban a la misma altura, encimados, y llegaban a la caja de la lifeline."""
    dg, a, b = _secuencia(vacio, 'D')
    m1 = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Message', nombre='cobrar()', desde='caja', hasta='banco'))
    m2 = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Reply Message', nombre='ok', desde=b['vista'],
                 hasta=a['vista']))
    m3 = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Message', nombre='imprimir()', desde='caja',
                 hasta='banco', y=400))
    doc = M.Doc(vacio)
    ys = []
    for m in (m1, m2, m3):
        v = doc.get(m['vista'])
        assert doc.get(v['head']['$ref'])['_type'] == 'UMLLinePartView'
        (_, y0), (_, y1) = [tuple(map(float, q.split(':'))) for q in v['points'].split(';')]
        assert y0 == y1
        ys.append(y0)
    assert ys[0] + 40 <= ys[1] and ys[2] == 400


def test_restriccion_de_tiempo_junto_a_su_mensaje(vacio):
    ds = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='secuencia', nombre='Compra'))['diagrama']
    r = ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=ds, disposicion='secuencia', elementos=[
        {'simbolo': 'Lifeline', 'nombre': 'cliente'}, {'simbolo': 'Lifeline', 'nombre': 'tienda'}],
        relaciones=[{'simbolo': 'Message', 'desde': 'cliente', 'hasta': 'tienda', 'nombre': 'comprar()', 'clave': 'm1'}]))
    # en otra llamada, sobre la vista del mensaje (como la galeria): antes quedaba en (92, 57), sobre los encabezados
    r2 = ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=ds, elementos=[
        {'simbolo': 'Time Constraint', 'nombre': '{t < 2s}', 'sobre': r['vistas']['m1']}]))
    doc = M.Doc(vacio)
    msj = doc.get(r['vistas']['m1'])
    (x0, y0), (x1, _) = [tuple(map(float, p.split(':'))) for p in msj['points'].split(';')]
    tc = doc.get(r2['vistas']['{t < 2s}'])
    assert y0 < tc['top'] < y0 + 30, (tc['top'], y0)  # debajo del mensaje: su nombre va arriba
    assert min(x0, x1) < tc['left'] < max(x0, x1)


def test_secuencia_no_se_encima_con_lo_que_ya_hay(vacio):
    ds = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='secuencia', nombre='Compra en linea'))['diagrama']
    ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=ds, disposicion='secuencia', elementos=[
        {'simbolo': 'Lifeline', 'nombre': 'cliente'}, {'simbolo': 'Lifeline', 'nombre': 'tienda'}],
        relaciones=[{'simbolo': 'Message', 'desde': 'cliente', 'hasta': 'tienda', 'nombre': 'comprar()'}]))
    ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=ds, disposicion='secuencia', elementos=[
        {'simbolo': 'Lifeline', 'nombre': 'banco'}, {'simbolo': 'Lifeline', 'nombre': 'paqueteria'}],
        relaciones=[{'simbolo': 'Message', 'desde': 'banco', 'hasta': 'paqueteria', 'nombre': 'avisar()'},
                    {'simbolo': 'Message', 'desde': 'tienda', 'hasta': 'banco', 'nombre': 'cobrar()'}]))
    doc = M.Doc(vacio)
    dg = doc.diagram('Compra en linea')
    lls = sorted((v for v in dg['ownedViews'] if v['_type'] == 'UMLSeqLifelineView'), key=lambda v: v['left'])
    assert len(lls) == 4
    for a, b in zip(lls, lls[1:]):
        assert a['left'] + a['width'] < b['left'], 'lifelines encimadas'
    ys = sorted(float(v['points'].split(';')[0].split(':')[1]) for v in dg['ownedViews'] if v['_type'] == 'UMLSeqMessageView')
    assert len(ys) == 3 and all(b - a >= 40 for a, b in zip(ys, ys[1:])), ys
    # las de la primera llamada se alargan hasta el ultimo mensaje
    assert all(v['top'] + v['height'] > ys[-1] for v in lls)


def test_lifelines_separadas_segun_sus_mensajes(vacio):
    nombre = 'registrarPedidoConDireccionDeEnvio(cliente, carrito, direccion)'
    ds = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='secuencia', nombre='S'))['diagrama']
    r = ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=ds, disposicion='secuencia', elementos=[
        {'simbolo': 'Lifeline', 'nombre': 'a'}, {'simbolo': 'Lifeline', 'nombre': 'b'}],
        relaciones=[{'simbolo': 'Message', 'desde': 'a', 'hasta': 'b', 'nombre': nombre}]))
    doc = M.Doc(vacio)
    a, b = (doc.get(r['vistas'][k]) for k in ('a', 'b'))
    distancia = (b['left'] + b['width'] / 2) - (a['left'] + a['width'] / 2)
    assert distancia >= M.ancho13('1 : ' + nombre) + 30


# ---------------------------------------------------------------------------
# mdj_validar y las anotaciones
# ---------------------------------------------------------------------------

def test_validar_admite_notas_y_anotaciones_en_cualquier_diagrama(modelo):
    """Antes: 'UMLNoteView no esta en las vistas que admite UMLClassDiagram' (y en despliegue, secuencia...)."""
    assert ok(tool('mdj_validar', archivo=modelo, oose=False))['metamodelo'] == []  # trae una nota en cu_1
    for t in ('despliegue', 'secuencia', 'casos_de_uso', 'erd', 'estados', 'bpmn'):
        dg = ok(tool('mdj_diagrama_crear', archivo=modelo, tipo=t, nombre='N ' + t))['diagrama']
        ok(tool('mdj_nota', archivo=modelo, diagrama=dg, texto='revisar con el equipo', x=40, y=40, ancho=160))
    assert ok(tool('mdj_validar', archivo=modelo, oose=False))['metamodelo'] == []


def test_validar_el_modelo_real_sin_falsos_positivos(real):
    assert ok(tool('mdj_validar', archivo=real, oose=False))['metamodelo'] == []


# ---------------------------------------------------------------------------
# Acomodo: nombres de iconos libres de lineas
# ---------------------------------------------------------------------------

def _cruza(p, q, r):
    """El segmento p-q toca el rectangulo r (x0, y0, x1, y1)."""
    (x0, y0), (x1, y1) = p, q
    for k in range(41):
        t = k / 40
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
            return True
    return False


CREDITO = dict(elementos=[
    {'simbolo': 'Start Event', 'nombre': 'Solicitud de credito recibida'},
    {'simbolo': 'Gateway (Exclusive)', 'nombre': 'Monto mayor al limite?'},
    {'simbolo': 'Task', 'nombre': 'Aprobar'},
    {'simbolo': 'End Event', 'nombre': 'Credito rechazado al cliente'}],
    relaciones=[{'simbolo': 'Sequence Flow', 'desde': 'Solicitud de credito recibida', 'hasta': 'Monto mayor al limite?'},
                {'simbolo': 'Sequence Flow', 'desde': 'Monto mayor al limite?', 'hasta': 'Aprobar'},
                {'simbolo': 'Sequence Flow', 'desde': 'Monto mayor al limite?', 'hasta': 'Credito rechazado al cliente'}])


def test_las_lineas_no_pasan_sobre_los_nombres_largos_de_los_iconos(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='bpmn', nombre='Credito'))['diagrama']
    r = ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, **CREDITO))
    doc = M.Doc(vacio)
    d = doc.diagram('Credito')
    zonas = []
    for v in d['ownedViews']:
        labs = [x for x in v.get('subViews', []) if x.get('_type') == 'NodeLabelView' and x.get('visible') is not False
                and isinstance(x.get('top'), (int, float)) and x['top'] >= v['top'] + v['height'] - 2 and x.get('text')]
        for x in labs:
            cx, w = v['left'] + v['width'] / 2, M.ancho13(x['text'])
            zonas.append((x['text'], (cx - w / 2, x['top'], cx + w / 2, x['top'] + 13)))
    assert len(zonas) == 3
    for k in r['vistas']:
        v = doc.get(r['vistas'][k])
        if not isinstance(v.get('points'), str):
            continue
        pts = [tuple(map(float, p.split(':'))) for p in v['points'].split(';')]
        for texto, z in zonas:
            assert not any(_cruza(p, q, z) for p, q in zip(pts, pts[1:])), (texto, v['points'])


def test_la_persona_c4_se_mide_con_su_cabeza():
    """StarUML dibuja la cabeza (un tercio del ancho) arriba de la caja y la alarga: el acomodo usa ese alto."""
    _, p = U.plantilla_simbolo('C4Diagram', 'Person')
    w, h = U._tam_natural(p, 'Cliente frecuente de la tienda')
    assert h >= round(w / 3) + 75


# ---------------------------------------------------------------------------
# Con el StarUML verdadero
# ---------------------------------------------------------------------------

@pytest.fixture
def staruml(monkeypatch):
    cli = M.staruml_cli()
    if not cli:
        pytest.skip('StarUML no esta instalado (o define STARUML_MCP_STARUML_BIN)')
    monkeypatch.setenv('STARUML_MCP_EXPORT_TIMEOUT', os.environ.get('STARUML_MCP_EXPORT_TIMEOUT', '300'))
    return cli


def test_staruml_dibuja_lo_corregido(vacio, tmp_path, staruml):
    """Un mensaje creado sin vista y dibujado despues (antes quedaba dentro de la lifeline y el CLI tronaba, sin
    exportar los diagramas siguientes), columnas, atributos y literales creados sin campo, los nombres de restricciones,
    usos de interaccion, anotaciones y relaciones C4, y un diagrama de clases creado despues."""
    ds, a, b = _secuencia(vacio, 'Secuencia de cobro')
    m = ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLMessage', origen=a['elemento'], destino=b['elemento'],
                nombre='cobrar()'))
    ok(tool('mdj_vista_agregar', archivo=vacio, diagrama=ds, elemento=m['relacion'], desde=a['vista'], hasta=b['vista']))
    ok(tool('mdj_dibujar', archivo=vacio, diagrama=ds, simbolo='Duration Constraint', nombre='{0..5s}', x=300, y=300))
    ok(tool('mdj_dibujar', archivo=vacio, diagrama=ds, simbolo='Interaction Use', nombre='Autenticar', x=60, y=380))
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='erd', nombre='Datos'))
    e = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Datos', simbolo='Entity', nombre='Envio', x=40, y=40))
    ok(tool('mdj_elemento_crear', archivo=vacio, tipo='ERDColumn', nombre='id_envio', dentro_de=e['elemento']))
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='clases', nombre='Clases'))
    c = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Clases', simbolo='Class', nombre='Pedido', x=40, y=40))
    ok(tool('mdj_elemento_crear', archivo=vacio, tipo='UMLAttribute', nombre='folio', dentro_de=c['elemento']))
    en = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Clases', simbolo='Enumeration', nombre='Estado', x=300, y=40))
    ok(tool('mdj_elemento_crear', archivo=vacio, tipo='UMLEnumerationLiteral', nombre='NUEVO', dentro_de=en['elemento']))
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='bpmn', nombre='Credito'))
    ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama='Credito', **CREDITO))
    ok(tool('mdj_dibujar', archivo=vacio, diagrama='Credito', simbolo='Text Annotation', nombre='Maximo 2 dias', x=600, y=60))
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='c4', nombre='Contexto'))
    p1 = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Contexto', simbolo='Person', nombre='Cliente', x=40, y=40))
    p2 = ok(tool('mdj_dibujar', archivo=vacio, diagrama='Contexto', simbolo='Software System', nombre='Tienda', x=400, y=40))
    ok(tool('mdj_dibujar', archivo=vacio, diagrama='Contexto', simbolo='Relationship', nombre='compra en',
            desde=p1['vista'], hasta=p2['vista']))
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='despliegue', nombre='Zeta despues'))
    ok(tool('mdj_nota', archivo=vacio, diagrama='Zeta despues', texto='servidor de pruebas', x=40, y=40, ancho=160))
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['metamodelo'] == []
    r = ok(tool('staruml_exportar', archivo=vacio, carpeta=str(tmp_path / 'svg')))
    svgs = {os.path.splitext(os.path.basename(x))[0]: x for x in r['archivos']}
    for n in ('Secuencia de cobro', 'Datos', 'Clases', 'Credito', 'Contexto', 'Zeta despues'):
        assert n in svgs and os.path.getsize(svgs[n]) > 300, (n, r)
    texto = lambda n: open(svgs[n], encoding='utf-8').read()
    for n, palabras in (('Secuencia de cobro', ('cobrar()', '{0..5s}', 'Autenticar')), ('Datos', ('id_envio',)),
                        ('Clases', ('folio', 'NUEVO')), ('Credito', ('Maximo', 'Monto mayor al limite?')),
                        ('Contexto', ('compra',)), ('Zeta despues', ('servidor de pruebas',))):
        for w in palabras:
            assert w in texto(n), f'StarUML no dibujo "{w}" en {n}'
    # el mensaje llega a la lifeline de destino con su activacion
    assert '1 : cobrar()' in texto('Secuencia de cobro')
    rev = ok(tool('svg_revisar', archivo=vacio, svg=svgs['Credito'], diagrama='Credito'))
    assert not [x for x in rev['problemas'] if x.startswith('LINEA SOBRE TEXTO')], rev['problemas']
