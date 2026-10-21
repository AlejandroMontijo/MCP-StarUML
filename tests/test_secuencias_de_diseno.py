# Diseno (como el ejemplo de la sesion de analisis a diseno: UsuarioExterno -> interfaz del subsistema -> fachada
# «Facade» -> control -> objeto de negocio «Singleton»). Las reglas de OOSE son del analisis: no se aplican a esas
# secuencias ni al control dibujado en etiqueta junto a la fachada. mdj_secuencia_revisar acepta los tipos como
# argumentos (buscarCuenta(Long)) y no pide mensajes al constructor ni a getInstance. Y una llamada hacia la derecha
# justo despues de un auto-mensaje deja el ancho de la activacion anidada (antes se bajaba cientos de pixeles).
from staruml_mcp import uml as U
from apoyo import LIFELINES, MENSAJES, M, ids_integros, ok, tool


def operacion(doc, c, nombre, params=(), ret=None, estatico=False):
    o = {'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': M.ref(c['_id']), 'name': nombre}
    if estatico:
        o['isStatic'] = True
    o['parameters'] = [{'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': M.ref(o['_id']), 'name': n, 'type': t}
                       for n, t in params]
    if ret:
        o['parameters'].append({'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': M.ref(o['_id']), 'type': ret,
                                'direction': 'return'})
    c.setdefault('operations', []).append(o)


def con_diseno(path):
    """Paquete admCuentas con la interfaz, la fachada, el control y el objeto de negocio, su diagrama de clases (el
    control en etiqueta junto a la fachada) y la secuencia metodo_buscarCuenta."""
    doc = M.Doc(path)
    raiz = doc.find('UMLModel:Model')
    pk = {'_type': 'UMLPackage', '_id': doc.new_id(), '_parent': M.ref(raiz['_id']), 'name': 'admCuentas',
          'ownedElements': []}
    raiz['ownedElements'].append(pk)

    def elemento(tipo, nombre, estereotipo=None):
        e = {'_type': tipo, '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': nombre}
        if estereotipo:
            e['stereotype'] = estereotipo
        pk['ownedElements'].append(e)
        return e
    usr = elemento('UMLActor', 'UsuarioExterno')
    interfaz = elemento('UMLInterface', 'IAdmCuentas')
    fachada = elemento('UMLClass', 'FAdmCuentas', 'Facade')
    control = elemento('UMLClass', 'ControlAdmCuentas', M.ref(doc.stereotype_id('control')))
    bo = elemento('UMLClass', 'CuentaBO', 'Singleton')
    elemento('UMLClass', 'CuentaDTO')
    for c in (interfaz, fachada, control):
        operacion(doc, c, 'buscarCuenta', [('id', 'Long')], 'CuentaDTO')
    operacion(doc, control, 'validarId', [('id', 'Long')], 'boolean')
    operacion(doc, bo, 'CuentaBO')
    operacion(doc, bo, 'getInstance', ret='CuentaBO', estatico=True)
    operacion(doc, bo, 'consultarCuenta', [('id', 'Long')], 'CuentaDTO')
    doc.reindex()
    for tipo, x, y in (('UMLAssociation', usr, interfaz), ('UMLInterfaceRealization', fachada, interfaz),
                       ('UMLAssociation', fachada, control), ('UMLDependency', control, bo)):
        U.crear_relacion(doc, tipo, x['_id'], y['_id'])
        doc.reindex()
    dc = M.crear_diagrama(doc, 'clases', 'diagrama_clases', pk['_id'])
    M.vista_nueva(doc, dc, fachada, 40, 40)
    M.vista_nueva(doc, dc, control, 40, 260)['stereotypeDisplay'] = 'label'
    dg = M.crear_diagrama(doc, 'secuencia', 'metodo_buscarCuenta', pk['_id'])
    lls = [{'clave': k, 'tipo': e['_id']} for k, e in (('usr', usr), ('i', interfaz), ('f', fachada), ('c', control),
                                                         ('bo', bo))]
    ms = [{'de': 'usr', 'a': 'i', 'nombre': 'buscarCuenta(Long)'}, {'de': 'i', 'a': 'f', 'nombre': 'buscarCuenta(Long)'},
          {'de': 'f', 'a': 'c', 'nombre': 'buscarCuenta(Long)'}, {'de': 'c', 'a': 'c', 'nombre': 'validarId(Long)'},
          {'de': 'c', 'a': 'bo', 'nombre': 'consultarCuenta(Long)'},
          {'de': 'bo', 'a': 'c', 'nombre': 'CuentaDTO cuenta', 'reply': True},
          {'de': 'c', 'a': 'f', 'nombre': 'CuentaDTO cuenta', 'reply': True},
          {'de': 'f', 'a': 'i', 'nombre': 'CuentaDTO cuenta', 'reply': True},
          {'de': 'i', 'a': 'usr', 'nombre': 'CuentaDTO cuenta', 'reply': True}]
    M.generar_secuencia(doc, dg['_id'], lls, ms)
    doc.save(backup=False)


