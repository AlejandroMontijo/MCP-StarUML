# Prueba de punta a punta: arranca server.py, habla MCP por stdio y usa todas las herramientas.
# Las de escritura trabajan sobre copias temporales; el .mdj que se pasa solo se lee.
#   python3 pruebas/probar_servidor.py "/ruta/al/archivo.mdj" [diagrama_clases] [diagrama_secuencia]
import json
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(os.path.dirname(AQUI), 'server.py')
MDJ = os.path.abspath(sys.argv[1])
DC = sys.argv[2] if len(sys.argv) > 2 else 'cu_1'
DS = sys.argv[3] if len(sys.argv) > 3 else 'cu_1_FB'
TMP = tempfile.mkdtemp(prefix='prueba_mcp_')

env = dict(os.environ, STARUML_MCP_BACKUP_DIR=os.path.join(TMP, 'respaldos'))   # los respaldos de prueba no ensucian el MCP
p = subprocess.Popen([sys.executable, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
nid = [0]
fallas = []


def rpc(method, params=None, notif=False):
    msg = {'jsonrpc': '2.0', 'method': method}
    if params is not None:
        msg['params'] = params
    if not notif:
        nid[0] += 1; msg['id'] = nid[0]
    p.stdin.write(json.dumps(msg) + '\n'); p.stdin.flush()
    if notif:
        return None
    r = json.loads(p.stdout.readline())
    assert r.get('id') == nid[0], r
    return r


def call(name, **args):
    r = rpc('tools/call', {'name': name, 'arguments': args})
    if 'error' in r:
        raise AssertionError(f'{name}: {r["error"]}')
    res = r['result']
    txt = res['content'][0]['text']
    try:
        data = json.loads(txt)
    except Exception:
        data = txt
    return res.get('isError'), data, res


def check(cond, texto):
    print(('OK   ' if cond else 'FALLA') + ' ' + texto)
    if not cond:
        fallas.append(texto)


r = rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'prueba', 'version': '1'}})
check(r['result']['serverInfo']['name'] == 'staruml', 'initialize')
rpc('notifications/initialized', notif=True)
tools = rpc('tools/list')['result']['tools']
print('herramientas:', len(tools), [t['name'] for t in tools])
check(len(tools) >= 20, 'tools/list')
check(rpc('ping')['result'] == {}, 'ping')

err, est, _ = call('staruml_estado'); print('estado:', est)
err, reg, _ = call('staruml_reglas'); check(not err and 'OOSE' in reg, 'staruml_reglas')
err, res, _ = call('mdj_resumen', archivo=MDJ); check(not err and res['diagramas'], f'mdj_resumen ({len(res["diagramas"])} diagramas)')
err, mod, _ = call('mdj_modelo', archivo=MDJ); check(not err and mod['clases'], f'mdj_modelo ({len(mod["clases"])} clases, {len(mod["asociaciones"])} asociaciones)')
err, sec, _ = call('mdj_secuencia', archivo=MDJ, diagrama=DS); check(not err and sec['mensajes'], f'mdj_secuencia ({len(sec["mensajes"])} mensajes)')
err, geo, _ = call('mdj_geometria', archivo=MDJ, diagrama=DC); check(not err and geo['cajas'], 'mdj_geometria')
err, bus, _ = call('mdj_buscar', archivo=MDJ, texto='Cotiz'); check(not err and bus, 'mdj_buscar')
err, val, _ = call('mdj_validar', archivo=MDJ); check(not err and val['n_duplicados'] == 0 and val['n_colgantes'] == 0, f'mdj_validar {val.get("oose")}')
err, dif, _ = call('mdj_diff', archivo_a=MDJ, archivo_b=MDJ); check(not err and not dif['cambios'], 'mdj_diff (mismo archivo)')
err, _, _ = call('mdj_modelo', archivo='/no/existe.mdj'); check(err, 'error controlado con archivo inexistente')

# exportar, revisar y recortar
err, ex, _ = call('staruml_exportar', archivo=MDJ, carpeta=os.path.join(TMP, 'exp'), diagrama=DC)
check(not err and ex['archivos'], f'staruml_exportar {ex if err else ex["archivos"]}')
svg = ex['archivos'][0] if not err and ex['archivos'] else None
if svg:
    err, rv, _ = call('svg_revisar', svg=svg, archivo=MDJ, diagrama=DC); check(not err, f'svg_revisar ({rv["n_problemas"]} problemas)')
    err, rc, raw = call('svg_recortar', svg=svg, x=0, y=0, ancho=600, alto=400, salida=os.path.join(TMP, 'recorte.png'))
    img = [c for c in raw['content'] if c['type'] == 'image']
    check(not err and img and len(img[0]['data']) > 1000 and os.path.exists(os.path.join(TMP, 'recorte.png')), 'svg_recortar (devuelve imagen)')

