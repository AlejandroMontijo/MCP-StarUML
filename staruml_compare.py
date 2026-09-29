# staruml_compare.py
# Comparador de diagramas StarUML (.mdj) contra codigo fuente (Java, Python, TypeScript/JavaScript, C#)
# y generador bidireccional (diagrama <-> codigo).
#  - Python se analiza con el modulo ast de la biblioteca estandar.
#  - Java, C# y TypeScript se analizan sobre una copia del codigo sin comentarios y con el contenido de los
#    textos vaciado (un '//' dentro de una URL o una llave dentro de un texto ya no confunden al parser), y los
#    miembros se toman solo del primer nivel de llaves de cada clase (lo que hay dentro de los metodos no cuenta).

import ast
import keyword
import os
import re
import unicodedata
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Normalizacion de tipos y nombres
# ---------------------------------------------------------------------------

_PRIMITIVOS = {
    'String': ('string', 'str', 'varchar', 'nvarchar', 'text', 'char', 'character'),
    'int': ('int', 'integer', 'long', 'short', 'byte', 'int16', 'int32', 'int64', 'uint', 'ulong', 'bigint', 'smallint'),
    'double': ('float', 'double', 'number', 'decimal', 'bigdecimal', 'real', 'money', 'single'),
    'boolean': ('bool', 'boolean'),
    'Date': ('date', 'localdate', 'datetime', 'localdatetime', 'timestamp', 'fecha', 'instant', 'offsetdatetime',
             'zoneddatetime', 'datetimeoffset', 'dateonly'),
    'void': ('void', 'none', 'null', 'undefined', 'unit'),
    'Object': ('object', 'any', 'unknown', 'var', 'dynamic'),
}
_ALIAS = {a: canon for canon, alias in _PRIMITIVOS.items() for a in alias}
_LISTAS = {'list', 'arraylist', 'linkedlist', 'collection', 'iterable', 'ienumerable', 'ilist', 'icollection', 'array',
           'sequence', 'readonlyarray', 'vector', 'readonlycollection', 'observablecollection', 'ireadonlylist',
           'ireadonlycollection'}
_SETS = {'set', 'hashset', 'treeset', 'linkedhashset', 'iset', 'frozenset', 'sortedset', 'readonlyset'}
_MAPAS = {'map', 'hashmap', 'treemap', 'linkedhashmap', 'dict', 'dictionary', 'idictionary', 'record', 'mapping',
          'sorteddictionary', 'readonlymap', 'ireadonlydictionary'}
_OPCIONALES = {'optional', 'nullable'}


