# Correcciones del servidor y de staruml_mdj: borrar a cualquier profundidad, notas, extremos y dueno de asociaciones,
# alto al mover una vista, deteccion de StarUML abierto, anotaciones de las herramientas, lineas que no son UTF-8,
# etiqueta de los auto-mensajes, respaldos en una carpeta indicada y aviso de programa grande.
import json
import math
import os
import shutil
import subprocess
import sys
import time

import pytest

from apoyo import LIFELINES, ClienteMCP, M, S, fuentes, ids_integros, ok, tool


def _bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def _todas(dg):
    res, pila = [], list(dg.get('ownedViews', []))
    while pila:
        v = pila.pop()
        res.append(v)
        pila.extend(v.get('subViews', []))
    return res


# ---------------------------------------------------------------------------
# mdj_borrar: vistas a cualquier profundidad
# ---------------------------------------------------------------------------

def test_borrar_un_atributo_quita_su_vista_y_rehace_el_compartimento(dominio):
    doc = M.Doc(dominio)
    cli = doc.find('UMLClass:Cliente')
    email = next(a for a in cli['attributes'] if a['name'] == 'email')
    v = doc.view_in(doc.diagram('cu_1'), cli['_id'])
    assert any(s.get('model', {}).get('$ref') == email['_id'] for s in _todas({'ownedViews': [v]}))
    alto_antes = v['height']
    r = ok(tool('mdj_borrar', archivo=dominio, elemento=email['_id']))
    assert r['vistas_borradas'] == 1
    doc = M.Doc(dominio)
    cli = doc.find('UMLClass:Cliente')
    assert [a['name'] for a in cli['attributes']] == ['nombre', 'direccion']
    v = doc.view_in(doc.diagram('cu_1'), cli['_id'])
    assert not any(s.get('model', {}).get('$ref') == email['_id'] for s in _todas({'ownedViews': [v]}))
    # el compartimento queda con dos renglones seguidos y la caja un renglon mas baja
    attr = [s for s in _todas({'ownedViews': [v]}) if s['_type'] == 'UMLAttributeView']
    assert sorted(s['top'] - v['top'] for s in attr) == [72, 87]
    assert v['height'] == alto_antes - 15
    assert ids_integros(dominio)


def test_borrar_una_operacion_con_vista_dentro_de_su_compartimento(dominio):
    doc = M.Doc(dominio)
    ped = doc.find('UMLClass:Pedido')
    op = ped['operations'][0]
    v = doc.view_in(doc.diagram('cu_1'), ped['_id'])
    ocv = next(s for s in v['subViews'] if s['_type'] == 'UMLOperationCompartmentView')
    ocv['subViews'] = [{'_type': 'UMLOperationView', '_id': doc.new_id(), '_parent': M.ref(ocv['_id']),
                        'model': M.ref(op['_id']), 'font': 'Arial;13;0', 'parentStyle': True, 'left': v['left'] + 5,
                        'top': v['top'] + 110, 'width': v['width'] - 9, 'height': 13, 'text': '+calcularTotal(): double'}]
    doc.save(backup=False)
    ok(tool('mdj_borrar', archivo=dominio, elemento=op['_id']))
    doc = M.Doc(dominio)
    assert not doc.find('UMLClass:Pedido').get('operations')
    assert not any(s['_type'] == 'UMLOperationView' for s in _todas(doc.diagram('cu_1')))
    assert ids_integros(dominio)


# ---------------------------------------------------------------------------
# mdj_nota
# ---------------------------------------------------------------------------

def test_nota_no_edita_una_vista_que_no_es_nota(modelo):
    doc = M.Doc(modelo)
    dg = doc.diagram('cu_1')
    clase = doc.view_in(dg, 'Cuenta')
    nota = next(v for v in dg['ownedViews'] if v['_type'] == 'UMLNoteView')
    antes = _bytes(modelo)
    r = tool('mdj_nota', archivo=modelo, diagrama='cu_1', texto='texto de nota', x=10, y=10, ancho=150, vista=clase['_id'])
    assert 'no una nota' in r['error']
    assert _bytes(modelo) == antes
    ok(tool('mdj_nota', archivo=modelo, diagrama='cu_1', texto='otro texto', x=40, y=420, ancho=200, vista=nota['_id']))
    assert M.Doc(modelo).get(nota['_id'])['text'] == 'otro texto'


