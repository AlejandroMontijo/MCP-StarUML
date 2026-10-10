# Correcciones de staruml_render: la salida PNG no pisa otros archivos (nunca el .mdj), ver_visual no toma un SVG de
# otro modelo y vuelve a exportar si cambia el contenido, la exportacion a PDF funciona o falla con claridad, los
# nombres que el selector del CLI no acepta se exportan sin cambiar el dibujo, una region fuera del SVG es error y
# svg_revisar ve las lineas (punteadas o de color) que cruzan cajas en cualquier tipo de diagrama.
import hashlib
import json
import os
import shutil
import stat
import struct
import sys
import tempfile
import zlib

import pytest

import staruml_render as R
from apoyo import M, ok, tool

# CLI de prueba mas parecido al real: entiende @Tipo y @Tipo[campo=valor] (y rechaza, como el real, valores con '.',
# '@', '[', ']', '=' o '::'), las plantillas <%=element.name%> y la del _id que usa staruml_render, el subcomando pdf
# (que, como el real, deja un PDF con una pagina en blanco si no selecciona nada) y solo los formatos png, jpeg y svg
# en image. FALSO_LOG guarda cada llamada; FALSO_NADA no exporta nada; FALSO_ROMPER deja vacio el archivo de ese
# diagrama y deja de exportar los que siguen (como cuando el CLI truena a la mitad); FALSO_CORTAR deja el SVG de ese
# diagrama sin terminar; FALSO_CALLADO no imprime el aviso de exito del PDF (otras versiones del CLI).
CLI_FIEL = r'''
import json, os, re, sys


def diagramas(o, res):
    if isinstance(o, dict):
        if 'Diagram' in o.get('_type', ''):
            res.append(o)
        for v in o.values():
            diagramas(v, res)
    elif isinstance(o, list):
        for v in o:
            diagramas(v, res)
    return res


def id_archivo(i):
    return re.sub(r'[^A-Za-z0-9]', lambda m: '_%x_' % ord(m.group()), i)


def plantilla(patron, g):
    def evaluar(m):
        expr = m.group(1).strip()
        if expr == 'element.name':
            return g.get('name', '')
        if expr.startswith('element._id.replace('):
            return id_archivo(g['_id'])
        raise SystemExit('[Error] plantilla desconocida: ' + expr)
    return re.sub(r'<%=(.*?)%>', evaluar, patron)


def seleccionar(todos, selector):
    m = re.fullmatch(r'@(\w+)(?:\[(\w+)=(.*)\])?', selector, re.S)
    if not m or (m.group(3) is not None and re.search(r'[.@\[\]=]|::', m.group(3))):
        print("[Error] Error: [Selector] Value selector should be format of '[field=value]'")
        return []
    tipo, campo, valor = m.groups()
    return [g for g in todos if (tipo == 'Diagram' or (tipo == 'UMLDiagram' and g['_type'].startswith('UML'))
                                 or g['_type'] == tipo) and (campo is None or str(g.get(campo, '')) == valor.strip())]


def main(a):
    if os.environ.get('FALSO_LOG'):
        with open(os.environ['FALSO_LOG'], 'a', encoding='utf-8') as f:
            f.write(json.dumps(a) + '\n')
    cmd, mdj = a[0], a[1]
    opc = dict(zip(a[2::2], a[3::2]))
    with open(mdj, encoding='utf-8') as f:
        elegidos = seleccionar(diagramas(json.load(f), []), opc.get('-s', '@Diagram'))
    if os.environ.get('FALSO_NADA'):
        print('[Error] TypeError: Cannot read properties of undefined')
        return
    if cmd == 'pdf':
        paginas = ''.join('%d 0 obj << /Type /Page >> (%s) endobj\n' % (i + 1, g.get('name', ''))
                          for i, g in enumerate(elegidos)) or '1 0 obj << /Type /Page >> endobj\n'
        with open(opc['-o'], 'w', encoding='utf-8') as f:
            f.write('%PDF-1.3\n' + paginas + '%%EOF\n')
        if not os.environ.get('FALSO_CALLADO'):
            print('[StarUML] PDF document was exported as ' + opc['-o'])
        return
    formato = opc.get('-f', 'png')
    if formato not in ('png', 'jpeg', 'svg'):
        print('Invalid values: Argument: f, Given: "%s", Choices: "png", "jpeg", "svg"' % formato)
        return
    for n, g in enumerate(elegidos):
        salida = plantilla(opc['-o'], g)
        os.makedirs(os.path.dirname(salida), exist_ok=True)
        if g.get('name') == os.environ.get('FALSO_ROMPER'):
            open(salida, 'w').close()
            print('[Error] TypeError: Cannot read properties of undefined')
            return
        if formato == 'svg':
            nombre = g.get('name', '').replace('&', '&amp;').replace('<', '&lt;')
            texto = ('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" data-id="%s">'
                     '<text x="20" y="40" font-size="13px">%s</text></svg>' % (g['_id'], nombre))
            if g.get('name') == os.environ.get('FALSO_CORTAR'):
                texto = texto[:len(texto) // 2]
            with open(salida, 'w', encoding='utf-8') as f:
                f.write(texto)
        else:
            with open(salida, 'wb') as f:
                f.write((b'\x89PNG\r\n\x1a\n' if formato == 'png' else b'\xff\xd8\xff\xe0') + g['_id'].encode())
    print('[StarUML] Total %d diagrams were exported' % len(elegidos))


main(sys.argv[1:])
'''


