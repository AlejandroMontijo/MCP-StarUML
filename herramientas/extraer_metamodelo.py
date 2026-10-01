# Extrae del StarUML instalado la tabla de metamodelo que usa el servidor (staruml_metamodelo.json).
# StarUML trae su metamodelo dentro de resources/app.asar: un metamodel.json por extension (uml, bpmn, sysml...)
# y uno del nucleo (Element, Model, View...). Aqui solo se guarda lo que hace falta para crear y validar archivos:
# herencia, si el tipo es abstracto, sus atributos (nombre, kind, type), la vista de cada elemento, las vistas que
# admite cada diagrama y la paleta (toolbox) de cada diagrama, que es la simbologia que StarUML ofrece en cada uno. El JSON original de StarUML no se versiona.
#
# Uso: python herramientas/extraer_metamodelo.py [ruta/a/app.asar | ruta/a/StarUML(.exe)]
#      sin argumento usa STARUML_MCP_STARUML_BIN o las rutas tipicas (las mismas de staruml_cli()).
import json
import os
import struct
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

import staruml_mdj as M  # noqa: E402

SALIDA = os.path.join(RAIZ, 'staruml_metamodelo.json')


def ruta_asar(arg=None):
    """app.asar a partir del argumento, del ejecutable de StarUML o de las rutas tipicas."""
    p = arg or M.staruml_cli()
    if not p:
        raise SystemExit('No encuentro StarUML; pasa la ruta a app.asar o define STARUML_MCP_STARUML_BIN')
    if p.endswith('.asar'):
        return p
    d = os.path.dirname(os.path.realpath(p))
    for c in (os.path.join(d, 'resources', 'app.asar'),                  # Windows y Linux
              os.path.join(d, '..', 'Resources', 'app.asar')):           # macOS (Contents/MacOS/StarUML)
        if os.path.exists(c):
            return os.path.normpath(c)
    raise SystemExit(f'No encuentro app.asar junto a {p}')


def leer_asar(ruta, quiero):
    """Devuelve {ruta_interna: bytes} de los archivos del asar para los que quiero(ruta_interna) es verdadero.
    Formato asar: [4][tam_encabezado][4][tam_json][json] y luego los archivos, con offset relativo a 8+tam_encabezado."""
    with open(ruta, 'rb') as f:
        _, tam, _, tam_json = struct.unpack('<4I', f.read(16))
        enc = json.loads(f.read(tam_json))
        base = 8 + tam
        hallados = {}

        def recorrer(nodo, camino):
            for nombre, v in nodo.get('files', {}).items():
                q = f'{camino}/{nombre}'
                if 'files' in v:
                    if 'node_modules' not in q:
                        recorrer(v, q)
                elif 'offset' in v and quiero(q):
                    hallados[q] = (int(v['offset']), v['size'])
        recorrer(enc, '')
        datos = {}
        for q, (off, size) in hallados.items():
            f.seek(base + off)
            datos[q] = f.read(size)
    return datos


def leer_staruml(ruta):
    """Metamodelos {origen: dict}, paletas [(origen, grupos)] y version de StarUML."""
    datos = leer_asar(ruta, lambda q: q == '/package.json' or q.endswith('/metamodel.json') or '/toolbox/' in q)
    version = json.loads(datos['/package.json']).get('version') if '/package.json' in datos else None
    metamodelos, paletas = {}, []
    for q, b in sorted(datos.items()):
        partes = q.strip('/').split('/')
        origen = partes[2] if partes[0] == 'extensions' and len(partes) > 3 else 'core'
        if q.endswith('/metamodel.json'):
            metamodelos[origen] = json.loads(b)
        elif '/toolbox/' in q:
            paletas.append((origen, json.loads(b)))
    return metamodelos, paletas, version


def compactar_paletas(paletas):
    """Paleta de cada diagrama, como la muestra StarUML: {diagrama: [{grupo, label, id, forma, command?, arg?}]}."""
    por_diagrama = {}
    for origen, grupos in paletas:
        for g in grupos:
            for it in g.get('items', []):
                e = {'grupo': g.get('label'), 'label': it['label'], 'id': it['id'],
                     'forma': it.get('rubberband', 'rect'), 'origen': origen}
                if it.get('command'):
                    e['command'] = it['command']
                if it.get('command-arg'):
                    e['arg'] = it['command-arg']
                for d in g.get('diagram-types', []):
                    por_diagrama.setdefault(d, []).append(e)
    return por_diagrama


def compactar(metamodelos):
    """{origen: metamodelo} -> tabla compacta {tipo: {...}}."""
    tipos = {}
    for origen, mm in sorted(metamodelos.items()):
        for nombre, d in mm.items():
            if d.get('kind') == 'enum':
                tipos[nombre] = {'kind': 'enum', 'origen': origen,
                                 'literales': [x if isinstance(x, str) else x.get('name') for x in d.get('literals', [])]}
                continue
            t = {'kind': 'class', 'origen': origen}
            for k in ('super', 'view', 'views'):
                if d.get(k):
                    t[k] = d[k]
            if d.get('abstract'):
                t['abstract'] = True
            atrs = [{'name': a['name'], 'kind': a['kind'], 'type': a['type']} for a in d.get('attributes', [])]
            if atrs:
                t['attributes'] = atrs
            tipos[nombre] = t
    return tipos


def main(argv):
    asar = ruta_asar(argv[1] if len(argv) > 1 else None)
    metamodelos, paletas, version = leer_staruml(asar)
    tabla = {'staruml': version, 'tipos': compactar(metamodelos), 'paletas': compactar_paletas(paletas)}
    with open(SALIDA, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(tabla, f, ensure_ascii=False, indent='\t', sort_keys=True)
        f.write('\n')
    print(f'{len(tabla["tipos"])} tipos de {len(metamodelos)} metamodelos y paletas de {len(tabla["paletas"])} diagramas '
          f'(StarUML {version}) -> {SALIDA}')


if __name__ == '__main__':
    main(sys.argv)
