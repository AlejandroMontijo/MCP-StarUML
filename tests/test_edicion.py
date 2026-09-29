# Herramientas de edicion y lectura sobre el caso de uso de ejemplo.
import os


from apoyo import LIFELINES, MENSAJES, M, ids_integros, ok, tool


def test_modelo_de_ejemplo_cumple_oose(modelo):
    v = ok(tool('mdj_validar', archivo=modelo))
    assert v['n_duplicados'] == v['n_colgantes'] == v['n_parent_mismatch'] == 0
    assert v['oose'] == {'problemas': [], 'avisos': []}


# --- diagramas sin vistas (asi guarda StarUML un diagrama recien creado) ---

def test_nota_en_diagrama_vacio(vacio):
    r = ok(tool('mdj_nota', archivo=vacio, diagrama='cu_1', texto='hola', x=10, y=10, ancho=120))
    assert M.Doc(vacio).get(r['vista'])['_type'] == 'UMLNoteView'


def test_secuencia_en_diagrama_sin_vistas(vacio):
    doc = M.Doc(vacio)
    doc.diagram('cu_1_FB').pop('ownedViews')
    pk = doc.find('Analisis')
    for n, st in (('B', 'boundary'), ('C', 'control')):
        pk['ownedElements'].append({'_type': 'UMLClass', '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': n,
                                    'stereotype': M.ref(doc.stereotype_id(st))})
    doc.save(backup=False)
    ok(tool('mdj_secuencia_generar', archivo=vacio, diagrama='cu_1_FB', lifelines=[{'clave': 'b', 'tipo': 'B'}, {'clave': 'c', 'tipo': 'C'}],
            mensajes=[{'de': 'b', 'a': 'c', 'nombre': 'm()'}]))
    assert ids_integros(vacio)


def test_linea_ruta_en_diagrama_vacio_da_error_claro(vacio):
    assert 'No encontre esa linea' in tool('mdj_linea_ruta', archivo=vacio, diagrama='cu_1', linea='XYZ')['error']


# --- secuencias ---

def test_regenerar_secuencia_conserva_notas_y_descarta_enlaces_colgados(modelo):
    doc = M.Doc(modelo)
    dg = doc.diagram('cu_1_FB')
    nota = M.nota(doc, dg, 'Precondicion: usuario registrado', 500, 60, 150)
    ll_v = next(v for v in dg['ownedViews'] if v['_type'] == 'UMLSeqLifelineView')
    dg['ownedViews'].append({'_type': 'UMLNoteLinkView', '_id': doc.new_id(), '_parent': M.ref(dg['_id']),
                             'head': M.ref(ll_v['_id']), 'tail': M.ref(nota['_id']), 'points': '500:70;300:70'})
    doc.save(backup=False)
    r = ok(tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=MENSAJES))
    tipos = [v['_type'] for v in M.Doc(modelo).diagram('cu_1_FB')['ownedViews']]
    assert r['vistas_conservadas'] == 1 and r['vistas_descartadas'] == ['UMLNoteLinkView']
    assert tipos[0] == 'UMLFrameView' and tipos[-1] == 'UMLNoteView'


def test_dos_lifelines_del_mismo_tipo(modelo):
    lls = [{'clave': 'ctrl', 'tipo': 'Control Autenticación'}, {'clave': 'c1', 'tipo': 'Cuenta'}, {'clave': 'c2', 'tipo': 'Cuenta'}]
    ms = [{'de': 'ctrl', 'a': 'c1', 'nombre': 'leer()'}, {'de': 'c1', 'a': 'c2', 'nombre': 'copiar()'}]
    ids = []
    for orden in (lls, lls, [lls[0], lls[2], lls[1]]):
        ok(tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=orden, mensajes=ms))
        assert ids_integros(modelo)
        doc = M.Doc(modelo)
        it = M.interaction_of(doc, doc.diagram('cu_1_FB'))
        ids.append({doc.get(l['represent']['$ref'])['name']: l['_id'] for l in it['participants']})
        assert len(set(ids[-1].values())) == 3
        assert it['messages'][1]['source'] != it['messages'][1]['target']
    assert ids[0] == ids[1] == ids[2]  # cada clave conserva su lifeline aunque cambie el orden


