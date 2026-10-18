# Ingenieria inversa: diagrama de clases de un programa ya hecho (Java por defecto, y los demas lenguajes que entiende
# codigo.py). Crea paquetes, clases, interfaces y enumeraciones con atributos y metodos (visibilidad, static,
# abstract), herencia, interfaces implementadas, asociaciones que salen de los campos y, si se pide, dependencias.
# Acomoda las cajas por niveles de herencia sin encimarlas y rutea las lineas para que no crucen otras cajas.
import base64
import math
import os
import re
import time

from . import codigo as C
from . import mdj as M
from .mdj import MdjError, ref

LIMITE_UN_DIAGRAMA = 60  # mas clases que esto (en varios paquetes): un diagrama por paquete si no se pide otra cosa
SIMBOLO = {'public': '+', 'private': '-', 'protected': '#', 'package': '~', 'internal': '~'}
_DIRS_PRUEBAS = {'test', 'tests', '__tests__', 'androidTest', 'testFixtures'}
# PedidoTest.java, PedidoIT.java, test_pedido.py, pedido.spec.ts... (una clase llamada solo Test si entra)
_ARCH_PRUEBAS = re.compile(r'.(Test|Tests|IT)\.(java|kt|cs)$|^test_.*\.py$|_test\.(py|go)$|\.(test|spec)\.(ts|tsx|js|jsx)$')
_NO_CLASES = set(C._PRIMITIVOS) | {'List', 'Set', 'Map'}
VISTA_DE = {'UMLClass': 'UMLClassView', 'UMLInterface': 'UMLInterfaceView', 'UMLEnumeration': 'UMLEnumerationView'}
VISTA_RELACION = {'UMLGeneralization': 'UMLGeneralizationView', 'UMLInterfaceRealization': 'UMLInterfaceRealizationView',
                  'UMLDependency': 'UMLDependencyView'}


# ---------------------------------------------------------------------------
# Lectura del programa
# ---------------------------------------------------------------------------

def _paquete_de_archivo(info, rel):
    """Paquete de la clase dentro del programa. Java, Kotlin y C# lo declaran (package, namespace). En Python el modulo
    es el paquete (app/ventas/modelos.py -> app.ventas.modelos); en TypeScript/JavaScript, si no hay namespace, y en Go
    cuenta la carpeta (en Go todos los archivos de una carpeta son un paquete y 'package' solo da el nombre corto)."""
    lang = info.get('lenguaje')
    partes = [p for p in rel.replace('\\', '/').split('/') if p not in ('', '.')]
    carpetas = partes[:-1]
    archivo = os.path.splitext(partes[-1])[0] if partes else ''
    if lang == 'python':
        return '.'.join(carpetas + ([] if archivo == '__init__' else [archivo]))
    if lang == 'typescript':
        return info.get('paquete') or '.'.join(carpetas)
    if lang == 'go':
        return '.'.join(carpetas) or info.get('paquete') or ''
    return info.get('paquete') or ''


def leer_programa(ruta, lenguaje='java', incluir_pruebas=False):
    """Clases del programa por nombre calificado (paquete.Nombre, y paquete.Externa.Nombre para una anidada). A
    diferencia de escanear_codigo no se pierden las que se llaman igual en paquetes, modulos o clases distintas; las
    partes de una partial class de C# se juntan. Sin incluir_pruebas se omiten las carpetas y archivos de pruebas."""
    ruta = os.path.abspath(os.path.expanduser(ruta))
    if lenguaje != 'auto' and lenguaje not in C._EXTENSIONES:
        raise MdjError(f'Lenguaje no soportado: {lenguaje}. Validos: auto, {", ".join(C._EXTENSIONES)}')
    exts = tuple(C._LENGUAJE_DE) if lenguaje == 'auto' else C._EXTENSIONES[lenguaje]
    if os.path.isfile(ruta):
        archivos, base = [ruta], os.path.dirname(ruta)
    elif os.path.isdir(ruta):
        archivos, base = [], ruta
        for raiz, dirs, files in os.walk(ruta):
            dirs[:] = sorted(d for d in dirs if d not in C._NO_ESCANEAR and not d.endswith('.egg-info')
                             and (incluir_pruebas or d not in _DIRS_PRUEBAS))
            for f in sorted(files):
                if f.lower().endswith(exts) and not f.endswith(('.min.js', '.d.ts')) and (incluir_pruebas or not _ARCH_PRUEBAS.search(f)):
                    archivos.append(os.path.join(raiz, f))
    else:
        raise MdjError(f'La ruta de codigo no existe: {ruta}')
    clases, repetidas = {}, []
    for a in archivos:
        rel = os.path.relpath(a, base)
        for info in C.CodeParser.parse_archivo(a, lenguaje).values():
            info['paquete'] = _paquete_de_archivo(info, rel)
            info['archivo_relativo'] = rel
            q = '.'.join(p for p in (info['paquete'], info.get('externa'), info['nombre']) if p)
            repetidas += [q] * len(info.get('repetida_en', []))  # la misma clase dos veces en un archivo
            previa = clases.get(q)
            if previa is None:
                info['q'] = q
                clases[q] = info
            elif C._misma_parcial(previa, info):
                C._juntar_partes(previa, info)
            else:
                repetidas.append(q)
    return clases, repetidas


_NOMBRE = re.compile(r'[^\W\d][\w$]*(?:\.[^\W\d][\w$]*)*')


def _modulo_python(ruta, info):
    """Modulo al que apunta un import de Python, tambien relativo (.modelos, ..comun), visto desde el archivo de info."""
    nivel = len(ruta) - len(ruta.lstrip('.'))
    resto = ruta[nivel:]
    if not nivel:
        return resto
    partes = (info.get('paquete') or '').split('.') if info.get('paquete') else []
    if os.path.splitext(os.path.basename(info.get('archivo_relativo') or ''))[0] != '__init__':
        partes = partes[:-1]  # el paquete que contiene al modulo
    partes = partes[:max(0, len(partes) - (nivel - 1))]
    return '.'.join(partes + ([resto] if resto else []))


def _carpetas_ts(ruta, info):
    """Paquetes (carpetas) donde puede estar lo que importa './user' o '../modelos' (un archivo o una carpeta con index)."""
    if not ruta.startswith('.'):
        return []  # una biblioteca: no es del programa
    destino = os.path.normpath(os.path.join(os.path.dirname(info.get('archivo_relativo') or ''), ruta)).replace('\\', '/')
    if destino.startswith('..'):
        return []
    partes = [p for p in destino.split('/') if p not in ('', '.')]
    return ['.'.join(partes[:-1]), '.'.join(partes)]


class _Resolutor:
    """Nombre de un tipo en el codigo -> clase del programa (nombre calificado). Busca, en este orden: el nombre ya
    calificado, las clases anidadas de la clase que lo usa (y de sus externas), lo que se importa con ese nombre, el
    mismo paquete, los imports con comodin (using de C#), los modulos importados, los namespace que la contienen y,
    al final, la unica clase del programa (de primer nivel) que se llame asi. Si sigue habiendo varias no elige: lo
    anota en ambiguos y no se crea la relacion."""

    def __init__(self, clases):
        self.clases = clases
        self.por_nombre = {}
        for q, info in clases.items():
            self.por_nombre.setdefault(info['nombre'], []).append(q)
        self.paquetes = {info.get('paquete') or '' for info in clases.values()}
        self.contextos, self.ambiguos = {}, {}

    def _paquete_go(self, ruta):
        """Paquete del programa al que apunta un import de Go ('github.com/x/app/ventas/models' -> 'ventas.models')."""
        punteada = '.'.join(p for p in ruta.split('/') if p)
        cands = [p for p in self.paquetes if p and (punteada == p or punteada.endswith('.' + p))]
        return max(cands, key=len) if cands else None

    def _contexto(self, desde):
        """Lo que la clase ve por sus imports: {'alias': {nombre: [clases]}, 'comodines': [paquetes], 'modulos': {alias:
        paquete}}. Un alias sin clases (import de una biblioteca) decide igual: ese nombre no es del programa."""
        if desde in self.contextos:
            return self.contextos[desde]
        info = self.clases[desde]
        lang = info.get('lenguaje')
        ctx = {'alias': {}, 'comodines': [], 'modulos': {}}
        for imp in info.get('imports', []):
            tipo, ruta, alias = imp.get('tipo'), imp.get('ruta') or '', imp.get('alias')
            if lang == 'python':
                mod = _modulo_python(ruta, info)
                if tipo == 'clase':
                    destino = f'{mod}.{imp["nombre"]}' if mod else imp['nombre']
                    ctx['alias'].setdefault(alias, []).append(destino)
                    ctx['modulos'][alias] = destino  # from paquete import modulo
                elif tipo == 'paquete':
                    ctx['comodines'].append(mod)
                else:
                    ctx['modulos'][alias] = ruta
            elif lang == 'typescript':
                carpetas = _carpetas_ts(ruta, info)
                if tipo == 'clase':
                    ctx['alias'].setdefault(alias, []).extend(f'{c}.{imp["nombre"]}' if c else imp['nombre'] for c in carpetas)
                elif tipo == 'modulo' and carpetas:
                    ctx['modulos'][alias] = carpetas[0]
            elif lang == 'go':
                pk = self._paquete_go(ruta)
                if pk:
                    ctx['modulos'][alias] = pk
            elif tipo == 'clase':
                ctx['alias'].setdefault(alias, []).append(ruta)
            elif tipo == 'paquete':
                ctx['comodines'].append(ruta)
            elif tipo == 'modulo':
                ctx['modulos'][alias] = ruta
        self.contextos[desde] = ctx
        return ctx

    def _existe(self, q, lang):
        """q si es una clase del programa. En Python y Go el import puede venir desde una carpeta de mas arriba de la
        que se leyo (app.ventas.modelos.Estado leyendo app/): se prueba tambien sin los primeros paquetes."""
        if q in self.clases:
            return q
        if lang in ('python', 'go'):
            partes = q.split('.')
            for i in range(1, len(partes) - 1):
                if '.'.join(partes[i:]) in self.clases:
                    return '.'.join(partes[i:])
        return None

    def __call__(self, nombre, desde=None):
        nombre = (nombre or '').strip()
        if not _NOMBRE.fullmatch(nombre):
            return None
        if nombre in self.clases:
            return nombre
        info = self.clases.get(desde) or {}
        pk, lang = info.get('paquete') or '', info.get('lenguaje')
        ctx = self._contexto(desde) if desde in self.clases else {'alias': {}, 'comodines': [], 'modulos': {}}
        primero, _, resto = nombre.partition('.')
        alcance = desde or ''
        while alcance and alcance != pk:  # anidadas de la clase y de sus externas
            if f'{alcance}.{nombre}' in self.clases:
                return f'{alcance}.{nombre}'
            alcance = alcance.rpartition('.')[0]
        if primero in ctx['alias']:  # lo importado con ese nombre manda, aunque no sea del programa
            for c in ctx['alias'][primero]:
                q = self._existe(c + ('.' + resto if resto else ''), lang)
                if q:
                    return q
            return None
        q = f'{pk}.{nombre}' if pk else nombre
        if q in self.clases:
            return q
        for w in ctx['comodines']:
            q = self._existe(f'{w}.{nombre}' if w else nombre, lang)
            if q:
                return q
        if resto and primero in ctx['modulos']:
            return self._existe(f"{ctx['modulos'][primero]}.{resto}", lang)
        if lang in ('csharp', 'typescript'):  # los namespace que contienen a la clase tambien se ven
            partes = pk.split('.') if pk else []
            while partes:
                partes.pop()
                q = '.'.join(partes + [nombre])
                if q in self.clases:
                    return q
        if resto:
            return None  # calificado con algo que no es del programa (java.util.Date): no se adivina
        cands = self.por_nombre.get(nombre, [])
        if len(cands) > 1:  # una anidada casi nunca se nombra sin su externa desde fuera
            cands = [c for c in cands if not self.clases[c].get('externa')] or cands
        if len(cands) == 1:
            return cands[0]
        if cands and desde:
            self.ambiguos.setdefault(desde, {})[nombre] = sorted(cands)
        return None

    def en_tipo(self, tipo, desde, original=None):
        """Clases del programa que aparecen en un tipo, en orden: List<Pedido> -> [Pedido]."""
        out = []
        for n in _NOMBRE.findall(original or tipo or ''):
            q = self(n, desde) if n not in _NO_CLASES else None
            if q and q not in out:
                out.append(q)
        return out


