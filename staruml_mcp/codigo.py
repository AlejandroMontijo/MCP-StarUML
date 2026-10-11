# codigo.py
# Comparador de diagramas StarUML (.mdj) contra codigo fuente (Java, Python, TypeScript/JavaScript, C#)
# y generador bidireccional (diagrama <-> codigo).
#  - Python se analiza con el modulo ast de la biblioteca estandar.
#  - Java, C# y TypeScript se analizan sobre una copia del codigo sin comentarios y con el contenido de los
#    textos vaciado (un '//' dentro de una URL o una llave dentro de un texto ya no confunden al parser), y los
#    miembros se toman solo del primer nivel de llaves de cada clase (lo que hay dentro de los metodos no cuenta).

import ast
import collections
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
    'int': ('int', 'integer', 'long', 'short', 'byte', 'int8', 'int16', 'int32', 'int64', 'uint', 'uint8', 'uint16', 'uint32',
            'uint64', 'ulong', 'ushort', 'ubyte', 'rune', 'bigint', 'smallint', 'biginteger'),
    'double': ('float', 'double', 'number', 'decimal', 'bigdecimal', 'real', 'money', 'single', 'float32', 'float64'),
    'boolean': ('bool', 'boolean'),
    'Date': ('date', 'localdate', 'datetime', 'localdatetime', 'timestamp', 'fecha', 'instant', 'offsetdatetime',
             'zoneddatetime', 'datetimeoffset', 'dateonly'),
    'Time': ('time', 'localtime', 'timeonly', 'timespan', 'offsettime'),
    'void': ('void', 'none', 'null', 'undefined', 'unit'),
    'Object': ('object', 'any', 'unknown', 'var', 'dynamic'),
}
_ALIAS = {a: canon for canon, alias in _PRIMITIVOS.items() for a in alias}
# En la forma comun long cuenta como int, BigDecimal como double y LocalDateTime como Date. La forma precisa (para
# importar, generar y comparar) conserva el tamano y la precision: estos tipos no se juntan con los demas.
_RICOS = {
    'char': ('char',),
    'byte': ('byte', 'sbyte', 'int8'),
    'short': ('short', 'int16', 'smallint'),
    'long': ('long', 'int64', 'uint64', 'ulong', 'bigint'),
    'BigInteger': ('biginteger',),
    'float': ('float', 'single', 'float32'),
    'decimal': ('decimal', 'bigdecimal', 'money'),
    'DateTime': ('datetime', 'localdatetime', 'timestamp', 'instant', 'offsetdatetime', 'zoneddatetime', 'datetimeoffset'),
}
_ALIAS_RICO = dict(_ALIAS, **{a: canon for canon, alias in _RICOS.items() for a in alias})
# Clases envoltorio de Java (pueden ser null). En la forma precisa se conservan como estan escritas para que el Java
# generado las respete; al comparar cuentan como su primitivo (Long es long; en Kotlin y C# son el mismo tipo).
_CAJAS = {'Integer': 'int', 'Long': 'long', 'Short': 'short', 'Byte': 'byte', 'Character': 'char', 'Float': 'float',
          'Double': 'double', 'Boolean': 'boolean'}
# Lo que un lenguaje no distingue se compara como un solo tipo: en TypeScript todo numero es number (y la hora se
# escribe como string); en Python int no tiene tamano y float es de doble precision. Ninguno de los dos tiene char.
_IGUALES = {
    'typescript': dict(dict.fromkeys(('byte', 'short', 'int', 'long', 'BigInteger', 'float', 'double', 'decimal'), 'double'),
                       char='String', Time='String', DateTime='Date'),
    'python': dict(dict.fromkeys(('byte', 'short', 'long', 'BigInteger'), 'int'), float='double', char='String'),
}
_BASICOS = set(_PRIMITIVOS) | set(_RICOS) | {'List', 'Set', 'Map'}
_LISTAS = {'list', 'arraylist', 'linkedlist', 'collection', 'iterable', 'ienumerable', 'ilist', 'icollection', 'array',
           'sequence', 'readonlyarray', 'vector', 'readonlycollection', 'observablecollection', 'ireadonlylist',
           'ireadonlycollection', 'mutablelist', 'mutablecollection', 'arraydeque'}
_SETS = {'set', 'hashset', 'treeset', 'linkedhashset', 'iset', 'frozenset', 'sortedset', 'readonlyset', 'mutableset'}
_MAPAS = {'map', 'hashmap', 'treemap', 'linkedhashmap', 'dict', 'dictionary', 'idictionary', 'record', 'mapping',
          'sorteddictionary', 'readonlymap', 'ireadonlydictionary', 'mutablemap'}
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


def _normalizar_tipo(tipo, rico: bool = False) -> str:
    """Forma comun de un tipo en UML y en cualquier lenguaje: String, int, double, boolean, Date, Time, void, Object,
    List<X>, Set<X>, Map<K,V> o el nombre de la clase tal cual (con sus mayusculas). Con rico=True se conservan
    char, byte, short, long, BigInteger, float, decimal, DateTime y las clases envoltorio de Java (Long, Integer...),
    para importar, generar y comparar sin perder precision."""
    if not isinstance(tipo, str) or not tipo.strip():
        return 'Object'
    alias_de = _ALIAS_RICO if rico else _ALIAS
    sub = (lambda x: _normalizar_tipo(x, rico)) if rico else _normalizar_tipo
    # las referencias adelantadas de Python van entre comillas: List["Pedido"]
    t = re.sub(r'^(java\.lang\.|java\.util\.|typing\.|System\.Collections\.Generic\.|System\.)', '', tipo.strip().replace('"', '').replace("'", ''))
    t = re.sub(r'^(final|const|readonly)\s+', '', t)
    if t.endswith('?') or t.endswith('!'):
        t = t[:-1].strip()
    alternativas = [p for p in _dividir(t, '|') if p not in ('None', 'null', 'undefined')]
    if len(alternativas) == 1:
        t = alternativas[0]
    # sintaxis de Go (los tipos de un programa en Go quedan asi en el modelo): *T, []T, [N]T, map[K]V, time.Time
    if t.startswith('*'):
        return sub(t.lstrip('*'))
    m = re.match(r'\[[\w.]*\]\s*(\S.*)$', t, re.S)
    if m:
        return f'List<{sub(m.group(1))}>'
    if t.startswith('map['):
        k = _cerrar_par(t, 3, '[', ']')
        if k < len(t) - 1:
            return f'Map<{sub(t[4:k])},{sub(t[k + 1:])}>'
    if t == 'time.Time':
        return alias_de['datetime']
    if t.endswith('[]'):
        return f'List<{sub(t[:-2])}>'
    m = re.fullmatch(r'([\w.$]+)\s*[<\[]\s*(.+?)\s*[>\]]', t, re.S)
    if m:
        base, args = m.group(1).split('.')[-1], _dividir(m.group(2), ',')
        b = base.lower()
        if b in _OPCIONALES and len(args) == 1:
            return sub(args[0])
        if b in _LISTAS and len(args) == 1:
            return f'List<{sub(args[0])}>'
        if b in _SETS and len(args) == 1:
            return f'Set<{sub(args[0])}>'
        if b in _MAPAS and len(args) == 2:
            return f'Map<{sub(args[0])},{sub(args[1])}>'
        return f'{base}<{",".join(sub(a) for a in args)}>'
    if t.endswith('[]'):
        return f'List<{sub(t[:-2])}>'
    if t.endswith('...'):
        return f'List<{sub(t[:-3])}>'
    if rico and t.split('.')[-1] in _CAJAS:
        return t.split('.')[-1]
    b = t.split('.')[-1].lower()
    if b in alias_de:
        return alias_de[b]
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


def _clave_exacta(nombre: str) -> str:
    """Clave sin quitar prefijos: 'BC_Cliente' -> 'bccliente', 'Orden de Entrega' -> 'ordendeentrega'."""
    return re.sub(r'[\s_\-]+', '', _sin_acentos(nombre or '')).lower()


def _emparejar(nombres_uml, nombres_codigo) -> Dict[str, str]:
    """{nombre del modelo: nombre en el codigo}. Primero la coincidencia exacta (sin acentos, espacios ni mayusculas);
    el nombre sin prefijo de estereotipo (BC_, ctrl_...) solo se usa cuando no hay otra, asi BC_Cliente no se confunde
    con Cliente. Cada clase del codigo se empareja una sola vez."""
    res, usados = {}, set()
    for clave in (_clave_exacta, _normalizar_nombre):
        libres = {}
        for k in nombres_codigo:
            if k not in usados:
                libres.setdefault(clave(k), []).append(k)
        for n in nombres_uml:
            if n in res:
                continue
            cands = [k for k in libres.get(clave(n), []) if k not in usados]
            if cands:
                res[n] = cands[0]
                usados.add(cands[0])
    return res


def _tipo_preciso(tipo, lenguaje: str = '', fechas: bool = True) -> str:
    """Forma precisa de un tipo vista desde un lenguaje: int no es long, double no es BigDecimal ni float, char no es
    String; Long cuenta como long (las clases envoltorio son su primitivo) y lo que el lenguaje no distingue se junta
    (_IGUALES: number de TypeScript, int y float de Python). Con fechas=False, Date y DateTime se juntan."""
    iguales = _IGUALES.get(lenguaje, {})

    def palabra(m):
        w = _CAJAS.get(m.group(0), m.group(0))
        if w == 'DateTime' and not fechas:
            w = 'Date'
        return iguales.get(w, w)
    return re.sub(r'[^\W\d][\w$]*', palabra, _normalizar_tipo(tipo, True))