def test_opciones_de_secuencia_validadas(modelo):
    r = tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=MENSAJES,
             opciones={'espaciado': [36, 29]})
    assert 'minimo <= maximo' in r['error']
    assert 'Opcion desconocida' in tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=LIFELINES,
                                        mensajes=MENSAJES, opciones={'color': 1})['error']
    ok(tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=MENSAJES,
            opciones={'espaciado': [30, 30], 'semilla': 'abc'}))


def test_clase_sin_nombre_no_rompe_validacion_ni_secuencia(modelo):
    doc = M.Doc(modelo)
    pk = doc.find('Analisis')
    pk['ownedElements'].append({'_type': 'UMLClass', '_id': doc.new_id(), '_parent': M.ref(pk['_id']),
                                'stereotype': M.ref(doc.stereotype_id('control'))})
    doc.save(backup=False)
    v = ok(tool('mdj_validar', archivo=modelo))
    assert any('controles' in p for p in v['oose']['problemas'])
    r = ok(tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=MENSAJES))
    assert 'oose' in r


def test_reglas_oose_de_mensajes(modelo):
    ms = [{'de': 'usr', 'a': 'ui', 'nombre': 'pedir()'}, {'de': 'ctrl', 'a': 'usr', 'nombre': 'avisar()'},
          {'de': 'ui', 'a': 'cta', 'nombre': 'leer()'}, {'de': 'ui', 'a': 'usr', 'nombre': 'ok', 'reply': True},
          {'de': 'cta', 'a': 'ses', 'nombre': 'enlazar()'}]
    ok(tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=ms))
    prob = ok(tool('mdj_validar', archivo=modelo))['oose']['problemas']
    assert any('control->actor' in p for p in prob)
    assert any('boundary->entity' in p for p in prob)
    assert any('Reply de boundary a actor' in p for p in prob)
    assert not any('entity->entity sin asociacion' in p for p in prob)  # Cuenta--Sesion estan asociadas


# --- vistas, lineas y nombres ---

def test_renombrar_lifeline_sin_nombre_y_clase(modelo):
    doc = M.Doc(modelo)
    ll = M.interaction_of(doc, doc.diagram('cu_1_FB'))['participants'][1]
    ok(tool('mdj_renombrar', archivo=modelo, elemento=ll['_id'], nuevo_nombre='ui'))
    doc = M.Doc(modelo)
    assert [M._name_label(v)['text'] for _, v in doc.views_of(ll['_id'])] == ['ui: Pantalla Autenticación']
    r = ok(tool('mdj_renombrar', archivo=modelo, elemento='Sesión', nuevo_nombre='Sesion Activa'))
    doc = M.Doc(modelo)
    ses_ll = [l for l in M.interaction_of(doc, doc.diagram('cu_1_FB'))['participants']
              if M.lifeline_info(doc, l['_id'])[0] == 'Sesion Activa'][0]
    assert M._name_label(doc.views_of(ses_ll['_id'])[0][1])['text'] == ': Sesion Activa' and r['vistas_actualizadas'] == 2


def test_vista_de_interfaz_y_de_clase_comun(modelo):
    doc = M.Doc(modelo)
    pk = doc.find('Analisis')
    pk['ownedElements'] += [{'_type': 'UMLInterface', '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': 'IRepositorio'}]
    comun = {'_type': 'UMLClass', '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': 'Utilidad'}
    comun['attributes'] = [{'_type': 'UMLAttribute', '_id': doc.new_id(), '_parent': M.ref(comun['_id']), 'name': 'x', 'type': 'int'}]
    pk['ownedElements'].append(comun)
    doc.save(backup=False)
    vi = ok(tool('mdj_vista_agregar', archivo=modelo, diagrama='cu_1', elemento='IRepositorio', x=300, y=600))
    vc = ok(tool('mdj_vista_agregar', archivo=modelo, diagrama='cu_1', elemento='Utilidad', x=500, y=600))
    doc = M.Doc(modelo)
    assert doc.get(vi['vista'])['_type'] == 'UMLInterfaceView'
    v = doc.get(vc['vista'])
    assert not v.get('suppressAttributes')  # atributos visibles en clases comunes
    textos = [s['text'] for c in v['subViews'] if c['_type'] == 'UMLAttributeCompartmentView' for s in c.get('subViews', [])]
    assert textos == ['+x: int']


