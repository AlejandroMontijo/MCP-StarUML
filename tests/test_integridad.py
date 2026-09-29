# Integridad del .mdj: ninguna escritura puede dejar ids duplicados, referencias colgantes, _parent incoherente
# ni numeros NaN/infinito; y lo que ya venia mal se puede seguir editando sin sumarle problemas.
import json
import os
import random

import pytest

from apoyo import M, guardar_json, ids_integros, ok, tool


def test_guardar_sin_cambios_es_identico_byte_a_byte(modelo):
    antes = open(modelo, 'rb').read()
    M.Doc(modelo).save(backup=False)
    assert open(modelo, 'rb').read() == antes
    assert b'\r' not in antes and not antes.endswith(b'\n')


def test_rechaza_id_duplicado_sin_tocar_disco(modelo):
    antes, respaldos = open(modelo, 'rb').read(), set(os.listdir(M.BACKUP_DIR)) if os.path.isdir(M.BACKUP_DIR) else set()
    doc = M.Doc(modelo)
    c = doc.find('Cuenta')
    c['attributes'].append(c['attributes'][0])
    with pytest.raises(M.MdjError, match='ids duplicados'):
        doc.save()
    assert open(modelo, 'rb').read() == antes
    assert (set(os.listdir(M.BACKUP_DIR)) if os.path.isdir(M.BACKUP_DIR) else set()) == respaldos


def test_rechaza_nan(modelo):
    doc = M.Doc(modelo)
    doc.diagram('cu_1')['ownedViews'][0]['left'] = float('nan')
    with pytest.raises(M.MdjError, match='NaN'):
        doc.save(backup=False)


def test_archivo_con_problema_previo_se_puede_editar(modelo):
    doc = M.Doc(modelo)
    doc.find('Model')['ownedElements'][0]['huerfana'] = {'$ref': 'NO_EXISTE_0000000000='}
    guardar_json(doc.d, modelo)  # el problema entra por fuera (Doc.save no lo dejaria pasar)
    doc = M.Doc(modelo)
    doc.find('Cuenta')['documentation'] = 'editada'
    doc.save(backup=False)
    doc = M.Doc(modelo)
    doc.find('Model')['ownedElements'][0]['otra'] = {'$ref': 'NO_EXISTE_0000000000='}
    with pytest.raises(M.MdjError, match='referencias colgantes'):
        doc.save(backup=False)


def test_json_invalido_da_error_claro(tmp_path):
    p = tmp_path / 'roto.mdj'
    p.write_text('[1, 2')
    with pytest.raises(M.MdjError, match='no es un .mdj valido'):
        M.Doc(str(p))


def test_atributos_repetidos_se_rechazan(modelo):
    antes = open(modelo, 'rb').read()
    r = tool('mdj_atributos', archivo=modelo, clase='Cuenta', atributos=['usuario', 'usuario', 'hash'])
    assert 'Atributos repetidos' in r['error'] and open(modelo, 'rb').read() == antes
    r = tool('mdj_clase_crear', archivo=modelo, paquete='Analisis', nombre='Nueva', estereotipo='entity', atributos=['a', 'a'])
    assert 'Atributos repetidos' in r['error']


def test_borrar_quita_referencias_dentro_de_listas(modelo):
    doc = M.Doc(modelo)
    pk, ses = doc.find('Analisis'), doc.find('Sesión')
    pk['ownedElements'].append({'_type': 'UMLConstraint', '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': 'k',
                                'constrainedElements': [M.ref(ses['_id']), M.ref(doc.find('Usuario')['_id'])]})
    doc.save(backup=False)
    r = ok(tool('mdj_borrar', archivo=modelo, elemento='Sesión'))
    assert r['referencias_quitadas'] and len(M.Doc(modelo).find('k')['constrainedElements']) == 1
    assert ids_integros(modelo)


def test_borrar_elemento_con_referencia_simple_se_rechaza(modelo):
    """Una lifeline con mensajes no se puede borrar sin dejar mensajes colgando: se rechaza sin escribir."""
    doc = M.Doc(modelo)
    ll = M.interaction_of(doc, doc.diagram('cu_1_FB'))['participants'][1]
    antes = open(modelo, 'rb').read()
    r = tool('mdj_borrar', archivo=modelo, elemento=ll['_id'])
    assert 'colgantes' in r['error'] and open(modelo, 'rb').read() == antes


# ---------------------------------------------------------------------------
# Fuzzer: secuencias aleatorias de herramientas de edicion (incluidos los disparadores de corrupcion conocidos)
# ---------------------------------------------------------------------------

NOMBRES = ['Cliente', 'Pedido', 'Factura', 'Orden de Entrega', 'Máquina', 'Contrato', 'Pago', 'Unidad', 'Póliza', 'Cotización']
ATTRS = ['folio', 'fecha', 'monto', 'estado', 'descripción', 'folio']  # 'folio' repetido a proposito