def _clave_tipo(tipo: str, lenguaje: str = '') -> str:
    """Clave para comparar el tipo del modelo con el del codigo: la forma precisa en ese lenguaje (las fechas en su
    forma comun) con los nombres de clase normalizados (acentos, mayusculas)."""
    return re.sub(r'[^\W\d][\w$]*', lambda m: m.group(0) if m.group(0) in _BASICOS else _normalizar_nombre(m.group(0)),
                  _tipo_preciso(tipo, lenguaje, fechas=False))


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
        # en el orden de las vistas (no de un set): la respuesta sale igual cada vez
        ids_en_diagrama = list(dict.fromkeys(v['model']['$ref'] for v in dg.get('ownedViews', [])
                                             if isinstance(v.get('model'), dict) and '$ref' in v['model']))
        for cid in ids_en_diagrama:
            el = doc.ids.get(cid)
            if not el or el.get('_type') not in ('UMLClass', 'UMLInterface', 'UMLActor', 'UMLEnumeration'):
                continue
            attrs = []
            for a in el.get('attributes', []):
                t = _tipo_uml(doc, a.get('type'))
                if _es_coleccion_mult(a.get('multiplicity', '')) and t:
                    t = f'List<{t}>'
                # 'tipo' es la forma comun (para comparar); 'tipo_gen' conserva long, BigDecimal, LocalDateTime... (para generar)
                attrs.append({'nombre': a.get('name', ''), 'tipo': _normalizar_tipo(t), 'tipo_gen': _normalizar_tipo(t, True),
                              'visibilidad': a.get('visibility', 'public')})
            metodos = []
            for op in el.get('operations', []):
                params, ret, ret_gen = [], 'void', 'void'
                for p in op.get('parameters', []):
                    t = _tipo_uml(doc, p.get('type'))
                    if p.get('direction') == 'return':
                        ret, ret_gen = _normalizar_tipo(t), _normalizar_tipo(t, True)
                    else:
                        params.append({'nombre': p.get('name', ''), 'tipo': _normalizar_tipo(t), 'tipo_gen': _normalizar_tipo(t, True)})
                metodos.append({'nombre': op.get('name', ''), 'retorno': ret, 'retorno_gen': ret_gen, 'parametros': params,
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
        from . import mdj as M
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
                'csharp': ('.cs',), 'kotlin': ('.kt', '.kts'), 'go': ('.go',)}
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
            if lang in ('java', 'kotlin') and code.startswith('"""', i):
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
            res.append({'nombre': m.group(3), 'tipo': _normalizar_tipo(m.group(1) + ('[]' if m.group(2) else '')),
                        'tipo_original': m.group(1).strip() + ('...' if m.group(2) else '')})
    return res


def _params_ts(texto: str):
    res, props = [], []
    for p in _dividir(texto, ','):
        p = _quitar_anotaciones(p)
        mods, p = _modificadores(p, _MODIF_TS)
        if '=' in p:
            p = _dividir(p, '=')[0]
        m = re.match(r'(\.\.\.)?([\w$]+)\s*(\?)?\s*(?::\s*(.+))?$', p.strip())
        if m:
            tipo = (m.group(4) or 'any') + ('[]' if m.group(1) and not (m.group(4) or '').endswith(']') else '')
            res.append({'nombre': m.group(2), 'tipo': _normalizar_tipo(tipo), 'tipo_original': tipo.strip()})
            if mods:  # propiedad declarada en el constructor: constructor(private repo: Repo)
                props.append({'nombre': m.group(2), 'tipo': _normalizar_tipo(m.group(4) or 'any'),
                              'tipo_original': (m.group(4) or '').strip(), 'opcional': bool(m.group(3)),
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
    """Genericos, componentes de record, superclases, interfaces y {nombre simple: nombre calificado} de las bases
    escritas con su paquete, a partir de lo que sigue al nombre."""
    calificadas = {}

    def _base(b):
        simple = _base_simple(b)
        t = re.sub(r'<.*>', '', b).strip()
        if '.' in t:
            calificadas[simple] = t
        return simple
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
            bases = [_base(b) for b in _dividir(m.group(1), ',')]
            for i, b in enumerate(bases):
                (imp if (i > 0 or re.match(r'I[A-Z]', b) or tipo_decl == 'interface') else sup).append(b)
    else:
        r = re.split(r'\bpermits\b', r)[0]  # sealed: las subclases permitidas no son bases
        m = re.search(r'\bextends\s+(.*?)(?=\bimplements\b|$)', r, re.S)
        if m:
            sup = [_base(b) for b in _dividir(m.group(1), ',')]
        m = re.search(r'\bimplements\s+(.*)$', r, re.S)
        if m:
            imp = [_base(b) for b in _dividir(m.group(1), ',')]
        if tipo_decl == 'interface':
            imp, sup = sup + imp, []
    return componentes, [s for s in sup if s], [i for i in imp if i], calificadas


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
            abstracto = 'abstract' in mods or (tipo_decl == 'interface' and term == ';' and not {'default', 'static'} & set(mods))
            parametros = _params_jc(m.group(3))
            if 'partial' in mods and any((x['nombre'], len(x['parametros'])) == (nom, len(parametros)) for x in metodos):
                continue  # metodo partial de C#: la declaracion y su implementacion son el mismo metodo
            metodos.append({'nombre': nom, 'retorno': _normalizar_tipo(ret), 'retorno_original': ret,
                            'parametros': parametros,
                            'visibilidad': _visibilidad(mods, 'public' if tipo_decl == 'interface' else 'package'),
                            'estatico': 'static' in mods, 'abstracto': abstracto})
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
                              'visibilidad': _visibilidad(mods, 'private' if lang == 'csharp' else 'package'),
                              'estatico': 'static' in mods or 'const' in mods, 'final': bool({'final', 'readonly', 'const'} & set(mods))})
    return atributos, metodos, literales


def _miembros_ts(cuerpo: str, tipo_decl: str):
    atributos, metodos, literales, vistos = [], [], [], set()
    decls = _declaraciones(_nivel_uno(cuerpo), por_linea=True)
    if tipo_decl == 'enum':
        texto = ' '.join(u for u, _ in decls)
        return [], [], [re.match(r'[\w$]+', x).group(0) for x in _dividir(texto, ',') if re.match(r'[\w$]+', x)]

    def agregar_attr(nombre, tipo, vis, opcional=False, original=None):
        if nombre not in vistos:
            vistos.add(nombre)
            atributos.append({'nombre': nombre, 'tipo': _normalizar_tipo(tipo), 'visibilidad': vis,
                              'tipo_original': tipo if original is None else original, 'opcional': opcional})
    for u, term in decls:
        u = _quitar_anotaciones(u)
        mods, u = _modificadores(u, _MODIF_TS)
        vis = 'private' if u.startswith('#') else _visibilidad(mods, 'public')  # #campo es privado en JavaScript
        if not u or u.startswith('[') or _CABECERA.match(u):
            continue
        m = re.match(r'constructor\s*\((.*)\)$', u, re.S)
        if m:
            for p in _params_ts(m.group(1))[1]:
                agregar_attr(p['nombre'], p['tipo'], p['visibilidad'], p['opcional'], p['tipo_original'])
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
                            'retorno_original': (m.group(3) or '').strip(), 'parametros': _params_ts(m.group(2))[0],
                            'visibilidad': vis})
            continue
        m = re.match(r'([#\w$]+)\s*([?!])?\s*(?::\s*([^=]+?))?\s*(?:=\s*(.*))?$', u, re.S)
        if m and m.group(1) not in _NO_METODOS:  # nombre?: Tipo es opcional (0..1)
            agregar_attr(m.group(1).lstrip('#'), m.group(3) or _tipo_de_valor(m.group(4)), vis, m.group(2) == '?')
    return atributos, metodos, literales


def _espacios(limpio: str, lang: str):
    """[(inicio, fin, nombre)] de los package/namespace del archivo. Un namespace con llaves cubre su bloque (puede haber
    varios en un archivo, y anidados); 'package x;' y el namespace de archivo de C# ('namespace X;') cubren el resto."""
    if lang == 'java':
        m = re.search(r'^\s*package\s+([\w.]+)\s*;', limpio, re.M)
        return [(0, len(limpio), m.group(1))] if m else []
    patron = r'\bnamespace\s+([\w.]+)\s*([{;])' if lang == 'csharp' else r'(?<![\w.$])(?:namespace|module)\s+([\w.]+)\s*(\{)'
    res = []
    for m in re.finditer(patron, limpio):
        res.append((m.start(), len(limpio) if m.group(2) == ';' else _cierre(limpio, m.end() - 1), m.group(1)))
    return res


def _espacio_en(espacios, pos: int) -> str:
    return '.'.join(n for i, f, n in sorted(espacios) if i <= pos <= f)


def _anidadas(entradas):
    """Clave de cada clase dentro de su archivo: la anidada lleva delante sus clases externas (Arbol.Nodo), asi dos
    clases anidadas con el mismo nombre en clases distintas no se pisan. entradas: [(inicio, ini_cuerpo, fin_cuerpo,
    nombre)]. Devuelve [(clave, externa)] en el mismo orden."""
    res = []
    for inicio, _, _, nombre in entradas:
        externas = sorted((e for e in entradas if e[1] is not None and e[1] < inicio < e[2]), key=lambda e: e[1])
        externa = '.'.join(e[3] for e in externas)
        res.append(((externa + '.' if externa else '') + nombre, externa))
    return res


def _en_codigo(limpio: str, pos: int, palabra: str) -> bool:
    """La palabra que empieza en pos es codigo (no esta dentro de un comentario ni de un texto)."""
    return limpio[pos:pos + len(palabra)] == palabra


def _imports_c(code: str, limpio: str, lang: str):
    """Imports del archivo: {'tipo': 'clase', 'ruta', 'nombre', 'alias'}, {'tipo': 'paquete', 'ruta'} (comodin o
    using de C#) o {'tipo': 'modulo', 'ruta', 'alias'} (import * as m de TS, alias de namespace de C#)."""
    res = []
    if lang == 'java':
        for m in re.finditer(r'^\s*import\s+(static\s+)?([\w.]+?)(\.\*)?\s*;', limpio, re.M):
            if not m.group(1):
                ruta = m.group(2)
                res.append({'tipo': 'paquete', 'ruta': ruta} if m.group(3) else
                           {'tipo': 'clase', 'ruta': ruta, 'nombre': ruta.split('.')[-1], 'alias': ruta.split('.')[-1]})
    elif lang == 'csharp':
        for m in re.finditer(r'^\s*(?:global\s+)?using\s+(static\s+)?(?:(\w+)\s*=\s*)?([\w.]+)\s*;', limpio, re.M):
            if m.group(1):
                continue
            if m.group(2):  # using Alias = Espacio.Clase; (o un espacio de nombres)
                res.append({'tipo': 'clase', 'ruta': m.group(3), 'nombre': m.group(3).split('.')[-1], 'alias': m.group(2)})
                res.append({'tipo': 'modulo', 'ruta': m.group(3), 'alias': m.group(2)})
            else:
                res.append({'tipo': 'paquete', 'ruta': m.group(3)})
    else:  # TypeScript/JavaScript: la ruta va en un texto, asi que se lee del codigo original
        for m in re.finditer(r'\bimport\s+(?:type\s+)?(?:([\w$]+)\s*,?\s*)?(?:\{([^}]*)\}|\*\s*as\s+([\w$]+))?\s*from\s*'
                             r'[\'"]([^\'"]+)[\'"]', code):
            if not _en_codigo(limpio, m.start(), 'import'):
                continue
            desde = m.group(4)
            if m.group(1):
                res.append({'tipo': 'clase', 'ruta': desde, 'nombre': m.group(1), 'alias': m.group(1)})
            for parte in (m.group(2) or '').split(','):
                mm = re.match(r'\s*(?:type\s+)?([\w$]+)(?:\s+as\s+([\w$]+))?\s*$', parte)
                if mm:
                    res.append({'tipo': 'clase', 'ruta': desde, 'nombre': mm.group(1), 'alias': mm.group(2) or mm.group(1)})
            if m.group(3):
                res.append({'tipo': 'modulo', 'ruta': desde, 'alias': m.group(3)})
        for m in re.finditer(r'\b(?:const|let|var)\s+(?:\{([^}]*)\}|([\w$]+))\s*=\s*require\(\s*[\'"]([^\'"]+)[\'"]\s*\)', code):
            if not _en_codigo(limpio, m.start(), m.group(0).split()[0]):
                continue
            for parte in (m.group(1) or '').split(','):
                mm = re.match(r'\s*([\w$]+)(?:\s*:\s*([\w$]+))?\s*$', parte)
                if mm:
                    res.append({'tipo': 'clase', 'ruta': m.group(3), 'nombre': mm.group(1), 'alias': mm.group(2) or mm.group(1)})
            if m.group(2):
                res.append({'tipo': 'clase', 'ruta': m.group(3), 'nombre': m.group(2), 'alias': m.group(2)})
                res.append({'tipo': 'modulo', 'ruta': m.group(3), 'alias': m.group(2)})
    return res


def _campos_this(cuerpo: str):
    """Campos que el constructor crea con this.x = ... (la forma normal de declararlos en JavaScript), con el tipo del
    parametro que se les asigna o el del valor."""
    res = []
    for mc in re.finditer(r'\bconstructor\s*\(', cuerpo):
        if cuerpo[:mc.start()].count('{') != cuerpo[:mc.start()].count('}'):
            continue  # no es el constructor de esta clase
        p = mc.end() - 1
        q = _cerrar_par(cuerpo, p)
        ll = q + 1 + len(cuerpo[q + 1:]) - len(cuerpo[q + 1:].lstrip())
        if cuerpo[ll:ll + 1] != '{':
            continue  # firma sin cuerpo (sobrecarga de TypeScript): el que crea los campos es el que tiene cuerpo
        tipos = {x['nombre']: x.get('tipo_original') or x['tipo'] for x in _params_ts(cuerpo[p + 1:q])[0]}
        for ma in re.finditer(r'\bthis\s*\.\s*(#?)([A-Za-z_$][\w$]*)\s*=(?![=>])\s*([^;\n]*)', cuerpo[ll:_cierre(cuerpo, ll) + 1]):
            valor = ma.group(3).strip()
            # el tipo del parametro que se asigna; si no, el del literal (true, 0, 'x', [], new Date()); otra cosa es Object
            tipo = tipos.get(valor) or _tipo_de_valor(valor)
            if ma.group(2) not in [r['nombre'] for r in res]:
                res.append({'nombre': ma.group(2), 'tipo': _normalizar_tipo(tipo), 'tipo_original': tipo,
                            'visibilidad': 'private' if ma.group(1) else 'public'})
        break
    return res