def test_asociacion_reflexiva_dibuja_un_lazo(modelo):
    r = ok(tool('mdj_asociacion_crear', archivo=modelo, desde='Cuenta', hacia='Cuenta', diagrama='cu_1'))
    pts = r['puntos'].split(';')
    assert len(pts) == 5 and pts[0] != pts[-1]


def test_avisos_oose_al_crear_asociacion(modelo):
    r = ok(tool('mdj_asociacion_crear', archivo=modelo, desde='Pantalla Autenticación', hacia='Cuenta'))
    assert r['avisos']


# --- crear actores, paquetes y diagramas ---

def _avisos_cu(path):
    return [a for a in M.reglas_oose(M.Doc(path))['avisos'] if 'caso' in a.lower()]


def test_consistencia_de_caso_de_uso_con_su_paquete_de_robustez(modelo):
    doc = M.Doc(modelo)
    raiz = next(o for o in doc.ids.values() if o and o['_type'] == 'UMLModel')
    # el caso de uso se llama como el paquete de robustez (sin acentos ni mayusculas de por medio)
    uc = {'_type': 'UMLUseCase', '_id': doc.new_id(), '_parent': {'$ref': raiz['_id']}, 'name': 'ANÁLISIS'}
    raiz['ownedElements'].append(uc)
    doc.reindex()
    usuario = doc.find('Usuario')
    asoc = M.asociacion_crear(doc, usuario, uc)
    doc.save(backup=False)
    assert _avisos_cu(modelo) == []
    assert ok(tool('mdj_validar', archivo=modelo))['oose'] == {'problemas': [], 'avisos': []}

    # un actor del caso de uso sin boundary, y una boundary que atiende a un actor ajeno al caso de uso
    doc = M.Doc(modelo)
    M.borrar(doc, doc.get(asoc['_id']))
    admin = {'_type': 'UMLActor', '_id': doc.new_id(), '_parent': {'$ref': raiz['_id']}, 'name': 'Administrador'}
    doc.get(raiz['_id'])['ownedElements'].append(admin)
    doc.reindex()
    M.asociacion_crear(doc, admin, doc.get(uc['_id']))
    doc.save(backup=False)
    avisos = _avisos_cu(modelo)
    assert len(avisos) == 2, avisos
    assert any('Administrador participa' in a for a in avisos)
    assert any('Usuario se asocia con Pantalla Autenticación pero no participa' in a for a in avisos)

    # si Usuario especializa a Administrador, participa por herencia
    doc = M.Doc(modelo)
    gen = {'_type': 'UMLGeneralization', '_id': doc.new_id(), '_parent': {'$ref': usuario['_id']},
           'source': {'$ref': usuario['_id']}, 'target': {'$ref': admin['_id']}}
    doc.get(usuario['_id']).setdefault('ownedElements', []).append(gen)
    doc.reindex()
    doc.save(backup=False)
    assert _avisos_cu(modelo) == []

    # sin control en el paquete, y otro caso de uso aun sin analizar
    doc = M.Doc(modelo)
    doc.get(raiz['_id'])['ownedElements'].append({'_type': 'UMLUseCase', '_id': doc.new_id(),
                                                   '_parent': {'$ref': raiz['_id']}, 'name': 'Consultar saldo'})
    doc.reindex()
    doc.save(backup=False)
    ok(tool('mdj_borrar', archivo=modelo, elemento='Control Autenticación', forzar=True))
    avisos = _avisos_cu(modelo)
    assert any('no tiene clase control' in a for a in avisos), avisos
    assert any("1 caso(s) de uso sin paquete de analisis del mismo nombre: ['Consultar saldo']" in a for a in avisos), avisos


def test_sin_convencion_de_paquetes_no_hay_avisos_de_casos_de_uso(modelo):
    doc = M.Doc(modelo)
    raiz = next(o for o in doc.ids.values() if o and o['_type'] == 'UMLModel')
    raiz['ownedElements'].append({'_type': 'UMLUseCase', '_id': doc.new_id(), '_parent': {'$ref': raiz['_id']}, 'name': 'Iniciar sesión'})
    doc.reindex()
    doc.save(backup=False)
    assert _avisos_cu(modelo) == []

