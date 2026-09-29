# Utilidades compartidas por las pruebas: modelos .mdj sinteticos con la estructura que guarda StarUML,
# un cliente MCP por stdio y la llamada directa a las herramientas del servidor.
import base64
import glob
import json
import os
import subprocess
import sys
import textwrap
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import server as S  # noqa: E402
import staruml_mdj as M  # noqa: E402

_ts = [int(time.time() * 1000) - 900000]


def nid():
    _ts[0] += 3
    return base64.b64encode(b'\x00' * 4 + _ts[0].to_bytes(6, 'big') + os.urandom(4)).decode()


ref = M.ref


def proyecto_vacio(nombre='Fixture'):
    """Project > UMLProfile (boundary/control/entity) + UMLModel > diagrama de clases 'cu_1' (vacio, sin ownedViews,
    como lo guarda StarUML), paquete 'Analisis' con el actor 'Usuario' y colaboracion > interaccion > 'cu_1_FB'."""
    root, prof, model, pk, dcl, colab, inter, dsec, fv, fl1, fl2, actor = [nid() for _ in range(12)]
    st = {n: nid() for n in ('boundary', 'control', 'entity')}
    return {
        '_type': 'Project', '_id': root, 'name': nombre,
        'ownedElements': [
            {'_type': 'UMLProfile', '_id': prof, '_parent': ref(root), 'name': 'UMLStandardProfile',
             'ownedElements': [{'_type': 'UMLStereotype', '_id': st[n], '_parent': ref(prof), 'name': n} for n in st]},
            {'_type': 'UMLModel', '_id': model, '_parent': ref(root), 'name': 'Model',
             'ownedElements': [
                 {'_type': 'UMLClassDiagram', '_id': dcl, '_parent': ref(model), 'name': 'cu_1', 'defaultDiagram': True},
                 {'_type': 'UMLPackage', '_id': pk, '_parent': ref(model), 'name': 'Analisis',
                  'ownedElements': [{'_type': 'UMLActor', '_id': actor, '_parent': ref(pk), 'name': 'Usuario'}]},
                 {'_type': 'UMLCollaboration', '_id': colab, '_parent': ref(model), 'name': 'Collaboration1',
                  'ownedElements': [
                      {'_type': 'UMLInteraction', '_id': inter, '_parent': ref(colab), 'name': 'flujo basico',
                       'ownedElements': [
                           {'_type': 'UMLSequenceDiagram', '_id': dsec, '_parent': ref(inter), 'name': 'cu_1_FB',
                            'ownedViews': [
                                {'_type': 'UMLFrameView', '_id': fv, '_parent': ref(dsec), 'model': ref(dsec),
                                 'subViews': [
                                     {'_type': 'LabelView', '_id': fl1, '_parent': ref(fv), 'font': 'Arial;13;0',
                                      'left': 32.72998046875, 'top': 15, 'width': 60, 'height': 13, 'text': 'cu_1_FB'},
                                     {'_type': 'LabelView', '_id': fl2, '_parent': ref(fv), 'font': 'Arial;13;1',
                                      'left': 13, 'top': 15, 'width': 14.72, 'height': 13, 'text': 'sd'}],
                                 'font': 'Arial;13;0', 'left': 8, 'top': 10, 'width': 695, 'height': 595,
                                 'nameLabel': ref(fl1), 'frameTypeLabel': ref(fl2)}]}]}]}]}]}


def guardar_json(d, path):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent='\t')
    return path


def tool(_herramienta, /, **a):
    """Llama la herramienta como lo hace el servidor (esquema + rutas); los errores vuelven como {'error': ...}."""
    r = S.llamar_herramienta({'name': _herramienta, 'arguments': a})
    assert r is not None, f'herramienta desconocida {_herramienta}'
    contenido = r['content'][0]
    texto = contenido.get('text', '') if contenido['type'] == 'text' else ''
    if r['isError']:
        return {'error': texto}
    try:
        return json.loads(texto)
    except ValueError:
        return {'texto': texto, 'content': r['content']}


def ok(r):
    assert 'error' not in r, r.get('error')
    return r