def _arbol_tipo(t, lang=''):
    """(base, [argumentos], opcional) de un tipo tal como esta escrito: List<Pedido>, Optional[Equipo], Pedido[],
    Cliente?, Cliente | None, []*Pedido y map[string]*Pedido de Go..."""
    t = (t or '').strip().replace('"', '').replace("'", '')
    t = re.sub(r'^(final|const|readonly)\s+', '', t)
    if lang == 'go':
        while t.startswith('*'):
            t = t[1:].strip()
        if t.startswith('...'):
            return 'List', [_arbol_tipo(t[3:], lang)], False
        m = re.match(r'\[[^\]]*\]\s*(.+)$', t)
        if m:
            return 'List', [_arbol_tipo(m.group(1), lang)], False
        if t.startswith('map['):
            k = C._cerrar_par(t, 3, '[', ']')
            return 'Map', [_arbol_tipo(t[4:k], lang), _arbol_tipo(t[k + 1:], lang)], False
        return t, [], False
    opcional = t.endswith('?')
    if t.endswith(('?', '!')):
        t = t[:-1].strip()
    partes = C._dividir(t, '|')
    if len(partes) > 1:
        utiles = [p for p in partes if p not in ('None', 'null', 'undefined')]
        if len(utiles) != 1:
            return '', [], True  # union de varios tipos: no hay un solo destino
        base, args, _ = _arbol_tipo(utiles[0], lang)
        return base, args, True
    if t.endswith('[]'):
        return 'List', [_arbol_tipo(t[:-2], lang)], opcional
    if t.endswith('...'):
        return 'List', [_arbol_tipo(t[:-3], lang)], opcional
    m = re.fullmatch(r'([\w$.]+)\s*[<\[]\s*(.*?)\s*[>\]]', t, re.S)
    if m:
        return m.group(1), [_arbol_tipo(x, lang) for x in C._dividir(m.group(2), ',')], opcional
    return t, [], opcional


def _destino_campo(tipo, lang, es_clase, opcional=False):
    """(nombre de la clase destino tal como esta escrito, multiplicidad) de un campo, o None si no es una asociacion.
    Una coleccion o un mapa apuntan a su elemento (0..*) y un opcional a su contenido (0..1); cualquier otro generico
    del programa (Repositorio<Pedido, Long>) es la asociacion con esa clase, no con su argumento."""
    def visitar(nodo, mult):
        base, args, opc = nodo
        if opc and mult == '1':
            mult = '0..1'
        clase = base.split('.')[-1].lower()
        if clase in C._LISTAS or clase in C._SETS:
            return visitar(args[0], '0..*') if len(args) == 1 else None
        if clase in C._MAPAS:
            return (visitar(args[1], '0..*') or visitar(args[0], '0..*')) if len(args) == 2 else None
        if clase in C._OPCIONALES:
            return visitar(args[0], '0..1' if mult == '1' else mult) if len(args) == 1 else None
        return (base, mult) if base and es_clase(base) else None
    return visitar(_arbol_tipo(tipo, lang), '0..1' if opcional else '1')


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

def _nuevo_id(estado=[int(time.time() * 1000) - 900000]):
    estado[0] += 3
    return base64.b64encode(b'\x00' * 4 + estado[0].to_bytes(6, 'big') + os.urandom(4)).decode()


def proyecto_nuevo(nombre):
    """Proyecto vacio de StarUML (Project > UMLModel)."""
    pid, mid = _nuevo_id(), _nuevo_id()
    return {'_type': 'Project', '_id': pid, 'name': nombre,
            'ownedElements': [{'_type': 'UMLModel', '_id': mid, '_parent': {'$ref': pid}, 'name': 'Model'}]}


def _es_accesor(m, campos):
    n = m['nombre']
    for pre in ('get', 'set', 'is'):
        if n.startswith(pre) and len(n) > len(pre) and n[len(pre)].isupper() and (n[len(pre)].lower() + n[len(pre) + 1:]) in campos:
            return True
    return False


def _tipo(doc_tipo, original, resolver, desde, elems, lang=''):
    """Tipo de un atributo o parametro: referencia a la clase del programa si es exactamente una, si no el texto.
    Se resuelve con el tipo como esta escrito (calificado o importado); con el normalizado solo si el escrito no es
    un nombre simple (Pedido? de Kotlin, Optional[Pedido] de Python)."""
    escrito = (original or '').strip()
    if lang == 'go':
        escrito = escrito.lstrip('*').strip()
    if _NOMBRE.fullmatch(escrito):
        nombre = escrito
    elif doc_tipo and _NOMBRE.fullmatch(doc_tipo) and doc_tipo not in _NO_CLASES:
        nombre = doc_tipo
    else:
        nombre = None
    q = resolver(nombre, desde) if nombre else None
    if q in elems:
        return ref(elems[q]['_id'])
    texto = (original or doc_tipo or '').strip()
    return '' if texto in ('Object', 'var') else texto


