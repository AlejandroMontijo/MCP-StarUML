# Exportacion (con un CLI de StarUML de prueba), cache de ver_visual, recorte con Chrome y revision de SVG.
import os
import tempfile
import time

import pytest

import staruml_render as R
from apoyo import M, S, ok, tool


@pytest.fixture
def cache_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path / 'tmp'))
    os.makedirs(tmp_path / 'tmp', exist_ok=True)
    return tmp_path / 'tmp' / 'staruml_mcp_renders'


def _duplicar_diagrama(path):
    doc = M.Doc(path)
    model = doc.find('Model')
    dup = {'_type': 'UMLClassDiagram', '_id': doc.new_id(), '_parent': M.ref(model['_id']), 'name': 'cu_1'}
    model['ownedElements'].append(dup)
    doc.save(backup=False)
    return dup['_id']


def test_exportar_un_diagrama_por_id_aunque_haya_homonimos(modelo, tmp_path, staruml_falso):
    dup = _duplicar_diagrama(modelo)
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'out'), diagrama=dup))
    assert r['archivos'] == [str(tmp_path / 'out' / 'cu_1.svg')]
    assert f'data-id="{dup}"' in open(r['archivos'][0]).read()


def test_exportar_nombre_con_corchetes_y_barras(modelo, tmp_path, staruml_falso):
    doc = M.Doc(modelo)
    doc.diagram('cu_1')['name'] = 'Vista [v2] / final'
    doc.save(backup=False)
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'out'), diagrama='Vista [v2] / final'))
    assert os.path.basename(r['archivos'][0]) == 'Vista _v2_ _ final.svg' and 'corchetes' in r['nota']


def test_exportar_todos(modelo, tmp_path, staruml_falso):
    r = ok(tool('staruml_exportar', archivo=modelo, carpeta='renders'))  # carpeta relativa: junto al .mdj
    assert r['exportados'] == 2 and all(os.path.dirname(f) == os.path.join(os.path.dirname(modelo), 'renders') for f in r['archivos'])


def test_exportar_con_limite_de_tiempo(modelo, tmp_path, staruml_falso, monkeypatch):
    monkeypatch.setenv('STARUML_FALSO_DORMIR', '30')
    monkeypatch.setenv('STARUML_MCP_EXPORT_TIMEOUT', '1')
    t0 = time.time()
    assert 'no termino en 1 s' in tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path / 'o'), diagrama='cu_1')['error']
    assert time.time() - t0 < 10


def test_sin_staruml_error_claro(modelo, tmp_path, monkeypatch):
    monkeypatch.setenv('STARUML_MCP_STARUML_BIN', str(tmp_path / 'no_existe'))
    assert 'No encontre StarUML' in tool('staruml_exportar', archivo=modelo, carpeta=str(tmp_path))['error']


def test_ver_visual_cache_por_proyecto_y_diagrama(modelo, tmp_path, staruml_falso, chrome, cache_temporal):
    otro = str(tmp_path / 'otro_proyecto.mdj')
    import shutil
    shutil.copy(modelo, otro)
    dup = _duplicar_diagrama(otro)
    r1 = R.ver_visual(modelo, 'cu_1', max_lado=300)
    r2 = R.ver_visual(otro, dup, max_lado=300)  # mismo nombre de diagrama, otro proyecto y otro id
    carpetas = sorted(os.listdir(cache_temporal))
    assert len(carpetas) == 2
    svgs = [open(os.path.join(cache_temporal, c, 'diagrama.svg')).read() for c in carpetas]
    assert any(f'data-id="{dup}"' in s for s in svgs)
    assert R.tamano_png(r1['png'])[0] <= 300 and R.tamano_png(r2['png'])[0] <= 300


def test_ver_visual_sin_svg_generado_no_toma_otro(modelo, tmp_path, cache_temporal, monkeypatch, chrome):
    os.makedirs(cache_temporal, exist_ok=True)
    (cache_temporal / 'otro_diagrama.svg').write_text('<svg/>')
    monkeypatch.setattr(R, 'exportar', lambda *a, **k: {'archivos': []})
    with pytest.raises(Exception):
        R.ver_visual(modelo, 'cu_1', forzar=True)


def test_recortar_con_chrome_tamano_exacto(tmp_path, chrome):
    svg = tmp_path / 'negro.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="600">'
                   '<rect x="0" y="0" width="1200" height="600" fill="#000"/></svg>')
    for max_lado, esperado in ((None, (1200, 600)), (600, (600, 300)), (240, (240, 120))):
        r = R.recortar(str(svg), max_lado=max_lado, salida=str(tmp_path / 'out' / f'{max_lado}.png'))
        assert R.tamano_png(r['png']) == esperado
        assert os.path.exists(r['salida'])
    r = R.recortar(str(svg), x=100, y=50, ancho=300, alto=200)
    assert R.tamano_png(r['png']) == (300, 200)


def test_svg_recortar_por_protocolo_devuelve_imagen(tmp_path, chrome):
    svg = tmp_path / 's.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><text x="10" y="50">Hola</text></svg>')
    r = S.llamar_herramienta({'name': 'svg_recortar', 'arguments': {'svg': str(svg), 'max_lado': 100}})
    assert not r['isError'] and r['content'][1]['type'] == 'image' and r['content'][1]['mimeType'] == 'image/png'


def test_png_primeras_filas_conserva_la_imagen():
    import struct
    import zlib
    w, h = 4, 6
    filas = b''.join(b'\x00' + bytes([y * 10] * (w * 3)) for y in range(h))
    trozo = lambda t, c: struct.pack('>I', len(c)) + t + c + struct.pack('>I', zlib.crc32(t + c))
    png = b'\x89PNG\r\n\x1a\n' + trozo(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + \
        trozo(b'IDAT', zlib.compress(filas)) + trozo(b'IEND', b'')
    corto = R._png_primeras_filas(png, 3)
    assert R.tamano_png(corto) == (4, 3)
    idat = corto[corto.index(b'IDAT') + 4:]
    assert zlib.decompress(idat[:struct.unpack('>I', corto[corto.index(b'IDAT') - 4:corto.index(b'IDAT')])[0]]) == filas[:3 * (w * 3 + 1)]


def test_svg_revisar_tolera_atributos_faltantes(modelo, tmp_path):
    svg = tmp_path / 's.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200">'
                   '<text x="20" y="40" font-size="13px">Sin anchor &amp;lt; ok</text>'
                   '<text x="22" y="41">Encima</text>'
                   '<path d="M 0 40 L 300 40" stroke="#000000"/></svg>')
    r = ok(tool('svg_revisar', svg=str(svg), archivo=modelo, diagrama='cu_1'))
    assert r['textos'] == 2 and any('TEXTOS ENCIMADOS' in p for p in r['problemas'])
    assert any('LINEA SOBRE TEXTO "Sin anchor &lt; ok"' in p for p in r['problemas'])
