# Exportar diagramas con el CLI de StarUML, revisar el SVG y recortar zonas a PNG.
# Funciona en macOS, Linux y Windows: StarUML y Chrome se buscan en las rutas tipicas, en el PATH o en
# STARUML_MCP_STARUML_BIN / STARUML_MCP_CHROME_BIN; los limites de tiempo se ajustan con
# STARUML_MCP_EXPORT_TIMEOUT y STARUML_MCP_CHROME_TIMEOUT (segundos).
import hashlib
import json
import logging
import math
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

from .mdj import Doc, MdjError, staruml_cli, chrome_bin

log = logging.getLogger('staruml_mcp.render')


def _timeout(variable, defecto):
    try:
        return max(1, int(os.environ.get(variable, defecto)))
    except ValueError:
        return defecto


_RESERVADOS_WINDOWS = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{d}{i}' for d in ('COM', 'LPT') for i in range(1, 10)}


def _nombre_archivo(nombre):
    """Nombre de diagrama convertido en nombre de archivo valido en cualquier sistema (en Windows, 'con' o 'aux'
    son dispositivos aunque lleven extension: se les agrega '_' antes del primer punto)."""
    n = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', nombre or '').strip(' .') or 'diagrama'
    base, punto, resto = n.partition('.')
    return base + '_' + punto + resto if base.rstrip(' ').upper() in _RESERVADOS_WINDOWS else n


# ---------------------------------------------------------------------------
# Exportar
# ---------------------------------------------------------------------------

FORMATOS = ('svg', 'png', 'jpeg', 'pdf')
_PNG_FIRMA = b'\x89PNG\r\n\x1a\n'
# El CLI nombra el archivo de cada diagrama con su _id: letras y digitos tal cual, lo demas como _<hex>_. Asi no
# chocan homonimos ni nombres con '/', ':' o vacios. (Sin '/' en la plantilla: el CLI la toma como parte de la ruta.)
_PLANTILLA_ID = ("<%=element._id.replace(new RegExp('[^A-Za-z0-9]', 'g'), "
                 "function (c) { return '_' + c.charCodeAt(0).toString(16) + '_' })%>")


def _id_archivo(i):
    """Nombre de archivo que da _PLANTILLA_ID para un _id."""
    return re.sub(r'[^A-Za-z0-9]', lambda m: '_%x_' % ord(m.group()), i)


def _nombre_seleccionable(nombre):
    """True si el selector [name=...] del CLI encuentra este nombre: el CLI parte el valor en '.', '@', '[', ']',
    '=' y '::' y le quita los espacios de las orillas."""
    return bool(nombre) and nombre == nombre.strip() and not re.search(r'[.@\[\]=:\x00-\x1f]', nombre)


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


def _archivo_valido(p, formato):
    """El CLI a veces deja archivos vacios o a medias (p. ej. si truena a mitad de un diagrama): se revisa la firma
    (y en SVG y PDF, tambien el final)."""
    try:
        with open(p, 'rb') as f:
            ini = f.read(4096)
            f.seek(max(0, os.path.getsize(p) - 64))
            fin = f.read().rstrip()
    except OSError:
        return False
    if formato == 'png':
        return ini.startswith(_PNG_FIRMA)
    if formato == 'jpeg':
        return ini.startswith(b'\xff\xd8\xff')
    if formato == 'pdf':
        return ini.startswith(b'%PDF') and b'%%EOF' in fin
    return b'<svg' in ini and fin.endswith(b'</svg>')


def _archivos_en(carpeta):
    return sorted(os.path.join(r, f) for r, _, fs in os.walk(carpeta) for f in fs)