def _sin_acentos(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def _dividir(texto: str, sep: str = ',') -> List[str]:
    """Divide por `sep` solo en el nivel superior (fuera de <>, (), [] y {})."""
    partes, actual, nivel = [], [], 0
    for c in texto:
        if c in '<([{':
            nivel += 1
        elif c in '>)]}':
            nivel = max(0, nivel - 1)
        if c == sep and nivel == 0:
            partes.append(''.join(actual))
            actual = []
        else:
            actual.append(c)
    partes.append(''.join(actual))
    return [p.strip() for p in partes if p.strip()]


def _normalizar_tipo(tipo) -> str:
    """Forma comun de un tipo en UML y en cualquier lenguaje: String, int, double, boolean, Date, void, Object,
    List<X>, Set<X>, Map<K,V> o el nombre de la clase tal cual (con sus mayusculas)."""
    if not isinstance(tipo, str) or not tipo.strip():
        return 'Object'
    # las referencias adelantadas de Python van entre comillas: List["Pedido"]
    t = re.sub(r'^(java\.lang\.|java\.util\.|typing\.|System\.Collections\.Generic\.|System\.)', '', tipo.strip().replace('"', '').replace("'", ''))
    t = re.sub(r'^(final|const|readonly)\s+', '', t)
    if t.endswith('?') or t.endswith('!'):
        t = t[:-1].strip()
    alternativas = [p for p in _dividir(t, '|') if p not in ('None', 'null', 'undefined')]
    if len(alternativas) == 1:
        t = alternativas[0]
    if t.endswith('[]'):
        return f'List<{_normalizar_tipo(t[:-2])}>'
    m = re.fullmatch(r'([\w.$]+)\s*[<\[]\s*(.+?)\s*[>\]]', t, re.S)
    if m:
        base, args = m.group(1).split('.')[-1], _dividir(m.group(2), ',')
        b = base.lower()
        if b in _OPCIONALES and len(args) == 1:
            return _normalizar_tipo(args[0])
        if b in _LISTAS and len(args) == 1:
            return f'List<{_normalizar_tipo(args[0])}>'
        if b in _SETS and len(args) == 1:
            return f'Set<{_normalizar_tipo(args[0])}>'
        if b in _MAPAS and len(args) == 2:
            return f'Map<{_normalizar_tipo(args[0])},{_normalizar_tipo(args[1])}>'
        return f'{base}<{",".join(_normalizar_tipo(a) for a in args)}>'
    if t.endswith('[]'):
        return f'List<{_normalizar_tipo(t[:-2])}>'
    if t.endswith('...'):
        return f'List<{_normalizar_tipo(t[:-3])}>'
    b = t.split('.')[-1].lower()
    if b in _ALIAS:
        return _ALIAS[b]
    if b in _LISTAS:
        return 'List<Object>'
    if b in _SETS:
        return 'Set<Object>'
    if b in _MAPAS:
        return 'Map<Object,Object>'
    return t.split('.')[-1] if re.fullmatch(r'[\w.$]+', t) else t


def _normalizar_nombre(nombre: str) -> str:
    """Clave para emparejar nombres: sin prefijos de estereotipo, acentos, espacios, guiones ni mayusculas."""
    if not nombre:
        return ''
    limpio = re.sub(r'^(bc_|ctrl_|ent_|i_|cls_)', '', nombre, flags=re.IGNORECASE)
    return re.sub(r'[\s_\-]+', '', _sin_acentos(limpio)).lower()


def _clave_tipo(tipo: str, numeros_iguales: bool = False) -> str:
    """Tipo normalizado con los nombres de clase tambien normalizados (acentos, mayusculas)."""
    t = _normalizar_tipo(tipo)
    if numeros_iguales:  # TypeScript/JavaScript solo tienen number
        t = re.sub(r'\bint\b', 'double', t)
    return re.sub(r'[^\W\d][\w$]*', lambda m: m.group(0) if m.group(0) in _PRIMITIVOS or m.group(0) in ('List', 'Set', 'Map')
                  else _normalizar_nombre(m.group(0)), t)


def _nombres_en_tipo(tipo: str) -> List[str]:
    """Nombres de clase (normalizados) que aparecen en un tipo: List<Pedido> -> ['pedido']."""
    return [_normalizar_nombre(n) for n in re.findall(r'[^\W\d][\w$]*', _normalizar_tipo(tipo))
            if n not in _PRIMITIVOS and n not in ('List', 'Set', 'Map')]


def _es_coleccion_tipo(tipo: str) -> bool:
    return bool(re.match(r'(List|Set|Map)<', _normalizar_tipo(tipo)))


def _es_coleccion_mult(mult: str) -> bool:
    mult = (mult or '').strip()
    if '*' in mult:
        return True
    if '..' in mult:
        return mult.split('..')[1].strip() not in ('0', '1', '')
    return mult.isdigit() and int(mult) > 1


def _nombre_metodo(mensaje: str) -> str:
    """'res = buscar(x)' -> 'buscar'; 'solicitar contrato' -> 'solicitar contrato'."""
    antes = (mensaje or '').split('(')[0]
    if '(' in (mensaje or ''):
        ids = re.findall(r'[^\W\d][\w$]*', antes)
        return ids[-1] if ids else antes.strip()
    return antes.strip()


# ---------------------------------------------------------------------------
# Extractor de UML desde .mdj
# ---------------------------------------------------------------------------

def _tipo_uml(doc, t) -> str:
    """El tipo de un atributo o parametro puede ser texto o una referencia {"$ref"} a una clase del modelo."""
    if isinstance(t, dict):
        el = doc.ids.get(t.get('$ref'))
        return (el.get('name') or '') if el else ''
    return t if isinstance(t, str) else ''


def extraer_elementos_diagrama(doc, nombre_diagrama: str) -> Dict[str, Any]:
    """Extrae clases, atributos, metodos, asociaciones y mensajes de un diagrama."""
    dg = doc.diagram(nombre_diagrama)
    tipo_dg = dg.get('_type')

    if tipo_dg == 'UMLClassDiagram':
        clases, asociaciones, generalizaciones = {}, [], []
        ids_en_diagrama = {v['model']['$ref'] for v in dg.get('ownedViews', [])
                           if isinstance(v.get('model'), dict) and '$ref' in v['model']}
        for cid in ids_en_diagrama:
            el = doc.ids.get(cid)
            if not el or el.get('_type') not in ('UMLClass', 'UMLInterface', 'UMLActor', 'UMLEnumeration'):
                continue
            attrs = []
            for a in el.get('attributes', []):
                t = _tipo_uml(doc, a.get('type'))
                if _es_coleccion_mult(a.get('multiplicity', '')) and t:
                    t = f'List<{t}>'
                attrs.append({'nombre': a.get('name', ''), 'tipo': _normalizar_tipo(t), 'visibilidad': a.get('visibility', 'public')})
            metodos = []
            for op in el.get('operations', []):
                params, ret = [], 'void'
                for p in op.get('parameters', []):
                    if p.get('direction') == 'return':
                        ret = _normalizar_tipo(_tipo_uml(doc, p.get('type')))
                    else:
                        params.append({'nombre': p.get('name', ''), 'tipo': _normalizar_tipo(_tipo_uml(doc, p.get('type')))})
                metodos.append({'nombre': op.get('name', ''), 'retorno': ret, 'parametros': params,
                                'visibilidad': op.get('visibility', 'public')})
            clases[el.get('name', '')] = {
                'id': el['_id'], 'nombre': el.get('name', ''), 'tipo': el['_type'], 'estereotipo': doc.kind(el),
                'documentacion': el.get('documentation', ''), 'atributos': attrs, 'metodos': metodos,
                'literales': [l.get('name', '') for l in el.get('literals', [])],
                'superclases': [], 'interfaces': [], 'asociaciones': []}

        # asociaciones: una entrada por cada sentido navegable, en la clase desde la que se navega.
        # 'navigable' cuenta; 'notNavigable' no; sin especificar (el default de StarUML) se toma como el sentido
        # extremo1 -> extremo2, salvo que el extremo 1 sea el unico marcado como navegable.
        for el in doc.ids.values():
            if not el:
                continue
            if el.get('_type') == 'UMLAssociation':
                e1, e2 = el.get('end1', {}), el.get('end2', {})
                o1, o2 = doc.ids.get(e1.get('reference', {}).get('$ref')), doc.ids.get(e2.get('reference', {}).get('$ref'))
                if not o1 or not o2:
                    continue
                c1, c2 = o1.get('name'), o2.get('name')
                if c1 not in clases and c2 not in clases:
                    continue
                n1, n2 = e1.get('navigable'), e2.get('navigable')
                nav2 = n2 == 'navigable' or (n2 is None and n1 != 'navigable')
                nav1 = n1 == 'navigable'
                asociaciones.append({'id': el['_id'], 'origen': c1, 'destino': c2, 'mult_origen': e1.get('multiplicity', ''),
                                     'mult_destino': e2.get('multiplicity', ''), 'rol_origen': e1.get('name', ''),
                                     'rol_destino': e2.get('name', ''), 'navegable': nav2, 'navegable_inverso': nav1})
                for (desde, hacia, fin, nav) in ((c1, c2, e2, nav2), (c2, c1, e1, nav1)):
                    if nav and desde in clases:
                        clases[desde]['asociaciones'].append({'id': el['_id'], 'origen': desde, 'destino': hacia,
                                                              'mult_destino': fin.get('multiplicity', ''),
                                                              'rol_destino': fin.get('name', ''), 'navegable': True})
            elif el.get('_type') in ('UMLGeneralization', 'UMLInterfaceRealization'):
                sub, sup = doc.ids.get(el.get('source', {}).get('$ref')), doc.ids.get(el.get('target', {}).get('$ref'))
                if sub and sup:
                    if el['_type'] == 'UMLGeneralization':
                        generalizaciones.append({'subclase': sub.get('name'), 'superclase': sup.get('name')})
                    if sub.get('name') in clases:
                        clave = 'superclases' if el['_type'] == 'UMLGeneralization' and sup['_type'] != 'UMLInterface' else 'interfaces'
                        clases[sub['name']][clave].append(sup.get('name'))
        return {'tipo_diagrama': 'UMLClassDiagram', 'nombre': dg.get('name'), 'clases': clases,
                'asociaciones': asociaciones, 'generalizaciones': generalizaciones}

    if tipo_dg == 'UMLSequenceDiagram':
        import staruml_mdj as M
        sec = M.secuencia(doc, dg['_id'])
        it = M.interaction_of(doc, dg)
        lifelines = []
        for l in it.get('participants', []):
            nombre, kind = M.lifeline_info(doc, l['_id'])
            lifelines.append({'tipo': nombre, 'estereotipo': kind})
        return {'tipo_diagrama': 'UMLSequenceDiagram', 'nombre': dg.get('name'), 'lifelines': lifelines,
                'mensajes': sec.get('mensajes', [])}

    return {'tipo_diagrama': tipo_dg, 'nombre': dg.get('name')}


# ---------------------------------------------------------------------------
# Parsers de codigo fuente
# ---------------------------------------------------------------------------

_EXTENSIONES = {'java': ('.java',), 'python': ('.py', '.pyw'), 'typescript': ('.ts', '.tsx', '.mts', '.cts', '.js', '.jsx', '.mjs', '.cjs'),
                'csharp': ('.cs',)}
_LENGUAJE_DE = {ext: lang for lang, exts in _EXTENSIONES.items() for ext in exts}
_NO_ESCANEAR = {'.git', '.hg', '.svn', 'target', 'build', 'node_modules', '__pycache__', '.idea', '.vscode', '.venv', 'venv',
                'env', 'dist', 'obj', 'bin', 'out', '.tox', '.mypy_cache', '.pytest_cache', 'site-packages', '.gradle',
                '.next', 'coverage', '.nuxt', 'vendor'}


def _limpiar_codigo(code: str, lang: str) -> str:
    """Quita comentarios y vacia el contenido de textos y caracteres, conservando comillas, longitudes y saltos
    de linea (las posiciones siguen coincidiendo con el original)."""
    out, i, n = [], 0, len(code)
    blanco = lambda s: re.sub(r'[^\n]', ' ', s)
    while i < n:
        c = code[i]
        d = code[i + 1] if i + 1 < n else ''
        if c == '/' and d == '/':
            j = code.find('\n', i)
            j = n if j < 0 else j
            out.append(' ' * (j - i))
            i = j
        elif c == '/' and d == '*':
            j = code.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(blanco(code[i:j]))
            i = j
        elif c in '"\'`':
            if lang == 'java' and code.startswith('"""', i):
                j = code.find('"""', i + 3)
                j = n if j < 0 else j + 3
            elif lang == 'csharp' and c == '"' and i > 0 and code[i - 1] == '@':
                j = i + 1
                while j < n:
                    if code[j] == '"':
                        if code[j + 1:j + 2] == '"':
                            j += 2
                            continue
                        break
                    j += 1
                j = min(n, j + 1)
            else:
                j = i + 1
                while j < n and code[j] != c:
                    if code[j] == '\\':
                        j += 2
                        continue
                    if code[j] == '\n' and c != '`':
                        break
                    j += 1
                j = min(n, j + 1)
            seg = code[i:j]
            out.append(seg[0] + blanco(seg[1:-1]) + seg[-1] if len(seg) > 1 else seg)
            i = j
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def _cierre(code: str, inicio: int) -> int:
    """Indice de la llave que cierra la que abre en `inicio`."""
    nivel = 0
    for i in range(inicio, len(code)):
        if code[i] == '{':
            nivel += 1
        elif code[i] == '}':
            nivel -= 1
            if nivel == 0:
                return i
    return len(code)


def _nivel_uno(cuerpo: str) -> str:
    """El cuerpo de una clase con cada bloque interno (metodos, clases anidadas, accesores) reducido a '{}'."""
    out, nivel = [], 0
    for c in cuerpo:
        if c == '{':
            if nivel == 0:
                out.append('{')
            nivel += 1
        elif c == '}':
            nivel -= 1
            if nivel == 0:
                out.append('}')
        elif nivel == 0:
            out.append(c)
    return ''.join(out)


def _declaraciones(texto: str, por_linea: bool = False):
    """Divide el primer nivel de una clase en declaraciones: (texto, terminador) con terminador ';', '{}' o '\\n'."""
    res, actual, par = [], [], 0
    i = 0
    while i < len(texto):
        c = texto[i]
        if c in '([':
            par += 1
        elif c in ')]':
            par = max(0, par - 1)
        if c == ';' and par == 0:
            res.append((''.join(actual), ';'))
            actual = []
        elif c == '{' and par == 0:
            res.append((''.join(actual), '{}'))
            actual = []
            i = texto.find('}', i) if texto.find('}', i) >= 0 else len(texto)
        elif c == '\n' and par == 0 and por_linea:
            u = ''.join(actual).strip()
            if u and not re.search(r'[,=|&(:<?.+\-*/]$', u) and not re.match(r'\s*[.?|&=]', texto[i + 1:]):
                res.append((''.join(actual), '\n'))
                actual = []
            else:
                actual.append(' ')
        else:
            actual.append(c)
        i += 1
    if ''.join(actual).strip():
        res.append((''.join(actual), ''))
    return [(re.sub(r'\s+', ' ', u).strip(), t) for u, t in res if u.strip()]


def _quitar_anotaciones(u: str) -> str:
    """Quita anotaciones de Java/TS (@X, @X(...)) y atributos de C# ([X], [X(...)])."""
    anterior = None
    while anterior != u:
        anterior = u
        u = re.sub(r'^\s*@[\w.$]+\s*(\((?:[^()]|\([^()]*\))*\))?\s*', '', u)
        u = re.sub(r'^\s*\[[^\[\]]*\]\s*', '', u)
    return u.strip()


_MODIF_JC = {'public', 'private', 'protected', 'internal', 'static', 'final', 'abstract', 'synchronized', 'native',
             'transient', 'volatile', 'default', 'sealed', 'override', 'virtual', 'readonly', 'const', 'async', 'extern',
             'unsafe', 'new', 'partial', 'strictfp', 'required', 'non-sealed'}
_MODIF_TS = {'public', 'private', 'protected', 'static', 'readonly', 'abstract', 'async', 'override', 'declare',
             'accessor', 'export', 'default'}
_NO_METODOS = {'if', 'for', 'while', 'switch', 'catch', 'return', 'new', 'typeof', 'function', 'super', 'this', 'sizeof',
               'foreach', 'using', 'lock', 'throw', 'await', 'yield', 'else', 'do', 'try', 'with', 'nameof', 'base'}
_CABECERA = re.compile(r'\b(class|interface|enum|record|struct)\s+(?:(?:struct|class)\s+)?([^\W\d][\w$]*)')


def _modificadores(u: str, validos: set):
    mods = []
    while True:
        m = re.match(r'([a-z-]+)\s+', u)
        if m and m.group(1) in validos:
            mods.append(m.group(1))
            u = u[m.end():]
        else:
            return mods, u


def _visibilidad(mods, defecto='package'):
    return next((m for m in mods if m in ('public', 'private', 'protected', 'internal')), defecto)


def _base_simple(t: str) -> str:
    t = re.sub(r'<.*>', '', t).strip()
    return t.split('.')[-1] if t else ''


def _params_jc(texto: str):
    res = []
    for p in _dividir(texto, ','):
        p = _quitar_anotaciones(p)
        p = re.sub(r'\b(final|ref|out|in|params|this|scoped|readonly)\s+', '', p)
        p = _dividir(p, '=')[0] if '=' in p else p
        m = re.match(r'(.+?)\s*(\.\.\.)?\s+([^\W\d][\w$]*)$', p.strip())
        if m:
            res.append({'nombre': m.group(3), 'tipo': _normalizar_tipo(m.group(1) + ('[]' if m.group(2) else ''))})
    return res


def _params_ts(texto: str):
    res, props = [], []
    for p in _dividir(texto, ','):
        p = _quitar_anotaciones(p)
        mods, p = _modificadores(p, _MODIF_TS)
        if '=' in p:
            p = _dividir(p, '=')[0]
        m = re.match(r'(\.\.\.)?([\w$]+)\s*\??\s*(?::\s*(.+))?$', p.strip())
        if m:
            tipo = (m.group(3) or 'any') + ('[]' if m.group(1) and not (m.group(3) or '').endswith(']') else '')
            res.append({'nombre': m.group(2), 'tipo': _normalizar_tipo(tipo)})
            if mods:  # propiedad declarada en el constructor: constructor(private repo: Repo)
                props.append({'nombre': m.group(2), 'tipo': _normalizar_tipo(m.group(3) or 'any'),
                              'visibilidad': _visibilidad(mods, 'public')})
        elif p.strip():
            res.append({'nombre': 'args', 'tipo': _normalizar_tipo(p.split(':', 1)[1] if ':' in p else 'any')})
    return res, props


def _tipo_de_valor(v: str) -> str:
    v = (v or '').strip()
    if re.match(r'^["\'`]', v):
        return 'String'
    if re.match(r'^-?\d+$', v):
        return 'int'
    if re.match(r'^-?\d*\.\d+', v):
        return 'double'
    if v in ('true', 'false'):
        return 'boolean'
    if v.startswith('['):
        return 'List<Object>'
    m = re.match(r'new\s+([\w$.]+)(\s*<[^()]*>)?', v)
    return (m.group(1) + (m.group(2) or '')) if m else 'Object'


def _cabecera(resto: str, lang: str, tipo_decl: str):
    """Genericos, componentes de record, superclases e interfaces a partir de lo que sigue al nombre."""
    r = resto.strip()
    if r.startswith('<'):
        nivel = 0
        for i, c in enumerate(r):
            nivel += (c == '<') - (c == '>')
            if nivel == 0:
                r = r[i + 1:].strip()
                break
    componentes = ''
    if r.startswith('('):
        nivel = 0
        for i, c in enumerate(r):
            nivel += (c == '(') - (c == ')')
            if nivel == 0:
                componentes, r = r[1:i], r[i + 1:].strip()
                break
    sup, imp = [], []
    if lang == 'csharp':
        m = re.match(r':\s*(.*?)(?:\bwhere\b.*)?$', r, re.S)
        if m:
            bases = [_base_simple(b) for b in _dividir(m.group(1), ',')]
            for i, b in enumerate(bases):
                (imp if (i > 0 or re.match(r'I[A-Z]', b) or tipo_decl == 'interface') else sup).append(b)
    else:
        m = re.search(r'\bextends\s+(.*?)(?=\bimplements\b|$)', r, re.S)
        if m:
            sup = [_base_simple(b) for b in _dividir(m.group(1), ',')]
        m = re.search(r'\bimplements\s+(.*)$', r, re.S)
        if m:
            imp = [_base_simple(b) for b in _dividir(m.group(1), ',')]
        if tipo_decl == 'interface':
            imp, sup = sup + imp, []
    return componentes, [s for s in sup if s], [i for i in imp if i]


def _llamadas_c(cuerpo: str):
    llamadas = []
    for m in re.finditer(r'(?:\bthis\s*\.\s*)?([A-Za-z_$][\w$]*)\s*\??\.\s*([A-Za-z_$][\w$]*)\s*\(', cuerpo):
        llamadas.append({'objeto': m.group(1), 'metodo': m.group(2)})
    for m in re.finditer(r'(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(', cuerpo):
        if m.group(1) not in _NO_METODOS and not m.group(1)[0].isupper():
            llamadas.append({'objeto': 'this', 'metodo': m.group(1)})
    return llamadas


def _miembros_jc(cuerpo: str, nombre: str, lang: str, tipo_decl: str):
    atributos, metodos, literales = [], [], []
    decls = _declaraciones(_nivel_uno(cuerpo))
    if tipo_decl == 'enum':
        if decls:
            primero, term = decls[0]
            literales = [re.match(r'[^\W\d][\w$]*', x).group(0) for x in _dividir(_quitar_anotaciones(primero), ',')
                         if re.match(r'[^\W\d][\w$]*', x)]
            decls = decls[1:] if (lang == 'java' and term == ';') else []
    for u, term in decls:
        u = _quitar_anotaciones(u)
        mods, u = _modificadores(u, _MODIF_JC)
        if not u or _CABECERA.match(u) or re.match(r'(class|interface|enum|record|struct|delegate|event)\b', u):
            continue
        izq = u.split('=>')[0].strip() if '=>' in u else u
        pos_par, pos_igual = izq.find('('), izq.find('=')
        if pos_par >= 0 and (pos_igual < 0 or pos_par < pos_igual):
            m = re.match(r'(?:<[^()]*?>\s*)?(.*?)\s*\b([^\W\d][\w$]*)\s*\((.*)\)\s*(?:throws\b.*|where\b.*)?$', izq, re.S)
            if not m:
                continue
            ret, nom = m.group(1).strip(), m.group(2)
            if nom in _NO_METODOS or nom == 'this':
                continue
            if not ret:
                if nom != nombre:
                    continue  # llamada suelta o algo que no es declaracion
                continue  # constructor: no es un metodo del modelo
            metodos.append({'nombre': nom, 'retorno': _normalizar_tipo(ret), 'parametros': _params_jc(m.group(3)),
                            'visibilidad': _visibilidad(mods, 'public' if tipo_decl == 'interface' else 'package')})
            continue
        if lang == 'java' and term == '{}' and '(' not in izq:
            continue  # bloque de inicializacion o constructor compacto de record
        # campos (uno o varios declaradores) y propiedades de C#
        partes = _dividir(izq, ',')
        if not partes:
            continue
        primero = _dividir(partes[0], '=')[0] if '=' in partes[0] else partes[0]
        m = re.match(r'(.+?)\s+([^\W\d][\w$]*)$', primero.strip())
        if not m or m.group(2) in _MODIF_JC:
            continue
        tipo = m.group(1).strip()
        nombres = [m.group(2)] + [re.match(r'\s*([^\W\d][\w$]*)', p).group(1) for p in partes[1:] if re.match(r'\s*[^\W\d][\w$]*', p)]
        for n in nombres:
            atributos.append({'nombre': n, 'tipo': _normalizar_tipo(tipo), 'tipo_original': tipo,
                              'visibilidad': _visibilidad(mods, 'private' if lang == 'csharp' else 'package')})
    return atributos, metodos, literales


def _miembros_ts(cuerpo: str, tipo_decl: str):
    atributos, metodos, literales, vistos = [], [], [], set()
    decls = _declaraciones(_nivel_uno(cuerpo), por_linea=True)
    if tipo_decl == 'enum':
        texto = ' '.join(u for u, _ in decls)
        return [], [], [re.match(r'[\w$]+', x).group(0) for x in _dividir(texto, ',') if re.match(r'[\w$]+', x)]

    def agregar_attr(nombre, tipo, vis):
        if nombre not in vistos:
            vistos.add(nombre)
            atributos.append({'nombre': nombre, 'tipo': _normalizar_tipo(tipo), 'tipo_original': tipo, 'visibilidad': vis})
    for u, term in decls:
        u = _quitar_anotaciones(u)
        mods, u = _modificadores(u, _MODIF_TS)
        vis = _visibilidad(mods, 'public')
        if not u or u.startswith('[') or _CABECERA.match(u):
            continue
        m = re.match(r'constructor\s*\((.*)\)$', u, re.S)
        if m:
            for p in _params_ts(m.group(1))[1]:
                agregar_attr(p['nombre'], p['tipo'], p['visibilidad'])
            continue
        m = re.match(r'([#\w$]+)\s*[?!]?\s*(?::[^=]+)?=\s*(?:async\s+)?(?:\(([^()]*(?:\([^()]*\))*[^()]*)\)|([\w$]+))\s*(?::\s*[^=]+)?=>', u)
        if m:  # funcion flecha asignada a una propiedad: se toma como metodo
            metodos.append({'nombre': m.group(1).lstrip('#'), 'retorno': 'Object',
                            'parametros': _params_ts(m.group(2) or m.group(3) or '')[0], 'visibilidad': vis})
            continue
        m = re.match(r'(get|set)\s+([#\w$]+)\s*\((.*)\)\s*(?::\s*(.+))?$', u)
        if m:  # accesores: la propiedad es un atributo
            agregar_attr(m.group(2).lstrip('#'), m.group(4) or (m.group(3).split(':', 1)[1] if ':' in m.group(3) else 'any'), vis)
            continue
        m = re.match(r'([#\w$]+)\s*\??\s*(?:<[^()]*>)?\s*\((.*)\)\s*(?::\s*(.+))?$', u, re.S)
        if m and m.group(1) not in _NO_METODOS:
            metodos.append({'nombre': m.group(1).lstrip('#'), 'retorno': _normalizar_tipo(m.group(3) or 'void'),
                            'parametros': _params_ts(m.group(2))[0], 'visibilidad': vis})
            continue
        m = re.match(r'([#\w$]+)\s*[?!]?\s*(?::\s*([^=]+?))?\s*(?:=\s*(.*))?$', u, re.S)
        if m and m.group(1) not in _NO_METODOS:
            agregar_attr(m.group(1).lstrip('#'), m.group(2) or _tipo_de_valor(m.group(3)), vis)
    return atributos, metodos, literales


def _parse_c(code: str, ruta: str, lang: str) -> Dict[str, Any]:
    """Java, C# y TypeScript/JavaScript."""
    limpio = _limpiar_codigo(code, lang)
    m_pkg = re.search(r'\b(?:package|namespace)\s+([\w.]+)', limpio)
    paquete = m_pkg.group(1) if m_pkg else ''
    clases = {}
    for m in _CABECERA.finditer(limpio):
        tipo_decl, nombre = m.group(1), m.group(2)
        if tipo_decl == 'record' and lang == 'typescript':
            continue
        # la cabecera termina en la primera llave (o ';' en records de C# sin cuerpo) fuera de parentesis
        nivel, k = 0, m.end()
        while k < len(limpio):
            c = limpio[k]
            if c == '(':
                nivel += 1
            elif c == ')':
                nivel -= 1
            elif nivel == 0 and c in '{;':
                break
            k += 1
        if k >= len(limpio):
            continue
        componentes, superclases, interfaces = _cabecera(limpio[m.end():k], lang, tipo_decl)
        if limpio[k] == '{':
            fin = _cierre(limpio, k)
            cuerpo = limpio[k + 1:fin]
        else:
            cuerpo = ''
        previo = limpio[max(0, limpio.rfind('\n', 0, max(0, m.start() - 200))):m.start()]
        anotaciones = re.findall(r'@([\w$]+)', previo.split(';')[-1].split('}')[-1])
        if lang == 'typescript':
            atributos, metodos, literales = _miembros_ts(cuerpo, tipo_decl)
        else:
            atributos, metodos, literales = _miembros_jc(cuerpo, nombre, lang, tipo_decl)
        if componentes:  # record: sus componentes son atributos
            atributos = [{'nombre': p['nombre'], 'tipo': p['tipo'], 'tipo_original': p['tipo'], 'visibilidad': 'public'}
                         for p in _params_jc(componentes)] + atributos
        clases[nombre] = {'nombre': nombre, 'paquete': paquete, 'tipo_decl': tipo_decl, 'archivo': ruta, 'lenguaje': lang,
                          'anotaciones': anotaciones, 'superclases': superclases, 'interfaces': interfaces,
                          'atributos': atributos, 'metodos': metodos, 'literales': literales,
                          'llamadas': _llamadas_c(cuerpo)}
    return clases


def _texto_ast(nodo) -> str:
    if nodo is None:
        return ''
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value  # anotacion como texto: "Cliente"
    try:
        return ast.unparse(nodo)
    except Exception:
        return ''


def _nombre_ast(nodo) -> str:
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Attribute):
        return nodo.attr
    if isinstance(nodo, ast.Subscript):
        return _nombre_ast(nodo.value)
    if isinstance(nodo, ast.Call):
        return _nombre_ast(nodo.func)
    return ''


