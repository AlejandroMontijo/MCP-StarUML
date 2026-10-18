# Diagrama de analisis (robustez, OOSE) de un caso de uso con la disposicion con que se dibuja en el curso:
#   actor | pantallas (boundary) en columna, cada una con su nota opcional | un control | modelo de dominio
# Actor -> pantalla y pantalla -> control van rectas con flecha; si la recta tocaria otra caja o una nota, entra a la
# pantalla con un tramo horizontal (un solo codo). Las entidades se acomodan como modelo de dominio por capas
# (programa.acomodar), siguiendo la navegabilidad de sus asociaciones y la herencia, y sus lineas se rutean
# aqui: cada linea llega por arriba o por abajo de la caja en su propio puerto, separado de los demas lo que piden sus
# etiquetas (multiplicidad y rol), corre por su carril entre filas (en un orden que evita cruces cuando se puede) y
# cruza las filas intermedias por su hueco; se guarda rectilinea para que StarUML la meta derecha a la caja. Las cajas
# con muchas lineas se ensanchan para que quepan las etiquetas. Las lineas control -> entidad no se dibujan por defecto
# (ensucian el diagrama y no se acostumbran); con lineas_control=True entran por el canal de arriba de su fila.
import math
import random

from . import mdj as M
from . import programa as P
from .mdj import MdjError, ref

ANCHO_NOTA = 230          # ancho de una nota larga (mas si una palabra no cabe)
ALTO_ACTOR = 80
SEP_ACTOR, SEP_CONTROL, SEP_DOMINIO = 170, 170, 170  # espacio entre columnas
CODO = 18                 # una linea doblada entra a la pantalla con un tramo horizontal desde aqui
SEP_GRUPOS = 110          # entre grupos de entidades sin relacion entre si
LADO, A_LO_LARGO = 7, 15  # etiqueta de un extremo: separacion de su linea y distancia al borde de la caja
ENTRE_LINEAS = 16         # separacion minima entre dos lineas que llegan al mismo lado de una caja
TALON = 6                 # ultimo tramo de una linea: del punto junto a la caja hasta su borde
FLECHA = 7                # media flecha (o medio triangulo de herencia) mas un margen
BAJA, SUBE = 26, 30       # un carril queda a esto de la fila de arriba (baja) o de la de abajo (sube)
CARRIL = P.CARRIL
ARRIBA, ABAJO = 'arriba', 'abajo'
NAVEGABLE = ('hacia', 'ambos', 'ninguno', 'desde')
# navegable de una asociacion segun (navega el extremo desde, navega el extremo hasta)
NAVEGA = {(False, True): 'hacia', (True, True): 'ambos', (False, False): 'ninguno', (True, False): 'desde'}


# etiquetas y orden de carriles viven en programa (tambien los usa el diagrama de un programa)
_ancho_etiqueta, _orden_canal = P._ancho_etiqueta, P._orden_canal
_poner_etiqueta, _centro_etiqueta = P._poner_etiqueta, P._centro_etiqueta


def _ancho(nombre, textos=()):
    return round(max([M.ancho13(nombre) * 1.15 + 24, 90] + [M.ancho13(x) + 24 for x in textos]))


def _ancho11(texto):
    return sum(M.ARIAL11.get(c, 6.1) for c in texto)


def _renglones(parrafo, ancho):
    """Renglones de un parrafo partido como lo parte StarUML (por espacios, Arial 11); el vacio no ocupa renglon."""
    if not parrafo:
        return 0
    n, actual = 0, 0.0
    for palabra in parrafo.split(' '):
        w = _ancho11(palabra)
        if n and actual + 3.1 + w > ancho:
            n, actual = n + 1, w
        elif n:
            actual += 3.1 + w
        else:
            n, actual = 1, w
    return n


def _medidas_nota(texto):
    """(texto, ancho, alto) de una nota segun como la dibuja StarUML: la ensancha hasta que quepa su palabra mas larga
    y le da de alto lo que miden sus parrafos partidos al ancho menos 20 (11 px por renglon y 2 por parrafo, mas 10).
    Cada parrafo lo dibuja partido al ancho menos 11, pero baja al siguiente lo que mide partido al ancho menos 1: si
    ahi le salen menos renglones, el parrafo siguiente se le encima. Se busca un ancho cercano en el que coincidan
    (con un margen, porque StarUML mide el texto un poco distinto) y, si no hay, los parrafos de en medio se parten a
    mano en renglones. Los anchos estimados salen algo mas grandes que los de StarUML: el alto no se queda corto."""
    parrafos = texto.split('\n')
    largo = max(_ancho11(p) for p in parrafos)
    minimo = max([90] + [math.ceil(_ancho11(w) + 22) for p in parrafos for w in p.split(' ')])
    base = max(minimo, ANCHO_NOTA if largo + 18 > ANCHO_NOTA else round(largo + 18))
    bien = lambda w: all(_renglones(p, (w - 11) * 0.95) == _renglones(p, (w - 1) * 1.05) for p in parrafos[:-1])
    w = next((w for d in range(40) for w in (base - d, base + d) if w >= minimo and bien(w)), None)
    if w is None:
        w, partidos = base, []
        for p in parrafos[:-1]:
            renglon = ''
            for palabra in p.split(' '):
                if renglon and _ancho11(renglon + ' ' + palabra) > (w - 11) * 0.9:
                    partidos.append(renglon)
                    renglon = palabra
                else:
                    renglon = (renglon + ' ' + palabra) if renglon else palabra
            partidos.append(renglon)
        parrafos = partidos + parrafos[-1:]
        texto = '\n'.join(parrafos)
    return texto, w, sum(_renglones(p, (w - 20) * 0.96) * 11 + 2 for p in parrafos) + 10


def _elemento(doc, paquete, nombre, estereotipo, atributos=None, documentacion=None):
    """El elemento con ese nombre en el paquete (se reusa) o uno nuevo. Un actor que no esta en el paquete pero si en
    otro lado del proyecto (el del diagrama de casos de uso, por ejemplo) se reusa si es el unico con ese nombre: asi
    no queda un segundo actor igual con sus propias asociaciones."""
    tipo = 'UMLActor' if estereotipo == 'actor' else 'UMLClass'
    el = next((o for o in paquete.get('ownedElements', []) if o.get('name') == nombre and o['_type'] == tipo), None)
    if el is None and tipo == 'UMLActor':
        otros = [o for o in doc.ids.values() if o and o.get('_type') == 'UMLActor' and o.get('name') == nombre]
        el = otros[0] if len(otros) == 1 else None
    if el is None:
        el = {'_type': tipo, '_id': doc.new_id(), '_parent': ref(paquete['_id']), 'name': nombre}
        if estereotipo != 'actor':
            el['stereotype'] = ref(doc.stereotype_id(estereotipo))
        paquete.setdefault('ownedElements', []).append(el)
        doc.reindex()
    elif estereotipo != 'actor' and doc.kind(el) != estereotipo:
        raise MdjError(f'{nombre} ya existe en {paquete.get("name")} como {doc.kind(el)}, no como {estereotipo}')
    if documentacion:
        el['documentation'] = documentacion
    # con la misma lista que ya tiene no se toca nada (rehacer las vistas las moveria en otros diagramas)
    if atributos is not None and [x.get('name') for x in el.get('attributes', [])] != list(atributos):
        M.set_atributos(doc, el, list(atributos))
    return el


