# Todos los diagramas y simbolos de StarUML: tablas (metamodelo y plantillas), dibujo de cada simbolo de cada paleta,
# elementos y relaciones guiados por el metamodelo, generacion con acomodo y anidamiento, y validacion.
import json
import os

import pytest

from apoyo import M, ok, tool, poblar_paleta, ids_integros
import staruml_uml as U

TIPOS_DIAGRAMA = sorted(U.plantillas()['diagramas'])


# ---------------------------------------------------------------------------
# Tablas
# ---------------------------------------------------------------------------

def test_cada_simbolo_de_cada_paleta_tiene_plantilla_o_motivo():
    """La paleta de StarUML (metamodelo) contra las plantillas: nada queda fuera sin explicacion."""
    paletas = U.metamodelo()['paletas']
    pl = U.plantillas()
    no = {(o['diagrama'], o['simbolo']) for o in pl['no_dibujables']}
    faltan = [(d, f'{it["label"]}|{it["id"]}') for d, items in paletas.items() for it in items
              if f'{it["label"]}|{it["id"]}' not in pl['plantillas'].get(d, {}) and (d, f'{it["label"]}|{it["id"]}') not in no]
    assert not faltan
    assert set(paletas) == set(pl['diagramas']), 'cada diagrama de la paleta se puede crear'
    assert len(pl['no_dibujables']) <= 2


def test_las_plantillas_solo_usan_marcadores_conocidos():
    conocidos = ('@diagrama', '@dueno', '@cola', '@cabeza', '@ext:')
    for d, ps in U.plantillas()['plantillas'].items():
        for c, p in ps.items():
            ids = U._ids_plantilla([e['objeto'] for e in p['objetos']])
            for m in U._marcas([e['objeto'] for e in p['objetos']]) | {e['padre'] for e in p['objetos']}:
                assert m in ids or m.startswith(conocidos), (d, c, m)


def test_catalogo():
    r = ok(tool('mdj_catalogo'))
    tipos = {d['tipo']: d for d in r['diagramas']}
    assert len(tipos) == 28
    assert tipos['UMLDeploymentDiagram']['alias'] == 'despliegue' and tipos['ERDDiagram']['origen'] == 'erd'
    r = ok(tool('mdj_catalogo', diagrama='despliegue'))
    simbolos = {s['simbolo']: s for s in r['simbolos']}
    assert {'Node', 'Artifact', 'Deployment', 'Communication Path', 'Node Instance'} <= set(simbolos)
    assert simbolos['Deployment']['forma'] == 'line'
    assert 'error' in tool('mdj_catalogo', diagrama='no_existe')


# ---------------------------------------------------------------------------
# Todos los simbolos de cada tipo de diagrama
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('tipo', TIPOS_DIAGRAMA)
def test_dibuja_toda_la_paleta(vacio, tipo):
    doc = M.Doc(vacio)
    dg, _ = U.crear_diagrama(doc, tipo, 'D_' + tipo)
    hechos, fallas = poblar_paleta(doc, dg)
    assert not fallas, fallas
    assert len(hechos) == len(U.plantillas()['plantillas'][tipo])
    doc.save(backup=False)  # save rechaza ids duplicados, referencias colgantes y _parent incoherente
    doc = M.Doc(vacio)
    assert ids_integros(vacio)
    assert U.validar_metamodelo(doc) == []
    assert doc.diagram('D_' + tipo)['_type'] == tipo


def test_diagramas_con_dueno_propio(vacio):
    """El bloque interno de SysML solo vive dentro de un bloque: si se pide en el modelo, se crea el bloque."""
    r = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='sysml_bloque_interno', nombre='Motor'))
    doc = M.Doc(vacio)
    dg = doc.get(r['diagrama'])
    assert doc.ids[doc.parent[dg['_id']]]['_type'] == 'SysMLBlock'
    r = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='estados', nombre='Pedido'))
    doc = M.Doc(vacio)
    sm = doc.ids[doc.parent[r['diagrama']]]
    assert sm['_type'] == 'UMLStateMachine' and sm['name'] == 'Pedido' and sm['regions']


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------

