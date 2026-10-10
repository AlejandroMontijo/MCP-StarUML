# Verificaciones que necesitan la aplicacion StarUML. Se omiten donde no esta instalada (p. ej. en CI).
#  - Auto-mensajes: StarUML abre y dibuja la secuencia generada con auto-mensajes.
#  - Exportacion real: todos los diagramas del modelo real salen del CLI verdadero y svg_revisar lee el SVG autentico.
#  - Estados y actividades: los diagramas hechos en StarUML (en pruebas/*.mdj) se leen completos con las reglas.
#  - Programa a diagrama: StarUML abre y dibuja el diagrama de clases generado desde un programa Java.
# Si existe la carpeta local pruebas/ (ignorada por git), los SVG, PNG e informes quedan en
# pruebas/verificacion_staruml/ para revisarlos a ojo.
import glob
import json
import os
import shutil

import pytest

import staruml_render as R
from apoyo import LIFELINES, PROGRAMA_JAVA, RAIZ, M, fuentes, ok, tool


def carpeta_revision():
    base = os.path.join(RAIZ, 'pruebas')
    if not os.path.isdir(base):
        return None
    destino = os.path.join(base, 'verificacion_staruml')
    os.makedirs(destino, exist_ok=True)
    return destino


def guardar_para_revision(*archivos, informe=None, nombre_informe=None):
    destino = carpeta_revision()
    if not destino:
        return
    for a in archivos:
        shutil.copy(a, destino)
    if informe is not None:
        with open(os.path.join(destino, nombre_informe), 'w', encoding='utf-8') as f:
            json.dump(informe, f, ensure_ascii=False, indent=1)


@pytest.fixture
def staruml(monkeypatch):
    cli = M.staruml_cli()
    if not cli:
        pytest.skip('StarUML no esta instalado (o define STARUML_MCP_STARUML_BIN)')
    monkeypatch.setenv('STARUML_MCP_EXPORT_TIMEOUT', os.environ.get('STARUML_MCP_EXPORT_TIMEOUT', '300'))
    return cli


def test_staruml_dibuja_los_auto_mensajes(modelo, tmp_path, staruml):
    ms = [{'de': 'usr', 'a': 'ui', 'nombre': 'ingresar(usuario)'},
          {'de': 'ui', 'a': 'ctrl', 'nombre': 'autenticar(usuario)'},
          {'de': 'ctrl', 'a': 'ctrl', 'nombre': 'validarFormatoDeUsuario(usuario)'},
          {'de': 'ctrl', 'a': 'cta', 'nombre': 'buscarCuenta(usuario)'},
          {'de': 'cta', 'a': 'ctrl', 'nombre': 'cuenta', 'reply': True},
          {'de': 'ctrl', 'a': 'ctrl', 'nombre': 'registrarIntento()'},
          {'de': 'ctrl', 'a': 'ui', 'nombre': 'mostrarResultado()'}]
    ok(tool('mdj_secuencia_generar', archivo=modelo, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=ms))
    svg = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'svg'), diagrama='cu_1_FB'))['archivos'][0]
    texto = open(svg, encoding='utf-8').read()
    for m in ms:
        assert m['nombre'].split('(')[0] in texto, f'StarUML no dibujo el mensaje {m["nombre"]}'
    rev = ok(tool('svg_revisar', svg=svg, archivo=modelo, diagrama='cu_1_FB'))
    archivos = [svg]
    if M.chrome_bin():
        png = str(tmp_path / 'cu_1_FB_auto_mensajes.png')
        R.recortar(svg, salida=png)
        archivos.append(png)
    destino = str(tmp_path / 'auto_mensajes.mdj')
    shutil.copy(modelo, destino)  # para abrirlo en StarUML y compararlo con la imagen
    guardar_para_revision(*archivos, destino, informe=rev, nombre_informe='auto_mensajes_svg_revisar.json')
    assert rev['activaciones'] >= 6, rev  # 7 mensajes; la activacion del reply va oculta
    assert rev['n_problemas'] == 0, rev['problemas']