def _validar(actores, pantallas, control, entidades, asociaciones, generalizaciones):
    if not actores or not pantallas or not control or not entidades:
        raise MdjError('Faltan actores, pantallas, control o entidades')
    for grupo, lista in (('actores', actores), ('pantallas', pantallas), ('entidades', entidades),
                         ('control', [control])):
        for x in lista:
            if not isinstance(x, dict) or not isinstance(x.get('nombre'), str) or not x['nombre'].strip():
                raise MdjError(f'Cada elemento de {grupo} necesita un nombre')
    nombres = [a['nombre'] for a in actores] + [p['nombre'] for p in pantallas] + [control['nombre']] + \
        [e['nombre'] for e in entidades]
    repetidos = sorted({n for n in nombres if nombres.count(n) > 1})
    if repetidos:
        raise MdjError(f'Nombres repetidos: {repetidos}')
    for grupo, lista in (('asociaciones', asociaciones), ('generalizaciones', generalizaciones)):
        if any(not isinstance(x, dict) for x in lista):
            raise MdjError(f'Cada elemento de {grupo} debe ser un objeto')
    ent = {e['nombre']: e for e in entidades}
    for a in asociaciones:
        for k in ('desde', 'hasta'):
            if a.get(k) not in ent:
                raise MdjError(f'Asociacion {a.get("desde")} - {a.get("hasta")}: {a.get(k)} no es una entidad. En '
                               'robustez el actor solo habla con pantallas, las pantallas con el control y el control '
                               'con las entidades; esas lineas se dibujan solas')
        for k in ('mult_desde', 'mult_hacia', 'rol_desde', 'rol_hacia'):
            if a.get(k) is not None and not isinstance(a[k], str):
                raise MdjError(f'Asociacion {a["desde"]} - {a["hasta"]}: {k} debe ser texto')
        if a.get('navegable') and a['navegable'] not in NAVEGABLE:
            raise MdjError(f'Asociacion {a["desde"]} - {a["hasta"]}: navegable "{a["navegable"]}" no es '
                           f'{", ".join(NAVEGABLE)}')
    for e in entidades:
        padre = e.get('depende_de')
        if not padre:
            continue
        if padre not in ent:
            raise MdjError(f'{e["nombre"]}: depende_de "{padre}" no es una entidad de la lista')
        if ent[padre].get('depende_de'):
            raise MdjError(f'{e["nombre"]}: depende de {padre}, que tambien es dependiente; '
                           'debe depender de una entidad que use el control')
        # la asociacion entre las dos (el camino por el que se llega a la dependiente) puede venir en la lista o ya
        # existir en el modelo: eso se revisa en generar_robustez, cuando ya se conocen los elementos
    pares = []
    for g in generalizaciones:
        h, p = g.get('hijo'), g.get('padre')
        for x in (h, p):
            if x not in ent:
                raise MdjError(f'Generalizacion {h} -> {p}: {x} no es una entidad de la lista')
        if h == p or (h, p) in pares:
            raise MdjError(f'Generalizacion {h} -> {p} repetida o de una entidad hacia si misma')
        pares.append((h, p))
    padres = {}
    for h, p in pares:
        padres.setdefault(h, []).append(p)

    def sube(n, camino):
        for p in padres.get(n, ()):
            if p in camino:
                raise MdjError(f'La herencia forma un ciclo: {" -> ".join(camino + [p])}')
            sube(p, camino + [p])
    for h in padres:
        sube(h, [h])
    pant_nombres = [p['nombre'] for p in pantallas]
    for a in actores:
        for p in a.get('pantallas') or ():
            if p not in pant_nombres:
                raise MdjError(f'{a["nombre"]}: la pantalla "{p}" no esta en la lista')


def _navega(extremo):
    """Si el extremo de una asociacion navega ('navigable'; en archivos viejos, true). Sin especificar o
    'notNavigable' no navega."""
    return extremo.get('navigable') in (True, 'navigable')


def _pedido(a):
    """Lo que una asociacion pide de forma explicita: las multiplicidades y los roles que no vienen vacios y la
    navegabilidad si se da. Lo demas no se pide (en una asociacion nueva queda vacio o con la flecha por defecto)."""
    return {k: a[k] for k in ('mult_desde', 'mult_hacia', 'rol_desde', 'rol_hacia', 'navegable') if a.get(k)}


def _extremos(asoc, inv):
    """(extremo desde, extremo hasta) de la asociacion."""
    return (asoc['end2'], asoc['end1']) if inv else (asoc['end1'], asoc['end2'])


def _como_queda(asoc, inv):
    """mult_desde, mult_hacia, rol_desde, rol_hacia y navegable que tiene la asociacion en el modelo: con eso se
    acomoda y se etiqueta la linea, que es lo que StarUML dibuja."""
    ea, eb = _extremos(asoc, inv)
    return {'mult_desde': ea.get('multiplicity') or '', 'mult_hacia': eb.get('multiplicity') or '',
            'rol_desde': ea.get('name') or '', 'rol_hacia': eb.get('name') or '',
            'navegable': NAVEGA[(_navega(ea), _navega(eb))]}