def _colocar(origen, destino):
    """Copia origen a destino sin dejar un archivo a medias (copia temporal junto al destino + os.replace)."""
    if os.path.isdir(destino):
        raise MdjError(f'Ya existe una carpeta con el nombre de salida: {destino}')
    tmp = os.path.join(os.path.dirname(destino), f'.{os.path.basename(destino)}.{uuid.uuid4().hex[:8]}.tmp')
    try:
        shutil.copyfile(origen, tmp)
        os.replace(tmp, destino)
    except OSError as e:
        raise MdjError(f'No pude escribir {destino}: {e.strerror or e}') from None
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _copia_para_seleccionar(doc, dg, tmp, siempre_marca=False):
    """Copia temporal del modelo donde un selector del CLI encuentra solo al diagrama pedido. Si su nombre lo admite
    el selector, se usa [name=...] y los homonimos se renombran en la copia; si no, se marca su 'documentation' (que
    no se dibuja) y se selecciona por esa marca. El diagrama pedido no cambia, asi que la imagen es la misma.
    Devuelve (ruta del .mdj a exportar, selector)."""
    nombre = dg.get('name') or ''
    homonimos = [d for d in doc.diagrams() if d is not dg and d.get('name') == nombre]
    if _nombre_seleccionable(nombre) and not siempre_marca:
        if not homonimos:
            return doc.path, f'@{dg["_type"]}[name={nombre}]'
        for i, d in enumerate(homonimos):
            d['name'] = f'{nombre}__mcp_homonimo_{i}'
        selector = f'@{dg["_type"]}[name={nombre}]'
    else:
        marca = 'mcpsel' + uuid.uuid4().hex
        dg['documentation'] = marca
        selector = f'@Diagram[documentation={marca}]'
    fuente = os.path.join(tmp, 'modelo.mdj')
    with open(fuente, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc.d, f, ensure_ascii=False, indent='\t')
    return fuente, selector


def _exportar_pdf(cli, doc, dgs, todos, carpeta, timeout, tmp):
    # el subcomando pdf junta en un solo archivo todo lo que seleccione (una pagina por diagrama)
    if todos:
        fuente, selector = doc.path, '@Diagram'
        nombre = _nombre_archivo(os.path.splitext(os.path.basename(doc.path))[0])
    else:
        # siempre por marca: si el selector no encontrara nada, el CLI igual deja un PDF con una pagina en blanco
        fuente, selector = _copia_para_seleccionar(doc, dgs[0], tmp, siempre_marca=True)
        nombre = _nombre_archivo(dgs[0].get('name'))
    pdf = os.path.join(tmp, 'salida.pdf')
    salida = _correr([cli, 'pdf', fuente, '-s', selector, '-o', pdf], timeout)
    if not os.path.isfile(pdf) or not _archivo_valido(pdf, 'pdf'):
        raise MdjError('StarUML no genero el PDF. Salida del CLI: ' + (salida.strip()[-600:] or '(vacia)'))
    with open(pdf, 'rb') as f:
        paginas = len(re.findall(rb'/Type\s*/Page\b', f.read()))
    destino = os.path.join(carpeta, nombre + '.pdf')
    _colocar(pdf, destino)
    r = {'exportados': paginas if todos else 1, 'archivos': [destino], 'selector': selector,
         'nota': 'Un solo PDF con una pagina por diagrama.' if todos else '', 'salida_cli': ''}
    if not todos:
        r['id'] = dgs[0]['_id']
    return r