# ---------------------------------------------------------------------------
# mdj_asociacion_crear / mdj_asociacion_editar
# ---------------------------------------------------------------------------

def test_asociacion_no_acepta_un_diagrama_como_extremo(modelo):
    doc = M.Doc(modelo)
    dg = doc.diagram('cu_1')
    antes = _bytes(modelo)
    for hacia in ('cu_1_FB', dg['_id']):
        r = tool('mdj_asociacion_crear', archivo=modelo, desde='Cuenta', hacia=hacia)
        assert 'clases, actores o interfaces' in r['error'], r
    r = tool('mdj_asociacion_crear', archivo=modelo, desde=dg['_id'], hacia='Cuenta')
    assert 'clases, actores o interfaces' in r['error']
    asoc = next(o for o in doc.ids.values() if o and o['_type'] == 'UMLAssociation')
    for clase in ('cu_1', dg['_id']):
        r = tool('mdj_asociacion_editar', archivo=modelo, asociacion=asoc['_id'], extremo=2, clase=clase)
        assert 'clases, actores o interfaces' in r['error'], r
    assert _bytes(modelo) == antes


def test_asociacion_solo_se_guarda_en_un_paquete_o_clasificador(modelo):
    doc = M.Doc(modelo)
    dg = doc.diagram('cu_1')
    antes = _bytes(modelo)
    for duenio in ('cu_1', dg['_id']):
        r = tool('mdj_asociacion_crear', archivo=modelo, desde='Cuenta', hacia='Usuario', duenio=duenio)
        assert 'paquete o en un clasificador' in r['error'], r
    asoc = next(o for o in doc.ids.values() if o and o['_type'] == 'UMLAssociation')
    r = tool('mdj_asociacion_editar', archivo=modelo, asociacion=asoc['_id'], extremo=1, duenio='cu_1_FB')
    assert 'paquete o en un clasificador' in r['error']
    assert _bytes(modelo) == antes
    # lo valido sigue funcionando: clase con actor, guardada en el paquete
    a = ok(tool('mdj_asociacion_crear', archivo=modelo, desde='Cuenta', hacia='Usuario', duenio='Analisis'))
    doc = M.Doc(modelo)
    assert doc.name_of(doc.parent[a['asociacion']]) == 'Analisis'


def test_buscar_por_id_respeta_los_tipos(modelo):
    doc = M.Doc(modelo)
    dg = doc.diagram('cu_1')
    with pytest.raises(M.MdjError, match='UMLClassDiagram'):
        doc.find(dg['_id'], types=('UMLClass',))
    assert doc.find(dg['_id'])['_id'] == dg['_id']


# ---------------------------------------------------------------------------
# mdj_vista_mover
# ---------------------------------------------------------------------------

def test_mover_vista_respeta_el_alto_pedido(modelo):
    r = ok(tool('mdj_vista_mover', archivo=modelo, diagrama='cu_1', elemento='Cuenta', alto=300, ancho=200))
    assert (r['ancho'], r['alto']) == (200, 300) and 'aviso' not in r
    # un movimiento simple no cambia el tamano
    r = ok(tool('mdj_vista_mover', archivo=modelo, diagrama='cu_1', elemento='Cuenta', x=700))
    assert (r['x'], r['ancho'], r['alto']) == (700, 200, 300)
    # si el alto pedido no alcanza para los atributos, crece hasta lo necesario y lo dice
    r = ok(tool('mdj_vista_mover', archivo=modelo, diagrama='cu_1', elemento='Cuenta', alto=40))
    assert r['alto'] == M.alto_minimo_atributos(2) and 'no alcanza' in r['aviso']