def _asociacion(doc, usadas, a, b, pedido):
    """La asociacion entre a y b que ya exista en el modelo (y no se haya usado en esta llamada) o una nueva: volver a
    generar en otro diagrama no duplica las asociaciones del modelo. De varias entre el mismo par toma la que mas se
    parece a lo pedido (primero los roles, luego multiplicidades y navegabilidad). pedido: lo que se pide de forma
    explicita (_pedido). En una que ya existia solo cambia lo pedido que sea distinto; lo que no se pide se queda
    como estaba aunque este vacio o sin flecha, porque la asociacion tambien se ve en otros diagramas. Una nueva toma
    lo pedido y, si no se pide navegable, la flecha de a hacia b.
    Devuelve (asociacion, invertida, reporte); invertida si su extremo desde (a) es end2; reporte es None si la
    asociacion es nueva o {asociacion, id, cambios[, se_ve_en]} si ya existia."""
    cands = []
    for o in doc.ids.values():
        if not o or o.get('_type') != 'UMLAssociation' or o['_id'] in usadas:
            continue
        e1 = (o.get('end1') or {}).get('reference', {}).get('$ref')
        e2 = (o.get('end2') or {}).get('reference', {}).get('$ref')
        if {e1, e2} != {a['_id'], b['_id']} or (e1 == e2) != (a is b):
            continue
        # en una reflexiva cualquiera de los dos extremos puede ser desde: el que mejor coincida con lo pedido
        for inv in ((False, True) if a is b else (e1 != a['_id'],)):
            q = _como_queda(o, inv)
            roles = sum(q[k] != pedido.get(k, '') for k in ('rol_desde', 'rol_hacia'))
            resto = sum(k in pedido and q[k] != pedido[k] for k in ('mult_desde', 'mult_hacia', 'navegable'))
            cands.append(((roles, resto, inv, len(cands)), o, inv))
    if not cands:
        asoc = M.asociacion_crear(doc, a, b, pedido.get('mult_desde', ''), pedido.get('mult_hacia', ''),
                                  pedido.get('rol_desde', ''), pedido.get('rol_hacia', ''),
                                  pedido.get('navegable', 'hacia'), a)
        usadas.add(asoc['_id'])
        return asoc, False, None
    _, asoc, inv = min(cands, key=lambda c: c[0])
    usadas.add(asoc['_id'])
    nombre = lambda e: doc.name_of(e['reference']['$ref'])
    reporte = {'asociacion': f'{nombre(asoc["end1"])} - {nombre(asoc["end2"])}', 'id': asoc['_id'], 'cambios': []}
    ea, eb = _extremos(asoc, inv)
    for num, e, lado in ((2 if inv else 1, ea, 'desde'), (1 if inv else 2, eb, 'hacia')):
        extremo = nombre(e) + (f' ({lado})' if a is b else '')
        cambio = {}
        for clave, campo, que, arg in ((f'mult_{lado}', 'multiplicity', 'multiplicidad', 'mult'),
                                       (f'rol_{lado}', 'name', 'rol', 'rol')):
            if clave in pedido and (e.get(campo) or '') != pedido[clave]:
                reporte['cambios'].append({'extremo': extremo, 'que': que, 'antes': e.get(campo) or '',
                                           'despues': pedido[clave]})
                cambio[arg] = pedido[clave]
        if 'navegable' in pedido and _navega(e) != (pedido['navegable'] in ('ambos', lado)):
            reporte['cambios'].append({'extremo': extremo, 'que': 'navegable', 'antes': _navega(e),
                                       'despues': not _navega(e)})
            cambio['navegable'] = not _navega(e)
        if cambio:
            M.asociacion_editar(doc, asoc, num, **cambio)
    if reporte['cambios']:
        # donde ya estaba dibujada (esta llamada todavia no la dibuja): ahi tambien se ve el cambio
        se_ve_en = sorted({dg.get('name') or dg['_id'] for dg, _ in doc.views_of(asoc['_id'])})
        if se_ve_en:
            reporte['se_ve_en'] = se_ve_en
    return asoc, inv, reporte


def _generalizacion(doc, hijo, padre):
    for o in doc.ids.values():
        if o and o.get('_type') == 'UMLGeneralization' and (o.get('source') or {}).get('$ref') == hijo['_id'] \
                and (o.get('target') or {}).get('$ref') == padre['_id']:
            return o
    g = {'_type': 'UMLGeneralization', '_id': doc.new_id(), '_parent': ref(hijo['_id']),
         'source': ref(hijo['_id']), 'target': ref(padre['_id'])}
    hijo.setdefault('ownedElements', []).append(g)
    doc.reindex()
    return g


# ---------------------------------------------------------------------------
# Modelo de dominio: capas, puertos, carriles y rutas
# ---------------------------------------------------------------------------

def _componentes(nombres, aristas):
    vecinos = {n: set() for n in nombres}
    for a, b, _ in aristas:
        vecinos[a].add(b)
        vecinos[b].add(a)
    visto, comps, sueltas = set(), [], []
    for n in nombres:
        if n in visto:
            continue
        comp, pila = [], [n]
        while pila:
            m = pila.pop()
            if m not in visto:
                visto.add(m)
                comp.append(m)
                pila.extend(sorted(vecinos[m]))
        if len(comp) > 1:
            comps.append(comp)
        else:
            sueltas.append(n)
    comps.sort(key=lambda c: -len(c))
    return comps, sueltas


def _acomodo(nombres, tam, aristas):
    """Cada componente conexa por capas (programa.acomodar) desde (0, 0); las entidades sueltas van en filas
    aparte (cada fila es un grupo de una sola capa)."""
    comps, sueltas = _componentes(nombres, aristas)
    grupos = []
    for comp in comps:
        miembros = set(comp)
        pos, geos = P.acomodar(comp, {n: tam[n] for n in comp}, [e for e in aristas if e[0] in miembros])
        g = geos[0]
        x0, y0 = min(x for x, _ in pos.values()), min(y for _, y in pos.values())
        grupos.append({'pos': {n: [x - x0, y - y0] for n, (x, y) in pos.items()}, 'capa': g['capa'],
                       'tops': [t - y0 for t in g['tops']], 'altos': list(g['altos']),
                       'huecos': {h: x - x0 for h, x in g['huecos'].items()}, 'cadenas': g['cadenas']})
    ancho_fila = max([max(p[0] + tam[n][0] for n, p in g['pos'].items()) for g in grupos] + [700])
    fila, x = [], 0
    for n in sueltas + [None]:
        if n is None or (fila and x + tam[n][0] > ancho_fila):
            if fila:
                pos, x0 = {}, 0
                for m in fila:
                    pos[m] = [x0, 0]
                    x0 += tam[m][0] + P.SEP_X
                grupos.append({'pos': pos, 'capa': {m: 0 for m in fila}, 'tops': [0],
                               'altos': [max(tam[m][1] for m in fila)], 'huecos': {}, 'cadenas': {}})
            fila, x = [], 0
        if n is not None:
            fila.append(n)
            x += tam[n][0] + P.SEP_X
    return grupos


def _tramos(grupos, lineas, controladas):
    """Cada linea del dominio de x hacia z: {clave, tipo, g, x, z, lx, lz, huecos}. lx y lz: lado de la caja por donde
    sale y llega (arriba o abajo); huecos en el orden de x a z. tipo: 'capas' (filas distintas), 'fila' (la misma
    fila), 'lazo' (asociacion de una entidad consigo misma, por el lado de la caja con menos lineas) o 'control'
    (llega del control a x por su lado izquierdo, a media altura)."""
    de = {n: i for i, g in enumerate(grupos) for n in g['pos']}
    tramos = []
    for clave, x, z in lineas:
        g = grupos[de[x]]
        t = {'clave': clave, 'g': de[x], 'x': x, 'z': z, 'huecos': []}
        if x == z:
            t.update(tipo='lazo')
        elif g['capa'][x] == g['capa'][z]:
            lado = ARRIBA if g['capa'][x] > 0 else ABAJO
            t.update(tipo='fila', lx=lado, lz=lado)
        else:
            baja = g['capa'][x] < g['capa'][z]
            arriba, abajo = (x, z) if baja else (z, x)
            huecos = g['cadenas'].get((arriba, abajo), [arriba, abajo])[1:-1]
            t.update(tipo='capas', lx=ABAJO if baja else ARRIBA, lz=ARRIBA if baja else ABAJO,
                     huecos=huecos if baja else huecos[::-1])
        tramos.append(t)
    cuenta = {}
    for t in tramos:
        if t['tipo'] != 'lazo':
            for n, lado in ((t['x'], t['lx']), (t['z'], t['lz'])):
                cuenta[(n, lado)] = cuenta.get((n, lado), 0) + 1
    for t in tramos:
        if t['tipo'] == 'lazo':
            lado = ARRIBA if cuenta.get((t['x'], ARRIBA), 0) <= cuenta.get((t['x'], ABAJO), 0) else ABAJO
            t.update(lx=lado, lz=lado)
            cuenta[(t['x'], lado)] = cuenta.get((t['x'], lado), 0) + 2
    for e in controladas:
        tramos.append({'clave': ('control', e), 'tipo': 'control', 'g': de[e], 'x': e, 'z': None, 'lx': None,
                       'lz': None, 'huecos': []})
    return tramos


