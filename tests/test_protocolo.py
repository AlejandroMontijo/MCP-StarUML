# Protocolo MCP (JSON-RPC 2.0 por stdio) y escenario completo de punta a punta con el servidor real.
import json
import os
import shutil

import pytest

from apoyo import ClienteMCP, LIFELINES, MENSAJES, M, S, guardar_json, proyecto_vacio


def necesita_forzar():
    return M.staruml_gui_abierto() is not False  # si quien corre la suite tiene StarUML abierto


@pytest.fixture
def cliente(tmp_path):
    c = ClienteMCP(env={'STARUML_MCP_BACKUP_DIR': str(tmp_path / 'respaldos')})
    r = c.pedir('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'pytest', 'version': '1'}})
    assert r['result']['protocolVersion'] == '2025-06-18'
    c.crudo(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}))
    yield c
    c.cerrar()


def test_initialize_negocia_version():
    c = ClienteMCP()
    r = c.pedir('initialize', {'protocolVersion': '1999-01-01'})
    assert r['result']['protocolVersion'] == S.PROTOCOLOS[0]
    assert r['result']['capabilities'] == {'tools': {'listChanged': False}}
    assert c.pedir('ping')['result'] == {}
    c.cerrar()


def test_tools_list_completo(cliente):
    tools = cliente.pedir('tools/list')['result']['tools']
    assert len(tools) == 32
    nombres = [t['name'] for t in tools]
    assert len(set(nombres)) == len(nombres)
    for t in tools:
        assert set(t) == {'name', 'description', 'inputSchema', 'annotations'}
        assert t['inputSchema']['type'] == 'object' and t['inputSchema']['additionalProperties'] is False
        # una herramienta que escribe archivos nunca se anuncia como de solo lectura
        if any(k in t['inputSchema']['properties'] for k in ('salida', 'carpeta_salida', 'carpeta')):
            assert t['annotations']['readOnlyHint'] is False, t['name']


def test_errores_de_herramienta(cliente, tmp_path):
    r = cliente.pedir('tools/call', {'name': 'no_existe', 'arguments': {}})
    assert r['error']['code'] == -32602
    malos = [({}, 'Falta el argumento "archivo"'), ({'archivo': 5}, 'debe ser string'),
             ({'archivo': 'x.mdj', 'otro': 1}, 'Argumentos que no existen')]
    for args, texto in malos:
        es_error, datos = cliente.llamar('mdj_resumen', **args)
        assert es_error and texto in datos
    es_error, datos = cliente.llamar('mdj_resumen', archivo=str(tmp_path / 'no_existe.mdj'))
    assert es_error and 'No existe el archivo' in datos
    roto = tmp_path / 'roto.mdj'
    roto.write_text('{"_type": "Project", ')
    es_error, datos = cliente.llamar('mdj_resumen', archivo=str(roto))
    assert es_error and 'no es un .mdj valido' in datos


def test_nan_e_infinito_rechazados(cliente, modelo):
    antes = open(modelo, 'rb').read()
    for valor in ('NaN', 'Infinity', '-Infinity'):
        cliente.crudo('{"jsonrpc":"2.0","id":90,"method":"tools/call","params":{"name":"mdj_vista_mover","arguments":'
                      '{"archivo":%s,"diagrama":"cu_1","elemento":"Cuenta","x":%s}}}' % (json.dumps(modelo), valor))
        assert cliente.leer()['error']['code'] == -32700
    cliente.crudo('{"jsonrpc":"2.0","id":91,"method":"tools/call","params":{"name":"mdj_vista_mover","arguments":'
                  '{"archivo":%s,"diagrama":"cu_1","elemento":"Cuenta","x":1e999}}}' % json.dumps(modelo))
    r = cliente.leer()
    assert r['result']['isError'] and 'number' in r['result']['content'][0]['text']
    assert open(modelo, 'rb').read() == antes