def test_secuencia_de_diseno_no_se_revisa_con_las_reglas_de_oose(modelo):
    con_diseno(modelo)
    doc = M.Doc(modelo)
    assert not M.secuencia_de_analisis(doc, doc.diagram('metodo_buscarCuenta'))
    assert M.secuencia_de_analisis(doc, doc.diagram('cu_1_FB'))
    v = ok(tool('mdj_validar', archivo=modelo, metodos='control_entidad'))
    assert v['oose'] == {'problemas': [], 'avisos': []}, v['oose']
    assert ids_integros(modelo)


def test_las_reglas_de_oose_siguen_en_las_secuencias_de_analisis(modelo):
    con_diseno(modelo)
    ms = [dict(m) for m in MENSAJES] + [{'de': 'ctrl', 'a': 'usr', 'nombre': 'avisar()'}]
    r = ok(tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=ms))
    assert [p for p in r['oose']['problemas'] if 'Mensaje no valido' in p] == [
        'Mensaje no valido en OOSE: cu_1_FB #9 avisar() (control->actor)']


def test_control_en_etiqueta_solo_se_avisa_en_un_diagrama_de_robustez(modelo):
    con_diseno(modelo)
    v = ok(tool('mdj_validar', archivo=modelo, metodos='control_entidad'))
    assert not [a for a in v['oose']['avisos'] if 'notacion de iconos' in a]
    doc = M.Doc(modelo)
    control = doc.find('UMLClass:Control Autenticación')
    next(vista for dg, vista in doc.views_of(control['_id']) if dg['name'] == 'cu_1')['stereotypeDisplay'] = 'label'
    doc.save(backup=False)
    v = ok(tool('mdj_validar', archivo=modelo, metodos='control_entidad'))
    assert [a for a in v['oose']['avisos'] if 'notacion de iconos' in a] == [
        'cu_1: Control Autenticación no usa la notacion de iconos']


def test_revisar_secuencia_de_diseno_con_tipos_y_singleton(modelo):
    con_diseno(modelo)
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, secuencias=['metodo_buscarCuenta'], metodos='todos'))
    assert r['resumen']['problemas'] == 0, r
    assert not [h for s in r['secuencias'] for h in s['avisos'] if h['revision'] == 'argumentos']
    assert r['metodos_otras_clases']['CuentaBO'] == {'usados': ['consultarCuenta'], 'sin_usar': []}
    assert not [a for a in r['generales']['avisos'] if a.get('operacion') in ('CuentaBO', 'getInstance')]
    # un argumento que no es un tipo y no sale de ningun lado si se sigue avisando
    doc = M.Doc(modelo)
    it = M.interaction_of(doc, doc.diagram('metodo_buscarCuenta'))
    next(m for m in it['messages'] if m['name'] == 'consultarCuenta(Long)')['name'] = 'consultarCuenta(token)'
    doc.save(backup=False)
    r = ok(tool('mdj_secuencia_revisar', archivo=modelo, secuencias=['metodo_buscarCuenta'], metodos='todos'))
    assert [h['n'] for s in r['secuencias'] for h in s['avisos'] if h['revision'] == 'argumentos'] == [5]


def test_llamada_despues_de_un_auto_mensaje_no_se_baja(modelo):
    ms = [{'de': 'usr', 'a': 'ui', 'nombre': 'ingresar(usuario)'},
          {'de': 'ui', 'a': 'ctrl', 'nombre': 'autenticar(usuario)'},
          {'de': 'ctrl', 'a': 'ctrl', 'nombre': 'validar(usuario)'},
          {'de': 'ctrl', 'a': 'cta', 'nombre': 'buscarCuentaConSuHistorialCompleto(usuario, contraseña)'},
          {'de': 'cta', 'a': 'ctrl', 'nombre': 'cuenta', 'reply': True},
          {'de': 'ctrl', 'a': 'ui', 'nombre': 'mostrarResultado()'}]
    r = ok(tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=ms))
    assert not [a for a in r['ajustes'] if 'AVISO' in a]
    doc = M.Doc(modelo)
    ys = {doc.ids[v['model']['$ref']]['name']: float(v['points'].split(';')[0].split(':')[1])
          for v in doc.diagram('cu_1_FB')['ownedViews'] if v['_type'] == 'UMLSeqMessageView'}
    assert ys['buscarCuentaConSuHistorialCompleto(usuario, contraseña)'] - ys['validar(usuario)'] < 80, ys
    assert ids_integros(modelo)