# escritura: sobre una copia
copia = os.path.join(TMP, 'copia.mdj'); shutil.copy2(MDJ, copia)
abierto = est['staruml_abierto']
if abierto:
    err, msg, _ = call('mdj_documentacion', archivo=copia, elemento=mod['clases'][0]['id'], texto='x')
    check(err and 'abierto' in str(msg), 'se niega a escribir con StarUML abierto')
F = {'forzar': True}   # la copia temporal no esta cargada en StarUML
paquete = [c for c in mod['clases'] if c['estereotipo'] == 'entity'][0]['paquete']
err, r1, _ = call('mdj_clase_crear', archivo=copia, paquete=paquete, nombre='ClasePrueba', estereotipo='entity',
                  atributos=['idPrueba', 'nombre'], documentacion='Clase de prueba.', **F)
check(not err and r1['validacion']['n_colgantes'] == 0, 'mdj_clase_crear')
err, r2, _ = call('mdj_atributos', archivo=copia, clase='ClasePrueba', atributos=['idPrueba', 'descripcion', 'monto'], **F)
check(not err and r2['quitados'] == ['nombre'], 'mdj_atributos')
err, r3, _ = call('mdj_vista_agregar', archivo=copia, diagrama=DC, elemento='ClasePrueba', x=40, y=40, **F)
check(not err, f'mdj_vista_agregar {r3 if err else ""}')
ent = [c for c in mod['clases'] if c['estereotipo'] == 'entity' and c['nombre'] != 'ClasePrueba'][0]['nombre']
err, r4, _ = call('mdj_asociacion_crear', archivo=copia, desde='ClasePrueba', hacia=ent, mult_desde='1', mult_hacia='0..*',
                  rol_hacia='prueba', diagrama=DC, puntos=[[120, 300]], **F)
check(not err and r4.get('vista'), f'mdj_asociacion_crear {r4 if err else r4["puntos"]}')
aid = r4.get('asociacion')
err, r5, _ = call('mdj_asociacion_editar', archivo=copia, asociacion=aid, extremo=2, mult='1..*', rol='', **F)
check(not err, 'mdj_asociacion_editar')
err, r6, _ = call('mdj_vista_mover', archivo=copia, diagrama=DC, elemento='ClasePrueba', x=60, y=50, ancho=150, **F)
check(not err and r6['ancho'] == 150, 'mdj_vista_mover')
err, r7, _ = call('mdj_linea_ruta', archivo=copia, diagrama=DC, linea=r4.get('vista', ''), puntos=[[135, 320], [300, 320]], **F)
check(not err, f'mdj_linea_ruta {r7}')
err, r8, _ = call('mdj_linea_etiqueta', archivo=copia, linea=r4.get('vista', ''), etiqueta='headMultiplicityLabel', alpha=-0.52, distancia=25, **F)
check(not err, 'mdj_linea_etiqueta')
err, r9, _ = call('mdj_nota', archivo=copia, diagrama=DC, texto='Nota de prueba para ver que el alto se calcula solo con el texto.', x=40, y=500, ancho=200, **F)
check(not err and r9['alto'] > 20, f'mdj_nota (alto {r9.get("alto")})')
err, r10, _ = call('mdj_renombrar', archivo=copia, elemento='ClasePrueba', nuevo_nombre='ClasePrueba2', **F)
check(not err and r10['vistas_actualizadas'] >= 1, 'mdj_renombrar')
err, r11, _ = call('mdj_documentacion', archivo=copia, elemento='ClasePrueba2', texto='Otra responsabilidad.', **F)
check(not err, 'mdj_documentacion')
err, v1, _ = call('mdj_validar', archivo=copia); check(v1['n_colgantes'] == 0 and v1['n_duplicados'] == 0 and v1['n_parent_mismatch'] == 0, 'copia valida despues de editar')
err, r12, _ = call('mdj_borrar', archivo=copia, elemento='ClasePrueba2', **F)
check(not err and r12['vistas_borradas'] >= 2, f'mdj_borrar {r12}')
err, v2, _ = call('mdj_validar', archivo=copia); check(v2['n_colgantes'] == 0, 'copia valida despues de borrar')
err, r13, _ = call('mdj_respaldar', archivo=copia, carpeta=os.path.join(TMP, 'resp')); check(not err and os.path.exists(r13['respaldo']), 'mdj_respaldar')