def _parse_c(code: str, ruta: str, lang: str) -> Dict[str, Any]:
    """Java, C# y TypeScript/JavaScript. Las clases se devuelven por su clave en el archivo (Arbol.Nodo para una
    anidada), con 'nombre' (simple), 'externa' (la clase que la contiene) y el package/namespace que la encierra."""
    limpio = _limpiar_codigo(code, lang)
    espacios = _espacios(limpio, lang)
    imports = _imports_c(code, limpio, lang)
    entradas = []
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
        entradas.append((m, k, _cierre(limpio, k) if limpio[k] == '{' else None))
    claves = _anidadas([(m.start(), k if fin is not None else None, fin, m.group(2)) for m, k, fin in entradas])
    clases = {}
    for (m, k, fin), (clave, externa) in zip(entradas, claves):
        tipo_decl, nombre = m.group(1), m.group(2)
        componentes, superclases, interfaces, calificadas = _cabecera(limpio[m.end():k], lang, tipo_decl)
        cuerpo = limpio[k + 1:fin] if fin is not None else ''
        previo = limpio[max(0, limpio.rfind('\n', 0, max(0, m.start() - 200))):m.start()]
        anotaciones = re.findall(r'@([\w$]+)', previo.split(';')[-1].split('}')[-1])
        modificadores = re.split(r'[;{}]', previo)[-1]
        abstracta = tipo_decl == 'class' and bool(re.search(r'\babstract\b', modificadores))
        if lang == 'typescript':
            atributos, metodos, literales = _miembros_ts(cuerpo, tipo_decl)
            if tipo_decl == 'class':  # JavaScript: los campos se crean en el constructor con this.x = ...
                vistos = {a['nombre'] for a in atributos}
                atributos += [a for a in _campos_this(cuerpo) if a['nombre'] not in vistos]
        else:
            atributos, metodos, literales = _miembros_jc(cuerpo, nombre, lang, tipo_decl)
        if componentes:  # record: sus componentes son atributos
            atributos = [{'nombre': p['nombre'], 'tipo': p['tipo'], 'tipo_original': p['tipo_original'], 'visibilidad': 'public'}
                         for p in _params_jc(componentes)] + atributos
        info = {'nombre': nombre, 'paquete': _espacio_en(espacios, m.start()), 'externa': externa, 'tipo_decl': tipo_decl,
                'archivo': ruta, 'lenguaje': lang, 'abstracta': abstracta,
                'parcial': lang == 'csharp' and bool(re.search(r'\bpartial\b', modificadores)),
                'anotaciones': anotaciones, 'superclases': superclases, 'interfaces': interfaces,
                'bases_calificadas': calificadas, 'atributos': atributos, 'metodos': metodos, 'literales': literales,
                'llamadas': _llamadas_c(cuerpo), 'imports': list(imports)}
        # la clave lleva el namespace: en C# un archivo puede tener varios con clases que se llaman igual
        _agregar_clase(clases, f'{info["paquete"]}.{clave}' if info['paquete'] else clave, info)
    return clases


def _juntar_partes(previa: Dict[str, Any], info: Dict[str, Any]) -> None:
    """Junta en previa otra parte de la misma clase (partial class de C# en varios archivos o bloques)."""
    nombres = {a['nombre'] for a in previa['atributos']}
    previa['atributos'] += [a for a in info['atributos'] if a['nombre'] not in nombres]
    firmas = {(m['nombre'], len(m.get('parametros', []))) for m in previa['metodos']}
    previa['metodos'] += [m for m in info['metodos'] if (m['nombre'], len(m.get('parametros', []))) not in firmas]
    previa['llamadas'] += info.get('llamadas', [])
    for k in ('superclases', 'interfaces', 'anotaciones', 'imports'):
        previa[k] = previa.get(k, []) + [x for x in info.get(k, []) if x not in previa.get(k, [])]
    previa['abstracta'] = previa.get('abstracta') or info.get('abstracta')
    archivos = previa.setdefault('archivos', [previa['archivo']])
    if info['archivo'] not in archivos:
        archivos.append(info['archivo'])