def _tipo_valor_ast(nodo) -> str:
    if isinstance(nodo, ast.Constant):
        return {str: 'str', int: 'int', float: 'float', bool: 'bool'}.get(type(nodo.value), 'Object')
    if isinstance(nodo, (ast.List, ast.ListComp)):
        return 'list'
    if isinstance(nodo, (ast.Dict, ast.DictComp)):
        return 'dict'
    if isinstance(nodo, (ast.Set, ast.SetComp)):
        return 'set'
    if isinstance(nodo, ast.Call) and _nombre_ast(nodo.func) not in ('field', 'Field'):
        return _nombre_ast(nodo.func) or 'Object'
    return 'Object'


def _es_self(nodo, nombre='self') -> bool:
    return isinstance(nodo, ast.Attribute) and isinstance(nodo.value, ast.Name) and nodo.value.id in ('self', 'cls')


def _parse_python(code: str, ruta: str) -> Dict[str, Any]:
    try:
        arbol = ast.parse(code)
    except (SyntaxError, ValueError):
        return {}
    clases = {}
    for nodo in arbol.body:
        if not isinstance(nodo, ast.ClassDef):
            continue
        bases = [b for b in (_nombre_ast(x) for x in nodo.bases) if b and b != 'object']
        es_enum = any(b in ('Enum', 'IntEnum', 'StrEnum', 'Flag', 'IntFlag') for b in bases)
        atributos, metodos, llamadas, literales, vistos = [], [], [], [], set()

        def agregar_attr(nombre, tipo):
            if nombre not in vistos:
                vistos.add(nombre)
                atributos.append({'nombre': nombre, 'tipo': _normalizar_tipo(tipo), 'tipo_original': tipo or '',
                                  'visibilidad': 'private' if nombre.startswith('_') else 'public'})
        for item in nodo.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                (literales.append(item.target.id) if es_enum else agregar_attr(item.target.id, _texto_ast(item.annotation)))
            elif isinstance(item, ast.Assign):
                for tg in item.targets:
                    if isinstance(tg, ast.Name) and not tg.id.startswith('__'):
                        (literales.append(tg.id) if es_enum else agregar_attr(tg.id, _tipo_valor_ast(item.value)))
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decoradores = [_nombre_ast(d) for d in item.decorator_list]
                if 'property' in decoradores or any(isinstance(d, ast.Attribute) and d.attr in ('setter', 'getter', 'deleter')
                                                    for d in item.decorator_list):
                    agregar_attr(item.name, _texto_ast(item.returns))
                    continue
                args = item.args.posonlyargs + item.args.args + item.args.kwonlyargs
                if args and 'staticmethod' not in decoradores and args[0].arg in ('self', 'cls'):
                    args = args[1:]
                anot = {a.arg: _texto_ast(a.annotation) for a in args}
                if not item.name.startswith('__'):
                    metodos.append({'nombre': item.name, 'retorno': _normalizar_tipo(_texto_ast(item.returns) or 'None'),
                                    'parametros': [{'nombre': a.arg, 'tipo': _normalizar_tipo(anot[a.arg])} for a in args],
                                    'visibilidad': 'private' if item.name.startswith('_') else 'public'})
                for sub in ast.walk(item):
                    if isinstance(sub, ast.AnnAssign) and _es_self(sub.target):
                        agregar_attr(sub.target.attr, _texto_ast(sub.annotation))
                    elif isinstance(sub, ast.Assign):
                        for tg in sub.targets:
                            for t in (tg.elts if isinstance(tg, ast.Tuple) else [tg]):
                                if _es_self(t):
                                    tipo = anot.get(sub.value.id, '') if isinstance(sub.value, ast.Name) else ''
                                    agregar_attr(t.attr, tipo or _tipo_valor_ast(sub.value))
                    elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                        v = sub.func.value
                        objeto = v.id if isinstance(v, ast.Name) else (v.attr if _es_self(v) else '')
                        if objeto:
                            llamadas.append({'objeto': 'this' if objeto in ('self', 'cls') else objeto, 'metodo': sub.func.attr})
        clases[nodo.name] = {'nombre': nodo.name, 'paquete': '', 'tipo_decl': 'enum' if es_enum else 'class', 'archivo': ruta,
                             'lenguaje': 'python', 'anotaciones': [_nombre_ast(d) for d in nodo.decorator_list],
                             'superclases': bases, 'interfaces': [], 'atributos': atributos, 'metodos': metodos,
                             'literales': literales, 'llamadas': llamadas}
    return clases


