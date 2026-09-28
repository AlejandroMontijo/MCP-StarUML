# Exportar diagramas con el CLI de StarUML, revisar el SVG y recortar zonas a PNG.
import base64
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from urllib.parse import quote

from staruml_mdj import Doc, MdjError, staruml_cli, chrome_bin

# ---------------------------------------------------------------------------
# Exportar
# ---------------------------------------------------------------------------

def exportar(mdj, carpeta, diagrama=None, formato='svg', timeout=150):
    cli = staruml_cli()
    if not cli:
        raise MdjError('No encontre StarUML.app en ~/Applications ni en /Applications')
    if formato not in ('svg', 'png', 'jpeg', 'pdf'):
        raise MdjError('formato debe ser svg, png, jpeg o pdf')
    mdj = os.path.abspath(os.path.expanduser(mdj))
    carpeta = os.path.abspath(os.path.expanduser(carpeta))
    os.makedirs(carpeta, exist_ok=True)
    if diagrama in (None, '', 'todos'):
        selector = '@UMLDiagram'
    else:
        doc = Doc(mdj)
        dg = doc.diagram(diagrama)
        selector = f'@{dg["_type"]}[name={dg["name"]}]'
    antes = {f: os.path.getmtime(f) for f in glob.glob(os.path.join(carpeta, f'*.{formato}'))}
    cmd = ['perl', '-e', f'alarm {int(timeout)}; exec @ARGV', cli, 'image', mdj, '-f', formato, '-s', selector,
           '-o', os.path.join(carpeta, f'<%=element.name%>.{formato}')]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
    except subprocess.TimeoutExpired:
        raise MdjError('La exportacion no termino a tiempo')
    salida = (r.stdout or '') + (r.stderr or '')
    total = re.search(r'Total (\d+) diagrams were exported', salida)
    archivos = sorted(f for f in glob.glob(os.path.join(carpeta, f'*.{formato}')) if os.path.getmtime(f) != antes.get(f))
    return {'exportados': int(total.group(1)) if total else None, 'archivos': archivos, 'selector': selector,
            'nota': 'Diagramas con el mismo nombre se sobrescriben entre si.' if selector == '@UMLDiagram' else '',
            'salida_cli': salida.strip()[-600:] if not total else ''}


# ---------------------------------------------------------------------------
# Revisar SVG
# ---------------------------------------------------------------------------