def _lados(grupos, tam, tramos, etiquetas):
    """Por (caja, lado): [(clave, extremo, orden, (izq, der))]. orden pone primero las lineas que van a la izquierda
    (para que no se crucen junto a la caja); izq y der son los anchos de las etiquetas a cada lado de la linea."""
    lados = {}

    def cx(t, n):
        g = grupos[t['g']]
        return g['pos'][n][0] + tam[n][0] / 2
    for i, t in enumerate(tramos):
        g = grupos[t['g']]
        if t['tipo'] == 'control':
            continue
        if t['tipo'] == 'lazo':
            dx = dz = 1e9
        else:
            dx = g['huecos'][t['huecos'][0]] if t['huecos'] else cx(t, t['z'])
            dz = g['huecos'][t['huecos'][-1]] if t['huecos'] else cx(t, t['x'])
        lados.setdefault((t['x'], t['lx']), []).append((t['clave'], 'x', (dx, i, 0),
                                                         etiquetas.get((t['clave'], 'x'), (0, 0))))
        lados.setdefault((t['z'], t['lz']), []).append((t['clave'], 'z', (dz, i, 1),
                                                         etiquetas.get((t['clave'], 'z'), (0, 0))))
    for lista in lados.values():
        lista.sort(key=lambda e: e[2])
    return lados


def _separaciones(espacios):
    """Separaciones minimas: borde izquierdo -> primera linea, entre lineas vecinas y ultima linea -> borde derecho.
    espacios: (izq, der) de cada linea, en orden."""
    lado = lambda w: w + LADO if w else FLECHA
    seps = [2 + lado(espacios[0][0])]
    for (_, der), (izq, _) in zip(espacios, espacios[1:]):
        seps.append(max(lado(der) + 4 + lado(izq), ENTRE_LINEAS))
    seps.append(lado(espacios[-1][1]) + 2)
    return seps


def _lados_de_etiquetas(lista):
    """(izq, der) de cada linea de un lado y si sus etiquetas van al reves (rol a la derecha). Por defecto el rol va a
    la izquierda y la multiplicidad a la derecha; en la primera y la ultima linea la etiqueta mas ancha va hacia
    afuera, asi las lineas quedan mas juntas y mas cerca del centro de la caja."""
    res = []
    for k, e in enumerate(lista):
        izq, der = e[3]
        invertir = len(lista) > 1 and ((k == 0 and der > izq) or (k == len(lista) - 1 and izq > der))
        res.append(((der, izq) if invertir else (izq, der), invertir))
    return res


def _ancho_lado(lista):
    """Ancho que necesita un lado: las etiquetas de todas sus lineas y, si no cuesta mas de 40 px, el que permite
    centrar las lineas en la caja (StarUML apunta el ultimo tramo al centro: fuera del centro la linea se quiebra)."""
    seps = _separaciones([e for e, _ in _lados_de_etiquetas(lista)])
    total = sum(seps)
    centrado = sum(seps[1:-1]) + 2 * max(seps[0], seps[-1])
    return math.ceil(min(centrado, total + 40))


