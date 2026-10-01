# Saca plantillas_vistas.json del .mdj de referencia que dibujo StarUML (herramientas/generar_referencia.py).
# Por cada simbolo de cada paleta guarda exactamente lo que StarUML creo al dibujarlo: los elementos de modelo y las
# vistas (con sus subvistas, etiquetas y compartimentos), con los ids cambiados por marcadores:
#   @0, @1...         objetos creados por el simbolo
#   @diagrama         el diagrama donde se dibujo
#   @dueno            el dueno de los elementos del diagrama (diagram._parent)
#   @cola, @cabeza    vistas a las que se conecto (lineas) o sobre las que se puso (puertos, pines, regiones...)
#   @cola_m, @cabeza_m  sus elementos de modelo
#   @ext              cualquier otra referencia: se guarda tipo y nombre para resolverla en el archivo destino
# staruml_uml.dibujar() instancia una plantilla en cualquier diagrama del mismo tipo.
#
# Uso: python herramientas/extraer_plantillas.py [carpeta_referencia]   (por defecto pruebas/referencia)
import copy
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

import staruml_mdj as M  # noqa: E402

SALIDA = os.path.join(RAIZ, 'plantillas_vistas.json')


def campo_en_padre(padre, obj):
    for k, v in padre.items():
        if v is obj:
            return k, False
        if isinstance(v, list) and any(x is obj for x in v):
            return k, True
    return None, None


def geometria_base(v):
    """Punto de referencia de una vista: esquina de una caja o el primer punto de una linea."""
    if isinstance(v.get('left'), (int, float)) and isinstance(v.get('top'), (int, float)):
        return v['left'], v['top']
    pts = v.get('points')
    if isinstance(pts, str) and pts:
        x, y = pts.split(';')[0].split(':')
        return float(x), float(y)
    return 0, 0


