# Diagramas de estados y de actividades: lectura (mdj_comportamiento) y reglas (mdj_validar).
import pytest

from apoyo import M, ids_integros, modelo_comportamiento, ok, ref, tool


@pytest.fixture
def comp(tmp_path):
    return modelo_comportamiento(str(tmp_path / 'comportamiento.mdj'))


def reglas(path):
    return ok(tool('mdj_validar', archivo=path))['comportamiento']


def nuevo(doc, tipo, padre, lista, **kw):
    o = {'_type': tipo, '_id': doc.new_id(), '_parent': ref(padre['_id']), **kw}
    padre.setdefault(lista, []).append(o)
    return o


def test_lee_la_maquina_de_estados(comp):
    r = ok(tool('mdj_comportamiento', archivo=comp, diagrama='estados_pedido'))
    assert r['tipo'] == 'maquina_de_estados' and r['nombre'] == 'Ciclo de pedido'
    assert [e['nombre'] for e in r['estados']] == ['(initial)', 'Creado', '(choice)', 'Pagado', 'En preparación', '(initial)',
                                                   'Empacando', 'Etiquetando', 'Enviado', '(final)']
    por_nombre = {e['nombre']: e for e in r['estados']}
    assert por_nombre['Empacando']['dentro_de'] == 'En preparación' and por_nombre['Creado']['dentro_de'] is None
    assert por_nombre['Pagado']['hacer'] == ['notificar al almacén']
    assert por_nombre['Empacando']['en_diagrama'] and not por_nombre['Enviado']['en_diagrama']
    t = {(x['de'], x['a']): x for x in r['transiciones']}
    assert t[('Creado', '(choice)')]['disparadores'] == ['pagar']
    assert t[('(choice)', 'Pagado')]['guarda'] == 'pago válido'
    assert len(r['transiciones']) == 9


def test_lee_la_actividad(comp):
    r = ok(tool('mdj_comportamiento', archivo=comp, diagrama='actividad_pedido'))
    assert r['tipo'] == 'actividad' and r['particiones'] == ['Almacén']
    tipos = {n['nombre']: n['tipo'] for n in r['nodos']}
    assert tipos['Recibir pedido'] == 'accion' and tipos['(decision)'] == 'decision' and tipos['(bifurcacion)'] == 'bifurcacion'
    assert next(n for n in r['nodos'] if n['nombre'] == 'Empacar')['particion'] == 'Almacén'
    guardas = {f['a']: f['guarda'] for f in r['flujos'] if f['de'] == '(decision)'}
    assert guardas == {'Rechazar pedido': 'sin existencias', 'Cobrar': 'con existencias'}


def test_diagrama_que_no_es_de_estados_ni_actividades(comp):
    assert 'no pertenece' in tool('mdj_comportamiento', archivo=comp, diagrama='cu_1')['error']


def test_modelo_correcto_sin_problemas_ni_avisos(comp):
    assert reglas(comp) == {'problemas': [], 'avisos': []}


def test_reglas_de_estados(comp):
    doc = M.Doc(comp)
    reg = next(o for o in doc.ids.values() if o and o['_type'] == 'UMLRegion' and doc.ids[doc.parent[o['_id']]]['_type'] == 'UMLStateMachine')
    v = {(o.get('name') or o.get('kind') or o['_type']): o for o in reg['vertices']}
    huerfano = nuevo(doc, 'UMLState', reg, 'vertices', name='Huérfano')
    nuevo(doc, 'UMLPseudostate', reg, 'vertices', kind='initial')  # segundo inicial
    nuevo(doc, 'UMLTransition', reg, 'transitions', source=ref(v['UMLFinalState']['_id']), target=ref(v['Creado']['_id']))
    for t in reg['transitions']:  # la decision se queda sin guardas
        t.pop('guard', None)
    t = nuevo(doc, 'UMLTransition', reg, 'transitions', source=ref(v['Creado']['_id']), target=ref(v['Pagado']['_id']))
    t['triggers'] = [{'_type': 'UMLEvent', '_id': doc.new_id(), '_parent': ref(t['_id']), 'name': 'pagar'}]
    doc.reindex()
    doc.save(backup=False)
    r = reglas(comp)
    texto = '\n'.join(r['problemas'] + r['avisos'])
    assert any('2 estados iniciales' in p for p in r['problemas'])
    assert any('(final) es final y tiene transiciones de salida' in p for p in r['problemas'])
    assert any('estado inicial debe tener exactamente una' in p for p in r['problemas'])  # el nuevo no tiene salida
    assert 'no se puede llegar a Huérfano' in texto and 'el estado Huérfano no tiene transiciones de salida' in texto
    assert 'varias salidas sin guarda' in texto
    assert "Creado tiene 2 transiciones con el mismo disparador ['pagar']" in texto
    assert 'Etiquetando' not in texto  # dentro del compuesto: sale por la transicion del compuesto
    assert huerfano['_id'] and ids_integros(comp)