def test_dibujar_despliegue_con_herramientas(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='despliegue', nombre='Infra'))['diagrama']
    srv = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Node', nombre='Servidor', x=300, y=100))
    app = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Artifact', nombre='app.jar', x=40, y=100))
    assert srv['elemento_tipo'] == 'UMLNode' and app['elemento_tipo'] == 'UMLArtifact'
    r = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Deployment', desde=app['vista'], hasta='Servidor'))
    doc = M.Doc(vacio)
    dep = doc.get(r['elemento'])
    assert dep['_type'] == 'UMLDeployment'
    assert dep['source']['$ref'] == app['elemento'] and dep['target']['$ref'] == srv['elemento']
    v = doc.get(r['vista'])
    assert v['tail']['$ref'] == app['vista'] and v['head']['$ref'] == srv['vista']
    n = doc.get(srv['elemento'])
    assert n['name'] == 'Servidor' and n['_parent']['$ref'] == doc.diagram('Infra')['_parent']['$ref']
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['metamodelo'] == []


def test_dibujar_errores(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='componentes', nombre='C'))['diagrama']
    r = tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Clase')
    assert 'error' in r and 'Component' in r['error']  # dice que si hay en la paleta
    r = tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Dependency')
    assert 'error' in r and 'desde' in r['error']
    r = tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Port')
    assert 'error' in r and 'sobre' in r['error']
    c = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Component', nombre='Pagos'))
    p = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Port', nombre='api', sobre=c['vista']))
    doc = M.Doc(vacio)
    assert doc.get(p['elemento'])['_parent']['$ref'] == c['elemento']  # el puerto es del componente
    assert doc.get(p['vista'])['containerView']['$ref'] == c['vista']


def test_mensajes_sin_origen_o_sin_destino(vacio):
    doc = M.Doc(vacio)
    dg = doc.diagram('cu_1_FB')
    ll = U.dibujar(doc, dg['_id'], 'Lifeline', 'Caja', x=200, y=60)
    U.dibujar(doc, dg['_id'], 'Found Message', hasta=ll['vista'])
    U.dibujar(doc, dg['_id'], 'Lost Message', desde=ll['vista'])
    with pytest.raises(M.MdjError, match='hasta'):
        U.dibujar(doc, dg['_id'], 'Found Message')
    doc.save(backup=False)
    assert ids_integros(vacio)


def test_elemento_y_relacion_sin_vista(vacio):
    nodo = ok(tool('mdj_elemento_crear', archivo=vacio, tipo='UMLNode', nombre='Servidor'))
    art = ok(tool('mdj_elemento_crear', archivo=vacio, tipo='UMLArtifact', nombre='app.war', dentro_de=nodo['elemento'],
                  propiedades={'fileName': 'app.war'}))
    doc = M.Doc(vacio)
    assert doc.get(art['elemento'])['_parent']['$ref'] == nodo['elemento']
    assert doc.get(art['elemento'])['fileName'] == 'app.war'
    otro = ok(tool('mdj_elemento_crear', archivo=vacio, tipo='UMLNode', nombre='BD'))
    r = ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLCommunicationPath', origen='Servidor', destino='BD'))
    doc = M.Doc(vacio)
    cp = doc.get(r['relacion'])
    assert cp['end1']['_type'] == 'UMLAssociationEnd' and cp['end2']['reference']['$ref'] == otro['elemento']
    r = ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLDeployment', origen='app.war', destino='BD'))
    assert M.Doc(vacio).get(r['relacion'])['source']['$ref'] == art['elemento']
    # errores del metamodelo
    assert 'error' in tool('mdj_elemento_crear', archivo=vacio, tipo='UMLClassifier')  # abstracto
    assert 'error' in tool('mdj_elemento_crear', archivo=vacio, tipo='UMLNode', propiedades={'noExiste': 1})
    assert 'error' in tool('mdj_elemento_crear', archivo=vacio, tipo='UMLNode', propiedades={'isAbstract': 'si'})
    # ownedElements admite cualquier Element (asi lo define StarUML), pero un campo que el nodo no tiene no
    assert 'error' in tool('mdj_elemento_crear', archivo=vacio, tipo='UMLRegion', dentro_de='Servidor', campo='regions')
    assert 'error' in tool('mdj_elemento_crear', archivo=vacio, tipo='UMLNodeView')  # una vista no es un elemento
    assert 'error' in tool('mdj_relacion_crear', archivo=vacio, tipo='UMLNode', origen='Servidor', destino='BD')
    assert ids_integros(vacio)