def _misma_parcial(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return bool(a.get('parcial') and b.get('parcial') and a.get('paquete') == b.get('paquete')
                and a.get('externa') == b.get('externa'))


def _agregar_clase(clases: Dict[str, Any], clave: str, info: Dict[str, Any]) -> None:
    """Agrega la clase con su clave. Las partes de una partial class se juntan; si la clave se repite por otra
    razon se conserva la primera y se anota donde mas aparece (nunca se pierde en silencio)."""
    previa = clases.get(clave)
    if previa is None:
        clases[clave] = info
    elif _misma_parcial(previa, info):
        _juntar_partes(previa, info)
    else:
        previa.setdefault('repetida_en', []).append(info['archivo'])


# --- Kotlin ---

_MODIF_KT = {'public', 'private', 'protected', 'internal', 'open', 'final', 'abstract', 'sealed', 'data', 'enum', 'annotation',
             'inner', 'value', 'inline', 'override', 'lateinit', 'const', 'suspend', 'operator', 'infix', 'tailrec',
             'external', 'expect', 'actual', 'vararg', 'noinline', 'crossinline', 'companion'}
_CABECERA_KT = re.compile(r'(?<!::)\b(class|interface|object)\s+([^\W\d]\w*)')
_SIN_DECL_KT = re.compile(r'\bfun\s+(?:<[^()]*?>\s*)?(?:[\w.<>?]+\.)?[^\W\d]\w*\s*\(')  # declaraciones, no llamadas


def _cerrar_par(texto: str, i: int, abre: str = '(', cierra: str = ')') -> int:
    """Indice del cierre que corresponde a la apertura en i (o len(texto))."""
    nivel = 0
    for k in range(i, len(texto)):
        nivel += (texto[k] == abre) - (texto[k] == cierra)
        if nivel == 0:
            return k
    return len(texto)


def _tipo_valor_kt(v: str) -> str:
    v = (v or '').strip()
    m = re.match(r'(mutableListOf|listOf|arrayListOf|arrayOf|emptyList|mutableSetOf|setOf|hashSetOf|emptySet|'
                 r'mutableMapOf|mapOf|hashMapOf|emptyMap)\s*(?:<(.+)>)?\s*\(', v)
    if m:
        args = m.group(2) or ('Object,Object' if 'map' in m.group(1).lower() else 'Object')
        base = 'Map' if 'map' in m.group(1).lower() else 'Set' if 'set' in m.group(1).lower() else 'List'
        return f'{base}<{args}>'
    m = re.match(r'([A-Z][\w.]*)\s*(<[^()]*>)?\s*\(', v)
    if m:
        return m.group(1) + (m.group(2) or '')
    if re.match(r'^-?\d+[lL]?$', v):
        return 'int'
    if re.match(r'^-?\d*\.\d+[fF]?$', v):
        return 'double'
    return _tipo_de_valor(v)


def _params_kt(texto: str):
    """Parametros, propiedades del constructor primario (las que llevan val/var) y {parametro: tipo como esta escrito}."""
    params, props, originales = [], [], {}
    for p in _dividir(texto, ','):
        p = _quitar_anotaciones(p)
        mods, p = _modificadores(p, _MODIF_KT)
        es_prop = bool(re.match(r'(val|var)\s', p))
        p = re.sub(r'^(val|var)\s+', '', p)
        p = _dividir(p, '=')[0] if '=' in p else p
        m = re.match(r'([^\W\d]\w*)\s*:\s*(.+)$', p.strip())
        if not m:
            continue
        tipo = _normalizar_tipo(m.group(2))
        if 'vararg' in mods:
            tipo = f'List<{tipo}>'
        params.append({'nombre': m.group(1), 'tipo': tipo})
        originales[m.group(1)] = f'List<{m.group(2).strip()}>' if 'vararg' in mods else m.group(2).strip()
        if es_prop:
            props.append({'nombre': m.group(1), 'tipo': tipo, 'tipo_original': m.group(2).strip(),
                          'visibilidad': _visibilidad(mods, 'public')})
    return params, props, originales


def _fin_cabecera_kt(texto: str, i: int) -> int:
    """Donde termina la cabecera de una clase de Kotlin: su '{' o el fin de la declaracion (sin cuerpo)."""
    nivel = 0
    while i < len(texto):
        c = texto[i]
        if c in '(<':
            nivel += 1
        elif c in ')>':
            nivel = max(0, nivel - 1)
        elif nivel == 0 and c in '{};':
            return i
        elif nivel == 0 and c == '\n':
            antes, despues = texto[:i].rstrip(), texto[i + 1:].lstrip()
            if not antes.endswith((':', ',')) and not despues.startswith((':', ',', '{', 'where')):
                return i
        i += 1
    return i


def _parse_kotlin(code: str, ruta: str) -> Dict[str, Any]:
    limpio = _limpiar_codigo(code, 'kotlin')
    m_pkg = re.search(r'^\s*package\s+([\w.]+)', limpio, re.M)
    paquete = m_pkg.group(1) if m_pkg else ''
    imports = []
    for mi in re.finditer(r'^\s*import\s+([\w.]+?)(\.\*)?(?:\s+as\s+(\w+))?\s*$', limpio, re.M):
        ruta_i = mi.group(1)
        imports.append({'tipo': 'paquete', 'ruta': ruta_i} if mi.group(2) else
                       {'tipo': 'clase', 'ruta': ruta_i, 'nombre': ruta_i.split('.')[-1], 'alias': mi.group(3) or ruta_i.split('.')[-1]})
    entradas = []
    for m in _CABECERA_KT.finditer(limpio):
        palabra, nombre = m.group(1), m.group(2)
        linea = limpio[limpio.rfind('\n', 0, m.start()) + 1:m.start()]
        mods = set(re.findall(r'\b\w+\b', _quitar_anotaciones(linea)))
        if 'companion' in mods or nombre in _MODIF_KT:
            continue
        tipo_decl = 'enum' if 'enum' in mods else 'interface' if palabra == 'interface' else 'class'
        fin = _fin_cabecera_kt(limpio, m.end())
        cab = limpio[m.end():fin].strip()
        if cab.startswith('<'):
            cab = cab[_cerrar_par(cab, 0, '<', '>') + 1:].strip()
        cab = re.sub(r'^(?:@\w+(?:\([^()]*\))?\s*)*(?:(?:private|protected|internal|public)\s+)?constructor\b\s*', '', cab)
        props = []
        if cab.startswith('('):
            k = _cerrar_par(cab, 0)
            _, props, _ = _params_kt(cab[1:k])
            cab = cab[k + 1:].strip()
        superclases, interfaces = [], []
        if cab.startswith(':'):
            bases = re.split(r'\bwhere\b', cab[1:])[0]
            for b in _dividir(bases, ','):
                b = re.split(r'\bby\b', b)[0].strip()
                if not b:
                    continue
                (superclases if ('(' in b and tipo_decl != 'interface') else interfaces).append(_base_simple(b.split('(')[0]))
        con_cuerpo = fin < len(limpio) and limpio[fin] == '{'
        fin_cuerpo = _cierre(limpio, fin) if con_cuerpo else None
        cuerpo = limpio[fin + 1:fin_cuerpo] if con_cuerpo else ''
        atributos, metodos, literales = list(props), [], []
        decls = _declaraciones(_nivel_uno(cuerpo), por_linea=True)
        if tipo_decl == 'enum':
            while decls and not re.match(r'(?:@\w+\s*)*(?:\w+\s+)*(fun|val|var)\b', decls[0][0]):
                u, term = decls.pop(0)
                literales += [x.group(1) for x in (re.match(r'\s*([^\W\d]\w*)', e) for e in _dividir(u, ',')) if x]
                if term == ';':
                    break
        for u, _term in decls:
            u = _quitar_anotaciones(u)
            mods_m, u = _modificadores(u, _MODIF_KT)
            vis = _visibilidad(mods_m, 'public')
            mf = re.match(r'fun\s+(?:<[^()]*?>\s*)?(?:[\w.<>?, ]+\.)?([^\W\d]\w*)\s*\(', u)
            if mf:
                k = _cerrar_par(u, mf.end() - 1)
                parametros, _, originales = _params_kt(u[mf.end():k])
                resto = u[k + 1:].strip()
                mr = re.match(r':\s*([^=]+?)\s*(?:=.*)?$', resto)
                retorno = _normalizar_tipo(mr.group(1)) if mr else ('Object' if resto.startswith('=') else 'void')
                metodos.append({'nombre': mf.group(1), 'retorno': retorno, 'retorno_original': mr.group(1) if mr else '',
                                'parametros': parametros, 'tipos_originales': originales,
                                'visibilidad': 'public' if tipo_decl == 'interface' else vis})
                continue
            mv = re.match(r'(val|var)\s+(?:[\w.<>?]+\.)?([^\W\d]\w*)\s*(?::\s*(.+?))?\s*(?:(=|by\b)\s*(.*))?$', u)
            if mv:
                tipo_txt = mv.group(3)
                if tipo_txt:
                    tipo_txt = re.split(r'\s+get\b|\s+set\b', tipo_txt)[0]
                tipo = _normalizar_tipo(tipo_txt) if tipo_txt else (_normalizar_tipo(_tipo_valor_kt(mv.group(5))) if mv.group(4) == '=' else 'Object')
                atributos.append({'nombre': mv.group(2), 'tipo': tipo, 'tipo_original': tipo_txt or '', 'visibilidad': vis})
        previas = limpio[:m.start()].split('\n')[:-1]
        anotaciones = []
        while previas and re.fullmatch(r'\s*(@[\w.:]+(\([^()]*\))?\s*)+', previas[-1]):
            anotaciones = re.findall(r'@(?:\w+:)?([\w.]+)', previas.pop()) + anotaciones
        anotaciones += re.findall(r'@(?:\w+:)?([\w.]+)', linea)
        info = {'nombre': nombre, 'paquete': paquete, 'tipo_decl': tipo_decl, 'archivo': ruta, 'lenguaje': 'kotlin',
                'anotaciones': anotaciones, 'superclases': superclases, 'interfaces': interfaces,
                'atributos': atributos, 'metodos': metodos, 'literales': literales,
                'llamadas': [ll for ll in _llamadas_c(_SIN_DECL_KT.sub(' ', cuerpo)) if ll['metodo'] != 'constructor'],
                'imports': list(imports)}
        entradas.append((m.start(), fin if con_cuerpo else None, fin_cuerpo, nombre, info))
    clases = {}
    for (clave, externa), e in zip(_anidadas([x[:4] for x in entradas]), entradas):
        e[4]['externa'] = externa
        _agregar_clase(clases, clave, e[4])
    return clases


# --- Go ---

_SPEC_GO = re.compile(r'[\s;]*([^\W\d]\w*)(\[[^\]]*\])?\s*=?\s*')
_CUERPO_GO = re.compile(r'(struct|interface)\s*\{')


def _tipo_go(t: str) -> str:
    """Tipo de Go a la forma comun: []T y [N]T -> List<T>, map[K]V -> Map<K,V>, *T -> T, time.Time -> Date."""
    t = (t or '').strip()
    while t.startswith('*'):
        t = t[1:].strip()
    if t.startswith('...'):
        return f'List<{_tipo_go(t[3:])}>'
    m = re.match(r'\[[^\]]*\]\s*(.+)$', t)
    if m:
        return f'List<{_tipo_go(m.group(1))}>'
    if t.startswith('map['):
        k = _cerrar_par(t, 3, '[', ']')
        return f'Map<{_tipo_go(t[4:k])},{_tipo_go(t[k + 1:])}>'
    if t in ('interface{}', 'interface {}', 'any') or t.startswith(('chan ', 'func')):
        return 'Object'
    if t == 'time.Time':
        return 'Date'
    return _normalizar_tipo(t)


def _params_go(texto: str, originales=None):
    """a, b int, c string -> a:int, b:int, c:string (los nombres agrupados comparten el tipo). En originales (si se da)
    queda el tipo de cada parametro como esta escrito."""
    partes = [p.strip() for p in _dividir(texto, ',') if p.strip()]
    con_nombre = any(re.match(r'[^\W\d]\w*\s+\S', p) for p in partes)
    res, pendientes = [], []
    for p in partes:
        m = re.match(r'([^\W\d]\w*)\s+(.+)$', p)
        if con_nombre and m:
            for n in pendientes + [m.group(1)]:
                res.append({'nombre': n, 'tipo': _tipo_go(m.group(2))})
                if originales is not None:
                    originales[n] = m.group(2).strip()
            pendientes = []
        elif con_nombre:
            pendientes.append(p)
        else:
            res.append({'nombre': f'p{len(res)}', 'tipo': _tipo_go(p)})
    return res


def _retorno_go(texto: str) -> str:
    texto = texto.strip()
    if not texto:
        return 'void'
    if texto.startswith('('):
        tipos = [r['tipo'] for r in _params_go(texto[1:_cerrar_par(texto, 0)])]
    else:
        tipos = [_tipo_go(texto)]
    utiles = [t for t in tipos if t != 'error']
    return (utiles or tipos or ['void'])[0]


def _vis_go(nombre: str) -> str:
    return 'public' if nombre[:1].isupper() else 'package'


def _parse_go(code: str, ruta: str) -> Dict[str, Any]:
    limpio = _limpiar_codigo(code, 'go')
    limpio = re.sub(r'`[^`]*`', lambda x: ' ' * len(x.group(0)), limpio)  # etiquetas de campos y textos crudos
    m_pkg = re.search(r'^\s*package\s+(\w+)', limpio, re.M)
    paquete = m_pkg.group(1) if m_pkg else ''
    imports = []  # la ruta va en un texto: se lee del codigo original
    for m in re.finditer(r'\bimport\s*(?:\(([^)]*)\)|((?:[\w.]+\s+)?"[^"]+"))', code):
        if _en_codigo(limpio, m.start(), 'import'):
            for mi in re.finditer(r'(?:([\w.]+)\s+)?"([^"]+)"', m.group(1) or m.group(2)):
                imports.append({'tipo': 'modulo', 'ruta': mi.group(2), 'alias': mi.group(1) or mi.group(2).split('/')[-1]})
    nivel, prof = 0, []
    for c in limpio:
        prof.append(nivel)
        nivel += (c == '{') - (c == '}')

    def especificaciones(texto):
        """(nombre, subyacente, cuerpo) de cada tipo en 'Nombre [T any] subyacente'."""
        i, out = 0, []
        while i < len(texto):
            m = _SPEC_GO.match(texto, i)
            if not m:
                break
            j = m.end()
            ms = _CUERPO_GO.match(texto, j)
            if ms:
                k = _cierre(texto, ms.end() - 1)
                out.append((m.group(1), ms.group(1), texto[ms.end():k]))
                i = k + 1
            else:
                fin = texto.find('\n', j)
                fin = len(texto) if fin < 0 else fin
                out.append((m.group(1), texto[j:fin].strip(), None))
                i = fin + 1
        return out

    specs = []
    for m in re.finditer(r'\btype\b', limpio):
        if prof[m.start()] != 0:
            continue
        i = m.end()
        while i < len(limpio) and limpio[i] in ' \t':
            i += 1
        if limpio[i:i + 1] == '(':
            k = _cerrar_par(limpio, i)
            specs += especificaciones(limpio[i + 1:k])
        else:
            specs += especificaciones(limpio[i:])[:1]

    clases, basicos = {}, {}
    for nombre, sub, cuerpo in specs:
        if cuerpo is None:
            if re.fullmatch(r'u?int\d*|float\d+|string|byte|rune|bool', sub):
                basicos[nombre] = sub
            continue
        atributos, metodos, superclases, interfaces = [], [], [], []
        for linea in re.split(r'[\n;]', cuerpo):
            linea = linea.strip()
            if not linea:
                continue
            if sub == 'struct':
                mc = re.match(r'([^\W\d]\w*(?:\s*,\s*[^\W\d]\w*)*)\s+(\S.*)$', linea)
                if mc:
                    for n in re.split(r'\s*,\s*', mc.group(1)):
                        atributos.append({'nombre': n, 'tipo': _tipo_go(mc.group(2)), 'tipo_original': mc.group(2).strip(),
                                          'visibilidad': _vis_go(n)})
                elif re.fullmatch(r'\*?[\w.]+(\[.*\])?', linea):
                    superclases.append(_base_simple(linea.lstrip('*').split('[')[0]))  # campo embebido
            else:
                mm = re.match(r'([^\W\d]\w*)\s*\(', linea)
                if mm:
                    k = _cerrar_par(linea, mm.end() - 1)
                    metodos.append({'nombre': mm.group(1), 'retorno': _retorno_go(linea[k + 1:]),
                                    'parametros': _params_go(linea[mm.end():k]), 'visibilidad': 'public'})
                elif re.fullmatch(r'[\w.]+', linea):
                    interfaces.append(_base_simple(linea))  # interfaz embebida
        clases[nombre] = {'nombre': nombre, 'paquete': paquete, 'tipo_decl': 'interface' if sub == 'interface' else 'class',
                          'archivo': ruta, 'lenguaje': 'go', 'anotaciones': [], 'superclases': superclases,
                          'interfaces': interfaces, 'atributos': atributos, 'metodos': metodos, 'literales': [],
                          'llamadas': [], 'imports': list(imports)}

    # metodos con receptor: func (c *Cliente) Total(...) float64 { ... }
    for m in re.finditer(r'\bfunc\s*\(\s*(?:([^\W\d]\w*)\s+)?\*?\s*([^\W\d]\w*)(?:\[[^\]]*\])?\s*\)\s*([^\W\d]\w*)\s*(?:\[[^\]]*\])?\s*\(', limpio):
        if prof[m.start()] != 0 or m.group(2) not in clases:
            continue
        k = _cerrar_par(limpio, m.end() - 1)
        llave = limpio.find('{', k)
        if llave < 0:
            continue
        cuerpo = limpio[llave + 1:_cierre(limpio, llave)]
        c = clases[m.group(2)]
        originales = {}
        c['metodos'].append({'nombre': m.group(3), 'retorno': _retorno_go(limpio[k + 1:llave]),
                             'parametros': _params_go(limpio[m.end():k], originales), 'tipos_originales': originales,
                             'visibilidad': _vis_go(m.group(3))})
        receptor = m.group(1)
        for ll in _llamadas_c(cuerpo):
            c['llamadas'].append({'objeto': 'this' if ll['objeto'] == receptor else ll['objeto'], 'metodo': ll['metodo']})

    # enumeraciones: type Estado int + const ( Activo Estado = iota; Inactivo )
    literales = {}
    for m in re.finditer(r'\bconst\b', limpio):
        if prof[m.start()] != 0:
            continue
        i = m.end()
        while i < len(limpio) and limpio[i] in ' \t':
            i += 1
        if limpio[i:i + 1] == '(':
            lineas = limpio[i + 1:_cerrar_par(limpio, i)].split('\n')
        else:
            lineas = [limpio[i:limpio.find('\n', i) if limpio.find('\n', i) >= 0 else len(limpio)]]
        actual = None
        for linea in lineas:
            linea = linea.strip()
            mc = re.match(r'([^\W\d]\w*(?:\s*,\s*[^\W\d]\w*)*)\s*(?:([^\W\d][\w.]*)\s*)?(=.*)?$', linea)
            if not mc:
                continue
            if mc.group(2) or mc.group(3):
                actual = mc.group(2) if mc.group(2) in basicos else None
            if actual:
                literales.setdefault(actual, []).extend(n for n in re.split(r'\s*,\s*', mc.group(1)) if n != '_')
    for nombre, lits in literales.items():
        clases.setdefault(nombre, {'nombre': nombre, 'paquete': paquete, 'tipo_decl': 'enum', 'archivo': ruta, 'lenguaje': 'go',
                                   'anotaciones': [], 'superclases': [], 'interfaces': [], 'atributos': [], 'metodos': [],
                                   'literales': lits, 'llamadas': [], 'imports': list(imports)})
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
        # handler.ErrorHandler() conserva el modulo: con el se sabe de cual clase ErrorHandler se trata
        texto = _texto_ast(nodo.func) if isinstance(nodo.func, ast.Attribute) else ''
        if re.fullmatch(r'[\w.]+', texto) and texto.split('.')[-1][:1].isupper():
            return texto
        return _nombre_ast(nodo.func) or 'Object'
    return 'Object'


def _es_self(nodo, nombre='self') -> bool:
    return isinstance(nodo, ast.Attribute) and isinstance(nodo.value, ast.Name) and nodo.value.id in ('self', 'cls')


def _recorrer_sin_clases(nodo):
    """Como ast.walk (a lo ancho y en el mismo orden), sin entrar en las clases que se definen dentro: lo que hay en
    una clase local de un metodo (sus self.x) no es de la clase que se esta leyendo."""
    pendientes = collections.deque([nodo])
    while pendientes:
        actual = pendientes.popleft()
        pendientes.extend(h for h in ast.iter_child_nodes(actual) if not isinstance(h, ast.ClassDef))
        yield actual


def _parse_python(code: str, ruta: str) -> Dict[str, Any]:
    """Clases de un modulo de Python, tambien las anidadas (class A: class B: ...): van con su clave en el archivo
    (A.B), 'nombre' simple y 'externa' (la clase que la contiene), como en los demas lenguajes. Una clase que se define
    dentro de un metodo o de una funcion es local: no es parte del modelo."""
    try:
        arbol = ast.parse(code)
    except (SyntaxError, ValueError):
        return {}
    imports = []  # 'desde' guarda el modulo con los puntos de un import relativo (.modelos, ..comun)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            desde = '.' * (nodo.level or 0) + (nodo.module or '')
            for n in nodo.names:
                if n.name != '*':
                    imports.append({'tipo': 'clase', 'ruta': desde, 'nombre': n.name, 'alias': n.asname or n.name})
                else:
                    imports.append({'tipo': 'paquete', 'ruta': desde})
        elif isinstance(nodo, ast.Import):
            for n in nodo.names:
                imports.append({'tipo': 'modulo', 'ruta': n.name, 'alias': n.asname or n.name})
    clases = {}

    def leer_clase(nodo, externa):
        bases = [b for b in (_nombre_ast(x) for x in nodo.bases) if b and b != 'object']
        es_enum = any(b in ('Enum', 'IntEnum', 'StrEnum', 'Flag', 'IntFlag') for b in bases)
        atributos, metodos, llamadas, literales, vistos, anidadas = [], [], [], [], set(), []

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
            elif isinstance(item, ast.ClassDef):
                anidadas.append(item)
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
                                    'retorno_original': _texto_ast(item.returns),
                                    'parametros': [{'nombre': a.arg, 'tipo': _normalizar_tipo(anot[a.arg])} for a in args],
                                    'tipos_originales': {k: v for k, v in anot.items() if v},
                                    'visibilidad': 'private' if item.name.startswith('_') else 'public'})
                for sub in _recorrer_sin_clases(item):
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
        info = {'nombre': nodo.name, 'paquete': '', 'externa': externa, 'tipo_decl': 'enum' if es_enum else 'class',
                'archivo': ruta, 'lenguaje': 'python', 'anotaciones': [_nombre_ast(d) for d in nodo.decorator_list],
                'superclases': bases, 'interfaces': [], 'atributos': atributos, 'metodos': metodos,
                'literales': literales, 'llamadas': llamadas, 'imports': list(imports),
                'bases_calificadas': {t.split('.')[-1]: t for t in (_texto_ast(x.value if isinstance(x, ast.Subscript) else x)
                                                                     for x in nodo.bases) if '.' in t}}
        clave = f'{externa}.{nodo.name}' if externa else nodo.name
        _agregar_clase(clases, clave, info)
        for interna in anidadas:
            leer_clase(interna, clave)

    for nodo in arbol.body:
        if isinstance(nodo, ast.ClassDef):
            leer_clase(nodo, '')
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
        if lenguaje == 'kotlin':
            return _parse_kotlin(contenido, ruta_archivo)
        if lenguaje == 'go':
            return _parse_go(contenido, ruta_archivo)
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
                if f.lower().endswith(exts) and not f.endswith(('.min.js', '.d.ts', '_test.go')):
                    archivos.append(os.path.join(root, f))
    else:
        raise FileNotFoundError(f"La ruta de codigo no existe: {ruta}")
    resultado = {}
    for a in archivos:
        for info in CodeParser.parse_archivo(a, lenguaje).values():
            nom = info['nombre']
            previa = resultado.get(nom)
            if previa is None:
                resultado[nom] = info
            elif _misma_parcial(previa, info):  # partial class de C# repartida en varios archivos
                _juntar_partes(previa, info)
            elif previa.get('externa') and not info.get('externa'):
                # una clase de primer nivel gana sobre una anidada que se llama igual
                info['repetida_en'] = [previa['archivo']] + previa.get('repetida_en', []) + info.get('repetida_en', [])
                resultado[nom] = info
            else:  # se queda la primera y se anota donde mas aparece
                previa['repetida_en'] = previa.get('repetida_en', []) + [info['archivo']] + info.get('repetida_en', [])
    return resultado


