# mdj_secuencia_revisar: las secuencias contra el modelo de clases (solo lectura).
import hashlib

import apoyo
from apoyo import M, ok, tool

LL = [dict(x) for x in apoyo.LIFELINES]


def md5(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def rehacer(path, mensajes, lifelines=LL):
    ok(tool('mdj_secuencia_generar', archivo=path, diagrama='cu_1_FB', lifelines=lifelines, mensajes=mensajes))


def revisiones(r, campo='problemas'):
    """(revision, n) de cada hallazgo de las secuencias."""
    return [(h['revision'], h.get('n')) for s in r['secuencias'] for h in s[campo]]


def con_operaciones(path, clase, ops):
    doc = M.Doc(path)
    c = doc.find(clase, types=('UMLClass',))
    c['operations'] = []
    for nombre, params in ops:
        oid = doc.new_id()
        op = {'_type': 'UMLOperation', '_id': oid, '_parent': M.ref(c['_id']), 'name': nombre}
        if params:
            op['parameters'] = [{'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': M.ref(oid), 'name': p, 'type': ''}
                                for p in params]
        c['operations'].append(op)
    doc.reindex()
    doc.save(force=True)


def test_modelo_de_ejemplo_sin_problemas_y_no_escribe(modelo):
    antes = md5(modelo)
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, clases='cu_1'))
    assert r['resumen']['problemas'] == 0 and r['resumen']['mensajes'] == 8
    # las asociaciones de ejemplo solo navegan hacia adelante: el regreso a la pantalla es aviso, no problema
    assert ('relacion', 7) in revisiones(r, 'avisos')
    # sin operaciones en el control no se revisan sus mensajes: un solo aviso general
    assert any(a['revision'] == 'metodos' for a in r['generales']['avisos'])
    assert md5(modelo) == antes


def test_lifeline_de_un_tipo_que_no_esta_en_el_diagrama(modelo):
    ok(tool('mdj_clase_crear', archivo=modelo, paquete='Analisis', nombre='Bitacora', estereotipo='entity', atributos=['evento']))
    ok(tool('mdj_asociacion_crear', archivo=modelo, desde='Control Autenticación', hacia='Bitacora'))
    rehacer(modelo, apoyo.MENSAJES[:4] + [{'de': 'ctrl', 'a': 'bit', 'nombre': 'registrarEvento(usuario)'}],
            LL + [{'clave': 'bit', 'tipo': 'Bitacora'}])
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, clases='cu_1', metodos='no'))
    assert any(h['revision'] == 'lifelines' and 'Bitacora' in h['explicacion'] for s in r['secuencias'] for h in s['problemas'])
    # sin el diagrama de clases no hay nada que reclamar
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, metodos='no'))
    assert r['resumen']['problemas'] == 0


def test_mensaje_entre_clases_sin_relacion(modelo):
    ok(tool('mdj_clase_crear', archivo=modelo, paquete='Analisis', nombre='Bitacora', estereotipo='entity', atributos=['evento']))
    rehacer(modelo, apoyo.MENSAJES[:4] + [{'de': 'ctrl', 'a': 'bit', 'nombre': 'registrarEvento(usuario)'}],
            LL + [{'clave': 'bit', 'tipo': 'Bitacora'}])
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, metodos='no'))
    assert ('relacion', 5) in revisiones(r)


def test_metodos_del_control(modelo):
    con_operaciones(modelo, 'Control Autenticación', [('autenticar', ['usuario', 'contraseña']), ('cerrarSesion', [])])
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo))
    ctrl = r['metodos_control']['Control Autenticación']
    assert any(u.startswith('autenticar') for u in ctrl['usados'])
    assert any(u.startswith('cerrarSesion') for u in ctrl['sin_usar'])
    assert r['resumen']['problemas'] == 0
    # nombre que no es operacion del control: problema; otro numero de argumentos: aviso
    mensajes = [dict(m) for m in apoyo.MENSAJES]
    mensajes[1]['nombre'] = 'iniciarSesion(usuario, contraseña)'
    rehacer(modelo, mensajes)
    assert ('metodos', 2) in revisiones(ok(tool('mdj_secuencia_revisar', archivo=modelo)))
    mensajes[1]['nombre'] = 'autenticar(usuario)'
    rehacer(modelo, mensajes)
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo))
    assert ('metodos', 2) in revisiones(r, 'avisos') and ('metodos', 2) not in revisiones(r)
    # con metodos='no' no se revisa nada de eso
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, metodos='no'))
    assert 'metodos_control' not in r or not r.get('metodos_control')


def test_argumento_sin_origen(modelo):
    mensajes = [dict(m) for m in apoyo.MENSAJES]
    mensajes[4]['nombre'] = 'crearSesion(token)'
    rehacer(modelo, mensajes)
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, metodos='no'))
    assert any(h['revision'] == 'argumentos' and 'token' in h['explicacion'] and h['n'] == 5
               for s in r['secuencias'] for h in s['avisos'])
    # los literales y lo que ya llego antes no cuentan
    mensajes[4]['nombre'] = 'crearSesion(cuenta, ACTIVA, 30)'
    rehacer(modelo, mensajes)
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, metodos='no'))
    assert not any(h['revision'] == 'argumentos' for s in r['secuencias'] for h in s['avisos'])
    # con parametros=false no se revisan
    mensajes[4]['nombre'] = 'crearSesion(token)'
    rehacer(modelo, mensajes)
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, metodos='no', parametros=False))
    assert not any(h['revision'] == 'argumentos' for s in r['secuencias'] for h in s['avisos'])


def test_reply_a_quien_no_hizo_la_llamada(modelo):
    mensajes = [dict(m) for m in apoyo.MENSAJES]
    mensajes[3] = {'de': 'cta', 'a': 'ui', 'nombre': 'cuenta', 'reply': True}
    rehacer(modelo, mensajes)
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, metodos='no'))
    assert any(h['revision'] == 'replies' and h['n'] == 4 for s in r['secuencias'] for h in s['problemas'])


def test_clase_del_diagrama_que_no_sale_en_ninguna_secuencia(modelo):
    ok(tool('mdj_clase_crear', archivo=modelo, paquete='Analisis', nombre='Bitacora', estereotipo='entity', atributos=['evento']))
    ok(tool('mdj_vista_agregar', archivo=modelo, diagrama='cu_1', elemento='Bitacora', x=900, y=420))
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, clases='cu_1', metodos='no'))
    assert any(a.get('clase') == 'Bitacora' and a['revision'] == 'clases' for a in r['generales']['avisos'])


def test_errores_de_entrada(modelo):
    assert 'error' in tool('mdj_secuencia_revisar', archivo=modelo, secuencias=['No existe'])
    assert 'error' in tool('mdj_secuencia_revisar', archivo=modelo, clases='cu_1_FB')  # es de secuencia, no de clases
    assert 'error' in tool('mdj_secuencia_revisar', archivo=modelo, metodos='algunos')