def _dominio(nombres, tam, lineas, etiquetas, controladas):
    """Acomoda y rutea el modelo de dominio desde (0, 0). lineas: [(clave, x, z)] (x queda arriba de z si se puede: el
    que navega o el padre); etiquetas: {(clave, 'x'|'z'): (izq, der)}. Devuelve (posiciones, tam con las cajas
    ensanchadas, {clave: medios de x hacia z}, {(clave, 'x'|'z'): (caja, lado, x del puerto)})."""
    tam = dict(tam)
    aristas = [(x, z, clave[0] == 'gen') for clave, x, z in lineas if x != z]
    for _ in range(3):  # las capas no dependen del ancho: con las cajas ensanchadas basta una vuelta mas
        grupos = _acomodo(nombres, tam, aristas)
        tramos = _tramos(grupos, lineas, controladas)
        lados = _lados(grupos, tam, tramos, etiquetas)
        cambio = False
        for (n, _), lista in lados.items():
            falta = _ancho_lado(lista)
            if falta > tam[n][0]:
                tam[n] = (falta, tam[n][1])
                cambio = True
        if not cambio:
            break
    # carriles de cada canal (c: entre la fila c y la c+1; -1: arriba de la primera). Las lineas bajan desde la fila de
    # arriba; lazos y lineas del control suben desde la de abajo. Los canales que no alcanzan se agrandan.
    usan = {}

    def usa(gi, c, sentido):
        usan[(gi, c, sentido)] = usan.get((gi, c, sentido), 0) + 1
    for t in tramos:
        capa = grupos[t['g']]['capa']
        cx = capa[t['x']]
        if t['tipo'] == 'capas':
            for c in range(min(cx, capa[t['z']]), max(cx, capa[t['z']])):
                usa(t['g'], c, 'baja')
        elif t['tipo'] == 'fila' or (t['tipo'] == 'lazo' and t['lx'] == ABAJO):
            usa(t['g'], cx - 1 if t['lx'] == ARRIBA else cx, 'baja')
        else:
            usa(t['g'], cx - 1, 'sube')
    y = 0
    for gi, g in enumerate(grupos):
        tops = list(g['tops'])
        for c in range(len(tops) - 1):
            n = usan.get((gi, c, 'baja'), 0) + usan.get((gi, c, 'sube'), 0)
            falta = BAJA + SUBE + CARRIL * max(n - 1, 0) + 10 - (tops[c + 1] - tops[c] - g['altos'][c])
            if falta > 0:
                tops[c + 1:] = [t + falta for t in tops[c + 1:]]
        arriba = usan.get((gi, -1, 'sube'), 0)
        y += SUBE + CARRIL * (arriba - 1) + 10 if arriba else 0
        g['tops'] = [t + y for t in tops]
        for n, p in g['pos'].items():
            p[1] = g['tops'][g['capa'][n]]
        abajo = usan.get((gi, len(tops) - 1, 'baja'), 0)
        y = g['tops'][-1] + g['altos'][-1] + (BAJA + CARRIL * abajo if abajo else 0) + SEP_GRUPOS
    caja = {n: (p[0], p[1], p[0] + tam[n][0], p[1] + tam[n][1]) for g in grupos for n, p in g['pos'].items()}

    # puertos: las lineas de cada lado, en su orden, juntas y centradas en la caja con el espacio de sus etiquetas
    puertos, seps_de = {}, {}
    for (n, lado), lista in lados.items():
        lados_et = _lados_de_etiquetas(lista)
        seps = _separaciones([e for e, _ in lados_et])
        x0, x1 = caja[n][0], caja[n][2]
        extra = min(8.0, max(0.0, (x1 - x0) - sum(seps)) / (len(lista) + 1))
        tramo = sum(seps[1:-1]) + extra * (len(lista) - 1)
        x = min(max((x0 + x1) / 2 - tramo / 2, x0 + seps[0]), x1 - seps[-1] - tramo)
        for k, (e, (_, invertir)) in enumerate(zip(lista, lados_et)):
            if k:
                x += seps[k] + extra
            puertos[(e[0], e[1])] = [n, lado, x, invertir]
        seps_de[(n, lado)] = seps

    def cabe(clave, extremo, nx):
        n, lado = puertos[(clave, extremo)][:2]
        lista, seps = lados[(n, lado)], seps_de[(n, lado)]
        i = next(k for k, e in enumerate(lista) if (e[0], e[1]) == (clave, extremo))
        izq = puertos[(lista[i - 1][0], lista[i - 1][1])][2] if i else caja[n][0]
        der = puertos[(lista[i + 1][0], lista[i + 1][1])][2] if i + 1 < len(lista) else caja[n][2]
        return izq + seps[i] - 0.5 <= nx <= der - seps[i + 1] + 0.5

    # una linea entre filas vecinas sin huecos queda vertical si sus dos puertos se pueden alinear. La que llega sola a
    # su lado esta en el centro de la caja y se corre a lo mas un cuarto del ancho (mas lejos se ve mejor el codo)
    for t in tramos:
        if t['tipo'] != 'capas' or t['huecos']:
            continue
        holgura = [tam[t[e]][0] / 4 if len(lados[tuple(puertos[(t['clave'], e)][:2])]) == 1 else 1e9
                   for e in ('x', 'z')]
        px, pz = puertos[(t['clave'], 'x')][2], puertos[(t['clave'], 'z')][2]
        for obj in (pz, px, (px + pz) / 2):
            if all(abs(obj - p) <= h for p, h in zip((px, pz), holgura)) and \
                    cabe(t['clave'], 'x', obj) and cabe(t['clave'], 'z', obj):
                puertos[(t['clave'], 'x')][2] = puertos[(t['clave'], 'z')][2] = obj
                break

    # cada linea pide su carril en los canales que cruza; luego se ordenan los carriles de cada canal para que las
    # lineas no se crucen si se puede (_orden_canal) y se arman los puntos con la altura de cada carril
    pedidos, planes, vistos = [], [], {}

    def pedir(gi, c, sentido, sube_a, baja_a):
        """Un carril en el canal c. sube_a / baja_a: x de los tramos verticales que van de el a la fila de arriba o a
        la de abajo."""
        p = {'canal': (gi, c, sentido), 'sube_a': list(sube_a), 'baja_a': list(baja_a), 'y': None}
        pedidos.append(p)
        return p
    # las del control, de izquierda a derecha: la de mas a la izquierda toma el carril mas bajo y no se cruzan
    orden = [t for t in tramos if t['tipo'] != 'control'] + \
        sorted((t for t in tramos if t['tipo'] == 'control'), key=lambda t: (caja[t['x']][1], caja[t['x']][0]))
    for t in orden:
        g, gi, x, z = grupos[t['g']], t['g'], t['x'], t['z']
        borde = lambda n, lado: caja[n][1] - TALON if lado == ARRIBA else caja[n][3] + TALON
        if t['tipo'] == 'control':
            # baja junto a la caja y entra por su lado izquierdo a media altura: el tramo final apunta al centro
            xb = caja[x][0] - 14
            p = pedir(gi, g['capa'][x] - 1, 'sube', [], [xb])
            p['control'] = True
            planes.append((t['clave'], [(p, p), (xb, p), (xb, (caja[x][1] + caja[x][3]) / 2)]))
            continue
        px, pz = puertos[(t['clave'], 'x')][2], puertos[(t['clave'], 'z')][2]
        if t['tipo'] == 'lazo':
            # StarUML dibuja los extremos de un lazo en perpendicular al borde (no hacia el centro)
            if t['lx'] == ARRIBA:
                p = pedir(gi, g['capa'][x] - 1, 'sube', [], [px, pz])
            else:
                p = pedir(gi, g['capa'][x], 'baja', [px, pz], [])
            planes.append((t['clave'], [(px, p), (pz, p)]))
            continue
        if t['tipo'] == 'fila':
            if t['lx'] == ARRIBA:
                p = pedir(gi, g['capa'][x] - 1, 'baja', [], [px, pz])
            else:
                p = pedir(gi, g['capa'][x], 'baja', [px, pz], [])
            planes.append((t['clave'], [(px, borde(x, t['lx'])), (px, p), (pz, p), (pz, borde(z, t['lz']))]))
            continue
        if not t['huecos'] and abs(px - pz) < 0.5:
            planes.append((t['clave'], [(px, borde(x, t['lx'])), (pz, borde(z, t['lz']))]))
            continue
        # las asociaciones repetidas entre el mismo par cruzan las filas por el mismo hueco, un poco corridas
        par = frozenset((x, z))
        dup = vistos.get(par, 0)
        vistos[par] = dup + 1
        cx, cz = g['capa'][x], g['capa'][z]
        baja = cx < cz
        canales = range(cx, cz) if baja else range(cx - 1, cz - 1, -1)
        pts, actual = [(px, borde(x, t['lx']))], px
        for i, c in enumerate(canales):
            sig = g['huecos'][t['huecos'][i]] + 4 * dup if i < len(t['huecos']) else pz
            p = pedir(gi, c, 'baja', [actual] if baja else [sig], [sig] if baja else [actual])
            pts += [(actual, p), (sig, p)]
            actual = sig
        pts.append((pz, borde(z, t['lz'])))
        planes.append((t['clave'], pts))
    canales = {}
    for p in pedidos:
        canales.setdefault(p['canal'], []).append(p)
    for (gi, c, sentido), lista in canales.items():
        g = grupos[gi]
        for k, p in enumerate(_orden_canal(lista) if sentido == 'baja' else lista):
            p['y'] = g['tops'][c] + g['altos'][c] + BAJA + CARRIL * k if sentido == 'baja' else \
                g['tops'][c + 1] - SUBE - CARRIL * k
    # las del control llegan a su carril por una diagonal desde el control (que queda a media altura del dominio). En
    # cada canal se abren en abanico: la del carril mas cercano al control dobla mas a la derecha, asi las diagonales
    # no se juntan y ninguna cruza el tramo horizontal de otra
    medio = (min([c[1] for c in caja.values()] + [p['y'] for p in pedidos]) + max(c[3] for c in caja.values())) / 2
    for lista in canales.values():
        ctrl = [p for p in lista if p.get('control')]
        paso = min(12, 60 / max(len(ctrl) - 1, 1))
        for j, p in enumerate(ctrl):
            p['x'] = -25 - paso * (j if p['y'] < medio else len(ctrl) - 1 - j)
    medios = {}
    for clave, pts in planes:
        pts = [(x['x'] if isinstance(x, dict) else x, y['y'] if isinstance(y, dict) else y) for x, y in pts]
        medios[clave] = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    pos = {n: (c[0], c[1]) for n, c in caja.items()}
    return pos, tam, medios, {k: tuple(v) for k, v in puertos.items()}