def test_exportacion_real_del_modelo_y_svg_revisar(real, tmp_path, staruml):
    doc = M.Doc(real)
    diagramas = doc.diagrams()
    carpeta = str(tmp_path / 'todos')
    r = ok(tool('staruml_exportar', archivo=real, carpeta=carpeta, diagrama='todos'))
    assert r['exportados'], r
    nombres = [d.get('name') or '' for d in diagramas]
    unicos = [d for d in diagramas if nombres.count(d.get('name') or '') == 1]  # los homonimos se sobrescriben entre si
    faltan = [d.get('name') for d in unicos if not os.path.isfile(os.path.join(carpeta, f'{d.get("name") or ""}.svg'))]
    assert not faltan, f'StarUML no exporto: {faltan}'
    informe, revisados = {}, 0
    for d in unicos:
        n = d.get('name') or ''
        svg = os.path.join(carpeta, f'{n}.svg')
        rev = ok(tool('svg_revisar', svg=svg, archivo=real, diagrama=d['_id']))
        informe[n] = {'tipo': d['_type'], 'textos': rev['textos'], 'segmentos': rev['segmentos'],
                      'activaciones': rev['activaciones'], 'n_problemas': rev['n_problemas'], 'problemas': rev['problemas']}
        if d.get('ownedViews') and d['_type'] in ('UMLClassDiagram', 'UMLSequenceDiagram'):
            assert rev['textos'] > 0, f'svg_revisar no encontro textos en el SVG de {n}'
        if d['_type'] == 'UMLSequenceDiagram' and d.get('ownedViews'):
            assert rev['activaciones'] > 0, f'svg_revisar no encontro activaciones en {n}'
        revisados += 1
    guardar_para_revision(informe=informe, nombre_informe='exportacion_real.json')
    assert revisados == len(unicos)


def _modelos_con_estados_o_actividades():
    candidatos = sorted(glob.glob(os.path.join(RAIZ, 'pruebas', '*.mdj')))
    if os.environ.get('STARUML_MCP_MODELO_REAL'):
        candidatos.insert(0, os.environ['STARUML_MCP_MODELO_REAL'])
    out = []
    for p in candidatos:
        try:
            doc = M.Doc(p)
        except M.MdjError:
            continue
        if any(d['_type'] in ('UMLStatechartDiagram', 'UMLActivityDiagram') for d in doc.diagrams()):
            out.append(p)
    return out