def poblar(path):
    """Caso de uso de ejemplo completo: 4 clases de robustez, vistas, asociaciones, una nota y la secuencia."""
    for nombre, est, attrs in (('Pantalla Autenticación', 'boundary', None), ('Control Autenticación', 'control', None),
                               ('Cuenta', 'entity', ['usuario', 'contraseña']), ('Sesión', 'entity', ['inicio', 'fin'])):
        a = dict(archivo=path, paquete='Analisis', nombre=nombre, estereotipo=est)
        if attrs:
            a['atributos'] = attrs
        ok(tool('mdj_clase_crear', **a))
    for el, x, y in (('Usuario', 40, 120), ('Pantalla Autenticación', 200, 110), ('Control Autenticación', 430, 125),
                     ('Cuenta', 680, 105), ('Sesión', 690, 330)):
        ok(tool('mdj_vista_agregar', archivo=path, diagrama='cu_1', elemento=el, x=x, y=y))
    for a_, b_, m1, m2 in (('Usuario', 'Pantalla Autenticación', '', ''), ('Pantalla Autenticación', 'Control Autenticación', '', ''),
                           ('Control Autenticación', 'Cuenta', '', ''), ('Control Autenticación', 'Sesión', '', ''),
                           ('Cuenta', 'Sesión', '1', '0..*')):
        ok(tool('mdj_asociacion_crear', archivo=path, desde=a_, hacia=b_, mult_desde=m1, mult_hacia=m2, diagrama='cu_1'))
    ok(tool('mdj_nota', archivo=path, diagrama='cu_1', texto='Responsabilidad: autenticar al usuario.', x=40, y=420, ancho=200))
    ok(tool('mdj_secuencia_generar', archivo=path, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=MENSAJES))
    return path


LIFELINES = [{'clave': 'usr', 'tipo': 'Usuario'}, {'clave': 'ui', 'tipo': 'Pantalla Autenticación'},
             {'clave': 'ctrl', 'tipo': 'Control Autenticación'}, {'clave': 'cta', 'tipo': 'Cuenta'}, {'clave': 'ses', 'tipo': 'Sesión'}]
MENSAJES = [
    {'de': 'usr', 'a': 'ui', 'nombre': 'ingresarCredenciales(usuario, contraseña)', 'flujo': 'F1'},
    {'de': 'ui', 'a': 'ctrl', 'nombre': 'autenticar(usuario, contraseña)', 'flujo': 'F1'},
    {'de': 'ctrl', 'a': 'cta', 'nombre': 'buscarCuenta(usuario)', 'flujo': 'F1'},
    {'de': 'cta', 'a': 'ctrl', 'nombre': 'cuenta', 'reply': True, 'flujo': 'F1'},
    {'de': 'ctrl', 'a': 'ses', 'nombre': 'crearSesion(cuenta)', 'flujo': 'F2'},
    {'de': 'ses', 'a': 'ctrl', 'nombre': 'sesion', 'reply': True, 'flujo': 'F2'},
    {'de': 'ctrl', 'a': 'ui', 'nombre': 'mostrarBienvenida()', 'flujo': 'F2'},
    {'de': 'ui', 'a': 'usr', 'nombre': 'verBienvenida()', 'flujo': 'F2'},
]