def test_mover_no_achica_una_entity_mas_alta_que_sus_atributos(modelo):
    doc = M.Doc(modelo)
    v = doc.view_in(doc.diagram('cu_1'), 'Sesión')
    v['height'] += 30  # mas alta de lo que piden sus dos atributos
    doc.save(backup=False)
    r = ok(tool('mdj_vista_mover', archivo=modelo, diagrama='cu_1', elemento='Sesión', x=v['left'] + 10))
    assert r['alto'] == v['height']


# ---------------------------------------------------------------------------
# Deteccion de StarUML abierto: el ejecutable tiene que ir primero
# ---------------------------------------------------------------------------

@pytest.mark.deteccion_real
@pytest.mark.skipif(os.name == 'nt' or not shutil.which('ps'), reason='usa ps')
def test_un_programa_en_una_carpeta_staruml_no_cuenta_como_staruml_abierto(tmp_path):
    if M.staruml_gui_abierto() is not False:
        pytest.skip('StarUML esta abierto en esta maquina')
    carpeta = tmp_path / 'StarUML MCP'
    carpeta.mkdir()
    script = carpeta / 'server.py'
    script.write_text('import time\ntime.sleep(30)\n')
    p = subprocess.Popen([sys.executable, str(script)])
    try:
        time.sleep(0.5)
        assert p.poll() is None, 'el proceso de prueba no arranco'
        assert M.staruml_gui_abierto() is False
    finally:
        p.kill()
        p.wait()


# ---------------------------------------------------------------------------
# Anotaciones MCP
# ---------------------------------------------------------------------------

SOLO_LECTURA = {'staruml_estado', 'staruml_reglas', 'mdj_resumen', 'mdj_modelo', 'mdj_secuencia', 'mdj_comportamiento',
                'mdj_catalogo', 'mdj_geometria', 'mdj_buscar', 'mdj_validar', 'mdj_diff', 'svg_revisar',
                'staruml_comparar_codigo', 'mdj_secuencia_revisar'}
# quitan, reemplazan o sobrescriben algo que ya existe (atributos, vistas, puntos, textos, archivos)
DESTRUCTIVAS = {'staruml_exportar', 'svg_recortar', 'staruml_ver_visual', 'staruml_diagrama_a_codigo',
                'staruml_codigo_a_diagrama', 'staruml_programa_a_diagrama', 'mdj_diagrama_crear', 'mdj_renombrar',
                'mdj_documentacion', 'mdj_atributos', 'mdj_asociacion_editar', 'mdj_borrar', 'mdj_vista_mover',
                'mdj_linea_ruta', 'mdj_linea_etiqueta', 'mdj_nota', 'mdj_secuencia_generar',
                'mdj_robustez_generar'}
# solo agregan
ADITIVAS = {'mdj_respaldar', 'mdj_clase_crear', 'mdj_paquete_crear', 'mdj_dibujar', 'mdj_diagrama_generar',
            'mdj_elemento_crear', 'mdj_relacion_crear', 'mdj_asociacion_crear', 'mdj_vista_agregar'}


def test_anotaciones_de_todas_las_herramientas():
    nombres = {t['name'] for t in S.TOOLS}
    assert nombres == SOLO_LECTURA | DESTRUCTIVAS | ADITIVAS, 'herramienta sin clasificar'
    assert not (SOLO_LECTURA & DESTRUCTIVAS or SOLO_LECTURA & ADITIVAS or DESTRUCTIVAS & ADITIVAS), 'en dos grupos'
    for t in S.TOOLS:
        ann = t['annotations']
        if t['name'] in SOLO_LECTURA:
            assert ann['readOnlyHint'] is True, t['name']
            assert not {'salida', 'carpeta', 'carpeta_salida', 'forzar'} & set(t['inputSchema']['properties'])
        else:
            assert ann['readOnlyHint'] is False, t['name']
            assert ann['destructiveHint'] is (t['name'] in DESTRUCTIVAS), t['name']