def _repetidas(codigo: Dict[str, Any]) -> Dict[str, List[str]]:
    """{clase: [archivo que se uso, archivos donde tambien aparece]} de las que se llaman igual en el codigo."""
    return {n: [c.get('archivo')] + c['repetida_en'] for n, c in codigo.items() if c.get('repetida_en')}


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


def _ancestros_codigo(codigo: Dict[str, Any], nombre: str) -> set:
    """Claves (_clave_exacta) de todo lo que la clase del codigo hereda o implementa, tambien por medio de otras clases
    del codigo: si C extiende B y B extiende A, C hereda de A."""
    por_clave = {}
    for k in codigo:
        por_clave.setdefault(_clave_exacta(k), k)
    vistos, pila = set(), [nombre]
    while pila:
        c = codigo.get(pila.pop()) or {}
        for x in c.get('superclases', []) + c.get('interfaces', []):
            kx = _clave_exacta(x)
            if kx not in vistos:
                vistos.add(kx)
                if kx in por_clave:
                    pila.append(por_clave[kx])
    return vistos


def _comparar_clases_con_codigo(uml: Dict[str, Any], codigo: Dict[str, Any]) -> Dict[str, Any]:
    clases_uml = uml.get('clases', {})
    pares = _emparejar([n for n, c in clases_uml.items() if c.get('tipo') != 'UMLActor'], list(codigo))
    coincidentes, faltantes, detalles, actores = [], [], {}, []
    total = exitos = 0.0

    for nom_uml, c_uml in clases_uml.items():
        if c_uml.get('tipo') == 'UMLActor':
            actores.append(nom_uml)  # los actores son externos al sistema: no se exigen en el codigo
            continue
        total += 10
        if nom_uml not in pares:
            faltantes.append({'nombre': nom_uml, 'estereotipo': c_uml.get('estereotipo'), 'tipo': c_uml.get('tipo'),
                              'atributos_pendientes': [a['nombre'] for a in c_uml.get('atributos', [])],
                              'documentacion': c_uml.get('documentacion')})
            continue
        exitos += 10
        nom_cod = pares[nom_uml]
        c_cod = codigo[nom_cod]
        lang_cod = c_cod.get('lenguaje') or ''
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
            # con el tipo del codigo como esta escrito se compara la forma precisa (int contra long, double contra
            # BigDecimal); si el tipo se dedujo de un valor (val total = 0.0) solo se sabe su forma comun
            t_uml, t_cod = ((a.get('tipo_gen') or a['tipo'], ac['tipo_original']) if ac.get('tipo_original')
                            else (a['tipo'], ac['tipo']))
            if 'Object' not in (a['tipo'], ac['tipo']) and _clave_tipo(t_uml, lang_cod) != _clave_tipo(t_cod, lang_cod):
                attrs_tipo.append({'atributo': a['nombre'], 'tipo_uml': _normalizar_tipo(t_uml, True),
                                   'tipo_codigo': _normalizar_tipo(t_cod, True)})
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

        # herencia: cada generalizacion o realizacion del diagrama debe estar en el codigo (directa o por medio de otra
        # clase); y lo que el codigo hereda de otra clase del diagrama sin que el diagrama lo diga sobra
        esperadas = [b for b in dict.fromkeys(c_uml.get('superclases', []) + c_uml.get('interfaces', []))
                     if b in clases_uml and clases_uml[b].get('tipo') != 'UMLActor']
        ancestros = _ancestros_codigo(codigo, nom_cod)
        her_ok, her_falta = [], []
        for b in esperadas:
            total += 2
            if _clave_exacta(pares.get(b, b)) in ancestros:
                her_ok.append(b)
                exitos += 2
            else:
                her_falta.append(b)
        del_codigo = {v: k for k, v in pares.items()}
        her_sobra = [del_codigo[x] for x in dict.fromkeys(c_cod.get('superclases', []) + c_cod.get('interfaces', []))
                     if x in del_codigo and del_codigo[x] not in esperadas and del_codigo[x] != nom_uml]
        detalles[nom_uml] = {
            'archivo': c_cod.get('archivo'), 'estereotipo': c_uml.get('estereotipo'),
            'atributos': {'coincidentes': attrs_ok, 'faltan_en_codigo': attrs_faltan,
                          'sobran_en_codigo': [a['nombre'] for k, a in attrs_cod.items() if k not in usados and k not in usados_asoc],
                          'discrepancias_tipo': attrs_tipo},
            'metodos': {'coincidentes': mets_ok, 'faltan_en_codigo': mets_faltan,
                        'sobran_en_codigo': [m['nombre'] for m in c_cod.get('metodos', []) if _normalizar_nombre(m['nombre']) not in mets_uml]},
            'asociaciones': {'verificadas_en_codigo': verificadas, 'faltantes_en_codigo': faltan_asoc,
                             'multiplicidad_incorrecta': mult_mal},
            'herencia': {'coincidentes': her_ok, 'faltan_en_codigo': her_falta, 'sobran_en_codigo': her_sobra}}

    # lo que no se emparejo es extra, salvo lo que se llama como un actor (los actores no se exigen en el codigo)
    usados = set(pares.values())
    claves_actores = {f(a) for a in actores for f in (_clave_exacta, _normalizar_nombre)}
    sobrantes = [{'nombre': n, 'archivo': c.get('archivo')} for n, c in codigo.items()
                 if n not in usados and _clave_exacta(n) not in claves_actores and _normalizar_nombre(n) not in claves_actores]
    res = {
        'tipo_diagrama': 'UMLClassDiagram', 'diagrama': uml.get('nombre'),
        'porcentaje_sincronizacion': round(exitos / total * 100, 1) if total else 0.0,
        'resumen': {'total_clases_uml': len(clases_uml) - len(actores), 'clases_implementadas': len(coincidentes),
                    'clases_faltantes': len(faltantes), 'clases_extras_en_codigo': len(sobrantes)},
        'actores_omitidos': actores,
        'clases_coincidentes': coincidentes, 'clases_faltantes_en_codigo': faltantes,
        'clases_sobrantes_en_codigo': sobrantes, 'detalles_por_clase': detalles}
    if _repetidas(codigo):
        res['clases_repetidas_en_codigo'] = _repetidas(codigo)
    return res