def plantilla(doc, e, ajenos, otros):
    creados = [i for i in e.get('vistas_nuevas', []) + e.get('modelos_nuevos', []) if doc.ids.get(i)]
    if not creados:
        return None, 'los objetos creados ya no estan en el archivo'
    cre = set(creados)
    # diagrama: el que contiene la vista principal
    vista = doc.ids.get(e.get('vista_id')) or doc.ids[e['vistas_nuevas'][0]]
    i = vista['_id']
    while i in doc.parent and 'Diagram' not in doc.ids[i]['_type']:
        i = doc.parent[i]
    dg = doc.ids[i]
    # @dueno es el contenedor del diagrama (o donde se pidio el diagrama) y @dueno2, @dueno3... sus ancestros
    inicio = e['padre_id'] if e['forma'] == 'diagrama' else dg['_parent']['$ref']
    externos = {} if e['forma'] == 'diagrama' else {dg['_id']: '@diagrama'}
    n, i = 1, inicio
    while i:
        externos.setdefault(i, '@dueno' if n == 1 else f'@dueno{n}')
        n, i = n + 1, doc.parent.get(i)
    for k in ('cola', 'cabeza'):
        vid = e.get(f'{k}_id')
        if vid and vid in doc.ids:
            externos.setdefault(vid, f'@{k}')
            m = doc.ids[vid].get('model')
            if isinstance(m, dict):
                externos.setdefault(m['$ref'], f'@{k}_m')
    marca = {i: f'@{n}' for n, i in enumerate(creados)}
    raices = [i for i in creados if doc.parent.get(i) not in cre]
    x0, y0 = geometria_base(vista)
    ext = {}

    def nombre_ref(rid, preferir=None):
        if rid in marca:
            return marca[rid]
        if rid in externos:
            return externos[rid]
        if rid in ajenos:
            # si cuelga de algo conocido (la region de la maquina de estados que creo el diagrama...) se guarda
            # como ruta desde ese marcador: @dueno/regions/0; si no, lo creo otro simbolo y no es parte de esta
            return ruta_desde(rid, preferir)
        o = doc.ids.get(rid)
        ext[rid] = {'tipo': o['_type'] if o else None, 'nombre': o.get('name') if o else None}
        return f'@ext:{rid}'

    def ruta_desde(rid, preferir=None):
        """Camino mas corto (hasta 4 pasos) desde un marcador conocido hasta rid: 'campo/indice' baja a un hijo,
        '>campo' sigue una referencia y '..' sube al padre. No se baja por indice a objetos de otros simbolos (lo que
        una contencion metio ahi), pero si se sigue una referencia a ellos (la lifeline de la que sale un mensaje)."""
        inicio = [(i, m) for i, m in externos.items() if i in doc.ids]
        if preferir:  # con empate, el destino se busca desde @cabeza y el origen desde @cola
            inicio.sort(key=lambda x: not x[1].startswith(preferir))
        vistos = {i for i, _ in inicio}
        capa = inicio
        for _ in range(4):
            siguiente = []
            for i, camino in capa:
                o = doc.ids[i]
                pasos = []
                for k, v in o.items():
                    if isinstance(v, dict) and set(v) == {'$ref'} and k != '_parent':
                        pasos.append((f'>{k}', v['$ref']))
                if i in doc.parent:
                    pasos.append(('..', doc.parent[i]))
                for k, v in o.items():
                    if isinstance(v, dict) and isinstance(v.get('_id'), str):
                        pasos.append((k, v['_id']))
                    elif isinstance(v, list):
                        for n, x in enumerate(v):
                            if isinstance(x, dict) and isinstance(x.get('_id'), str) and x['_id'] not in otros:
                                pasos.append((f'{k}/{n}', x['_id']))
                for paso, j in pasos:
                    if j == rid:
                        return f'{camino}/{paso}'
                    if j in vistos or j not in doc.ids or j in marca:
                        continue
                    vistos.add(j)
                    siguiente.append((j, f'{camino}/{paso}'))
            capa = siguiente
        return None

    def propio(v):
        return not (isinstance(v, dict) and isinstance(v.get('_id'), str) and v['_id'] not in marca)

    # una linea dibujada de una vista a si misma: el destino se distingue por el campo, como lo guarda StarUML
    mismo = e.get('cola_id') and e.get('cola_id') == e.get('cabeza_id')
    destino_m = doc.ids[e['cabeza_id']].get('model', {}).get('$ref') if mismo else None

    def ref_en(k, rid, dentro):
        if mismo and rid == e['cabeza_id'] and k == 'head':
            return '@cabeza'
        if mismo and rid == destino_m and (k == 'target' or (k == 'reference' and dentro == 'end2')):
            return '@cabeza_m'
        destino = k in ('target', 'head') or (k == 'reference' and dentro == 'end2')
        origen = k in ('source', 'tail') or (k == 'reference' and dentro == 'end1')
        return nombre_ref(rid, '@cabeza' if destino else '@cola' if origen else None)

    def normal(o, dentro=None):
        # se quitan los objetos que otros simbolos agregaron despues dentro de este (un puerto en un componente...)
        if isinstance(o, dict):
            r = {}
            for k, v in o.items():
                if k == '_id':
                    r[k] = marca[v]
                elif isinstance(v, dict) and set(v) == {'$ref'}:
                    n = ref_en(k, v['$ref'], dentro)
                    if n is not None:
                        r[k] = {'$ref': n}
                elif isinstance(v, list) and v and all(isinstance(x, dict) and set(x) == {'$ref'} for x in v):
                    r[k] = [{'$ref': n} for n in (nombre_ref(x['$ref']) for x in v) if n is not None]
                elif propio(v):
                    r[k] = normal(v, k)
            return r
        if isinstance(o, list):
            return [normal(x, dentro) for x in o if propio(x)]
        return o

    objetos = []
    for rid in raices:
        obj = doc.ids[rid]
        pid = doc.parent[rid]
        campo, lista = campo_en_padre(doc.ids[pid], obj)
        # un marcador conocido manda (el componente sobre el que va el puerto); si no, lo que otro simbolo creo no
        # sirve de padre (una contencion lo metio ahi despues)
        padre = nombre_ref(pid) if pid in externos or pid in marca or pid not in otros else None
        if padre is None:
            # una contencion dibujada despues lo movio dentro de otro simbolo; al crearse estaba en el dueno
            padre, campo, lista = '@dueno', 'ownedElements', True
        o = normal(copy.deepcopy(obj))
        o['_parent'] = {'$ref': padre}
        objetos.append({'padre': padre, 'campo': campo, 'lista': lista, 'objeto': o})
    modelo_principal = vista.get('model', {}).get('$ref') if isinstance(vista.get('model'), dict) else None
    p = {'forma': e['forma'], 'vista': vista['_type'], 'principal': marca.get(vista['_id']),
         'modelo': marca.get(modelo_principal) or (externos.get(modelo_principal) if modelo_principal else None),
         'nombre': doc.ids[modelo_principal].get('name') if modelo_principal in doc.ids else None,
         'origen': [x0, y0], 'objetos': objetos}
    for k in ('cola', 'cabeza'):
        if e.get(f'{k}_id'):
            p[k] = doc.ids[e[f'{k}_id']]['_type'] if e[f'{k}_id'] in doc.ids else None
    if ext:
        p['externos'] = {f'@ext:{k}': v for k, v in ext.items()}
    return p, None