def exportar(mdj, carpeta, diagrama=None, formato='svg', timeout=None):
    """Exporta un diagrama (nombre o id) o todos. Cada archivo se identifica por el _id del diagrama, asi que funciona
    con homonimos y con nombres que el selector del CLI no acepta. Lanza MdjError si no sale ningun archivo valido."""
    cli = staruml_cli()
    if not cli:
        raise MdjError('No encontre StarUML: instalalo o define STARUML_MCP_STARUML_BIN con la ruta del ejecutable')
    if formato not in FORMATOS:
        raise MdjError('formato debe ser svg, png, jpeg o pdf')
    timeout = timeout or _timeout('STARUML_MCP_EXPORT_TIMEOUT', 150)
    mdj = os.path.abspath(os.path.expanduser(mdj))
    carpeta = os.path.abspath(os.path.expanduser(carpeta))
    doc = Doc(mdj)
    todos = diagrama in (None, '', 'todos')
    dgs = doc.diagrams() if todos else [doc.diagram(diagrama)]
    if not dgs:
        raise MdjError('El modelo no tiene diagramas')
    try:
        os.makedirs(carpeta, exist_ok=True)
    except OSError as e:
        raise MdjError(f'No pude crear la carpeta {carpeta}: {e.strerror or e}') from None
    tmp = tempfile.mkdtemp(prefix='staruml_mcp_exp_')
    try:
        if formato == 'pdf':
            return _exportar_pdf(cli, doc, dgs, todos, carpeta, timeout, tmp)
        salida_tmp = os.path.join(tmp, 'out')
        os.makedirs(salida_tmp)
        plantilla = os.path.join(salida_tmp, f'{_PLANTILLA_ID}.{formato}')
        if not todos:
            dg = dgs[0]
            fuente, selector = _copia_para_seleccionar(doc, dg, tmp)
            salida = _correr([cli, 'image', fuente, '-f', formato, '-s', selector, '-o', plantilla], timeout)
            # la seleccion da un solo diagrama: el unico archivo que salga es el suyo
            producidos = _archivos_en(salida_tmp)
            if len(producidos) != 1 or not _archivo_valido(producidos[0], formato):
                raise MdjError(f'StarUML no genero la imagen del diagrama "{dg.get("name")}" '
                               f'({len(producidos)} archivos). Salida del CLI: {salida.strip()[-400:]}')
            destino = os.path.join(carpeta, f'{_nombre_archivo(dg.get("name"))}.{formato}')
            _colocar(producidos[0], destino)
            return {'exportados': 1, 'archivos': [destino], 'selector': selector, 'id': dg['_id'], 'nota': '',
                    'salida_cli': ''}
        selector = '@Diagram'  # todos: UML y los de las extensiones (ERD, BPMN, C4, SysML...)
        salida = _correr([cli, 'image', mdj, '-f', formato, '-s', selector, '-o', plantilla], timeout)
        hechos, danados = {}, []
        for d in dgs:
            p = os.path.join(salida_tmp, f'{_id_archivo(d["_id"])}.{formato}')
            if os.path.isfile(p):
                if _archivo_valido(p, formato):
                    hechos[d['_id']] = p
                else:
                    danados.append(d)
        if not hechos:
            raise MdjError('StarUML no genero ninguna imagen. Salida del CLI: ' + (salida.strip()[-600:] or '(vacia)'))
        # el archivo lleva el nombre del diagrama; si dos darian el mismo (homonimos, o iguales sin distinguir
        # mayusculas como en macOS y Windows), los dos llevan su id al final
        nombres = {d['_id']: _nombre_archivo(d.get('name')) for d in dgs if d['_id'] in hechos}
        cuenta = {}
        for n in nombres.values():
            cuenta[n.lower()] = cuenta.get(n.lower(), 0) + 1
        archivos, con_id = [], 0
        for d in dgs:
            if d['_id'] not in hechos:
                continue
            n = nombres[d['_id']]
            if cuenta[n.lower()] > 1:
                n = f'{n}__{_id_archivo(d["_id"])}'
                con_id += 1
            destino = os.path.join(carpeta, f'{n}.{formato}')
            _colocar(hechos[d['_id']], destino)
            archivos.append(destino)
        faltan = [f'{d.get("name")} ({d["_id"]})' for d in dgs if d['_id'] not in hechos]
        nota = []
        if con_id:
            nota.append(f'{con_id} diagramas con nombre repetido llevan su id al final del archivo (nombre__id).')
        if danados:
            nota.append(f'{len(danados)} salieron vacios o incompletos: '
                        + ', '.join(f'{d.get("name")} ({d["_id"]})' for d in danados))
        if len(faltan) > len(danados):
            nota.append(f'No salieron {len(faltan) - len(danados)} diagramas.')
        r = {'exportados': len(archivos), 'archivos': sorted(archivos), 'selector': selector,
             'nota': ' '.join(nota), 'salida_cli': salida.strip()[-600:] if faltan else ''}
        if faltan:
            r['sin_exportar'] = faltan
        return r
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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