def _comparar_secuencia_con_codigo(uml: Dict[str, Any], codigo: Dict[str, Any]) -> Dict[str, Any]:
    pares = _emparejar(list(dict.fromkeys(lf['tipo'] for lf in uml.get('lifelines', []) if lf.get('estereotipo') != 'actor')),
                       list(codigo))

    def par_de(nombre):  # nombre de la lifeline -> (nombre en el codigo, clase)
        return (pares[nombre], codigo[pares[nombre]]) if nombre in pares else None
    kind_de = {lf['tipo']: lf.get('estereotipo') for lf in uml.get('lifelines', [])}

    lifelines = []
    for lf in uml.get('lifelines', []):
        if lf.get('estereotipo') == 'actor':
            lifelines.append({'tipo_uml': lf['tipo'], 'estereotipo': 'actor', 'aplica': False})
            continue
        par = par_de(lf['tipo'])
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
        par = par_de(a)
        existe = bool(par) and metodo in {_normalizar_nombre(x['nombre']) for x in par[1].get('metodos', [])}
        info.update({'aplica': True, 'metodo_implementado_en_destino': existe})
        if not par:
            info['nota'] = f'Clase receptora "{a}" no encontrada en codigo'
        verificados += existe
        # flujo: la clase que envia el mensaje debe invocar ese metodo en algun punto
        origen = par_de(de) if k_de != 'actor' else None
        if origen:
            flujo_total += 1
            llama = metodo in {_normalizar_nombre(x['metodo']) for x in origen[1].get('llamadas', [])}
            flujo_ok += llama
            info['llamada_desde_origen'] = llama
        mensajes.append(info)

    res = {
        'tipo_diagrama': 'UMLSequenceDiagram', 'diagrama': uml.get('nombre'),
        'porcentaje_sincronizacion': round(verificados / aplicables * 100, 1) if aplicables else 0.0,
        'porcentaje_flujo': round(flujo_ok / flujo_total * 100, 1) if flujo_total else None,
        'resumen': {'total_mensajes': len(mensajes), 'mensajes_que_aplican': aplicables,
                    'mensajes_no_aplican': len(mensajes) - aplicables, 'mensajes_verificados_en_codigo': verificados,
                    'mensajes_pendientes': aplicables - verificados, 'llamadas_verificadas_desde_origen': flujo_ok},
        'lifelines': lifelines, 'mensajes': mensajes}
    if _repetidas(codigo):
        res['clases_repetidas_en_codigo'] = _repetidas(codigo)
    return res


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
    'csharp': {'abstract', 'as', 'base', 'bool', 'break', 'byte', 'case', 'catch', 'char', 'checked', 'class', 'const',
               'continue', 'decimal', 'default', 'delegate', 'do', 'double', 'else', 'enum', 'event', 'explicit', 'extern',
               'false', 'finally', 'fixed', 'float', 'for', 'foreach', 'goto', 'if', 'implicit', 'in', 'int', 'interface',
               'internal', 'is', 'lock', 'long', 'namespace', 'new', 'null', 'object', 'operator', 'out', 'override',
               'params', 'private', 'protected', 'public', 'readonly', 'ref', 'return', 'sbyte', 'sealed', 'short',
               'sizeof', 'stackalloc', 'static', 'string', 'struct', 'switch', 'this', 'throw', 'true', 'try', 'typeof',
               'uint', 'ulong', 'unchecked', 'unsafe', 'ushort', 'using', 'virtual', 'void', 'volatile', 'while'},
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


def _tg(x: Dict[str, Any], clave: str = 'tipo') -> str:
    """Tipo para generar: el que conserva la precision (tipo_gen, retorno_gen) o, si no viene, el normalizado."""
    return x.get(f'{clave}_gen') or x.get(clave) or ('void' if clave == 'retorno' else 'Object')


_IMPORTS_JAVA = {'BigDecimal': 'java.math.BigDecimal', 'BigInteger': 'java.math.BigInteger',
                 'LocalDateTime': 'java.time.LocalDateTime', 'LocalTime': 'java.time.LocalTime'}


def _tipo_java(t: str, caja: bool = False) -> str:
    base, args = _partes_tipo(t)
    if base == 'Map' and len(args) == 2:
        return f'Map<{_tipo_java(args[0], True)}, {_tipo_java(args[1], True)}>'
    if base:
        return f'{base}<{_tipo_java(args[0], True)}>'
    primitivos = {'int': ('int', 'Integer'), 'long': ('long', 'Long'), 'double': ('double', 'Double'),
                  'boolean': ('boolean', 'Boolean'), 'char': ('char', 'Character'), 'byte': ('byte', 'Byte'),
                  'short': ('short', 'Short'), 'float': ('float', 'Float')}
    if t in primitivos:
        return primitivos[t][1 if caja else 0]
    if t in _CAJAS:
        return t  # Long, Integer...: se respeta la clase envoltorio del modelo (puede ser null)
    return {'String': 'String', 'Date': 'LocalDate', 'DateTime': 'LocalDateTime', 'Time': 'LocalTime', 'decimal': 'BigDecimal',
            'BigInteger': 'BigInteger', 'void': 'void', 'Object': 'Object'}.get(t) or _identificador(t, 'pascal', 'java')


def _tipo_python(t: str) -> str:
    base, args = _partes_tipo(t)
    if base == 'Map' and len(args) == 2:
        return f'Dict[{_tipo_python(args[0])}, {_tipo_python(args[1])}]'
    if base:
        return f'{base}[{_tipo_python(args[0])}]'
    t = _CAJAS.get(t, t)
    return {'String': 'str', 'char': 'str', 'int': 'int', 'byte': 'int', 'short': 'int', 'long': 'int', 'BigInteger': 'int',
            'float': 'float', 'double': 'float', 'decimal': 'Decimal', 'boolean': 'bool', 'Date': 'date', 'DateTime': 'datetime',
            'Time': 'time', 'void': 'None', 'Object': 'Any'}.get(t) or _identificador(t, 'pascal', 'python')


def _tipo_ts(t: str) -> str:
    base, args = _partes_tipo(t)
    if base == 'Map' and len(args) == 2:
        return f'Map<{_tipo_ts(args[0])}, {_tipo_ts(args[1])}>'
    if base == 'Set':
        return f'Set<{_tipo_ts(args[0])}>'
    if base == 'List':
        inner = _tipo_ts(args[0])
        return f'{inner}[]' if re.fullmatch(r'\w+', inner) else f'Array<{inner}>'
    t = _CAJAS.get(t, t)
    return {'String': 'string', 'char': 'string', 'int': 'number', 'byte': 'number', 'short': 'number', 'long': 'number',
            'float': 'number', 'double': 'number', 'decimal': 'number', 'BigInteger': 'bigint', 'boolean': 'boolean', 'Date': 'Date',
            'DateTime': 'Date', 'Time': 'string', 'void': 'void', 'Object': 'unknown'}.get(t) or _identificador(t, 'pascal', 'typescript')


def _tipo_cs(t: str) -> str:
    base, args = _partes_tipo(t)
    if base == 'Map' and len(args) == 2:
        return f'Dictionary<{_tipo_cs(args[0])}, {_tipo_cs(args[1])}>'
    if base == 'Set':
        return f'HashSet<{_tipo_cs(args[0])}>'
    if base:
        return f'List<{_tipo_cs(args[0])}>'
    t = _CAJAS.get(t, t)
    return {'String': 'string', 'char': 'char', 'int': 'int', 'byte': 'byte', 'short': 'short', 'long': 'long',
            'float': 'float', 'double': 'double', 'decimal': 'decimal',
            'BigInteger': 'System.Numerics.BigInteger', 'boolean': 'bool', 'Date': 'DateOnly', 'DateTime': 'DateTime',
            'Time': 'TimeSpan', 'void': 'void', 'Object': 'object'}.get(t) or _identificador(t, 'pascal', 'csharp')


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


def _params_unicos(m: Dict[str, Any], lang: str):
    """[(identificador, tipo para generar)] de los parametros, sin nombres vacios ni repetidos (no compilarian)."""
    res, usados = [], ({'self'} if lang == 'python' else set())
    for i, p in enumerate(m.get('parametros', [])):
        n = _identificador(p.get('nombre') or f'p{i + 1}', 'camel', lang)
        base, k = n, 2
        while n in usados:
            n, k = f'{base}{k}', k + 1
        usados.add(n)
        res.append((n, _tg(p)))
    return res


def _metodos_unicos(metodos, lang, nombre_de, firma_de=None, ocupadas=(), campos=()):
    """[(identificador, metodo, parametros)] sin dos metodos con la misma firma, que no compilarian (firma_de da la
    parte de los parametros; sin ella cuenta solo el nombre). Se omite el metodo cuya (nombre, numero de parametros)
    ya esta en ocupadas (un get/set que ya sale del campo) y al que se llama como un campo (en C#, TypeScript y
    Python no pueden compartir nombre) se le agrega '_'."""
    res, vistas = [], set()
    for m in metodos:
        nom = nombre_de(m['nombre'])
        params = _params_unicos(m, lang)
        if (nom, len(params)) in ocupadas:
            continue
        if nom in campos:
            nom += '_'
        firma = (nom, firma_de(params) if firma_de else ())
        if firma in vistas:
            continue
        vistas.add(firma)
        res.append((nom, m, params))
    return res


def _generar_clase_java(c: Dict[str, Any], todas: Dict[str, Any] = None, paquete: str = 'modelo') -> str:
    todas = todas or {}
    nom = _identificador(c['nombre'], 'pascal', 'java')
    lineas = []
    if c.get('documentacion'):
        lineas += ['/**'] + _comentario_doc(c['documentacion']) + [' */']

    def firma(params):  # Java no admite dos metodos con los mismos parametros (sin contar los genericos)
        return tuple(re.sub(r'<.*>', '', _tipo_java(t)) for _, t in params)

    def nombre_metodo(n):
        return _identificador(n, 'camel', 'java')

    def con_params(params):
        return ', '.join(f'{_tipo_java(t)} {p}' for p, t in params)
    if c.get('tipo') == 'UMLEnumeration':
        lits = list(dict.fromkeys(_identificador(l, 'pascal', 'java').upper() for l in c.get('literales', []))) or ['VALOR']
        lineas += [f'public enum {nom} {{', '    ' + ', '.join(lits) + ';', '}']
    elif c.get('tipo') == 'UMLInterface':
        bases = [s for s in c.get('superclases', []) + c.get('interfaces', []) if s in todas]
        cab = f'public interface {nom}' + (' extends ' + ', '.join(_identificador(i, 'pascal', 'java') for i in bases) if bases else '')
        lineas.append(cab + ' {')
        for n, m, params in _metodos_unicos(c.get('metodos', []), 'java', nombre_metodo, firma):
            lineas.append(f"    {_tipo_java(_tg(m, 'retorno'))} {n}({con_params(params)});")
        lineas.append('}')
    else:
        supers = [s for s in c.get('superclases', []) if s in todas]
        ifaces = [i for i in c.get('interfaces', []) if i in todas]
        cab = f'public class {nom}'
        if supers:
            cab += f' extends {_identificador(supers[0], "pascal", "java")}'
        if ifaces:
            cab += ' implements ' + ', '.join(_identificador(i, 'pascal', 'java') for i in ifaces)
        lineas.append(cab + ' {')
        campos = []
        for a in c.get('atributos', []):
            n = _identificador(a['nombre'], 'camel', 'java')
            if n not in [x for x, _ in campos]:  # dos atributos con el mismo identificador no compilarian
                campos.append((n, _tg(a)))
        asocs = _campos_asociacion(c, 'java', todas)
        for n, t in campos:
            lineas.append(f'    private {_tipo_java(t)} {n};')
        for n, t in asocs:
            jt = _tipo_java(t)
            lineas.append(f'    private {jt} {n}' + (' = new ArrayList<>();' if jt.startswith('List<') else ';'))
        lineas += ['', f'    public {nom}() {{}}', '']
        accesores = set()
        for n, t in campos + asocs:
            cap = n[0].upper() + n[1:]
            lineas.append(f'    public {_tipo_java(t)} get{cap}() {{ return this.{n}; }}')
            lineas.append(f'    public void set{cap}({_tipo_java(t)} {n}) {{ this.{n} = {n}; }}')
            lineas.append('')
            accesores |= {(f'get{cap}', 0), (f'set{cap}', 1)}
        defecto = {'int': '0', 'byte': '0', 'short': '0', 'long': '0L', 'float': '0.0f', 'double': '0.0', 'char': "'\\0'",
                   'boolean': 'false'}
        # los get/set del modelo que ya salen de un campo no se repiten: queda el generado, con el tipo del campo
        for n, m, params in _metodos_unicos(_metodos_con_interfaces(c, todas), 'java', nombre_metodo, firma, accesores):
            ret = _tg(m, 'retorno')
            lineas.append(f"    public {_tipo_java(ret)} {n}({con_params(params)}) {{")
            if ret != 'void':
                lineas.append(f"        return {defecto.get(ret, 'null')};")
            lineas += ['    }', '']
        if lineas[-1] == '':
            lineas.pop()
        lineas.append('}')
    # imports de los tipos que no estan en java.util (solo los que se usan y no chocan con una clase del diagrama)
    propias = {_identificador(n, 'pascal', 'java') for n in todas}
    texto = '\n'.join(lineas)
    extra = [f'import {imp};' for corto, imp in sorted(_IMPORTS_JAVA.items())
             if corto not in propias and re.search(rf'\b{corto}\b', texto)]
    cabecera = ([f'package {paquete};', ''] if paquete else []) + ['import java.util.*;', 'import java.time.LocalDate;'] + extra
    return '\n'.join(cabecera + [''] + lineas) + '\n'


