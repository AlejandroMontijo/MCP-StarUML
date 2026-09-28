# Pruebas exhaustivas del MCP de StarUML.
#   python3 pruebas/probar_todo.py "/ruta/modelo.mdj" [carpeta_con_mas_mdj ...]
# El .mdj y las carpetas solo se leen: todo lo que escribe va a copias en un directorio temporal.
import base64
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
import staruml_mdj as M          # noqa: E402
import staruml_render as R       # noqa: E402

MDJ = os.path.abspath(sys.argv[1])
EXTRA = sys.argv[2:]
TMP = tempfile.mkdtemp(prefix='mcp_todo_')
os.environ['STARUML_MCP_BACKUP_DIR'] = os.path.join(TMP, 'respaldos')
M.BACKUP_DIR = os.environ['STARUML_MCP_BACKUP_DIR']
md5 = lambda f: hashlib.md5(open(f, 'rb').read()).hexdigest()
MD5_ORIGINAL = md5(MDJ)
resultados = []


class Cliente:
    def __init__(self):
        env = dict(os.environ)
        self.p = subprocess.Popen([sys.executable, os.path.join(RAIZ, 'server.py')], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        self.n = 0
        self.lineas = []
        r = self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '1'}})
        assert r['result']['serverInfo']['name'] == 'staruml'
        self.enviar({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def enviar(self, obj, crudo=None):
        self.p.stdin.write((crudo if crudo is not None else json.dumps(obj)) + '\n'); self.p.stdin.flush()

    def leer(self):
        l = self.p.stdout.readline()
        self.lineas.append(l)
        return json.loads(l)

    def rpc(self, method, params=None, mid=None):
        self.n += 1
        m = {'jsonrpc': '2.0', 'id': mid if mid is not None else self.n, 'method': method}
        if params is not None:
            m['params'] = params
        self.enviar(m)
        return self.leer()

    def call(self, name, **args):
        r = self.rpc('tools/call', {'name': name, 'arguments': args})
        if 'error' in r:
            return True, r['error']['message'], r
        res = r['result']
        txt = res['content'][0]['text']
        try:
            data = json.loads(txt)
        except Exception:
            data = txt
        return bool(res.get('isError')), data, res

    def cerrar(self):
        try:
            self.p.stdin.close(); self.p.wait(10)
        except Exception:
            self.p.kill()
        return self.p.stderr.read()


CL = None


def prueba(nombre):
    def deco(fn):
        t0 = time.time()
        try:
            fn()
            resultados.append((nombre, True, '', time.time() - t0))
            print(f'OK    {nombre}')
        except Exception as e:
            det = ''.join(traceback.format_exception_only(type(e), e)).strip()
            resultados.append((nombre, False, det, time.time() - t0))
            print(f'FALLA {nombre}: {det[:400]}')
        return fn
    return deco


def copia(nombre='c'):
    d = os.path.join(TMP, f'{nombre}_{len(os.listdir(TMP))}.mdj')
    shutil.copy2(MDJ, d)
    return d


def valida(path):
    v = M.validar(M.Doc(path), oose=False)
    assert v['n_duplicados'] == 0 and v['n_colgantes'] == 0 and v['n_parent_mismatch'] == 0, \
        f"integridad: dup={v['n_duplicados']} colg={v['colgantes'][:3]} parent={v['parent_mismatch'][:3]}"
    return v


F = {'forzar': True}   # las copias temporales no estan abiertas en StarUML
DOC0 = M.Doc(MDJ)
DCLASES = next(d['name'] for d in sorted(DOC0.diagrams(), key=lambda d: -len(d.get('ownedViews', []))) if d['_type'] == 'UMLClassDiagram')
DSEC = next(d['name'] for d in sorted(DOC0.diagrams(), key=lambda d: -len(d.get('ownedViews', []))) if d['_type'] == 'UMLSequenceDiagram')
ENT = [o for o in DOC0.ids.values() if o and o['_type'] == 'UMLClass' and DOC0.kind(o) == 'entity' and DOC0.views_of(o['_id'], DOC0.diagram(DCLASES))]
BND = [o for o in DOC0.ids.values() if o and o['_type'] == 'UMLClass' and DOC0.kind(o) == 'boundary']
_po = DOC0.ids[DOC0.parent[ENT[0]['_id']]]
PAQ = f"{_po['_type']}:{_po.get('name')}"
print(f'modelo: {MDJ}\ndiagrama de clases: {DCLASES}; secuencia: {DSEC}; paquete: {PAQ}; temporales: {TMP}\n')

# ===========================================================================
# PROTOCOLO
# ===========================================================================
CL = Cliente()


@prueba('P01 initialize: version conocida se respeta, desconocida cae en la del servidor')
def _():
    c = Cliente()
    r = c.rpc('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'x', 'version': '1'}})
    assert r['result']['protocolVersion'] == '2024-11-05'
    r = c.rpc('initialize', {'protocolVersion': '1999-01-01', 'capabilities': {}, 'clientInfo': {'name': 'x', 'version': '1'}})
    assert r['result']['protocolVersion'] == '2025-06-18'
    assert 'tools' in r['result']['capabilities'] and r['result']['instructions']
    c.cerrar()


@prueba('P02 tools/list: esquemas validos, nombres unicos, required dentro de properties')
def _():
    tools = CL.rpc('tools/list')['result']['tools']
    nombres = [t['name'] for t in tools]
    assert len(nombres) == len(set(nombres)) and len(tools) >= 26
    for t in tools:
        assert re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', t['name']), t['name']
        assert t['description'] and len(t['description']) > 20, t['name']
        s = t['inputSchema']
        assert s['type'] == 'object' and isinstance(s['properties'], dict), t['name']
        assert set(s.get('required', [])) <= set(s['properties']), t['name']
        assert 'annotations' in t and 'readOnlyHint' in t['annotations'], t['name']
        json.dumps(s)
        for k, v in s['properties'].items():
            assert 'type' in v, f'{t["name"]}.{k} sin type'


@prueba('P03 ping, id tipo texto, metodo desconocido (-32601) y notificacion desconocida sin respuesta')
def _():
    assert CL.rpc('ping')['result'] == {}
    r = CL.rpc('ping', mid='abc-1'); assert r['id'] == 'abc-1'
    r = CL.rpc('no/existe'); assert r['error']['code'] == -32601
    CL.enviar({'jsonrpc': '2.0', 'method': 'notifications/algo'})
    r = CL.rpc('ping'); assert r['id'] == CL.n and r['result'] == {}


@prueba('P04 JSON malformado (-32700) y el servidor sigue vivo')
def _():
    CL.enviar(None, crudo='{esto no es json')
    r = CL.leer(); assert r['error']['code'] == -32700 and r['id'] is None
    assert CL.rpc('ping')['result'] == {}


@prueba('P05 lote de dos peticiones regresa dos respuestas')
def _():
    CL.enviar(None, crudo=json.dumps([{'jsonrpc': '2.0', 'id': 'b1', 'method': 'ping'}, {'jsonrpc': '2.0', 'id': 'b2', 'method': 'ping'}]))
    a, b = CL.leer(), CL.leer()
    assert {a['id'], b['id']} == {'b1', 'b2'}


@prueba('P06 herramienta desconocida y argumentos mal formados dan error claro, sin tumbar el servidor')
def _():
    r = CL.rpc('tools/call', {'name': 'no_existe', 'arguments': {}}); assert r['error']['code'] == -32602
    e, d, _ = CL.call('mdj_modelo'); assert e and 'Falta el argumento "archivo"' in d, d
    e, d, _ = CL.call('mdj_modelo', archivo=MDJ, inventado=1); assert e and 'no existen' in d, d
    e, d, _ = CL.call('mdj_nota', archivo=MDJ, diagrama=DCLASES, texto='x', x='10', y=1, ancho=100); assert e and '"x" debe ser number' in d, d
    e, d, _ = CL.call('staruml_exportar', archivo=MDJ, carpeta=TMP, formato='gif'); assert e and 'uno de' in d, d
    e, d, _ = CL.call('mdj_linea_ruta', archivo=MDJ, diagrama=DCLASES, linea='x', puntos=[[1, 2, 3]]); assert e and 'forma' in d, d
    e, d, _ = CL.call('mdj_secuencia_generar', archivo=MDJ, diagrama=DSEC, lifelines=[{'clave': 'a'}], mensajes=[]); assert e and 'tipo' in d, d
    assert CL.rpc('ping')['result'] == {}


@prueba('P07 archivo inexistente, elemento inexistente y diagrama inexistente dan isError')
def _():
    for args in ({'archivo': '/no/hay.mdj'},):
        e, d, _ = CL.call('mdj_resumen', **args); assert e and 'No existe' in d
    e, d, _ = CL.call('mdj_geometria', archivo=MDJ, diagrama='NoHayTal'); assert e and 'No encontre el diagrama' in d
    e, d, _ = CL.call('mdj_documentacion', archivo=copia(), elemento='NoHayTalClase', texto='x', **F); assert e and 'No encontre' in d


@prueba('P08 stdout solo tiene JSON-RPC valido')
def _():
    for l in CL.lineas:
        o = json.loads(l); assert o.get('jsonrpc') == '2.0'

# ===========================================================================
# FORMATO E IDS
# ===========================================================================
ARCHIVOS = sorted({MDJ, *[f for d in EXTRA for f in glob.glob(os.path.join(d, '*.mdj'))]})


@prueba(f'F01 cargar y guardar sin cambios deja el archivo identico byte por byte ({len(ARCHIVOS)} archivos)')
def _():
    distintos = []
    for f in ARCHIVOS:
        d = M.Doc(f)
        out = os.path.join(TMP, 'rt_' + hashlib.md5(f.encode()).hexdigest()[:8] + '.mdj')
        d.save(out, backup=False, force=True)
        if md5(out) != md5(f):
            distintos.append(os.path.basename(f))
    assert not distintos, f'no quedaron identicos: {distintos}'


@prueba('F02 ids nuevos: formato StarUML, unicos y sin chocar con los existentes')
def _():
    d = M.Doc(MDJ)
    antes = set(k for k, v in d.ids.items() if v)
    nuevos = [d.new_id() for _ in range(5000)]
    assert len(set(nuevos)) == 5000 and not (set(nuevos) & antes)
    for s in nuevos[:200]:
        b = base64.b64decode(s)
        assert len(s) == 20 and len(b) == 14 and b[:4] == b'\x00' * 4
        ts = int.from_bytes(b[4:10], 'big') / 1000
        assert abs(ts - time.time()) < 86400


@prueba('F03 respaldo identico y con nombre unico aunque se pida dos veces en el mismo segundo')
def _():
    c = copia()
    a = M.backup_file(c, os.path.join(TMP, 'bk')); b = M.backup_file(c, os.path.join(TMP, 'bk'))
    assert a != b and md5(a) == md5(c) == md5(b)


@prueba('F04 si el guardado falla a la mitad, el original queda intacto y no queda temporal')
def _():
    c = copia(); h = md5(c)
    d = M.Doc(c); d.d['_roto'] = object()
    try:
        d.save(force=True, backup=False); raise AssertionError('debio fallar')
    except TypeError:
        pass
    assert md5(c) == h and not os.path.exists(c + '.tmp_mcp')


@prueba('F05 deteccion de la app: la app si, el CLI de exportacion y los helpers no; save se niega si esta abierta')
def _():
    pat = r'StarUML\.app/Contents/MacOS/StarUML(\s+-psn\S*)?\s*$'
    assert re.search(pat, '/Users/x/Applications/StarUML.app/Contents/MacOS/StarUML')
    assert re.search(pat, '/Applications/StarUML.app/Contents/MacOS/StarUML -psn_0_123')
    assert not re.search(pat, '/Users/x/Applications/StarUML.app/Contents/MacOS/StarUML image a.mdj -f svg')
    assert not re.search(pat, '/Users/x/Applications/StarUML.app/Contents/Frameworks/StarUML Helper.app/Contents/MacOS/StarUML Helper --type=gpu')
    orig = M.staruml_gui_abierto; M.staruml_gui_abierto = lambda: True
    try:
        c = copia(); h = md5(c)
        try:
            M.Doc(c).save(); raise AssertionError('debio negarse')
        except M.MdjError as e:
            assert 'abierto' in str(e)
        assert md5(c) == h
        M.Doc(c).save(force=True)
    finally:
        M.staruml_gui_abierto = orig

# ===========================================================================
# LECTURA SOBRE TODOS LOS ARCHIVOS
# ===========================================================================


@prueba(f'L01 resumen, modelo, validar, buscar y geometria/secuencia de cada diagrama en {len(ARCHIVOS)} archivos')
def _():
    for f in ARCHIVOS:
        d = M.Doc(f)
        M.resumen(d); M.modelo(d); M.validar(d, oose=True); M.buscar(d, 'a')
        for dg in d.diagrams():
            if dg['_type'] == 'UMLSequenceDiagram':
                try:
                    M.secuencia(d, dg['_id'])
                except M.MdjError:
                    pass
            elif dg['_type'] in ('UMLClassDiagram', 'UMLUseCaseDiagram'):
                M.geometria(d, dg['_id'])


@prueba('L02 el modelo vigente pasa validar con OOSE sin problemas ni avisos')
def _():
    v = M.validar(M.Doc(MDJ), oose=True)
    assert v['n_duplicados'] == v['n_colgantes'] == v['n_parent_mismatch'] == 0
    assert not v['oose']['problemas'] and not v['oose']['avisos'], v['oose']


@prueba('L03 diff: un archivo contra si mismo sin cambios; contra una copia editada muestra el cambio')
def _():
    d = M.diff(M.Doc(MDJ), M.Doc(MDJ)); assert not d['cambios'] and not d['quitados'] and not d['agregados']
    c = copia(); e, _, _ = CL.call('mdj_renombrar', archivo=c, elemento=ENT[0]['_id'], nuevo_nombre='ZZRenombrada', **F); assert not e
    d = M.diff(M.Doc(MDJ), M.Doc(c)); assert any('ZZRenombrada' in x for x in d['cambios']), d['cambios']


@prueba('L04 buscar ambiguo por nombre exige id o Tipo:Nombre')
def _():
    c = copia()
    e, _, _ = CL.call('mdj_clase_crear', archivo=c, paquete=PAQ, nombre=ENT[0]['name'], estereotipo='entity', **F); assert not e
    e, d, _ = CL.call('mdj_documentacion', archivo=c, elemento=ENT[0]['name'], texto='x', **F); assert e and 'ambiguo' in d, d

# ===========================================================================
# ESCRITURA
# ===========================================================================


@prueba('W01 clase_crear entity/control/ninguno; boundary con atributos se rechaza; paquete inexistente se rechaza')
def _():
    c = copia()
    e, r, _ = CL.call('mdj_clase_crear', archivo=c, paquete=PAQ, nombre='TEnt', estereotipo='entity', atributos=['a', 'b'], documentacion='doc', **F)
    assert not e, r
    d = M.Doc(c); k = d.find('TEnt')
    assert d.kind(k) == 'entity' and [a['name'] for a in k['attributes']] == ['a', 'b'] and k['documentation'] == 'doc'
    assert d.parent[k['_id']] == d.find(PAQ)['_id']
    e, _, _ = CL.call('mdj_clase_crear', archivo=c, paquete=PAQ, nombre='TCtl', estereotipo='control', **F); assert not e
    e, _, _ = CL.call('mdj_clase_crear', archivo=c, paquete=PAQ, nombre='TNada', estereotipo='ninguno', **F); assert not e
    assert 'stereotype' not in M.Doc(c).find('TNada')
    e, d2, _ = CL.call('mdj_clase_crear', archivo=c, paquete=PAQ, nombre='TBnd', estereotipo='boundary', atributos=['x'], **F); assert e and 'sin atributos' in d2
    e, d2, _ = CL.call('mdj_clase_crear', archivo=c, paquete='NoExistePaquete', nombre='X', **F); assert e
    valida(c)


@prueba('W02 atributos: conserva ids, reordena, quita y agrega; rehace el compartimento en todas las vistas')
def _():
    c = copia(); d = M.Doc(c)
    cls = ENT[0]; viejos = {a['name']: a['_id'] for a in d.find(cls['_id'])['attributes']}
    nombres = list(viejos)
    nuevo = [nombres[-1]] + nombres[1:-1] + ['nuevoAtributo']
    e, r, _ = CL.call('mdj_atributos', archivo=c, clase=cls['_id'], atributos=nuevo, **F); assert not e, r
    assert r['quitados'] == [nombres[0]]
    d = M.Doc(c); k = d.find(cls['_id'])
    assert [a['name'] for a in k['attributes']] == nuevo
    for a in k['attributes'][:-1]:
        assert a['_id'] == viejos[a['name']]
    for dg, v in d.views_of(k['_id']):
        acv = [s for s in v['subViews'] if s['_type'] == 'UMLAttributeCompartmentView'][0]
        assert [s['text'] for s in acv['subViews']] == ['+' + n for n in nuevo]
        assert v['height'] >= 73 + 15 * len(nuevo)
        for i, s in enumerate(acv['subViews']):
            assert s['top'] == v['top'] + 72 + 15 * i
    valida(c)
    e, d2, _ = CL.call('mdj_atributos', archivo=c, clase=BND[0]['_id'], atributos=['x'], **F); assert e and 'sin atributos' in d2


@prueba('W03 vista_agregar: entity, boundary, control y actor; no en secuencia; no dos veces; se exporta limpio')
def _():
    c = copia()
    for nom, est in (('VEnt', 'entity'), ('VBnd', 'boundary'), ('VCtl', 'control')):
        e, r, _ = CL.call('mdj_clase_crear', archivo=c, paquete=PAQ, nombre=nom, estereotipo=est,
                          **({'atributos': ['id', 'dato']} if est == 'entity' else {}), **F); assert not e, r
    # un diagrama de clases vacio para dibujar sin estorbar
    d = M.Doc(c)
    vacio = next(g for g in d.diagrams() if g['_type'] == 'UMLClassDiagram' and not g.get('ownedViews'))
    actor = next(o for o in d.ids.values() if o and o['_type'] == 'UMLActor')
    for i, nom in enumerate(('VEnt', 'VBnd', 'VCtl', actor['_id'])):
        e, r, _ = CL.call('mdj_vista_agregar', archivo=c, diagrama=vacio['_id'], elemento=nom, x=60 + 230 * i, y=80 + 7 * i, **F)
        assert not e, r
    e, r, _ = CL.call('mdj_vista_agregar', archivo=c, diagrama=vacio['_id'], elemento='VEnt', x=10, y=10, **F); assert e and 'ya tiene vista' in r
    e, r, _ = CL.call('mdj_vista_agregar', archivo=c, diagrama=DSEC, elemento='VEnt', x=10, y=10, **F); assert e and 'secuencia' in r.lower() or 'UMLSequenceDiagram' in r, r
    d = M.Doc(c); g = d.diagram(vacio['_id'])
    v = d.views_of(d.find('VEnt')['_id'], g)[0][1]
    acv = [s for s in v['subViews'] if s['_type'] == 'UMLAttributeCompartmentView'][0]
    assert [s['text'] for s in acv['subViews']] == ['+id', '+dato']
    assert M._name_label(v)['text'] == 'VEnt'
    valida(c)
    out = os.path.join(TMP, 'exp_w03')
    ex = R.exportar(c, out, vacio['_id'])
    assert ex['archivos'], ex
    rv = R.revisar_svg(ex['archivos'][0], c, vacio['_id']); assert rv['n_problemas'] == 0, rv['problemas'][:5]


@prueba('W04 asociacion_crear con vista: extremos sobre el borde, etiquetas del modelo, navegabilidad y aviso OOSE')
def _():
    c = copia(); a, b = ENT[0], ENT[1]
    e, r, _ = CL.call('mdj_asociacion_crear', archivo=c, desde=a['_id'], hacia=b['_id'], mult_desde='1', mult_hacia='0..*',
                      rol_hacia='rolPrueba', navegable='ambos', diagrama=DCLASES, **F); assert not e, r
    d = M.Doc(c); dg = d.diagram(DCLASES); asoc = d.get(r['asociacion']); v = d.get(r['vista'])
    assert asoc['end1'].get('navigable') == 'navigable' and asoc['end2'].get('navigable') == 'navigable'
    tv = d.get(v['tail']['$ref']); hv = d.get(v['head']['$ref'])
    assert tv['model']['$ref'] == a['_id'] and hv['model']['$ref'] == b['_id']
    P = [tuple(map(float, p.split(':'))) for p in v['points'].split(';')]
    enborde = lambda p, x: min(abs(p[0] - x['left']), abs(p[0] - x['left'] - x['width']), abs(p[1] - x['top']), abs(p[1] - x['top'] - x['height'])) <= 1.5
    assert enborde(P[0], tv) and enborde(P[-1], hv), (P, tv['left'], tv['top'])
    sub = {s['_id']: s for s in v['subViews']}
    assert sub[v['tailMultiplicityLabel']['$ref']]['text'] == '1' and sub[v['headMultiplicityLabel']['$ref']]['text'] == '0..*'
    assert sub[v['headRoleNameLabel']['$ref']]['text'] == '+rolPrueba' and sub[v['tailRoleNameLabel']['$ref']].get('visible') is False
    valida(c)
    e, r2, _ = CL.call('mdj_asociacion_crear', archivo=c, desde=BND[0]['_id'], hacia=a['_id'], navegable='ninguno', **F)
    assert not e and r2['avisos'], r2
    asoc2 = M.Doc(c).get(r2['asociacion']); assert 'navigable' not in asoc2['end1'] and 'navigable' not in asoc2['end2']


@prueba('W05 asociacion_crear sin vista del elemento en el diagrama falla y no escribe nada')
def _():
    c = copia(); h = md5(c)
    e, r, _ = CL.call('mdj_clase_crear', archivo=c, paquete=PAQ, nombre='SinVista', estereotipo='entity', **F); assert not e
    h2 = md5(c)
    e, r, _ = CL.call('mdj_asociacion_crear', archivo=c, desde='SinVista', hacia=ENT[0]['_id'], diagrama=DCLASES, **F)
    assert e and 'no tiene vista' in r, r
    assert md5(c) == h2 != h


@prueba('W06 asociacion_editar: multiplicidad, rol y navegabilidad se ven en las etiquetas; mover extremo reapunta o quita vistas')
def _():
    c = copia(); a, b, x = ENT[0], ENT[1], ENT[2]
    e, r, _ = CL.call('mdj_asociacion_crear', archivo=c, desde=a['_id'], hacia=b['_id'], mult_hacia='1', diagrama=DCLASES, **F); assert not e
    aid, vid = r['asociacion'], r['vista']
    e, r2, _ = CL.call('mdj_asociacion_editar', archivo=c, asociacion=aid, extremo=2, mult='1..*', rol='otro', navegable=False, **F); assert not e, r2
    d = M.Doc(c); v = d.get(vid); sub = {s['_id']: s for s in v['subViews']}
    assert sub[v['headMultiplicityLabel']['$ref']]['text'] == '1..*' and sub[v['headRoleNameLabel']['$ref']]['text'] == '+otro'
    assert 'navigable' not in d.get(aid)['end2']
    e, r3, _ = CL.call('mdj_asociacion_editar', archivo=c, asociacion=aid, extremo=2, rol='', mult='', **F); assert not e
    d = M.Doc(c); v = d.get(vid); sub = {s['_id']: s for s in v['subViews']}
    assert sub[v['headRoleNameLabel']['$ref']].get('visible') is False and sub[v['headMultiplicityLabel']['$ref']].get('visible') is False
    e, r4, _ = CL.call('mdj_asociacion_editar', archivo=c, asociacion=aid, extremo=2, clase=x['_id'], **F); assert not e, r4
    d = M.Doc(c); v = d.get(vid); assert d.get(v['head']['$ref'])['model']['$ref'] == x['_id']
    e, _, _ = CL.call('mdj_clase_crear', archivo=c, paquete=PAQ, nombre='SinVista2', estereotipo='entity', **F)
    e, r5, _ = CL.call('mdj_asociacion_editar', archivo=c, asociacion=aid, extremo=2, clase='SinVista2', **F); assert not e and r5.get('vistas_quitadas_en'), r5
    assert vid not in M.Doc(c).ids
    valida(c)
    e, r6, _ = CL.call('mdj_asociacion_editar', archivo=c, asociacion=ENT[0]['_id'], extremo=1, mult='1', **F); assert e and 'no es una asociacion' in r6


@prueba('W07 borrar: clase con vistas y relaciones no deja nada colgando; si es tipo de lifeline vacia el tipo')
def _():
    c = copia(); d = M.Doc(c)
    rel = [o for o in d.ids.values() if o and o['_type'] == 'UMLAssociation' and ENT[0]['_id'] in (o['end1']['reference']['$ref'], o['end2']['reference']['$ref'])]
    e, r, _ = CL.call('mdj_borrar', archivo=c, elemento=ENT[0]['_id'], **F); assert not e, r
    d = M.Doc(c)
    assert ENT[0]['_id'] not in d.ids and all(o['_id'] not in d.ids for o in rel)
    tipos = r['tipos_vaciados']
    usado_en_secuencia = any(isinstance(a.get('type'), dict) and a['type']['$ref'] == ENT[0]['_id']
                             for o in DOC0.ids.values() if o and o['_type'] == 'UMLCollaboration' for a in o.get('attributes', []))
    assert bool(tipos) == usado_en_secuencia, (tipos, usado_en_secuencia)
    valida(c)
    # borrar una asociacion sola
    c2 = copia(); d2 = M.Doc(c2)
    asoc = next(o for o in d2.ids.values() if o and o['_type'] == 'UMLAssociation' and d2.views_of(o['_id']))
    nv = len(d2.views_of(asoc['_id']))
    e, r2, _ = CL.call('mdj_borrar', archivo=c2, elemento=asoc['_id'], **F); assert not e and r2['vistas_borradas'] == nv, r2
    valida(c2)


@prueba('W08 vista_mover: posicion y ancho; los atributos se mueven con la caja')
def _():
    c = copia()
    e, r, _ = CL.call('mdj_vista_mover', archivo=c, diagrama=DCLASES, elemento=ENT[0]['_id'], x=111, y=222, ancho=177, **F); assert not e, r
    d = M.Doc(c); v = d.views_of(ENT[0]['_id'], d.diagram(DCLASES))[0][1]
    assert (v['left'], v['top'], v['width']) == (111, 222, 177)
    acv = [s for s in v['subViews'] if s['_type'] == 'UMLAttributeCompartmentView'][0]
    for i, s in enumerate(acv['subViews']):
        assert s['top'] == 222 + 72 + 15 * i and s['left'] == 116
    lab = M._name_label(v); assert lab['width'] == 177 - 9
    e, r2, _ = CL.call('mdj_vista_mover', archivo=c, diagrama=DCLASES, elemento=v['_id'], y=250, **F); assert not e and r2['y'] == 250 and r2['x'] == 111
    valida(c)


@prueba('W09 linea_ruta: con puntos alineados al centro los tramos salen rectos; linea desconocida falla')
def _():
    c = copia(); a, b = ENT[0], ENT[1]
    e, r, _ = CL.call('mdj_asociacion_crear', archivo=c, desde=a['_id'], hacia=b['_id'], diagrama=DCLASES, **F); assert not e
    d = M.Doc(c); dg = d.diagram(DCLASES)
    va = d.views_of(a['_id'], dg)[0][1]; vb = d.views_of(b['_id'], dg)[0][1]
    ca, cb = M.centro(va), M.centro(vb)
    medios = [[ca[0], ca[1] + 400], [cb[0], ca[1] + 400]]
    e, r2, _ = CL.call('mdj_linea_ruta', archivo=c, diagrama=DCLASES, linea=r['vista'], puntos=medios, **F); assert not e, r2
    P = [tuple(map(float, p.split(':'))) for p in r2['puntos'].split(';')]
    assert abs(P[0][0] - P[1][0]) <= 1 and abs(P[-1][0] - P[-2][0]) <= 1, P
    e, r3, _ = CL.call('mdj_linea_ruta', archivo=c, diagrama=DCLASES, linea=r['asociacion'], puntos=[], **F); assert not e
    e, r4, _ = CL.call('mdj_linea_ruta', archivo=c, diagrama=DCLASES, linea='noexiste', puntos=[], **F); assert e


@prueba('W10 linea_etiqueta cambia alpha y distance; etiqueta invalida se rechaza')
def _():
    c = copia(); d = M.Doc(c)
    v = next(x for x in d.diagram(DCLASES)['ownedViews'] if x['_type'] == 'UMLAssociationView')
    e, r, _ = CL.call('mdj_linea_etiqueta', archivo=c, linea=v['_id'], etiqueta='tailMultiplicityLabel', alpha=0.9, distancia=33, **F)
    assert not e and r['alpha'] == 0.9 and r['distance'] == 33
    e, r, _ = CL.call('mdj_linea_etiqueta', archivo=c, linea=v['_id'], etiqueta='otraCosa', **F); assert e


@prueba('W11 nota: alto automatico crece con el texto; editar por id; id inexistente falla')
def _():
    c = copia()
    e, r1, _ = CL.call('mdj_nota', archivo=c, diagrama=DCLASES, texto='corta', x=10, y=10, ancho=200, **F)
    e2, r2, _ = CL.call('mdj_nota', archivo=c, diagrama=DCLASES, texto='muy larga ' * 30, x=10, y=100, ancho=200, **F)
    assert not e and not e2 and r2['alto'] > r1['alto'] + 40
    e, r3, _ = CL.call('mdj_nota', archivo=c, diagrama=DCLASES, texto='editada', x=20, y=20, ancho=150, vista=r1['vista'], **F)
    assert not e and M.Doc(c).get(r1['vista'])['text'] == 'editada'
    e, r4, _ = CL.call('mdj_nota', archivo=c, diagrama=DCLASES, texto='x', x=1, y=1, ancho=100, vista='noexiste', **F); assert e


@prueba('W12 renombrar actualiza el nombre en todas las vistas; documentacion se guarda')
def _():
    c = copia()
    e, r, _ = CL.call('mdj_renombrar', archivo=c, elemento=ENT[1]['_id'], nuevo_nombre='NuevoNombreX', **F); assert not e and r['vistas_actualizadas'] >= 1
    d = M.Doc(c)
    for dg, v in d.views_of(ENT[1]['_id']):
        lab = M._name_label(v)
        if lab:
            assert lab['text'].endswith('NuevoNombreX')
    e, _, _ = CL.call('mdj_documentacion', archivo=c, elemento='NuevoNombreX', texto='resp', **F); assert not e
    assert M.Doc(c).find('NuevoNombreX')['documentation'] == 'resp'


@prueba('W13 salida: el original no se toca y el resultado queda en el otro archivo con respaldo solo si existia')
def _():
    c = copia(); h = md5(c); out = os.path.join(TMP, 'salida_w13.mdj')
    e, r, _ = CL.call('mdj_documentacion', archivo=c, elemento=ENT[0]['_id'], texto='zz', salida=out, **F); assert not e
    assert md5(c) == h and os.path.exists(out) and r['respaldo'] is None
    assert M.Doc(out).get(ENT[0]['_id'])['documentation'] == 'zz'
    e, r2, _ = CL.call('mdj_documentacion', archivo=c, elemento=ENT[0]['_id'], texto='yy', salida=out, **F)
    assert r2['respaldo'] and md5(r2['respaldo']) != md5(out)


@prueba('W14 toda herramienta de escritura se niega si StarUML esta abierto (sin forzar)')
def _():
    orig = M.staruml_gui_abierto
    M.staruml_gui_abierto = lambda: True
    try:
        c = copia(); h = md5(c); d = M.Doc(c)
        M.set_atributos(d, d.get(ENT[0]['_id']), ['a'])
        try:
            d.save(); raise AssertionError('no se nego')
        except M.MdjError:
            pass
        assert md5(c) == h
    finally:
        M.staruml_gui_abierto = orig
    import server as S
    escriben = [t['name'] for t in S.TOOLS if not t['annotations'].get('readOnlyHint') and t['name'] not in ('staruml_exportar', 'mdj_respaldar')]
    for t in S.TOOLS:
        if t['name'] in escriben:
            assert 'forzar' in t['inputSchema']['properties'] and 'salida' in t['inputSchema']['properties'], t['name']
    assert len(escriben) >= 12

# ===========================================================================
# GENERADOR DE SECUENCIAS
# ===========================================================================
SEC = M.secuencia(DOC0, DSEC)


def spec_actual():
    idx = {n: f'l{i}' for i, n in enumerate(SEC['lifelines'])}
    lls = [{'clave': f'l{i}', 'tipo': n} for i, n in enumerate(SEC['lifelines'])]
    msgs, ultimo, f = [], None, 0
    for m in SEC['mensajes']:
        if m['tipos'].startswith('actor->') and m['a'] != ultimo:
            f += 1; ultimo = m['a']
        msgs.append({'de': idx[m['de']], 'a': idx[m['a']], 'nombre': m['nombre'], 'reply': m['reply'], 'flujo': f'F{f}'})
    return lls, msgs


@prueba('S01 rehace la secuencia real: mismos mensajes, OOSE limpio, reglas de alturas, espaciados y marco')
def _():
    c = copia(); lls, msgs = spec_actual()
    e, r, _ = CL.call('mdj_secuencia_generar', archivo=c, diagrama=DSEC, lifelines=lls, mensajes=msgs, **F); assert not e, r
    assert not r['oose']['problemas'] and not r['oose']['avisos'], r['oose']
    d = M.Doc(c); dg = d.diagram(DSEC)
    s2 = M.secuencia(d, DSEC)
    assert [(m['de'], m['a'], m['nombre'], m['reply']) for m in s2['mensajes']] == [(m['de'], m['a'], m['nombre'], m['reply']) for m in SEC['mensajes']]
    ys = [int(float(v['points'].split(';')[0].split(':')[1])) for v in sorted(
        [v for v in dg['ownedViews'] if v['_type'] == 'UMLSeqMessageView'],
        key=lambda v: [m['_id'] for m in M.interaction_of(d, dg)['messages']].index(v['model']['$ref']))]
    fin = ys[-1] + 60
    for v in dg['ownedViews']:
        if v['_type'] == 'UMLSeqLifelineView':
            lp = [s for s in v['subViews'] if s['_type'] == 'UMLLinePartView'][0]
            assert v['height'] == fin - 40 and lp['top'] == 106 and lp['height'] == v['height'] - 66
        if v['_type'] == 'UMLSeqMessageView':
            t = [s['_type'] for s in v['subViews']]
            assert t.count('EdgeLabelView') == 3 and t.count('UMLActivationView') == 1
    fr = [v for v in dg['ownedViews'] if v['_type'] == 'UMLFrameView'][0]
    assert fr['top'] + fr['height'] >= fin and fr['left'] + fr['width'] >= max(v['left'] + v['width'] for v in dg['ownedViews'] if v['_type'] == 'UMLSeqLifelineView')
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    assert min(gaps) >= 29 and len(set(gaps)) > 5, gaps
    ex = R.exportar(c, os.path.join(TMP, 'exp_s01'), DSEC)
    rv = R.revisar_svg(ex['archivos'][0], c, DSEC); assert rv['n_problemas'] == 0, rv['problemas'][:5]
    valida(c)


@prueba('S02 la misma especificacion y semilla da el mismo acomodo (solo cambian los ids)')
def _():
    lls, msgs = spec_actual(); c1, c2 = copia(), copia()
    CL.call('mdj_secuencia_generar', archivo=c1, diagrama=DSEC, lifelines=lls, mensajes=msgs, **F)
    CL.call('mdj_secuencia_generar', archivo=c2, diagrama=DSEC, lifelines=lls, mensajes=msgs, **F)
    geo = lambda f: [(v['_type'], v.get('points'), v.get('left'), v.get('top'), v.get('height')) for v in M.Doc(f).diagram(DSEC)['ownedViews']]
    assert geo(c1) == geo(c2)


@prueba('S03 secuencia nueva en un diagrama vacio: crea roles y lifelines, queda valida y se exporta limpia')
def _():
    c = copia(); d = M.Doc(c)
    vacio = next((g for g in d.diagrams() if g['_type'] == 'UMLSequenceDiagram' and len(g.get('ownedViews', [])) <= 1
                  and d.ids.get(d.parent.get(g['_id']), {}).get('_type') == 'UMLInteraction'
                  and d.ids.get(d.parent.get(d.parent.get(g['_id'])), {}).get('_type') == 'UMLCollaboration'), None)
    if vacio is None:
        print('      (no hay un diagrama de secuencia vacio dentro de una colaboracion; se omite)'); return
    actor = next(o for o in d.ids.values() if o and o['_type'] == 'UMLActor')
    ctl = next(o for o in d.ids.values() if o and o['_type'] == 'UMLClass' and d.kind(o) == 'control')
    lls = [{'clave': 'a', 'tipo': actor['_id']}, {'clave': 'b', 'tipo': BND[0]['_id']}, {'clave': 'c', 'tipo': ctl['_id']}, {'clave': 'e', 'tipo': ENT[0]['_id']}]
    msgs = [{'de': 'a', 'a': 'b', 'nombre': 'pedir(x)', 'flujo': 'F1'}, {'de': 'b', 'a': 'c', 'nombre': 'procesar(x)', 'flujo': 'F1'},
            {'de': 'c', 'a': 'e', 'nombre': 'consultarDato(x)', 'flujo': 'F1'}, {'de': 'e', 'a': 'c', 'nombre': 'dato', 'reply': True, 'flujo': 'F1'},
            {'de': 'c', 'a': 'b', 'nombre': 'mostrarDato(dato)', 'flujo': 'F1'}]
    e, r, _ = CL.call('mdj_secuencia_generar', archivo=c, diagrama=vacio['_id'], lifelines=lls, mensajes=msgs, **F); assert not e, r
    assert r['mensajes'] == 5 and r['lifelines'] == 4 and not r['oose']['problemas'], r
    valida(c)
    ex = R.exportar(c, os.path.join(TMP, 'exp_s03'), vacio['_id'])
    rv = R.revisar_svg(ex['archivos'][0], c, vacio['_id']); assert rv['n_problemas'] == 0, rv['problemas'][:5]


@prueba('S04 errores del generador: sin mensajes, clave desconocida, claves repetidas, auto-mensaje, tipo inexistente, diagrama no de secuencia')
def _():
    c = copia(); h = md5(c); lls, msgs = spec_actual()
    casos = [dict(lifelines=lls, mensajes=[]),
             dict(lifelines=lls, mensajes=[{'de': 'l0', 'a': 'zz', 'nombre': 'x'}]),
             dict(lifelines=lls + [lls[0]], mensajes=msgs),
             dict(lifelines=lls, mensajes=[{'de': 'l0', 'a': 'l0', 'nombre': 'x'}]),
             dict(lifelines=[{'clave': 'q', 'tipo': 'NoExisteTipo'}], mensajes=[{'de': 'q', 'a': 'q', 'nombre': 'x'}])]
    for k in casos:
        e, r, _ = CL.call('mdj_secuencia_generar', archivo=c, diagrama=DSEC, **k, **F); assert e, (k, r)
    e, r, _ = CL.call('mdj_secuencia_generar', archivo=c, diagrama=DCLASES, lifelines=lls, mensajes=msgs, **F); assert e and 'secuencia' in r
    assert md5(c) == h


@prueba('S05 roles que usa otra interaccion de la misma colaboracion no se borran')
def _():
    c = copia(); d = M.Doc(c)
    dg = d.diagram(DSEC); it = M.interaction_of(d, dg); col = d.ids[d.parent[it['_id']]]
    otra = next((o for o in col.get('ownedElements', []) if o['_type'] == 'UMLInteraction' and o['_id'] != it['_id']), None)
    if otra is None:
        otra = {'_type': 'UMLInteraction', '_id': d.new_id(), '_parent': M.ref(col['_id']), 'name': 'otra'}
        col.setdefault('ownedElements', []).append(otra)
    ll = it['participants'][-1]; rol = ll['represent']['$ref']
    otra.setdefault('participants', []).append({'_type': 'UMLLifeline', '_id': d.new_id(), '_parent': M.ref(otra['_id']),
                                                 'represent': M.ref(rol), 'isMultiInstance': False})
    d.save(force=True, backup=False)
    lls, msgs = spec_actual()
    quitar = lls[-1]['clave']
    lls2 = [l for l in lls if l['clave'] != quitar]
    msgs2 = [m for m in msgs if quitar not in (m['de'], m['a'])]
    e, r, _ = CL.call('mdj_secuencia_generar', archivo=c, diagrama=DSEC, lifelines=lls2, mensajes=msgs2, **F); assert not e, r
    d = M.Doc(c); assert rol in d.ids, 'se borro un rol que usa otra interaccion'
    valida(c)

# ===========================================================================
# RENDER
# ===========================================================================


@prueba('R01 exportar: un diagrama, todos, png y diagrama inexistente')
def _():
    e, r, _ = CL.call('staruml_exportar', archivo=MDJ, carpeta=os.path.join(TMP, 'r01'), diagrama=DCLASES); assert not e and r['exportados'] == 1
    e, r, _ = CL.call('staruml_exportar', archivo=MDJ, carpeta=os.path.join(TMP, 'r01_todos')); assert not e and r['exportados'] == len(DOC0.diagrams()), r
    e, r, _ = CL.call('staruml_exportar', archivo=MDJ, carpeta=os.path.join(TMP, 'r01_png'), diagrama=DCLASES, formato='png')
    assert not e and r['archivos'] and open(r['archivos'][0], 'rb').read(8) == b'\x89PNG\r\n\x1a\n'
    e, r, _ = CL.call('staruml_exportar', archivo=MDJ, carpeta=os.path.join(TMP, 'r01'), diagrama='NoHay'); assert e


@prueba('R02 svg_revisar corre en todos los SVG exportados; clases y secuencia principales sin problemas')
def _():
    carpeta = os.path.join(TMP, 'r01_todos')
    d = M.Doc(MDJ)
    for g in d.diagrams():
        f = os.path.join(carpeta, g['name'] + '.svg')
        if os.path.exists(f) and len([x for x in d.diagrams() if x['name'] == g['name']]) == 1:
            rv = R.revisar_svg(f, MDJ, g['_id'])
            if g['name'] in (DCLASES, DSEC):
                assert rv['n_problemas'] == 0, (g['name'], rv['problemas'][:5])


@prueba('R03 recortar: todo, una zona, rutas con espacios, salida con espacios y devuelve PNG')
def _():
    base = os.path.join(TMP, 'r01', DCLASES + '.svg')
    esp = os.path.join(TMP, 'carpeta con espacios'); os.makedirs(esp, exist_ok=True)
    svg = os.path.join(esp, 'diagrama con espacios.svg'); shutil.copy2(base, svg)
    r = R.recortar(svg, salida=os.path.join(esp, 'salida todo.png'), max_lado=900)
    assert r['png'][:8] == b'\x89PNG\r\n\x1a\n' and os.path.exists(os.path.join(esp, 'salida todo.png'))
    r2 = R.recortar(svg, 100, 50, 400, 300)
    assert r2['png'][:8] == b'\x89PNG\r\n\x1a\n' and r2['region'] == [100, 50, 400, 300]
    e, d, res = CL.call('svg_recortar', svg=svg, x=0, y=0, ancho=300, alto=200)
    img = [x for x in res['content'] if x['type'] == 'image']
    assert not e and img and base64.b64decode(img[0]['data'])[:4] == b'\x89PNG'


@prueba('R04 dos recortes al mismo tiempo no se estorban')
def _():
    svg = os.path.join(TMP, 'r01', DCLASES + '.svg')
    out, err = [], []

    def uno(i):
        try:
            out.append(R.recortar(svg, 50 * i, 0, 500, 400)['png'][:8])
        except Exception as e:
            err.append(e)
    hs = [threading.Thread(target=uno, args=(i,)) for i in range(3)]
    [h.start() for h in hs]; [h.join() for h in hs]
    assert not err and len(out) == 3 and all(o == b'\x89PNG\r\n\x1a\n' for o in out), err


@prueba('Z01 el archivo original nunca se modifico')
def _():
    assert md5(MDJ) == MD5_ORIGINAL


stderr = CL.cerrar()
ok = sum(1 for r in resultados if r[1]); mal = [r for r in resultados if not r[1]]
print(f'\n{ok}/{len(resultados)} pruebas pasaron en {sum(r[3] for r in resultados):.0f}s')
for n, _, det, _ in mal:
    print(' FALLA', n, '->', det[:600])
if stderr.strip():
    print('\nstderr del servidor (ultimas lineas):\n' + '\n'.join(stderr.strip().splitlines()[-12:]))
print('temporales:', TMP)
sys.exit(1 if mal else 0)