class CodeParser:
    """Parser multilingue de codigo fuente para extraer clases, miembros y llamadas."""

    @staticmethod
    def parse_archivo(ruta_archivo: str, lenguaje: str = 'auto') -> Dict[str, Any]:
        ext = os.path.splitext(ruta_archivo)[1].lower()
        if lenguaje == 'auto':
            lenguaje = _LENGUAJE_DE.get(ext)
            if not lenguaje:
                return {}
        with open(ruta_archivo, 'r', encoding='utf-8', errors='replace') as f:
            contenido = f.read()
        if lenguaje in ('java', 'csharp', 'typescript'):
            return _parse_c(contenido, ruta_archivo, lenguaje)
        if lenguaje == 'python':
            return _parse_python(contenido, ruta_archivo)
        return {}

    # compatibilidad con la API anterior
    @staticmethod
    def _parse_java_csharp(code: str, ruta: str, lang: str) -> Dict[str, Any]:
        return _parse_c(code, ruta, lang)

    @staticmethod
    def _parse_python(code: str, ruta: str) -> Dict[str, Any]:
        return _parse_python(code, ruta)

    @staticmethod
    def _parse_typescript(code: str, ruta: str) -> Dict[str, Any]:
        return _parse_c(code, ruta, 'typescript')


# ---------------------------------------------------------------------------
# Escaneo recursivo de directorios de codigo
# ---------------------------------------------------------------------------