def _operacion(rnd, p, n):
    doc = M.Doc(p)
    clases = [o for o in doc.ids.values() if o and o['_type'] in ('UMLClass', 'UMLActor')]
    asocs = [o for o in doc.ids.values() if o and o['_type'] == 'UMLAssociation']
    dg = doc.diagram('cu_1')
    vistas = dg.get('ownedViews', [])
    con_vista = {v['model']['$ref'] for v in vistas if isinstance(v.get('model'), dict)}
    nombres = {c.get('name') for c in clases}
    pick = lambda xs: rnd.choice(xs) if xs else None
    k = rnd.choice(['crear', 'vista', 'asoc', 'asoc', 'editar', 'attrs', 'renombrar', 'mover', 'ruta', 'nota', 'borrar',
                    'secuencia', 'etiqueta'])
    if k == 'crear':
        est = rnd.choice(['entity', 'boundary', 'control', 'ninguno', 'actor'])
        a = dict(paquete='Analisis', nombre=rnd.choice([x for x in NOMBRES if x not in nombres] or [f'C{n}']), estereotipo=est)
        if est in ('entity', 'ninguno'):
            a['atributos'] = [rnd.choice(ATTRS) for _ in range(rnd.randint(0, 3))]
        return tool('mdj_clase_crear', archivo=p, **a)
    if k == 'vista' and (c := pick([c for c in clases if c['_id'] not in con_vista])):
        return tool('mdj_vista_agregar', archivo=p, diagrama='cu_1', elemento=c['_id'], x=rnd.randint(0, 1400), y=rnd.randint(0, 900))
    if k == 'asoc' and len(clases) > 1:
        x, y = rnd.choice(clases), rnd.choice(clases)
        a = dict(desde=x['_id'], hacia=y['_id'], mult_hacia=rnd.choice(['', '1', '0..*']), navegable=rnd.choice(['hacia', 'ambos', 'ninguno', 'desde']))
        if x['_id'] in con_vista and y['_id'] in con_vista:
            a['diagrama'] = 'cu_1'
        return tool('mdj_asociacion_crear', archivo=p, **a)
    if k == 'editar' and (s := pick(asocs)):
        a = rnd.choice([{'mult': '0..*'}, {'rol': 'items'}, {'navegable': False}, {'clase': pick(clases)['_id']}])
        return tool('mdj_asociacion_editar', archivo=p, asociacion=s['_id'], extremo=rnd.choice([1, 2]), **a)
    if k == 'attrs' and (c := pick([c for c in clases if c['_type'] == 'UMLClass' and doc.kind(c) not in ('boundary', 'control')])):
        return tool('mdj_atributos', archivo=p, clase=c['_id'], atributos=[rnd.choice(ATTRS) for _ in range(rnd.randint(0, 4))])
    if k == 'renombrar' and (c := pick(clases)):
        return tool('mdj_renombrar', archivo=p, elemento=c['_id'], nuevo_nombre=rnd.choice(NOMBRES) + str(n))
    if k == 'mover' and (v := pick([v for v in vistas if v['_type'] in ('UMLClassView', 'UMLActorView')])):
        return tool('mdj_vista_mover', archivo=p, diagrama='cu_1', elemento=v['_id'], x=rnd.randint(0, 1400), y=rnd.randint(0, 900))
    if k == 'ruta' and (v := pick([v for v in vistas if v['_type'] == 'UMLAssociationView'])):
        return tool('mdj_linea_ruta', archivo=p, diagrama='cu_1', linea=v['_id'],
                    puntos=[[rnd.randint(0, 1400), rnd.randint(0, 900)] for _ in range(rnd.randint(0, 2))])
    if k == 'etiqueta' and (v := pick([v for v in vistas if v['_type'] == 'UMLAssociationView'])):
        return tool('mdj_linea_etiqueta', archivo=p, linea=v['_id'], etiqueta='headMultiplicityLabel', alpha=rnd.uniform(-3, 3), distancia=20)
    if k == 'nota':
        return tool('mdj_nota', archivo=p, diagrama=rnd.choice(['cu_1', 'cu_1_FB']), texto='nota ' * rnd.randint(1, 30),
                    x=rnd.randint(0, 900), y=rnd.randint(0, 700), ancho=rnd.randint(90, 300))
    if k == 'borrar' and (c := pick(clases + asocs)):
        return tool('mdj_borrar', archivo=p, elemento=c['_id'])
    if k == 'secuencia' and len(clases) > 1:
        tipos = [rnd.choice(clases) for _ in range(rnd.randint(2, 5))]  # con tipos repetidos a proposito
        lls = [{'clave': f'l{i}', 'tipo': t['_id']} for i, t in enumerate(tipos)]
        ms = []
        for _ in range(rnd.randint(1, 10)):
            de, a_ = rnd.sample(range(len(lls)), 2)
            ms.append({'de': f'l{de}', 'a': f'l{a_}', 'nombre': rnd.choice(['buscar(x)', 'dato']), 'reply': rnd.random() < .25})
        return tool('mdj_secuencia_generar', archivo=p, diagrama='cu_1_FB', lifelines=lls, mensajes=ms)
    return None


@pytest.mark.parametrize('semilla', [1, 2, 3])
def test_fuzzer_nunca_deja_un_archivo_invalido(modelo, semilla):
    rnd = random.Random(semilla)
    for n in range(60):
        r = _operacion(rnd, modelo, n)
        if r is not None:
            assert 'Error inesperado' not in r.get('error', ''), r['error']
        assert ids_integros(modelo), f'operacion {n} dejo el archivo inconsistente'
        json.loads(open(modelo, encoding='utf-8').read(), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