_NUM = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
_PARAMS = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'A': 7, 'C': 6, 'S': 4, 'Q': 4, 'T': 2}


def _polilineas(d):
    """Tramos abiertos del atributo d de un <path>, como listas de puntos. Arcos (las esquinas redondeadas de las
    lineas) y curvas se aproximan con puntos. Un tramo cerrado (Z, o que vuelve a su primer punto) es el contorno de
    una figura, no una linea, y no se devuelve."""
    fichas = re.findall(r'[A-Za-z]|' + _NUM, d or '')
    tramos, pts, cmd, i, x, y, x0, y0 = [], [], None, 0, 0.0, 0.0, 0.0, 0.0

    def cerrar(abierto):
        if len(pts) > 1 and abierto and not (len(pts) > 3 and abs(pts[0][0] - pts[-1][0]) + abs(pts[0][1] - pts[-1][1]) < 0.5):
            tramos.append(list(pts))
        pts.clear()

    while i < len(fichas):
        f = fichas[i]
        if f.isalpha():
            cmd, i = f, i + 1
            if cmd in 'Zz':
                cerrar(False)
                x, y = x0, y0
            elif cmd.upper() not in _PARAMS:
                break  # comando desconocido: se deja lo leido hasta aqui
            continue
        n = _PARAMS.get((cmd or '').upper())
        if not n or i + n > len(fichas) or any(t.isalpha() for t in fichas[i:i + n]):
            break
        v = [float(t) for t in fichas[i:i + n]]
        i += n
        c, rel = cmd.upper(), cmd.islower()
        bx, by = (x, y) if rel else (0.0, 0.0)
        if c == 'M':
            cerrar(True)
            x, y = bx + v[0], by + v[1]
            x0, y0 = x, y
            pts.append((x, y))
            cmd = 'l' if rel else 'L'  # los pares que siguen a un M son L
            continue
        if not pts:
            pts.append((x, y))
        if c == 'H':
            x = bx + v[0] if rel else v[0]
            nuevos = [(x, y)]
        elif c == 'V':
            y = (y + v[0]) if rel else v[0]
            nuevos = [(x, y)]
        elif c in ('L', 'T', 'A'):
            nx, ny = bx + v[-2], by + v[-1]
            nuevos = [(nx, ny)]
        else:  # C, S, Q: puntos de la curva (las de control solo sirven para seguirla)
            ctl = [(bx + v[k], by + v[k + 1]) for k in range(0, n, 2)]
            ctl = [(x, y)] + ctl if c != 'S' else [(x, y), (x, y)] + ctl
            nuevos = []
            for t in (0.25, 0.5, 0.75, 1.0):
                q = ctl
                while len(q) > 1:
                    q = [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for a, b in zip(q, q[1:])]
                nuevos.append(q[0])
        pts.extend(nuevos)
        x, y = pts[-1]
    cerrar(True)
    return tramos


def _es_linea(a):
    """Un <path> que se dibuja como linea: con trazo visible (de cualquier color, continuo o punteado) y sin relleno.
    Los rellenos son fondos de figuras y puntas de flecha."""
    trazo = (_atributo(a, 'stroke', '') or '').strip().lower()
    if trazo in ('', 'none', 'transparent') or _numero(_atributo(a, 'stroke-opacity'), 1.0) <= 0 \
            or _numero(_atributo(a, 'stroke-width'), 1.0) <= 0:
        return False
    return (_atributo(a, 'fill', 'none') or 'none').strip().lower() in ('none', 'transparent')