def escanear_codigo(ruta: str, lenguaje: str = 'auto') -> Dict[str, Any]:
    """Escanea un archivo o directorio completo y devuelve el mapa de clases encontradas. Con un lenguaje
    concreto solo se leen los archivos de ese lenguaje."""
    ruta = os.path.abspath(os.path.expanduser(ruta))
    exts = tuple(_LENGUAJE_DE) if lenguaje == 'auto' else _EXTENSIONES.get(lenguaje, ())
    archivos = []
    if os.path.isfile(ruta):
        archivos = [ruta]
    elif os.path.isdir(ruta):
        for root, dirs, files in os.walk(ruta):
            dirs[:] = sorted(d for d in dirs if d not in _NO_ESCANEAR and not d.endswith('.egg-info'))
            for f in sorted(files):
                if f.lower().endswith(exts) and not f.endswith(('.min.js', '.d.ts')):
                    archivos.append(os.path.join(root, f))
    else:
        raise FileNotFoundError(f"La ruta de codigo no existe: {ruta}")
    resultado = {}
    for a in archivos:
        for nom, info in CodeParser.parse_archivo(a, lenguaje).items():
            resultado.setdefault(nom, info)  # si se repite el nombre, gana el primero encontrado
    return resultado


# ---------------------------------------------------------------------------
# Motor de comparacion: UML vs Codigo
# ---------------------------------------------------------------------------

def comparar_diagrama_con_codigo(doc, nombre_diagrama: str, ruta_codigo: str, lenguaje: str = 'auto') -> Dict[str, Any]:
    """Compara exhaustivamente el diagrama UML contra el codigo fuente."""
    uml_info = extraer_elementos_diagrama(doc, nombre_diagrama)
    codigo_clases = escanear_codigo(ruta_codigo, lenguaje)
    tipo_dg = uml_info.get('tipo_diagrama')
    if tipo_dg == 'UMLClassDiagram':
        return _comparar_clases_con_codigo(uml_info, codigo_clases)
    if tipo_dg == 'UMLSequenceDiagram':
        return _comparar_secuencia_con_codigo(uml_info, codigo_clases)
    return {'error': f'Tipo de diagrama no soportado para comparacion con codigo: {tipo_dg}', 'diagrama': nombre_diagrama}


def _comparar_clases_con_codigo(uml: Dict[str, Any], codigo: Dict[str, Any]) -> Dict[str, Any]:
    clases_uml = uml.get('clases', {})
    mapa_codigo = {}
    for k, v in codigo.items():
        mapa_codigo.setdefault(_normalizar_nombre(k), (k, v))
    coincidentes, faltantes, detalles, actores = [], [], {}, []
    total = exitos = 0.0

    for nom_uml, c_uml in clases_uml.items():
        if c_uml.get('tipo') == 'UMLActor':
            actores.append(nom_uml)  # los actores son externos al sistema: no se exigen en el codigo
            continue
        total += 10
        par = mapa_codigo.get(_normalizar_nombre(nom_uml))
        if not par:
            faltantes.append({'nombre': nom_uml, 'estereotipo': c_uml.get('estereotipo'), 'tipo': c_uml.get('tipo'),
                              'atributos_pendientes': [a['nombre'] for a in c_uml.get('atributos', [])],
                              'documentacion': c_uml.get('documentacion')})
            continue
        exitos += 10
        nom_cod, c_cod = par
        numeros = c_cod.get('lenguaje') == 'typescript'
        coincidentes.append({'uml': nom_uml, 'codigo': nom_cod, 'archivo': c_cod.get('archivo')})

        attrs_cod = {_normalizar_nombre(a['nombre']): a for a in c_cod.get('atributos', [])}
        attrs_ok, attrs_faltan, attrs_tipo = [], [], []
        usados = set()
        for a in c_uml.get('atributos', []):
            total += 3
            clave = _normalizar_nombre(a['nombre'])
            ac = attrs_cod.get(clave)
            if not ac:
                attrs_faltan.append(a['nombre'])
                continue
            usados.add(clave)
            if 'Object' not in (a['tipo'], ac['tipo']) and _clave_tipo(a['tipo'], numeros) != _clave_tipo(ac['tipo'], numeros):
                attrs_tipo.append({'atributo': a['nombre'], 'tipo_uml': a['tipo'], 'tipo_codigo': ac['tipo']})
                exitos += 1.5
            else:
                attrs_ok.append(a['nombre'])
                exitos += 3

        mets_cod = {_normalizar_nombre(m['nombre']) for m in c_cod.get('metodos', [])}
        mets_ok, mets_faltan = [], []
        for m in c_uml.get('metodos', []):
            total += 3
            if _normalizar_nombre(m['nombre']) in mets_cod:
                mets_ok.append(m['nombre'])
                exitos += 3
            else:
                mets_faltan.append(m['nombre'])
        mets_uml = {_normalizar_nombre(m['nombre']) for m in c_uml.get('metodos', [])}

        verificadas, faltan_asoc, mult_mal, usados_asoc = [], [], [], set()
        for asoc in c_uml.get('asociaciones', []):
            if asoc.get('origen') != nom_uml or not asoc.get('navegable'):
                continue
            destino, mult = asoc['destino'], asoc.get('mult_destino', '')
            if clases_uml.get(destino, {}).get('tipo') == 'UMLActor':
                continue  # hacia un actor (externo) no hay campo que exigir
            etiqueta = f"{nom_uml} -> {destino} ({mult})"
            total += 2
            clave_dest, rol = _normalizar_nombre(destino), _normalizar_nombre(asoc.get('rol_destino', ''))
            campo = next((a for k, a in attrs_cod.items() if k not in usados_asoc and clave_dest in _nombres_en_tipo(a['tipo'])), None) \
                or (attrs_cod.get(rol) if rol and rol not in usados_asoc else None)
            if not campo:
                faltan_asoc.append(etiqueta)
                continue
            usados_asoc.add(_normalizar_nombre(campo['nombre']))
            if _es_coleccion_mult(mult) == _es_coleccion_tipo(campo['tipo']):
                verificadas.append(etiqueta)
                exitos += 2
            else:
                mult_mal.append({'asociacion': etiqueta, 'campo': campo['nombre'], 'tipo_codigo': campo['tipo'],
                                 'esperado': 'coleccion' if _es_coleccion_mult(mult) else 'un solo objeto'})
                exitos += 1
        detalles[nom_uml] = {
            'archivo': c_cod.get('archivo'), 'estereotipo': c_uml.get('estereotipo'),
            'atributos': {'coincidentes': attrs_ok, 'faltan_en_codigo': attrs_faltan,
                          'sobran_en_codigo': [a['nombre'] for k, a in attrs_cod.items() if k not in usados and k not in usados_asoc],
                          'discrepancias_tipo': attrs_tipo},
            'metodos': {'coincidentes': mets_ok, 'faltan_en_codigo': mets_faltan,
                        'sobran_en_codigo': [m['nombre'] for m in c_cod.get('metodos', []) if _normalizar_nombre(m['nombre']) not in mets_uml]},
            'asociaciones': {'verificadas_en_codigo': verificadas, 'faltantes_en_codigo': faltan_asoc,
                             'multiplicidad_incorrecta': mult_mal}}

    claves_uml = {_normalizar_nombre(k) for k in clases_uml}
    sobrantes = [{'nombre': n, 'archivo': c.get('archivo')} for n, c in codigo.items() if _normalizar_nombre(n) not in claves_uml]
    return {
        'tipo_diagrama': 'UMLClassDiagram', 'diagrama': uml.get('nombre'),
        'porcentaje_sincronizacion': round(exitos / total * 100, 1) if total else 0.0,
        'resumen': {'total_clases_uml': len(clases_uml) - len(actores), 'clases_implementadas': len(coincidentes),
                    'clases_faltantes': len(faltantes), 'clases_extras_en_codigo': len(sobrantes)},
        'actores_omitidos': actores,
        'clases_coincidentes': coincidentes, 'clases_faltantes_en_codigo': faltantes,
        'clases_sobrantes_en_codigo': sobrantes, 'detalles_por_clase': detalles}