def construir(doc, clases, raiz_nombre, op):
    """Crea el paquete raiz con los paquetes, clasificadores y relaciones del programa. Devuelve lo creado."""
    modelo = M.modelo_raiz(doc)
    raiz = {'_type': 'UMLPackage', '_id': doc.new_id(), '_parent': ref(modelo['_id']), 'name': raiz_nombre}
    modelo.setdefault('ownedElements', []).append(raiz)
    paquetes = {'': raiz}

    def paquete(nombre):
        if nombre not in paquetes:
            padre_nom, _, hoja = nombre.rpartition('.')
            padre = paquete(padre_nom)
            pk = {'_type': 'UMLPackage', '_id': doc.new_id(), '_parent': ref(padre['_id']), 'name': hoja}
            padre.setdefault('ownedElements', []).append(pk)
            paquetes[nombre] = pk
        return paquetes[nombre]

    elems = {}
    # primero las de primer nivel y luego las anidadas, que van dentro de su clase externa (como en StarUML)
    for q in sorted(clases, key=lambda q: (len((clases[q].get('externa') or '').split('.')) if clases[q].get('externa') else 0, q)):
        info = clases[q]
        tipo = {'interface': 'UMLInterface', 'enum': 'UMLEnumeration'}.get(info.get('tipo_decl'), 'UMLClass')
        pkn = info.get('paquete') or ''
        externa = info.get('externa')
        duenio = elems.get(f'{pkn}.{externa}' if pkn else externa) if externa else None
        duenio = duenio or paquete(pkn)
        el = {'_type': tipo, '_id': doc.new_id(), '_parent': ref(duenio['_id']), 'name': info['nombre']}
        if info.get('abstracta'):
            el['isAbstract'] = True
        duenio.setdefault('ownedElements', []).append(el)
        elems[q] = el
    resolver = _Resolutor(clases)

    candidatas = []  # asociaciones que salen de campos: (origen, destino, rol, multiplicidad)
    for q, info in clases.items():
        el, lang = elems[q], info.get('lenguaje')
        if el['_type'] == 'UMLEnumeration' and info.get('literales'):
            el['literals'] = [{'_type': 'UMLEnumerationLiteral', '_id': doc.new_id(), '_parent': ref(el['_id']), 'name': l}
                              for l in info['literales']]
        attrs = []
        for a in info.get('atributos', []):
            # los campos de instancia son asociaciones; las constantes y campos static (en una interfaz de Java
            # todos lo son) quedan como atributos
            estatico = a.get('estatico') or (info.get('tipo_decl') == 'interface' and lang == 'java')
            destino = _destino_campo(a.get('tipo_original') or a.get('tipo'), lang, lambda n: resolver(n, q) is not None,
                                     a.get('opcional')) if op['asociaciones'] and not estatico else None
            if destino:
                candidatas.append((q, resolver(destino[0], q), a['nombre'], destino[1]))
                continue
            if not op['atributos'] or (op['solo_publicos'] and a.get('visibilidad') != 'public'):
                continue
            at = {'_type': 'UMLAttribute', '_id': doc.new_id(), '_parent': ref(el['_id']), 'name': a['nombre']}
            if a.get('visibilidad', 'public') != 'public':
                at['visibility'] = 'package' if a['visibilidad'] == 'internal' else a['visibilidad']
            if estatico:
                at['isStatic'] = True
            if a.get('final'):
                at['isReadOnly'] = True
            t = _tipo(a.get('tipo'), a.get('tipo_original'), resolver, q, elems, lang)
            if t:
                at['type'] = t
            attrs.append(at)
        if attrs:
            el['attributes'] = attrs
        if op['metodos']:
            campos = {a['nombre'] for a in info.get('atributos', [])}
            ops = []
            for m in info.get('metodos', []):
                if (op['solo_publicos'] and m.get('visibilidad') not in ('public', None)) or \
                        (op['omitir_accesores'] and _es_accesor(m, campos)):
                    continue
                o = {'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': ref(el['_id']), 'name': m['nombre']}
                vis = m.get('visibilidad', 'public')
                if vis not in ('public', None):
                    o['visibility'] = 'package' if vis == 'internal' else vis
                if m.get('estatico'):
                    o['isStatic'] = True
                if m.get('abstracto'):
                    o['isAbstract'] = True
                params, originales = [], m.get('tipos_originales') or {}
                for p in m.get('parametros', []):
                    pa = {'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': ref(o['_id']), 'name': p['nombre']}
                    t = _tipo(p.get('tipo'), p.get('tipo_original') or originales.get(p['nombre']), resolver, q, elems, lang)
                    if t:
                        pa['type'] = t
                    params.append(pa)
                if m.get('retorno') not in ('void', None):
                    pa = {'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': ref(o['_id']), 'direction': 'return'}
                    t = _tipo(m.get('retorno'), m.get('retorno_original'), resolver, q, elems, lang)
                    if t:
                        pa['type'] = t
                    params.append(pa)
                if params:
                    o['parameters'] = params
                ops.append(o)
            if ops:
                el['operations'] = ops
    doc.reindex()

    relaciones, externas = [], {}

    def relacion(tipo, origen, destino):
        r = {'_type': tipo, '_id': doc.new_id(), '_parent': ref(elems[origen]['_id']),
             'source': ref(elems[origen]['_id']), 'target': ref(elems[destino]['_id'])}
        elems[origen].setdefault('ownedElements', []).append(r)
        relaciones.append((r, origen, destino))

    for q, info in clases.items():
        es_interfaz = elems[q]['_type'] == 'UMLInterface'
        for base in info.get('superclases', []) + info.get('interfaces', []):
            t = resolver(info.get('bases_calificadas', {}).get(base, base), q)
            if not t or t == q:
                externas.setdefault(info['nombre'], []).append(base)
                continue
            destino_interfaz = elems[t]['_type'] == 'UMLInterface'
            relacion('UMLInterfaceRealization' if destino_interfaz and not es_interfaz else 'UMLGeneralization', q, t)

    # un campo en cada sentido entre dos clases: una sola asociacion navegable en ambos sentidos
    por_par = {}
    for c in candidatas:
        por_par.setdefault((c[0], c[1]), []).append(c)
    hechas = set()
    for (a, b), lista in por_par.items():
        if (a, b) in hechas:
            continue
        inversa = por_par.get((b, a), [])
        if a != b and len(lista) == 1 and len(inversa) == 1:
            _, _, rol_b, mult_b = lista[0]
            _, _, rol_a, mult_a = inversa[0]
            asoc = M.asociacion_crear(doc, elems[a], elems[b], m1=mult_a, m2=mult_b, rol1=rol_a, rol2=rol_b, navegable='ambos')
            relaciones.append((asoc, a, b))
            hechas.update({(a, b), (b, a)})
            continue
        for _, _, rol, mult in lista:
            asoc = M.asociacion_crear(doc, elems[a], elems[b], m2=mult, rol2=rol, navegable='hacia')
            relaciones.append((asoc, a, b))
        hechas.add((a, b))

    if op['dependencias']:
        unidos = {frozenset((o, d)) for _, o, d in relaciones}
        for q, info in clases.items():
            usados = []
            for m in info.get('metodos', []):
                originales = m.get('tipos_originales') or {}
                tipos = [(m.get('retorno'), m.get('retorno_original'))] + \
                    [(p.get('tipo'), p.get('tipo_original') or originales.get(p['nombre'])) for p in m.get('parametros', [])]
                for t, original in tipos:
                    usados += [d for d in resolver.en_tipo(t, q, original) if d != q and d not in usados]
            for d in usados:
                if frozenset((q, d)) not in unidos:
                    relacion('UMLDependency', q, d)
                    unidos.add(frozenset((q, d)))
    doc.reindex()
    ambiguos = sorted(f'{clases[d]["nombre"]}: {n} ({", ".join(cands)})' for d, porn in resolver.ambiguos.items()
                      for n, cands in porn.items())
    return {'raiz': raiz, 'paquetes': paquetes, 'elementos': elems, 'relaciones': relaciones, 'herencia_externa': externas,
            'tipos_ambiguos': ambiguos}


# ---------------------------------------------------------------------------
# Tamano y vistas de los clasificadores
# ---------------------------------------------------------------------------

def _texto_tipo(doc, t):
    if isinstance(t, dict):
        return doc.name_of(t.get('$ref'))
    return t or ''


def textos(doc, el):
    """Lineas que StarUML muestra en cada compartimento."""
    attrs = []
    for a in el.get('attributes', []):
        t = _texto_tipo(doc, a.get('type'))
        attrs.append(f'{SIMBOLO.get(a.get("visibility", "public"), "+")}{a.get("name", "")}' + (f': {t}' if t else ''))
    ops = []
    for o in el.get('operations', []):
        ps = [p for p in o.get('parameters', []) if p.get('direction') != 'return']
        ret = next((p for p in o.get('parameters', []) if p.get('direction') == 'return'), None)
        firma = ', '.join(p.get('name', '') + (f': {_texto_tipo(doc, p.get("type"))}' if p.get('type') else '') for p in ps)
        rt = _texto_tipo(doc, ret.get('type')) if ret else ''
        ops.append(f'{SIMBOLO.get(o.get("visibility", "public"), "+")}{o.get("name", "")}({firma})' + (f': {rt}' if rt else ''))
    lits = [l.get('name', '') for l in el.get('literals', [])]
    return attrs, ops, lits


def medir(doc, el, op, espacio=None, de=None):
    """(ancho, alto) de la caja: generosos, porque StarUML agranda una caja chica pero no achica una grande.
    Con espacio (el paquete de una clase de otro paquete, que se dibuja como contexto) la caja es compacta: solo el
    nombre y "(from paquete)". Con de (la clase externa de una anidada) la caja completa lleva "(from Externa)"."""
    estereotipo = {'UMLInterface': '«interface»', 'UMLEnumeration': '«enumeration»'}.get(el['_type'])
    if espacio is not None:
        ancho = max(M.ancho13(el.get('name', '')) * 1.12, M.ancho13(f'(from {espacio})'), M.ancho13(estereotipo or '')) + 26
        return max(110, round(ancho)), 27 + 15 + (15 if estereotipo else 0)
    attrs, ops, lits = textos(doc, el)
    lineas = attrs + ops + lits + ([estereotipo] if estereotipo else []) + ([f'(from {de})'] if de else [])
    ancho = max([M.ancho13(el.get('name', '')) * 1.12] + [M.ancho13(t) for t in lineas]) + 26
    alto = 27 + (15 if estereotipo else 0) + (15 if de else 0)
    for items, visible in _compartimentos(el, attrs, ops, lits, op):
        if visible:
            alto += 15 * len(items) + 10
    return max(110, round(ancho)), round(alto)


def _compartimentos(el, attrs, ops, lits, op):
    """[(items, visible)] en el orden de StarUML: literales (enumeraciones), atributos, operaciones."""
    t = el['_type']
    out = []
    if t == 'UMLEnumeration':
        out.append((lits, True))
    out.append((attrs, bool(attrs) or (t == 'UMLClass' and op['atributos'])))
    out.append((ops, bool(ops) or (t == 'UMLClass' and op['metodos'])))
    return out