# Vistas que son zonas: las lineas pasan por ellas sin que sea un problema (marcos, fragmentos y usos de interaccion
# de las secuencias, carriles, particiones, pools, grupos, regiones y zonas de nube, diagramas de tiempos)
_ZONAS = ('Frame', 'Fragment', 'Operand', 'InteractionUse', 'Continuation', 'Swimlane', 'Partition', 'Lane', 'Pool',
          'Group', 'Zone', 'Region', 'Timing')


def _rect(v):
    return (v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height'])


def _con_geometria(v):
    return v.get('visible', True) is not False and 'head' not in v and \
        all(isinstance(v.get(k), (int, float)) and not isinstance(v.get(k), bool) for k in ('left', 'top', 'width', 'height'))


def revisar_svg(svg, mdj, diagrama, max_items=80):
    """Lineas que cruzan notas o cajas, lineas sobre etiquetas, etiquetas encimadas,
    texto que se sale de las notas y etiquetas sobre activaciones (secuencias)."""
    with open(os.path.expanduser(svg), encoding='utf-8') as f:
        s = f.read()
    doc = Doc(mdj)
    dg = doc.diagram(diagrama)
    textos, girados, off = [], [], None
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
        gm = re.search(r'matrix\((-?[\d.e+-]+) (-?[\d.e+-]+) (-?[\d.e+-]+) (-?[\d.e+-]+) (-?[\d.e+-]+) (-?[\d.e+-]+)\)', a)
        if gm and not tr:
            # texto girado (nombres de carriles, pools y lanes): se transforman las esquinas de su caja
            ma, mb, mc, md, me, mf = (float(g) for g in gm.groups())
            arriba = 'text-before-edge' in (_atributo(a, 'dominant-baseline', '') or '')
            y0, y1 = (y, y + px) if arriba else (y - px / 2 + 1, y + px / 2 - 1)
            esq = [(ma * cx + mc * cy + me, mb * cx + md * cy + mf) for cx in (x0, x0 + w) for cy in (y0, y1)]
            girados.append((t, min(p[0] for p in esq), min(p[1] for p in esq),
                            max(p[0] for p in esq), max(p[1] for p in esq)))
            continue
        if 'text-before-edge' in (_atributo(a, 'dominant-baseline', '') or ''):
            textos.append((t, x0, y + 1, x0 + w, y + px - 1))  # y es el borde de arriba del texto
        else:
            textos.append((t, x0, y - px / 2 + 1, x0 + w, y + px / 2 - 1))
    dx, dy = off if off else (0, 0)
    # los girados estan en coordenadas del SVG; los demas, en las del desfase de StarUML
    textos += [(t, a_ - dx, b_ - dy, c_ - dx, d_ - dy) for t, a_, b_, c_, d_ in girados]
    polis = []
    for m in re.finditer(r'<path([^>]*)/?>', s):
        if _es_linea(m.group(1)):
            for pts in _polilineas(_atributo(m.group(1), 'd', '')):
                polis.append([(px_ - dx, py_ - dy) for px_, py_ in pts])
    vistas = [v for v in dg.get('ownedViews', []) if _con_geometria(v)]
    # cajas que una linea no debe cruzar: todas las vistas menos las zonas; de una lifeline de secuencia solo cuenta
    # su encabezado (los mensajes pasan por su linea punteada)
    cajas, notas = [], []
    for v in vistas:
        nombre = doc.name_of(v['model'].get('$ref')) if isinstance(v.get('model'), dict) else v['_type']
        if v['_type'] == 'UMLNoteView':
            notas.append((v.get('text', '')[:40], _rect(v)))
        elif v['_type'] == 'UMLSeqLifelineView':
            cab = next((c for c in v.get('subViews', []) if c.get('_type') == 'UMLNameCompartmentView'
                        and _con_geometria(c)), None)
            if cab:
                cajas.append((nombre, _rect(cab)))
        elif not any(z in v['_type'] for z in _ZONAS):
            cajas.append((nombre, _rect(v)))
    dentro = lambda p, r, m=0: r[0] - m <= p[0] <= r[2] + m and r[1] - m <= p[1] <= r[3] + m
    enc = lambda r, m: (r[0] + m, r[1] + m, r[2] - m, r[3] - m)
    # el dibujo propio de una figura sin nada adentro (rombo, triangulo, icono, linea punteada de una lifeline...) no
    # es una linea que pase sobre algo: los segmentos que caen enteros dentro de ella se ignoran. Una figura con otras
    # adentro (paquete, nodo, sistema, clase con partes), aunque no las tenga en containedViews, no cuenta: las lineas
    # entre lo que tiene adentro si se revisan. La lifeline siempre cuenta (su linea punteada es suya).
    contiene = lambda r, w: r[0] <= w[0] and r[1] <= w[1] and w[2] <= r[2] and w[3] <= r[3]
    hojas = [_rect(v) for v in vistas if v['_type'] != 'UMLNoteView' and not any(z in v['_type'] for z in _ZONAS)
             and (v['_type'] == 'UMLSeqLifelineView' or (not v.get('containedViews')
                  and not any(w is not v and contiene(_rect(v), _rect(w)) for w in vistas)))]
    propios = lambda p, q: any(dentro(p, r, 2) and dentro(q, r, 2) for r in [r for _, r in notas] + hojas)
    # notas primero: se revisan con margen hacia afuera; las cajas, con margen hacia adentro (la linea llega a su borde)
    figuras = [(f'LINEA CRUZA NOTA "{n}"', enc(r, -3), r) for n, r in notas] + \
              [(f'LINEA CRUZA CAJA {n}', enc(r, 4), r) for n, r in cajas]
    prob, nseg = [], 0
    rd = lambda p: [round(c) for c in p]
    for pts in polis:
        # las cajas y notas donde empieza o termina la linea (y las que las contienen) son suyas: no las cruza
        suyas = {k for k, (_, _, r) in enumerate(figuras) if dentro(pts[0], r, 3) or dentro(pts[-1], r, 3)}
        for p, q in zip(pts, pts[1:]):
            if abs(p[0] - q[0]) + abs(p[1] - q[1]) <= 0.5 or propios(p, q):
                continue
            nseg += 1
            for k, (texto, r, _) in enumerate(figuras):
                if k not in suyas and _cruza(p, q, r):
                    prob.append(f'{texto} {rd(p)}-{rd(q)}')
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
    return {'diagrama': dg.get('name'), 'segmentos': nseg, 'textos': len(textos), 'activaciones': len(acts),
            'n_problemas': len(prob), 'problemas': prob[:max_items],
            'desfase_svg': {'x': dx, 'y': dy}}


# ---------------------------------------------------------------------------
# Recortar SVG a PNG (Chrome headless)
# ---------------------------------------------------------------------------

def _svg_size(svg):
    """(ancho, alto) del elemento raiz <svg>: de width/height o, si no hay, del viewBox. (None, None) si no se sabe."""
    with open(svg, encoding='utf-8', errors='replace') as f:
        head = f.read(8192)
    raiz = re.search(r'<svg\b[^>]*>', head)
    if not raiz:
        return (None, None)
    a = raiz.group(0)
    w = re.search(r'\swidth\s*=\s*["\']\s*([\d.]+)\s*(?:px)?\s*["\']', a)
    h = re.search(r'\sheight\s*=\s*["\']\s*([\d.]+)\s*(?:px)?\s*["\']', a)
    if w and h:
        return (int(float(w.group(1))), int(float(h.group(1))))
    vb = re.search(r'\sviewBox\s*=\s*["\']\s*' + _NUM + r'[\s,]+' + _NUM + r'[\s,]+([\d.]+)[\s,]+([\d.]+)\s*["\']', a)
    return (int(float(vb.group(1))), int(float(vb.group(2)))) if vb else (None, None)


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


def _validar_salida_png(salida):
    """Ruta absoluta donde guardar un PNG. Tiene que terminar en .png y, si ya existe, ser un archivo PNG (no un
    enlace, una carpeta ni otro tipo de archivo): asi nunca se pisa el .mdj ni nada que no sea una imagen."""
    if not salida:
        return None
    destino = os.path.abspath(os.path.expanduser(salida))
    if not destino.lower().endswith('.png'):
        raise MdjError(f'salida debe terminar en .png: {destino}')
    if os.path.islink(destino):
        raise MdjError(f'salida es un enlace; usa la ruta real: {destino}')
    if os.path.exists(destino):
        if not os.path.isfile(destino):
            raise MdjError(f'salida ya existe y no es un archivo: {destino}')
        with open(destino, 'rb') as f:
            if f.read(8) != _PNG_FIRMA:
                raise MdjError(f'salida ya existe y no es un PNG; no se sobrescribe: {destino}')
    return destino


def _entero(v, nombre, defecto=None):
    if v is None:
        return defecto
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise MdjError(f'{nombre} debe ser un numero: {v!r}') from None
    if not math.isfinite(n):
        raise MdjError(f'{nombre} debe ser un numero finito: {v!r}')
    return int(n)


def _validar_max_lado(max_lado):
    n = _entero(max_lado, 'max_lado')
    if n is not None and n < 0:
        raise MdjError('max_lado no puede ser negativo (0 = sin reducir)')
    return n


def recortar(svg, x=0, y=0, ancho=None, alto=None, salida=None, max_lado=None, timeout=None):
    """Recorta la region (x, y, ancho, alto) del SVG a PNG; sin ancho/alto llega hasta el borde. La region puede
    salirse en parte del SVG (esa parte queda en blanco), pero no por completo. salida, si se da, debe ser .png."""
    destino = _validar_salida_png(salida)
    x, y = _entero(x, 'x', 0), _entero(y, 'y', 0)
    ancho, alto = _entero(ancho, 'ancho'), _entero(alto, 'alto')
    if (ancho is not None and ancho <= 0) or (alto is not None and alto <= 0):
        raise MdjError('ancho y alto deben ser mayores que 0')
    max_lado = _validar_max_lado(max_lado)
    svg = os.path.abspath(os.path.expanduser(svg))
    if not os.path.isfile(svg):
        raise MdjError(f'No existe el SVG: {svg}')
    W, H = _svg_size(svg)
    if W is not None and H is not None:
        pedido = f'x={x}, y={y}, ancho={"hasta el borde" if ancho is None else ancho}, ' \
                 f'alto={"hasta el borde" if alto is None else alto}'
        ancho = W - x if ancho is None else ancho
        alto = H - y if alto is None else alto
        if x >= W or y >= H or x + ancho <= 0 or y + alto <= 0:
            raise MdjError(f'La region pedida queda fuera del SVG (mide {W}x{H}): {pedido}')
    else:
        ancho, alto = ancho or 1200, alto or 800
    chrome = chrome_bin()
    if not chrome:
        raise MdjError('No encontre Chrome, Chromium ni Edge: instala uno o define STARUML_MCP_CHROME_BIN')
    timeout = timeout or _timeout('STARUML_MCP_CHROME_TIMEOUT', 30)
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
                    f"<img src='{pathlib.Path(svg).as_uri()}' style='position:absolute;left:{-x}px;top:{-y}px'>"
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
        if destino:
            _validar_salida_png(destino)  # pudo cambiar mientras corria Chrome
            try:
                os.makedirs(os.path.dirname(destino), exist_ok=True)
            except OSError as e:
                raise MdjError(f'No pude crear la carpeta de salida: {e.strerror or e}') from None
            with open(png, 'wb') as f:
                f.write(data)
            _colocar(png, destino)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {'png': data, 'salida': destino, 'region': [x, y, ancho, alto], 'tamano_svg': [W, H]}


def _svg_en_cache(mdj, dg, forzar=False):
    """SVG del diagrama en una cache del temporal: una carpeta por archivo (ruta real) y diagrama (_id), con la huella
    (sha1) del contenido del .mdj que se dibujo. Se exporta de una copia de esos mismos bytes, asi la huella
    corresponde justo a la imagen; si el archivo cambia, se vuelve a exportar. Un SVG que este junto al .mdj no se
    usa: puede ser de otro modelo con un diagrama del mismo nombre."""
    ruta = os.path.realpath(mdj)
    with open(ruta, 'rb') as f:
        datos = f.read()
    huella = f'{hashlib.sha1(datos).hexdigest()} {dg["_id"]}'
    clave = hashlib.sha1(f'{ruta}|{dg["_id"]}'.encode('utf-8', 'surrogateescape')).hexdigest()[:16]
    carpeta = os.path.join(tempfile.gettempdir(), 'staruml_mcp_renders', clave)
    svg, sello = os.path.join(carpeta, 'diagrama.svg'), os.path.join(carpeta, 'diagrama.sha1')
    if not forzar and os.path.isfile(svg) and os.path.getsize(svg) > 0 and os.path.isfile(sello):
        with open(sello, encoding='utf-8') as f:
            if f.read().strip() == huella:
                return svg
    os.makedirs(carpeta, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='exp_', dir=carpeta)
    try:
        copia = os.path.join(tmp, 'modelo.mdj')
        with open(copia, 'wb') as f:
            f.write(datos)
        r = exportar(copia, os.path.join(tmp, 'out'), dg['_id'], formato='svg')
        if not r.get('archivos') or not os.path.isfile(r['archivos'][0]):
            raise MdjError(f'StarUML no genero el SVG del diagrama "{dg.get("name")}"')
        nuevo = os.path.join(tmp, 'sello')
        with open(nuevo, 'w', encoding='utf-8') as f:
            f.write(huella)
        # primero se invalida el sello, luego se cambia el SVG y al final se escribe el sello nuevo
        if os.path.exists(sello):
            os.remove(sello)
        os.replace(r['archivos'][0], svg)
        os.replace(nuevo, sello)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return svg


def ver_visual(mdj, diagrama, salida=None, max_lado=1600, formato='png', forzar=False):
    """Imagen PNG del diagrama (nombre o id) para revisarlo a simple vista. El SVG sale del CLI de StarUML y se
    guarda en una cache con clave por archivo, contenido y diagrama."""
    destino = _validar_salida_png(salida)
    _validar_max_lado(max_lado)
    mdj = os.path.abspath(os.path.expanduser(mdj))
    doc = Doc(mdj)
    dg = doc.diagram(diagrama)
    dg_nombre = dg.get('name') or ''
    svg_origen = _svg_en_cache(mdj, dg, forzar)

    res_crop = recortar(svg_origen, salida=destino, max_lado=max_lado)

    resumen_elementos = []
    if dg.get('_type') == 'UMLClassDiagram':
        for v in dg.get('ownedViews', []):
            m = v.get('model')
            if isinstance(m, dict) and '$ref' in m and m['$ref'] in doc.ids:
                el = doc.ids[m['$ref']]
                if el and el.get('_type') in ('UMLClass', 'UMLActor', 'UMLInterface'):
                    resumen_elementos.append(f"{el.get('name')} ({doc.kind(el)})")
    elif dg.get('_type') == 'UMLSequenceDiagram':
        from . import mdj as M
        sec = M.secuencia(doc, dg['_id'])
        resumen_elementos = [f"Lifeline: {lf}" for lf in sec.get('lifelines', [])]

    return {
        'diagrama': dg_nombre,
        'id': dg['_id'],
        'tipo': dg['_type'],
        'png': res_crop['png'],
        'salida': res_crop['salida'],
        'tamano_original': res_crop['tamano_svg'],
        'vistas': len(dg.get('ownedViews', [])),
        'elementos': resumen_elementos[:35]
    }