def test_vista_de_un_elemento_existente(vacio):
    ok(tool('mdj_elemento_crear', archivo=vacio, tipo='UMLNode', nombre='Servidor'))
    ok(tool('mdj_elemento_crear', archivo=vacio, tipo='UMLNode', nombre='BD'))
    ok(tool('mdj_relacion_crear', archivo=vacio, tipo='UMLCommunicationPath', origen='Servidor', destino='BD'))
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='despliegue', nombre='Infra'))['diagrama']
    a = ok(tool('mdj_vista_agregar', archivo=vacio, diagrama=dg, elemento='Servidor', x=40, y=40))
    b = ok(tool('mdj_vista_agregar', archivo=vacio, diagrama=dg, elemento='BD', x=400, y=40))
    doc = M.Doc(vacio)
    cp = next(o for o in doc.ids.values() if o and o.get('_type') == 'UMLCommunicationPath')
    ok(tool('mdj_vista_agregar', archivo=vacio, diagrama=dg, elemento=cp['_id'], desde=a['vista'], hasta=b['vista']))
    doc = M.Doc(vacio)
    vistas = [v['_type'] for v in doc.diagram('Infra')['ownedViews']]
    assert vistas.count('UMLNodeView') == 2 and 'UMLCommunicationPathView' in vistas
    assert 'error' in tool('mdj_vista_agregar', archivo=vacio, diagrama=dg, elemento='Servidor', x=0, y=0)  # ya esta
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['metamodelo'] == []


# ---------------------------------------------------------------------------
# Generar diagramas completos
# ---------------------------------------------------------------------------

def _cajas_encimadas(doc, dg):
    cajas = [v for v in dg['ownedViews'] if U._es_caja(v) and not v.get('containerView')]
    res = []
    for i, a in enumerate(cajas):
        for b in cajas[i + 1:]:
            if a['left'] < b['left'] + b['width'] and b['left'] < a['left'] + a['width'] and \
                    a['top'] < b['top'] + b['height'] and b['top'] < a['top'] + a['height']:
                res.append((a['_id'], b['_id']))
    return res


def test_generar_despliegue_anidado(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='despliegue', nombre='Arquitectura'))['diagrama']
    r = ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=[
        {'simbolo': 'Node', 'nombre': 'Servidor web'},
        {'simbolo': 'Node', 'nombre': 'Tomcat', 'dentro': 'Servidor web'},
        {'simbolo': 'Artifact', 'nombre': 'tienda.war', 'dentro': 'Tomcat'},
        {'simbolo': 'Node', 'nombre': 'Servidor BD'},
        {'simbolo': 'Artifact', 'nombre': 'esquema.sql', 'dentro': 'Servidor BD'},
        {'simbolo': 'Node', 'nombre': 'Navegador'}],
        relaciones=[{'simbolo': 'Communication Path', 'desde': 'Navegador', 'hasta': 'Servidor web', 'nombre': 'HTTPS'},
                    {'simbolo': 'Communication Path', 'desde': 'Servidor web', 'hasta': 'Servidor BD', 'nombre': 'JDBC'}]))
    assert r['cajas'] == 6 and r['lineas'] == 2 and r['lineas_que_cruzan_cajas'] == []
    doc = M.Doc(vacio)
    padre = lambda n: doc.name_of(doc.parent[doc.find(n)['_id']])
    assert padre('Tomcat') == 'Servidor web' and padre('tienda.war') == 'Tomcat' and padre('esquema.sql') == 'Servidor BD'
    d = doc.diagram('Arquitectura')
    v = {doc.name_of(x['model']['$ref']): x for x in d['ownedViews'] if isinstance(x.get('model'), dict)}
    srv, tom = v['Servidor web'], v['Tomcat']
    assert tom['containerView']['$ref'] == srv['_id']
    assert srv['left'] < tom['left'] and tom['left'] + tom['width'] <= srv['left'] + srv['width']
    assert srv['top'] < tom['top'] and tom['top'] + tom['height'] <= srv['top'] + srv['height']
    assert _cajas_encimadas(doc, d) == []
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['metamodelo'] == []