def test_diagramas_de_estados_y_actividades_hechos_en_staruml():
    modelos = _modelos_con_estados_o_actividades()
    if not modelos:
        pytest.skip('dibuja un diagrama de estados o de actividades en StarUML y guarda el .mdj en pruebas/')
    informe = {}
    for p in modelos:
        doc = M.Doc(p)
        for dg in doc.diagrams():
            if dg['_type'] not in ('UMLStatechartDiagram', 'UMLActivityDiagram'):
                continue
            r = M.comportamiento(doc, dg['_id'])
            dueno = M._dueno_comportamiento(doc, dg)
            leidos = {e['id'] for e in r.get('estados', r.get('nodos', []))}
            aristas = r.get('transiciones', r.get('flujos', []))
            # cada transicion o flujo debe unir dos elementos reconocidos: si StarUML usa un tipo que no conocemos,
            # aqui aparece con su nombre
            for a in aristas:
                el = doc.ids[a['id']]
                for k in ('source', 'target'):
                    ref = (el.get(k) or {}).get('$ref')
                    obj = doc.ids.get(ref)
                    duenio_pin = doc.ids.get(doc.parent.get(ref)) if obj and obj['_type'] in M.PINES else None
                    assert ref in leidos or (duenio_pin and duenio_pin['_id'] in leidos), \
                        f'{os.path.basename(p)} / {dg.get("name")}: {k} de {el["_type"]} es {obj and obj["_type"]}, que no se reconoce'
            for e in r.get('estados', []):
                assert e['tipo'] in ('estado', 'final', 'initial', 'choice', 'junction', 'fork', 'join', 'shallowHistory',
                                     'deepHistory', 'entryPoint', 'exitPoint', 'terminate'), e
            vistos = [v.get('model', {}).get('$ref') for v in M._ids_y_refs_vistas(dg) if isinstance(v.get('model'), dict)]
            dibujados = {i for i in vistos if i in doc.ids and doc.ids[i]['_type'] not in ('UMLTransition', 'UMLControlFlow', 'UMLObjectFlow')
                         and doc.ids[i]['_type'].startswith('UML') and not doc.ids[i]['_type'].endswith(('Diagram', 'Partition'))}
            sin_leer = sorted({doc.ids[i]['_type'] for i in dibujados - leidos if doc.ids[i] is not dueno
                               and doc.ids[i]['_type'] not in M.PINES + ('UMLRegion',)})
            assert not sin_leer, f'{os.path.basename(p)} / {dg.get("name")}: hay elementos dibujados que no se leen: {sin_leer}'
            informe[f'{os.path.basename(p)} / {dg.get("name")}'] = r
    reglas = {os.path.basename(p): M.reglas_comportamiento(M.Doc(p)) for p in modelos}
    guardar_para_revision(informe={'lectura': informe, 'reglas': reglas}, nombre_informe='estados_y_actividades.json')


def test_staruml_dibuja_el_diagrama_de_un_programa(tmp_path, staruml):
    codigo = fuentes(str(tmp_path / 'tienda'), PROGRAMA_JAVA)
    mdj = str(tmp_path / 'programa_tienda.mdj')
    ok(tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=codigo))
    svg = ok(tool('staruml_exportar', archivo=mdj, carpeta=str(tmp_path / 'svg'), diagrama='Diagrama de clases'))['archivos'][0]
    texto = open(svg, encoding='utf-8').read()
    for esperado in ('Persona', 'Cliente', 'Pedido', 'LineaPedido', 'EstadoPedido', 'NUEVO', 'Notificable',
                     'RepositorioPedidos', 'calcularTotal', 'pedidos'):
        assert esperado in texto, f'StarUML no dibujo "{esperado}"'
    rev = ok(tool('svg_revisar', svg=svg, archivo=mdj, diagrama='Diagrama de clases'))
    archivos = [svg, mdj]
    if M.chrome_bin():
        png = str(tmp_path / 'programa_tienda.png')
        R.recortar(svg, salida=png)
        archivos.append(png)
    guardar_para_revision(*archivos, informe=rev, nombre_informe='programa_svg_revisar.json')
    assert not [p for p in rev['problemas'] if p.startswith('LINEA CRUZA CAJA')], rev['problemas']


def test_staruml_abre_y_dibuja_todos_los_tipos_de_diagrama(vacio, tmp_path, staruml):
    """Un archivo con los 28 tipos de diagrama y cada simbolo de cada paleta, hecho con las plantillas: el StarUML
    verdadero lo abre y exporta cada diagrama, con los nombres de los simbolos en el SVG."""
    import staruml_uml as U
    from apoyo import poblar_paleta
    doc = M.Doc(vacio)
    for tipo in sorted(U.plantillas()['diagramas']):
        dg, _ = U.crear_diagrama(doc, tipo, 'D_' + tipo)
        _, fallas = poblar_paleta(doc, dg)
        assert not fallas, (tipo, fallas)
    doc.save(backup=False)
    r = ok(tool('staruml_exportar', archivo=vacio, carpeta=str(tmp_path / 'svg')))
    nombres = {os.path.splitext(os.path.basename(a))[0] for a in r['archivos']}
    faltan = sorted(f'D_{t}' for t in U.plantillas()['diagramas'] if f'D_{t}' not in nombres)
    assert not faltan, f'StarUML no exporto {faltan}'
    for a in r['archivos']:
        if os.path.basename(a).startswith('D_'):
            texto = open(a, encoding='utf-8').read()
            assert '<svg' in texto and len(texto) > 500, a
    guardar_para_revision(vacio, *[a for a in r['archivos'] if os.path.basename(a).startswith('D_')])


