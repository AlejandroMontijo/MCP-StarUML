# Diagrama de analisis (robustez, OOSE) de un caso de uso con la disposicion con que se dibuja en el curso:
#   actor | pantallas (boundary) en columna, cada una con su nota opcional | un control | modelo de dominio
# Actor -> pantalla y pantalla -> control son rectas con flecha. Las entidades se acomodan como modelo de dominio por
# capas, siguiendo la navegabilidad de sus asociaciones (con flecha, multiplicidad y rol), y sus lineas se rutean sin
# cruzar cajas, como en staruml_programa_a_diagrama. Las lineas control -> entidad no se dibujan por defecto (ensucian
# el diagrama y no se acostumbran); con lineas_control=True se agregan para las entidades que usa el control.
import staruml_mdj as M
from staruml_mdj import MdjError, ref


def _ancho(nombre, atributos=()):
    return round(max([M.ancho13(nombre) * 1.15 + 24, 90] + [M.ancho13('+' + x) + 24 for x in atributos]))


def _elemento(doc, paquete, nombre, estereotipo, atributos=None, documentacion=None):
    """El elemento con ese nombre en el paquete (se reusa) o uno nuevo."""
    tipo = 'UMLActor' if estereotipo == 'actor' else 'UMLClass'
    el = next((o for o in paquete.get('ownedElements', []) if o.get('name') == nombre and o['_type'] == tipo), None)
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
    if atributos is not None:
        M.set_atributos(doc, el, list(atributos))
    return el