@pytest.fixture
def cli_fiel(tmp_path, monkeypatch):
    if os.name == 'nt':
        pytest.skip('el CLI de prueba es un script de shell')
    script = tmp_path / 'cli_fiel.py'
    script.write_text(CLI_FIEL, encoding='utf-8')
    envoltorio = tmp_path / 'staruml_fiel'
    envoltorio.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    envoltorio.chmod(envoltorio.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv('STARUML_MCP_STARUML_BIN', str(envoltorio))
    log = tmp_path / 'llamadas.log'
    monkeypatch.setenv('FALSO_LOG', str(log))
    return log


@pytest.fixture
def cache_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path / 'tmp'))
    os.makedirs(tmp_path / 'tmp', exist_ok=True)
    return tmp_path / 'tmp' / 'staruml_mcp_renders'


@pytest.fixture
def staruml(monkeypatch):
    if not M.staruml_cli():
        pytest.skip('StarUML no esta instalado (o define STARUML_MCP_STARUML_BIN)')
    monkeypatch.setenv('STARUML_MCP_EXPORT_TIMEOUT', os.environ.get('STARUML_MCP_EXPORT_TIMEOUT', '300'))


def _llamadas(log):
    return log.read_text(encoding='utf-8').splitlines() if log.exists() else []


def _md5(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def _renombrar(path, viejo, nuevo):
    doc = M.Doc(path)
    dg = doc.diagram(viejo)
    dg['name'] = nuevo
    doc.save(backup=False)
    return dg['_id']


def _agregar_diagrama(path, nombre, tipo='UMLClassDiagram'):
    doc = M.Doc(path)
    model = doc.find('Model')
    dg = {'_type': tipo, '_id': doc.new_id(), '_parent': M.ref(model['_id']), 'name': nombre}
    model['ownedElements'].append(dg)
    doc.save(backup=False)
    return dg['_id']


def _png(w, h):
    filas = b''.join(b'\x00' + b'\xff' * (w * 3) for _ in range(h))
    trozo = lambda t, c: struct.pack('>I', len(c)) + t + c + struct.pack('>I', zlib.crc32(t + c))
    return b'\x89PNG\r\n\x1a\n' + trozo(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + \
        trozo(b'IDAT', zlib.compress(filas)) + trozo(b'IEND', b'')


def _svg(tmp_path, w=200, h=100, nombre='s.svg'):
    p = tmp_path / nombre
    p.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
                 f'<rect x="0" y="0" width="{w}" height="{h}" fill="#000"/></svg>')
    return str(p)


# ---------------------------------------------------------------------------
# Exportar (#34, #35)
# ---------------------------------------------------------------------------

NOMBRES_RAROS = ['Flujo alterno v1.2', 'rd FA=1', 'rd @x', 'Vista [v2] / final', 'x::y', ' espacio ', '.oculto',
                 'a/b: c']


@pytest.mark.parametrize('nombre', NOMBRES_RAROS)
def test_exportar_nombres_que_el_selector_no_acepta(modelo, tmp_path, cli_fiel, nombre):
    dg = _renombrar(modelo, 'cu_1_FB', nombre)
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'out'), diagrama=nombre))
    assert r['archivos'] == [str(tmp_path / 'out' / f'{R._nombre_archivo(nombre)}.svg')]
    texto = open(r['archivos'][0], encoding='utf-8').read()
    assert f'data-id="{dg}"' in texto
    # el diagrama se exporto con su nombre: el dibujo no cambia
    assert nombre.replace('&', '&amp;') in texto
    assert os.listdir(tmp_path / 'out') == [os.path.basename(r['archivos'][0])]