def test_crear_actor_paquete_y_diagramas(vacio):
    ok(tool('mdj_paquete_crear', archivo=vacio, nombre='Diseño'))
    a = ok(tool('mdj_clase_crear', archivo=vacio, paquete='Diseño', nombre='Servicio de Correo', estereotipo='actor'))
    assert 'sin atributos' in tool('mdj_clase_crear', archivo=vacio, paquete='Diseño', nombre='X', estereotipo='actor', atributos=['a'])['error']
    ds = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='secuencia', nombre='cu_2_FB', dentro_de='Diseño', por_defecto=True))
    dc = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='clases', nombre='cu_2'))
    ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='casos_de_uso', nombre='Casos'))
    doc = M.Doc(vacio)
    assert doc.get(a['clase'])['_type'] == 'UMLActor'
    seq = doc.get(ds['diagrama'])
    assert seq['defaultDiagram'] is True and [v['_type'] for v in seq['ownedViews']] == ['UMLFrameView']
    assert M.interaction_of(doc, seq)['_type'] == 'UMLInteraction'
    assert sum(1 for d in doc.diagrams() if d.get('defaultDiagram')) == 1
    ok(tool('mdj_vista_agregar', archivo=vacio, diagrama=dc['diagrama'], elemento='Servicio de Correo', x=10, y=10))
    assert ids_integros(vacio)


# --- rutas, respaldos, lectura ---

def test_salida_relativa_se_guarda_junto_al_mdj(modelo, tmp_path, monkeypatch):
    otro = tmp_path / 'cwd_del_servidor'
    otro.mkdir()
    monkeypatch.chdir(otro)
    r = ok(tool('mdj_documentacion', archivo=modelo, elemento='Cuenta', texto='x', salida='copia.mdj'))
    assert r['guardado_en'] == os.path.join(os.path.dirname(modelo), 'copia.mdj')


def test_carpetas_permitidas(modelo, tmp_path, monkeypatch):
    monkeypatch.setenv('STARUML_MCP_ALLOWED_DIRS', str(tmp_path))
    ok(tool('mdj_resumen', archivo=modelo))
    fuera = tmp_path.parent / (tmp_path.name + '-otro')  # mismo prefijo, otra carpeta
    assert 'fuera de las carpetas permitidas' in tool('mdj_documentacion', archivo=modelo, elemento='Cuenta', texto='x',
                                                      salida=str(fuera / 'x.mdj'))['error']


def test_rotacion_de_respaldos(modelo, monkeypatch):
    monkeypatch.setenv('STARUML_MCP_BACKUP_KEEP', '3')
    for i in range(6):
        ok(tool('mdj_documentacion', archivo=modelo, elemento='Cuenta', texto=f'v{i}'))
    propios = [f for f in os.listdir(M.BACKUP_DIR) if f.startswith('modelo_')]
    assert len(propios) == 3


def test_modelo_paginado(modelo):
    r = ok(tool('mdj_modelo', archivo=modelo, limite=2))
    assert len(r['clases']) == 2 and r['total']['clases'] == 5 and r['siguiente_desde'] == 2
    r2 = ok(tool('mdj_modelo', archivo=modelo, limite=2, desde=4))
    assert len(r2['clases']) == 1


def test_lectura_y_diff(modelo, tmp_path):
    copia = str(tmp_path / 'copia.mdj')
    ok(tool('mdj_borrar', archivo=modelo, elemento='Sesión', salida=copia))
    d = ok(tool('mdj_diff', archivo_a=modelo, archivo_b=copia))
    assert d['quitados'].get('UMLClass') == 1 and any('Sesión' in x for x in d['detalle_quitados'])
    g = ok(tool('mdj_geometria', archivo=modelo, diagrama='cu_1'))
    assert len(g['cajas']) == 6 and len(g['lineas']) == 5
    s = ok(tool('mdj_secuencia', archivo=modelo, diagrama='cu_1_FB'))
    assert len(s['mensajes']) == len(MENSAJES) and s['mensajes'][3]['reply']
    assert ok(tool('mdj_buscar', archivo=modelo, tipo='UMLClass', limite=2)).__len__() == 2
    assert 'Robustez' in tool('staruml_reglas')['texto']


def test_estado_informa_deteccion_y_herramientas():
    r = ok(tool('staruml_estado'))
    assert set(r) >= {'staruml_abierto', 'cli_staruml', 'chrome', 'carpeta_respaldos', 'version_mcp'}