def test_reglas_de_actividad(comp):
    doc = M.Doc(comp)
    act = next(o for o in doc.ids.values() if o and o['_type'] == 'UMLActivity')
    n = {(o.get('name') or o['_type']): o for o in act['nodes']}
    nuevo(doc, 'UMLAction', act, 'nodes', name='Auditar')  # inalcanzable y sin salida
    nuevo(doc, 'UMLAction', act, 'nodes')  # sin nombre
    nuevo(doc, 'UMLControlFlow', act, 'edges', source=ref(n['Recibir pedido']['_id']), target=ref(n['Facturar']['_id']))
    nuevo(doc, 'UMLControlFlow', act, 'edges', source=ref(n['UMLActivityFinalNode']['_id']), target=ref(n['Cobrar']['_id']))
    nuevo(doc, 'UMLControlFlow', act, 'edges', source=ref(n['UMLDecisionNode']['_id']), target=ref(n['Empacar']['_id']),
          guard='con existencias')
    doc.reindex()
    doc.save(backup=False)
    r = reglas(comp)
    texto = '\n'.join(r['avisos'])
    assert r['problemas'] == ['Actividad "Procesar pedido": el nodo final (final) tiene flujos de salida']
    assert 'Recibir pedido tiene 2 flujos de salida (bifurcacion implicita)' in texto
    assert 'Facturar recibe 2 flujos (union implicita' in texto and 'Cobrar recibe 2 flujos' in texto
    assert 'no se puede llegar a Auditar' in texto and 'Auditar no lleva a ningun otro nodo' in texto
    assert 'hay una accion sin nombre' in texto and 'la decision (decision) repite guardas' in texto


def test_actividad_anidada_en_un_estado_se_valida_aparte(comp):
    doc = M.Doc(comp)
    pagado = doc.find('Pagado')
    sub = nuevo(doc, 'UMLActivity', pagado, 'doActivities', name='Surtir')
    nuevo(doc, 'UMLAction', sub, 'nodes', name='Tomar del estante')
    doc.reindex()
    doc.save(backup=False)
    r = reglas(comp)
    assert r['avisos'] == ['Actividad "Surtir": no tiene nodo inicial',
                           'Actividad "Surtir": Tomar del estante no lleva a ningun otro nodo ni a un nodo final']
    lectura = ok(tool('mdj_comportamiento', archivo=comp, diagrama='actividad_pedido'))
    assert 'Tomar del estante' not in [x['nombre'] for x in lectura['nodos']]
    estados = ok(tool('mdj_comportamiento', archivo=comp, diagrama='estados_pedido'))['estados']
    assert next(e for e in estados if e['nombre'] == 'Pagado')['hacer'] == ['notificar al almacén', 'Surtir']


def test_cajas_encimadas_en_actividades_pero_no_subestados(comp):
    doc = M.Doc(comp)
    dg = doc.diagram('actividad_pedido')
    dg['ownedViews'][1]['top'] = 100  # Cobrar encima de Recibir pedido
    doc.save(backup=False)
    assert reglas(comp)['avisos'] == ['actividad_pedido: cajas encimadas Recibir pedido / Cobrar']