@pytest.mark.parametrize('nombre, archivo', [('con', 'con_'), ('Aux.v2', 'Aux_.v2'), ('NUL ', 'NUL_'), ('com1', 'com1_'),
                                             ('COM10', 'COM10'), ('consola', 'consola'), ('a/b: c', 'a_b_ c'),
                                             (' .oculto.', 'oculto'), ('', 'diagrama')])
def test_nombre_de_archivo_valido_en_cualquier_sistema(nombre, archivo):
    # en Windows CON, PRN, AUX, NUL, COM1-9 y LPT1-9 son dispositivos aunque lleven extension
    assert R._nombre_archivo(nombre) == archivo


def test_exportar_diagrama_con_nombre_reservado_de_windows(modelo, tmp_path, cli_fiel):
    dg = _renombrar(modelo, 'cu_1', 'Con')
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'out'), diagrama='Con'))
    assert r['archivos'] == [str(tmp_path / 'out' / 'Con_.svg')] and r['id'] == dg


def test_exportar_por_id_con_homonimos_de_nombre_raro(modelo, tmp_path, cli_fiel):
    _renombrar(modelo, 'cu_1', 'v1.2')
    dup = _agregar_diagrama(modelo, 'v1.2')
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'out'), diagrama=dup))
    assert f'data-id="{dup}"' in open(r['archivos'][0], encoding='utf-8').read() and r['id'] == dup


def test_exportar_todos_no_pisa_homonimos_ni_crea_subcarpetas(modelo, tmp_path, cli_fiel):
    dup = _agregar_diagrama(modelo, 'cu_1')
    _agregar_diagrama(modelo, 'a/b')
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'out')))
    assert r['exportados'] == 4 == len(r['archivos']), r
    ids = {open(a, encoding='utf-8').read().split('data-id="')[1].split('"')[0] for a in r['archivos']}
    assert len(ids) == 4 and dup in ids
    nombres = sorted(os.listdir(tmp_path / 'out'))
    assert 'a_b.svg' in nombres and 'cu_1_FB.svg' in nombres
    assert sum(n.startswith('cu_1__') for n in nombres) == 2, nombres
    assert all(os.path.isfile(tmp_path / 'out' / n) for n in nombres)


def test_exportar_sin_archivos_es_error(modelo, tmp_path, cli_fiel, monkeypatch):
    monkeypatch.setenv('FALSO_NADA', '1')
    for args in ({}, {'diagrama': 'cu_1'}, {'formato': 'pdf'}, {'diagrama': 'cu_1', 'formato': 'pdf'}):
        r = tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'out'), **args)
        assert 'error' in r and 'no genero' in r['error'], (args, r)
    assert not os.listdir(tmp_path / 'out')


def test_exportar_archivo_vacio_no_cuenta_como_exportado(modelo, tmp_path, cli_fiel, monkeypatch):
    monkeypatch.setenv('FALSO_ROMPER', 'cu_1')
    assert 'no genero' in tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'uno'), diagrama='cu_1')['error']
    assert not os.listdir(tmp_path / 'uno')
    # todos: el CLI de prueba recorre en el orden del archivo (cu_1, cu_1_FB, zz despues) y truena en cu_1_FB
    monkeypatch.setenv('FALSO_ROMPER', 'cu_1_FB')
    _agregar_diagrama(modelo, 'zz despues')
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'todos')))
    assert r['archivos'] == [str(tmp_path / 'todos' / 'cu_1.svg')] and r['exportados'] == 1
    assert [f.split(' (')[0] for f in r['sin_exportar']] == ['cu_1_FB', 'zz despues'], r
    assert '1 salieron vacios' in r['nota'] and 'No salieron 1' in r['nota'] and r['salida_cli']
    assert os.listdir(tmp_path / 'todos') == ['cu_1.svg']


