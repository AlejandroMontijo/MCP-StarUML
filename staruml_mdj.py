# Biblioteca para leer, validar y editar archivos .mdj de StarUML sin abrir la aplicacion.
# Reglas de trabajo que respeta (ver reglas.md):
#  - Guarda siempre con json.dump(d, f, ensure_ascii=False, indent='\t'), igual que StarUML.
#  - Respalda antes de escribir y no escribe si la aplicacion de StarUML esta abierta (o si no se puede saber).
#  - No escribe un cambio que deje el archivo peor de lo que estaba: ids duplicados, referencias colgantes,
#    _parent incoherente o numeros NaN/infinito (StarUML ya no lo abriria).
#  - IDs con el mismo formato de StarUML: 4 bytes cero + 6 bytes de timestamp en ms + 4 aleatorios, en base64.
#  - StarUML recalcula el primer y ultimo punto de cada linea: queda donde la recta del centro de la caja
#    hacia el punto vecino cruza el borde. Aqui se calcula igual (junction) para que el archivo quede limpio.
import base64
import copy
import datetime
import json
import math
import os
import random
import re
import shutil
import subprocess
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.environ.get('STARUML_MCP_BACKUP_DIR', os.path.join(HERE, 'respaldos'))

VIEW_TYPES_BOX = ('UMLClassView', 'UMLActorView', 'UMLNoteView', 'UMLUseCaseView', 'UMLInterfaceView',
                  'UMLUseCaseSubjectView', 'UMLPackageView', 'UMLComponentView')
EDGE_TYPES = ('UMLAssociationView', 'UMLGeneralizationView', 'UMLDependencyView', 'UMLRealizationView',
              'UMLNoteLinkView', 'UMLInterfaceRealizationView', 'UMLIncludeView', 'UMLExtendView')


class MdjError(Exception):
    pass


def ref(i):
    return {'$ref': i}


# ---------------------------------------------------------------------------
# Estado de la aplicacion
# ---------------------------------------------------------------------------

def _programas_windows(*partes):
    bases = [os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')]
    if os.environ.get('LOCALAPPDATA'):
        bases += [os.environ['LOCALAPPDATA'], os.path.join(os.environ['LOCALAPPDATA'], 'Programs')]
    return [os.path.join(b, *partes) for b in bases if b]


def _buscar_ejecutable(variable, rutas, nombres):
    """La variable de entorno manda (si apunta a algo que no existe, no se adivina otra cosa); luego las rutas tipicas
    de cada sistema y al final el PATH."""
    env = os.environ.get(variable)
    if env:
        return env if os.path.exists(env) else None
    for p in rutas:
        if os.path.exists(p):
            return p
    return next((w for w in map(shutil.which, nombres) if w), None)


def staruml_cli():
    return _buscar_ejecutable('STARUML_MCP_STARUML_BIN',
                              [os.path.expanduser('~/Applications/StarUML.app/Contents/MacOS/StarUML'),
                               '/Applications/StarUML.app/Contents/MacOS/StarUML', '/opt/StarUML/staruml',
                               '/usr/lib/staruml/staruml'] + _programas_windows('StarUML', 'StarUML.exe'),
                              ('staruml', 'StarUML'))


def chrome_bin():
    return _buscar_ejecutable('STARUML_MCP_CHROME_BIN',
                              ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                               os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
                               '/Applications/Chromium.app/Contents/MacOS/Chromium',
                               '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']
                              + _programas_windows('Google', 'Chrome', 'Application', 'chrome.exe')
                              + _programas_windows('Microsoft', 'Edge', 'Application', 'msedge.exe'),
                              ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome',
                               'msedge', 'microsoft-edge'))


def es_gui_staruml(cmd):
    """True si la linea de comando es la aplicacion de StarUML: macOS (StarUML.app), Linux (/opt/StarUML/staruml,
    AppImage). No cuentan las exportaciones por CLI (staruml image ...) ni los procesos auxiliares de Electron."""
    m = re.search(r'(StarUML\.app/Contents/MacOS/StarUML|/staruml|StarUML[^/]*\.AppImage)(?=\s|$)(.*)$', cmd, re.I)
    if not m:
        return False
    args = m.group(2).split()
    return not args or (args[0].lower() not in ('image', 'html', 'ejs', 'exec')
                        and not any(a.startswith('--type=') for a in args))


