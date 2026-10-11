# Correcciones del servidor y de staruml_mdj: esquema de mdj_robustez_generar (actor secundario y generalizaciones),
# descripciones que prometian mas de lo que hace el codigo, sobre en mdj_dibujar, clases y paquetes repetidos y el
# modo de metodos de la regla OOSE (control_getset).
import os
import shutil

import pytest

from apoyo import RAIZ, M, S, ids_integros, ok, tool

import staruml_uml as U

REAL_VIGENTE = os.path.join(os.path.dirname(RAIZ), 'UML actualizado', 'AvanceDiagramaFlujoF1-F2-F3-F4-F5.mdj')


def _bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def _herramienta(nombre):
    return next(t for t in S.TOOLS if t['name'] == nombre)


# ---------------------------------------------------------------------------
# mdj_robustez_generar: secundario y generalizaciones pasan el esquema y llegan al generador
# ---------------------------------------------------------------------------

def test_robustez_acepta_actor_secundario_y_generalizaciones(vacio):
    r = ok(tool('mdj_robustez_generar', archivo=vacio, diagrama='cu_1', paquete='Analisis',
                actores=[{'nombre': 'Asesor', 'pantallas': ['BC_Registro']},
                         {'nombre': 'Servicio de Correo', 'secundario': True, 'pantallas': ['BC_Correo']}],
                pantallas=[{'nombre': 'BC_Registro', 'nota': 'Junta las pantallas de registro.'},
                           {'nombre': 'BC_Correo'}],
                control={'nombre': 'ControlRenta'},
                entidades=[{'nombre': 'Cliente', 'atributos': ['nombre']},
                           {'nombre': 'ClienteEmpresa', 'atributos': ['razonSocial']}],
                generalizaciones=[{'hijo': 'ClienteEmpresa', 'padre': 'Cliente'}]))
    assert r['generalizaciones'] == 1
    doc = M.Doc(vacio)
    correo, bc = doc.find('UMLActor:Servicio de Correo'), doc.find('BC_Correo')
    asoc = [o for o in doc.ids.values() if o and o['_type'] == 'UMLAssociation'
            and {o['end1']['reference']['$ref'], o['end2']['reference']['$ref']} == {correo['_id'], bc['_id']}]
    assert len(asoc) == 1
    extremo = {e['reference']['$ref']: e for e in (asoc[0]['end1'], asoc[0]['end2'])}
    # la flecha va de la pantalla hacia el actor secundario
    assert extremo[correo['_id']].get('navigable') == 'navigable'
    assert extremo[bc['_id']].get('navigable') != 'navigable'
    hijo, padre = doc.find('ClienteEmpresa'), doc.find('UMLClass:Cliente')
    gens = [o for o in doc.ids.values() if o and o['_type'] == 'UMLGeneralization'
            and o['source']['$ref'] == hijo['_id'] and o['target']['$ref'] == padre['_id']]
    assert len(gens) == 1 and doc.views_of(gens[0]['_id'], doc.diagram('cu_1'))
    assert ids_integros(vacio)


def test_robustez_esquema_trae_secundario_y_generalizaciones():
    t = _herramienta('mdj_robustez_generar')
    props = t['inputSchema']['properties']
    assert props['actores']['items']['properties']['secundario']['type'] == 'boolean'
    gen = props['generalizaciones']
    assert gen['items']['required'] == ['hijo', 'padre'] and gen['items']['additionalProperties'] is False
    # un elemento con otra clave sigue rechazandose
    e = S.revisar_args(t['inputSchema'], {'archivo': 'x.mdj', 'diagrama': 'd', 'paquete': 'p', 'actores': [{'nombre': 'a'}],
                                          'pantallas': [{'nombre': 'b'}], 'control': {'nombre': 'c'},
                                          'entidades': [{'nombre': 'e'}],
                                          'generalizaciones': [{'hijo': 'e', 'padre': 'f', 'tipo': 'x'}]})
    assert e and 'tipo' in e