def _generar_clase_python(c: Dict[str, Any], todas: Dict[str, Any] = None) -> str:
    todas = todas or {}
    nom = _identificador(c['nombre'], 'pascal', 'python')
    lineas = ['from __future__ import annotations', '', 'from abc import ABC, abstractmethod',
              'from dataclasses import dataclass, field', 'from datetime import date, datetime, time', 'from decimal import Decimal',
              'from enum import Enum', 'from typing import Any, Dict, List, Optional, Set', '']
    bases = list(dict.fromkeys(_identificador(s, 'pascal', 'python') for s in c.get('superclases', []) + c.get('interfaces', [])
                               if s in todas))
    for b in bases:  # funciona como paquete (import relativo) o con los archivos sueltos
        lineas += ['try:', f'    from .{b} import {b}', 'except ImportError:', f'    from {b} import {b}']
    lineas.append('')
    doc = (c.get('documentacion') or '').replace('"""', "'''")
    if c.get('tipo') == 'UMLEnumeration':
        lineas.append(f'class {nom}(Enum):')
        if doc:
            lineas.append(f'    """{doc}"""')
        for ident in dict.fromkeys(_identificador(l, 'pascal', 'python').upper() for l in c.get('literales', []) or ['VALOR']):
            lineas.append(f"    {ident} = '{ident}'")
        return '\n'.join(lineas) + '\n'
    es_interfaz = c.get('tipo') == 'UMLInterface'
    if not es_interfaz:
        lineas.append('@dataclass')
    lineas.append(f"class {nom}({', '.join(bases or (['ABC'] if es_interfaz else []))}):" if (bases or es_interfaz) else f'class {nom}:')
    cuerpo = [f'    """{doc}"""'] if doc else []
    campos = set()
    if not es_interfaz:
        for a in c.get('atributos', []):
            n = _identificador(a['nombre'], 'camel', 'python')
            if n not in campos:
                campos.add(n)
                cuerpo.append(f"    {n}: Optional[{_tipo_python(_tg(a))}] = None")
        for n, t in _campos_asociacion(c, 'python', todas):
            campos.add(n)
            if t.startswith('List<'):
                cuerpo.append(f'    {n}: {_tipo_python(t)} = field(default_factory=list)')
            else:
                cuerpo.append(f'    {n}: Optional[{_tipo_python(t)}] = None')
    metodos = c.get('metodos', []) if es_interfaz else _metodos_con_interfaces(c, todas)
    for n, m, params in _metodos_unicos(metodos, 'python', lambda x: _identificador(x, 'camel', 'python'), campos=campos):
        cuerpo += [''] + (['    @abstractmethod'] if es_interfaz else [])
        firma = ''.join(f', {p}: {_tipo_python(t)}' for p, t in params)
        cuerpo.append(f"    def {n}(self{firma}) -> {_tipo_python(_tg(m, 'retorno'))}:")
        cuerpo.append('        raise NotImplementedError')
    return '\n'.join(lineas + (cuerpo or ['    pass'])) + '\n'


def _generar_clase_typescript(c: Dict[str, Any], todas: Dict[str, Any] = None) -> str:
    todas = todas or {}
    nom = _identificador(c['nombre'], 'pascal', 'typescript')
    conocidas = {_identificador(n, 'pascal', 'typescript') for n in todas}
    tipos = [_tg(a) for a in c.get('atributos', [])] + [t for _, t in _campos_asociacion(c, 'typescript', todas)]
    for m in _metodos_con_interfaces(c, todas):
        tipos += [_tg(m, 'retorno')] + [_tg(p) for p in m.get('parametros', [])]
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
        lits = list(dict.fromkeys(_identificador(l, 'pascal', 'typescript').upper() for l in c.get('literales', []))) or ['VALOR']
        return '\n'.join(lineas + [f'export enum {nom} {{'] + [f"  {l} = '{l}'," for l in lits] + ['}']) + '\n'

    def nombre_metodo(n):
        return _identificador(n, 'camel', 'typescript')

    def con_params(params):
        return ', '.join(f'{p}: {_tipo_ts(t)}' for p, t in params)
    campos = []
    for a in c.get('atributos', []):
        n = _identificador(a['nombre'], 'camel', 'typescript')
        if n not in [x for x, _ in campos]:
            campos.append((n, _tg(a)))
    # TypeScript no admite dos metodos con el mismo nombre (sin firma: cuenta solo el nombre)
    if c.get('tipo') == 'UMLInterface':
        cab = f'export interface {nom}' + (' extends ' + ', '.join(_identificador(i, 'pascal', 'typescript') for i in supers + ifaces) if supers + ifaces else '')
        lineas.append(cab + ' {')
        for n, t in campos:
            lineas.append(f"  {n}?: {_tipo_ts(t)};")
        for n, m, params in _metodos_unicos(c.get('metodos', []), 'typescript', nombre_metodo, campos={x for x, _ in campos}):
            lineas.append(f"  {n}({con_params(params)}): {_tipo_ts(_tg(m, 'retorno'))};")
        return '\n'.join(lineas + ['}']) + '\n'
    cab = f'export class {nom}'
    if supers:
        cab += f' extends {_identificador(supers[0], "pascal", "typescript")}'
    if ifaces:
        cab += ' implements ' + ', '.join(_identificador(i, 'pascal', 'typescript') for i in ifaces)
    lineas.append(cab + ' {')
    for n, t in campos:
        lineas.append(f"  public {n}?: {_tipo_ts(t)};")
    asocs = _campos_asociacion(c, 'typescript', todas)
    for n, t in asocs:
        lineas.append(f'  public {n}: {_tipo_ts(t)} = [];' if t.startswith('List<') else f'  public {n}?: {_tipo_ts(t)};')
    lineas += ['', f'  constructor(init?: Partial<{nom}>) {{'] + (['    super();'] if supers else []) + \
              ['    Object.assign(this, init);', '  }']
    ocupados = {x for x, _ in campos} | {x for x, _ in asocs}
    for n, m, params in _metodos_unicos(_metodos_con_interfaces(c, todas), 'typescript', nombre_metodo, campos=ocupados):
        lineas += ['', f"  public {n}({con_params(params)}): {_tipo_ts(_tg(m, 'retorno'))} {{",
                   "    throw new Error('No implementado');", '  }']
    return '\n'.join(lineas + ['}']) + '\n'


def _generar_clase_csharp(c: Dict[str, Any], todas: Dict[str, Any] = None, espacio: str = 'Modelo') -> str:
    """Clase C# con propiedades automaticas (PascalCase), metodos que lanzan NotImplementedException y el espacio de
    nombres dado (vacio = sin namespace)."""
    todas = todas or {}
    nom = _identificador(c['nombre'], 'pascal', 'csharp')

    def miembro(n):  # PascalCase, y un miembro no puede llamarse como su clase (CS0542)
        n = _identificador(n, 'pascal', 'csharp')
        n = n[0].upper() + n[1:]
        return n + '_' if n == nom or n in _RESERVADAS['csharp'] else n

    def firma(params):  # C# no admite dos metodos con los mismos tipos de parametros
        return tuple(_tipo_cs(t) for _, t in params)

    def con_params(params):
        return ', '.join(f'{_tipo_cs(t)} {p}' for p, t in params)

    cuerpo = []
    if c.get('documentacion'):
        cuerpo += ['/// <summary>'] + ['/// ' + l.replace('<', '&lt;').replace('>', '&gt;') for l in c['documentacion'].splitlines()] + \
                  ['/// </summary>']
    supers = [s for s in c.get('superclases', []) if s in todas]
    ifaces = [i for i in c.get('interfaces', []) if i in todas]
    if c.get('tipo') == 'UMLEnumeration':
        lits = list(dict.fromkeys(_identificador(l, 'pascal', 'csharp') for l in c.get('literales', []))) or ['Valor']
        cuerpo += [f'public enum {nom}', '{'] + [f'    {l},' for l in lits] + ['}']
    elif c.get('tipo') == 'UMLInterface':
        bases = [_identificador(i, 'pascal', 'csharp') for i in supers + ifaces]
        cuerpo += [f'public interface {nom}' + (' : ' + ', '.join(bases) if bases else ''), '{']
        for n, m, params in _metodos_unicos(c.get('metodos', []), 'csharp', miembro, firma):
            cuerpo.append(f"    {_tipo_cs(_tg(m, 'retorno'))} {n}({con_params(params)});")
        cuerpo.append('}')
    else:
        bases = [_identificador(s, 'pascal', 'csharp') for s in supers[:1] + ifaces]
        cuerpo += [f'public class {nom}' + (' : ' + ', '.join(bases) if bases else ''), '{']
        props = set()
        for a in c.get('atributos', []):
            n = miembro(a['nombre'])
            if n not in props:  # dos propiedades con el mismo nombre no compilarian
                props.add(n)
                cuerpo.append(f"    public {_tipo_cs(_tg(a))} {n} {{ get; set; }}")
        for n, t in _campos_asociacion(c, 'csharp', todas):
            ct, n = _tipo_cs(t), miembro(n)
            props.add(n)
            cuerpo.append(f'    public {ct} {n} {{ get; set; }}' + (f' = new {ct}();' if ct.startswith('List<') else ''))
        for n, m, params in _metodos_unicos(_metodos_con_interfaces(c, todas), 'csharp', miembro, firma, campos=props):
            cuerpo += ['', f"    public {_tipo_cs(_tg(m, 'retorno'))} {n}({con_params(params)})", '    {',
                       '        throw new NotImplementedException();', '    }']
        cuerpo.append('}')
    lineas = ['#nullable disable', '', 'using System;', 'using System.Collections.Generic;', '']
    if espacio:
        return '\n'.join(lineas + [f'namespace {espacio}', '{'] + [('    ' + l) if l else '' for l in cuerpo] + ['}']) + '\n'
    return '\n'.join(lineas + cuerpo) + '\n'


def _espacio_cs(paquete: str) -> str:
    """'modelo.dominio' -> 'Modelo.Dominio'."""
    partes = [_identificador(p, 'pascal', 'csharp') for p in (paquete or '').split('.') if p.strip()]
    return '.'.join(p[0].upper() + p[1:] for p in partes)


_EXT_GEN = {'java': '.java', 'python': '.py', 'typescript': '.ts', 'csharp': '.cs'}


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
        elif lenguaje == 'csharp':
            codigo = _generar_clase_csharp(c, clases, _espacio_cs(paquete))
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

def _tipo_go_modelo(t: str) -> str:
    """Tipo de Go con la sintaxis de UML, sin perder el tamano: []T -> List<T>, map[K]V -> Map<K, V>, *T -> T,
    time.Time -> DateTime; int64, float32... quedan como estan."""
    t = (t or '').strip()
    while t.startswith('*'):
        t = t[1:].strip()
    if t.startswith('...'):
        return f'List<{_tipo_go_modelo(t[3:])}>'
    m = re.match(r'\[[^\]]*\]\s*(.+)$', t)
    if m:
        return f'List<{_tipo_go_modelo(m.group(1))}>'
    if t.startswith('map['):
        k = _cerrar_par(t, 3, '[', ']')
        return f'Map<{_tipo_go_modelo(t[4:k])}, {_tipo_go_modelo(t[k + 1:])}>'
    if t in ('interface{}', 'interface {}', 'any') or t.startswith(('chan ', 'func')):
        return ''
    return 'DateTime' if t == 'time.Time' else t