def staruml_gui_abierto():
    """True si la aplicacion de StarUML (no una exportacion por CLI) esta corriendo, False si no, y None si no se
    pudo averiguar (sin ps ni tasklist). Quien escribe trata None como abierto."""
    try:
        if os.name == 'nt':  # tasklist no da la linea de comando: cualquier StarUML.exe cuenta como abierto
            r = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=10)
            if r.returncode:
                return None
            return any(l.lower().startswith('"staruml.exe"') for l in r.stdout.splitlines())
        # -ww: sin eso ps recorta la linea al ancho de la terminal (80 columnas sin terminal) y una ruta larga
        # (~/Applications con un usuario de nombre largo) deja de reconocerse
        r = subprocess.run(['ps', '-Aww', '-o', 'pid=,command='], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if r.returncode:
        return None
    for line in r.stdout.splitlines():
        partes = line.strip().split(None, 1)
        if len(partes) > 1 and es_gui_staruml(partes[1]):
            return True
    return False


# ---------------------------------------------------------------------------
# Documento
# ---------------------------------------------------------------------------

class Doc:
    def __init__(self, path):
        self.path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(self.path):
            raise MdjError(f'No existe el archivo: {self.path}')
        with open(self.path, encoding='utf-8') as f:
            self._texto = f.read()  # estado al cargar: al guardar se compara contra el para no empeorar el archivo
        try:
            self.d = json.loads(self._texto)
        except ValueError as e:
            raise MdjError(f'{self.path} no es un .mdj valido (JSON mal formado: {e})') from None
        if not isinstance(self.d, dict):
            raise MdjError(f'{self.path} no es un .mdj valido (la raiz no es un objeto)')
        self.reindex()
        self._ts = int(time.time() * 1000) - 600000
        self._rnd = random.Random()

    # --- indices ---
    def reindex(self):
        self.ids, self.parent = {}, {}

        def walk(o, p=None):
            if isinstance(o, dict):
                if '_id' in o:
                    self.ids[o['_id']] = o
                    if p is not None:
                        self.parent[o['_id']] = p
                    p = o['_id']
                for v in o.values():
                    walk(v, p)
            elif isinstance(o, list):
                for v in o:
                    walk(v, p)
        walk(self.d)

    def new_id(self):
        while True:
            self._ts += self._rnd.randint(1, 5)
            s = base64.b64encode(b'\x00' * 4 + self._ts.to_bytes(6, 'big') + os.urandom(4)).decode()
            if s not in self.ids:
                self.ids[s] = None
                return s

    def get(self, i):
        o = self.ids.get(i)
        if o is None:
            raise MdjError(f'No existe el id {i}')
        return o

    def name_of(self, i):
        o = self.ids.get(i)
        return (o.get('name') or o.get('_type')) if o else '?'

    # --- busqueda ---
    def find(self, spec, types=None):
        """Busca un elemento por id o por nombre. 'Tipo:Nombre' limita el tipo (p. ej. UMLClass:Cliente)."""
        if isinstance(spec, dict):
            spec = spec.get('$ref')
        if spec in self.ids and self.ids[spec] is not None:
            return self.ids[spec]
        tipo = None
        if isinstance(spec, str) and ':' in spec and spec.split(':', 1)[0].startswith('UML'):
            tipo, spec = spec.split(':', 1)
        cands = [o for o in self.ids.values() if o and o.get('name') == spec
                 and (tipo is None or o['_type'] == tipo) and (types is None or o['_type'] in types)
                 and not o['_type'].endswith('View')]
        if not cands:
            raise MdjError(f'No encontre "{spec}"' + (f' de tipo {tipo or types}' if (tipo or types) else ''))
        if len(cands) > 1:
            opts = ', '.join(f"{c['_type']}:{c['_id']}" for c in cands[:6])
            raise MdjError(f'"{spec}" es ambiguo ({opts}). Usa el id o Tipo:Nombre.')
        return cands[0]

    def diagram(self, spec):
        if spec in self.ids and self.ids[spec] and 'Diagram' in self.ids[spec]['_type']:
            return self.ids[spec]
        cands = [o for o in self.ids.values() if o and 'Diagram' in o.get('_type', '') and o.get('name') == spec]
        if not cands:
            raise MdjError(f'No encontre el diagrama "{spec}"')
        if len(cands) > 1:
            raise MdjError(f'Hay {len(cands)} diagramas "{spec}": ' + ', '.join(c['_id'] for c in cands) + '. Usa el id.')
        return cands[0]

    def diagrams(self):
        return [o for o in self.ids.values() if o and 'Diagram' in o.get('_type', '')]

    def views_of(self, model_id, diagram=None):
        res = []
        for dg in ([diagram] if diagram else self.diagrams()):
            for v in dg.get('ownedViews', []):
                m = v.get('model')
                if isinstance(m, dict) and m.get('$ref') == model_id:
                    res.append((dg, v))
        return res

    def view_in(self, dg, spec):
        """Vista dentro de un diagrama: por id de vista, o por el elemento que representa."""
        for v in dg.get('ownedViews', []):
            if v['_id'] == spec:
                return v
        el = self.find(spec)
        vs = self.views_of(el['_id'], dg)
        if not vs:
            raise MdjError(f'"{self.name_of(el["_id"])}" no tiene vista en {dg.get("name")}')
        return vs[0][1]

    # --- estereotipos ---
    def stereotype_id(self, name):
        for o in self.ids.values():
            if o and o.get('_type') == 'UMLStereotype' and o.get('name') == name:
                return o['_id']
        raise MdjError(f'No hay estereotipo "{name}" en el perfil del archivo')

    def kind(self, el):
        """'actor', 'boundary', 'control', 'entity' o el tipo."""
        if el is None:
            return '?'
        if el['_type'] == 'UMLActor':
            return 'actor'
        st = el.get('stereotype')
        if isinstance(st, dict):
            s = self.ids.get(st.get('$ref'))
            if s:
                return s.get('name', '?')
        elif isinstance(st, str) and st:
            return st
        return el['_type']

    # --- guardado ---
    def save(self, out=None, backup=True, force=False):
        target = os.path.abspath(os.path.expanduser(out)) if out else self.path
        abierto = staruml_gui_abierto()
        if abierto is not False and not force:
            if abierto:
                raise MdjError('StarUML esta abierto. Cierralo (sin guardar) antes de escribir el .mdj, '
                               'o usa forzar=true si sabes que no tiene este archivo cargado.')
            raise MdjError('No se pudo saber si StarUML esta abierto (no hay ps ni tasklist). '
                           'Usa forzar=true si sabes que no tiene este archivo cargado.')
        # se valida en memoria antes de tocar el disco: si el cambio empeora el archivo, no se escribe nada
        nuevos = self.problemas_nuevos()
        if nuevos:
            raise MdjError('No se escribio nada: el cambio dejaria el .mdj inconsistente (' + '; '.join(nuevos) + ')')
        try:
            texto = json.dumps(self.d, ensure_ascii=False, indent='\t', allow_nan=False)
        except ValueError:
            raise MdjError('No se escribio nada: el modelo tiene numeros NaN o infinitos, que StarUML no puede leer') from None
        bk = None
        if backup and os.path.exists(target):
            bk = backup_file(target)
        # las entradas None del indice de ids nuevos no se guardan: solo sirven para no repetir ids
        tmp = target + '.tmp_mcp'
        try:
            with open(tmp, 'w', encoding='utf-8', newline='\n') as f:  # saltos \n como StarUML, tambien en Windows
                f.write(texto)
            os.replace(tmp, target)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        self.path = target
        self._texto = texto
        self.reindex()
        return bk

    def problemas_nuevos(self):
        """Problemas de integridad del modelo en memoria que no estaban al cargarlo. Se comparan por id y no por
        conteo, para que un archivo que ya venia con problemas se pueda seguir editando sin sumarle otros."""
        _, dup, colg, mism = integridad(self.d)
        if not (dup or colg or mism):
            return []
        _, dup0, colg0, mism0 = integridad(json.loads(self._texto))
        res = []
        for nombre, ahora, antes in (('ids duplicados', dup, dup0),
                                     ('referencias colgantes', [r for r, _ in colg], [r for r, _ in colg0]),
                                     ('_parent incoherente', [i for i, _ in mism], [i for i, _ in mism0])):
            n = sorted(set((Counter(ahora) - Counter(antes)).elements()))
            if n:
                res.append(f'{nombre}: ' + ', '.join(n[:5]) + (f' y {len(n) - 5} mas' if len(n) > 5 else ''))
        return res


def backup_file(path, folder=None):
    folder = folder or BACKUP_DIR
    os.makedirs(folder, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(folder, f'{base}_{stamp}.mdj')
    n = 1
    while os.path.exists(dst):
        dst = os.path.join(folder, f'{base}_{stamp}_{n}.mdj'); n += 1
    shutil.copy2(path, dst)
    with open(path, 'rb') as a, open(dst, 'rb') as b:
        if a.read() != b.read():
            raise MdjError('El respaldo no quedo identico al original')
    # rotacion: se conservan los ultimos STARUML_MCP_BACKUP_KEEP respaldos de este archivo (0 = todos)
    try:
        keep = int(os.environ.get('STARUML_MCP_BACKUP_KEEP', '100'))
    except ValueError:
        keep = 100
    if keep > 0:
        patron = re.compile(re.escape(base) + r'_\d{8}_\d{6}(_\d+)?\.mdj$')
        propios = sorted((f for f in os.listdir(folder) if patron.match(f)),
                         key=lambda f: os.path.getmtime(os.path.join(folder, f)))
        for f in propios[:-keep]:
            if os.path.join(folder, f) != dst:
                os.remove(os.path.join(folder, f))
    return dst


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def resumen(doc):
    out = {'proyecto': doc.d.get('name'), 'archivo': doc.path, 'ids': sum(1 for v in doc.ids.values() if v), 'diagramas': []}
    for dg in doc.diagrams():
        path = []
        p = doc.parent.get(dg['_id'])
        while p:
            path.append(doc.name_of(p)); p = doc.parent.get(p)
        out['diagramas'].append({'id': dg['_id'], 'tipo': dg['_type'], 'nombre': dg.get('name'),
                                 'vistas': len(dg.get('ownedViews', [])), 'abre_por_defecto': bool(dg.get('defaultDiagram')),
                                 'ruta': ' / '.join(reversed(path))})
    cnt = {}
    for o in doc.ids.values():
        if o and o['_type'] in ('UMLClass', 'UMLActor'):
            k = doc.kind(o); cnt[k] = cnt.get(k, 0) + 1
    out['clases_por_estereotipo'] = cnt
    return out


def modelo(doc, filtro=None, paquete=None, limite=None, desde=0):
    clases, asoc, gen = [], [], []
    pk = doc.find(paquete)['_id'] if paquete else None
    vistas_de = {}
    for dg in doc.diagrams():
        for v in dg.get('ownedViews', []):
            m = v.get('model')
            if isinstance(m, dict):
                vistas_de.setdefault(m.get('$ref'), []).append(dg.get('name'))
    for o in doc.ids.values():
        if not o:
            continue
        if o['_type'] in ('UMLClass', 'UMLActor', 'UMLInterface'):
            if pk and doc.parent.get(o['_id']) != pk:
                continue
            if filtro and filtro.lower() not in (o.get('name') or '').lower():
                continue
            clases.append({'id': o['_id'], 'nombre': o.get('name'), 'estereotipo': doc.kind(o),
                           'paquete': doc.name_of(doc.parent.get(o['_id'])),
                           'atributos': [a.get('name') for a in o.get('attributes', [])],
                           'operaciones': [a.get('name') for a in o.get('operations', [])],
                           'documentacion': o.get('documentation', '')})
    for o in doc.ids.values():
        if not o:
            continue
        if o['_type'] == 'UMLAssociation':
            e1, e2 = o['end1'], o['end2']
            n1, n2 = doc.name_of(e1['reference']['$ref']), doc.name_of(e2['reference']['$ref'])
            if filtro and filtro.lower() not in (n1 + n2).lower():
                continue
            asoc.append({'id': o['_id'], 'duenio': doc.name_of(doc.parent.get(o['_id'])), 'nombre': o.get('name', ''),
                         'extremo1': {'clase': n1, 'mult': e1.get('multiplicity', ''), 'rol': e1.get('name', ''),
                                      'navegable': e1.get('navigable') == 'navigable'},
                         'extremo2': {'clase': n2, 'mult': e2.get('multiplicity', ''), 'rol': e2.get('name', ''),
                                      'navegable': e2.get('navigable') == 'navigable'},
                         'vistas': vistas_de.get(o['_id'], [])})
        elif o['_type'] in ('UMLGeneralization', 'UMLRealization', 'UMLDependency', 'UMLInterfaceRealization'):
            s, t = doc.name_of(o['source']['$ref']), doc.name_of(o['target']['$ref'])
            if filtro and filtro.lower() not in (s + t).lower():
                continue
            gen.append({'id': o['_id'], 'tipo': o['_type'], 'de': s, 'a': t})
    res = {'clases': clases, 'asociaciones': asoc, 'otras_relaciones': gen}
    if limite:
        desde, limite = max(0, int(desde or 0)), int(limite)
        total = {k: len(v) for k, v in res.items()}
        res = {k: v[desde:desde + limite] for k, v in res.items()}
        res.update({'total': total, 'desde': desde,
                    'siguiente_desde': desde + limite if any(n > desde + limite for n in total.values()) else None})
    return res


def interaction_of(doc, dg):
    it = doc.ids.get(doc.parent.get(dg['_id']))
    if not it or it['_type'] != 'UMLInteraction':
        raise MdjError(f'El diagrama {dg.get("name")} no cuelga de una interaccion')
    return it


def lifeline_info(doc, ll_id):
    ll = doc.ids.get(ll_id)
    if not ll:
        return ('?', '?')
    role = doc.ids.get(ll.get('represent', {}).get('$ref')) if ll.get('represent') else None
    t = doc.ids.get(role['type']['$ref']) if role and isinstance(role.get('type'), dict) else None
    if t:
        return (t.get('name'), doc.kind(t))
    return (ll.get('name') or '?', '?')


def secuencia(doc, diagrama):
    dg = doc.diagram(diagrama)
    it = interaction_of(doc, dg)
    msgs = []
    for n, m in enumerate(it.get('messages', []), 1):
        s, ks = lifeline_info(doc, m['source']['$ref'])
        t, kt = lifeline_info(doc, m['target']['$ref'])
        msgs.append({'n': n, 'de': s, 'a': t, 'tipos': f'{ks}->{kt}', 'reply': m.get('messageSort') == 'reply', 'nombre': m.get('name')})
    return {'diagrama': dg.get('name'), 'interaccion': it.get('name'),
            'lifelines': [lifeline_info(doc, l['_id'])[0] for l in it.get('participants', [])], 'mensajes': msgs}


def geometria(doc, diagrama):
    dg = doc.diagram(diagrama)
    cajas, lineas = [], []
    for v in dg.get('ownedViews', []):
        t = v['_type']
        if t in VIEW_TYPES_BOX or t == 'UMLSeqLifelineView':
            m = v.get('model')
            cajas.append({'vista': v['_id'], 'tipo': t, 'elemento': doc.name_of(m['$ref']) if isinstance(m, dict) else 'NOTA',
                          'x': v.get('left'), 'y': v.get('top'), 'ancho': v.get('width'), 'alto': v.get('height'),
                          **({'texto': v.get('text', '')[:80]} if t == 'UMLNoteView' else {})})
        elif t in EDGE_TYPES:
            tl = doc.ids.get(v.get('tail', {}).get('$ref')); hd = doc.ids.get(v.get('head', {}).get('$ref'))
            nm = lambda x: doc.name_of(x['model']['$ref']) if x and isinstance(x.get('model'), dict) else 'nota'
            lineas.append({'vista': v['_id'], 'tipo': t, 'modelo': v.get('model', {}).get('$ref'),
                           'de': nm(tl), 'a': nm(hd), 'puntos': v.get('points')})
    return {'diagrama': dg.get('name'), 'cajas': cajas, 'lineas': lineas}


def buscar(doc, texto=None, tipo=None, limite=60):
    res = []
    for o in doc.ids.values():
        if not o or o['_type'].endswith('View') or o['_type'] in ('EdgeLabelView', 'LabelView'):
            continue
        if tipo and o['_type'] != tipo:
            continue
        nm = o.get('name') or ''
        if texto and texto.lower() not in nm.lower():
            continue
        res.append({'id': o['_id'], 'tipo': o['_type'], 'nombre': nm, 'dentro_de': doc.name_of(doc.parent.get(o['_id']))})
        if len(res) >= limite:
            break
    return res


# ---------------------------------------------------------------------------
# Validacion
# ---------------------------------------------------------------------------

def integridad(d):
    """Un solo recorrido del arbol JSON: ids vistos, ids duplicados, referencias colgantes [(ref, ruta)] y
    elementos cuyo _parent no es su contenedor real [(id, descripcion)]."""
    seen, dup, refs, mism = set(), [], [], []

    def walk(o, p=None, path=''):
        if isinstance(o, dict):
            if '$ref' in o and len(o) == 1:
                refs.append((o['$ref'], path))
            if '_id' in o:
                if o['_id'] in seen:
                    dup.append(o['_id'])
                seen.add(o['_id'])
                par = o.get('_parent')
                if p is not None and isinstance(par, dict) and par.get('$ref') != p:
                    mism.append((o['_id'], f"{o.get('_type')} {o.get('name', '')} {o['_id']}"))
                p = o['_id']
            for k, v in o.items():
                if isinstance(v, (dict, list)):
                    walk(v, p, path + '/' + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                if isinstance(v, (dict, list)):
                    walk(v, p, path + f'[{i}]')
    walk(d)
    colg = [(r, pth[-100:]) for r, pth in refs if r not in seen]
    return seen, dup, colg, mism


def validar(doc, oose=True):
    seen, dup, colg, mism = integridad(doc.d)
    res = {'ids': len(seen), 'duplicados': dup[:20], 'n_duplicados': len(dup), 'colgantes': colg[:20],
           'n_colgantes': len(colg), 'parent_mismatch': [m for _, m in mism[:20]], 'n_parent_mismatch': len(mism)}
    if oose:
        res['oose'] = reglas_oose(doc)
    return res


def reglas_oose(doc):
    prob, avisos = [], []
    kinds = {}
    for o in doc.ids.values():
        if o and o['_type'] in ('UMLClass', 'UMLActor'):
            kinds[o['_id']] = doc.kind(o)
    # atributos y metodos
    for i, k in kinds.items():
        o = doc.ids[i]
        if o.get('operations'):
            prob.append(f'{o.get("name", "(sin nombre)")} ({k}) tiene metodos; en analisis no se ponen metodos')
        if k in ('boundary', 'control') and o.get('attributes'):
            prob.append(f'{o.get("name", "(sin nombre)")} ({k}) tiene atributos; boundary y control van sin atributos')
    # un control por paquete
    por_pk = {}
    for i, k in kinds.items():
        if k == 'control':
            por_pk.setdefault(doc.parent.get(i), []).append(doc.ids[i].get('name', '(sin nombre)'))
    for pk, cs in por_pk.items():
        if len(cs) > 1:
            prob.append(f'El paquete {doc.name_of(pk)} tiene {len(cs)} controles: {cs}')
    # asociaciones
    pares = set()
    for o in doc.ids.values():
        if o and o['_type'] == 'UMLAssociation':
            a, b = o['end1']['reference']['$ref'], o['end2']['reference']['$ref']
            ka, kb = kinds.get(a), kinds.get(b)
            pares.add(frozenset((a, b)))
            par = {ka, kb}
            nm = f'{doc.name_of(a)} -- {doc.name_of(b)}'
            if par == {'boundary', 'entity'}:
                prob.append(f'Asociacion boundary--entity: {nm}')
            elif ka == kb == 'boundary':
                prob.append(f'Asociacion boundary--boundary: {nm}')
            elif par == {'control', 'actor'}:
                prob.append(f'Asociacion control--actor: {nm} (debe pasar por una boundary)')
            elif par == {'entity', 'actor'}:
                prob.append(f'Asociacion entity--actor: {nm}')
    # estereotipos como texto (StarUML dibuja una caja tachada) y una sola notacion (iconos) para robustez
    for o in doc.ids.values():
        if o and o['_type'] == 'UMLClass' and isinstance(o.get('stereotype'), str) and o['stereotype'] in ('boundary', 'control', 'entity'):
            prob.append(f'{o.get("name", "(sin nombre)")}: el estereotipo {o["stereotype"]} esta como texto; debe ser referencia al perfil')
    cajas_tipos = ('UMLClassView', 'UMLActorView', 'UMLInterfaceView', 'UMLNoteView', 'UMLUseCaseView')
    for dg in doc.diagrams():
        if dg['_type'] not in ('UMLClassDiagram', 'UMLUseCaseDiagram'):
            continue
        cajas = []
        for v in dg.get('ownedViews', []):
            m = v.get('model')
            if v['_type'] == 'UMLClassView' and isinstance(m, dict) and kinds.get(m.get('$ref')) in ('boundary', 'control', 'entity') \
                    and v.get('stereotypeDisplay', 'label') != 'icon':
                avisos.append(f'{dg.get("name")}: {doc.name_of(m["$ref"])} no usa la notacion de iconos')
            if v['_type'] in cajas_tipos and v.get('visible', True) is not False and all(isinstance(v.get(k), (int, float)) for k in ('left', 'top', 'width', 'height')):
                cajas.append((doc.name_of(m['$ref']) if isinstance(m, dict) else 'nota', v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height']))
        for i, x in enumerate(cajas):
            for y in cajas[i + 1:]:
                if x[1] < y[3] and y[1] < x[3] and x[2] < y[4] and y[2] < x[4]:
                    avisos.append(f'{dg.get("name")}: cajas encimadas {x[0]} / {y[0]}')
    # secuencias
    for dg in doc.diagrams():
        if dg['_type'] != 'UMLSequenceDiagram' or not dg.get('ownedViews'):
            continue
        try:
            it = interaction_of(doc, dg)
        except MdjError:
            continue
        msgs = it.get('messages', [])
        if not msgs:
            continue
        tipo_ll = {}
        for l in it.get('participants', []):
            role = doc.ids.get(l.get('represent', {}).get('$ref')) if l.get('represent') else None
            t = role.get('type', {}).get('$ref') if role and isinstance(role.get('type'), dict) else None
            tipo_ll[l['_id']] = t
        for n, m in enumerate(msgs, 1):
            s, t = tipo_ll.get(m['source']['$ref']), tipo_ll.get(m['target']['$ref'])
            ks, kt = kinds.get(s, '?'), kinds.get(t, '?')
            rep = m.get('messageSort') == 'reply'
            tag = f'{dg.get("name")} #{n} {m.get("name")} ({ks}->{kt})'
            ok = {('actor', 'boundary'), ('boundary', 'control'), ('control', 'entity'), ('entity', 'control'),
                  ('control', 'boundary'), ('boundary', 'actor'), ('entity', 'entity')}
            if (ks, kt) not in ok:
                prob.append(f'Mensaje no valido en OOSE: {tag}')
            if rep and ks == 'boundary' and kt == 'actor':
                prob.append(f'Reply de boundary a actor: {tag}')
            if (ks, kt) == ('entity', 'entity') and frozenset((s, t)) not in pares:
                prob.append(f'Mensaje entity->entity sin asociacion en el modelo: {tag}')
            if not rep and ks == 'control' and kt == 'entity' and re.match(r'(consultar|buscar|obtener)', m.get('name') or '', re.I):
                sig = msgs[n] if n < len(msgs) else None
                if not (sig and sig.get('messageSort') == 'reply'):
                    avisos.append(f'Consulta sin reply inmediato: {tag}')
        # estructura de las vistas de mensaje y activaciones
        acts = {}
        for v in dg['ownedViews']:
            if v['_type'] == 'UMLSeqMessageView':
                tipos = [s['_type'] for s in v.get('subViews', [])]
                if tipos.count('EdgeLabelView') != 3 or tipos.count('UMLActivationView') != 1:
                    prob.append(f'{dg.get("name")}: vista de mensaje incompleta {v["_id"]} ({tipos.count("EdgeLabelView")} etiquetas)')
                act = [s for s in v.get('subViews', []) if s['_type'] == 'UMLActivationView']
                m = doc.ids.get(v['model']['$ref'])
                if act and m and act[0].get('visible', True) is not False:
                    acts.setdefault(m['target']['$ref'], []).append((act[0]['top'], act[0]['top'] + act[0]['height']))
        fuera = 0
        for v in dg['ownedViews']:
            if v['_type'] != 'UMLSeqMessageView':
                continue
            m = doc.ids.get(v['model']['$ref'])
            if not m or m.get('messageSort') == 'reply':
                continue
            src = m['source']['$ref']
            if kinds.get(tipo_ll.get(src)) == 'actor':
                continue
            y = float(v['points'].split(';')[0].split(':')[1])
            if not any(a - 1 <= y <= b + 1 for a, b in acts.get(src, [])):
                fuera += 1
        if fuera:
            avisos.append(f'{dg.get("name")}: {fuera} llamadas salen de una lifeline sin activacion')
    return {'problemas': prob, 'avisos': avisos}


def diff(doc_a, doc_b):
    A, B = doc_a.ids, doc_b.ids
    isview = lambda t: t.endswith('View') or t in ('EdgeLabelView', 'LabelView')
    gone = [i for i, o in A.items() if o and i not in B and not isview(o['_type'])]
    new = [i for i, o in B.items() if o and i not in A and not isview(o['_type'])]
    cuenta = lambda ids, lst: {t: sum(1 for i in lst if ids[i]['_type'] == t) for t in {ids[i]['_type'] for i in lst}}
    out = {'quitados': cuenta(A, gone), 'agregados': cuenta(B, new), 'detalle_quitados': [], 'detalle_agregados': [], 'cambios': [], 'diagramas': []}
    for lst, ids, doc, key in ((gone, A, doc_a, 'detalle_quitados'), (new, B, doc_b, 'detalle_agregados')):
        for i in lst:
            o = ids[i]; t = o['_type']
            if t in ('UMLClass', 'UMLActor', 'UMLUseCase', 'UMLNote', 'UMLPackage') or 'Diagram' in t:
                out[key].append(f"{t} {o.get('name', '')}")
            elif t == 'UMLAssociation':
                out[key].append(f"Asociacion {doc.name_of(o['end1']['reference']['$ref'])} -- {doc.name_of(o['end2']['reference']['$ref'])}")
            elif t == 'UMLAttribute' and ids.get(doc.parent.get(i), {}) and ids[doc.parent[i]]['_type'] == 'UMLClass':
                out[key].append(f"Atributo {doc.name_of(doc.parent[i])}.{o.get('name')}")
    for i, a in A.items():
        b = B.get(i)
        if a and b and not isview(a['_type']):
            for k in ('name', 'documentation', 'multiplicity', 'navigable', 'aggregation', 'stereotype', 'messageSort'):
                if a.get(k) != b.get(k):
                    out['cambios'].append(f"{a['_type']} {doc_a.name_of(i)}: {k} {str(a.get(k))[:60]!r} -> {str(b.get(k))[:60]!r}")
            if a['_type'] == 'UMLAssociationEnd' and a.get('reference') != b.get('reference'):
                out['cambios'].append(f"Extremo de asociacion {i}: {doc_a.name_of(a['reference']['$ref'])} -> {doc_b.name_of(b['reference']['$ref'])}")
    for i, a in A.items():
        if a and 'Diagram' in a['_type']:
            b = B.get(i)
            na, nb = len(a.get('ownedViews', [])), len(b.get('ownedViews', [])) if b else None
            if na != nb:
                out['diagramas'].append(f"{a.get('name')}: {na} -> {nb} vistas")
    return out


# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------

def centro(v):
    return (v['left'] + v['width'] / 2, v['top'] + v['height'] / 2)


def junction(v, p):
    cx, cy = centro(v)
    dx, dy = p[0] - cx, p[1] - cy
    if dx == 0 and dy == 0:
        return (cx, cy)
    hw, hh = v['width'] / 2, v['height'] / 2
    t = min(hw / abs(dx) if dx else 1e9, hh / abs(dy) if dy else 1e9)
    return (cx + dx * t, cy + dy * t)


def ruta(tail_v, head_v, medios=()):
    medios = [tuple(m) for m in medios or ()]
    if not medios and tail_v.get('_id') == head_v.get('_id'):
        # asociacion reflexiva: un lazo por la esquina superior derecha (una recta de largo cero no se veria)
        l, t, w, h = tail_v['left'], tail_v['top'], tail_v['width'], tail_v['height']
        medios = [(l + w * 3 / 4, t - 30), (l + w + 30, t - 30), (l + w + 30, t + h / 4)]
    a = junction(tail_v, medios[0] if medios else centro(head_v))
    b = junction(head_v, medios[-1] if medios else centro(tail_v))
    return ';'.join(f'{round(x)}:{round(y)}' for x, y in [a] + medios + [b])


# ---------------------------------------------------------------------------
# Edicion: vistas de clase, atributos, notas
# ---------------------------------------------------------------------------

def _name_label(v):
    nc = [s for s in v.get('subViews', []) if s['_type'] == 'UMLNameCompartmentView']
    if not nc:
        return None
    nc = nc[0]
    for l in nc.get('subViews', []):
        if l['_id'] == nc.get('nameLabel', {}).get('$ref'):
            return l
    return None


def mover_vista(v, left=None, top=None, width=None, height=None):
    left = v['left'] if left is None else left
    top = v['top'] if top is None else top
    dx, dy = left - v['left'], top - v['top']

    def walk(o, raiz):
        if isinstance(o, dict):
            if not raiz and isinstance(o.get('left'), (int, float)) and o.get('visible') is not False:
                o['left'] = round(o['left'] + dx, 2)
                if isinstance(o.get('top'), (int, float)):
                    o['top'] = round(o['top'] + dy, 2)
            for x in o.get('subViews', []):
                walk(x, False)
    walk(v, True)
    v['left'], v['top'] = left, top
    if width is not None:
        v['width'] = width
        for s in v.get('subViews', []):
            if s['_type'] in ('UMLNameCompartmentView', 'UMLAttributeCompartmentView') and s.get('visible') is not False:
                s['width'] = width + 1
                for l in s.get('subViews', []):
                    if l.get('visible') is not False and 'text' in l:
                        l['width'] = width - 9
    if height is not None:
        v['height'] = height


def rehacer_atributos_vista(doc, v, cls):
    acv = [s for s in v.get('subViews', []) if s['_type'] == 'UMLAttributeCompartmentView']
    if not acv:
        return
    acv = acv[0]
    n = len(cls.get('attributes', []))
    if acv.get('visible') is False:
        return
    acv['top'] = v['top'] + 67; acv['left'] = v['left']; acv['height'] = 15 * n + 8
    viejos = {s['model']['$ref']: s for s in acv.get('subViews', []) if isinstance(s.get('model'), dict)}
    subs = []
    for i, a in enumerate(cls.get('attributes', [])):
        s = viejos.get(a['_id']) or {'_type': 'UMLAttributeView', '_id': doc.new_id(), '_parent': ref(acv['_id']),
                                     'model': ref(a['_id']), 'font': 'Arial;13;0', 'parentStyle': True}
        s.update({'left': v['left'] + 5, 'top': v['top'] + 72 + 15 * i, 'width': v['width'] - 9, 'height': 13,
                  'text': _texto_atributo(doc, a), 'horizontalAlignment': 0})
        subs.append(s)
    acv['subViews'] = subs
    v['height'] = max(v['height'] if n == 0 else 0, 73 + 15 * n)


def _texto_atributo(doc, a):
    t = a.get('type')
    t = doc.name_of(t['$ref']) if isinstance(t, dict) and t.get('$ref') else (t if isinstance(t, str) else '')
    return '+' + (a.get('name') or '') + (f': {t}' if t else '')


def set_atributos(doc, cls, nombres):
    repetidos = sorted({n for n in nombres if nombres.count(n) > 1})
    if repetidos:  # el mismo atributo quedaria dos veces en el archivo, con el mismo _id
        raise MdjError(f'Atributos repetidos: {repetidos}')
    viejos = {a.get('name'): a for a in cls.get('attributes', [])}
    nuevos = []
    for n in nombres:
        a = viejos.get(n) or {'_type': 'UMLAttribute', '_id': doc.new_id(), '_parent': ref(cls['_id']), 'name': n, 'type': ''}
        nuevos.append(a)
    quitados = [n for n in viejos if n not in nombres]
    cls['attributes'] = nuevos
    ids_quitados = {viejos[n]['_id'] for n in quitados}
    for dg, v in doc.views_of(cls['_id']):
        acv = [s for s in v.get('subViews', []) if s['_type'] == 'UMLAttributeCompartmentView']
        if acv:
            acv[0]['subViews'] = [s for s in acv[0].get('subViews', []) if s.get('model', {}).get('$ref') not in ids_quitados]
        rehacer_atributos_vista(doc, v, cls)
    return quitados


def agregar_atributos(doc, cls, nombres):
    """Agrega los atributos que falten (por nombre) sin tocar ni quitar los que ya tiene la clase."""
    existentes = {a.get('name') for a in cls.get('attributes', [])}
    nuevos = [n for n in dict.fromkeys(nombres) if n not in existentes]
    for n in nuevos:
        cls.setdefault('attributes', []).append({'_type': 'UMLAttribute', '_id': doc.new_id(), '_parent': ref(cls['_id']),
                                                 'name': n, 'type': ''})
    if nuevos:
        for _, v in doc.views_of(cls['_id']):
            rehacer_atributos_vista(doc, v, cls)
    return nuevos


ARIAL11 = {**{c: 6.1 for c in 'abcdeghnopqusvxyz'}, **{c: 2.5 for c in 'ijl'}, **{c: 3.1 for c in 'ftr'},
           **{c: 9.2 for c in 'mw'}, **{c: 7.4 for c in 'ABCDEFGHIJKLNOPQRSTUVXYZ'}, 'M': 9.2, 'W': 10.4,
           ' ': 3.1, ',': 3.1, '.': 3.1, ';': 3.1, ':': 3.1, '(': 3.7, ')': 3.7}


def lineas_nota(texto, ancho):
    total = 0
    for parrafo in texto.split('\n'):
        n, actual = 1, 0.0
        for palabra in parrafo.split(' '):
            w = sum(ARIAL11.get(c, 6.1) for c in palabra)
            if actual and actual + 3.1 + w > ancho:
                n += 1; actual = w
            else:
                actual += (3.1 if actual else 0) + w
        total += n
    return total


def nota(doc, dg, texto, x, y, ancho, alto=None, vista=None):
    """Crea o edita una nota. El alto se calcula solo: cada renglon de Arial 11 ocupa 11 px."""
    if alto is None:
        alto = lineas_nota(texto, ancho - 10) * 11 + 15 + random.randint(0, 3)
    if vista:
        nv = [v for v in dg.get('ownedViews', []) if v['_id'] == vista]
        if not nv:
            raise MdjError(f'No hay vista {vista} en {dg.get("name")}')
        nv = nv[0]
    else:
        nv = {'_type': 'UMLNoteView', '_id': doc.new_id(), '_parent': ref(dg['_id']), 'font': 'Arial;11;0', 'parentStyle': False}
        dg.setdefault('ownedViews', []).append(nv)
    nv.update({'left': x, 'top': y, 'width': ancho, 'height': alto, 'text': texto})
    return nv


def modelo_raiz(doc):
    modelos = [o for o in doc.d.get('ownedElements', []) if isinstance(o, dict) and o.get('_type') == 'UMLModel']
    if not modelos:
        raise MdjError('El proyecto no tiene un UMLModel; indica dentro_de')
    return modelos[0]


def crear_paquete(doc, nombre, dentro_de=None):
    padre = doc.find(dentro_de, types=('UMLModel', 'UMLPackage', 'UMLSubsystem')) if dentro_de else modelo_raiz(doc)
    pk = {'_type': 'UMLPackage', '_id': doc.new_id(), '_parent': ref(padre['_id']), 'name': nombre}
    padre.setdefault('ownedElements', []).append(pk)
    doc.reindex()
    return pk


def crear_diagrama(doc, tipo, nombre, dentro_de=None, por_defecto=False):
    """Diagrama de clases, de casos de uso o de secuencia. El de secuencia se crea como lo hace StarUML:
    colaboracion > interaccion > diagrama, con su marco."""
    padre = doc.find(dentro_de, types=('UMLModel', 'UMLPackage', 'UMLSubsystem')) if dentro_de else modelo_raiz(doc)
    if tipo in ('clases', 'casos_de_uso'):
        dg = {'_type': 'UMLClassDiagram' if tipo == 'clases' else 'UMLUseCaseDiagram', '_id': doc.new_id(),
              '_parent': ref(padre['_id']), 'name': nombre}
        padre.setdefault('ownedElements', []).append(dg)
    elif tipo == 'secuencia':
        cid, iid, did, fid, l1, l2 = [doc.new_id() for _ in range(6)]
        marco = {'_type': 'UMLFrameView', '_id': fid, '_parent': ref(did), 'model': ref(did),
                 'subViews': [{'_type': 'LabelView', '_id': l1, '_parent': ref(fid), 'font': 'Arial;13;0',
                               'left': 32.72998046875, 'top': 15, 'width': round(ancho13(nombre), 2), 'height': 13, 'text': nombre},
                              {'_type': 'LabelView', '_id': l2, '_parent': ref(fid), 'font': 'Arial;13;1',
                               'left': 13, 'top': 15, 'width': 14.72, 'height': 13, 'text': 'sd'}],
                 'font': 'Arial;13;0', 'left': 8, 'top': 10, 'width': 695, 'height': 595,
                 'nameLabel': ref(l1), 'frameTypeLabel': ref(l2)}
        dg = {'_type': 'UMLSequenceDiagram', '_id': did, '_parent': ref(iid), 'name': nombre, 'ownedViews': [marco]}
        inter = {'_type': 'UMLInteraction', '_id': iid, '_parent': ref(cid), 'name': nombre, 'ownedElements': [dg]}
        padre.setdefault('ownedElements', []).append(
            {'_type': 'UMLCollaboration', '_id': cid, '_parent': ref(padre['_id']), 'name': nombre, 'ownedElements': [inter]})
    else:
        raise MdjError('tipo debe ser "clases", "casos_de_uso" o "secuencia"')
    if por_defecto:
        for otro in doc.diagrams():
            otro.pop('defaultDiagram', None)
        dg['defaultDiagram'] = True
    doc.reindex()
    return dg


def _clonar(doc, v, modelos):
    c = copy.deepcopy(v)
    mapa = {}

    def renum(o):
        if isinstance(o, dict):
            if '_id' in o:
                mapa[o['_id']] = doc.new_id(); o['_id'] = mapa[o['_id']]
            for x in o.values():
                renum(x)
        elif isinstance(o, list):
            for x in o:
                renum(x)
    renum(c)

    def fix(o):
        if isinstance(o, dict):
            for k, x in list(o.items()):
                if isinstance(x, dict) and set(x) == {'$ref'}:
                    if x['$ref'] in mapa:
                        o[k] = ref(mapa[x['$ref']])
                    elif x['$ref'] in modelos:
                        o[k] = ref(modelos[x['$ref']])
                else:
                    fix(x)
        elif isinstance(o, list):
            for x in o:
                fix(x)
    fix(c)
    return c


def _compartment(doc, tipo, parent, model, visible=False, x=0, y=0):
    c = {'_type': tipo, '_id': doc.new_id(), '_parent': ref(parent), 'model': ref(model)}
    if not visible:
        c['visible'] = False
    c.update({'font': 'Arial;13;0', 'parentStyle': True, 'left': x, 'top': y, 'width': 10, 'height': 10})
    return c


def vista_nueva(doc, dg, el, x, y, ancho=None, alto=None):
    """Agrega la vista de una clase o actor a un diagrama de clases, en notacion de iconos."""
    if dg['_type'] not in ('UMLClassDiagram', 'UMLUseCaseDiagram'):
        raise MdjError(f'{dg.get("name")} es {dg["_type"]}: aqui solo se agregan vistas a diagramas de clases o de casos de uso')
    if el['_type'] not in ('UMLClass', 'UMLActor', 'UMLInterface'):
        raise MdjError(f'{el.get("name")} es {el["_type"]}: solo se dibujan clases, interfaces o actores')
    k = doc.kind(el)
    # si ya hay una vista de otra clase del mismo estereotipo, se clona para copiar su estilo exacto
    plantilla = None
    for d2 in doc.diagrams():
        for v in d2.get('ownedViews', []):
            m = v.get('model')
            if v['_type'] in ('UMLClassView', 'UMLActorView', 'UMLInterfaceView') and isinstance(m, dict):
                o = doc.ids.get(m['$ref'])
                if o and o['_id'] != el['_id'] and doc.kind(o) == k and o['_type'] == el['_type']:
                    plantilla = (v, o); break
        if plantilla:
            break
    nombre = el.get('name', '')
    if ancho is None:
        ancho = max(100, round(7.6 * len(nombre) + 12))
    if plantilla:
        v, o = plantilla
        nv = _clonar(doc, v, {o['_id']: el['_id']})
        acv = [s for s in nv.get('subViews', []) if s['_type'] == 'UMLAttributeCompartmentView']
        if acv:
            acv[0]['subViews'] = []
        nv['_parent'] = ref(dg['_id'])
        mover_vista(nv, x, y, ancho)
    else:
        vid = doc.new_id(); ncid = doc.new_id(); labs = [doc.new_id() for _ in range(4)]
        es_actor = el['_type'] == 'UMLActor'
        robustez = k in ('boundary', 'control', 'entity')
        nc = {'_type': 'UMLNameCompartmentView', '_id': ncid, '_parent': ref(vid), 'model': ref(el['_id']),
              'subViews': [
                  {'_type': 'LabelView', '_id': labs[0], '_parent': ref(ncid), 'visible': False, 'font': 'Arial;13;0', 'parentStyle': True, 'left': x, 'top': y, 'height': 13},
                  {'_type': 'LabelView', '_id': labs[1], '_parent': ref(ncid), 'font': 'Arial;13;1', 'parentStyle': True, 'left': x + 5, 'top': y + 47, 'width': ancho - 9, 'height': 13, 'text': nombre},
                  {'_type': 'LabelView', '_id': labs[2], '_parent': ref(ncid), 'visible': False, 'font': 'Arial;13;0', 'parentStyle': True, 'left': x, 'top': y, 'height': 13},
                  {'_type': 'LabelView', '_id': labs[3], '_parent': ref(ncid), 'visible': False, 'font': 'Arial;13;0', 'parentStyle': True, 'left': x, 'top': y, 'height': 13, 'horizontalAlignment': 1}],
              'font': 'Arial;13;0', 'parentStyle': True, 'left': x, 'top': y + 40, 'width': ancho + 1, 'height': 25,
              'stereotypeLabel': ref(labs[0]), 'nameLabel': ref(labs[1]), 'namespaceLabel': ref(labs[2]), 'propertyLabel': ref(labs[3])}
        con_attr = not es_actor and k not in ('boundary', 'control')
        ac = _compartment(doc, 'UMLAttributeCompartmentView', vid, el['_id'], visible=con_attr, x=x, y=y + 67)
        subs = [nc, ac, _compartment(doc, 'UMLOperationCompartmentView', vid, el['_id']),
                _compartment(doc, 'UMLReceptionCompartmentView', vid, el['_id']),
                _compartment(doc, 'UMLTemplateParameterCompartmentView', vid, el['_id'])]
        tipo_vista = 'UMLActorView' if es_actor else ('UMLInterfaceView' if el['_type'] == 'UMLInterface' else 'UMLClassView')
        nv = {'_type': tipo_vista, '_id': vid, '_parent': ref(dg['_id']),
              'model': ref(el['_id']), 'subViews': subs, 'font': 'Arial;13;0', 'parentStyle': False,
              'containerChangeable': True, 'left': x, 'top': y, 'width': ancho, 'height': 80 if es_actor else 65}
        if not es_actor:
            nv['stereotypeDisplay'] = 'icon' if robustez else 'label'
        nv.update({'nameCompartment': ref(ncid)})
        if not con_attr:
            nv['suppressAttributes'] = True
        if es_actor or robustez or not el.get('operations'):
            nv['suppressOperations'] = True
        nv.update({'attributeCompartment': ref(subs[1]['_id']), 'operationCompartment': ref(subs[2]['_id']),
                   'receptionCompartment': ref(subs[3]['_id']), 'templateParameterCompartment': ref(subs[4]['_id'])})
    lab = _name_label(nv)
    if lab:
        lab['text'] = nombre
    # los atributos se ven en todo lo que no sea actor, boundary o control (aunque la plantilla los ocultara)
    muestra_attrs = el['_type'] != 'UMLActor' and k not in ('boundary', 'control')
    if muestra_attrs and el.get('attributes'):
        nv.pop('suppressAttributes', None)
        for s in nv.get('subViews', []):
            if s['_type'] == 'UMLAttributeCompartmentView':
                s.pop('visible', None)
    dg.setdefault('ownedViews', []).append(nv)
    if muestra_attrs:
        rehacer_atributos_vista(doc, nv, el)
    if alto:
        nv['height'] = alto
    return nv


# ---------------------------------------------------------------------------
# Edicion: asociaciones y lineas
# ---------------------------------------------------------------------------

def asociacion_crear(doc, a, b, m1='', m2='', rol1='', rol2='', navegable='hacia', duenio=None):
    duenio = duenio or a
    aid = doc.new_id()
    e1 = {'_type': 'UMLAssociationEnd', '_id': doc.new_id(), '_parent': ref(aid)}
    if rol1:
        e1['name'] = rol1
    e1['reference'] = ref(a['_id'])
    if navegable in ('ambos', 'desde'):
        e1['navigable'] = 'navigable'
    if m1:
        e1['multiplicity'] = m1
    e2 = {'_type': 'UMLAssociationEnd', '_id': doc.new_id(), '_parent': ref(aid)}
    if rol2:
        e2['name'] = rol2
    e2['reference'] = ref(b['_id'])
    if navegable in ('ambos', 'hacia'):
        e2['navigable'] = 'navigable'
    if m2:
        e2['multiplicity'] = m2
    asoc = {'_type': 'UMLAssociation', '_id': aid, '_parent': ref(duenio['_id']), 'end1': e1, 'end2': e2}
    duenio.setdefault('ownedElements', []).append(asoc)
    doc.reindex()
    return asoc


def asociacion_editar(doc, asoc, extremo, mult=None, rol=None, navegable=None, clase=None):
    e = asoc['end1' if extremo == 1 else 'end2']
    if mult is not None:
        if mult:
            e['multiplicity'] = mult
        else:
            e.pop('multiplicity', None)
    if rol is not None:
        if rol:
            e['name'] = rol
        else:
            e.pop('name', None)
    if navegable is not None:
        if navegable:
            e['navigable'] = 'navigable'
        else:
            e.pop('navigable', None)
    if clase is not None:
        e['reference'] = ref(clase['_id'])
    orden = ('_type', '_id', '_parent', 'name', 'reference', 'navigable', 'aggregation', 'multiplicity')
    asoc['end1' if extremo == 1 else 'end2'] = {**{k: e[k] for k in orden if k in e}, **{k: v for k, v in e.items() if k not in orden}}
    quitadas = []
    for dg, v in doc.views_of(asoc['_id']):
        if clase is not None:
            lado = 'tail' if extremo == 1 else 'head'
            nuevas = doc.views_of(clase['_id'], dg)
            if nuevas:
                v[lado] = ref(nuevas[0][1]['_id'])
                otra = [x for x in dg['ownedViews'] if x['_id'] == v['tail' if lado == 'head' else 'head']['$ref']]
                if otra:
                    tv = nuevas[0][1] if lado == 'tail' else otra[0]
                    hv = otra[0] if lado == 'tail' else nuevas[0][1]
                    v['points'] = ruta(tv, hv)
            else:
                dg['ownedViews'] = [x for x in dg['ownedViews'] if x['_id'] != v['_id']]
                quitadas.append(dg.get('name'))
                continue
        etiquetas_asoc(doc, v)
    doc.reindex()
    return quitadas


def etiquetas_asoc(doc, av):
    """Deja texto y visibilidad de multiplicidades y roles como en el modelo (solo toca las que cambian)."""
    a = doc.ids[av['model']['$ref']]
    sub = {s['_id']: s for s in av.get('subViews', [])}
    P = [tuple(float(n) for n in p.split(':')) for p in av['points'].split(';')]
    for lado, e, p in (('tail', a['end1'], P[0]), ('head', a['end2'], P[-1])):
        for clave, valor in (('MultiplicityLabel', e.get('multiplicity', '')),
                             ('RoleNameLabel', ('+' + e['name']) if e.get('name') else '')):
            if lado + clave not in av:
                continue
            l = sub.get(av[lado + clave]['$ref'])
            if l is None:
                continue
            if valor:
                if l.get('text') != valor or l.get('visible') is False:
                    l.pop('visible', None)
                    l['text'] = valor
                    l['width'] = round(6.9 * len(valor) + 2, 2)
                    l['left'] = round(p[0] + (8 if lado == 'tail' else -8 - l['width']))
                    l['top'] = round(p[1] + (6 if clave.startswith('Mult') else -18))
            elif l.get('visible') is not False or 'text' in l:
                l['visible'] = False
                l.pop('text', None); l.pop('width', None)


def vista_asociacion(doc, dg, asoc, tail_v, head_v, medios=()):
    vid = doc.new_id()
    e1, e2 = asoc['end1'], asoc['end2']
    puntos = ruta(tail_v, head_v, medios)
    P = [tuple(float(n) for n in p.split(':')) for p in puntos.split(';')]
    mx = (P[0][0] + P[-1][0]) / 2; my = (P[0][1] + P[-1][1]) / 2
    t, h = P[0], P[-1]

    def lab(model, alpha, dist, pos, vis, x, y):
        l = {'_type': 'EdgeLabelView', '_id': doc.new_id(), '_parent': ref(vid), 'model': ref(model)}
        if vis is not True:
            l['visible'] = vis
        l.update({'font': 'Arial;13;0', 'parentStyle': False, 'left': round(x), 'top': round(y), 'height': 13,
                  'alpha': alpha, 'distance': dist, 'hostEdge': ref(vid)})
        if pos is not None:
            l['edgePosition'] = pos
        return l
    pi2 = math.pi / 2
    subs = [lab(asoc['_id'], pi2, 15, 1, False, mx, my - 15), lab(asoc['_id'], pi2, 30, 1, None, mx, my - 30),
            lab(asoc['_id'], -pi2, 15, 1, False, mx, my + 15),
            lab(e1['_id'], 0.5235987755982988, 30, 2, False, t[0], t[1] - 20),
            lab(e1['_id'], 0.7853981633974483, 40, 2, False, t[0], t[1] - 30),
            lab(e1['_id'], -0.5235987755982988, 25, 2, False, t[0], t[1] + 6),
            lab(e2['_id'], -0.5235987755982988, 30, None, False, h[0], h[1] - 20),
            lab(e2['_id'], -0.7853981633974483, 40, None, False, h[0], h[1] - 30),
            lab(e2['_id'], 0.5235987755982988, 25, None, False, h[0], h[1] + 6)]
    for e in (e1, e2):
        subs.append({'_type': 'UMLQualifierCompartmentView', '_id': doc.new_id(), '_parent': ref(vid), 'model': ref(e['_id']),
                     'visible': False, 'font': 'Arial;13;0', 'parentStyle': True, 'left': round(t[0]), 'top': round(t[1]),
                     'width': 10, 'height': 10})
    av = {'_type': 'UMLAssociationView', '_id': vid, '_parent': ref(dg['_id']), 'model': ref(asoc['_id']), 'subViews': subs,
          'font': 'Arial;13;0', 'parentStyle': False, 'head': ref(head_v['_id']), 'tail': ref(tail_v['_id']),
          'lineStyle': 1, 'points': puntos, 'showVisibility': True,
          'nameLabel': ref(subs[0]['_id']), 'stereotypeLabel': ref(subs[1]['_id']), 'propertyLabel': ref(subs[2]['_id']),
          'showEndOrder': 'hide',
          'tailRoleNameLabel': ref(subs[3]['_id']), 'tailPropertyLabel': ref(subs[4]['_id']), 'tailMultiplicityLabel': ref(subs[5]['_id']),
          'headRoleNameLabel': ref(subs[6]['_id']), 'headPropertyLabel': ref(subs[7]['_id']), 'headMultiplicityLabel': ref(subs[8]['_id']),
          'tailQualifiersCompartment': ref(subs[9]['_id']), 'headQualifiersCompartment': ref(subs[10]['_id'])}
    dg.setdefault('ownedViews', []).append(av)
    etiquetas_asoc(doc, av)
    return av


def linea_ruta(doc, dg, v, medios):
    tail = [x for x in dg.get('ownedViews', []) if x['_id'] == v.get('tail', {}).get('$ref')]
    head = [x for x in dg.get('ownedViews', []) if x['_id'] == v.get('head', {}).get('$ref')]
    if not tail or not head:
        raise MdjError('La linea no tiene sus dos cajas en el mismo diagrama')
    v['points'] = ruta(tail[0], head[0], medios)
    if v['_type'] == 'UMLAssociationView':
        etiquetas_asoc(doc, v)
    return v['points']


# ---------------------------------------------------------------------------
# Edicion: borrar
# ---------------------------------------------------------------------------

def borrar(doc, el):
    """Borra un elemento, lo que contiene, las relaciones que lo tocan y todas sus vistas."""
    quitar = set()

    def junta(o):
        if isinstance(o, dict):
            if '_id' in o:
                quitar.add(o['_id'])
            for x in o.values():
                junta(x)
        elif isinstance(o, list):
            for x in o:
                junta(x)
    junta(el)
    for o in list(doc.ids.values()):
        if not o:
            continue
        if o['_type'] == 'UMLAssociation' and (o['end1']['reference']['$ref'] in quitar or o['end2']['reference']['$ref'] in quitar):
            junta(o)
        elif o['_type'] in ('UMLGeneralization', 'UMLRealization', 'UMLDependency', 'UMLInterfaceRealization', 'UMLInclude', 'UMLExtend') \
                and (o['source']['$ref'] in quitar or o['target']['$ref'] in quitar):
            junta(o)
    vistas = set()
    for dg in doc.diagrams():
        for v in dg.get('ownedViews', []):
            m = v.get('model')
            if isinstance(m, dict) and m.get('$ref') in quitar:
                vistas.add(v['_id'])
    # lineas cuyas cajas se van
    for dg in doc.diagrams():
        for v in dg.get('ownedViews', []):
            if v.get('tail', {}).get('$ref') in vistas or v.get('head', {}).get('$ref') in vistas:
                vistas.add(v['_id'])

    def poda(o):
        if isinstance(o, dict):
            for k, x in list(o.items()):
                if isinstance(x, list):
                    o[k] = [e for e in x if not (isinstance(e, dict) and (e.get('_id') in quitar or e.get('_id') in vistas))]
                    for e in o[k]:
                        poda(e)
                elif isinstance(x, dict):
                    poda(x)
        elif isinstance(o, list):
            for e in o:
                poda(e)
    poda(doc.d)
    doc.reindex()
    # lo que todavia apunta a algo borrado: los 'type' (roles de lifelines, atributos tipados) se vacian y las
    # listas de referencias (constrainedElements, containedViews...) pierden esa entrada;
    # cualquier otra referencia es un problema y no se deja pasar
    tipos_vaciados, colgantes, refs_quitadas = [], [], []
    borrado = lambda x: isinstance(x, dict) and set(x) == {'$ref'} and (x['$ref'] in quitar or x['$ref'] in vistas)

    def revisa(o, path=''):
        if isinstance(o, dict):
            for k, x in list(o.items()):
                if borrado(x):
                    if k == 'type':
                        o[k] = ''
                        tipos_vaciados.append(f"{o.get('_type')} {o.get('name', '')}")
                    else:
                        colgantes.append(f"{o.get('_type')} {o.get('_id')} .{k}")
                else:
                    if isinstance(x, list) and any(borrado(e) for e in x):
                        o[k] = x = [e for e in x if not borrado(e)]
                        refs_quitadas.append(f"{o.get('_type')} {o.get('name', '')} .{k}")
                    revisa(x, path + '/' + k)
        elif isinstance(o, list):
            for x in o:
                revisa(x, path)
    revisa(doc.d)
    if colgantes:
        raise MdjError('No se puede borrar sin dejar referencias colgantes: ' + '; '.join(colgantes[:8]))
    return {'elementos_borrados': len(quitar), 'vistas_borradas': len(vistas), 'tipos_vaciados': tipos_vaciados,
            'referencias_quitadas': refs_quitadas}


# ---------------------------------------------------------------------------
# Secuencia: generador completo
# ---------------------------------------------------------------------------

AR13 = {**{c: 556 for c in 'abdeghnopqu0123456789'}, **{c: 500 for c in 'cksvxyz'}, **{c: 222 for c in 'ijl'},
        **{c: 278 for c in 'ft ,.:;I'}, 'r': 333, 'm': 833, 'w': 722, '(': 333, ')': 333, '-': 333, '_': 556,
        **{c: 667 for c in 'ABEKPSVXY'}, **{c: 722 for c in 'CDHNRU'}, **{c: 778 for c in 'GOQ'}, 'F': 611, 'T': 611,
        'L': 556, 'M': 833, 'J': 500, 'W': 944, 'Z': 611}


def ancho13(t):
    return sum(AR13.get(c, 556) for c in t) * 13 / 1000


def _ids_y_refs(o):
    """Ids definidos dentro de o, e ids a los que o hace referencia."""
    ids, refs = set(), set()

    def walk(x):
        if isinstance(x, dict):
            if '_id' in x:
                ids.add(x['_id'])
            if '$ref' in x and len(x) == 1:
                refs.add(x['$ref'])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(o)
    return ids, refs


def _opciones_secuencia(opciones):
    op = {'y_inicio': 152, 'espaciado': [29, 36], 'espaciado_izq_der': [50, 56], 'extra_flujo': [22, 34],
          'semilla': 24092026, 'margen_etiqueta': 30, 'separacion_minima': 170}
    es_num = lambda n: isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)
    for k, v in (opciones or {}).items():
        if k not in op:
            raise MdjError(f'Opcion desconocida "{k}". Validas: {sorted(op)}')
        if k in ('espaciado', 'espaciado_izq_der', 'extra_flujo'):
            if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(es_num(n) for n in v) and 0 <= v[0] <= v[1]):
                raise MdjError(f'"{k}" debe ser [minimo, maximo] con 0 <= minimo <= maximo')
            v = [int(round(v[0])), int(round(v[1]))]
        elif k == 'semilla':
            if not (es_num(v) or isinstance(v, str)):
                raise MdjError('"semilla" debe ser un numero o un texto')
        elif not es_num(v) or v < 0:
            raise MdjError(f'"{k}" debe ser un numero >= 0')
        op[k] = v
    return op


def generar_secuencia(doc, diagrama, lifelines, mensajes, opciones=None):
    """Rehace por completo un diagrama de secuencia.
    lifelines: [{'clave': 'asesor', 'tipo': 'Asesor de Renta'}, ...] en orden de izquierda a derecha.
    mensajes: [{'de': clave, 'a': clave, 'nombre': 'buscarCliente(rfc)', 'reply': False, 'flujo': 'F1'}, ...]
    """
    op = _opciones_secuencia(opciones)
    rnd = random.Random(op['semilla'])
    dg = doc.diagram(diagrama)
    if dg['_type'] != 'UMLSequenceDiagram':
        raise MdjError(f'{dg.get("name")} no es un diagrama de secuencia')
    inter = interaction_of(doc, dg)
    colab = doc.ids.get(doc.parent.get(inter['_id']))
    if not colab or colab['_type'] != 'UMLCollaboration':
        raise MdjError('La interaccion no cuelga de una colaboracion')
    if not lifelines or not mensajes:
        raise MdjError('Se necesita al menos una lifeline y un mensaje')
    claves = [l['clave'] for l in lifelines]
    if len(set(claves)) != len(claves):
        raise MdjError('Hay claves de lifeline repetidas')
    for m in mensajes:
        for k in ('de', 'a', 'nombre'):
            if not m.get(k):
                raise MdjError(f'Falta "{k}" en un mensaje: {m}')
        for k in ('de', 'a'):
            if m[k] not in claves:
                raise MdjError(f'El mensaje "{m.get("nombre")}" usa la lifeline "{m[k]}", que no esta en la lista')
        if m['de'] == m['a']:
            raise MdjError(f'El mensaje "{m["nombre"]}" va de una lifeline a si misma; el generador no dibuja auto-mensajes')

    # roles y lifelines: se reusan los que ya existen para ese tipo (primero el rol que se llama como la clave),
    # pero cada clave recibe los suyos: dos lifelines del mismo tipo nunca comparten rol ni objeto
    roles_de, lls_de = {}, {}
    for a in colab.get('attributes', []):
        if isinstance(a.get('type'), dict):
            roles_de.setdefault(a['type']['$ref'], []).append(a)
    for l in inter.get('participants', []):
        if l.get('represent'):
            lls_de.setdefault(l['represent']['$ref'], []).append(l)
    viejos_ll = {l['_id'] for l in inter.get('participants', [])}
    roles_viejos = {l['represent']['$ref'] for l in inter.get('participants', []) if l.get('represent')}
    lifeline, tipo_de, participantes, asignados = {}, {}, [], set()
    for l in lifelines:
        t = doc.find(l['tipo'], types=('UMLClass', 'UMLActor', 'UMLInterface'))
        tipo_de[l['clave']] = t
        libres = [r for r in roles_de.get(t['_id'], []) if r['_id'] not in asignados]
        rol = next((r for r in libres if r.get('name') == l['clave']), libres[0] if libres else None)
        if rol is None:
            rol = {'_type': 'UMLAttribute', '_id': doc.new_id(), '_parent': ref(colab['_id']), 'name': l['clave'], 'type': ref(t['_id'])}
            colab.setdefault('attributes', []).append(rol)
            roles_de.setdefault(t['_id'], []).append(rol)
        else:
            rol['name'] = l['clave']
        ll = next((x for x in lls_de.get(rol['_id'], []) if x['_id'] not in asignados), None)
        if ll is None:
            ll = {'_type': 'UMLLifeline', '_id': doc.new_id(), '_parent': ref(inter['_id']), 'represent': ref(rol['_id']), 'isMultiInstance': False}
        asignados.update((rol['_id'], ll['_id']))
        for k in ('name', 'stereotype'):
            ll.pop(k, None)
        participantes.append(ll)
        lifeline[l['clave']] = ll['_id']
    inter['participants'] = participantes

    # posicion horizontal: la etiqueta mas larga entre dos lifelines no debe pisar las activaciones
    orden = {c: i for i, c in enumerate(claves)}
    minimo = {}
    for k, m in enumerate(mensajes):
        i, j = sorted((orden[m['de']], orden[m['a']]))
        if i != j:
            minimo[(i, j)] = max(minimo.get((i, j), 0), ancho13(f'{k + 1} : {m["nombre"]}') + op['margen_etiqueta'])
    centro_ll, ancho_ll = {}, {}
    x = None; prev_w = None
    for j, c in enumerate(claves):
        texto = ': ' + (tipo_de[c].get('name') or '')
        w = max(96, round(7.4 * len(texto) + 22))
        if prev_w is None:
            x = 24 + w / 2
        else:
            x += max(op['separacion_minima'], (prev_w + w) / 2 + 44) + rnd.randint(-6, 14)
        for (a, b), mn in minimo.items():
            if b == j and x < centro_ll[claves[a]] + mn:
                x = centro_ll[claves[a]] + mn + rnd.randint(0, 8)
        centro_ll[c] = int(x); ancho_ll[c] = w; prev_w = w
    min_izq = min([(centro_ll[m['de']] + centro_ll[m['a']]) / 2 - ancho13(f'{k + 1} : {m["nombre"]}') / 2 for k, m in enumerate(mensajes)] +
                  [centro_ll[c] - ancho_ll[c] / 2 for c in claves])
    if min_izq < 22:
        corr = int(22 - min_izq) + rnd.randint(2, 7)
        for c in centro_ll:
            centro_ll[c] += corr

    # posicion vertical
    flujo_de = [m.get('flujo') for m in mensajes]
    izq_de = [centro_ll[m['a']] < centro_ll[m['de']] for m in mensajes]
    salto = []
    for k in range(len(mensajes)):
        g = 0
        if k > 0:
            if flujo_de[k] != flujo_de[k - 1]:
                g += rnd.randint(*op['extra_flujo'])
            g += rnd.randint(*op['espaciado_izq_der']) if (izq_de[k - 1] and not izq_de[k]) else rnd.randint(*op['espaciado'])
        salto.append(g)
    extra = [0] * len(mensajes)

    def armar():
        y = op['y_inicio']; plan = []
        for k, m in enumerate(mensajes):
            y += salto[k] + extra[k]
            plan.append((m['de'], m['a'], m['nombre'], bool(m.get('reply')), y))
        return plan

    def activaciones(plan):
        alto, pila = {}, []

        def cerrar(e, y_fin=None):
            alto[e['k']] = max(y_fin - e['y0'], 20) if y_fin is not None else max(28, e['ultimo'] - e['y0'] + 10)
        for k, (o, t, nom, rep, y) in enumerate(plan):
            if rep:
                while pila and pila[-1]['ll'] != o:
                    cerrar(pila.pop())
                if pila:
                    cerrar(pila.pop(), y)
                if pila and pila[-1]['ll'] == t:
                    pila[-1]['ultimo'] = y
                continue
            if any(e['ll'] == o for e in pila):
                while pila[-1]['ll'] != o:
                    cerrar(pila.pop())
                pila[-1]['ultimo'] = y
            else:
                while pila:
                    cerrar(pila.pop())
            pila.append({'ll': t, 'y0': y, 'k': k, 'ultimo': y})
        while pila:
            cerrar(pila.pop())
        return alto
    empujados = []
    for vuelta in range(120):
        plan = armar(); alto = activaciones(plan)
        cajas = [(centro_ll[plan[k][1]] - 7, plan[k][4], centro_ll[plan[k][1]] + 7, plan[k][4] + h) for k, h in alto.items()]
        choque = None
        for k, (o, t, nom, rep, y) in enumerate(plan):
            lw = ancho13(f'{k + 1} : {nom}') + 4; mx = (centro_ll[o] + centro_ll[t]) / 2
            top, bot = (y + 3, y + 16) if izq_de[k] else (y - 16, y - 3)
            for (x0, y0, x1, y1) in cajas:
                if x0 - 3 < mx + lw / 2 and x1 + 3 > mx - lw / 2 and y0 < bot and y1 + 2 > top:
                    choque = (k, y1 + 2 - top + rnd.randint(1, 3)); break
            if choque:
                break
        if not choque:
            break
        extra[choque[0]] += choque[1]
    else:
        empujados.append('AVISO: quedaron etiquetas sobre activaciones')
    empujados += [f'mensaje {k + 1} bajado {e}px' for k, e in enumerate(extra) if e]
    fin = plan[-1][4] + 60
    H = fin - 40

    # vistas: se regeneran las de lifelines y mensajes; el marco, las notas y lo demas se conservan
    regeneradas = ('UMLSeqLifelineView', 'UMLSeqMessageView')
    previas = dg.get('ownedViews', [])
    frames = [v for v in previas if v['_type'] == 'UMLFrameView']
    otras = [v for v in previas if v['_type'] not in regeneradas and v['_type'] != 'UMLFrameView']
    vistas = list(frames)
    linepart = {}
    for c in claves:
        t = tipo_de[c]; cx, w = centro_ll[c], ancho_ll[c]; left = cx - w // 2
        vid, ncid, l0, l1, l2, l3, lp = [doc.new_id() for _ in range(7)]
        k = doc.kind(t)
        lab0 = {'_type': 'LabelView', '_id': l0, '_parent': ref(ncid), 'visible': False, 'font': 'Arial;13;0', 'parentStyle': True,
                'left': left, 'top': 87, 'width': w - 9, 'height': 13}
        if k in ('entity', 'boundary', 'control'):
            lab0['text'] = f'«{k}»'
        ll_id = lifeline[c]
        v = {'_type': 'UMLSeqLifelineView', '_id': vid, '_parent': ref(dg['_id']), 'model': ref(ll_id),
             'subViews': [
                 {'_type': 'UMLNameCompartmentView', '_id': ncid, '_parent': ref(vid), 'model': ref(ll_id),
                  'subViews': [lab0,
                               {'_type': 'LabelView', '_id': l1, '_parent': ref(ncid), 'font': 'Arial;13;1', 'parentStyle': True,
                                'left': left + 5, 'top': 87, 'width': w - 9, 'height': 13, 'text': ': ' + (t.get('name') or '')},
                               {'_type': 'LabelView', '_id': l2, '_parent': ref(ncid), 'visible': False, 'font': 'Arial;13;0', 'parentStyle': True,
                                'left': left, 'top': 87, 'width': 103.30810546875, 'height': 13, 'text': f'(from {inter.get("name", "")})'},
                               {'_type': 'LabelView', '_id': l3, '_parent': ref(ncid), 'visible': False, 'font': 'Arial;13;0', 'parentStyle': True,
                                'left': left, 'top': 87, 'height': 13, 'horizontalAlignment': 1}],
                  'font': 'Arial;13;0', 'parentStyle': True, 'left': left, 'top': 80, 'width': w + 1, 'height': 25,
                  'stereotypeLabel': ref(l0), 'nameLabel': ref(l1), 'namespaceLabel': ref(l2), 'propertyLabel': ref(l3)},
                 {'_type': 'UMLLinePartView', '_id': lp, '_parent': ref(vid), 'model': ref(ll_id), 'font': 'Arial;13;0',
                  'parentStyle': False, 'left': cx, 'top': 106, 'width': 1, 'height': H - 66}],
             'font': 'Arial;13;0', 'parentStyle': False, 'left': left, 'top': 40, 'width': w, 'height': H,
             'stereotypeDisplay': 'icon', 'nameCompartment': ref(ncid), 'linePart': ref(lp)}
        vistas.append(v)
        linepart[c] = lp
    nuevos = []
    for k, (o, t, nom, rep, y) in enumerate(plan):
        mid = doc.new_id()
        m = {'_type': 'UMLMessage', '_id': mid, '_parent': ref(inter['_id']), 'name': nom,
             'source': ref(lifeline[o]), 'target': ref(lifeline[t])}
        if rep:
            m['messageSort'] = 'reply'
        nuevos.append(m)
        xo, xt = centro_ll[o], centro_ll[t]
        texto = f'{k + 1} : {nom}'
        lw = round(ancho13(texto) + 4, 2); mx = (xo + xt) / 2
        vid = doc.new_id(); sv = [doc.new_id() for _ in range(4)]
        v = {'_type': 'UMLSeqMessageView', '_id': vid, '_parent': ref(dg['_id']), 'model': ref(mid),
             'subViews': [
                 {'_type': 'EdgeLabelView', '_id': sv[0], '_parent': ref(vid), 'model': ref(mid), 'font': 'Arial;13;0',
                  'parentStyle': True, 'left': round(mx - lw / 2), 'top': y - 16 if xt > xo else y + 3, 'width': lw, 'height': 13,
                  'alpha': 1.5707963267948966, 'distance': 10, 'hostEdge': ref(vid), 'edgePosition': 1, 'text': texto},
                 {'_type': 'EdgeLabelView', '_id': sv[1], '_parent': ref(vid), 'model': ref(mid), 'visible': False,
                  'font': 'Arial;13;0', 'parentStyle': True, 'left': round(mx), 'top': y - 31, 'height': 13,
                  'alpha': 1.5707963267948966, 'distance': 25, 'hostEdge': ref(vid), 'edgePosition': 1},
                 {'_type': 'EdgeLabelView', '_id': sv[2], '_parent': ref(vid), 'model': ref(mid), 'visible': False,
                  'font': 'Arial;13;0', 'parentStyle': True, 'left': round(mx), 'top': y + 4, 'height': 13,
                  'alpha': -1.5707963267948966, 'distance': 10, 'hostEdge': ref(vid), 'edgePosition': 1},
                 {'_type': 'UMLActivationView', '_id': sv[3], '_parent': ref(vid), 'model': ref(mid), 'font': 'Arial;13;0',
                  'parentStyle': True, 'left': xt - 7, 'top': y, 'width': 14, 'height': 25 if rep else alto[k]}],
             'font': 'Arial;13;0', 'parentStyle': False, 'head': ref(linepart[t]), 'tail': ref(linepart[o]),
             'points': f'{xo}:{y};{xt}:{y}',
             'nameLabel': ref(sv[0]), 'stereotypeLabel': ref(sv[1]), 'propertyLabel': ref(sv[2]), 'activation': ref(sv[3])}
        if rep:
            v['subViews'][3]['visible'] = False
        vistas.append(v)
    # lo conservado que cuelga de una vista regenerada (p. ej. el enlace de una nota a una lifeline vieja) se descarta
    # y se reporta; lo demas queda encima de lo generado
    quitados, descartadas = _ids_y_refs([v for v in previas if v['_type'] in regeneradas])[0], []
    while True:
        colgadas = [v for v in otras if _ids_y_refs(v)[1] & quitados]
        if not colgadas:
            break
        for v in colgadas:
            otras.remove(v)
            quitados |= _ids_y_refs(v)[0]
            descartadas.append(v['_type'])
    vistas += otras
    inter['messages'] = nuevos
    dg['ownedViews'] = vistas
    derecha = max(centro_ll[c] + ancho_ll[c] - ancho_ll[c] // 2 for c in claves)
    derecha = max([derecha] + [round((centro_ll[m['de']] + centro_ll[m['a']]) / 2 + ancho13(f'{k + 1} : {m["nombre"]}') / 2) for k, m in enumerate(mensajes)])
    for fr in frames:
        fr['left'] = 8; fr['top'] = 10; fr['width'] = derecha + 28 - 8; fr['height'] = fin + 26 - 10
        for s in fr.get('subViews', []):
            s['top'] = 15
            s['left'] = 13 if s.get('text') == 'sd' else 32.72998046875
    # lifelines viejas que ya no se usan: fuera de la interaccion; sus roles solo si nadie mas los usa
    doc.reindex()
    usados = set(re.findall(r'"\$ref": "([^"]+)"', json.dumps(doc.d)))
    nuevos_ll = {l['_id'] for l in participantes}
    roles_libres = [r for r in roles_viejos if r not in usados and r not in {l['represent']['$ref'] for l in participantes}]
    colab['attributes'] = [a for a in colab.get('attributes', []) if a['_id'] not in roles_libres]
    doc.reindex()
    return {'mensajes': len(nuevos), 'lifelines': len(participantes), 'alto': fin, 'ancho': derecha,
            'lifelines_quitadas': len(viejos_ll - nuevos_ll), 'roles_quitados': len(roles_libres), 'ajustes': empujados,
            'vistas_conservadas': len(otras), 'vistas_descartadas': descartadas}