def main(argv):
    carpeta = os.path.abspath(argv[1] if len(argv) > 1 else os.path.join(RAIZ, 'pruebas', 'referencia'))
    doc = M.Doc(os.path.join(carpeta, 'referencia.mdj'))
    with open(os.path.join(carpeta, 'reporte.json'), encoding='utf-8') as f:
        reporte = json.load(f)
    plantillas, diagramas, omitidos = {}, {}, []
    creados_por = {}
    for e in reporte:
        for i in e.get('vistas_nuevas', []) + e.get('modelos_nuevos', []):
            creados_por.setdefault(i, len(creados_por))
    todos = set(creados_por)
    de_simbolos = {i for e in reporte if e.get('forma') != 'diagrama'
                   for i in e.get('vistas_nuevas', []) + e.get('modelos_nuevos', [])}
    for e in reporte:
        clave = f'{e.get("label")}|{e.get("id")}' if e.get('forma') != 'diagrama' else e['diagrama']
        if e.get('copia'):
            continue  # copias para tener dos vistas del mismo tipo, o la linea que unio una vista consigo misma
        if not e.get('ok'):
            omitidos.append({'diagrama': e['diagrama'], 'simbolo': clave, 'motivo': e.get('error')})
            continue
        propios = set(e.get('vistas_nuevas', []) + e.get('modelos_nuevos', []))
        p, motivo = plantilla(doc, e, todos - propios, de_simbolos - propios)
        if p is None:
            omitidos.append({'diagrama': e['diagrama'], 'simbolo': clave, 'motivo': motivo})
            continue
        if e['forma'] == 'diagrama':
            p['dueno'] = e.get('padre_tipo')
            p['nombre_diagrama'] = doc.ids[e['vista_id']].get('name')
            diagramas[e['diagrama']] = p
        else:
            plantillas.setdefault(e['diagrama'], {})[clave] = p
    salida = {'staruml': None, 'diagramas': diagramas, 'plantillas': plantillas, 'no_dibujables': omitidos}
    with open(os.path.join(RAIZ, 'staruml_metamodelo.json'), encoding='utf-8') as f:
        salida['staruml'] = json.load(f).get('staruml')
    with open(SALIDA, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(salida, f, ensure_ascii=False, indent='\t', sort_keys=True)
        f.write('\n')
    n = sum(map(len, plantillas.values()))
    print(f'{len(diagramas)} diagramas, {n} simbolos con plantilla, {len(omitidos)} sin plantilla -> {SALIDA}')
    for o in omitidos:
        print(f'  sin plantilla {o["diagrama"]}: {o["simbolo"]}: {o["motivo"]}')


if __name__ == '__main__':
    main(sys.argv)