def test_exportar_pdf_uno_y_todos(modelo, tmp_path, cli_fiel):
    _renombrar(modelo, 'cu_1_FB', 'Flujo v1.2')
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'pdf'), diagrama='Flujo v1.2', formato='pdf'))
    assert r['archivos'] == [str(tmp_path / 'pdf' / 'Flujo v1.2.pdf')] and r['exportados'] == 1
    data = open(r['archivos'][0], 'rb').read()
    assert data.startswith(b'%PDF') and b'(Flujo v1.2)' in data and b'(cu_1)' not in data
    assert json.loads(_llamadas(cli_fiel)[-1])[0] == 'pdf'
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'pdf'), formato='pdf'))
    assert r['archivos'] == [str(tmp_path / 'pdf' / 'modelo.pdf')] and r['exportados'] == 2


def test_exportar_svg_sin_terminar_no_cuenta_como_exportado(modelo, tmp_path, cli_fiel, monkeypatch):
    monkeypatch.setenv('FALSO_CORTAR', 'cu_1')
    r = tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'uno'), diagrama='cu_1')
    assert 'no genero' in r.get('error', ''), r
    assert not os.path.exists(tmp_path / 'uno' / 'cu_1.svg')
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'todos')))
    assert [os.path.basename(a) for a in r['archivos']] == ['cu_1_FB.svg']
    assert any(f.startswith('cu_1 (') for f in r['sin_exportar']) and 'incompletos' in r['nota'], r


def test_exportar_pdf_no_depende_del_aviso_del_cli(modelo, tmp_path, cli_fiel, monkeypatch):
    # lo que cuenta es que el PDF este completo, no el texto que imprima cada version del CLI
    monkeypatch.setenv('FALSO_CALLADO', '1')
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'pdf'), diagrama='cu_1', formato='pdf'))
    assert open(r['archivos'][0], 'rb').read().startswith(b'%PDF')


# ---------------------------------------------------------------------------
# ver_visual (#32 / #4)
# ---------------------------------------------------------------------------

def _sin_chrome(monkeypatch):
    """recortar falso: devuelve el SVG que le pasa ver_visual para revisar de donde salio."""
    vistos = []

    def recortar(svg, **k):
        vistos.append(open(svg, encoding='utf-8').read())
        return {'png': b'', 'salida': k.get('salida'), 'tamano_svg': [320, 200], 'region': [0, 0, 320, 200]}
    monkeypatch.setattr(R, 'recortar', recortar)
    return vistos


def test_ver_visual_no_usa_un_svg_de_otro_modelo_junto_al_mdj(modelo, tmp_path, cli_fiel, cache_temporal, monkeypatch):
    vistos = _sin_chrome(monkeypatch)
    carpeta = os.path.dirname(modelo)
    for p in (os.path.join(carpeta, 'cu_1.svg'), os.path.join(carpeta, 'renders', 'cu_1.svg')):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900" data-id="DE_OTRO_MODELO"/>')
    os.utime(modelo, (1, 1))  # el .mdj es mas viejo que esos SVG
    R.ver_visual(modelo, 'cu_1')
    dg = M.Doc(modelo).diagram('cu_1')['_id']
    assert f'data-id="{dg}"' in vistos[-1] and 'DE_OTRO_MODELO' not in vistos[-1]
    assert len(_llamadas(cli_fiel)) == 1


def test_ver_visual_vuelve_a_exportar_si_cambia_el_contenido(modelo, tmp_path, cli_fiel, cache_temporal, monkeypatch):
    vistos = _sin_chrome(monkeypatch)
    os.utime(modelo, (1000, 1000))
    R.ver_visual(modelo, 'cu_1')
    R.ver_visual(modelo, 'cu_1')
    assert len(_llamadas(cli_fiel)) == 1  # sin cambios: sale de la cache
    _renombrar(modelo, 'cu_1', 'cu_1 nuevo')
    os.utime(modelo, (1000, 1000))  # misma fecha, otro contenido
    R.ver_visual(modelo, 'cu_1 nuevo')
    assert len(_llamadas(cli_fiel)) == 2 and 'cu_1 nuevo' in vistos[-1]
    R.ver_visual(modelo, 'cu_1 nuevo', forzar=True)
    assert len(_llamadas(cli_fiel)) == 3


def test_ver_visual_mismo_contenido_en_otra_ruta_no_comparte_cache(modelo, tmp_path, cli_fiel, cache_temporal,
                                                                   monkeypatch):
    _sin_chrome(monkeypatch)
    otro = str(tmp_path / 'otra carpeta' / 'modelo.mdj')
    os.makedirs(os.path.dirname(otro))
    shutil.copy(modelo, otro)
    R.ver_visual(modelo, 'cu_1')
    R.ver_visual(otro, 'cu_1')
    assert len(os.listdir(cache_temporal)) == 2