def test_generar_estados_con_estado_compuesto(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='estados', nombre='Pedido'))['diagrama']
    ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=[
        {'simbolo': 'Initial State', 'clave': 'inicio'},
        {'simbolo': 'Simple State', 'nombre': 'Nuevo'},
        {'simbolo': 'Composite State', 'nombre': 'En proceso'},
        {'simbolo': 'Simple State', 'nombre': 'Empacando', 'dentro': 'En proceso'},
        {'simbolo': 'Simple State', 'nombre': 'Enviado', 'dentro': 'En proceso'},
        {'simbolo': 'Final State', 'clave': 'fin'}],
        relaciones=[{'simbolo': 'Transition', 'desde': 'inicio', 'hasta': 'Nuevo'},
                    {'simbolo': 'Transition', 'desde': 'Nuevo', 'hasta': 'En proceso', 'nombre': 'pagar'},
                    {'simbolo': 'Transition', 'desde': 'Empacando', 'hasta': 'Enviado'},
                    {'simbolo': 'Transition', 'desde': 'En proceso', 'hasta': 'fin'}]))
    doc = M.Doc(vacio)
    comp = doc.find('En proceso')
    assert {doc.name_of(x['_id']) for x in comp['regions'][0]['vertices']} == {'Empacando', 'Enviado'}
    r = M.comportamiento(doc, 'Pedido')
    estados = {e['nombre']: e for e in r['estados']}
    assert estados['Empacando']['dentro_de'] == 'En proceso'
    assert len(r['transiciones']) == 4
    assert _cajas_encimadas(doc, doc.diagram('Pedido')) == []
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['metamodelo'] == []


def test_generar_errores(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='despliegue', nombre='D'))['diagrama']
    r = tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=[{'simbolo': 'Node', 'nombre': 'A', 'dentro': 'X'}])
    assert 'error' in r and 'X' in r['error']
    r = tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg,
             elementos=[{'simbolo': 'Node', 'nombre': 'A'}, {'simbolo': 'Node', 'nombre': 'A'}])
    assert 'error' in r and 'clave' in r['error']
    r = tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=[{'simbolo': 'Node', 'nombre': 'A'}],
             relaciones=[{'simbolo': 'Deployment', 'desde': 'A', 'hasta': 'B'}])
    assert 'error' in r


# ---------------------------------------------------------------------------
# Lectura generica
# ---------------------------------------------------------------------------

def test_geometria_y_busqueda_genericas(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='erd', nombre='Datos'))['diagrama']
    a = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Entity', nombre='Cliente', x=40, y=40))
    b = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Entity', nombre='Pedido', x=400, y=40))
    rel = next(s['simbolo'] for s in ok(tool('mdj_catalogo', diagrama='erd'))['simbolos'] if s['forma'] == 'line')
    ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo=rel, desde=a['vista'], hasta=b['vista']))
    g = ok(tool('mdj_geometria', archivo=vacio, diagrama='Datos'))
    assert {c['elemento'] for c in g['cajas']} >= {'Cliente', 'Pedido'}
    assert len(g['lineas']) == 1 and {g['lineas'][0]['de'], g['lineas'][0]['a']} == {'Cliente', 'Pedido'}
    doc = M.Doc(vacio)
    assert doc.find('ERDEntity:Cliente')['_id'] == a['elemento']
    assert any(d['tipo'] == 'ERDDiagram' for d in ok(tool('mdj_resumen', archivo=vacio))['diagramas'])