def test_robustez_es_destructiva_porque_reemplaza_lo_que_reusa(dominio):
    # Cliente ya existe en el paquete con tres atributos y dibujado en cu_1: el diagrama de analisis lo reusa y le
    # deja solo los atributos y la documentacion que se le pasan, tambien en su vista de cu_1
    doc = M.Doc(dominio)
    cli = doc.find('UMLClass:Cliente')
    assert [x['name'] for x in cli['attributes']] == ['nombre', 'email', 'direccion']
    paquete = doc.name_of(doc.parent[cli['_id']])
    dg = ok(tool('mdj_diagrama_crear', archivo=dominio, tipo='clases', nombre='Robustez', dentro_de=paquete))['diagrama']
    ok(tool('mdj_robustez_generar', archivo=dominio, diagrama=dg, paquete=paquete, actores=[{'nombre': 'Asesor'}],
            pantallas=[{'nombre': 'PantallaCliente'}], control={'nombre': 'ControlCliente'},
            entidades=[{'nombre': 'Cliente', 'atributos': ['rfc'], 'documentacion': 'Quien renta'}]))
    doc = M.Doc(dominio)
    cli = doc.find('UMLClass:Cliente')
    assert [x['name'] for x in cli['attributes']] == ['rfc'] and cli['documentation'] == 'Quien renta'
    v = doc.view_in(doc.diagram('cu_1'), cli['_id'])
    assert [s['model']['$ref'] for s in _todas({'ownedViews': [v]}) if s['_type'] == 'UMLAttributeView'] == \
        [cli['attributes'][0]['_id']]
    assert ids_integros(dominio)
    # sin la lista de atributos, la entidad reusada conserva los que tiene
    dg = ok(tool('mdj_diagrama_crear', archivo=dominio, tipo='clases', nombre='Robustez2', dentro_de=paquete))['diagrama']
    ok(tool('mdj_robustez_generar', archivo=dominio, diagrama=dg, paquete=paquete, actores=[{'nombre': 'Asesor'}],
            pantallas=[{'nombre': 'PantallaCliente'}], control={'nombre': 'ControlCliente'},
            entidades=[{'nombre': 'Cliente'}]))
    assert [x['name'] for x in M.Doc(dominio).find('UMLClass:Cliente')['attributes']] == ['rfc']


# ---------------------------------------------------------------------------
# Protocolo: lineas que no son UTF-8 y surrogates sueltos
# ---------------------------------------------------------------------------

def test_linea_con_utf8_invalido_responde_error_y_sigue():
    c = ClienteMCP()
    c.p.stdin.write(b'{"jsonrpc":"2.0","id":1,"method":"ping","x":"\xff"}\n')
    c.p.stdin.flush()
    r = c.leer()
    assert r['id'] is None and r['error']['code'] == -32700
    assert c.pedir('ping')['result'] == {}
    assert 'Traceback' not in c.cerrar()


def test_surrogate_suelto_no_tumba_el_servidor():
    c = ClienteMCP()
    c.crudo('{"jsonrpc":"2.0","id":"\\ud800","method":"ping"}')
    r = c.leer()
    assert r['id'] == '\ud800' and r['result'] == {}
    assert c.pedir('ping')['result'] == {}
    assert 'Traceback' not in c.cerrar()


# ---------------------------------------------------------------------------
# Auto-mensajes: donde dibuja StarUML la etiqueta
# ---------------------------------------------------------------------------

def _left_como_staruml(v, lab):
    """Borde izquierdo de una etiqueta de linea como lo calcula StarUML (EdgeParasiticView.arrangeObject y
    Coord.getPointAwayLine): no usa left/top, sino el punto medio de la linea, alpha y distance."""
    pts = [tuple(float(n) for n in p.split(':')) for p in v['points'].split(';')]
    n = len(pts)
    i = n // 2 - (1 if n % 2 == 0 else 0)
    p1, p2 = pts[i], pts[i + 1]
    if n % 2 == 0:
        p1 = (math.floor((p1[0] + p2[0]) / 2), math.floor((p1[1] + p2[1]) / 2))
    a, b = p1[0] - p2[0], p1[1] - p2[1]
    th = math.atan(abs(b) / (abs(a) + 0.000001))
    if a > 0:
        th = math.pi - th if b > 0 else th + math.pi
    elif b < 0:
        th = 2 * math.pi - th
    return math.floor(lab['distance'] * math.cos(th + lab['alpha'])) + p1[0] - math.floor(lab['width'] / 2)