def test_ver_visual_salida_que_no_es_png_no_toca_nada(modelo, tmp_path, cli_fiel, cache_temporal):
    antes = _md5(modelo)
    for salida in ('modelo.mdj', 'imagen.jpg', str(tmp_path)):
        r = tool('staruml_ver_visual', archivo=modelo, diagrama='cu_1', salida=salida)
        assert 'error' in r and 'salida' in r['error'], (salida, r)
    assert _md5(modelo) == antes
    assert not _llamadas(cli_fiel)  # se rechaza antes de exportar


# ---------------------------------------------------------------------------
# recortar: salida (#33) y region (#41)
# ---------------------------------------------------------------------------

def test_recortar_nunca_pisa_lo_que_no_es_png(modelo, tmp_path):
    svg = _svg(tmp_path)
    texto = tmp_path / 'notas.png'
    texto.write_text('no soy una imagen')
    vacio = tmp_path / 'vacio.png'
    vacio.write_bytes(b'')
    carpeta = tmp_path / 'carpeta.png'
    carpeta.mkdir()
    casos = [modelo, str(tmp_path / 'nuevo.txt'), str(texto), str(vacio), str(carpeta)]
    if hasattr(os, 'symlink'):
        enlace = tmp_path / 'enlace.png'
        try:
            os.symlink(modelo, enlace)
            casos.append(str(enlace))
        except OSError:
            pass
    antes = {c: (_md5(c) if os.path.isfile(c) else None) for c in casos}
    for c in casos:
        with pytest.raises(M.MdjError, match='salida'):
            R.recortar(svg, salida=c)
        assert (_md5(c) if os.path.isfile(c) else None) == antes[c], c
    assert not os.path.exists(tmp_path / 'nuevo.txt')
    assert open(modelo, encoding='utf-8').read().startswith('{')


def test_svg_recortar_por_protocolo_no_pisa_el_mdj(modelo, tmp_path):
    svg = _svg(tmp_path)
    shutil.copy(modelo, tmp_path / 'junto.mdj')
    antes = _md5(tmp_path / 'junto.mdj')
    r = tool('svg_recortar', svg=svg, ancho=50, alto=50, salida='junto.mdj', devolver_imagen=False)
    assert 'error' in r and '.png' in r['error']
    assert _md5(tmp_path / 'junto.mdj') == antes


def test_recortar_reemplaza_un_png_existente(tmp_path, chrome):
    svg = _svg(tmp_path, 300, 150)
    salida = tmp_path / 'sub' / 'recorte.PNG'
    salida.parent.mkdir()
    salida.write_bytes(_png(4, 4))
    r = R.recortar(svg, ancho=120, alto=60, salida=str(salida))
    assert r['salida'] == str(salida) and R.tamano_png(salida.read_bytes()) == (120, 60)
    assert sorted(os.listdir(salida.parent)) == ['recorte.PNG']  # sin temporales


@pytest.mark.parametrize('region', [dict(x=9000, y=9000, ancho=300, alto=200), dict(x=-500, ancho=300),
                                    dict(y=-900, alto=200), dict(x=200), dict(y=100), dict(x=7000)])
def test_recortar_region_fuera_del_svg_es_error(tmp_path, region):
    with pytest.raises(M.MdjError, match='fuera del SVG'):
        R.recortar(_svg(tmp_path), **region)


@pytest.mark.parametrize('region', [dict(ancho=0), dict(alto=-5), dict(x=float('nan')), dict(max_lado=-1)])
def test_recortar_valores_invalidos(tmp_path, region):
    with pytest.raises(M.MdjError):
        R.recortar(_svg(tmp_path), **region)


def test_recortar_region_que_se_sale_en_parte(tmp_path, chrome):
    r = R.recortar(_svg(tmp_path), x=-50, y=0, ancho=150, alto=40)
    assert R.tamano_png(r['png']) == (150, 40) and r['region'] == [-50, 0, 150, 40]


def test_recortar_max_lado_como_texto(tmp_path, chrome):
    # algunos clientes mandan los numeros como texto: se aceptan igual que x, y, ancho y alto
    r = R.recortar(_svg(tmp_path, 400, 200), max_lado='100')
    assert R.tamano_png(r['png']) == (100, 50)