def vista_clasificador(doc, dg, el, x, y, ancho, alto, op, espacio=None, de=None):
    """Vista de clase, interfaz o enumeracion en notacion de etiqueta, con todos sus compartimentos. Con espacio es
    la caja compacta de una clase de otro paquete: sin miembros y con "(from paquete)". Con de (clase anidada) la
    caja es completa y lleva "(from Externa)" para distinguirla de otra anidada que se llame igual."""
    compacta = espacio is not None
    desde = espacio if compacta else de
    attrs, ops, lits = ([], [], []) if compacta else textos(doc, el)
    vid, ncid = doc.new_id(), doc.new_id()
    labs = [doc.new_id() for _ in range(4)]
    estereotipo = {'UMLInterface': '«interface»', 'UMLEnumeration': '«enumeration»'}.get(el['_type'])
    alto_nombre = 27 + (15 if estereotipo else 0) + (15 if desde else 0)
    top_nombre = y + 7 + (15 if estereotipo else 0)
    ns = {'_type': 'LabelView', '_id': labs[2], '_parent': ref(ncid), 'font': 'Arial;13;0', 'parentStyle': True,
          'left': x + 5, 'top': top_nombre + 15, 'width': ancho - 9, 'height': 13}
    if desde:
        ns['text'] = f'(from {desde})'
    else:
        ns['visible'] = False
    et = {'_type': 'LabelView', '_id': labs[0], '_parent': ref(ncid), 'font': 'Arial;13;0', 'parentStyle': True,
          'left': x + 5, 'top': y + 5, 'width': ancho - 9, 'height': 13}
    if estereotipo:
        et['text'] = estereotipo
    else:
        et['visible'] = False
    nc = {'_type': 'UMLNameCompartmentView', '_id': ncid, '_parent': ref(vid), 'model': ref(el['_id']),
          'subViews': [et,
                       {'_type': 'LabelView', '_id': labs[1], '_parent': ref(ncid), 'font': 'Arial;13;3' if el.get('isAbstract') else 'Arial;13;1',
                        'parentStyle': True, 'left': x + 5, 'top': top_nombre, 'width': ancho - 9, 'height': 13,
                        'text': el.get('name', '')},
                       ns,
                       {'_type': 'LabelView', '_id': labs[3], '_parent': ref(ncid), 'visible': False, 'font': 'Arial;13;0',
                        'parentStyle': True, 'left': x, 'top': y, 'height': 13, 'horizontalAlignment': 1}],
          'font': 'Arial;13;0', 'parentStyle': True, 'left': x, 'top': y, 'width': ancho, 'height': alto_nombre,
          'stereotypeLabel': ref(labs[0]), 'nameLabel': ref(labs[1]), 'namespaceLabel': ref(labs[2]), 'propertyLabel': ref(labs[3])}

    def compartimento(tipo, tipo_item, modelos, items, visible, top):
        cid = doc.new_id()
        c = {'_type': tipo, '_id': cid, '_parent': ref(vid), 'model': ref(el['_id'])}
        if not visible:
            c['visible'] = False
        subs = [{'_type': tipo_item, '_id': doc.new_id(), '_parent': ref(cid), 'model': ref(m['_id']), 'font': 'Arial;13;0',
                 'parentStyle': True, 'left': x + 5, 'top': top + 5 + 15 * i, 'width': ancho - 9, 'height': 13,
                 'text': t, 'horizontalAlignment': 0} for i, (m, t) in enumerate(zip(modelos, items))] if visible else []
        if subs:
            c['subViews'] = subs
        c.update({'font': 'Arial;13;0', 'parentStyle': True, 'left': x, 'top': top, 'width': ancho,
                  'height': 15 * len(items) + 10 if visible else 10})
        return c

    subs, top, campos = [nc], y + alto_nombre, {}
    visibles = [(items, False) for items, _ in _compartimentos(el, attrs, ops, lits, op)] if compacta else \
        _compartimentos(el, attrs, ops, lits, op)
    for (items, visible), (clave, tipo, tipo_item, modelos) in zip(
            visibles,
            ([('enumerationLiteralCompartment', 'UMLEnumerationLiteralCompartmentView', 'UMLEnumerationLiteralView', el.get('literals', []))]
             if el['_type'] == 'UMLEnumeration' else []) +
            [('attributeCompartment', 'UMLAttributeCompartmentView', 'UMLAttributeView', el.get('attributes', [])),
             ('operationCompartment', 'UMLOperationCompartmentView', 'UMLOperationView', el.get('operations', []))]):
        c = compartimento(tipo, tipo_item, modelos, items, visible, top)
        subs.append(c)
        campos[clave] = c
        if visible:
            top += c['height']
    for clave, tipo in (('receptionCompartment', 'UMLReceptionCompartmentView'),
                        ('templateParameterCompartment', 'UMLTemplateParameterCompartmentView')):
        c = compartimento(tipo, None, [], [], False, y)
        subs.append(c)
        campos[clave] = c
    v = {'_type': VISTA_DE[el['_type']], '_id': vid, '_parent': ref(dg['_id']), 'model': ref(el['_id']), 'subViews': subs,
         'font': 'Arial;13;0', 'parentStyle': False, 'containerChangeable': True,
         'left': x, 'top': y, 'width': ancho, 'height': alto, 'stereotypeDisplay': 'label', 'nameCompartment': ref(ncid)}
    if desde:
        v['showNamespace'] = True
    if campos['attributeCompartment'].get('visible', True) is False:
        v['suppressAttributes'] = True
    if campos['operationCompartment'].get('visible', True) is False:
        v['suppressOperations'] = True
    v.update({k: ref(c['_id']) for k, c in campos.items()})
    dg.setdefault('ownedViews', []).append(v)
    return v


def vista_relacion(doc, dg, rel, tail_v, head_v, medios=()):
    """Linea de generalizacion, realizacion de interfaz o dependencia (misma estructura que guarda StarUML)."""
    vid = doc.new_id()
    puntos = M.ruta(tail_v, head_v, medios)
    P = [tuple(float(n) for n in p.split(':')) for p in puntos.split(';')]
    mx, my = (P[0][0] + P[-1][0]) / 2, (P[0][1] + P[-1][1]) / 2
    subs = []
    for alpha, dist, visible, dy in ((1.5707963267948966, 15, False, -15), (1.5707963267948966, 30, None, -30),
                                     (-1.5707963267948966, 15, False, 15)):
        subs.append({'_type': 'EdgeLabelView', '_id': doc.new_id(), '_parent': ref(vid), 'model': ref(rel['_id']),
                     'visible': visible, 'font': 'Arial;13;0', 'parentStyle': False, 'left': round(mx), 'top': round(my + dy),
                     'height': 13, 'alpha': alpha, 'distance': dist, 'hostEdge': ref(vid), 'edgePosition': 1})
    v = {'_type': VISTA_RELACION[rel['_type']], '_id': vid, '_parent': ref(dg['_id']), 'model': ref(rel['_id']), 'subViews': subs,
         'font': 'Arial;13;0', 'parentStyle': False, 'head': ref(head_v['_id']), 'tail': ref(tail_v['_id']),
         'lineStyle': 1, 'points': puntos, 'showVisibility': True,
         'nameLabel': ref(subs[0]['_id']), 'stereotypeLabel': ref(subs[1]['_id']), 'propertyLabel': ref(subs[2]['_id'])}
    dg.setdefault('ownedViews', []).append(v)
    return v


# ---------------------------------------------------------------------------
# Acomodo por capas (Sugiyama) y ruteo ortogonal
# ---------------------------------------------------------------------------

SEP_X, SEP_X_HUECO, SEP_HUECOS, SEP_Y, MARGEN, ANCHO_BANDA, ANCHO_HUECO, MAX_POR_CAPA, CARRIL = 60, 22, 8, 120, 60, 2600, 2, 7, 9
ANCHO_MAX = 900  # lo mas que se ensancha una caja para que quepan las etiquetas de sus lineas