def _comparar_secuencia_con_codigo(uml: Dict[str, Any], codigo: Dict[str, Any]) -> Dict[str, Any]:
    mapa = {}
    for k, v in codigo.items():
        mapa.setdefault(_normalizar_nombre(k), (k, v))
    kind_de = {lf['tipo']: lf.get('estereotipo') for lf in uml.get('lifelines', [])}

    lifelines = []
    for lf in uml.get('lifelines', []):
        if lf.get('estereotipo') == 'actor':
            lifelines.append({'tipo_uml': lf['tipo'], 'estereotipo': 'actor', 'aplica': False})
            continue
        par = mapa.get(_normalizar_nombre(lf['tipo']))
        lifelines.append({'tipo_uml': lf['tipo'], 'estereotipo': lf.get('estereotipo'), 'aplica': True,
                          'en_codigo': bool(par), **({'archivo': par[1].get('archivo')} if par else {})})

    mensajes, aplicables, verificados, flujo_total, flujo_ok = [], 0, 0, 0, 0
    for m in uml.get('mensajes', []):
        de, a, nom = m.get('de'), m.get('a'), m.get('nombre', '')
        es_reply = bool(m.get('reply'))
        kinds = (m.get('tipos') or '->').split('->')
        k_de, k_a = kind_de.get(de, kinds[0]), kind_de.get(a, kinds[-1])
        info = {'n': m.get('n'), 'mensaje': nom, 'de': de, 'a': a, 'reply': es_reply, 'clase_destino': a}
        if es_reply or k_a == 'actor':
            info.update({'aplica': False, 'motivo': 'respuesta' if es_reply else 'el destino es un actor',
                         'metodo_implementado_en_destino': None})
            mensajes.append(info)
            continue
        aplicables += 1
        metodo = _normalizar_nombre(_nombre_metodo(nom))
        par = mapa.get(_normalizar_nombre(a))
        existe = bool(par) and metodo in {_normalizar_nombre(x['nombre']) for x in par[1].get('metodos', [])}
        info.update({'aplica': True, 'metodo_implementado_en_destino': existe})
        if not par:
            info['nota'] = f'Clase receptora "{a}" no encontrada en codigo'
        verificados += existe
        # flujo: la clase que envia el mensaje debe invocar ese metodo en algun punto
        origen = mapa.get(_normalizar_nombre(de)) if k_de != 'actor' else None
        if origen:
            flujo_total += 1
            llama = metodo in {_normalizar_nombre(x['metodo']) for x in origen[1].get('llamadas', [])}
            flujo_ok += llama
            info['llamada_desde_origen'] = llama
        mensajes.append(info)

    return {
        'tipo_diagrama': 'UMLSequenceDiagram', 'diagrama': uml.get('nombre'),
        'porcentaje_sincronizacion': round(verificados / aplicables * 100, 1) if aplicables else 0.0,
        'porcentaje_flujo': round(flujo_ok / flujo_total * 100, 1) if flujo_total else None,
        'resumen': {'total_mensajes': len(mensajes), 'mensajes_que_aplican': aplicables,
                    'mensajes_no_aplican': len(mensajes) - aplicables, 'mensajes_verificados_en_codigo': verificados,
                    'mensajes_pendientes': aplicables - verificados, 'llamadas_verificadas_desde_origen': flujo_ok},
        'lifelines': lifelines, 'mensajes': mensajes}


# ---------------------------------------------------------------------------
# Generador de esqueletos de codigo (Diagrama -> Codigo)
# ---------------------------------------------------------------------------

_RESERVADAS = {
    'java': {'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char', 'class', 'const', 'continue',
             'default', 'do', 'double', 'else', 'enum', 'extends', 'final', 'finally', 'float', 'for', 'goto', 'if',
             'implements', 'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new', 'package', 'private',
             'protected', 'public', 'return', 'short', 'static', 'strictfp', 'super', 'switch', 'synchronized', 'this',
             'throw', 'throws', 'transient', 'try', 'void', 'volatile', 'while', 'true', 'false', 'null', 'var', 'record'},
    'python': set(keyword.kwlist) | {'self', 'cls'},
    'typescript': {'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger', 'default', 'delete', 'do', 'else',
                   'enum', 'export', 'extends', 'false', 'finally', 'for', 'function', 'if', 'import', 'in', 'instanceof',
                   'new', 'null', 'return', 'super', 'switch', 'this', 'throw', 'true', 'try', 'typeof', 'var', 'void',
                   'while', 'with', 'constructor', 'interface', 'let', 'package', 'private', 'protected', 'public', 'static',
                   'yield', 'any', 'number', 'string', 'boolean'},
}


def _identificador(nombre: str, estilo: str, lang: str) -> str:
    """'Orden de Compra' -> OrdenDeCompra (pascal) u ordenDeCompra (camel), sin acentos ni simbolos."""
    nombre = nombre or ''
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', nombre):  # ya es un identificador valido: se respeta (BC_Registro)
        res = nombre if estilo == 'pascal' else nombre[0].lower() + nombre[1:]
        return res + '_' if res in _RESERVADAS.get(lang, ()) else res
    partes = re.findall(r'[A-Za-z0-9]+', _sin_acentos(nombre))
    if not partes:
        return 'Elemento' if estilo == 'pascal' else 'elemento'
    if estilo == 'pascal':
        res = ''.join(p[0].upper() + p[1:] for p in partes)
    else:
        res = partes[0][0].lower() + partes[0][1:] + ''.join(p[0].upper() + p[1:] for p in partes[1:])
    if res[0].isdigit():
        res = '_' + res
    return res + '_' if res in _RESERVADAS.get(lang, ()) else res


def _partes_tipo(t: str):
    m = re.fullmatch(r'(List|Set|Map)<(.*)>', t)
    return (m.group(1), _dividir(m.group(2), ',')) if m else (None, [])


def _tipo_java(t: str, caja: bool = False) -> str:
    base, args = _partes_tipo(t)
    if base == 'Map' and len(args) == 2:
        return f'Map<{_tipo_java(args[0], True)}, {_tipo_java(args[1], True)}>'
    if base:
        return f'{base}<{_tipo_java(args[0], True)}>'
    primitivos = {'int': ('int', 'Integer'), 'double': ('double', 'Double'), 'boolean': ('boolean', 'Boolean')}
    if t in primitivos:
        return primitivos[t][1 if caja else 0]
    return {'String': 'String', 'Date': 'LocalDate', 'void': 'void', 'Object': 'Object'}.get(t) or _identificador(t, 'pascal', 'java')


def _tipo_python(t: str) -> str:
    base, args = _partes_tipo(t)
    if base == 'Map' and len(args) == 2:
        return f'Dict[{_tipo_python(args[0])}, {_tipo_python(args[1])}]'
    if base:
        return f'{base}[{_tipo_python(args[0])}]'
    return {'String': 'str', 'int': 'int', 'double': 'float', 'boolean': 'bool', 'Date': 'date', 'void': 'None',
            'Object': 'Any'}.get(t) or _identificador(t, 'pascal', 'python')


def _tipo_ts(t: str) -> str:
    base, args = _partes_tipo(t)
    if base == 'Map' and len(args) == 2:
        return f'Map<{_tipo_ts(args[0])}, {_tipo_ts(args[1])}>'
    if base == 'Set':
        return f'Set<{_tipo_ts(args[0])}>'
    if base == 'List':
        inner = _tipo_ts(args[0])
        return f'{inner}[]' if re.fullmatch(r'\w+', inner) else f'Array<{inner}>'
    return {'String': 'string', 'int': 'number', 'double': 'number', 'boolean': 'boolean', 'Date': 'Date', 'void': 'void',
            'Object': 'unknown'}.get(t) or _identificador(t, 'pascal', 'typescript')


def _clases_en_tipo(t: str, conocidas: set) -> List[str]:
    return [n for n in re.findall(r'[^\W\d][\w$]*', t) if n in conocidas]


def _campos_asociacion(c, lang, todas=None):
    """(nombre del campo, tipo normalizado) por cada asociacion navegable desde la clase, sin nombres repetidos.
    No se generan campos hacia actores (son externos) ni hacia clases que no estan en el diagrama."""
    res, usados = [], {_identificador(a['nombre'], 'camel', lang) for a in c.get('atributos', [])}
    for asoc in c.get('asociaciones', []):
        if asoc.get('origen') != c['nombre'] or not asoc.get('navegable'):
            continue
        dest = asoc['destino']
        if todas is not None and (dest not in todas or todas[dest].get('tipo') == 'UMLActor'):
            continue
        coleccion = _es_coleccion_mult(asoc.get('mult_destino', ''))
        if asoc.get('rol_destino'):
            nombre = _identificador(asoc['rol_destino'], 'camel', lang)
        else:
            base = re.sub(r'^(bc|ctrl|ent|cls)_', '', dest, flags=re.I)
            nombre = _identificador(base, 'camel', lang) + ('s' if coleccion else '')
        base, n = nombre, 2
        while nombre in usados:
            nombre, n = f'{base}{n}', n + 1
        usados.add(nombre)
        res.append((nombre, f'List<{dest}>' if coleccion else dest))
    return res


def _comentario_doc(texto: str, prefijo: str = ' * ') -> List[str]:
    return [prefijo + l for l in (texto or '').replace('*/', '* /').splitlines()]


def _metodos_con_interfaces(c, todas):
    """Metodos propios mas los de las interfaces que implementa (para que el esqueleto compile)."""
    metodos, nombres = list(c.get('metodos', [])), {m['nombre'] for m in c.get('metodos', [])}
    for i in c.get('interfaces', []):
        for m in todas.get(i, {}).get('metodos', []):
            if m['nombre'] not in nombres:
                metodos.append(m)
                nombres.add(m['nombre'])
    return metodos


