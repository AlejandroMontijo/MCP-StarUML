# La galeria (tests/galeria.py): un diagrama de cada tipo de StarUML con todos los simbolos de su paleta. Aqui se
# comprueba sin StarUML que cubre todo, que se construye con las herramientas MCP sin errores de integridad ni de
# metamodelo, y la deteccion de lineas que atraviesan un contenedor. tests/test_staruml_real.py la exporta con el
# StarUML verdadero y revisa cada SVG.
import pytest

import galeria as G
import staruml_uml as U
from apoyo import M, ok, tool, ids_integros


def herramienta(_h, /, **a):
    return ok(tool(_h, **a))


def test_la_galeria_cubre_todos_los_tipos_y_todos_los_simbolos():
    tipos = [U.tipo_diagrama(g['tipo']) for g in G.GALERIA]
    assert sorted(tipos) == sorted(U.plantillas()['diagramas']), 'un diagrama por cada tipo'
    for g, t in zip(G.GALERIA, tipos):
        paleta = {c.split('|')[0] for c in U.plantillas()['plantillas'][t]}
        assert G.simbolos_usados(g) == paleta, (g['nombre'], paleta ^ G.simbolos_usados(g))


@pytest.fixture(scope='module')
def galeria(tmp_path_factory):
    import apoyo
    mp = pytest.MonkeyPatch()
    carpeta = tmp_path_factory.mktemp('galeria')
    mp.setattr(M, 'BACKUP_DIR', str(carpeta / 'respaldos'))
    mp.setattr(M, 'staruml_gui_abierto', lambda: False)
    try:
        archivo = apoyo.guardar_json(apoyo.proyecto_vacio('Galeria'), str(carpeta / 'galeria.mdj'))
        res = G.construir(herramienta, archivo)
    finally:
        mp.undo()
    return archivo, res


def test_la_galeria_se_construye_integra(galeria):
    archivo, res = galeria
    assert len(res) == 28
    assert ids_integros(archivo)
    v = ok(tool('mdj_validar', archivo=archivo, oose=False))
    assert v['metamodelo'] == []
    assert v['lineas_que_atraviesan_contenedores'] == []
    for nombre, r in res.items():
        assert not r.get('avisos'), (nombre, r['avisos'])
    doc = M.Doc(archivo)
    nombres = {d.get('name') for d in doc.diagrams()}
    assert {g['nombre'] for g in G.GALERIA} <= nombres


def test_carriles_contiguos_y_del_mismo_largo(galeria):
    archivo, _ = galeria
    doc = M.Doc(archivo)
    dg = doc.diagram('G09 Actividades')
    lanes = sorted((v for v in dg['ownedViews'] if v['_type'] == 'UMLSwimlaneView' and v.get('isVertical', True)),
                   key=lambda v: v['left'])
    assert len(lanes) == 2
    assert lanes[0]['left'] + lanes[0]['width'] == lanes[1]['left'] and lanes[0]['height'] == lanes[1]['height']
    # lo de cada carril queda dentro de el, tambien en el modelo
    accion = next(o for o in doc.ids.values() if o and o.get('name') == 'Elegir productos')
    assert doc.ids[doc.parent[accion['_id']]].get('name') == 'Cliente'


def test_detecta_la_linea_que_sale_de_un_contenedor(vacio):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='componentes', nombre='C'))['diagrama']
    r = ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=[
        {'simbolo': 'Component', 'nombre': 'API'}, {'simbolo': 'Component', 'nombre': 'Servicio', 'dentro': 'API'},
        {'simbolo': 'Component', 'nombre': 'Repo', 'dentro': 'API'}, {'simbolo': 'Port', 'nombre': 'p', 'sobre': 'API'},
        {'simbolo': 'Interface', 'nombre': 'IPagos'}, {'simbolo': 'Component', 'nombre': 'Pagos'}],
        relaciones=[{'simbolo': 'Dependency', 'desde': 'Servicio', 'hasta': 'IPagos'},
                    {'simbolo': 'Interface Realization', 'desde': 'Pagos', 'hasta': 'IPagos'},
                    {'simbolo': 'Dependency', 'desde': 'Servicio', 'hasta': 'Repo'},
                    {'simbolo': 'Connector', 'desde': 'p', 'hasta': 'Servicio'},
                    {'simbolo': 'Dependency', 'desde': 'p', 'hasta': 'IPagos'}]))
    # solo la dependencia del subcomponente hacia afuera; ni la interna ni las del puerto (esta en el borde)
    assert len(r['avisos']) == 1 and 'Servicio' in r['avisos'][0] and 'atraviesa API' in r['avisos'][0]
    v = ok(tool('mdj_validar', archivo=vacio, oose=False))['lineas_que_atraviesan_contenedores']
    assert len(v) == 1 and 'Servicio' in v[0] and 'IPagos' in v[0]


def test_cruzar_un_contenedor_que_no_encapsula_es_normal(vacio):
    """Actor hacia un caso de uso dentro del sujeto, o flujo entre carriles: en UML cruzan el borde."""
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='casos_de_uso', nombre='CU'))['diagrama']
    r = ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=[
        {'simbolo': 'Use Case Subject', 'nombre': 'Sistema'}, {'simbolo': 'Actor', 'nombre': 'Cliente'},
        {'simbolo': 'Use Case', 'nombre': 'Comprar', 'dentro': 'Sistema'}],
        relaciones=[{'simbolo': 'Association', 'desde': 'Cliente', 'hasta': 'Comprar'}]))
    assert not r.get('avisos')
    assert ok(tool('mdj_validar', archivo=vacio, oose=False))['lineas_que_atraviesan_contenedores'] == []