# ---------------------------------------------------------------------------
# Etiquetas de los extremos y revision final
# ---------------------------------------------------------------------------

def _puntos(v):
    return [tuple(float(n) for n in q.split(':')) for q in (v.get('points') or '').split(';') if ':' in q]


def _rectilinea(v, vt, vh):
    """Una linea con todos sus tramos horizontales o verticales se guarda rectilinea (lineStyle 0): asi StarUML baja
    cada extremo en perpendicular al borde desde el punto vecino. En oblicua lo apunta al centro de la caja y, si el
    puerto no esta en el centro, la linea se quiebra junto a la caja; en un lazo por abajo ademas lo angosta (lo
    calcula primero como oblicuo). Los extremos se guardan donde StarUML los dibuja, sin puntos de mas, para que las
    etiquetas se calculen sobre lo que se ve. Devuelve False (y no la toca) si algun tramo es diagonal."""
    pts = _puntos(v)
    for i, j, caja in ((0, 1, vt), (-1, -2, vh)):
        x0, y0 = caja['left'], caja['top']
        x1, y1 = x0 + caja['width'], y0 + caja['height']
        nx, ny = pts[j]
        if x0 < nx < x1:
            pts[i] = (nx, y0 if ny < y0 else y1)
        elif y0 < ny < y1:
            pts[i] = (x0 if nx < x0 else x1, ny)
        else:
            return False
    pts = [(round(x), round(y)) for x, y in pts]
    if any(p[0] != q[0] and p[1] != q[1] for p, q in zip(pts, pts[1:])):
        return False
    limpios = pts[:1]
    for p, q in zip(pts[1:], pts[2:] + [None]):
        a = limpios[-1]
        if p == a or (q is not None and (a[0] == p[0] == q[0] or a[1] == p[1] == q[1])):
            continue  # repetido o en medio de un tramo recto
        limpios.append(p)
    v['points'] = ';'.join(f'{x}:{y}' for x, y in limpios)
    v['lineStyle'] = 0
    return True


def _etiquetas(v, inv, a, puertos, clave, vistas, dx, volteada=False):
    """Multiplicidad a un lado y rol al otro de cada extremo, junto a la caja, en el espacio que les dejo el reparto de
    puertos (_lados_de_etiquetas). a: multiplicidades y roles como quedan en el modelo (_como_queda). volteada: el
    extremo 'x' del dominio (el de arriba) es hasta, no desde."""
    subs = {s['_id']: s for s in v.get('subViews', [])}
    for es_desde, mult, rol in ((True, a.get('mult_desde', ''), a.get('rol_desde', '')),
                                (False, a.get('mult_hacia', ''), a.get('rol_hacia', ''))):
        ext = 'x' if es_desde != volteada else 'z'
        if (clave, ext) not in puertos:
            continue
        n, lado, px, invertir = puertos[(clave, ext)]
        caja = vistas[n]
        y = caja['top'] - A_LO_LARGO if lado == ARRIBA else caja['top'] + caja['height'] + A_LO_LARGO
        extremo = 'tail' if es_desde != inv else 'head'
        signo = -1 if invertir else 1
        for k, texto, s in (('MultiplicityLabel', mult, signo), ('RoleNameLabel', ('+' + rol) if rol else '', -signo)):
            lab = subs.get((v.get(extremo + k) or {}).get('$ref'))
            if lab and texto:
                _poner_etiqueta(v, lab, (px + dx + s * (LADO + _ancho_etiqueta(texto) / 2), y))


