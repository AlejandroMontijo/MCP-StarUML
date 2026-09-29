# Exportar diagramas con el CLI de StarUML, revisar el SVG y recortar zonas a PNG.
# Funciona en macOS, Linux y Windows: StarUML y Chrome se buscan en las rutas tipicas, en el PATH o en
# STARUML_MCP_STARUML_BIN / STARUML_MCP_CHROME_BIN; los limites de tiempo se ajustan con
# STARUML_MCP_EXPORT_TIMEOUT y STARUML_MCP_CHROME_TIMEOUT (segundos).
import glob
import hashlib
import json
import logging
import os
import pathlib
import re
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
import zlib
from html import unescape

from staruml_mdj import Doc, MdjError, staruml_cli, chrome_bin

log = logging.getLogger('staruml_mcp.render')


def _timeout(variable, defecto):
    try:
        return max(1, int(os.environ.get(variable, defecto)))
    except ValueError:
        return defecto


def _nombre_archivo(nombre):
    """Nombre de diagrama convertido en nombre de archivo valido en cualquier sistema."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', nombre or '').strip(' .') or 'diagrama'


# ---------------------------------------------------------------------------
# Exportar
# ---------------------------------------------------------------------------

def _correr(cmd, timeout):
    """Ejecuta el CLI con limite de tiempo. Si se pasa, mata tambien a sus procesos hijos (Electron)."""
    kw = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    log.debug('ejecutando (limite %s s): %s', timeout, ' '.join(cmd))
    inicio = time.monotonic()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace', **kw)
    try:
        out, err = p.communicate(timeout=timeout)
        log.debug('termino con codigo %s en %.1f s', p.returncode, time.monotonic() - inicio)
    except subprocess.TimeoutExpired:
        log.warning('se paso del limite de %s s; se mata el grupo de procesos: %s', timeout, ' '.join(cmd))
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(p.pid)], capture_output=True)
        else:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
        p.communicate()
        raise MdjError(f'La exportacion no termino en {timeout} s') from None
    return (out or '') + (err or '')


def exportar(mdj, carpeta, diagrama=None, formato='svg', timeout=None):
    cli = staruml_cli()
    if not cli:
        raise MdjError('No encontre StarUML: instalalo o define STARUML_MCP_STARUML_BIN con la ruta del ejecutable')
    if formato not in ('svg', 'png', 'jpeg', 'pdf'):
        raise MdjError('formato debe ser svg, png, jpeg o pdf')
    timeout = timeout or _timeout('STARUML_MCP_EXPORT_TIMEOUT', 150)
    mdj = os.path.abspath(os.path.expanduser(mdj))
    carpeta = os.path.abspath(os.path.expanduser(carpeta))
    os.makedirs(carpeta, exist_ok=True)
    if diagrama in (None, '', 'todos'):
        selector = '@UMLDiagram'
        antes = {f: os.path.getmtime(f) for f in glob.glob(os.path.join(carpeta, f'*.{formato}'))}
        salida = _correr([cli, 'image', mdj, '-f', formato, '-s', selector,
                          '-o', os.path.join(carpeta, f'<%=element.name%>.{formato}')], timeout)
        total = re.search(r'Total (\d+) diagrams were exported', salida)
        archivos = sorted(f for f in glob.glob(os.path.join(carpeta, f'*.{formato}')) if os.path.getmtime(f) != antes.get(f))
        return {'exportados': int(total.group(1)) if total else None, 'archivos': archivos, 'selector': selector,
                'nota': 'Diagramas con el mismo nombre se sobrescriben entre si.',
                'salida_cli': salida.strip()[-600:] if not total else ''}
    doc = Doc(mdj)
    dg = doc.diagram(diagrama)
    nombre = dg.get('name') or ''
    # el selector del CLI busca por nombre: si hay homonimos, o el nombre trae corchetes, se exporta desde una copia
    # temporal donde el diagrama pedido es el unico con ese nombre
    homonimos = [d for d in doc.diagrams() if d.get('name') == nombre and d is not dg]
    tmp = tempfile.mkdtemp(prefix='staruml_mcp_exp_')
    try:
        fuente, aviso = mdj, ''
        if homonimos or re.search(r'[\[\]]', nombre):
            for i, d in enumerate(homonimos):
                d['name'] = f'{nombre}__mcp_homonimo_{i}'
            if re.search(r'[\[\]]', nombre):
                dg['name'] = nombre = re.sub(r'[\[\]]', '_', nombre)
                aviso = 'El nombre del diagrama tiene corchetes, que el selector de StarUML no admite; se exporto como ' + nombre
            fuente = os.path.join(tmp, 'modelo.mdj')
            with open(fuente, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(doc.d, f, ensure_ascii=False, indent='\t')
        selector = f'@{dg["_type"]}[name={nombre}]'
        destino_tmp = os.path.join(tmp, 'out')
        os.makedirs(destino_tmp)
        salida = _correr([cli, 'image', fuente, '-f', formato, '-s', selector,
                          '-o', os.path.join(destino_tmp, f'<%=element.name%>.{formato}')], timeout)
        producidos = [f for f in glob.glob(os.path.join(destino_tmp, '**', f'*.{formato}'), recursive=True)]
        if len(producidos) != 1:
            raise MdjError(f'StarUML no genero la imagen del diagrama "{dg.get("name")}" '
                           f'({len(producidos)} archivos). Salida del CLI: {salida.strip()[-400:]}')
        destino = os.path.join(carpeta, f'{_nombre_archivo(dg.get("name"))}.{formato}')
        shutil.move(producidos[0], destino)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {'exportados': 1, 'archivos': [destino], 'selector': selector, 'nota': aviso, 'salida_cli': ''}


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


def _atributo(a, k, defecto=None):
    m = re.search(r'\s' + k + r'="([^"]*)"', a)
    return m.group(1) if m else defecto


def _numero(v, defecto=0.0):
    m = re.search(r'-?[\d.]+', v or '')
    try:
        return float(m.group(0)) if m else defecto
    except ValueError:
        return defecto


def revisar_svg(svg, mdj, diagrama, max_items=80):
    """Lineas que cruzan notas o cajas, lineas sobre etiquetas, etiquetas encimadas,
    texto que se sale de las notas y etiquetas sobre activaciones (secuencias)."""
    with open(os.path.expanduser(svg), encoding='utf-8') as f:
        s = f.read()
    doc = Doc(mdj)
    dg = doc.diagram(diagrama)
    textos, off = [], None
    for m in re.finditer(r'<text([^>]*)>([^<]*)</text>', s):
        a, t = m.group(1), unescape(m.group(2))
        if not t.strip():
            continue
        # atributos que falten toman el valor por defecto de SVG
        x, y = _numero(_atributo(a, 'x')), _numero(_atributo(a, 'y'))
        px = _numero(_atributo(a, 'font-size'), 13.0) or 13.0
        peso = _atributo(a, 'font-weight', 'normal')
        bold = 'bold' in peso or _numero(peso, 400) >= 600
        tr = re.search(r'matrix\(1 0 0 1 (-?[\d.]+) (-?[\d.]+)\)', a)
        if tr:
            off = (float(tr.group(1)), float(tr.group(2)))
        w = _ancho(t, px, bold)
        anc = _atributo(a, 'text-anchor', 'start')
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
        if v['_type'] in ('UMLClassView', 'UMLActorView', 'UMLInterfaceView', 'UMLNoteView') and v.get('visible', True) is not False:
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
        ancho, alto = _numero(_atributo(a, 'width'), -1), _numero(_atributo(a, 'height'), -1)
        if abs(ancho - 14) > 0.01 or alto < 18:
            continue
        tr = re.search(r'matrix\(1 0 0 1 (-?[\d.]+) (-?[\d.]+)\)', a)
        rx, ry = (float(tr.group(1)), float(tr.group(2))) if tr else (0, 0)
        x, y = _numero(_atributo(a, 'x')) + rx - dx, _numero(_atributo(a, 'y')) + ry - dy
        acts.append((x, y, x + 14, y + alto))
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
        head = f.read(2000)
    m = re.search(r'<svg[^>]*?\swidth="([\d.]+)[^"]*"[^>]*?\sheight="([\d.]+)', head) or \
        re.search(r'width="([\d.]+)" height="([\d.]+)"', head)
    return (int(float(m.group(1))), int(float(m.group(2)))) if m else (None, None)


def tamano_png(data):
    """(ancho, alto) leidos de la cabecera IHDR de un PNG."""
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise MdjError('La imagen generada no es un PNG valido')
    return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')


def _png_primeras_filas(data, alto):
    """Deja solo las primeras `alto` filas de un PNG. No hace falta reinterpretar pixeles: el filtro de cada fila
    solo depende de las anteriores, asi que basta con cortar el flujo descomprimido."""
    w, h = tamano_png(data)
    bits, color, entrelazado = data[24], data[25], data[28]
    canales = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)
    if h <= alto or entrelazado or bits != 8 or not canales:
        return data
    otros, idat, i = [], b'', 8
    while i < len(data):
        n = int.from_bytes(data[i:i + 4], 'big')
        tipo, cuerpo = data[i + 4:i + 8], data[i + 8:i + 8 + n]
        if tipo == b'IDAT':
            idat += cuerpo
        elif tipo not in (b'IHDR', b'IEND'):
            otros.append((tipo, cuerpo))
        i += 12 + n
    filas = zlib.decompress(idat)[:alto * (w * canales + 1)]
    trozo = lambda t, c: len(c).to_bytes(4, 'big') + t + c + zlib.crc32(t + c).to_bytes(4, 'big')
    ihdr = data[16:20] + alto.to_bytes(4, 'big') + data[24:29]
    return (data[:8] + trozo(b'IHDR', ihdr) + b''.join(trozo(t, c) for t, c in otros)
            + trozo(b'IDAT', zlib.compress(filas, 6)) + trozo(b'IEND', b''))


def recortar(svg, x=0, y=0, ancho=None, alto=None, salida=None, max_lado=None, timeout=None):
    chrome = chrome_bin()
    if not chrome:
        raise MdjError('No encontre Chrome, Chromium ni Edge: instala uno o define STARUML_MCP_CHROME_BIN')
    timeout = timeout or _timeout('STARUML_MCP_CHROME_TIMEOUT', 30)
    svg = os.path.abspath(os.path.expanduser(svg))
    if not os.path.exists(svg):
        raise MdjError(f'No existe el SVG: {svg}')
    W, H = _svg_size(svg)
    ancho = int(ancho or (W - x if W else 1200)); alto = int(alto or (H - y if H else 800))
    if ancho <= 0 or alto <= 0:
        raise MdjError('La region pedida queda fuera del SVG')
    # max_lado se logra escalando en el navegador (el SVG es vectorial: la imagen queda nitida)
    escala = min(1.0, max_lado / max(ancho, alto)) if max_lado else 1.0
    vw, vh = max(1, round(ancho * escala)), max(1, round(alto * escala))
    tmp = tempfile.mkdtemp(prefix='staruml_mcp_')
    prof = os.path.join(tmp, 'perfil_' + uuid.uuid4().hex[:8])
    html = os.path.join(tmp, 'r.html')
    png = os.path.join(tmp, 'out.png')
    try:
        with open(html, 'w', encoding='utf-8') as f:
            f.write(f"<html><body style='margin:0;overflow:hidden;background:#fff'>"
                    f"<div style='position:absolute;left:0;top:0;transform:scale({escala});transform-origin:0 0'>"
                    f"<img src='{pathlib.Path(svg).as_uri()}' style='position:absolute;left:{-int(x)}px;top:{-int(y)}px'>"
                    f"</div></body></html>")
        # en modo headless el area visible es mas baja que la ventana (87 px en Chromium 14x): se pide una ventana
        # mas alta y la imagen se corta a la medida exacta
        cmd = [chrome, '--headless=new', '--disable-gpu', f'--user-data-dir={prof}', f'--screenshot={png}',
               f'--window-size={vw},{vh + 200}', '--hide-scrollbars', '--no-first-run', '--no-default-browser-check']
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            cmd.append('--no-sandbox')  # Chrome no arranca como root sin esto (contenedores, CI)
        log.debug('captura con Chrome (%sx%s, limite %s s): %s', vw, vh, timeout, ' '.join(cmd))
        p = subprocess.Popen(cmd + [pathlib.Path(html).as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        try:
            while time.time() - t0 < timeout and p.poll() is None:
                if os.path.exists(png) and os.path.getsize(png) > 0:
                    time.sleep(0.4)
                    break
                time.sleep(0.2)
        finally:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
            if shutil.which('pkill'):
                subprocess.run(['pkill', '-f', prof], capture_output=True)
        if not os.path.exists(png) or os.path.getsize(png) == 0:
            log.warning('Chrome no genero la imagen en %.1f s', time.time() - t0)
            raise MdjError('Chrome no genero la imagen')
        with open(png, 'rb') as f:
            data = _png_primeras_filas(f.read(), vh)
        destino = None
        if salida:
            destino = os.path.abspath(os.path.expanduser(salida))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, 'wb') as f:
                f.write(data)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {'png': data, 'salida': destino, 'region': [int(x), int(y), ancho, alto], 'tamano_svg': [W, H]}


def ver_visual(mdj, diagrama, salida=None, max_lado=1600, formato='png', forzar=False):
    """Genera una imagen visual PNG de alta fidelidad del diagrama indicado,
    optimizada para inspeccion visual e IA multimodal."""
    mdj = os.path.abspath(os.path.expanduser(mdj))
    doc = Doc(mdj)
    dg = doc.diagram(diagrama)
    dg_nombre = dg.get('name') or ''
    # cache propia de cada proyecto y diagrama (ruta del .mdj + id): dos proyectos con un diagrama homonimo no se pisan
    clave = hashlib.sha1(f'{mdj}|{dg["_id"]}'.encode('utf-8')).hexdigest()[:16]
    cache_dir = os.path.join(tempfile.gettempdir(), 'staruml_mcp_renders', clave)
    svg_cache = os.path.join(cache_dir, 'diagrama.svg')
    mdj_mtime = os.path.getmtime(mdj)
    # un SVG exportado a mano junto al .mdj solo sirve si ese nombre de diagrama es unico en el proyecto
    posibles = [svg_cache]
    if sum(1 for d in doc.diagrams() if d.get('name') == dg_nombre) == 1:
        mdj_dir = os.path.dirname(mdj)
        posibles = [os.path.join(mdj_dir, 'renders', f'{_nombre_archivo(dg_nombre)}.svg'),
                    os.path.join(mdj_dir, f'{_nombre_archivo(dg_nombre)}.svg'), svg_cache]
    svg_origen = next((p for p in posibles if os.path.exists(p) and os.path.getmtime(p) >= mdj_mtime), None)
    if forzar or svg_origen is None:
        os.makedirs(cache_dir, exist_ok=True)
        r = exportar(mdj, cache_dir, dg['_id'], formato='svg')
        os.replace(r['archivos'][0], svg_cache)
        svg_origen = svg_cache

    res_crop = recortar(svg_origen, salida=salida, max_lado=max_lado)

    resumen_elementos = []
    if dg.get('_type') == 'UMLClassDiagram':
        for v in dg.get('ownedViews', []):
            m = v.get('model')
            if isinstance(m, dict) and '$ref' in m and m['$ref'] in doc.ids:
                el = doc.ids[m['$ref']]
                if el and el.get('_type') in ('UMLClass', 'UMLActor', 'UMLInterface'):
                    resumen_elementos.append(f"{el.get('name')} ({doc.kind(el)})")
    elif dg.get('_type') == 'UMLSequenceDiagram':
        import staruml_mdj as M
        sec = M.secuencia(doc, dg['_id'])
        resumen_elementos = [f"Lifeline: {lf}" for lf in sec.get('lifelines', [])]

    return {
        'diagrama': dg_nombre,
        'tipo': dg['_type'],
        'png': res_crop['png'],
        'salida': res_crop['salida'],
        'tamano_original': res_crop['tamano_svg'],
        'vistas': len(dg.get('ownedViews', [])),
        'elementos': resumen_elementos[:35]
    }
