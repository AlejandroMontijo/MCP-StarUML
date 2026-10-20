# La galeria (tests/galeria.py): un diagrama de cada tipo de StarUML con todos los simbolos de su paleta. Aqui se
# comprueba sin StarUML que cubre todo, que se construye con las herramientas MCP sin errores de integridad ni de
# metamodelo, la deteccion de lineas que atraviesan un contenedor y, con los puntos que dibuja StarUML, que las lineas
# no pasen sobre cajas ni terminen en el aire junto a un icono. tests/test_staruml_real.py la exporta con el StarUML
# verdadero y revisa cada SVG.
import pytest

import galeria as G
from staruml_mcp import programa as P
from staruml_mcp import render as R
from staruml_mcp import uml as U
from apoyo import M, en_el_aire, ok, tool, ids_integros


def herramienta(_h, /, **a):
    return ok(tool(_h, **a))


def test_la_galeria_cubre_todos_los_tipos_y_todos_los_simbolos():
    tipos = [U.tipo_diagrama(g['tipo']) for g in G.GALERIA]
    assert sorted(tipos) == sorted(U.plantillas()['diagramas']), 'un diagrama por cada tipo'
    for g, t in zip(G.GALERIA, tipos):
        paleta = {c.split('|')[0] for c in U.plantillas()['plantillas'][t]}
        usados = G.simbolos_usados(g) | (G.SIMBOLOS_ROBUSTEZ if t == 'UMLClassDiagram' else set())
        assert usados == paleta, (g['nombre'], paleta ^ usados)


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
    assert len(res) == 29  # 28 tipos + el de robustez
    assert ids_integros(archivo)
    v = ok(tool('mdj_validar', archivo=archivo, oose=False))
    assert v['metamodelo'] == []
    assert v['lineas_que_atraviesan_contenedores'] == []
    for nombre, r in res.items():
        assert not r.get('avisos'), (nombre, r['avisos'])
    # las reglas OOSE revisan todo el archivo; del diagrama de robustez no debe salir nada (los demas no son OOSE)
    oose = res['G29 Robustez']['oose']
    assert not [x for x in oose['problemas'] + oose['avisos'] if 'G29' in x]
    assert not [x for x in oose['avisos'] if 'cajas encimadas' in x], oose['avisos']
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


def lineas_sobre_cajas(doc, dg):
    """Lineas que pasan sobre una caja que no es de sus extremos (ni los contiene), con los puntos que dibuja StarUML y
    el criterio de svg_revisar: sin las zonas (marcos, carriles...) y con la caja encogida 4 px, porque la linea llega
    a su borde."""
    cajas = [(doc.name_of(v['model']['$ref']), U._rect(v)) for v in dg['ownedViews'] if U._es_caja(v)
             and isinstance(v.get('model'), dict) and not any(z in v['_type'] for z in R._ZONAS)]
    cerca = lambda p, r: r[0] - 3 <= p[0] <= r[2] + 3 and r[1] - 3 <= p[1] <= r[3] + 3
    res = []
    for v in dg['ownedViews']:
        if not isinstance(v.get('points'), str):
            continue
        pts = U._puntos_staruml(doc, v)
        for nombre, r in cajas:
            if not cerca(pts[0], r) and not cerca(pts[-1], r) and any(
                    P._cruza(p, q, (r[0] + 4, r[1] + 4, r[2] - 4, r[3] - 4), 0) for p, q in zip(pts, pts[1:])):
                res.append(f'{v["_type"]} sobre {nombre}')
    return res


def test_componentes_sin_lineas_sobre_cajas(galeria):
    """G05: config, perfil y api-v2.jar en columna y un enlace de config a api-v2.jar que salta la fila de perfil. Ese
    enlace va por su hueco, a un lado de perfil (no recto encima de el), y ninguna linea pasa sobre otra caja: es lo
    que svg_revisar revisa en el SVG de StarUML."""
    archivo, res = galeria
    doc = M.Doc(archivo)
    dg = doc.diagram('G05 Componentes')
    assert res['G05 Componentes']['lineas_que_cruzan_cajas'] == []
    assert lineas_sobre_cajas(doc, dg) == []
    vista = {doc.name_of(v['model']['$ref']): v['_id'] for v in dg['ownedViews']
             if U._es_caja(v) and isinstance(v.get('model'), dict)}
    enlace = next(v for v in dg['ownedViews'] if v['_type'] == 'UMLLinkView' and {v['tail']['$ref'], v['head']['$ref']}
                  == {vista['config: Configuracion'], vista['api-v2.jar']})
    assert len(U._puntos_staruml(doc, enlace)) > 2


def test_ninguna_linea_queda_en_el_aire_junto_a_un_icono(galeria):
    """La caja de un icono (actor, artefacto...) es tan ancha como su nombre: ninguna linea le llega por un costado ni
    por arriba fuera de su dibujo (en G05, los dos enlaces que llegan a api-v2.jar; en G08, la generalizacion que sale
    de Cliente frecuente)."""
    archivo, _ = galeria
    doc = M.Doc(archivo)
    assert [x for g in G.GALERIA for x in en_el_aire(doc, doc.diagram(g['nombre']))] == []


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