def test_tamano_del_svg_sale_del_elemento_raiz(tmp_path):
    p = tmp_path / 'a.svg'
    p.write_text('<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" height="80" width="300">'
                 '<rect width="5000" height="4000"/></svg>')
    assert R._svg_size(str(p)) == (300, 80)
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480"><rect width="10" height="10"/></svg>')
    assert R._svg_size(str(p)) == (640, 480)


# ---------------------------------------------------------------------------
# svg_revisar: lineas que cruzan cajas en cualquier diagrama (#28)
# ---------------------------------------------------------------------------

def _linea(puntos, trazo='#000000', punteada=''):
    d = ' M ' + ' L '.join(f'{x} {y}' for x, y in puntos)
    return (f'<path fill="none" stroke="{trazo}" paint-order="fill stroke markers" d="{d}" '
            f'stroke-miterlimit="10" stroke-dasharray="{punteada}"/>')


def _caja_svg(v):
    x0, y0, x1, y1 = v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height']
    # el contorno de una figura es un path cerrado: no es una linea
    return (f'<path fill="#ffffff" stroke="none" d=" M {x0} {y0} L {x1} {y0} L {x1} {y1} L {x0} {y1} L {x0} {y0}"/>'
            f'<path fill="none" stroke="#000000" d=" M {x0} {y0} L {x1} {y0} L {x1} {y1} L {x0} {y1} L {x0} {y0}" '
            f'stroke-dasharray=""/>')


def _revisar(tmp_path, mdj, diagrama, cuerpo, nombre='r.svg'):
    p = tmp_path / nombre
    p.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="600"><g>{cuerpo}</g></svg>',
                 encoding='utf-8')
    return R.revisar_svg(str(p), mdj, diagrama)


def _tres_cajas(vacio, tipo, simbolo):
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo=tipo, nombre=f'Fila {tipo}'))['diagrama']
    vistas = {}
    for n, x in (('Origen', 40), ('En medio', 300), ('Destino', 560)):
        r = ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo=simbolo, nombre=f'{n} {tipo}', x=x, y=100,
                    ancho=140, alto=80))
        vistas[n] = r['vista']
    doc = M.Doc(vacio)
    return dg, {n: doc.ids[i] for n, i in vistas.items()}


@pytest.mark.parametrize('tipo, simbolo, trazo, punteada', [
    ('despliegue', 'Node', '#000000', ''),        # ruta de comunicacion entre nodos
    ('clases', 'Class', '#000000', '3'),          # dependencia (punteada)
    ('gcp', 'Product', '#4284F3', ''),            # ruta de Google Cloud (azul)
    ('estados', 'Simple State', '#000000', ''),   # transicion entre estados
])
def test_svg_revisar_linea_que_cruza_una_caja(vacio, tmp_path, tipo, simbolo, trazo, punteada):
    dg, v = _tres_cajas(vacio, tipo, simbolo)
    cajas = ''.join(_caja_svg(x) for x in v.values())
    r = _revisar(tmp_path, vacio, dg, cajas + _linea([(180, 140), (560, 140)], trazo, punteada))
    assert [p for p in r['problemas'] if p.startswith('LINEA CRUZA CAJA')] == \
        [f'LINEA CRUZA CAJA En medio {tipo} [180, 140]-[560, 140]'], r['problemas']
    # la linea que llega a la caja de en medio, o que la rodea, no la cruza
    r = _revisar(tmp_path, vacio, dg, cajas + _linea([(180, 140), (300, 140)], trazo, punteada)
                 + _linea([(110, 100), (110, 60), (630, 60), (630, 100)], trazo, punteada))
    assert not [p for p in r['problemas'] if 'CRUZA' in p], r['problemas']