def test_robustez_descripcion_sin_promesas_falsas():
    t = _herramienta('mdj_robustez_generar')
    desc = t['description']
    assert 'cada linea es una asociacion nueva' not in desc
    assert 'reusa' in desc and 'secundario' in desc
    nota = t['inputSchema']['properties']['pantallas']['items']['properties']['nota']['description']
    assert 'debajo' in nota and 'si hay lugar' not in nota


def test_robustez_nota_siempre_debajo_de_su_pantalla(vacio):
    ok(tool('mdj_robustez_generar', archivo=vacio, diagrama='cu_1', paquete='Analisis', actores=[{'nombre': 'Asesor'}],
            pantallas=[{'nombre': 'BC_Uno', 'nota': 'Una nota corta.'},
                       {'nombre': 'BC_Dos', 'nota': 'Otra nota con algo mas de texto para que ocupe dos renglones.'}],
            control={'nombre': 'ControlX'}, entidades=[{'nombre': 'Cosa'}]))
    doc = M.Doc(vacio)
    dg = doc.diagram('cu_1')
    notas = sorted((v for v in dg['ownedViews'] if v['_type'] == 'UMLNoteView'), key=lambda v: v['top'])
    pantallas = [doc.view_in(dg, n) for n in ('BC_Uno', 'BC_Dos')]
    assert len(notas) == 2
    for nota, p in zip(notas, pantallas):
        assert nota['top'] >= p['top'] + p['height']


# ---------------------------------------------------------------------------
# mdj_dibujar: sobre solo en los simbolos que el catalogo marca con va_sobre
# ---------------------------------------------------------------------------

def test_catalogo_va_sobre_coincide_con_lo_que_usa_dibujar():
    pl = U.plantillas()['plantillas']
    for tipo, simbolos in pl.items():
        cat = {s['simbolo']: s for s in U.catalogo(tipo)['simbolos']}
        for clave, p in simbolos.items():
            if p['forma'] == 'line':
                continue
            assert ('va_sobre' in cat[clave.split('|')[0]]) == any(U.necesita(p)), (tipo, clave)


def test_dibujar_rechaza_sobre_en_un_simbolo_sin_va_sobre(vacio):
    da = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='actividades', nombre='Proceso'))['diagrama']
    accion = ok(tool('mdj_dibujar', archivo=vacio, diagrama=da, simbolo='Action', nombre='Cobrar', x=60, y=60))
    antes = _bytes(vacio)
    for simbolo in ('Swimlane (Vertical)', 'Swimlane (Horizontal)', 'Action'):
        r = tool('mdj_dibujar', archivo=vacio, diagrama=da, simbolo=simbolo, nombre='Caja', sobre=accion['vista'])
        assert 'no va sobre otra vista' in r['error'] and 'va_sobre' in r['error'], r
    r = tool('mdj_dibujar', archivo=vacio, diagrama=da, simbolo='Control Flow', sobre=accion['vista'])
    assert 'es una linea' in r['error']
    assert _bytes(vacio) == antes
    # los que si traen va_sobre siguen funcionando
    pin = ok(tool('mdj_dibujar', archivo=vacio, diagrama=da, simbolo='Input Pin', nombre='pedido', sobre=accion['vista']))
    assert pin['elemento_tipo'] == 'UMLInputPin'
    # un carril sin sobre se dibuja como siempre
    ok(tool('mdj_dibujar', archivo=vacio, diagrama=da, simbolo='Swimlane (Vertical)', nombre='Caja', x=300, y=40))
    assert ids_integros(vacio)


def test_dibujar_no_promete_sobre_para_region_ni_particion():
    desc = _herramienta('mdj_dibujar')['description']
    assert 'region' not in desc and 'particion' not in desc
    assert 'va_sobre' in desc


def test_descripciones_no_prometen_lo_que_no_garantizan():
    desc = {t['name']: t['description'] for t in S.TOOLS}
    assert 'ninguna etiqueta sobre activaciones' not in desc['mdj_secuencia_generar']
    assert 'ajustes' in desc['mdj_secuencia_generar']
    assert 'lineas_que_cruzan_cajas' in desc['staruml_programa_a_diagrama']
    assert 'lineas_que_cruzan_cajas' in desc['mdj_robustez_generar']
    assert 'lineas_que_cruzan_cajas' in desc['mdj_diagrama_generar']
    assert 'porcentaje_sincronizacion' in desc['staruml_comparar_codigo']