def _generar_clase_java(c: Dict[str, Any], todas: Dict[str, Any] = None, paquete: str = 'modelo') -> str:
    todas = todas or {}
    nom = _identificador(c['nombre'], 'pascal', 'java')
    lineas = ([f'package {paquete};', ''] if paquete else []) + ['import java.util.*;', 'import java.time.LocalDate;', '']
    if c.get('documentacion'):
        lineas += ['/**'] + _comentario_doc(c['documentacion']) + [' */']
    if c.get('tipo') == 'UMLEnumeration':
        lits = [_identificador(l, 'pascal', 'java').upper() for l in c.get('literales', [])] or ['VALOR']
        return '\n'.join(lineas + [f'public enum {nom} {{', '    ' + ', '.join(lits) + ';', '}']) + '\n'
    supers = [s for s in c.get('superclases', []) if s in todas]
    ifaces = [i for i in c.get('interfaces', []) if i in todas]
    if c.get('tipo') == 'UMLInterface':
        cab = f'public interface {nom}' + (' extends ' + ', '.join(_identificador(i, 'pascal', 'java') for i in supers + ifaces) if supers + ifaces else '')
        lineas.append(cab + ' {')
        for m in c.get('metodos', []):
            params = ', '.join(f"{_tipo_java(p['tipo'])} {_identificador(p['nombre'], 'camel', 'java')}" for p in m.get('parametros', []))
            lineas.append(f"    {_tipo_java(m.get('retorno') or 'void')} {_identificador(m['nombre'], 'camel', 'java')}({params});")
        return '\n'.join(lineas + ['}']) + '\n'
    cab = f'public class {nom}'
    if supers:
        cab += f' extends {_identificador(supers[0], "pascal", "java")}'
    if ifaces:
        cab += ' implements ' + ', '.join(_identificador(i, 'pascal', 'java') for i in ifaces)
    lineas.append(cab + ' {')
    campos = [(_identificador(a['nombre'], 'camel', 'java'), a.get('tipo') or 'Object') for a in c.get('atributos', [])]
    asocs = _campos_asociacion(c, 'java', todas)
    for n, t in campos:
        lineas.append(f'    private {_tipo_java(t)} {n};')
    for n, t in asocs:
        jt = _tipo_java(t)
        lineas.append(f'    private {jt} {n}' + (' = new ArrayList<>();' if jt.startswith('List<') else ';'))
    lineas += ['', f'    public {nom}() {{}}', '']
    for n, t in campos + asocs:
        cap = n[0].upper() + n[1:]
        lineas.append(f'    public {_tipo_java(t)} get{cap}() {{ return this.{n}; }}')
        lineas.append(f'    public void set{cap}({_tipo_java(t)} {n}) {{ this.{n} = {n}; }}')
        lineas.append('')
    defecto = {'int': '0', 'double': '0.0', 'boolean': 'false'}
    for m in _metodos_con_interfaces(c, todas):
        ret = m.get('retorno') or 'void'
        params = ', '.join(f"{_tipo_java(p['tipo'])} {_identificador(p['nombre'], 'camel', 'java')}" for p in m.get('parametros', []))
        lineas.append(f"    public {_tipo_java(ret)} {_identificador(m['nombre'], 'camel', 'java')}({params}) {{")
        if ret != 'void':
            lineas.append(f"        return {defecto.get(ret, 'null')};")
        lineas += ['    }', '']
    return '\n'.join(lineas + ['}']) + '\n'


def _generar_clase_python(c: Dict[str, Any], todas: Dict[str, Any] = None) -> str:
    todas = todas or {}
    nom = _identificador(c['nombre'], 'pascal', 'python')
    lineas = ['from __future__ import annotations', '', 'from abc import ABC, abstractmethod',
              'from dataclasses import dataclass, field', 'from datetime import date', 'from enum import Enum',
              'from typing import Any, Dict, List, Optional, Set', '']
    bases = [_identificador(s, 'pascal', 'python') for s in c.get('superclases', []) + c.get('interfaces', []) if s in todas]
    for b in bases:  # funciona como paquete (import relativo) o con los archivos sueltos
        lineas += ['try:', f'    from .{b} import {b}', 'except ImportError:', f'    from {b} import {b}']
    lineas.append('')
    doc = (c.get('documentacion') or '').replace('"""', "'''")
    if c.get('tipo') == 'UMLEnumeration':
        lineas.append(f'class {nom}(Enum):')
        if doc:
            lineas.append(f'    """{doc}"""')
        for l in c.get('literales', []) or ['VALOR']:
            ident = _identificador(l, 'pascal', 'python').upper()
            lineas.append(f"    {ident} = '{ident}'")
        return '\n'.join(lineas) + '\n'
    es_interfaz = c.get('tipo') == 'UMLInterface'
    if not es_interfaz:
        lineas.append('@dataclass')
    lineas.append(f"class {nom}({', '.join(bases or (['ABC'] if es_interfaz else []))}):" if (bases or es_interfaz) else f'class {nom}:')
    cuerpo = [f'    """{doc}"""'] if doc else []
    if not es_interfaz:
        for a in c.get('atributos', []):
            cuerpo.append(f"    {_identificador(a['nombre'], 'camel', 'python')}: Optional[{_tipo_python(a.get('tipo') or 'Object')}] = None")
        for n, t in _campos_asociacion(c, 'python', todas):
            if t.startswith('List<'):
                cuerpo.append(f'    {n}: {_tipo_python(t)} = field(default_factory=list)')
            else:
                cuerpo.append(f'    {n}: Optional[{_tipo_python(t)}] = None')
    for m in (c.get('metodos', []) if es_interfaz else _metodos_con_interfaces(c, todas)):
        params = ''.join(f", {_identificador(p['nombre'], 'camel', 'python')}: {_tipo_python(p['tipo'])}" for p in m.get('parametros', []))
        cuerpo += [''] + (['    @abstractmethod'] if es_interfaz else [])
        cuerpo.append(f"    def {_identificador(m['nombre'], 'camel', 'python')}(self{params}) -> {_tipo_python(m.get('retorno') or 'void')}:")
        cuerpo.append('        raise NotImplementedError')
    return '\n'.join(lineas + (cuerpo or ['    pass'])) + '\n'


def _generar_clase_typescript(c: Dict[str, Any], todas: Dict[str, Any] = None) -> str:
    todas = todas or {}
    nom = _identificador(c['nombre'], 'pascal', 'typescript')
    conocidas = {_identificador(n, 'pascal', 'typescript') for n in todas}
    tipos = [a.get('tipo') or 'Object' for a in c.get('atributos', [])] + [t for _, t in _campos_asociacion(c, 'typescript', todas)]
    for m in _metodos_con_interfaces(c, todas):
        tipos += [m.get('retorno') or 'void'] + [p['tipo'] for p in m.get('parametros', [])]
    supers = [s for s in c.get('superclases', []) if s in todas]
    ifaces = [i for i in c.get('interfaces', []) if i in todas]
    usadas = set()
    for t in tipos:
        usadas.update(_clases_en_tipo(_tipo_ts(t), conocidas))
    usadas.update(_identificador(s, 'pascal', 'typescript') for s in supers + ifaces)
    usadas.discard(nom)
    lineas = [f"import {{ {u} }} from './{u}';" for u in sorted(usadas)] + ([''] if usadas else [])
    if c.get('documentacion'):
        lineas += ['/**'] + _comentario_doc(c['documentacion']) + [' */']
    if c.get('tipo') == 'UMLEnumeration':
        lits = [_identificador(l, 'pascal', 'typescript').upper() for l in c.get('literales', [])] or ['VALOR']
        return '\n'.join(lineas + [f'export enum {nom} {{'] + [f"  {l} = '{l}'," for l in lits] + ['}']) + '\n'
    if c.get('tipo') == 'UMLInterface':
        cab = f'export interface {nom}' + (' extends ' + ', '.join(_identificador(i, 'pascal', 'typescript') for i in supers + ifaces) if supers + ifaces else '')
        lineas.append(cab + ' {')
        for a in c.get('atributos', []):
            lineas.append(f"  {_identificador(a['nombre'], 'camel', 'typescript')}?: {_tipo_ts(a.get('tipo') or 'Object')};")
        for m in c.get('metodos', []):
            params = ', '.join(f"{_identificador(p['nombre'], 'camel', 'typescript')}: {_tipo_ts(p['tipo'])}" for p in m.get('parametros', []))
            lineas.append(f"  {_identificador(m['nombre'], 'camel', 'typescript')}({params}): {_tipo_ts(m.get('retorno') or 'void')};")
        return '\n'.join(lineas + ['}']) + '\n'
    cab = f'export class {nom}'
    if supers:
        cab += f' extends {_identificador(supers[0], "pascal", "typescript")}'
    if ifaces:
        cab += ' implements ' + ', '.join(_identificador(i, 'pascal', 'typescript') for i in ifaces)
    lineas.append(cab + ' {')
    for a in c.get('atributos', []):
        lineas.append(f"  public {_identificador(a['nombre'], 'camel', 'typescript')}?: {_tipo_ts(a.get('tipo') or 'Object')};")
    for n, t in _campos_asociacion(c, 'typescript', todas):
        lineas.append(f'  public {n}: {_tipo_ts(t)} = [];' if t.startswith('List<') else f'  public {n}?: {_tipo_ts(t)};')
    lineas += ['', f'  constructor(init?: Partial<{nom}>) {{'] + (['    super();'] if supers else []) + \
              ['    Object.assign(this, init);', '  }']
    for m in _metodos_con_interfaces(c, todas):
        ret = _tipo_ts(m.get('retorno') or 'void')
        params = ', '.join(f"{_identificador(p['nombre'], 'camel', 'typescript')}: {_tipo_ts(p['tipo'])}" for p in m.get('parametros', []))
        lineas += ['', f"  public {_identificador(m['nombre'], 'camel', 'typescript')}({params}): {ret} {{",
                   "    throw new Error('No implementado');", '  }']
    return '\n'.join(lineas + ['}']) + '\n'


_EXT_GEN = {'java': '.java', 'python': '.py', 'typescript': '.ts'}