@pytest.mark.parametrize('anidados', [True, False])
def test_svg_revisar_lineas_dentro_y_a_traves_de_un_contenedor(vacio, tmp_path, anidados):
    """Un contenedor (nodo, paquete, sistema) con cajas adentro: la linea que entra a una de ellas no cruza el
    contenedor, la que lo atraviesa de lado a lado si, y la que une dos cajas de adentro pasando por una tercera
    tambien. Igual si el contenedor tiene sus cajas en containedViews o si solo estan dibujadas adentro (como el
    sistema de un diagrama de casos de uso)."""
    dg = ok(tool('mdj_diagrama_crear', archivo=vacio, tipo='despliegue', nombre='Contenedor'))['diagrama']
    for n, x, y, w, h in (('Servidor', 300, 60, 440, 260), ('Tomcat', 320, 180, 100, 60), ('Cache', 460, 180, 100, 60),
                          ('Base', 620, 180, 100, 60), ('Navegador', 40, 180, 140, 80)):
        ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo='Node', nombre=n, x=x, y=y, ancho=w, alto=h))
    doc = M.Doc(vacio)
    v = {doc.name_of(x['model']['$ref']): x for x in doc.diagram(dg)['ownedViews'] if 'left' in x}
    serv = v['Servidor']
    serv.pop('containedViews', None)
    for n in ('Tomcat', 'Cache', 'Base'):
        v[n].pop('containerView', None)
        if anidados:
            v[n]['containerView'] = M.ref(serv['_id'])
            serv.setdefault('containedViews', []).append(M.ref(v[n]['_id']))
    doc.save(backup=False)
    cajas = ''.join(_caja_svg(x) for x in v.values())
    medio = lambda n: v[n]['top'] + v[n]['height'] // 2
    der = lambda n: v[n]['left'] + v[n]['width']
    cruces = lambda r: [p for p in r['problemas'] if 'CRUZA' in p]
    # de afuera hacia una caja de adentro: pasa el borde del contenedor, que es suyo
    r = _revisar(tmp_path, vacio, dg, cajas + _linea([(der('Navegador'), medio('Tomcat')),
                                                      (v['Tomcat']['left'], medio('Tomcat'))], '#000000', '3'))
    assert not cruces(r), r['problemas']
    # de una caja de adentro a otra, pasando por la de en medio: es un cruce aunque todo quede dentro del contenedor
    r = _revisar(tmp_path, vacio, dg, cajas + _linea([(der('Tomcat'), medio('Tomcat')),
                                                      (v['Base']['left'], medio('Tomcat'))]))
    assert [p.split(' [')[0] for p in cruces(r)] == ['LINEA CRUZA CAJA Cache'], r['problemas']
    # de afuera hacia afuera, atravesando el contenedor
    r = _revisar(tmp_path, vacio, dg, _linea([(180, 70), (900, 70)]))
    assert [p.split(' [')[0] for p in cruces(r)] == ['LINEA CRUZA CAJA Servidor'], r['problemas']


def test_svg_revisar_secuencia_mensajes_y_lifelines(modelo, tmp_path):
    doc = M.Doc(modelo)
    dg = doc.diagram('cu_1_FB')
    ll = [x for x in dg['ownedViews'] if x['_type'] == 'UMLSeqLifelineView']
    centro = lambda x: next(s for s in x['subViews'] if s['_type'] == 'UMLLinePartView')['left'] + 0.5
    lineas = ''.join(_linea([(centro(x), 106), (centro(x), 470)], punteada='3') for x in ll)  # lineas de vida
    marco = _linea([(8, 10), (1047, 10), (1047, 505), (8, 505), (8, 10)])  # contorno del marco
    # un mensaje del primero al cuarto pasa por las lineas de vida de en medio: no es un cruce
    r = _revisar(tmp_path, modelo, dg['_id'], marco + lineas + _linea([(centro(ll[0]), 300), (centro(ll[3]), 300)]))
    assert not [p for p in r['problemas'] if 'CRUZA' in p], r['problemas']
    # uno que pasa por el encabezado de otra lifeline si lo es
    r = _revisar(tmp_path, modelo, dg['_id'], lineas + _linea([(centro(ll[0]), 92), (centro(ll[3]), 92)]))
    cruces = [p for p in r['problemas'] if p.startswith('LINEA CRUZA CAJA')]
    assert len(cruces) == 2 and all(doc.name_of(x['model']['$ref']) in ' '.join(cruces) for x in ll[1:3]), cruces


def test_svg_revisar_lineas_con_arcos_y_relativas(modelo, tmp_path):
    # lineas de esquinas redondeadas (BPMN, ERD) y comandos relativos tambien se leen
    assert R._polilineas(' M 0 0 L 100 0 A 8 8 0 0 1 108 8 L 108 50') == [[(0, 0), (100, 0), (108, 8), (108, 50)]]
    assert R._polilineas('m 10 10 l 5 0 h 5 v 5') == [[(10, 10), (15, 10), (20, 10), (20, 15)]]
    assert R._polilineas('M 0 0 L 10 0 L 10 10 Z M 50 50 L 60 60') == [[(50, 50), (60, 60)]]
    assert R._polilineas('M 0 0 L 10 0 L 10 10 L 0 10 L 0 0') == []  # contorno sin Z
    curva = R._polilineas('M 0 0 C 0 10 10 10 10 0')[0]
    assert curva[0] == (0, 0) and curva[-1] == (10, 0) and len(curva) == 5