# ---------------------------------------------------------------------------
# mdj_clase_crear y mdj_paquete_crear: sin repetir nombre en el mismo contenedor
# ---------------------------------------------------------------------------

def test_clase_crear_no_duplica_en_el_mismo_paquete(modelo):
    antes = _bytes(modelo)
    for est in ('entity', 'boundary', 'ninguno'):
        r = tool('mdj_clase_crear', archivo=modelo, paquete='Analisis', nombre='Cuenta', estereotipo=est)
        assert 'Ya hay un UMLClass "Cuenta" en Analisis' in r['error'], r
    r = tool('mdj_clase_crear', archivo=modelo, paquete='Analisis', nombre='Usuario', estereotipo='actor')
    assert 'Ya hay un UMLActor "Usuario"' in r['error']
    assert _bytes(modelo) == antes
    # una clase y un actor con el mismo nombre si pueden convivir (el actor Cliente y la entity Cliente)
    ok(tool('mdj_clase_crear', archivo=modelo, paquete='Analisis', nombre='Cuenta', estereotipo='actor'))
    ok(tool('mdj_clase_crear', archivo=modelo, paquete='Analisis', nombre='Usuario', estereotipo='entity'))
    # en otro paquete tampoco hay conflicto
    ok(tool('mdj_paquete_crear', archivo=modelo, nombre='Diseno'))
    ok(tool('mdj_clase_crear', archivo=modelo, paquete='Diseno', nombre='Cuenta', estereotipo='entity'))
    doc = M.Doc(modelo)
    cuentas = [o for o in doc.ids.values() if o and o.get('name') == 'Cuenta']
    assert sorted(o['_type'] for o in cuentas) == ['UMLActor', 'UMLClass', 'UMLClass']
    assert ids_integros(modelo)


def test_paquete_crear_no_duplica_en_el_mismo_contenedor(vacio):
    antes = _bytes(vacio)
    r = tool('mdj_paquete_crear', archivo=vacio, nombre='Analisis')
    assert 'Ya hay un UMLPackage "Analisis" en Model' in r['error'], r
    assert _bytes(vacio) == antes
    # un modelo es un paquete: tampoco puede haber un paquete con su nombre en el mismo lugar
    doc = M.Doc(vacio)
    pk = doc.find('Analisis')
    pk['ownedElements'].append({'_type': 'UMLModel', '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': 'Sub'})
    doc.reindex()
    doc.save(backup=False)
    antes = _bytes(vacio)
    r = tool('mdj_paquete_crear', archivo=vacio, nombre='Sub', dentro_de='Analisis')
    assert 'Ya hay un UMLModel "Sub" en Analisis' in r['error'], r
    assert _bytes(vacio) == antes
    # dentro de otro contenedor el mismo nombre si se puede
    ok(tool('mdj_paquete_crear', archivo=vacio, nombre='Analisis', dentro_de='Analisis'))
    ok(tool('mdj_paquete_crear', archivo=vacio, nombre='Dominio'))
    r = tool('mdj_paquete_crear', archivo=vacio, nombre='Dominio')
    assert 'Ya hay un UMLPackage "Dominio"' in r['error']
    assert ids_integros(vacio)


def test_nombre_libre_compara_tipos_con_el_metamodelo():
    cont = {'_type': 'UMLPackage', '_id': 'p', 'name': 'P',
            'ownedElements': [{'_type': 'UMLModel', '_id': 'm', 'name': 'X'},
                              {'_type': 'UMLActor', '_id': 'a', 'name': 'Y'},
                              {'_type': 'UMLInterface', '_id': 'i', 'name': 'Z'}]}
    with pytest.raises(M.MdjError, match='UMLModel "X"'):
        M.nombre_libre(cont, 'X', 'UMLPackage')
    M.nombre_libre(cont, 'Y', 'UMLClass')     # actor y clase: tipos distintos
    M.nombre_libre(cont, 'Z', 'UMLClass')     # interfaz y clase: ninguno es subtipo del otro
    M.nombre_libre(cont, 'x', 'UMLPackage')   # el nombre se compara tal cual
    with pytest.raises(M.MdjError):
        M.nombre_libre(cont, 'Y', 'UMLActor')