def _revisar(vistas, notas, lineas):
    """Lineas que cruzan cajas o notas y etiquetas de extremo encimadas entre si o sobre una linea, una caja o una
    nota: lo mismo que revisa svg_revisar, sobre el modelo."""
    cajas = {n: (v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height']) for n, v in vistas.items()}
    de = {v['_id']: n for n, v in vistas.items()}
    segs, cruzan = [], []
    for v in lineas:
        pts = _puntos(v)
        t_, h_ = de.get(v['tail']['$ref']), de.get(v['head']['$ref'])
        nombre = f'{t_} - {h_}'
        otras = [c for n, c in cajas.items() if n not in (t_, h_)] + [(a - 2, b - 2, c + 2, d + 2)
                                                                     for a, b, c, d in notas]
        if any(P._cruza(p, q, c, 2) for p, q in zip(pts, pts[1:]) for c in otras):
            cruzan.append(nombre)
        segs += [(p, q, nombre) for p, q in zip(pts, pts[1:])]
    textos = []
    for v in lineas:
        if v['_type'] != 'UMLAssociationView':
            continue
        subs = {s['_id']: s for s in v.get('subViews', [])}
        for k in ('tailMultiplicityLabel', 'tailRoleNameLabel', 'headMultiplicityLabel', 'headRoleNameLabel'):
            lab = subs.get((v.get(k) or {}).get('$ref'))
            if lab and lab.get('visible') is not False and lab.get('text'):
                c, w = _centro_etiqueta(v, lab), _ancho_etiqueta(lab['text'])
                textos.append((lab['text'], (c[0] - w / 2, c[1] - 5.5, c[0] + w / 2, c[1] + 5.5)))
    toca = lambda r, s: r[0] < s[2] and s[0] < r[2] and r[1] < s[3] and s[1] < r[3]
    choques = []
    for i, (t, r) in enumerate(textos):
        choques += [f'"{t}" sobre la linea {nombre}' for p, q, nombre in segs if P._cruza(p, q, r, -1)]
        choques += [f'"{t}" sobre la caja {n}' for n, c in cajas.items() if toca(r, c)]
        choques += [f'"{t}" sobre una nota' for nt in notas if toca(r, nt)]
        choques += [f'"{t}" encimada con "{t2}"' for t2, r2 in textos[i + 1:] if toca(r, r2)]
    return cruzan, choques


# ---------------------------------------------------------------------------
# Diagrama
# ---------------------------------------------------------------------------

def generar_robustez(doc, diagrama, paquete, actores, pantallas, control, entidades, asociaciones=(),
                     lineas_control=False, generalizaciones=()):
    """actores: [{nombre, documentacion?, pantallas?, secundario?}]  (pantallas: las que usa, default todas;
               secundario: actor externo al que el sistema le avisa, la flecha va de la pantalla hacia el)
    pantallas: [{nombre, documentacion?, nota?}] de arriba abajo; nota: texto de una nota debajo de la pantalla
    control: {nombre, documentacion?}
    entidades: [{nombre, atributos?, documentacion?, depende_de?}]  (depende_de: entidad que solo se alcanza desde
               otra por una asociacion entre las dos, que puede venir en asociaciones o ya existir en el modelo;
               queda debajo de ella y con lineas_control el control no se une a ella)
    asociaciones: [{desde, hasta, mult_desde?, mult_hacia?, rol_desde?, rol_hacia?, navegable?}] entre entidades;
               navegable 'hacia' por defecto (flecha de desde a hasta); el extremo que navega queda arriba.
               desde == hasta es una asociacion reflexiva.
    generalizaciones: [{hijo, padre}] entre entidades (el padre queda arriba).
    Reusa los elementos del paquete (un actor, tambien de otro paquete si es el unico con ese nombre) y las
    asociaciones que ya existan entre ellos (no los duplica). Una asociacion reusada se dibuja como esta en el modelo:
    solo cambia lo que se pide de forma explicita y es distinto (multiplicidad o rol no vacios, navegable); lo que no
    se pide no se toca, ni en las lineas actor-pantalla, pantalla-control y control-entidad, que no piden nada
    (secundario solo da el sentido de una linea nueva). La respuesta trae cada asociacion reusada con lo que se le
    cambio (reusadas)."""
    asociaciones = list(asociaciones or ())
    generalizaciones = list(generalizaciones or ())
    dg = doc.diagram(diagrama)
    if dg['_type'] != 'UMLClassDiagram':
        raise MdjError(f'{dg.get("name")} es {dg["_type"]}: el analisis de robustez va en un diagrama de clases')
    pk = doc.find(paquete, types=('UMLPackage', 'UMLModel', 'UMLSubsystem'))
    _validar(actores, pantallas, control, entidades, asociaciones, generalizaciones)
    pant_nombres = [p['nombre'] for p in pantallas]
    ent_nombres = [e['nombre'] for e in entidades]
    ctrl = control['nombre']

    # elementos (se reusan si ya existen en el paquete)
    els = {}
    for a in actores:
        els[a['nombre']] = _elemento(doc, pk, a['nombre'], 'actor', None, a.get('documentacion'))
    for p in pantallas:
        els[p['nombre']] = _elemento(doc, pk, p['nombre'], 'boundary', None, p.get('documentacion'))
    els[ctrl] = _elemento(doc, pk, ctrl, 'control', None, control.get('documentacion'))
    for e in entidades:
        els[e['nombre']] = _elemento(doc, pk, e['nombre'], 'entity', e.get('atributos'), e.get('documentacion'))
    for n, el in els.items():
        if doc.views_of(el['_id'], dg):
            raise MdjError(f'{n} ya esta dibujado en {dg.get("name")}: usa un diagrama vacio')

    # una entidad dependiente necesita una asociacion con la entidad de la que depende (el control no se une a ella).
    # Si no viene en la lista pero ya existe en el modelo, se usa esa tal como esta (no hay que repetirla)
    for e in entidades:
        padre = e.get('depende_de')
        if not padre or any({a['desde'], a['hasta']} == {e['nombre'], padre} for a in asociaciones):
            continue
        ya = any(o and o.get('_type') == 'UMLAssociation' and
                 {(o.get('end1') or {}).get('reference', {}).get('$ref'),
                  (o.get('end2') or {}).get('reference', {}).get('$ref')} == {els[e['nombre']]['_id'], els[padre]['_id']}
                 for o in doc.ids.values())
        if not ya:
            raise MdjError(f'{e["nombre"]} depende de {padre}, pero no hay una asociacion entre las dos: agregala '
                           'en asociaciones (es el camino por el que se llega a ella)')
        asociaciones.append({'desde': padre, 'hasta': e['nombre']})

    # asociaciones entre entidades: se resuelven antes de acomodar, porque una que ya existe se dibuja con lo que
    # tiene en el modelo. Entre varias del mismo par escogen primero las que piden roles y luego las que piden mas
    usadas, resueltas = set(), {}
    pedidos = [_pedido(a) for a in asociaciones]
    for i in sorted(range(len(asociaciones)), key=lambda i: (-sum(k in pedidos[i] for k in ('rol_desde', 'rol_hacia')),
                                                              -len(pedidos[i]), i)):
        resueltas[i] = _asociacion(doc, usadas, els[asociaciones[i]['desde']], els[asociaciones[i]['hasta']],
                                   pedidos[i])
    queda = {i: _como_queda(asoc, inv) for i, (asoc, inv, _) in resueltas.items()}

    # tamanos: cada caja con lo que de verdad muestra su vista. Pantallas, control y entidades se dibujan primero (y
    # despues del acomodo se mueven a su lugar) porque vista_nueva copia el estilo de otra vista: si esa muestra las
    # operaciones (o los atributos), la nueva tambien, y StarUML agrandaria la caja que no las contara (las lineas, las
    # notas y las etiquetas quedarian donde no se calcularon)
    tam = {a['nombre']: (_ancho(a['nombre']), ALTO_ACTOR) for a in actores}
    vistas = {}
    for n in pant_nombres + [ctrl] + ent_nombres:
        vistas[n] = M.vista_nueva(doc, dg, els[n], 0, 0)
        tam[n] = (_ancho(n, M.renglones_vista(doc, vistas[n], els[n])), M.alto_minimo_vista(vistas[n], els[n]))

    # modelo de dominio: arriba queda el extremo que navega (hasta si navegable es 'desde') y, entre una entidad y la
    # que depende de ella, la de la que depende
    lineas_d, etiquetas, volteadas = [], {}, set()
    depende = {e['nombre']: e['depende_de'] for e in entidades if e.get('depende_de')}
    for i, a in enumerate(asociaciones):
        x, z, q = a['desde'], a['hasta'], queda[i]
        if x != z and (depende.get(x) == z or (q['navegable'] == 'desde' and depende.get(z) != x)):
            x, z = z, x
            volteadas.add(i)
        lineas_d.append((('asoc', i), x, z))
        for ext, mult, rol in (('x', q['mult_desde'], q['rol_desde']), ('z', q['mult_hacia'], q['rol_hacia'])):
            if i in volteadas:
                ext = 'z' if ext == 'x' else 'x'
            etiquetas[(('asoc', i), ext)] = (_ancho_etiqueta(('+' + rol) if rol else ''), _ancho_etiqueta(mult))
    for i, g in enumerate(generalizaciones):
        lineas_d.append((('gen', i), g['padre'], g['hijo']))
    col_a = [e['nombre'] for e in entidades if not e.get('depende_de')]
    pos_e, tam_e, medios_e, puertos = _dominio(ent_nombres, {n: tam[n] for n in ent_nombres}, lineas_d, etiquetas,
                                               col_a if lineas_control else [])
    tam.update(tam_e)
    arriba_e = min([y for _, y in pos_e.values()] + [y for m in medios_e.values() for _, y in m])
    alto_e = max(pos_e[n][1] + tam[n][1] for n in ent_nombres) - arriba_e

    # izquierda: pantallas en una columna (cada una con su nota debajo), los actores a la altura de sus pantallas y el
    # control a la altura media
    notas = {}
    for p in pantallas:
        if p.get('nota'):
            t, w, h = _medidas_nota(p['nota'])
            notas[p['nombre']] = (t, w, h + random.randint(1, 4))
    paso = [tam[n][1] + (notas[n][2] + 12 if n in notas else 0) + 50 for n in pant_nombres]
    alto_p = sum(paso) - 50
    centro = 40 + max(alto_e, alto_p, 300) / 2
    w_act = max(tam[a['nombre']][0] for a in actores)
    izq_col = max([tam[n][0] / 2 for n in pant_nombres] + [40 if notas else 0])
    der_col = max([tam[n][0] / 2 for n in pant_nombres] + [w - 40 for _, w, _ in notas.values()])
    xc = 40 + w_act + SEP_ACTOR + izq_col  # centro de la columna de pantallas
    pos, y = {}, centro - alto_p / 2
    for n, dy_ in zip(pant_nombres, paso):
        pos[n] = (xc - tam[n][0] / 2, y)
        y += dy_
    cy = {n: pos[n][1] + tam[n][1] / 2 for n in pant_nombres}
    pos[ctrl] = (xc + der_col + SEP_CONTROL, sum(cy.values()) / len(cy) - tam[ctrl][1] / 2)
    deseo = sorted((sum(cy[p] for p in (a.get('pantallas') or pant_nombres)) / len(a.get('pantallas') or pant_nombres)
                    - ALTO_ACTOR / 2, i) for i, a in enumerate(actores))
    ys = [d for d, _ in deseo]
    for k in range(1, len(ys)):
        ys[k] = max(ys[k], ys[k - 1] + ALTO_ACTOR + 60)
    corre = (sum(ys) - sum(d for d, _ in deseo)) / len(ys)
    for (_, i), y_ in zip(deseo, ys):
        n = actores[i]['nombre']
        pos[n] = (40 + (w_act - tam[n][0]) / 2, y_ - corre)
    x_ent = pos[ctrl][0] + tam[ctrl][0] + SEP_DOMINIO + (40 if lineas_control else 0)
    dx, dy = x_ent, centro - alto_e / 2 - arriba_e
    for n, (x, y_) in pos_e.items():
        pos[n] = (x + dx, y_ + dy)
    sube = min(min(y_ for _, y_ in pos.values()), centro - alto_e / 2) - 40  # nada por arriba del margen
    if sube < 0:
        pos = {n: (x, y_ - sube) for n, (x, y_) in pos.items()}
        dy -= sube
    pos = {n: (round(x), round(y_)) for n, (x, y_) in pos.items()}
    dx, dy = round(dx), round(dy)
    pos.update({n: (x + dx, y_ + dy) for n, (x, y_) in pos_e.items()})
    cy = {n: pos[n][1] + tam[n][1] / 2 for n in pant_nombres}

    for n, (x, y_) in pos.items():
        if n in vistas:
            M.mover_vista(vistas[n], x, y_, tam[n][0], tam[n][1])
        else:
            vistas[n] = M.vista_nueva(doc, dg, els[n], x, y_, tam[n][0], tam[n][1])
    cajas_nota = []
    for n in pant_nombres:
        if n in notas:
            t, w, h = notas[n]
            x0, y0 = round(xc - 40), pos[n][1] + tam[n][1] + 12
            M.nota(doc, dg, t, x0, y0, w, h)
            cajas_nota.append((x0, y0, x0 + w, y0 + h))

    lineas, reusadas = [], []

    def caja(n):
        v = vistas[n]
        return (v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height'])

    def linea(a, b, medios=(), resuelta=None):
        """Dibuja la asociacion de a hacia b; resuelta: la que ya se escogio (_asociacion), si no se busca o se crea
        sin pedir nada."""
        asoc, inv, reporte = resuelta or _asociacion(doc, usadas, els[a], els[b], {})
        if reporte:
            reusadas.append(reporte)
        t_, h_ = (b, a) if inv else (a, b)
        v = M.vista_asociacion(doc, dg, asoc, vistas[t_], vistas[h_], list(medios)[::-1] if inv else list(medios))
        lineas.append(v)
        return v, inv

    # actor -> pantallas y pantallas -> control: rectas si no tocan otra caja ni una nota; si no, con un codo
    obst = {n: caja(n) for n in pos if n not in ent_nombres}
    izq_banda = min([caja(n)[0] for n in pant_nombres] + [c[0] for c in cajas_nota]) - CODO
    der_banda = max([caja(n)[2] for n in pant_nombres] + [c[2] for c in cajas_nota]) + CODO

    def recta_libre(a, b):
        pts = [tuple(float(q) for q in p.split(':')) for p in M.ruta(vistas[a], vistas[b]).split(';')]
        otras = [c for n, c in obst.items() if n not in (a, b)] + cajas_nota
        return not any(P._cruza(pts[0], pts[1], c, 6) for c in otras)

    for a in actores:
        for p_ in (a.get('pantallas') or pant_nombres):
            medios = [] if recta_libre(a['nombre'], p_) else [(izq_banda, cy[p_])]
            if a.get('secundario'):
                linea(p_, a['nombre'], medios)
            else:
                linea(a['nombre'], p_, medios)
    for p_ in pant_nombres:
        linea(p_, ctrl, [] if recta_libre(p_, ctrl) else [(der_banda, cy[p_])])
    de_vista = {v['_id']: v for v in vistas.values()}
    for i, a in enumerate(asociaciones):
        clave = ('asoc', i)
        medios = [(x + dx, y_ + dy) for x, y_ in medios_e[clave]]
        v, inv = linea(a['desde'], a['hasta'], medios[::-1] if i in volteadas else medios, resueltas[i])
        _rectilinea(v, de_vista[v['tail']['$ref']], de_vista[v['head']['$ref']])
        _etiquetas(v, inv, queda[i], puertos, clave, vistas, dx, i in volteadas)
    if lineas_control:
        for n in col_a:
            linea(ctrl, n, [(x + dx, y_ + dy) for x, y_ in medios_e[('control', n)]])
    gens = []
    for i, g in enumerate(generalizaciones):
        rel = _generalizacion(doc, els[g['hijo']], els[g['padre']])
        medios = [(x + dx, y_ + dy) for x, y_ in medios_e[('gen', i)]][::-1]
        gens.append(P.vista_relacion(doc, dg, rel, vistas[g['hijo']], vistas[g['padre']], medios))
        _rectilinea(gens[-1], vistas[g['hijo']], vistas[g['padre']])
    doc.reindex()
    cruzan, choques = _revisar(vistas, cajas_nota, lineas + gens)
    r = {'diagrama': dg.get('name'), 'actores': len(actores), 'pantallas': len(pantallas),
         'entidades': len(entidades), 'asociaciones': len(lineas), 'lineas_que_cruzan_cajas': cruzan,
         'etiquetas_que_chocan': choques}
    if gens:
        r['generalizaciones'] = len(gens)
    if reusadas:
        r['asociaciones_reusadas'] = len(reusadas)
        r['asociaciones_cambiadas'] = sum(1 for x in reusadas if x['cambios'])
        r['reusadas'] = reusadas
    fuera = {a['nombre']: doc.name_of(els[a['nombre']]['_parent']['$ref']) for a in actores
             if els[a['nombre']]['_parent']['$ref'] != pk['_id']}
    if fuera:
        r['actores_de_otro_paquete'] = fuera
    return r