# generador de secuencia: rehace la secuencia actual desde su propia especificacion
copia2 = os.path.join(TMP, 'copia2.mdj'); shutil.copy2(MDJ, copia2)
lls = [{'clave': f'l{i}', 'tipo': n} for i, n in enumerate(sec['lifelines'])]
idx = {n: f'l{i}' for i, n in enumerate(sec['lifelines'])}
flujo, cuenta_actor = 'F0', 0
msgs = []
for m in sec['mensajes']:
    if m['tipos'].startswith('actor->') and (not msgs or msgs[-1]['de'] != idx[m['de']] or True):
        pass
    msgs.append({'de': idx[m['de']], 'a': idx[m['a']], 'nombre': m['nombre'], 'reply': m['reply']})
# flujos: cada vez que el actor le habla a una boundary distinta de la anterior
ultimo_bc, f = None, 0
for m, orig in zip(msgs, sec['mensajes']):
    if orig['tipos'].startswith('actor->'):
        if orig['a'] != ultimo_bc:
            f += 1; ultimo_bc = orig['a']
    m['flujo'] = f'F{f}'
err, rg, _ = call('mdj_secuencia_generar', archivo=copia2, diagrama=DS, lifelines=lls, mensajes=msgs, **F)
check(not err and rg['mensajes'] == len(msgs) and rg['validacion']['n_colgantes'] == 0, f'mdj_secuencia_generar {rg if err else {k: rg[k] for k in ("mensajes", "lifelines", "alto", "ancho", "ajustes")}}')
if not err:
    check(not rg['oose']['problemas'], f'secuencia generada sin problemas OOSE {rg["oose"]}')
    err, sec2, _ = call('mdj_secuencia', archivo=copia2, diagrama=DS)
    check([m['nombre'] for m in sec2['mensajes']] == [m['nombre'] for m in sec['mensajes']], 'mismos mensajes y orden')
    err, ex2, _ = call('staruml_exportar', archivo=copia2, carpeta=os.path.join(TMP, 'exp2'), diagrama=DS)
    if not err and ex2['archivos']:
        err, rv2, _ = call('svg_revisar', svg=ex2['archivos'][0], archivo=copia2, diagrama=DS)
        check(not err and rv2['n_problemas'] == 0, f'secuencia generada: svg_revisar {rv2.get("problemas", [])[:5]}')

# deteccion de la aplicacion abierta y negativa a escribir (sin abrir StarUML)
sys.path.insert(0, os.path.dirname(AQUI))
import re as _re
import staruml_mdj as M
gui = '/Users/x/Applications/StarUML.app/Contents/MacOS/StarUML'
cli = '/Users/x/Applications/StarUML.app/Contents/MacOS/StarUML image /tmp/a.mdj -f svg -s @UMLDiagram -o /tmp/x.svg'
helper = '/Users/x/Applications/StarUML.app/Contents/Frameworks/StarUML Helper.app/Contents/MacOS/StarUML Helper --type=gpu'
pat = r'StarUML\.app/Contents/MacOS/StarUML(\s+-psn\S*)?\s*$'
check(bool(_re.search(pat, gui)) and not _re.search(pat, cli) and not _re.search(pat, helper), 'regla de deteccion: app si, CLI y helpers no')
original = M.staruml_gui_abierto
M.staruml_gui_abierto = lambda: True
try:
    d = M.Doc(copia)
    try:
        d.save(os.path.join(TMP, 'no_debe_existir.mdj'))
        check(False, 'save se niega con StarUML abierto')
    except M.MdjError as e:
        check('abierto' in str(e) and not os.path.exists(os.path.join(TMP, 'no_debe_existir.mdj')), 'save se niega con StarUML abierto')
finally:
    M.staruml_gui_abierto = original

p.stdin.close(); p.wait(10)
err_txt = p.stderr.read()
if err_txt.strip():
    print('stderr del servidor:\n' + err_txt[-2000:])
print('\nFALLAS:', len(fallas), fallas)
print('temporales en', TMP)
sys.exit(1 if fallas else 0)