# ---------------------------------------------------------------------------
# mdj_validar: metodos = ninguno | control_getset
# ---------------------------------------------------------------------------

def _con_metodos(path):
    """Cuenta (entity) con get/set/is de sus atributos y un metodo de negocio; el control con metodos; la boundary con
    uno; y Sesion (entity) con un get de un atributo que no es suyo."""
    doc = M.Doc(path)

    def ops(clase, nombres):
        c = doc.find(clase)
        c['operations'] = [{'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': M.ref(c['_id']), 'name': n}
                           for n in nombres]
    ops('Cuenta', ['getUsuario', 'setUsuario', 'isContraseña', 'validarAcceso'])
    ops('Control Autenticación', ['autenticar', 'cerrarSesion'])
    ops('Pantalla Autenticación', ['mostrar'])
    ops('Sesión', ['getInicio', 'getUsuario'])
    doc.reindex()
    doc.save(backup=False)
    return path


def _metodos(problemas):
    return sorted(p for p in problemas if 'metodos' in p)


def test_validar_metodos_ninguno_es_el_default(modelo):
    _con_metodos(modelo)
    por_omision = ok(tool('mdj_validar', archivo=modelo))['oose']['problemas']
    explicito = ok(tool('mdj_validar', archivo=modelo, metodos='ninguno'))['oose']['problemas']
    assert por_omision == explicito
    assert len(_metodos(por_omision)) == 4
    assert all('en analisis no se ponen metodos' in p for p in _metodos(por_omision))


def test_validar_control_getset(modelo):
    _con_metodos(modelo)
    probs = _metodos(ok(tool('mdj_validar', archivo=modelo, metodos='control_getset'))['oose']['problemas'])
    assert len(probs) == 3, probs
    texto = '\n'.join(probs)
    assert "Cuenta (entity) tiene metodos que no son get/set/is de sus propios atributos: ['validarAcceso']" in texto
    assert "Sesión (entity) tiene metodos que no son get/set/is de sus propios atributos: ['getUsuario']" in texto
    assert 'Pantalla Autenticación (boundary) tiene metodos' in texto
    assert 'Control' not in texto


def test_validar_control_getset_sin_metodos_de_mas(modelo):
    doc = M.Doc(modelo)
    c = doc.find('Cuenta')
    c['operations'] = [{'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': M.ref(c['_id']), 'name': n}
                       for n in ('getUsuario', 'setUsuario', 'getContraseña', 'setContraseña')]
    doc.reindex()
    doc.save(backup=False)
    assert not _metodos(ok(tool('mdj_validar', archivo=modelo, metodos='control_getset'))['oose']['problemas'])
    assert _metodos(ok(tool('mdj_validar', archivo=modelo))['oose']['problemas'])


def test_validar_metodos_valor_invalido(modelo):
    r = tool('mdj_validar', archivo=modelo, metodos='todos')
    assert 'metodos' in r['error'] and 'control_getset' in r['error']
    with pytest.raises(M.MdjError, match='control_getset'):
        M.reglas_oose(M.Doc(modelo), 'todos')


def test_validar_control_getset_en_el_modelo_real(tmp_path):
    if not os.path.exists(REAL_VIGENTE):
        pytest.skip('sin el modelo real vigente')
    copia = str(tmp_path / 'real.mdj')
    shutil.copy(REAL_VIGENTE, copia)
    r = ok(tool('mdj_validar', archivo=copia, metodos='control_getset'))
    assert not _metodos(r['oose']['problemas']), _metodos(r['oose']['problemas'])
    assert _bytes(copia) == _bytes(REAL_VIGENTE)