_R = dict(zip(' !"#$%&\'()*+,-./', [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278]))
_R.update({c: 556 for c in '0123456789'})
_R.update({':': 278, ';': 278, '<': 584, '=': 584, '>': 584, '?': 556, '@': 1015, '_': 556, '[': 278, ']': 278, '«': 556, '»': 556})
_R.update(dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', [667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611])))
_R.update(dict(zip('abcdefghijklmnopqrstuvwxyz', [556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500])))
_B = dict(_R)
_B.update(dict(zip('abcdefghijklmnopqrstuvwxyz', [556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500])))
_B.update(dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', [722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611])))
_BASE = str.maketrans('áéíóúñÁÉÍÓÚÑ', 'aeiounAEIOUN')


def _ancho(t, px, bold):
    tab = _B if bold else _R
    return sum(tab.get(c, 556) for c in t.translate(_BASE)) * px / 1000


def _cruza(p, q, r):
    x0, y0 = p; x1, y1 = q; t0, t1 = 0.0, 1.0
    for pp, qq in ((-(x1 - x0), x0 - r[0]), (x1 - x0, r[2] - x0), (-(y1 - y0), y0 - r[1]), (y1 - y0, r[3] - y0)):
        if pp == 0:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    return t0 < t1 - 1e-9


def revisar_svg(svg, mdj, diagrama, max_items=80):
    """Lineas que cruzan notas o cajas, lineas sobre etiquetas, etiquetas encimadas,
    texto que se sale de las notas y etiquetas sobre activaciones (secuencias)."""
    s = open(os.path.expanduser(svg), encoding='utf-8').read()
    doc = Doc(mdj)
    dg = doc.diagram(diagrama)
    textos, off = [], None
    for m in re.finditer(r'<text([^>]*)>([^<]*)</text>', s):
        a, t = m.group(1), m.group(2)
        if not t.strip():
            continue
        t = t.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
        g = lambda k: re.search(r'\s' + k + r'="([^"]*)"', a).group(1)
        x, y = float(g('x')), float(g('y'))
        px = float(g('font-size').replace('px', ''))
        bold = 'bold' in g('font-weight')
        tr = re.search(r'matrix\(1 0 0 1 (-?[\d.]+) (-?[\d.]+)\)', a)
        if tr:
            off = (float(tr.group(1)), float(tr.group(2)))
        w = _ancho(t, px, bold); anc = g('text-anchor')
        x0 = x - w / 2 if anc == 'middle' else (x - w if anc == 'end' else x)
        textos.append((t, x0, y - px / 2 + 1, x0 + w, y + px / 2 - 1))
    dx, dy = off if off else (0, 0)
    segs = []
    for m in re.finditer(r'<path([^>]*)/?>', s):
        a = m.group(1)
        if 'stroke="#000000"' not in a:
            continue
        da = re.search(r'stroke-dasharray="([^"]*)"', a)
        if da and da.group(1).strip():
            continue
        dd = re.search(r' d="([^"]*)"', a)
        if not dd or 'C' in dd.group(1) or 'Z' in dd.group(1):
            continue
        nums = re.findall(r'([ML])\s*(-?[\d.]+)\s+(-?[\d.]+)', dd.group(1))
        pts = [(float(x) - dx, float(y) - dy) for _, x, y in nums]
        for p, q in zip(pts, pts[1:]):
            if abs(p[0] - q[0]) + abs(p[1] - q[1]) > 0.5:
                segs.append((p, q))
    cajas, notas = [], []
    for v in dg.get('ownedViews', []):
        if v['_type'] in ('UMLClassView', 'UMLActorView', 'UMLNoteView') and v.get('visible', True) is not False:
            r = (v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height'])
            if v['_type'] == 'UMLNoteView':
                notas.append((v.get('text', '')[:40], r))
            else:
                cajas.append((doc.name_of(v['model']['$ref']), r))
    dentro = lambda p, r, m=0: r[0] - m <= p[0] <= r[2] + m and r[1] - m <= p[1] <= r[3] + m
    enc = lambda r, m: (r[0] + m, r[1] + m, r[2] - m, r[3] - m)
    propios = lambda p, q: any(dentro(p, r, 2) and dentro(q, r, 2) for _, r in cajas + notas)
    lineas = [(p, q) for p, q in segs if not propios(p, q)]
    prob = []
    rd = lambda p: [round(c) for c in p]
    for p, q in lineas:
        for n, r in notas:
            if _cruza(p, q, enc(r, -3)):
                prob.append(f'LINEA CRUZA NOTA "{n}" {rd(p)}-{rd(q)}')
        for n, r in cajas:
            if _cruza(p, q, enc(r, 4)):
                prob.append(f'LINEA CRUZA CAJA {n} {rd(p)}-{rd(q)}')
        for t in textos:
            if _cruza(p, q, enc((t[1], t[2], t[3], t[4]), 1)):
                prob.append(f'LINEA SOBRE TEXTO "{t[0][:50]}" {rd(p)}-{rd(q)}')
    for i, a in enumerate(textos):
        for b in textos[i + 1:]:
            if a[1] < b[3] - 1 and b[1] < a[3] - 1 and a[2] < b[4] - 1 and b[2] < a[4] - 1:
                prob.append(f'TEXTOS ENCIMADOS "{a[0][:40]}" | "{b[0][:40]}"')
    for n, r in notas:
        for t in textos:
            c = ((t[1] + t[3]) / 2, (t[2] + t[4]) / 2)
            if dentro(c, r) and (not dentro((t[1], t[2]), r, 1) or not dentro((t[3], t[4]), r, 1)):
                prob.append(f'TEXTO SE SALE DE LA NOTA "{n}": "{t[0][:40]}"')
    acts = []
    for m in re.finditer(r'<rect([^>]*)>', s):
        a = m.group(1)
        try:
            g = lambda k: float(re.search(r'\s' + k + r'="([^"]*)"', a).group(1))
            if abs(g('width') - 14) > 0.01 or g('height') < 18:
                continue
            tr = re.search(r'matrix\(1 0 0 1 (-?[\d.]+) (-?[\d.]+)\)', a)
            rx, ry = (float(tr.group(1)), float(tr.group(2))) if tr else (0, 0)
            x, y = g('x') + rx - dx, g('y') + ry - dy
            acts.append((x, y, x + 14, y + g('height')))
        except Exception:
            continue
    for t in textos:
        for r in acts:
            if t[1] < r[2] and r[0] < t[3] and t[2] < r[3] and r[1] < t[4]:
                prob.append(f'ETIQUETA SOBRE ACTIVACION "{t[0][:50]}" {rd(r[:2])}')
    return {'diagrama': dg.get('name'), 'segmentos': len(lineas), 'textos': len(textos), 'activaciones': len(acts),
            'n_problemas': len(prob), 'problemas': prob[:max_items],
            'desfase_svg': {'x': dx, 'y': dy}}


# ---------------------------------------------------------------------------
# Recortar SVG a PNG (Chrome headless)
# ---------------------------------------------------------------------------

def _svg_size(svg):
    with open(svg, encoding='utf-8') as f:
        head = f.read(600)
    m = re.search(r'width="([\d.]+)" height="([\d.]+)"', head)
    return (int(float(m.group(1))), int(float(m.group(2)))) if m else (None, None)


def recortar(svg, x=0, y=0, ancho=None, alto=None, salida=None, max_lado=None, timeout=30):
    chrome = chrome_bin()
    if not chrome:
        raise MdjError('No encontre Google Chrome')
    svg = os.path.abspath(os.path.expanduser(svg))
    W, H = _svg_size(svg)
    ancho = int(ancho or (W - x if W else 1200)); alto = int(alto or (H - y if H else 800))
    tmp = tempfile.mkdtemp(prefix='staruml_mcp_')
    prof = os.path.join(tmp, 'perfil_' + uuid.uuid4().hex[:8])
    html = os.path.join(tmp, 'r.html')
    png = os.path.join(tmp, 'out.png')
    url = 'file://' + quote(svg)
    with open(html, 'w') as f:
        f.write(f"<html><body style='margin:0;overflow:hidden;background:#fff'>"
                f"<img src='{url}' style='position:absolute;left:-{int(x)}px;top:-{int(y)}px'></body></html>")
    p = subprocess.Popen([chrome, '--headless=new', '--disable-gpu', f'--user-data-dir={prof}', f'--screenshot={png}',
                          f'--window-size={ancho},{alto}', '--hide-scrollbars', 'file://' + html],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    try:
        while time.time() - t0 < timeout:
            if os.path.exists(png) and os.path.getsize(png) > 0:
                time.sleep(0.4); break
            time.sleep(0.3)
    finally:
        p.terminate()
        try:
            p.wait(5)
        except Exception:
            p.kill()
        subprocess.run(['pkill', '-f', prof], capture_output=True)
    if not os.path.exists(png) or os.path.getsize(png) == 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise MdjError('Chrome no genero la imagen')
    if max_lado:
        subprocess.run(['sips', '-Z', str(int(max_lado)), png], capture_output=True)
    destino = None
    if salida:
        destino = os.path.abspath(os.path.expanduser(salida))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        shutil.copy2(png, destino)
    with open(png, 'rb') as f:
        data = f.read()
    shutil.rmtree(tmp, ignore_errors=True)
    return {'png': data, 'salida': destino, 'region': [int(x), int(y), ancho, alto], 'tamano_svg': [W, H]}