# ---------------------------------------------------------------------------
# Con el StarUML verdadero (se omiten si no esta instalado)
# ---------------------------------------------------------------------------

def test_staruml_exporta_nombres_raros_y_los_dibuja_igual(modelo, tmp_path, staruml):
    dg = M.Doc(modelo).diagram('cu_1_FB')['_id']
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'ref'), diagrama=dg))
    referencia = open(r['archivos'][0], encoding='utf-8').read()
    for nombre in ('Flujo alterno v1.2', 'rd FA=1', 'rd @x', 'Vista [v2] / final', 'x::y'):
        _renombrar(modelo, dg, nombre)
        r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'out'), diagrama=nombre))
        assert r['archivos'] == [str(tmp_path / 'out' / f'{R._nombre_archivo(nombre)}.svg')]
        # el diagrama se dibuja igual que con su nombre original (la marca para seleccionarlo no se ve)
        assert open(r['archivos'][0], encoding='utf-8').read() == referencia, nombre


def test_staruml_exporta_pdf(modelo, tmp_path, staruml):
    _renombrar(modelo, 'cu_1_FB', 'Flujo v1.2')
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'pdf uno'), diagrama='Flujo v1.2',
                formato='pdf'))
    data = open(r['archivos'][0], 'rb').read()
    assert data.startswith(b'%PDF') and r['archivos'][0].endswith('Flujo v1.2.pdf')
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'pdf todos'), formato='pdf'))
    assert r['exportados'] == len(M.Doc(modelo).diagrams()) and open(r['archivos'][0], 'rb').read(4) == b'%PDF'


def test_staruml_svg_revisar_ve_lineas_que_cruzan_cajas(vacio, tmp_path, staruml):
    casos = [('despliegue', 'Node', 'Communication Path'), ('clases', 'Class', 'Dependency'),
             ('estados', 'Simple State', 'Transition'), ('gcp', 'Product', 'Path')]
    dgs = []
    for tipo, caja, linea in casos:
        dg, _ = _tres_cajas(vacio, tipo, caja)
        ok(tool('mdj_dibujar', archivo=vacio, diagrama=dg, simbolo=linea, desde=f'Origen {tipo}',
                hasta=f'Destino {tipo}'))
        dgs.append((tipo, dg))
    r = ok(tool('staruml_exportar', archivo=vacio, carpeta=str(tmp_path / 'svg')))
    for tipo, dg in dgs:
        svg = str(tmp_path / 'svg' / f'Fila {tipo}.svg')
        rev = ok(tool('svg_revisar', svg=svg, archivo=vacio, diagrama=dg))
        assert any(p.startswith(f'LINEA CRUZA CAJA En medio {tipo}') for p in rev['problemas']), (tipo, rev)
    assert r['exportados'] >= len(casos)


def test_staruml_modelo_real_sin_falsos_cruces(real, tmp_path, staruml):
    """Los diagramas del caso de uso, revisados a mano, siguen sin observaciones con la deteccion ampliada."""
    doc = M.Doc(real)
    nombres = [d.get('name') for d in doc.diagrams()]
    revisar = [n for n in ('cu_1', 'cu_1_FB', 'cu_1_FA', 'cu_1_FA1', 'cu_1_FA2', 'Use Case View') if nombres.count(n) == 1]
    if not revisar:
        pytest.skip('el modelo real no tiene los diagramas del caso de uso')
    for n in revisar:
        svg = ok(tool('staruml_exportar', archivo=real, carpeta=str(tmp_path / 'svg'), diagrama=n))['archivos'][0]
        rev = ok(tool('svg_revisar', svg=svg, archivo=real, diagrama=n))
        assert rev['n_problemas'] == 0, (n, rev['problemas'])


def test_staruml_ver_visual_de_un_nombre_raro(modelo, tmp_path, staruml, chrome, cache_temporal):
    _renombrar(modelo, 'cu_1_FB', 'Flujo alterno v1.2')
    r = R.ver_visual(modelo, 'Flujo alterno v1.2', salida=str(tmp_path / 'flujo.png'), max_lado=400)
    assert R.tamano_png(open(tmp_path / 'flujo.png', 'rb').read())[0] <= 400 and r['id']