def generar_robustez(doc, diagrama, paquete, actores, pantallas, control, entidades, asociaciones=(),
                     lineas_control=False):
    """actores: [{nombre, documentacion?, pantallas?}]  (pantallas: las que usa; default todas)
    pantallas: [{nombre, documentacion?, nota?}] de arriba abajo; nota: texto de una nota debajo de la pantalla
    control: {nombre, documentacion?}
    entidades: [{nombre, atributos?, documentacion?, depende_de?}]  (depende_de: entidad que solo se alcanza desde
               otra; con lineas_control el control no se une a ella)
    asociaciones: [{desde, hasta, mult_desde?, mult_hacia?, rol_desde?, rol_hacia?, navegable?}] entre entidades;
               navegable 'hacia' por defecto (flecha de desde a hasta)."""
    dg = doc.diagram(diagrama)
    if dg['_type'] != 'UMLClassDiagram':
        raise MdjError(f'{dg.get("name")} es {dg["_type"]}: el analisis de robustez va en un diagrama de clases')
    pk = doc.find(paquete, types=('UMLPackage', 'UMLModel', 'UMLSubsystem'))
    if not actores or not pantallas or not control or not entidades:
        raise MdjError('Faltan actores, pantallas, control o entidades')
    nombres = [a['nombre'] for a in actores] + [p['nombre'] for p in pantallas] + [control['nombre']] + \
        [e['nombre'] for e in entidades]
    repetidos = sorted({n for n in nombres if nombres.count(n) > 1})
    if repetidos:
        raise MdjError(f'Nombres repetidos: {repetidos}')
    ent = {e['nombre']: e for e in entidades}
    for e in entidades:
        if e.get('depende_de') and e['depende_de'] not in ent:
            raise MdjError(f'{e["nombre"]}: depende_de "{e["depende_de"]}" no es una entidad de la lista')
        if e.get('depende_de') and ent[e['depende_de']].get('depende_de'):
            raise MdjError(f'{e["nombre"]}: depende de {e["depende_de"]}, que tambien es dependiente; '
                           'debe depender de una entidad que use el control')
    for a in asociaciones or ():
        for k in ('desde', 'hasta'):
            if a.get(k) not in ent:
                raise MdjError(f'Asociacion {a.get("desde")} - {a.get("hasta")}: {a.get(k)} no es una entidad. En '
                               'robustez el actor solo habla con pantallas, las pantallas con el control y el control '
                               'con las entidades; esas lineas se dibujan solas')
    pant_nombres = [p['nombre'] for p in pantallas]
    for a in actores:
        for p in a.get('pantallas') or ():
            if p not in pant_nombres:
                raise MdjError(f'{a["nombre"]}: la pantalla "{p}" no esta en la lista')

    # elementos (se reusan si ya existen en el paquete)
    els = {}
    for a in actores:
        els[a['nombre']] = _elemento(doc, pk, a['nombre'], 'actor', None, a.get('documentacion'))
    for p in pantallas:
        els[p['nombre']] = _elemento(doc, pk, p['nombre'], 'boundary', None, p.get('documentacion'))
    els[control['nombre']] = _elemento(doc, pk, control['nombre'], 'control', None, control.get('documentacion'))
    for e in entidades:
        els[e['nombre']] = _elemento(doc, pk, e['nombre'], 'entity', e.get('atributos'), e.get('documentacion'))
    for n, el in els.items():
        if doc.views_of(el['_id'], dg):
            raise MdjError(f'{n} ya esta dibujado en {dg.get("name")}: usa un diagrama vacio')

    # tamanos y columnas
    tam = {a['nombre']: (_ancho(a['nombre']), 80) for a in actores}
    tam.update({p['nombre']: (_ancho(p['nombre']), 65) for p in pantallas})
    tam[control['nombre']] = (_ancho(control['nombre']), 65)
    tam.update({e['nombre']: (_ancho(e['nombre'], e.get('atributos') or ()), 73 + 15 * len(e.get('atributos') or ()))
                for e in entidades})
    import staruml_programa as P
    col_a = [e['nombre'] for e in entidades if not e.get('depende_de')]
    depende = {e['nombre']: e['depende_de'] for e in entidades if e.get('depende_de')}

    # entidades: modelo de dominio por capas siguiendo la navegabilidad (de quien la tiene hacia el otro) y lineas
    # ruteadas sin cruzar cajas, como en staruml_programa_a_diagrama
    nombres_e = [e['nombre'] for e in entidades]
    aristas = [(a['desde'], a['hasta'], False) for a in asociaciones or () if a['desde'] != a['hasta']]
    pos_e, geos = P.acomodar(nombres_e, {n: tam[n] for n in nombres_e}, aristas)
    cajas_e = {n: (x, y, x + tam[n][0], y + tam[n][1]) for n, (x, y) in pos_e.items()}
    medios_de = P.rutas(cajas_e, geos)
    sentido = {frozenset(par): par for g in geos for par in list(g['cadenas']) + g['mismas']}
    alto_e = max(c[3] for c in cajas_e.values()) - min(c[1] for c in cajas_e.values())

    # izquierda: actor | pantallas en columna (con su nota debajo si la tiene) | control, centrados en lo alto
    notas = {p['nombre']: p.get('nota') for p in pantallas if p.get('nota')}
    ANCHO_NOTA = 230
    alto_nota = {n: max(30, 11 * M.lineas_nota(t, ANCHO_NOTA - 10) + 10) for n, t in notas.items()}
    paso = [65 + (alto_nota[n] + 25 if n in notas else 0) + 45 for n in pant_nombres]
    alto_p = sum(paso) - 45
    alto = max(alto_e, alto_p, 300)
    y0 = 40
    centro = y0 + alto / 2
    x_actor = 40
    x_pant = x_actor + max(tam[a['nombre']][0] for a in actores) + 140
    ancho_p = max([tam[n][0] for n in pant_nombres] + [ANCHO_NOTA if notas else 0])
    x_control = x_pant + ancho_p + 200
    x_ent = x_control + tam[control['nombre']][0] + 160
    pos = {}
    y = centro - alto_p / 2
    for n, dy in zip(pant_nombres, paso):
        pos[n] = [x_pant, round(y)]
        y += dy
    pos[control['nombre']] = [x_control, round(centro - 32)]
    alto_a = len(actores) * 80 + (len(actores) - 1) * 80
    for i, a in enumerate(actores):
        pos[a['nombre']] = [x_actor, round(centro - alto_a / 2 + i * 160)]
    ex0 = min(c[0] for c in cajas_e.values())
    ey0 = min(c[1] for c in cajas_e.values())
    dx, dy = x_ent - ex0, round(centro - alto_e / 2) - ey0
    for n, (x, y) in pos_e.items():
        pos[n] = [x + dx, y + dy]

    vistas = {}
    for n, (x, y) in pos.items():
        vistas[n] = M.vista_nueva(doc, dg, els[n], round(x), round(y), tam[n][0])
    # cada nota junto a su pantalla, en el primer lugar que no toque las rectas actor-pantalla ni pantalla-control
    def centro_de(n):
        return (pos[n][0] + tam[n][0] / 2, pos[n][1] + tam[n][1] / 2)
    rectas = [(centro_de(a['nombre']), centro_de(p_)) for a in actores for p_ in (a.get('pantallas') or pant_nombres)]
    rectas += [(centro_de(p_), centro_de(control['nombre'])) for p_ in pant_nombres]
    ocupado = [(x, y, x + tam[n][0], y + tam[n][1]) for n, (x, y) in pos.items()]

    def libre(r):
        if any(P._cruza(a, b, r, 4) for a, b in rectas):
            return False
        return not any(r[0] < o[2] + 8 and o[0] < r[2] + 8 and r[1] < o[3] + 8 and o[1] < r[3] + 8 for o in ocupado)
    for n, texto in notas.items():
        x, y = pos[n]
        w, h, hn = tam[n][0], tam[n][1], alto_nota[n]
        # primero los lugares de costumbre (debajo, a la derecha, arriba, a la izquierda); si ninguno esta libre, el
        # lugar libre mas cercano en una rejilla alrededor de la pantalla
        lugares = [(x - 30, y + h + 15), (x + w + 15, y - 5), (x - 30, y - hn - 12), (x - ANCHO_NOTA - 15, y),
                   (x + w + 15, y + h), (x - ANCHO_NOTA - 15, y + h)]
        lugares += sorted(((x + ddx, y + ddy) for ddx in range(-ANCHO_NOTA - 60, w + 90, 15)
                           for ddy in range(-hn - 60, h + 90, 10)),
                          key=lambda q: abs(q[0] + ANCHO_NOTA / 2 - x - w / 2) + abs(q[1] + hn / 2 - y - h / 2))
        nx, ny = next(((lx, ly) for lx, ly in lugares if libre((lx, ly, lx + ANCHO_NOTA, ly + hn))), lugares[0])
        M.nota(doc, dg, texto, round(nx), round(ny), ANCHO_NOTA)
        ocupado.append((nx, ny, nx + ANCHO_NOTA, ny + hn))

    lineas = []

    def linea(a, b, medios=(), m1='', m2='', r1='', r2='', nav='hacia'):
        asoc = M.asociacion_crear(doc, els[a], els[b], m1, m2, r1, r2, nav, els[a])
        v = M.vista_asociacion(doc, dg, asoc, vistas[a], vistas[b], medios)
        _separar_extremos(v, {'tail': (m1, r1), 'head': (m2, r2)})
        lineas.append(v)

    # actor -> pantallas y pantallas -> control: rectas, con su flecha
    for a in actores:
        for p_ in (a.get('pantallas') or pant_nombres):
            linea(a['nombre'], p_)
    for p_ in pant_nombres:
        linea(p_, control['nombre'])
    if lineas_control:
        for n in col_a:
            linea(control['nombre'], n)
    for a in asociaciones or ():
        x, z = a['desde'], a['hasta']
        medios = []
        par = frozenset((x, z))
        if x != z and par in sentido:
            m = list(medios_de.get(sentido[par], []))
            medios = [(mx + dx, my + dy) for mx, my in (m if sentido[par] == (x, z) else m[::-1])]
        linea(x, z, medios, a.get('mult_desde', ''), a.get('mult_hacia', ''), a.get('rol_desde', ''),
              a.get('rol_hacia', ''), a.get('navegable', 'hacia'))
    doc.reindex()
    cajas = {n: (v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height']) for n, v in vistas.items()}
    cruzan = []
    for v in lineas:
        t_ = doc.ids[v['tail']['$ref']]['model']['$ref']
        h_ = doc.ids[v['head']['$ref']]['model']['$ref']
        otras = [c for n, c in cajas.items() if els[n]['_id'] not in (t_, h_)]
        if P._cruces(P._puntos(v), otras):
            cruzan.append(f'{doc.name_of(t_)} - {doc.name_of(h_)}')
    return {'diagrama': dg.get('name'), 'actores': len(actores), 'pantallas': len(pantallas),
            'entidades': len(entidades), 'asociaciones': len(lineas), 'lineas_que_cruzan_cajas': cruzan}


def _separar_extremos(v, textos):
    """StarUML pone la multiplicidad y el rol de cada extremo perpendiculares al ultimo tramo, a 15-20 px: si ese tramo
    es vertical, el texto queda montado sobre la linea. Ahi se alejan segun su ancho."""
    pts = [tuple(map(float, q.split(':'))) for q in (v.get('points') or '').split(';') if ':' in q]
    if len(pts) < 2:
        return
    subs = {x['_id']: x for x in v.get('subViews', [])}
    for lado, (a, b) in (('tail', (pts[0], pts[1])), ('head', (pts[-1], pts[-2]))):
        if abs(a[1] - b[1]) <= abs(a[0] - b[0]):
            continue
        mult, rol = textos[lado]
        for etiqueta, texto in (('MultiplicityLabel', mult), ('RoleNameLabel', ('+' + rol) if rol else '')):
            lab = subs.get((v.get(lado + etiqueta) or {}).get('$ref'))
            if lab and texto:
                lab['distance'] = max(lab.get('distance') or 20, round(M.ancho13(texto) / 2 + 12))