def test_staruml_dibuja_un_despliegue_generado(vacio, tmp_path, staruml):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='despliegue', nombre='Arquitectura'))['diagrama']
    ok(tool('mdj_diagrama_generar', archivo=vacio, diagrama=dg, elementos=[
        {'simbolo': 'Node', 'nombre': 'Servidor web'},
        {'simbolo': 'Node', 'nombre': 'Tomcat', 'dentro': 'Servidor web'},
        {'simbolo': 'Artifact', 'nombre': 'tienda.war', 'dentro': 'Tomcat'},
        {'simbolo': 'Node', 'nombre': 'Servidor BD'},
        {'simbolo': 'Node', 'nombre': 'Navegador'}],
        relaciones=[{'simbolo': 'Communication Path', 'desde': 'Navegador', 'hasta': 'Servidor web'},
                    {'simbolo': 'Communication Path', 'desde': 'Servidor web', 'hasta': 'Servidor BD'}]))
    svg = ok(tool('staruml_exportar', archivo=vacio, carpeta=str(tmp_path / 'svg'), diagrama='Arquitectura'))['archivos'][0]
    texto = open(svg, encoding='utf-8').read()
    for n in ('Servidor web', 'Tomcat', 'tienda.war', 'Servidor BD', 'Navegador'):
        assert n in texto, f'StarUML no dibujo {n}'
    rev = ok(tool('svg_revisar', archivo=vacio, svg=svg, diagrama='Arquitectura'))
    assert not [p for p in rev['problemas'] if p.startswith('LINEA CRUZA CAJA')], rev['problemas']
    guardar_para_revision(svg, informe=rev, nombre_informe='despliegue_svg_revisar.json')


# observaciones de svg_revisar que quedan en la galeria (etiquetas de lineas que StarUML pone sobre nombres de
# contenedores o activaciones); la prueba evita que el acomodo empeore
MAX_OBSERVACIONES_GALERIA = 13


def test_staruml_dibuja_la_galeria(tmp_path, staruml):
    """Un diagrama de cada tipo con todos los simbolos de su paleta: StarUML exporta los 28 y svg_revisar no
    encuentra mas observaciones que las conocidas."""
    import galeria as G
    from apoyo import guardar_json, proyecto_vacio
    archivo = guardar_json(proyecto_vacio('Galeria'), str(tmp_path / 'galeria.mdj'))
    G.construir(lambda _h, **a: ok(tool(_h, **a)), archivo)
    r = ok(tool('staruml_exportar', archivo=archivo, carpeta=str(tmp_path / 'svg')))
    nombres = {os.path.splitext(os.path.basename(a))[0]: a for a in r['archivos']}
    faltan = [n for n in [g['nombre'] for g in G.GALERIA] + [G.ROBUSTEZ['nombre']] if n not in nombres]
    assert not faltan, f'StarUML no exporto {faltan}'
    informe, total = {}, 0
    todos = [g['nombre'] for g in G.GALERIA] + [G.ROBUSTEZ['nombre']]
    for n in todos:
        rev = ok(tool('svg_revisar', archivo=archivo, svg=nombres[n], diagrama=n))
        informe[n] = rev['problemas']
        total += rev['n_problemas']
    guardar_para_revision(archivo, *[nombres[n] for n in todos], informe=informe,
                          nombre_informe='galeria_svg_revisar.json')
    assert total <= MAX_OBSERVACIONES_GALERIA, informe