def _tipo_para_modelo(original, normalizado, lenguaje: str = '') -> str:
    """Tipo que se guarda en el modelo al importar: el del codigo como esta escrito (long, BigDecimal, LocalDateTime y
    los genericos no cambian), sin paquetes delante. Vacio si no se sabe (Object, any, var)."""
    t = _tipo_go_modelo(original) if lenguaje == 'go' and original else (original or '').strip()
    if not t:
        return '' if normalizado in ('Object', '', None) else normalizado
    t = t.replace('"', '').replace("'", '')
    t = re.sub(r'^(final|const|readonly)\s+', '', t)
    t = re.sub(r'(?:[A-Za-z_$][\w$]*\.)+(?=[A-Za-z_$])', '', t)  # java.util.List<com.x.Pedido> -> List<Pedido>
    return '' if _normalizar_tipo(t) == 'Object' else t


def _clase_en_paquete(pk: Dict[str, Any], nombre: str, tipos=('UMLClass', 'UMLInterface', 'UMLEnumeration')):
    """La clase del paquete que corresponde a una clase del codigo: primero por nombre exacto y, si no hay, sin acentos,
    espacios ni mayusculas ('Orden de Entrega' para OrdenDeEntrega). Nunca por el nombre sin prefijo: BC_Cliente no es
    Cliente. Devuelve (clase o None, candidatas si hay mas de una)."""
    hijos = [e for e in pk.get('ownedElements', []) if isinstance(e, dict) and e.get('_type') in tipos]
    for clave in (lambda x: x, _clave_exacta):
        cands = [e for e in hijos if clave(e.get('name') or '') == clave(nombre)]
        if cands:
            return (cands[0], []) if len(cands) == 1 else (None, cands)
    return None, []


def importar_codigo_a_diagrama(doc, ruta_codigo: str, paquete_nombre: str, nombre_diagrama: str = None, lenguaje: str = 'auto',
                               modo: str = 'agregar', metodos: bool = True) -> Dict[str, Any]:
    """Importa clases (o interfaces), atributos con su tipo y metodos desde codigo hacia un paquete del .mdj y, si se
    indica, dibuja las clases nuevas en un diagrama. Solo agrega lo que falta: nunca quita atributos, metodos ni
    clases. Cada clase se busca solo en el paquete pedido; si no esta ahi se crea ahi (una homonima de otro paquete no
    se toca). Si una clase del codigo corresponde a mas de una del paquete, no se cambia nada y se avisa.
    modo='agregar' completa solo los tipos vacios; 'sincronizar' ademas pone el tipo del codigo en los atributos que ya
    tienen otro y reporta, sin quitarlos, los atributos, metodos y literales que el codigo ya no tiene (tambien cuando
    la clase del codigo no tiene ninguno). Las vistas que ya tiene la clase conservan su alto y solo crecen si no les
    caben los atributos."""
    from . import mdj as M
    if modo not in ('agregar', 'sincronizar'):
        raise ValueError(f'modo debe ser "agregar" o "sincronizar", no "{modo}"')
    clases_codigo = escanear_codigo(ruta_codigo, lenguaje)
    if not clases_codigo:
        raise ValueError(f"No se encontraron clases en {ruta_codigo}")
    pk = doc.find(paquete_nombre, types=('UMLPackage', 'UMLModel', 'UMLSubsystem'))
    dg = doc.diagram(nombre_diagrama) if nombre_diagrama else None
    if dg is not None and dg.get('_type') != 'UMLClassDiagram':
        raise ValueError(f'"{dg.get("name")}" es {dg.get("_type")}: las clases solo se dibujan en un diagrama de clases')
    tipos_modelo = ('UMLClass', 'UMLInterface', 'UMLEnumeration')
    # primero se resuelve cada clase; si alguna es ambigua no se toca nada
    destinos, ambiguas = {}, []
    for nom in clases_codigo:
        destinos[nom], cands = _clase_en_paquete(pk, nom, tipos_modelo)
        if cands:
            ambiguas.append(f'{nom} ({", ".join(repr(e.get("name")) for e in cands)})')
    if ambiguas:
        raise ValueError(f'En el paquete "{pk.get("name")}" hay mas de una clase para: {"; ".join(ambiguas)}. '
                         'Deja una sola o importa a otro paquete; no se cambio nada.')
    creadas, actualizadas = [], []
    attrs_agregados, tipos_cambiados, mets_agregados, mets_omitidos, lits_agregados, sin_codigo = {}, {}, {}, {}, {}, {}

    for nom, c_cod in clases_codigo.items():
        lang = c_cod.get('lenguaje') or ''
        destino = destinos[nom]
        if destino is None:
            tipo = {'interface': 'UMLInterface', 'enum': 'UMLEnumeration'}.get(c_cod.get('tipo_decl'), 'UMLClass')
            destino = {'_type': tipo, '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': nom}
            pk.setdefault('ownedElements', []).append(destino)
            doc.reindex()
            creadas.append(nom)
        else:
            actualizadas.append(destino.get('name') or nom)
        nombre_modelo = destino.get('name') or nom
        kind = doc.kind(destino)
        if destino['_type'] == 'UMLEnumeration':
            presentes = {_clave_exacta(l.get('name', '')) for l in destino.get('literals', [])}
            nuevos = [l for l in dict.fromkeys(c_cod.get('literales', [])) if _clave_exacta(l) not in presentes]
            destino.setdefault('literals', []).extend(
                {'_type': 'UMLEnumerationLiteral', '_id': doc.new_id(), '_parent': M.ref(destino['_id']), 'name': l} for l in nuevos)
            if not destino['literals']:
                del destino['literals']
            if nuevos and nom not in creadas:
                lits_agregados[nombre_modelo] = nuevos
            if modo == 'sincronizar':
                en_codigo = {_clave_exacta(l) for l in c_cod.get('literales', [])}
                fuera = [l.get('name') for l in destino.get('literals', []) if _clave_exacta(l.get('name', '')) not in en_codigo]
                if fuera:
                    sin_codigo.setdefault(nombre_modelo, {})['literales'] = fuera
            continue

        # atributos (con el tipo del codigo). En boundary y control no van atributos.
        attrs = list({a['nombre']: a for a in c_cod.get('atributos', [])}.values())
        cambio_vista = False
        if kind not in ('boundary', 'control'):
            existentes = {_clave_exacta(a.get('name', '')) for a in destino.get('attributes', [])}
            # se agregan aqui y no con M.agregar_atributos, que ajusta el alto de las vistas a los atributos:
            # una vista que el usuario agrando no debe encogerse al importar
            agregados = []
            for ac in attrs:
                if _clave_exacta(ac['nombre']) not in existentes:
                    destino.setdefault('attributes', []).append({'_type': 'UMLAttribute', '_id': doc.new_id(),
                                                                 '_parent': M.ref(destino['_id']), 'name': ac['nombre'], 'type': ''})
                    agregados.append(ac['nombre'])
            cambio_vista = bool(agregados)
            por_clave = {_clave_exacta(a['nombre']): a for a in attrs}
            for a in destino.get('attributes', []):
                ac = por_clave.get(_clave_exacta(a.get('name', '')))
                tipo = _tipo_para_modelo(ac.get('tipo_original'), ac.get('tipo'), lang) if ac else ''
                actual = a.get('type')
                actual = doc.name_of(actual.get('$ref')) if isinstance(actual, dict) else (actual or '')
                if not tipo or _tipo_preciso(actual, lang) == _tipo_preciso(tipo, lang) and actual:
                    continue  # mismo tipo escrito de otra forma (String y string, Long y long, float y double en Python)
                if actual and not (ac.get('tipo_original') or '').strip():
                    continue  # el codigo no lo declara (se deduce del valor): no pisa un tipo que el modelo si declara
                # en 'agregar' solo se completa un tipo vacio; en 'sincronizar' se pone el del codigo
                if not actual:
                    a['type'] = tipo
                    cambio_vista = True
                elif modo == 'sincronizar':
                    tipos_cambiados.setdefault(nombre_modelo, []).append(f"{a.get('name')}: {actual} -> {tipo}")
                    a['type'] = tipo
                    cambio_vista = True
            if agregados:
                attrs_agregados[nombre_modelo] = agregados
            if modo == 'sincronizar':
                fuera = [a.get('name') for a in destino.get('attributes', []) if _clave_exacta(a.get('name', '')) not in por_clave]
                if fuera:
                    sin_codigo.setdefault(nombre_modelo, {})['atributos'] = fuera
        if cambio_vista:  # las vistas que ya tiene la clase muestran los atributos y tipos nuevos, con su mismo alto
            for _, v in doc.views_of(destino['_id']):
                M.rehacer_atributos_vista(doc, v, destino, conservar_alto=True)

        # metodos. En el analisis de robustez (boundary, control, entity) no se ponen metodos.
        if metodos and kind in ('boundary', 'control', 'entity'):
            if c_cod.get('metodos'):
                mets_omitidos[nombre_modelo] = [m['nombre'] for m in c_cod['metodos']]
        elif metodos:
            # aunque el codigo no tenga metodos se pasa por aqui: 'sincronizar' reporta los del modelo
            ops = destino.get('operations', [])
            presentes = {_clave_exacta(o.get('name', '')) for o in ops}
            codigo_claves, nuevos = set(), []
            for m in c_cod.get('metodos', []):
                k = _clave_exacta(m['nombre'])
                codigo_claves.add(k)
                if k in presentes:
                    continue
                presentes.add(k)
                originales = m.get('tipos_originales') or {}
                op = {'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': M.ref(destino['_id']), 'name': m['nombre']}
                params = [{'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': M.ref(op['_id']), 'name': p['nombre'],
                           'type': _tipo_para_modelo(p.get('tipo_original') or originales.get(p['nombre']), p['tipo'], lang)}
                          for p in m.get('parametros', [])]
                if m.get('retorno') not in ('void', None):
                    params.append({'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': M.ref(op['_id']),
                                   'type': _tipo_para_modelo(m.get('retorno_original'), m['retorno'], lang), 'direction': 'return'})
                if params:
                    op['parameters'] = params
                if m.get('visibilidad') in ('private', 'protected'):
                    op['visibility'] = m['visibilidad']
                destino.setdefault('operations', ops).append(op)
                nuevos.append(m['nombre'])
            if modo == 'sincronizar':
                fuera = [o.get('name') for o in ops if _clave_exacta(o.get('name', '')) not in codigo_claves]
                if fuera:
                    sin_codigo.setdefault(nombre_modelo, {})['metodos'] = fuera
            if nuevos:
                mets_agregados[nombre_modelo] = nuevos

    vistas_creadas, sin_vista = [], []
    if dg is not None:
        doc.reindex()
        # se colocan debajo de todo lo que ya esta dibujado, en filas de 4, sin encimarse
        cajas = [v for v in dg.get('ownedViews', []) if isinstance(v.get('top'), (int, float)) and isinstance(v.get('height'), (int, float))]
        y = max((v['top'] + v['height'] for v in cajas), default=20) + 60
        x, alto_fila, col = 60, 0, 0
        for nom in creadas:
            el = next((o for o in pk.get('ownedElements', []) if o.get('_type') in tipos_modelo and o.get('name') == nom), None)
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

    res = {
        'paquete': pk.get('name', paquete_nombre), 'diagrama': nombre_diagrama, 'total_clases_codigo': len(clases_codigo),
        'clases_creadas': creadas, 'clases_actualizadas': actualizadas, 'modo': modo,
        'atributos_agregados': attrs_agregados, 'metodos_agregados': mets_agregados,
        'metodos_omitidos_por_robustez': mets_omitidos, 'vistas_creadas': vistas_creadas,
        'enumeraciones_sin_vista': sin_vista}
    if lits_agregados:
        res['literales_agregados'] = lits_agregados
    if modo == 'sincronizar':
        res['tipos_cambiados'] = tipos_cambiados
        res['en_modelo_sin_codigo'] = sin_codigo
        res['nota'] = ('Nada se quito: lo que aparece en en_modelo_sin_codigo ya no esta en el codigo; '
                       'si sobra, quitalo con mdj_atributos o mdj_borrar.')
    if _repetidas(clases_codigo):
        res['clases_repetidas_en_codigo'] = _repetidas(clases_codigo)
        res['nota_repetidas'] = 'Esas clases se llaman igual en varios archivos del codigo; se importo solo la primera.'
    return res