def generar_codigo_desde_diagrama(doc, nombre_diagrama: str, lenguaje: str = 'java', carpeta_salida: str = None,
                                  sobrescribir: bool = False, paquete: str = 'modelo') -> Dict[str, Any]:
    """Genera archivos de codigo fuente limpios a partir de las clases de un diagrama. Sin carpeta_salida el codigo
    se devuelve en la respuesta."""
    uml = extraer_elementos_diagrama(doc, nombre_diagrama)
    if uml.get('tipo_diagrama') != 'UMLClassDiagram':
        raise ValueError('Solo se puede generar codigo a partir de diagramas de clases')
    if lenguaje not in _EXT_GEN:
        raise ValueError(f"Lenguaje no soportado: {lenguaje}")
    clases = uml.get('clases', {})
    archivos_generados = {}
    escritos, omitidos_existentes, omitidos_nombre = [], [], []
    carpeta = os.path.abspath(os.path.expanduser(carpeta_salida)) if carpeta_salida else None
    for nom, c in clases.items():
        if c.get('tipo') == 'UMLActor':
            continue  # los actores son externos al sistema
        if lenguaje == 'java':
            codigo = _generar_clase_java(c, clases, paquete)
        elif lenguaje == 'python':
            codigo = _generar_clase_python(c, clases)
        else:
            codigo = _generar_clase_typescript(c, clases)
        nom_archivo = _identificador(nom, 'pascal', lenguaje) + _EXT_GEN[lenguaje]
        if nom_archivo in archivos_generados:  # dos clases que dan el mismo identificador
            omitidos_nombre.append(nom)
            continue
        archivos_generados[nom_archivo] = codigo
        if carpeta:
            ruta_dest = os.path.join(carpeta, nom_archivo)
            # el nombre sale del modelo: no puede escaparse de la carpeta
            if os.path.dirname(os.path.abspath(ruta_dest)) != carpeta:
                omitidos_nombre.append(nom)
                continue
            if os.path.exists(ruta_dest) and not sobrescribir:
                omitidos_existentes.append(nom_archivo)
                continue
            os.makedirs(carpeta, exist_ok=True)
            with open(ruta_dest, 'w', encoding='utf-8', newline='\n') as f:
                f.write(codigo)
            escritos.append(nom_archivo)
    res = {'diagrama': nombre_diagrama, 'lenguaje': lenguaje, 'total_archivos': len(archivos_generados),
           'archivos': list(archivos_generados.keys()), 'guardado_en': carpeta_salida, 'escritos': escritos,
           'omitidos_por_existir': omitidos_existentes, 'omitidos_por_nombre_invalido': omitidos_nombre}
    if not carpeta:
        res['codigo'] = archivos_generados
    if omitidos_existentes:
        res['nota'] = 'Esos archivos ya existian y no se tocaron; usa sobrescribir=true para reemplazarlos.'
    return res


# ---------------------------------------------------------------------------
# Importador de codigo hacia .mdj (Codigo -> Diagrama)
# ---------------------------------------------------------------------------

def _tipo_para_uml(t: str) -> str:
    return '' if t in ('Object', '', None) else t


def importar_codigo_a_diagrama(doc, ruta_codigo: str, paquete_nombre: str, nombre_diagrama: str = None, lenguaje: str = 'auto',
                               modo: str = 'agregar', metodos: bool = True) -> Dict[str, Any]:
    """Importa clases (o interfaces), atributos con su tipo y metodos desde codigo hacia el modelo .mdj y, si se indica,
    las dibuja en un diagrama. modo='agregar' solo agrega lo que falte; 'sincronizar' deja exactamente lo del codigo."""
    import staruml_mdj as M
    if modo not in ('agregar', 'sincronizar'):
        raise ValueError(f'modo debe ser "agregar" o "sincronizar", no "{modo}"')
    clases_codigo = escanear_codigo(ruta_codigo, lenguaje)
    if not clases_codigo:
        raise ValueError(f"No se encontraron clases en {ruta_codigo}")
    pk = doc.find(paquete_nombre, types=('UMLPackage', 'UMLModel', 'UMLSubsystem'))
    tipos_modelo = ('UMLClass', 'UMLInterface', 'UMLEnumeration')
    creadas, actualizadas, ambiguas = [], [], []
    attrs_agregados, attrs_quitados, mets_agregados, mets_quitados, mets_omitidos = {}, {}, {}, {}, {}

    for nom, c_cod in clases_codigo.items():
        clave = _normalizar_nombre(nom)
        cands = [o for o in doc.ids.values() if o and o.get('_type') in tipos_modelo and _normalizar_nombre(o.get('name', '')) == clave]
        en_pk = [o for o in cands if doc.parent.get(o['_id']) == pk['_id']]
        if len(en_pk) == 1 or len(cands) == 1:
            destino = en_pk[0] if len(en_pk) == 1 else cands[0]
            actualizadas.append(nom)
        elif cands:
            ambiguas.append(nom)
            continue
        else:
            tipo = {'interface': 'UMLInterface', 'enum': 'UMLEnumeration'}.get(c_cod.get('tipo_decl'), 'UMLClass')
            destino = {'_type': tipo, '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': nom}
            if tipo == 'UMLEnumeration':
                destino['literals'] = [{'_type': 'UMLEnumerationLiteral', '_id': doc.new_id(), '_parent': M.ref(destino['_id']),
                                        'name': l} for l in c_cod.get('literales', [])]
            pk.setdefault('ownedElements', []).append(destino)
            doc.reindex()
            creadas.append(nom)
        kind = doc.kind(destino)
        if destino['_type'] == 'UMLEnumeration':
            continue

        # atributos (con su tipo). En boundary y control no van atributos.
        attrs = list({a['nombre']: a for a in c_cod.get('atributos', [])}.values())
        if attrs and kind not in ('boundary', 'control'):
            existentes = {_normalizar_nombre(a.get('name', '')): a for a in destino.get('attributes', [])}
            if modo == 'sincronizar':
                nombres = list(dict.fromkeys(existentes.get(_normalizar_nombre(a['nombre']), {}).get('name') or a['nombre'] for a in attrs))
                antes = {a.get('name') for a in destino.get('attributes', [])}
                quitados = M.set_atributos(doc, destino, nombres)
                if quitados:
                    attrs_quitados[nom] = quitados
                agregados = [n for n in nombres if n not in antes]
            else:
                agregados = M.agregar_atributos(doc, destino, [a['nombre'] for a in attrs if _normalizar_nombre(a['nombre']) not in existentes])
            por_clave = {_normalizar_nombre(a['nombre']): a for a in attrs}
            for a in destino.get('attributes', []):
                ac = por_clave.get(_normalizar_nombre(a.get('name', '')))
                # en 'agregar' solo se completa un tipo vacio; en 'sincronizar' manda el codigo
                if ac and _tipo_para_uml(ac['tipo']) and (modo == 'sincronizar' or not a.get('type')):
                    a['type'] = _tipo_para_uml(ac['tipo'])
            if agregados:
                attrs_agregados[nom] = agregados

        # metodos. En el analisis de robustez (boundary, control, entity) no se ponen metodos.
        if metodos and c_cod.get('metodos'):
            if kind in ('boundary', 'control', 'entity'):
                mets_omitidos[nom] = [m['nombre'] for m in c_cod['metodos']]
            else:
                ops = destino.setdefault('operations', [])
                por_clave = {_normalizar_nombre(o.get('name', '')): o for o in ops}
                codigo_claves = set()
                nuevos = []
                for m in c_cod['metodos']:
                    k = _normalizar_nombre(m['nombre'])
                    codigo_claves.add(k)
                    if k in por_clave:
                        continue
                    op = {'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': M.ref(destino['_id']), 'name': m['nombre']}
                    params = [{'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': M.ref(op['_id']), 'name': p['nombre'],
                               'type': _tipo_para_uml(p['tipo'])} for p in m.get('parametros', [])]
                    if m.get('retorno') not in ('void', None):
                        params.append({'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': M.ref(op['_id']),
                                       'type': _tipo_para_uml(m['retorno']), 'direction': 'return'})
                    if params:
                        op['parameters'] = params
                    if m.get('visibilidad') in ('private', 'protected'):
                        op['visibility'] = m['visibilidad']
                    ops.append(op)
                    nuevos.append(m['nombre'])
                if modo == 'sincronizar':
                    fuera = [o.get('name') for o in ops if _normalizar_nombre(o.get('name', '')) not in codigo_claves]
                    destino['operations'] = [o for o in ops if _normalizar_nombre(o.get('name', '')) in codigo_claves]
                    if fuera:
                        mets_quitados[nom] = fuera
                if not destino['operations']:
                    del destino['operations']
                if nuevos:
                    mets_agregados[nom] = nuevos

    vistas_creadas, sin_vista = [], []
    if nombre_diagrama:
        doc.reindex()
        dg = doc.diagram(nombre_diagrama)
        # se colocan debajo de todo lo que ya esta dibujado, en filas de 4, sin encimarse
        cajas = [v for v in dg.get('ownedViews', []) if isinstance(v.get('top'), (int, float)) and isinstance(v.get('height'), (int, float))]
        y = max((v['top'] + v['height'] for v in cajas), default=20) + 60
        x, alto_fila, col = 60, 0, 0
        for nom in creadas:
            el = next((o for o in doc.ids.values() if o and o.get('_type') in tipos_modelo and o.get('name') == nom
                       and doc.parent.get(o['_id']) == pk['_id']), None)
            if not el or el['_type'] == 'UMLEnumeration' or doc.views_of(el['_id'], dg):
                if el and el['_type'] == 'UMLEnumeration':
                    sin_vista.append(nom)
                continue
            v = M.vista_nueva(doc, dg, el, x, y)
            vistas_creadas.append({'clase': nom, 'vista': v['_id']})
            alto_fila = max(alto_fila, v['height'])
            col += 1
            x += max(v['width'], 180) + 60
            if col == 4:
                x, y, col, alto_fila = 60, y + alto_fila + 60, 0, 0

    return {
        'paquete': paquete_nombre, 'diagrama': nombre_diagrama, 'total_clases_codigo': len(clases_codigo),
        'clases_creadas': creadas, 'clases_actualizadas': actualizadas, 'clases_ambiguas': ambiguas, 'modo': modo,
        'atributos_agregados': attrs_agregados, 'atributos_quitados': attrs_quitados,
        'metodos_agregados': mets_agregados, 'metodos_quitados': mets_quitados,
        'metodos_omitidos_por_robustez': mets_omitidos, 'vistas_creadas': vistas_creadas,
        'enumeraciones_sin_vista': sin_vista}