def _capas(nodos, aristas):
    """Capa de cada nodo. aristas: (arriba, abajo, fija). La herencia (fija) manda: la clase base siempre arriba. Cada
    asociacion pone al dueno del campo arriba de la clase referida mientras eso no forme un ciclo ni alargue el
    diagrama mas alla de un tope de filas (~raiz de n); las que no caben quedan libres (misma fila o hacia arriba)
    y se rutean por los canales. Las clases sin ninguna restriccion se acercan a la fila de sus vecinas."""
    nodos = sorted(nodos)
    fijas = [(a, b) for a, b, f in aristas if f and a != b]
    suaves = sorted({(a, b) for a, b, f in aristas if not f and a != b})

    def niveles(restr):
        """Camino mas largo desde las raices; None si hay ciclo."""
        pred = {n: [] for n in nodos}
        for a, b in restr:
            pred[b].append(a)
        capa, pendientes = {}, list(nodos)
        while pendientes:
            listos = [n for n in pendientes if all(p in capa for p in pred[n])]
            if not listos:
                return None
            for n in listos:
                capa[n] = 1 + max((capa[p] for p in pred[n]), default=-1)
            pendientes = [n for n in pendientes if n not in capa]
        return capa
    capa = niveles(fijas) or {n: 0 for n in nodos}
    tope = max(max(capa.values()) + 1, math.ceil(math.sqrt(len(nodos))) + 2)
    restr = list(fijas)
    for a, b in suaves:
        prueba = niveles(restr + [(a, b)])
        if prueba is not None and max(prueba.values()) < tope:
            restr.append((a, b))
            capa = prueba
    # las fuentes bajan junto a lo que tienen debajo (lineas mas cortas)
    sucs = {n: [] for n in nodos}
    preds = {n: [] for n in nodos}
    for a, b in restr:
        sucs[a].append(b)
        preds[b].append(a)
    for n in sorted(nodos, key=lambda n: -capa[n]):
        if not preds[n] and sucs[n]:
            capa[n] = min(capa[s] for s in sucs[n]) - 1
    libres = [n for n in nodos if not preds[n] and not sucs[n]]
    vecinos = {n: [] for n in nodos}
    for a, b in suaves:
        vecinos[a].append((b, -1))
        vecinos[b].append((a, 1))
    for _ in range(10):
        for n in libres:
            if vecinos[n]:
                valores = sorted(capa[v] + d for v, d in vecinos[n])
                capa[n] = valores[(len(valores) - 1) // 2]
    base = min(capa.values())
    return {n: c - base for n, c in capa.items()}


def _cruces_orden(filas, arriba_de, mismas):
    """Cruces que deja un orden de las filas: pares de lineas entre filas vecinas que se cruzan (inversiones, contadas
    con un arbol de Fenwick) mas, por cada linea entre cajas de la misma fila, las cajas que quedan en medio."""
    pos = {n: i for f in filas for i, n in enumerate(f)}
    total = sum(abs(pos[a] - pos[b]) - 1 for a, b in mismas)
    for f in filas[1:]:
        lineas = sorted((pos[a], pos[b]) for b in f for a in arriba_de[b])
        arbol = [0] * (len(f) + 1)
        for k, (_, b) in enumerate(lineas):
            i, menores = b + 1, 0  # las ya vistas con b menor o igual
            while i:
                menores += arbol[i]
                i -= i & -i
            total += k - menores
            i = b + 1
            while i <= len(f):
                arbol[i] += 1
                i += i & -i
    return total


def _intercambiar(filas, arriba_de, abajo_de, junto_a):
    """Intercambia cajas vecinas de una fila mientras eso deje menos cruces con las filas de arriba y de abajo (y menos
    cajas en medio de las lineas de la misma fila)."""
    for _ in range(20):
        pos = {n: i for f in filas for i, n in enumerate(f)}
        cambio = False
        for f in filas:
            for j in range(len(f) - 1):
                u, w = f[j], f[j + 1]
                antes = despues = 0
                for vecinos in (arriba_de, abajo_de):
                    for a in vecinos[u]:
                        for b in vecinos[w]:
                            antes += pos[a] > pos[b]
                            despues += pos[a] < pos[b]
                for n, otro, crece in ((u, w, lambda p: p < j), (w, u, lambda p: p > j + 1)):
                    for v in junto_a[n]:
                        if v != otro:
                            despues += crece(pos[v])
                            antes += not crece(pos[v])
                if despues < antes:
                    f[j], f[j + 1] = w, u
                    pos[u], pos[w] = j + 1, j
                    cambio = True
        if not cambio:
            break


def _acomodar_componente(comp, tam, aristas, copias=None):
    """Posiciones de una componente conexa (desde 0,0) y la geometria de sus filas, huecos y canales, para rutear.
    copias: {frozenset(par): cuantas lineas lo unen}; esas lineas pasan juntas por un hueco mas ancho."""
    copias = copias or {}
    capa = _capas(comp, aristas)
    # una capa con demasiadas cajas se parte en varias: primero las que no conectan hacia abajo
    abajo = {a if capa[a] < capa[b] else b for a, b, _ in aristas if capa[a] != capa[b]}
    por_capa, nueva, desplazo = {}, {}, 0
    for n in comp:
        por_capa.setdefault(capa[n], []).append(n)
    for c in sorted(por_capa):
        lista = sorted(por_capa[c], key=lambda n: (n in abajo, n))
        for i, n in enumerate(lista):
            nueva[n] = c + desplazo + i // MAX_POR_CAPA
        desplazo += (len(lista) - 1) // MAX_POR_CAPA
    capa = nueva
    # cada relacion, de la caja de arriba a la de abajo; las que quedan en la misma fila van aparte
    pares, mismas = [], []
    for a, b, _ in aristas:
        if a == b:
            continue
        par = (a, b) if capa[a] < capa[b] else (b, a)
        if capa[a] == capa[b]:
            if par not in mismas and (b, a) not in mismas:
                mismas.append(par)
        elif par not in pares:
            pares.append(par)
    # huecos: una arista que salta capas pasa por un hueco reservado en cada capa intermedia
    ancho = {n: tam[n][0] for n in comp}
    cadenas, arriba_de, abajo_de, junto_a = {}, {n: [] for n in comp}, {n: [] for n in comp}, {n: [] for n in comp}
    for a, b in pares:
        previo, cadena = a, [a]
        for c in range(capa[a] + 1, capa[b]):
            h = ('hueco', a, b, c)
            capa[h], ancho[h] = c, ANCHO_HUECO + CARRIL * (copias.get(frozenset((a, b)), 1) - 1)
            arriba_de[h], abajo_de[h], junto_a[h] = [previo], [], []
            abajo_de[previo].append(h)
            cadena.append(h)
            previo = h
        abajo_de[previo].append(b)
        arriba_de[b].append(previo)
        cadena.append(b)
        cadenas[(a, b)] = cadena
    for a, b in mismas:
        junto_a[a].append(b)
        junto_a[b].append(a)
    filas = [[] for _ in range(max(capa.values()) + 1)]
    for n in sorted(capa, key=lambda n: (isinstance(n, tuple), str(n))):
        filas[capa[n]].append(n)
    # orden por baricentro (las vecinas de la misma fila tambien cuentan, para dejarlas juntas); se queda el orden con
    # menos cruces y luego se intercambian cajas vecinas mientras eso quite cruces
    mejor = (_cruces_orden(filas, arriba_de, mismas), [list(f) for f in filas])
    for pasada in range(10):
        pos = {n: i for f in filas for i, n in enumerate(f)}
        bajando = pasada % 2 == 0
        vecinos = arriba_de if bajando else abajo_de
        for i in (range(len(filas)) if bajando else range(len(filas) - 1, -1, -1)):
            def bari(n):
                vs = [pos[v] for v in vecinos[n]] + [pos[v] for v in junto_a[n]]
                return sum(vs) / len(vs) if vs else pos[n]
            filas[i].sort(key=bari)
            for j, n in enumerate(filas[i]):
                pos[n] = j
        cuantos = _cruces_orden(filas, arriba_de, mismas)
        if cuantos < mejor[0]:
            mejor = (cuantos, [list(f) for f in filas])
    filas = mejor[1]
    _intercambiar(filas, arriba_de, abajo_de, junto_a)

    def sep(a, b):  # las lineas largas que pasan juntas van como un haz de paralelas
        huecos = isinstance(a, tuple) + isinstance(b, tuple)
        return SEP_HUECOS if huecos == 2 else SEP_X_HUECO if huecos else SEP_X
    # x: empaquetado inicial y luego cada fila lo mas cerca posible del centro de sus vecinas, sin encimarse
    x = {}
    for f in filas:
        cx = 0
        for i, n in enumerate(f):
            cx += sep(f[i - 1], n) if i else 0
            x[n] = cx
            cx += ancho[n]
    for pasada in range(12):
        bajando = pasada % 2 == 0
        vecinos = arriba_de if bajando else abajo_de
        for f in (filas if bajando else filas[::-1]):
            deseo = []
            for n in f:
                vs = [x[v] + ancho[v] / 2 for v in vecinos[n]]
                deseo.append(sum(vs) / len(vs) - ancho[n] / 2 if vs else x[n])
            for n, v in zip(f, _colocar(deseo, [ancho[n] for n in f], [sep(a, b) for a, b in zip(f, f[1:])])):
                x[n] = v
    minx = min(x.values())
    altos = [max([tam[n][1] for n in f if not isinstance(n, tuple)] or [0]) for f in filas]
    # cada canal entre filas lo bastante alto para que cada linea que pasa por el tenga su carril; las de una misma
    # fila usan el canal de arriba (o el de abajo en la primera fila)
    pasan = [0] * len(filas)
    for a, b in pares:
        for c in range(capa[a], capa[b]):
            pasan[c] += copias.get(frozenset((a, b)), 1)
    for a, b in mismas:
        pasan[max(capa[a] - 1, 0)] += copias.get(frozenset((a, b)), 1)
    canales = [max(SEP_Y, 56 + CARRIL * n) for n in pasan]
    tops, y = [], 0
    for h, g in zip(altos, canales):
        tops.append(y)
        y += h + g
    posiciones = {n: (round(x[n] - minx), tops[capa[n]]) for n in comp}
    huecos = {n: x[n] - minx + ancho[n] / 2 for n in capa if isinstance(n, tuple)}
    return posiciones, {'cadenas': cadenas, 'mismas': mismas, 'capa': capa, 'tops': tops, 'altos': altos,
                        'canales': canales, 'huecos': huecos, 'ancho': max(x[n] + ancho[n] for n in capa) - minx,
                        'alto': y - canales[-1]}


def _colocar(deseo, anchos, seps):
    """Posiciones en una fila lo mas cerca posible de las deseadas (minimos cuadrados), en el orden dado y sin
    encimarse: regresion isotonica (pool-adjacent-violators) sobre deseo menos el desplazamiento minimo."""
    desplazo = [0.0]
    for w, sp in zip(anchos, seps):
        desplazo.append(desplazo[-1] + w + sp)
    bloques = []  # [suma, cuantos]
    for d, o in zip(deseo, desplazo):
        bloques.append([d - o, 1])
        while len(bloques) > 1 and bloques[-2][0] / bloques[-2][1] > bloques[-1][0] / bloques[-1][1]:
            suma, cuantos = bloques.pop()
            bloques[-1][0] += suma
            bloques[-1][1] += cuantos
    y = [suma / cuantos for suma, cuantos in bloques for _ in range(cuantos)]
    return [yi + o for yi, o in zip(y, desplazo)]


def acomodar(nodos, tam, aristas, copias=None):
    """Posicion (left, top) de cada caja y la geometria para rutear. Cada componente conexa por capas, una junto a
    otra; las clases sueltas (sin relaciones) al final, en filas. copias: {frozenset(par): cuantas lineas lo unen}."""
    vecinos = {n: set() for n in nodos}
    for a, b, _ in aristas:
        vecinos[a].add(b)
        vecinos[b].add(a)
    visto, componentes, sueltas = set(), [], []
    for n in sorted(nodos, key=lambda n: (-len(vecinos[n]), n)):
        if n in visto:
            continue
        comp, pila = [], [n]
        while pila:
            m = pila.pop()
            if m not in visto:
                visto.add(m)
                comp.append(m)
                pila.extend(vecinos[m])
        if len(comp) > 1:
            componentes.append(comp)
        else:
            sueltas.append(n)
    posiciones, geometrias = {}, []
    x0, y0, alto_banda = MARGEN, MARGEN, 0
    for comp in componentes:
        miembros = set(comp)
        pos, geo = _acomodar_componente(comp, tam, [(a, b, f) for a, b, f in aristas if a in miembros], copias)
        if x0 > MARGEN and x0 + geo['ancho'] > ANCHO_BANDA:
            x0, y0, alto_banda = MARGEN, y0 + alto_banda + SEP_Y, 0
        posiciones.update({n: (x + round(x0), y + y0) for n, (x, y) in pos.items()})
        geo['huecos'] = {h: hx + x0 for h, hx in geo['huecos'].items()}
        geo['tops'] = [t + y0 for t in geo['tops']]
        geometrias.append(geo)
        alto_banda = max(alto_banda, geo['alto'])
        x0 += geo['ancho'] + SEP_X * 2
    if sueltas:
        y0 = y0 + alto_banda + SEP_Y if posiciones else MARGEN
        x, alto = MARGEN, 0
        for n in sorted(sueltas):
            if x > MARGEN and x + tam[n][0] > ANCHO_BANDA:
                x, y0, alto = MARGEN, y0 + alto + SEP_Y // 2, 0
            posiciones[n] = (x, y0)
            x += tam[n][0] + SEP_X
            alto = max(alto, tam[n][1])
    return posiciones, geometrias


def _cruza(p, q, caja, margen=6):
    """El segmento p-q toca la caja (inflada por el margen)? Recorte de Liang-Barsky."""
    x0, y0, x1, y1 = caja[0] - margen, caja[1] - margen, caja[2] + margen, caja[3] + margen
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def _caja(v):
    return (v['left'], v['top'], v['left'] + v['width'], v['top'] + v['height'])


def _cruces(puntos, cajas):
    return sum(1 for a, b in zip(puntos, puntos[1:]) for c in cajas if _cruza(a, b, c))


def _puntos(v):
    return [tuple(float(n) for n in p.split(':')) for p in v['points'].split(';')]


def _sin_colineales(medios):
    limpio = []
    for p in medios:
        p = (round(p[0]), round(p[1]))
        if limpio and p == limpio[-1]:
            continue
        if len(limpio) >= 2 and (limpio[-2][0] == limpio[-1][0] == p[0] or limpio[-2][1] == limpio[-1][1] == p[1]):
            limpio[-1] = p
            continue
        limpio.append(p)
    return limpio


def _ancho_etiqueta(texto):
    return M.ancho13(texto) + 2 if texto else 0


def _sumideros(nodos, sig):
    """Nodos de las componentes fuertemente conexas de las que no sale ninguna arista (Tarjan, sin recursion)."""
    indice, bajo, comp, pila, en_pila = {}, {}, {}, [], set()

    def entrar(v):
        indice[v] = bajo[v] = len(indice)
        pila.append(v)
        en_pila.add(v)
        return (v, iter(sig(v)))
    for raiz in nodos:
        if raiz in indice:
            continue
        trabajo = [entrar(raiz)]
        while trabajo:
            v, siguientes = trabajo[-1]
            for w in siguientes:
                if w not in indice:
                    trabajo.append(entrar(w))
                    break
                if w in en_pila:
                    bajo[v] = min(bajo[v], indice[w])
            else:
                trabajo.pop()
                if trabajo:
                    u = trabajo[-1][0]
                    bajo[u] = min(bajo[u], bajo[v])
                if bajo[v] == indice[v]:
                    while True:
                        w = pila.pop()
                        en_pila.discard(w)
                        comp[w] = v
                        if w == v:
                            break
    sale = {comp[u] for u in nodos for w in sig(u) if comp[w] != comp[u]}
    return [v for v in nodos if comp[v] not in sale]


def _orden_canal(pedidos):
    """Orden de arriba abajo de los carriles de un canal para que las lineas no se crucen cuando se puede: si un tramo
    vertical de una linea que sube a la fila de arriba cae dentro del tramo horizontal de otra, va arriba de ella; si
    baja a la fila de abajo, debajo. Si una linea sube y baja dentro del tramo de otra (la cruza de lado a lado) el
    cruce no se puede evitar y no pone condicion. Si aun asi las condiciones se contradicen (un ciclo) se rompe el
    ciclo que no espera a ninguna otra linea, por la que tiene menos pendientes; a igualdad, en el orden en que se
    pidieron."""
    n = len(pedidos)
    arriba_de = {i: set() for i in range(n)}  # los que deben ir arriba de i
    for a, pa in enumerate(pedidos):
        xs = pa['sube_a'] + pa['baja_a']
        lo, hi = min(xs), max(xs)
        for b, pb in enumerate(pedidos):
            if a == b:
                continue
            sube = any(lo < x < hi for x in pb['sube_a'])
            baja = any(lo < x < hi for x in pb['baja_a'])
            if sube and not baja:
                arriba_de[a].add(b)
            elif baja and not sube:
                arriba_de[b].add(a)
    orden, quedan = [], list(range(n))
    while quedan:
        resto = set(quedan)
        libres = [i for i in quedan if not arriba_de[i] & resto]
        if not libres:
            # en un ciclo que no depende de otras lineas: todos sus ancestros dependen a su vez de ella
            libres = _sumideros(quedan, lambda i: arriba_de[i] & resto)
        j = min(libres, key=lambda i: (len(arriba_de[i] & resto), i))
        orden.append(j)
        quedan.remove(j)
    return [pedidos[i] for i in orden]


def _poner_etiqueta(v, lab, centro):
    """StarUML pone el centro de la etiqueta en p1 + distance * (cos(t - alpha), sin(t - alpha)), con p1 el extremo de
    la linea y t el angulo de p1 hacia el punto vecino: se calculan alpha y distance para que quede en centro."""
    pts = _puntos(v)
    p1, p2 = (pts[0], pts[1]) if lab.get('edgePosition') == 2 else (pts[-1], pts[-2])
    t = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    a = t - math.atan2(centro[1] - p1[1], centro[0] - p1[0])
    lab['alpha'] = math.atan2(math.sin(a), math.cos(a))
    lab['distance'] = round(math.hypot(centro[0] - p1[0], centro[1] - p1[1]), 2)
    lab['left'] = round(centro[0] - (lab.get('width') or 0) / 2)
    lab['top'] = round(centro[1] - 6.5)


def _centro_etiqueta(v, lab):
    pts = _puntos(v)
    p1, p2 = (pts[0], pts[1]) if lab.get('edgePosition') == 2 else (pts[-1], pts[-2])
    t = math.atan2(p2[1] - p1[1], p2[0] - p1[0]) - (lab.get('alpha') or 0)
    d = lab.get('distance') or 0
    return (p1[0] + d * math.cos(t), p1[1] + d * math.sin(t))


def _x_en(pts, y):
    """x de la linea a la altura y, por el primer tramo que la alcanza desde el extremo pts[0]."""
    for p, q in zip(pts, pts[1:]):
        if min(p[1], q[1]) <= y <= max(p[1], q[1]) and p[1] != q[1]:
            return p[0] + (q[0] - p[0]) * (y - p[1]) / (q[1] - p[1])
    return pts[0][0]


def _y_en(pts, x):
    """y de la linea en x, por el primer tramo que la alcanza desde el extremo pts[0]."""
    for p, q in zip(pts, pts[1:]):
        if min(p[0], q[0]) <= x <= max(p[0], q[0]) and p[0] != q[0]:
            return p[1] + (q[1] - p[1]) * (x - p[0]) / (q[0] - p[0])
    return pts[0][1]


def _lugares(pts, caja, ancho, lado):
    """Centros posibles de una etiqueta de extremo, en orden de preferencia: junto a la caja, del lado pedido de la
    linea (1: derecha o abajo, -1: izquierda o arriba), luego del otro lado, y cada vez mas lejos del borde."""
    e = pts[0]
    l, t, r, b = caja
    borde = min((abs(e[1] - t), 'arriba'), (abs(e[1] - b), 'abajo'), (abs(e[0] - l), 'izq'), (abs(e[0] - r), 'der'))[1]
    lugares = []
    for s, k in [(s, k) for ks in ((0, 1, 2), (3, 4, 5)) for s in (lado, -lado) for k in ks]:
        if borde in ('arriba', 'abajo'):
            y = t - 10.5 - 15 * k if borde == 'arriba' else b + 10.5 + 15 * k
            lugares.append((_x_en(pts, y) + s * (ancho / 2 + 5), y))
        else:
            x = l - 5 - ancho / 2 - 15 * k if borde == 'izq' else r + 5 + ancho / 2 + 15 * k
            lugares.append((x, _y_en(pts, x) + s * 11))
    return lugares


def etiquetas_extremos(lineas, cajas):
    """Multiplicidad (a la derecha de la linea) y rol (a la izquierda) de cada extremo de asociacion junto a su caja,
    en el primer lugar que no toque otra etiqueta, una linea ni una caja; si no hay, en el que toque menos.
    lineas: vistas de las relaciones; cajas: {id de la vista: (izq, arriba, der, abajo)}."""
    toca = lambda r, s: r[0] < s[2] and s[0] < r[2] and r[1] < s[3] and s[1] < r[3]
    # rejilla de celdas de 120 px con los tramos, las cajas y las etiquetas ya puestas que tocan cada celda
    rejilla = {}

    def celdas(r):
        return [(i, j) for i in range(int(r[0] // 120), int(r[2] // 120) + 1)
                for j in range(int(r[1] // 120), int(r[3] // 120) + 1)]

    def poner(r, cosa):
        for c in celdas(r):
            rejilla.setdefault(c, []).append(cosa)
    for v in lineas:
        pts = _puntos(v)
        for p, q in zip(pts, pts[1:]):
            poner((min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1])), ('linea', p, q))
    for c in cajas.values():
        poner(c, ('caja', c))
    for v in lineas:
        if v['_type'] != 'UMLAssociationView':
            continue
        subs = {s['_id']: s for s in v.get('subViews', [])}
        pts = _puntos(v)
        for extremo, camino in (('tail', pts), ('head', pts[::-1])):
            caja = cajas.get(v[extremo]['$ref'])
            if caja is None:
                continue
            for k, lado in (('MultiplicityLabel', 1), ('RoleNameLabel', -1)):
                lab = subs.get((v.get(extremo + k) or {}).get('$ref'))
                if not lab or lab.get('visible') is False or not lab.get('text'):
                    continue
                w = _ancho_etiqueta(lab['text'])
                mejor = None
                for i, (cx, cy) in enumerate(_lugares(camino, caja, w, lado)):
                    rect = (cx - w / 2 - 2, cy - 8.5, cx + w / 2 + 2, cy + 8.5)
                    costo = 0
                    for cosa in {cosa for c in celdas(rect) for cosa in rejilla.get(c, ())}:
                        if cosa[0] == 'linea':
                            costo += 10 * _cruza(cosa[1], cosa[2], rect, 0)
                        else:
                            costo += (100 if cosa[0] == 'caja' else 10) * toca(rect, cosa[1])
                    if mejor is None or (costo, i) < mejor[:2]:
                        mejor = (costo, i, (cx, cy), rect)
                    if costo == 0:
                        break
                _poner_etiqueta(v, lab, mejor[2])
                poner(mejor[3], ('etiqueta', mejor[3]))


def _seps(espacios):
    """Separaciones minimas: borde -> primer puerto, entre puertos vecinos y ultimo puerto -> borde. espacios: (izq, der)
    de las etiquetas de cada linea, en orden."""
    return [10] + [max(d + i + 14, 20) for (_, d), (i, _) in zip(espacios, espacios[1:])] + [10]


def _repartir(x0, x1, espacios):
    """x de los puertos de un lado de la caja (x0 a x1), en orden. espacios: (izq, der) de las etiquetas de cada linea;
    si caben, cada linea deja a sus lados el ancho de sus etiquetas y lo que sobra se reparte parejo."""
    seps = _seps(espacios)
    sobra = (x1 - x0) - sum(seps)
    if sobra < 0:
        return [x0 + (x1 - x0) * (k + 1) / (len(espacios) + 1) for k in range(len(espacios))]
    xs, x = [], x0
    for sp in seps[:-1]:
        x += sp + sobra / (len(espacios) + 1)
        xs.append(x)
    return xs


def rutas(cajas, geometrias, espacios=None, copias=None):
    """Puntos intermedios de cada relacion, por (arriba, abajo, j) o (izquierda, derecha, j) si estan en la misma fila;
    j numera las lineas que unen el mismo par (copias: {frozenset(par): cuantas}, una si no se dice).
    Cada linea sale de un puerto propio del borde, corre por su carril en el canal libre entre filas (si sus puertos
    quedan alineados baja recta), cruza las filas intermedias por su hueco reservado (las del mismo par, en paralelo) y
    entra por otro puerto propio. Entre cajas de la misma fila sube al canal de arriba (en la primera
    fila baja al de abajo), corre y vuelve. En cada canal los carriles se ordenan (_orden_canal) para que las lineas no
    se crucen cuando se puede. espacios: {(caja, clave): (izq, der)} ancho de las etiquetas de ese extremo a cada lado
    de la linea, que se deja libre junto a su puerto."""
    salida, espacios, copias = {}, espacios or {}, copias or {}
    centro_x = lambda n: (cajas[n][0] + cajas[n][2]) / 2
    for geo in geometrias:
        tops, altos, capa, canales = geo['tops'], geo['altos'], geo['capa'], geo['canales']
        puertos, tramos = {}, []

        def puerto(n, lado, clave, hacia_x):
            puertos.setdefault((n, lado), []).append((clave, hacia_x))
        for (a, b), cadena in geo['cadenas'].items():
            n = copias.get(frozenset((a, b)), 1)
            for j in range(n):
                xs = [geo['huecos'][h] + (j - (n - 1) / 2) * CARRIL for h in cadena[1:-1]]
                tramos.append(('capas', (a, b, j), xs))
                puerto(a, 'abajo', (a, b, j), (xs[0] if xs else centro_x(b), j))
                puerto(b, 'arriba', (a, b, j), (xs[-1] if xs else centro_x(a), j))
        for a, b in geo['mismas']:
            lado = 'arriba' if capa[a] > 0 else 'abajo'
            for j in range(copias.get(frozenset((a, b)), 1)):
                tramos.append(('fila', (a, b, j), lado))
                # las del mismo par van una dentro de otra: la de j mayor, mas lejos de la otra caja en las dos
                for n, m in ((a, b), (b, a)):
                    puerto(n, lado, (a, b, j), (centro_x(m), -j if centro_x(m) > centro_x(n) else j))
        px, orden = {}, {}
        for (n, lado), lista in puertos.items():  # los puertos de un lado, repartidos en el orden de su destino
            x0, _, x1, _ = cajas[n]
            lista.sort(key=lambda t: t[1])
            esp = [espacios.get((n, c), (0, 0)) for c, _ in lista]
            for (clave, _), x in zip(lista, _repartir(x0, x1, esp)):
                px[(n, lado, clave)] = x
            orden[(n, lado)] = ([c for c, _ in lista], _seps(esp))

        def cabe(n, lado, clave, x):
            claves, seps = orden[(n, lado)]
            i = claves.index(clave)
            izq = px[(n, lado, claves[i - 1])] if i else cajas[n][0]
            der = px[(n, lado, claves[i + 1])] if i + 1 < len(claves) else cajas[n][2]
            return izq + seps[i] - 0.5 <= x <= der - seps[i + 1] + 0.5
        # una linea entre filas vecinas baja recta si sus dos puertos se pueden alinear sin quitar lugar a las demas; una
        # que salta filas sale y llega alineada con el hueco por el que cruza, si cabe
        for tipo, clave, extra in tramos:
            if tipo != 'capas':
                continue
            a, b, _ = clave
            ax, bx = px[(a, 'abajo', clave)], px[(b, 'arriba', clave)]
            if extra:
                if cabe(a, 'abajo', clave, extra[0]):
                    px[(a, 'abajo', clave)] = extra[0]
                if cabe(b, 'arriba', clave, extra[-1]):
                    px[(b, 'arriba', clave)] = extra[-1]
                continue
            for obj in ((bx, ax, (ax + bx) / 2) if abs(ax - bx) >= 0.5 else ()):
                if cabe(a, 'abajo', clave, obj) and cabe(b, 'arriba', clave, obj):
                    px[(a, 'abajo', clave)] = px[(b, 'arriba', clave)] = obj
                    break

        # cada linea, por canal: x donde su tramo vertical sube a la fila de arriba y donde baja a la de abajo
        pedidos, planes = {}, {}
        for tipo, clave, extra in tramos:
            a, b, _ = clave
            if tipo == 'fila':
                ax, bx = px[(a, extra, clave)], px[(b, extra, clave)]
                c = capa[a] - 1 if extra == 'arriba' else capa[a]
                ped = {'clave': clave, 'sube_a': [] if extra == 'arriba' else [ax, bx],
                       'baja_a': [ax, bx] if extra == 'arriba' else []}
                pedidos.setdefault(c, []).append(ped)
                planes[clave] = ('fila', extra, ax, bx, c)
                continue
            xs, ca, cb = extra, capa[a], capa[b]
            ax, bx = px[(a, 'abajo', clave)], px[(b, 'arriba', clave)]
            paso = [ax] + list(xs) + [bx]  # x del tramo vertical en cada fila, de a hasta b
            for k, c in enumerate(range(ca, cb)):
                pedidos.setdefault(c, []).append({'clave': clave, 'sube_a': [paso[k]], 'baja_a': [paso[k + 1]]})
            planes[clave] = ('capas', ax, bx, paso, ca, cb)
        carril_de = {}
        for c, lista in pedidos.items():
            alto = max(CARRIL, canales[c] - 52)
            for k, ped in enumerate(_orden_canal(lista)):
                carril_de[(ped['clave'], c)] = tops[c] + altos[c] + 26 + (k * CARRIL) % alto
        for clave, plan in planes.items():
            a, b, _ = clave
            if plan[0] == 'fila':
                _, lado, ax, bx, c = plan
                y = carril_de[(clave, c)]
                borde = (lambda n: cajas[n][1] - 8) if lado == 'arriba' else (lambda n: cajas[n][3] + 8)
                salida[clave] = _sin_colineales([(ax, borde(a)), (ax, y), (bx, y), (bx, borde(b))])
                continue
            _, ax, bx, paso, ca, cb = plan
            medios = [(ax, cajas[a][3] + 8)]
            for k, c in enumerate(range(ca, cb)):
                y = carril_de[(clave, c)]
                medios += [(paso[k], y), (paso[k + 1], y)]
            medios.append((bx, cajas[b][1] - 8))
            salida[clave] = _sin_colineales(medios)
    return salida


# ---------------------------------------------------------------------------
# Diagramas
# ---------------------------------------------------------------------------

def dibujar(doc, dg, elementos, relaciones, op, contexto=None):
    """Vistas de los elementos y de las relaciones entre ellos. contexto: {id: paquete} de clases de otros paquetes
    que se dibujan compactas, con sus relaciones hacia los elementos. Devuelve el resumen del diagrama."""
    contexto = contexto or {}
    principales = {el['_id'] for el in elementos}
    elementos = list(elementos) + [doc.ids[i] for i in sorted(contexto, key=lambda i: doc.name_of(i))]
    ids = {el['_id'] for el in elementos}
    # "(from ...)" en la caja de una clase anidada (su clase externa) y en las que se llaman igual que otra del
    # diagrama (su paquete en el programa), para distinguirlas
    externa = {}
    nombres = [el.get('name') for el in elementos if el['_id'] not in contexto]
    for el in elementos:
        padre = doc.ids.get(doc.parent.get(el['_id']))
        if padre and padre.get('_type') in VISTA_DE:
            externa[el['_id']] = padre.get('name', '')
        elif padre and el['_id'] not in contexto and nombres.count(el.get('name')) > 1:
            ruta = []
            while padre and padre.get('_type') == 'UMLPackage' and doc.ids.get(doc.parent.get(padre['_id']), {}).get('_type') == 'UMLPackage':
                ruta.insert(0, padre.get('name', ''))
                padre = doc.ids.get(doc.parent.get(padre['_id']))
            if ruta:
                externa[el['_id']] = '.'.join(ruta)
    tam = {el['_id']: medir(doc, el, op, contexto.get(el['_id']), externa.get(el['_id'])) for el in elementos}
    rels, aristas = [], []
    for rel, _, _ in relaciones:
        if rel['_type'] == 'UMLAssociation':
            o, d = rel['end1']['reference']['$ref'], rel['end2']['reference']['$ref']
        else:
            o, d = rel['source']['$ref'], rel['target']['$ref']
        if o not in ids or d not in ids or (o not in principales and d not in principales):
            continue
        rels.append((rel, o, d))
        if o != d:
            # la clase base arriba de sus derivadas; la que tiene el campo arriba de la referida
            aristas.append((d, o, True) if rel['_type'] in ('UMLGeneralization', 'UMLInterfaceRealization') else (o, d, False))
    # el acomodo se hace por el orden de los elementos (por nombre), no por sus ids, que cambian en cada corrida: asi el
    # mismo programa da siempre el mismo diagrama
    clave = {el['_id']: f'{i:05d}' for i, el in enumerate(elementos)}
    # las lineas que unen el mismo par (varios campos del mismo tipo) se rutean cada una por su lado, en paralelo
    rels.sort(key=lambda r: (r[0]['_type'] not in ('UMLGeneralization', 'UMLInterfaceRealization'), r[0]['_type']))
    copias, numero = {}, []
    for _, o, d in rels:
        par = frozenset((clave[o], clave[d]))
        numero.append(copias.get(par, 0))
        copias[par] = numero[-1] + 1
    aristas = list(dict.fromkeys((clave[a], clave[b], f) for a, b, f in aristas))
    # a la derecha de una caja con una asociacion consigo misma queda lugar para el lazo y sus etiquetas
    lazo = {}
    for rel, o, d in rels:
        if o == d and rel['_type'] == 'UMLAssociation':
            textos = [('+' + e['name']) if e.get('name') else '' for e in (rel['end1'], rel['end2'])]
            textos += [e.get('multiplicity', '') for e in (rel['end1'], rel['end2'])]
            lazo[o] = max(lazo.get(o, 0), 40 + max(_ancho_etiqueta(t) for t in textos))

    def acomodo():
        return acomodar(sorted(clave.values()), {clave[n]: (w + lazo.get(n, 0), h) for n, (w, h) in tam.items()},
                        aristas, copias)
    posiciones, geometrias = acomodo()
    sentido = {frozenset(par): par for geo in geometrias for par in list(geo['cadenas']) + geo['mismas']}
    # cada extremo de asociacion deja junto a su puerto el ancho del rol (izquierda) y la multiplicidad (derecha)
    espacios = {}
    for (rel, o, d), k in zip(rels, numero):
        par = sentido.get(frozenset((clave[o], clave[d])))
        if rel['_type'] == 'UMLAssociation' and o != d and par is not None:
            for n, e in ((o, rel['end1']), (d, rel['end2'])):
                espacios[(clave[n], par + (k,))] = (_ancho_etiqueta(('+' + e['name']) if e.get('name') else ''),
                                                    _ancho_etiqueta(e.get('multiplicity', '')))
    # una caja con muchas lineas de un lado se ensancha (hasta ANCHO_MAX) para que quepan sus etiquetas junto a sus
    # puertos; las filas y su orden no dependen del ancho, asi que basta acomodar otra vez
    lados = {}
    for geo in geometrias:
        for a, b in list(geo['cadenas']) + geo['mismas']:
            la, lb = ('abajo', 'arriba') if (a, b) in geo['cadenas'] else ('arriba', 'arriba') if geo['capa'][a] else ('abajo', 'abajo')
            for k in range(copias.get(frozenset((a, b)), 1)):
                lados.setdefault((a, la), []).append(espacios.get((a, (a, b, k)), (0, 0)))
                lados.setdefault((b, lb), []).append(espacios.get((b, (a, b, k)), (0, 0)))
    de_clave, ancho = {c: i for i, c in clave.items()}, {}
    for (n, _), lista in lados.items():
        falta = min(ANCHO_MAX, 20 + sum(i + d for i, d in lista) + 14 * (len(lista) - 1))
        if falta > max(ancho.get(n, 0), tam[de_clave[n]][0]):
            ancho[n] = falta
    if ancho:
        for n, w in ancho.items():
            tam[de_clave[n]] = (w, tam[de_clave[n]][1])
        posiciones, geometrias = acomodo()
    vistas = {}
    for el in elementos:
        x, y = posiciones[clave[el['_id']]]
        vistas[el['_id']] = vista_clasificador(doc, dg, el, x, y, *tam[el['_id']], op, contexto.get(el['_id']),
                                               externa.get(el['_id']))
    cajas = {n: _caja(v) for n, v in vistas.items()}
    medios_de = rutas({clave[n]: c for n, c in cajas.items()}, geometrias, espacios, copias)
    cruzan, lineas = [], []
    for (rel, o, d), k in zip(rels, numero):
        medios, par = [], frozenset((clave[o], clave[d]))
        if o != d and par in sentido:
            medios = list(medios_de.get(sentido[par] + (k,), []))
            if sentido[par] != (clave[o], clave[d]):
                medios = medios[::-1]
        elif o == d and 0 < k < 4:  # otro lazo en la misma caja (Nodo izq, Nodo der): en otra esquina, sin encimarse
            l, t, w, h = (vistas[o][c] for c in ('left', 'top', 'width', 'height'))
            prueba = [[(l + w + 30, t + h * 3 / 4), (l + w + 30, t + h + 30), (l + w * 3 / 4, t + h + 30)],
                      [(l + w / 4, t + h + 30), (l - 30, t + h + 30), (l - 30, t + h * 3 / 4)],
                      [(l - 30, t + h / 4), (l - 30, t - 30), (l + w / 4, t - 30)]][k - 1]
            otras = [c for n, c in cajas.items() if n != o]
            if min(min(p) for p in prueba) >= 0 and not _cruces(_puntos({'points': M.ruta(vistas[o], vistas[d], prueba)}), otras):
                medios = [(round(x), round(y)) for x, y in prueba]
        if rel['_type'] == 'UMLAssociation':
            v = M.vista_asociacion(doc, dg, rel, vistas[o], vistas[d], medios)
        else:
            v = vista_relacion(doc, dg, rel, vistas[o], vistas[d], medios)
        lineas.append(v)
        otras = [c for n, c in cajas.items() if n not in (o, d)]
        if o != d and _cruces(_puntos(v), otras):
            cruzan.append(f'{doc.name_of(o)} - {doc.name_of(d)} ({rel["_type"]})')
    etiquetas_extremos(lineas, {vistas[n]['_id']: c for n, c in cajas.items()})
    return {'diagrama': dg.get('name'), 'id': dg['_id'], 'cajas': len(vistas), 'lineas': len(rels),
            'clases_de_otros_paquetes': sorted(doc.name_of(i) for i in contexto),
            'lineas_que_cruzan_cajas': cruzan,
            'ancho': max((c[2] for c in cajas.values()), default=0) + MARGEN,
            'alto': max((c[3] for c in cajas.values()), default=0) + MARGEN}


def programa_a_diagrama(doc, ruta_codigo, lenguaje='java', paquete=None, diagrama=None, diagrama_por=None,
                        atributos=True, metodos=True, solo_publicos=False, omitir_accesores=False, asociaciones=True,
                        dependencias=False, incluir_pruebas=False, reemplazar=False, por_defecto=False):
    """Lee el programa, crea su modelo en un paquete nuevo y dibuja su diagrama de clases: uno para todo el programa o
    uno por paquete (cada uno con las clases de otros paquetes con las que se relaciona). Sin diagrama_por se elige
    solo: por paquete si el programa tiene mas de LIMITE_UN_DIAGRAMA clases repartidas en varios paquetes."""
    if diagrama_por not in (None, 'programa', 'paquete'):
        raise MdjError('diagrama_por debe ser "programa" o "paquete"')
    clases, repetidas = leer_programa(ruta_codigo, lenguaje, incluir_pruebas)
    if not clases:
        raise MdjError(f'No se encontraron clases{" de " + lenguaje if lenguaje != "auto" else ""} en {ruta_codigo}')
    carpeta = os.path.abspath(os.path.expanduser(ruta_codigo))
    raiz_nombre = paquete or os.path.splitext(os.path.basename(carpeta.rstrip(os.sep)))[0] or 'Programa'
    modelo = M.modelo_raiz(doc)
    previo = [o for o in modelo.get('ownedElements', []) if o.get('_type') == 'UMLPackage' and o.get('name') == raiz_nombre]
    if previo:
        if not reemplazar:
            raise MdjError(f'Ya existe el paquete "{raiz_nombre}" en el modelo. Usa reemplazar=true para rehacerlo '
                           f'o indica otro nombre en "paquete".')
        for pk in previo:
            M.borrar(doc, pk)
        doc.reindex()
    op = {'atributos': atributos, 'metodos': metodos, 'solo_publicos': solo_publicos, 'omitir_accesores': omitir_accesores,
          'asociaciones': asociaciones, 'dependencias': dependencias}
    hecho = construir(doc, clases, raiz_nombre, op)
    elems, relaciones = hecho['elementos'], hecho['relaciones']
    paquete_de = {el['_id']: clases[q].get('paquete') or '' for q, el in elems.items()}
    automatico = diagrama_por is None
    if automatico:
        diagrama_por = 'paquete' if len(elems) > LIMITE_UN_DIAGRAMA and len(set(paquete_de.values())) > 1 else 'programa'
    grupos = []
    if diagrama_por == 'programa':
        grupos.append((diagrama or 'Diagrama de clases', hecho['raiz'], list(elems.values()), {}))
    else:
        por_pk = {}
        for el in elems.values():
            por_pk.setdefault(paquete_de[el['_id']], []).append(el)
        for pk_nombre in sorted(por_pk):
            propios = {el['_id'] for el in por_pk[pk_nombre]}
            contexto = {}
            for rel, _, _ in relaciones:  # clases de otros paquetes relacionadas directamente
                if rel['_type'] == 'UMLAssociation':
                    o, d = rel['end1']['reference']['$ref'], rel['end2']['reference']['$ref']
                else:
                    o, d = rel['source']['$ref'], rel['target']['$ref']
                for a, b in ((o, d), (d, o)):
                    if a in propios and b not in propios:
                        contexto[b] = paquete_de[b] or raiz_nombre
            grupos.append((pk_nombre or raiz_nombre, hecho['paquetes'][pk_nombre], por_pk[pk_nombre], contexto))
    diagramas = []
    for i, (nombre, dueno, elementos, contexto) in enumerate(grupos):
        dg = M.crear_diagrama(doc, 'clases', nombre, dentro_de=dueno['_id'], por_defecto=por_defecto and i == 0)
        diagramas.append(dibujar(doc, dg, sorted(elementos, key=lambda e: e.get('name', '')), relaciones, op, contexto))
    doc.reindex()
    cuenta = {}
    for el in elems.values():
        cuenta[el['_type']] = cuenta.get(el['_type'], 0) + 1
    rels = {}
    for rel, _, _ in relaciones:
        rels[rel['_type']] = rels.get(rel['_type'], 0) + 1
    return {'paquete': raiz_nombre, 'lenguaje': lenguaje, 'diagrama_por': diagrama_por,
            **({'nota': f'El programa tiene {len(elems)} clases en varios paquetes: se hizo un diagrama por paquete '
                        f'(con diagrama_por="programa" queda uno solo).'} if automatico and diagrama_por == 'paquete' else {}),
            'diagramas': diagramas,
            'clases': cuenta.get('UMLClass', 0), 'interfaces': cuenta.get('UMLInterface', 0),
            'enumeraciones': cuenta.get('UMLEnumeration', 0),
            'paquetes_del_programa': sorted(k for k in hecho['paquetes'] if k),
            'paquetes_con_clases': sorted({p for p in paquete_de.values() if p}),
            'asociaciones': rels.get('UMLAssociation', 0), 'generalizaciones': rels.get('UMLGeneralization', 0),
            'realizaciones': rels.get('UMLInterfaceRealization', 0), 'dependencias': rels.get('UMLDependency', 0),
            'herencia_externa': hecho['herencia_externa'], 'clases_repetidas_omitidas': repetidas,
            **({'tipos_ambiguos': hecho['tipos_ambiguos'],
                'nota_ambiguos': 'Esos tipos corresponden a varias clases del programa y no se pudo saber cual por sus '
                                 'imports: quedaron como atributo, sin asociacion.'} if hecho['tipos_ambiguos'] else {})}