def modelo_dominio(path, tipo_ref=False, nav_item='notNavigable'):
    """Diagrama 'cu_1' con Cliente, Direccion, Pedido, Item, ClienteVIP (generaliza a Cliente) y el actor Usuario."""
    guardar_json(proyecto_vacio(), path)
    doc = M.Doc(path)
    pk = doc.find('Analisis')
    dg = doc.diagram('cu_1')

    def clase(n, attrs=(), ops=()):
        c = {'_type': 'UMLClass', '_id': doc.new_id(), '_parent': ref(pk['_id']), 'name': n,
             'stereotype': ref(doc.stereotype_id('entity'))}
        c['attributes'] = [{'_type': 'UMLAttribute', '_id': doc.new_id(), '_parent': ref(c['_id']), 'name': a, 'type': t}
                           for a, t in attrs]
        if ops:
            c['operations'] = []
            for on, ret in ops:
                o = {'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': ref(c['_id']), 'name': on}
                o['parameters'] = [{'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': ref(o['_id']), 'type': ret,
                                    'direction': 'return'}]
                c['operations'].append(o)
        pk['ownedElements'].append(c)
        return c
    direc = clase('Direccion', [('calle', 'String')])
    cli = clase('Cliente', [('nombre', 'String'), ('email', 'String'),
                            ('direccion', ref(direc['_id']) if tipo_ref else 'Direccion')])
    ped = clase('Pedido', [('total', 'double'), ('items', 'List<Item>')], ops=[('calcularTotal', 'double')])
    item = clase('Item', [('cantidad', 'int')])
    vip = clase('ClienteVIP', [('descuento', 'double')])
    pk['ownedElements'].append({'_type': 'UMLGeneralization', '_id': doc.new_id(), '_parent': ref(pk['_id']),
                                'source': ref(vip['_id']), 'target': ref(cli['_id'])})
    doc.reindex()
    x = 40
    for el in (doc.find('Usuario'), direc, cli, ped, item, vip):
        M.vista_nueva(doc, dg, el, x, 100)
        x += 190
    M.asociacion_crear(doc, cli, ped, '1', '0..*')
    a2 = M.asociacion_crear(doc, ped, item, '1', '1..*', navegable='ninguno')
    if nav_item:
        a2['end2']['navigable'] = nav_item
    doc.save(backup=False)
    return path


def fuentes(carpeta, archivos):
    """Escribe archivos de codigo (texto con sangria comun eliminada) y devuelve la carpeta."""
    for nombre, src in archivos.items():
        p = os.path.join(carpeta, nombre)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(src))
    return carpeta


def ids_integros(path):
    v = M.validar(M.Doc(path), oose=False)
    return v['n_duplicados'] == 0 and v['n_colgantes'] == 0 and v['n_parent_mismatch'] == 0


def modelo_real():
    """El .mdj real del caso de uso (no se versiona): STARUML_MCP_MODELO_REAL o el primer pruebas/*.mdj."""
    p = os.environ.get('STARUML_MCP_MODELO_REAL')
    if p and os.path.exists(p):
        return p
    cands = sorted(glob.glob(os.path.join(RAIZ, 'pruebas', '*.mdj')))
    return cands[0] if cands else None


class ClienteMCP:
    """Cliente MCP minimo por stdio."""

    def __init__(self, env=None, cwd=None):
        entorno = dict(os.environ)
        entorno.update(env or {})
        self.p = subprocess.Popen([sys.executable, os.path.join(RAIZ, 'server.py')], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=entorno, cwd=cwd or RAIZ)
        self.n = 0

    def crudo(self, linea):
        self.p.stdin.write((linea if linea.endswith('\n') else linea + '\n').encode('utf-8'))
        self.p.stdin.flush()

    def leer(self):
        linea = self.p.stdout.readline()
        if not linea:
            raise RuntimeError('el servidor cerro stdout: ' + self.p.stderr.read().decode('utf-8', 'replace')[-2000:])
        return json.loads(linea.decode('utf-8'))

    def pedir(self, metodo, params=None):
        self.n += 1
        msg = {'jsonrpc': '2.0', 'id': self.n, 'method': metodo}
        if params is not None:
            msg['params'] = params
        self.crudo(json.dumps(msg, ensure_ascii=False))
        return self.leer()

    def llamar(self, _herramienta, /, **args):
        r = self.pedir("tools/call", {"name": _herramienta, "arguments": args})
        res = r['result']
        texto = res['content'][0].get('text', '')
        try:
            datos = json.loads(texto)
        except ValueError:
            datos = texto
        return res['isError'], datos

    def cerrar(self):
        try:
            self.p.stdin.close()
        except OSError:
            pass
        self.p.wait(15)
        return self.p.stderr.read().decode('utf-8', 'replace')

    def salida_restante(self):
        """Todo lo que queda en stdout (tras cerrar stdin)."""
        self.p.stdin.close()
        out = self.p.stdout.read().decode('utf-8').splitlines()
        self.p.wait(15)
        return out