def test_jsonrpc_lotes_invalidos_y_notificaciones():
    c = ClienteMCP()
    for linea in ('[{"jsonrpc":"2.0","id":1,"method":"ping"},{"jsonrpc":"2.0","id":2,"method":"ping"}]',
                  '42', '[]', '{"jsonrpc":"2.0","id":9,"method":5}', 'esto no es json',
                  '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"mdj_resumen","arguments":{}}}',
                  '{"jsonrpc":"2.0","method":"notifications/initialized"}',
                  '{"jsonrpc":"2.0","id":3,"method":"metodo/raro"}'):
        c.crudo(linea)
    salida = [json.loads(l) for l in c.salida_restante()]
    lote, numero, vacio, metodo, invalido, raro = salida  # las dos notificaciones no se responden
    assert isinstance(lote, list) and [r['id'] for r in lote] == [1, 2]
    assert numero['error']['code'] == vacio['error']['code'] == metodo['error']['code'] == -32600
    assert metodo['id'] == 9
    assert invalido['error']['code'] == -32700
    assert raro['error']['code'] == -32601


def test_utf8_aunque_el_entorno_diga_cp1252(tmp_path, modelo):
    """En Windows Python usa cp1252 en las tuberias: el servidor debe forzar UTF-8."""
    c = ClienteMCP(env={'PYTHONIOENCODING': 'cp1252', 'STARUML_MCP_BACKUP_DIR': str(tmp_path / 'r')})
    c.pedir('initialize', {'protocolVersion': '2025-06-18'})
    args = {'forzar': True} if necesita_forzar() else {}
    es_error, _ = c.llamar('mdj_documentacion', archivo=modelo, elemento='Cuenta', texto='Sesión → activa ✓', **args)
    assert not es_error
    es_error, datos = c.llamar('mdj_modelo', archivo=modelo, filtro='Cuenta')
    c.cerrar()
    assert not es_error and datos['clases'][0]['documentacion'] == 'Sesión → activa ✓'
    assert M.Doc(modelo).find('Cuenta')['documentation'] == 'Sesión → activa ✓'