def test_etiqueta_del_auto_mensaje_queda_a_la_derecha_del_lazo(modelo):
    ms = [{'de': 'usr', 'a': 'ui', 'nombre': 'ingresar(usuario)'},
          {'de': 'ui', 'a': 'ctrl', 'nombre': 'autenticar(usuario)'},
          {'de': 'ctrl', 'a': 'ctrl', 'nombre': 'validarFormatoDeUsuarioYContrasena(usuario, contrasena)'},
          {'de': 'ctrl', 'a': 'ui', 'nombre': 'mostrarResultado()'}]
    ok(tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=ms))
    doc = M.Doc(modelo)
    dg = doc.diagram('cu_1_FB')
    auto = [v for v in dg['ownedViews'] if v['_type'] == 'UMLSeqMessageView' and v['head'] == v['tail']]
    assert len(auto) == 1
    v = auto[0]
    lab = doc.get(v['nameLabel']['$ref'])
    x0 = float(v['points'].split(';')[0].split(':')[0])
    izq = _left_como_staruml(v, lab)
    # a la derecha del tramo vertical del lazo, lejos de la activacion de quien llama, y donde lo guarda el archivo
    assert izq > x0 + M.AUTO_ANCHO
    assert abs(izq - (x0 + M.AUTO_ETIQUETA)) <= 1 and abs(izq - lab['left']) <= 1


# ---------------------------------------------------------------------------
# mdj_respaldar en una carpeta indicada
# ---------------------------------------------------------------------------

def test_respaldar_en_una_carpeta_indicada_no_borra_nada(modelo, tmp_path, monkeypatch):
    monkeypatch.setenv('STARUML_MCP_BACKUP_KEEP', '2')
    carpeta = tmp_path / 'mis_respaldos'
    carpeta.mkdir()
    viejos = [carpeta / f'modelo_2020010{i}_120000.mdj' for i in range(1, 4)]
    for f in viejos:
        f.write_text('{}')
    r = ok(tool('mdj_respaldar', archivo=modelo, carpeta=str(carpeta)))
    assert all(f.exists() for f in viejos) and os.path.exists(r['respaldo'])
    assert json.loads(_bytes(r['respaldo'])) == json.loads(_bytes(modelo))


# ---------------------------------------------------------------------------
# staruml_programa_a_diagrama: el aviso de programa grande no sugiere algo que no sirve
# ---------------------------------------------------------------------------

def _programa_grande(carpeta, paquetes, n=64):
    archivos = {}
    for i in range(n):
        pk = paquetes[i % len(paquetes)]
        archivos[f'{pk.replace(".", "/")}/Clase{i}.java'] = (f'package {pk};\n\npublic class Clase{i} {{\n'
                                                             f'    private int dato{i};\n}}\n')
    return fuentes(carpeta, archivos)


def test_programa_grande_sugiere_partir_por_paquete_solo_si_hay_varios(tmp_path):
    uno = _programa_grande(str(tmp_path / 'uno'), ['app'])
    r = ok(tool('staruml_programa_a_diagrama', archivo=str(tmp_path / 'uno.mdj'), ruta_codigo=uno,
                diagrama_por='programa'))
    assert r['diagramas'][0]['cajas'] > 60
    assert 'no lo partiria' in r['aviso'] and 'queda uno por paquete' not in r['aviso']
    varios = _programa_grande(str(tmp_path / 'varios'), ['app.ventas', 'app.admin'])
    r = ok(tool('staruml_programa_a_diagrama', archivo=str(tmp_path / 'varios.mdj'), ruta_codigo=varios,
                diagrama_por='programa'))
    assert 'queda uno por paquete' in r['aviso']