def test_escenario_completo_por_stdio(tmp_path):
    """Construye el caso de uso con las herramientas, por el protocolo, y verifica integridad tras cada escritura."""
    base = guardar_json(proyecto_vacio(), str(tmp_path / 'base.mdj'))
    f = str(tmp_path / 'modelo.mdj')
    shutil.copy(base, f)
    c = ClienteMCP(env={'STARUML_MCP_BACKUP_DIR': str(tmp_path / 'respaldos')})
    c.pedir('initialize', {'protocolVersion': '2025-06-18'})
    extra = {'forzar': True} if necesita_forzar() else {}

    def escribe(_h, /, **a):
        es_error, d = c.llamar(_h, **a, **extra)
        assert not es_error, d
        v = d['validacion']
        assert v["n_duplicados"] == v["n_colgantes"] == v["n_parent_mismatch"] == 0, (_h, v)
        return d
    escribe('mdj_paquete_crear', archivo=f, nombre='Dominio')
    escribe('mdj_clase_crear', archivo=f, paquete='Analisis', nombre='Servicio de Correo', estereotipo='actor')
    for nombre, est, attrs in (('Pantalla Autenticación', 'boundary', None), ('Control Autenticación', 'control', None),
                               ('Cuenta', 'entity', ['usuario', 'contraseña']), ('Sesión', 'entity', ['inicio', 'fin'])):
        escribe('mdj_clase_crear', archivo=f, paquete='Analisis', nombre=nombre, estereotipo=est, **({'atributos': attrs} if attrs else {}))
    for el, x, y in (('Usuario', 40, 120), ('Pantalla Autenticación', 200, 110), ('Control Autenticación', 430, 125),
                     ('Cuenta', 680, 105), ('Sesión', 690, 330)):
        escribe('mdj_vista_agregar', archivo=f, diagrama='cu_1', elemento=el, x=x, y=y)
    for a, b, m1, m2 in (('Usuario', 'Pantalla Autenticación', '', ''), ('Pantalla Autenticación', 'Control Autenticación', '', ''),
                         ('Control Autenticación', 'Cuenta', '', ''), ('Control Autenticación', 'Sesión', '', ''),
                         ('Cuenta', 'Sesión', '1', '0..*')):
        d = escribe('mdj_asociacion_crear', archivo=f, desde=a, hacia=b, mult_desde=m1, mult_hacia=m2, diagrama='cu_1')
        assert d['avisos'] == []
    escribe('mdj_nota', archivo=f, diagrama='cu_1', texto='Responsabilidad: autenticar al usuario y abrir sesión.', x=40, y=420, ancho=200)
    es_error, v = c.llamar('mdj_validar', archivo=f)
    assert not es_error and v['oose'] == {'problemas': [], 'avisos': []}
    d = escribe('mdj_secuencia_generar', archivo=f, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=MENSAJES)
    assert d['oose'] == {'problemas': [], 'avisos': []}
    _, sec = c.llamar('mdj_secuencia', archivo=f, diagrama='cu_1_FB')
    assert [m['nombre'] for m in sec['mensajes']] == [m['nombre'] for m in MENSAJES]
    d = escribe('mdj_secuencia_generar', archivo=f, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=MENSAJES)
    assert d['lifelines_quitadas'] == 0 and d['roles_quitados'] == 0
    for nombre, kw in (('mdj_geometria', {'diagrama': 'cu_1'}), ('mdj_geometria', {'diagrama': 'cu_1_FB'}), ('mdj_buscar', {'texto': 'a'}),
                       ('mdj_modelo', {}), ('mdj_modelo', {'paquete': 'Analisis', 'filtro': 'Cuenta'}), ('mdj_resumen', {})):
        es_error, _ = c.llamar(nombre, archivo=f, **kw)
        assert not es_error, nombre
    d = escribe('mdj_renombrar', archivo=f, elemento='Cuenta', nuevo_nombre='Cuenta de Usuario')
    assert d['vistas_actualizadas'] >= 2  # la vista de la clase y la lifeline que la representa
    escribe('mdj_documentacion', archivo=f, elemento='Cuenta de Usuario', texto='Datos de acceso')
    _, g = c.llamar('mdj_geometria', archivo=f, diagrama='cu_1')
    vista = next(x['vista'] for x in g['cajas'] if x['elemento'] == 'Cuenta de Usuario')
    escribe('mdj_vista_mover', archivo=f, diagrama='cu_1', elemento=vista, x=700, y=90, ancho=150)
    linea = next(x for x in g['lineas'] if {x['de'], x['a']} == {'Control Autenticación', 'Cuenta de Usuario'})
    escribe('mdj_linea_ruta', archivo=f, diagrama='cu_1', linea=linea['vista'], puntos=[[600, 160]])
    lcs = next(x for x in g['lineas'] if {x['de'], x['a']} == {'Cuenta de Usuario', 'Sesión'})
    escribe('mdj_linea_etiqueta', archivo=f, linea=lcs['vista'], etiqueta='headMultiplicityLabel', alpha=0.4, distancia=22)
    escribe('mdj_asociacion_editar', archivo=f, asociacion=lcs['modelo'], extremo=2, mult='1..*', rol='sesiones')
    escribe('mdj_atributos', archivo=f, clase='Cuenta de Usuario', atributos=['usuario', 'hash', 'activo'])
    escribe('mdj_diagrama_crear', archivo=f, tipo='secuencia', nombre='cu_1_FA', dentro_de='Analisis')
    _, dif = c.llamar('mdj_diff', archivo_a=base, archivo_b=f)
    assert dif['agregados'].get('UMLClass') == 4 and dif['agregados'].get('UMLActor') == 1
    d = escribe('mdj_borrar', archivo=f, elemento='Sesión', salida='sin_sesion.mdj')
    assert d['guardado_en'] == str(tmp_path / 'sin_sesion.mdj')  # ruta relativa: junto al .mdj
    es_error, d = c.llamar('mdj_respaldar', archivo=f)
    assert not es_error and os.path.exists(d['respaldo'])
    for nombre in ('staruml_estado', 'staruml_reglas'):
        assert not c.llamar(nombre)[0]
    assert 'Traceback' not in c.cerrar()
