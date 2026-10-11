# Coherencia entre los diagramas de secuencia y el modelo de clases. Solo lee: no escribe nada.
# mdj_validar ya revisa los mensajes por estereotipo (OOSE), entity->entity sin asociacion, consultas sin reply y
# vistas incompletas; eso no se repite aqui. Aqui se cruza cada secuencia con el modelo y sus relaciones:
#  1. lifelines con tipo y que ese tipo exista (y, si se da un diagrama de clases, que este dibujado en el)
#  2. cada mensaje entre tipos distintos necesita una relacion en el modelo (asociacion, herencia, dependencia o
#     realizacion); si la asociacion solo navega al reves o no navega, es aviso
#  3. los mensajes al control (o a toda clase con operaciones) deben ser operaciones suyas con sus parametros
#  4. argumentos que no salen de ningun lado (avisos)
#  5. cada reply regresa a quien hizo la llamada, mientras esa llamada sigue abierta (pila de llamadas; en un
#     fragmento alt o par, una reply en otra rama no se marca)
#  6. clases del diagrama de clases que no aparecen en ninguna secuencia
import difflib
import re
import unicodedata

from . import mdj as M
from .mdj import MdjError

METODOS = ('no', 'control', 'todos')
# primera palabra de un nombre que agrupa valores (datosObra junta nombreObra, direccionObra...); id va con cualquiera
GENERICOS = {'datos', 'dato', 'info', 'informacion', 'lista', 'listado', 'conjunto', 'coleccion', 'id', 'ids'}
PALABRAS_LITERAL = {'true', 'false', 'null', 'nil', 'none', 'verdadero', 'falso', 'nulo', 'this', 'self', 'new'}
# palabras que no cuentan solas dentro de un nombre ("fecha de inicio", "Servicio de Correo")
VACIAS = {'de', 'del', 'la', 'las', 'el', 'los', 'lo', 'y', 'e', 'o', 'u', 'a', 'al', 'en', 'con', 'por', 'para',
          'que', 'sin'}
TIPOS_CLASIFICADOR = ('UMLClass', 'UMLActor', 'UMLInterface', 'UMLEnumeration', 'UMLDataType', 'UMLPrimitiveType',
                      'UMLSignal', 'UMLComponent', 'UMLSubsystem', 'UMLNode', 'UMLArtifact')
# clasificadores que no tipan una lifeline
NO_TIPAN = ('UMLStereotype', 'UMLTemplateParameter', 'UMLNaryAssociationNode', 'UMLUseCase', 'UMLCollaboration',
            'UMLInformationItem')
DEPENDENCIAS = ('UMLDependency', 'UMLAbstraction', 'UMLRealization', 'UMLInterfaceRealization',
                'UMLComponentRealization', 'UMLUsage')
ROBUSTEZ = ('actor', 'boundary', 'control', 'entity')
# pares que mdj_validar acepta en una secuencia de robustez; los demas ya los marca como mensaje no valido
VALIDOS_OOSE = {('actor', 'boundary'), ('boundary', 'control'), ('control', 'entity'), ('entity', 'control'),
                ('control', 'boundary'), ('boundary', 'actor'), ('entity', 'entity')}
NO_LLAMAN = ('createMessage', 'deleteMessage', 'asynchSignal')  # no llaman a una operacion del receptor
ASINCRONOS = ('asynchCall', 'asynchSignal')  # quien los manda no espera: sigue sin que regresen

_NUMERO = re.compile(r'[-+]?\$?\d[\d,]*(?:\.\d+)?(?:\s*(?:%|[^\W\d_]{1,6}))?')  # 16%, $1,500, 3.50 m, 120 HP
_TEXTO = re.compile(r'''(["']).*\1''', re.S)
_CONSTANTE = re.compile(r'[A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ0-9_]+')
_CLAVE = re.compile(r'[A-Za-z0-9]+(?:[-/.:][A-Za-z0-9]+)+')  # M-001, FOL-89241, 10/09/2026, 08:30
_IDENT = re.compile(r'[^\W\d][\w ]*')                          # nombre (con espacios: "fecha de inicio")
_RUTA = re.compile(r'[^\W\d]\w*(?:\.[^\W\d]\w*)+')             # cliente.rfc
_PALABRA = re.compile(r'[A-ZÁÉÍÓÚÑÜ]+(?![a-záéíóúñü])|[A-ZÁÉÍÓÚÑÜ]?[a-záéíóúñü]+|\d+')
_ACCESOR = re.compile(r'(?:get|set|is)(?=[A-Z_\d])')         # getTotal, setEstado, isActivo
_MILES_ANTES = re.compile(r'[-+]?\$?\d{1,3}(?:,\d{3})*')    # antes de una coma de miles: $1 o $1,500
_MILES_DESPUES = re.compile(r'\d{3}(?!\d)')                 # despues: tres digitos justos


# ---------------------------------------------------------------------------
# Nombres
# ---------------------------------------------------------------------------

def _txt(v):
    """El valor si es texto; si no (archivo editado a mano con un numero o null), texto vacio."""
    return v if isinstance(v, str) else ''


def _norm(texto):
    """Sin acentos, sin mayusculas, sin espacios ni guiones bajos."""
    t = unicodedata.normalize('NFKD', _txt(texto))
    return ''.join(c for c in t if not unicodedata.combining(c) and c not in '_ ').casefold()


def _palabras(nombre):
    """Partes de un nombre: 'BC_ServicioCorreo' -> ['bc', 'servicio', 'correo']."""
    return [_norm(p) for p in _PALABRA.findall(_txt(nombre))]


def _variantes(n):
    """El nombre normalizado y sus posibles singulares (accesorios -> accesorio, unidades -> unidad)."""
    v = {n}
    if len(n) > 3 and n.endswith('s'):
        v.add(n[:-1])
        if len(n) > 4 and n.endswith('es'):
            v.add(n[:-2])
    return v


def _es_literal(a):
    a = (a or '').strip()
    return (not a or a in ('...', '…') or bool(_NUMERO.fullmatch(a)) or bool(_TEXTO.fullmatch(a))
            or bool(_CONSTANTE.fullmatch(a)) or (bool(_CLAVE.fullmatch(a)) and any(c.isdigit() for c in a))
            or _norm(a) in PALABRAS_LITERAL)


def _separar(texto):
    """Argumentos separados por las comas de primer nivel (respeta parentesis, corchetes, comillas y la coma de miles
    de un monto: $1,500.00 es un solo argumento)."""
    out, actual, nivel, comilla = [], [], 0, None
    texto = texto or ''
    for i, c in enumerate(texto):
        if comilla:
            actual.append(c)
            if c == comilla:
                comilla = None
            continue
        if c in '"\'':
            comilla = c
        elif c in '([{':
            nivel += 1
        elif c in ')]}' and nivel:
            nivel -= 1
        elif c == ',' and nivel == 0 and not (_MILES_ANTES.fullmatch(''.join(actual).strip())
                                              and _MILES_DESPUES.match(texto, i + 1)):
            out.append(''.join(actual).strip())
            actual = []
            continue
        actual.append(c)
    out.append(''.join(actual).strip())
    return [x for x in out if x]


def _ref(v):
    return v.get('$ref') if isinstance(v, dict) else None


def _partes(doc, m):
    """(operacion, argumentos o None si el mensaje no los muestra, asignacion, texto como se ve en el diagrama)."""
    nombre = _txt(m.get('name')).strip()
    if not nombre:  # sin nombre, StarUML muestra el de la operacion asignada
        nombre = _txt((doc.ids.get(_ref(m.get('signature'))) or {}).get('name')).strip()
    extra = m.get('arguments').strip() if isinstance(m.get('arguments'), str) else ''
    asignacion = m.get('assignmentTarget').strip() if isinstance(m.get('assignmentTarget'), str) else ''
    texto = nombre + (f'({extra})' if extra and '(' not in nombre else '')
    cuerpo = nombre
    am = re.fullmatch(r'([^\W\d][\w.]*)\s*:?=(?!=)\s*(.+)', cuerpo, re.S)  # x = op(...)
    if am:
        asignacion = asignacion or am.group(1)
        cuerpo = am.group(2).strip()
    i = cuerpo.find('(')
    if i < 0:
        return cuerpo, (_separar(extra) if extra else None), asignacion, texto
    nivel, fin = 0, len(cuerpo)
    for j in range(i, len(cuerpo)):
        if cuerpo[j] == '(':
            nivel += 1
        elif cuerpo[j] == ')':
            nivel -= 1
            if nivel == 0:
                fin = j
                break
    return cuerpo[:i].strip(), _separar(cuerpo[i + 1:fin]), asignacion, texto


def _nombres_en(arg):
    """Nombres de un argumento que tienen que salir de algun lado. 'nombre=valor' se toma por el valor y
    'nombre: Tipo' por el nombre; de 'cliente.rfc' cuenta cliente; los valores fijos no llevan nombres."""
    a = arg.strip()
    m = re.fullmatch(r'([^\W\d]\w*)\s*=(?!=)\s*(.+)', a, re.S)
    if m:
        a = m.group(2).strip()
    if _es_literal(a):
        return []
    m = re.fullmatch(r'([^\W\d]\w*)\s*:\s*[^\W\d][\w.\[\]<>, ]*', a)
    if m:
        a = m.group(1)
    if _IDENT.fullmatch(a):
        return [a.strip()]
    if _RUTA.fullmatch(a):
        partes = a.split('.')
        if _norm(partes[0]) in ('this', 'self'):  # this.folio: cuenta folio
            return [partes[1]]
        return [] if _norm(partes[0]) in PALABRAS_LITERAL else [partes[0]]
    sin_textos = re.sub(r'(["\']).*?\1', ' ', a)
    return [x for x in re.findall(r'(?<![\w.])[^\W\d]\w*\b(?!\s*\()', sin_textos) if not _es_literal(x)]


def _recibe(arg):
    """Lo que el receptor sabe despues de recibir el argumento: sus nombres y, en 'nombre=valor' o 'nombre: Tipo',
    tambien el nombre."""
    m = re.match(r'\s*([^\W\d]\w*)\s*(?:=(?!=)|:)', arg)
    return _nombres_en(arg) + ([m.group(1)] if m else [])


class _Nombres:
    """Nombres conocidos: enteros (con sus singulares) y palabras sueltas (para nombres compuestos)."""

    def __init__(self):
        self.completos, self.partes, self.originales = set(), set(), []

    def agregar(self, nombre):
        if not nombre or not isinstance(nombre, str):
            return
        self.originales.append(nombre)
        self.completos |= _variantes(_norm(nombre))
        for p in _palabras(nombre):
            self.partes |= _variantes(p)


def _explicado(nombre, completos, partes, sueltas=frozenset()):
    """Si el nombre sale de algo conocido: entero, o compuesto de palabras conocidas (costosAccesorios), o un
    nombre que agrupa valores conocidos (datosObra). Las palabras como 'de' no cuentan. sueltas: palabras que
    cuentan solas (partes de los nombres que el emisor recibio: solicitado de equipoSolicitado)."""
    if _variantes(_norm(nombre)) & completos:
        return True
    todas = _palabras(nombre)
    pal = [p for p in todas if p not in VACIAS]
    if not pal:
        return False
    if len(pal) == 1:  # "la orden": cuenta la palabra que queda
        v = _variantes(pal[0])
        return bool(v & sueltas) or (len(todas) > 1 and bool(v & completos))
    if pal[0] in GENERICOS:
        return all(_variantes(p) & partes for p in pal[1:])
    return all(_variantes(p) & GENERICOS or _variantes(p) & completos for p in pal)


def _pista(nombre, originales):
    """Un nombre conocido que se parece (empieza igual o casi igual), para sugerirlo."""
    n = _norm(nombre)
    vistos = {}
    for o in originales:
        vistos.setdefault(_norm(o), o)
    for k, o in vistos.items():
        if len(n) >= 4 and k.startswith(n) and k != n:
            return o
    cerca = difflib.get_close_matches(n, list(vistos), n=1, cutoff=0.8)
    return vistos[cerca[0]] if cerca else None


# ---------------------------------------------------------------------------
# Indice del modelo
# ---------------------------------------------------------------------------

class _Indice:
    """Lo que hace falta del modelo, calculado una vez: tipos, superiores, relaciones, atributos y nombres."""

    def __init__(self, doc):
        self.doc = doc
        self.tipos, self.por_nombre, self.por_clave = {}, {}, {}
        self.superiores = {}        # id -> superclases directas e interfaces que realiza
        self.asociaciones = []      # (a, b, extremo a, extremo b)
        self.dirigidas = []         # (origen, destino) de dependencias y realizaciones
        self.enum_literales = set()
        self.globales = set()       # nombres de clase y roles de asociacion, normalizados y con singulares
        self._perfil, self._linaje, self._alcance, self._cerca = {}, {}, {}, {}
        for o in doc.ids.values():
            if not o:
                continue
            t = o.get('_type', '')
            if t == 'UMLAssociation':
                e1, e2 = (e if isinstance(e, dict) else {} for e in (o.get('end1'), o.get('end2')))
                a, b = _ref(e1.get('reference')), _ref(e2.get('reference'))
                if a and b:
                    self.asociaciones.append((a, b, e1, e2))
                for e in (e1, e2):
                    if _txt(e.get('name')):
                        self.globales |= _variantes(_norm(e['name']))
            elif t == 'UMLGeneralization':
                s, d = _ref(o.get('source')), _ref(o.get('target'))
                if s and d:
                    self.superiores.setdefault(s, set()).add(d)
            elif t in DEPENDENCIAS or M.es_subtipo(t, 'UMLDependency'):
                s, d = _ref(o.get('source')), _ref(o.get('target'))
                if s and d:
                    self.dirigidas.append((s, d))
                    if 'Realization' in t and (doc.ids.get(d) or {}).get('_type') == 'UMLInterface':
                        self.superiores.setdefault(s, set()).add(d)
            elif t == 'UMLEnumerationLiteral':
                self.enum_literales.add(_norm(o.get('name')))
            elif self._tipa(o):
                self.tipos[o['_id']] = o
                if _txt(o.get('name')):
                    self.por_nombre.setdefault(o['name'], []).append(o)
                    self.por_clave.setdefault(_norm(o['name']), []).append(o)
                    self.globales |= _variantes(_norm(o['name']))
        # primera palabra de cada nombre de clase (requisitos -> RequisitoRenta, orden -> OrdenEntrega); solo cuentan
        # las de las clases que tiene a la mano el mensaje. Las de boundaries, controles y actores no (registro de
        # BC_RegistroSolicitudRenta no es un dato), ni las palabras que siguen (renta de SolicitudRenta). rotulos:
        # las palabras de boundaries, controles y actores, que solas no nombran un dato
        self.palabras, self.rotulos = {}, set()
        for i, o in self.tipos.items():
            pal = [p for p in _palabras(o.get('name')) if p not in VACIAS]
            if doc.kind(o) in ('boundary', 'control', 'actor'):
                self.rotulos |= {v for p in pal for v in _variantes(p)}  # renta, registro, confirmacion...
                self.palabras[i] = set()
            else:
                self.palabras[i] = _variantes(pal[0]) if pal and len(pal[0]) >= 3 else set()

    def _tipa(self, o):
        t = o.get('_type', '')
        return ((t in TIPOS_CLASIFICADOR or M.es_subtipo(t, 'UMLClassifier'))
                and not any(M.es_subtipo(t, x) for x in NO_TIPAN) and t not in NO_TIPAN
                and not self._en_perfil(o['_id']))

    def _en_perfil(self, i):
        if i not in self._perfil:
            p, res, vistos = self.doc.parent.get(i), False, set()
            while p and p not in vistos:
                vistos.add(p)
                if (self.doc.ids.get(p) or {}).get('_type') == 'UMLProfile':
                    res = True
                    break
                p = self.doc.parent.get(p)
            self._perfil[i] = res
        return self._perfil[i]

    def linaje(self, i):
        """El tipo y todos sus superiores (herencia directa e indirecta e interfaces que realiza)."""
        if i not in self._linaje:
            vistos, pila = [], [i]
            while pila:
                x = pila.pop()
                if x not in vistos:
                    vistos.append(x)
                    pila.extend(sorted(self.superiores.get(x, ())))
            self._linaje[i] = vistos
        return self._linaje[i]

    def es_ancestro(self, sup, i):
        return sup != i and sup in self.linaje(i)

    def relacion(self, s, t):
        """'ok', 'contraria' (las asociaciones que hay solo navegan de t hacia s), 'cerrada' (no navegan en ningun
        sentido) o 'ninguna'. Cuentan las relaciones heredadas: lo que tiene la superclase lo tienen sus subclases."""
        ls, lt = set(self.linaje(s)), set(self.linaje(t))
        if s in lt or t in ls:
            return 'ok'
        for a, b in self.dirigidas:
            if (a in ls and b in lt) or (a in lt and b in ls):
                return 'ok'
        res = 'ninguna'
        for a, b, ea, eb in self.asociaciones:
            for x, y, ex, ey in ((a, b, ea, eb), (b, a, eb, ea)):
                if x in ls and y in lt:
                    if _navega(ex, ey):
                        return 'ok'
                    if _navega(ey, ex):
                        res = 'contraria'
                    elif res == 'ninguna':
                        res = 'cerrada'
        return res

    def atributos(self, i):
        return [a.get('name') for x in self.linaje(i) for a in (self.doc.ids.get(x) or {}).get('attributes') or []
                if isinstance(a, dict) and _txt(a.get('name'))]

    def asociadas(self, i):
        lin = set(self.linaje(i))
        out = []
        for a, b, _, _ in self.asociaciones:
            for x, y in ((a, b), (b, a)):
                if x in lin and y not in out:
                    out.append(y)
        return out

    def operaciones(self, i):
        return [op for x in self.linaje(i) for op in (self.doc.ids.get(x) or {}).get('operations') or []
                if isinstance(op, dict) and op.get('_id')]

    def palabras_de(self, ids):
        out = set()
        for i in ids:
            out |= self.palabras.get(i, set())
        return out

    def alcance(self, s, t):
        """Nombres que tiene a la mano un mensaje de s a t: atributos de los dos y de las clases asociadas a s."""
        if (s, t) not in self._alcance:
            n = _Nombres()
            for x in self.atributos(s) + self.atributos(t) + [a for y in self.asociadas(s) for a in self.atributos(y)]:
                n.agregar(x)
            self._alcance[(s, t)] = n
        return self._alcance[(s, t)]

    def cerca(self, s, t):
        """Palabras de los nombres de las clases cercanas al mensaje: las dos, sus superiores y sus asociadas."""
        if (s, t) not in self._cerca:
            ids = set(self.linaje(s)) | set(self.linaje(t)) | set(self.asociadas(s)) | set(self.asociadas(t))
            self._cerca[(s, t)] = self.palabras_de(ids)
        return self._cerca[(s, t)]


def _flecha(e):
    v = e.get('navigable')
    if v in (True, 'navigable'):
        return True
    if v in (False, 'notNavigable', 'nonNavigable', 'nonnavigable'):
        return False
    return None


def _navega(origen, destino):
    """Si una asociacion permite ir del extremo origen al extremo destino. Sin flechas navega en los dos sentidos;
    con flecha solo en el origen, no llega al destino."""
    d = _flecha(destino)
    return d if d is not None else _flecha(origen) is not True


def _parametros_entrada(op):
    return [p for p in op.get('parameters') or [] if isinstance(p, dict) and p.get('direction') in (None, 'in', 'inout')]


def _nombres_ops(ops):
    """Nombre de cada operacion para los reportes; con parametros si hay otra con el mismo nombre (sobrecarga)."""
    cuenta = {}
    for op in ops:
        cuenta[_txt(op.get('name'))] = cuenta.get(_txt(op.get('name')), 0) + 1
    return {op['_id']: (f'{_txt(op.get("name"))}({", ".join(_txt(p.get("name")) for p in _parametros_entrada(op))})'
                        if cuenta[_txt(op.get('name'))] > 1 else _txt(op.get('name'))) for op in ops}


def _cuantos(k, cosa='argumento'):
    return f'{k} {cosa}' + ('' if k == 1 else 's')


def _recibe_ops(ops):
    """Lo que reciben las operaciones, para el aviso de argumentos: '2 (tipoDecision, observaciones)', 'ninguno',
    o varias opciones si hay sobrecarga: '1 (folio) o 2 (folio, fecha)'."""
    por_cuenta = {}
    for o in ops:
        ps = _parametros_entrada(o)
        por_cuenta.setdefault(len(ps), ', '.join(_txt(p.get('name')) or '?' for p in ps))
    return ' o '.join(f'{k} ({nombres})' if k else 'ninguno' for k, nombres in sorted(por_cuenta.items()))


def _lo_marca_validar(ks, kt, relacion, con_vistas):
    """Si mdj_validar ya reporta el mensaje: par no valido en OOSE o entity->entity sin asociacion. mdj_validar
    solo revisa las secuencias que tienen vistas; las que no, se revisan aqui completas."""
    if not con_vistas or ks not in ROBUSTEZ or kt not in ROBUSTEZ:
        return False
    return (ks, kt) not in VALIDOS_OOSE or ((ks, kt) == ('entity', 'entity') and relacion == 'ninguna')


def _puntos(texto):
    """'x1:y1;x2:y2' de una vista de mensaje -> [(x1, y1), (x2, y2)]; [] si no se puede leer."""
    out = []
    for par in _txt(texto).split(';'):
        xy = par.split(':')
        try:
            out.append((float(xy[0]), float(xy[1])))
        except (ValueError, IndexError):
            return []
    return out


def _num(v, *campos):
    return all(isinstance(v.get(c), (int, float)) and not isinstance(v.get(c), bool) for c in campos)


def _fragmentos(dg, it):
    """(si la interaccion tiene fragmentos combinados, {mensaje dibujado: {fragmento: operando o None}}). Los
    mensajes no dicen en que operando van; se saca del dibujo: el operando cuya franja contiene la linea del
    mensaje, dentro del ancho del fragmento."""
    hay, pila = False, [it.get('fragments')]
    while pila and not hay:
        x = pila.pop()
        if isinstance(x, list):
            pila.extend(x)
        elif isinstance(x, dict):
            hay = 'CombinedFragment' in _txt(x.get('_type'))
            pila.extend(v for k, v in x.items() if k != '_parent' and isinstance(v, (list, dict)))
    if not hay:
        return False, {}
    marcos, lineas, pila = [], {}, list(dg.get('ownedViews') or [])
    while pila:
        v = pila.pop()
        if not isinstance(v, dict):
            continue
        t = v.get('_type')
        if t == 'UMLCombinedFragmentView' and _num(v, 'left', 'top', 'width', 'height'):
            ops, sub = [], list(v.get('subViews') or [])
            while sub:
                w = sub.pop()
                if isinstance(w, dict):
                    if w.get('_type') == 'UMLInteractionOperandView' and _num(w, 'top', 'height'):
                        ops.append((w['top'], w['top'] + w['height'], _ref(w.get('model')) or w.get('_id')))
                    sub.extend(w.get('subViews') or [])
            marcos.append((_ref(v.get('model')) or v.get('_id'), v['left'], v['left'] + v['width'], v['top'],
                           v['top'] + v['height'], ops))
        elif t == 'UMLSeqMessageView' and _ref(v.get('model')):
            pts = _puntos(v.get('points'))
            if pts:
                lineas[_ref(v['model'])] = pts
        pila.extend(v.get('subViews') or [])
    ubic = {}
    for mid, pts in lineas.items():
        xs, y = [p[0] for p in pts], pts[0][1]
        ubic[mid] = {}
        for f, izq, der, arriba, abajo, ops in marcos:
            if min(xs) < der and max(xs) > izq and arriba <= y <= abajo:
                ubic[mid][f] = next((o for a, b, o in ops if a <= y <= b), None)
    return True, ubic


def _otra_rama(ur, uc):
    """Si dos mensajes estan dibujados en operandos distintos del mismo fragmento: True, False, o None si no se sabe
    (sin dibujo o sin operandos)."""
    if ur is None or uc is None:
        return None
    comunes = [f for f in ur if f in uc]
    if any(ur[f] is not None and uc[f] is not None and ur[f] != uc[f] for f in comunes):
        return True
    return None if any(ur[f] is None or uc[f] is None for f in comunes) else False


def _cerrar(pendientes, desde, quien, cerradas, cierre):
    """Quita de pendientes, desde ese lugar, las llamadas que hizo quien y las que salieron de ellas: ya regresaron.
    Las asincronas de quien siguen abiertas porque no las espera. quien None (manda alguien a quien nadie llamo, como
    el actor: empieza otra cosa) las cierra todas. Cada una pasa a cerradas con el mensaje que la cerro."""
    activos, quedan = {quien}, pendientes[:desde]
    for p in pendientes[desde:]:
        if quien is None or (p[1] in activos and not p[3]):
            activos.add(p[2])
            cerradas.append(p + cierre)
        else:
            quedan.append(p)
    pendientes[:] = quedan


def _modelos_dibujados(dg):
    """Ids de los elementos que tienen vista en el diagrama, en orden (tambien los de vistas anidadas)."""
    out, pila = {}, list(reversed(dg.get('ownedViews') or []))
    while pila:
        v = pila.pop()
        if not isinstance(v, dict):
            continue
        r = _ref(v.get('model'))
        if r:
            out.setdefault(r, True)
        pila.extend(reversed(v.get('subViews') or []))
    return list(out)


# ---------------------------------------------------------------------------
# Revision
# ---------------------------------------------------------------------------

def _lifeline(doc, idx, ll):
    """Nombre de la lifeline, su tipo (elemento o None) y que tiene de malo ese tipo."""
    rol = doc.ids.get(_ref(ll.get('represent')))
    nombre = (rol or {}).get('name') or ll.get('name') or ''
    t = (rol or {}).get('type')
    info = {'id': ll['_id'], 'nombre': nombre, 'tipo': None, 'kind': '?', 'falla': None}
    if isinstance(t, dict):
        el = doc.ids.get(t.get('$ref'))
        if el is None:
            info['falla'] = ('no_existe', t.get('$ref'))
        elif el['_id'] not in idx.tipos:
            de = ', de un perfil' if idx._en_perfil(el['_id']) else ''
            info['falla'] = ('no_clase', f'{el.get("name") or "(sin nombre)"} ({el.get("_type")}{de})')
        else:
            info['tipo'] = el
    elif isinstance(t, str) and t.strip():
        cands = idx.por_nombre.get(t.strip())
        if cands:
            info['tipo'] = cands[0]
        else:
            info['falla'] = ('no_existe', t.strip())
    else:
        info['falla'] = ('sin_tipo', None)
    if info['tipo'] is not None:
        info['kind'] = doc.kind(info['tipo'])
    return info


def _etiquetas(infos):
    """Como se nombra cada lifeline en los mensajes: su tipo, o 'rol: Tipo' si hay otra del mismo tipo."""
    cuenta = {}
    for i in infos.values():
        if i['tipo'] is not None:
            cuenta[i['tipo']['_id']] = cuenta.get(i['tipo']['_id'], 0) + 1
    for i in infos.values():
        if i['tipo'] is None:
            i['etiqueta'] = i['nombre'] or '(lifeline sin nombre)'
        elif cuenta[i['tipo']['_id']] > 1 and i['nombre']:
            i['etiqueta'] = f'{i["nombre"]}: {i["tipo"].get("name")}'
        else:
            i['etiqueta'] = i['tipo'].get('name') or '(sin nombre)'


def _cual(spec, dg):
    """Como nombrar el diagrama pedido en un error: por su nombre y, si se pidio por id, tambien el id."""
    return f'"{spec}"' if spec == dg.get('name') else f'"{dg.get("name")}" ({spec})'


def _diagrama(doc, spec, tipo, que):
    """El diagrama pedido por id o por nombre. Por nombre se busca primero entre los del tipo pedido: si una secuencia
    y un diagrama de clases se llaman igual, no hace falta el id."""
    el = doc.ids.get(spec) if isinstance(spec, str) else None
    if not (isinstance(el, dict) and 'Diagram' in _txt(el.get('_type'))):
        del_tipo = [d for d in doc.diagrams() if d.get('name') == spec and d.get('_type') == tipo]
        if len(del_tipo) == 1:
            return del_tipo[0]
        if len(del_tipo) > 1:
            raise MdjError(f'Hay {len(del_tipo)} diagramas "{spec}" de ese tipo: '
                           + ', '.join(d['_id'] for d in del_tipo) + '. Usa el id.')
    dg = doc.diagram(spec)  # da el error si no existe o si hay varios de otros tipos
    if dg['_type'] != tipo:
        raise MdjError(f'{_cual(spec, dg)} es un {dg["_type"]}, no un {que}')
    return dg


def _resolver_secuencias(doc, secuencias):
    """[(diagrama, interaccion)] de las secuencias pedidas, o de todas las que tienen mensajes."""
    if isinstance(secuencias, str):
        secuencias = [secuencias]
    res, vistas = [], set()
    if not secuencias:
        for dg in doc.diagrams():
            if dg['_type'] != 'UMLSequenceDiagram':
                continue
            try:
                it = M.interaction_of(doc, dg)
            except MdjError:
                continue
            if it.get('messages') and it['_id'] not in vistas:
                vistas.add(it['_id'])
                res.append((dg, it))
        if not res:
            raise MdjError('El archivo no tiene diagramas de secuencia con mensajes')
        return res
    for spec in secuencias:
        dg = _diagrama(doc, spec, 'UMLSequenceDiagram', 'diagrama de secuencia')
        it = M.interaction_of(doc, dg)
        if it['_id'] not in vistas:  # dos diagramas de la misma interaccion muestran los mismos mensajes
            vistas.add(it['_id'])
            res.append((dg, it))
    return res


def revisar_secuencias(doc, secuencias=None, clases=None, metodos='control', parametros=True):
    """Revisa que los diagramas de secuencia cuadren con el modelo de clases (ver el encabezado del modulo).
    secuencias: nombres o ids (default: todas las que tienen mensajes); clases: nombre o id de un diagrama de clases
    para revisar tambien contra lo dibujado en el; metodos: 'no', 'control' o 'todos'; parametros: avisar de
    argumentos que no salen de ningun lado."""
    if metodos not in METODOS:
        raise MdjError(f'metodos debe ser uno de {list(METODOS)}, no {metodos!r}')
    pares = _resolver_secuencias(doc, secuencias)
    dg_clases, dibujados = None, []
    if clases:
        dg_clases = _diagrama(doc, clases, 'UMLClassDiagram', 'diagrama de clases')
        dibujados = _modelos_dibujados(dg_clases)
    idx = _Indice(doc)
    usadas, tipos_vistos = set(), {}  # ids de operaciones que reciben algun mensaje; tipos de las lifelines
    salida = [_revisar_una(doc, idx, dg, it, metodos, parametros, dg_clases, set(dibujados), usadas, tipos_vistos)
              for dg, it in pares]
    generales = {'problemas': [], 'avisos': []}
    res = {'secuencias': salida}
    # operaciones que no recibe ningun mensaje
    if metodos != 'no':
        por_control, por_clase = {}, {}
        for tid, el in tipos_vistos.items():
            k = doc.kind(el)
            if metodos == 'control' and k != 'control':
                continue
            ops = [op for op in el.get('operations') or [] if isinstance(op, dict) and op.get('_id')]
            if k == 'control' and not idx.operaciones(tid):
                generales['avisos'].append({
                    'clase': el.get('name'), 'revision': 'metodos',
                    'explicacion': f'{el.get("name")} no tiene operaciones: no se revisan los mensajes que recibe '
                                   '(si el analisis va sin metodos, usa metodos="no")'})
            if not ops and k != 'control':
                continue
            destino = por_control if k == 'control' else por_clase
            clave = el.get('name') if el.get('name') not in destino else f'{el.get("name")} ({tid})'
            nombres = _nombres_ops(ops)
            destino[clave] = {'usados': [nombres[op['_id']] for op in ops if op['_id'] in usadas],
                              'sin_usar': [nombres[op['_id']] for op in ops if op['_id'] not in usadas]}
            for op in ops:
                if op['_id'] not in usadas:
                    generales['avisos'].append({
                        'clase': el.get('name'), 'operacion': nombres[op['_id']], 'revision': 'metodos',
                        'explicacion': f'{el.get("name")}.{nombres[op["_id"]]} no recibe ningun mensaje en las '
                                       'secuencias revisadas'})
        res['metodos_control'] = por_control
        if metodos == 'todos':
            res['metodos_otras_clases'] = por_clase
    # clases del diagrama que no salen en ninguna secuencia
    if dg_clases is not None:
        for i in dibujados:
            el = doc.ids.get(i)
            if not el or el.get('_type') != 'UMLClass' or i in tipos_vistos:
                continue
            sup = next((tipos_vistos[x] for x in idx.linaje(i) if x in tipos_vistos), None)
            sub = next((e for x, e in tipos_vistos.items() if idx.es_ancestro(i, x)), None)
            pista = (f'; solo aparece su superclase {sup.get("name")}' if sup is not None else
                     f'; solo aparece su subclase {sub.get("name")}' if sub is not None else '')
            generales['avisos'].append({
                'diagrama': dg_clases.get('name'), 'clase': el.get('name'), 'revision': 'clases',
                'explicacion': f'{el.get("name")} esta en {dg_clases.get("name")} pero no sale en ninguna de las '
                               f'secuencias revisadas{pista}'})
    res['generales'] = generales
    res['resumen'] = {'secuencias': len(salida), 'mensajes': sum(s['mensajes'] for s in salida),
                      'problemas': sum(len(s['problemas']) for s in salida) + len(generales['problemas']),
                      'avisos': sum(len(s['avisos']) for s in salida) + len(generales['avisos'])}
    return res


def _sin_origen(faltan, es, ts, tt, rep, idx, conocidos):
    """Explicacion de los argumentos de un mensaje que no salen de ningun lado, con pistas si las hay."""
    uno = len(faltan) == 1
    citados = ', '.join(f'"{nm}"' for nm in faltan)
    pistas = [(nm, _pista(nm, conocidos)) for nm in faltan]
    if uno:
        parecidos = f'; se parece a {pistas[0][1]}' if pistas[0][1] else ''
    else:
        parecidos = ''.join(f'; "{nm}" se parece a {p}' for nm, p in pistas if p)
    lo, atributo = ('lo', 'es atributo suyo') if uno else ('los', 'son atributos suyos')
    if rep:
        attrs = idx.atributos(ts['_id'])
        cola = parecidos or (f'; sus atributos son {", ".join(attrs[:8])}{"..." if len(attrs) > 8 else ""}'
                             if attrs else '')
        return f'{es} responde {citados}, que no {atributo} ni de una clase asociada y no {lo} recibio antes{cola}'
    otro = f', de {tt.get("name")}' if ts['_id'] != tt['_id'] else ''
    sale = 'sale' if uno else 'salen'
    return (f'{citados} no {sale} de ningun lado: {es} no {lo} recibio antes y no {atributo}{otro} ni de una clase '
            'asociada' + (parecidos or ' (si es un valor fijo, va en MAYUSCULAS o entre comillas)'))


def _revisar_una(doc, idx, dg, it, metodos, parametros, dg_clases, dibujados, usadas, tipos_vistos):
    nombre_dg = dg.get('name')
    probs, avisos = [], []
    con_vistas = bool(dg.get('ownedViews'))  # mdj_validar solo revisa las secuencias con vistas
    lls = {}
    for ll in it.get('participants') or []:
        if isinstance(ll, dict) and ll.get('_type') == 'UMLLifeline' and ll.get('_id'):
            lls[ll['_id']] = _lifeline(doc, idx, ll)
    _etiquetas(lls)

    # 1. lifelines
    for i in lls.values():
        base = {'diagrama': nombre_dg, 'lifeline': i['etiqueta'], 'revision': 'lifelines'}
        falla = i['falla']
        if falla and falla[0] == 'sin_tipo':
            igual = idx.por_clave.get(_norm(i['nombre']))
            avisos.append(dict(base, explicacion=f'La lifeline {i["etiqueta"]} no tiene tipo (clase o actor): sus '
                               'mensajes no se pueden cruzar con el modelo' +
                               (f'; se llama igual que {igual[0].get("name")}' if igual else '')))
        elif falla and falla[0] == 'no_existe':
            probs.append(dict(base, explicacion=f'El tipo de la lifeline {i["etiqueta"]} ({falla[1]}) no existe en '
                              'el modelo'))
        elif falla:
            probs.append(dict(base, explicacion=f'El tipo de la lifeline {i["etiqueta"]} es {falla[1]}, no una clase '
                              'ni un actor del modelo'))
        if i['tipo'] is not None:
            tipos_vistos.setdefault(i['tipo']['_id'], i['tipo'])
            if dg_clases is not None and i['tipo']['_id'] not in dibujados:
                probs.append(dict(base, explicacion=f'{i["tipo"].get("name")} no esta dibujado en '
                                  f'{dg_clases.get("name")}'))

    nombres_ll = set()
    for i in lls.values():
        nombres_ll |= _variantes(_norm(i['nombre']))
    palabras_ll = idx.palabras_de(i['tipo']['_id'] for i in lls.values() if i['tipo'] is not None)
    recibidos = {k: _Nombres() for k in lls}
    # pila de llamadas: (n, origen, destino, asincrona) de las que siguen abiertas; las que ya regresaron pasan a
    # cerradas con (id, n, si fue su propia reply) del mensaje que las cerro
    pendientes, cerradas = [], []
    hay_fragmentos, ubic = _fragmentos(dg, it)
    msgs = [m for m in it.get('messages') or [] if isinstance(m, dict)]
    for n, m in enumerate(msgs, 1):
        sid, tid = _ref(m.get('source')), _ref(m.get('target'))
        s, t = lls.get(sid), lls.get(tid)
        ts = s['tipo'] if s else None
        tt = t['tipo'] if t else None
        es = s['etiqueta'] if s else doc.name_of(sid)
        et = t['etiqueta'] if t else doc.name_of(tid)
        op, args, asignacion, texto = _partes(doc, m)
        rep = m.get('messageSort') == 'reply'

        def hallazgo(lista, revision, explicacion):
            lista.append({'diagrama': nombre_dg, 'n': n, 'mensaje': texto, 'revision': revision,
                          'explicacion': explicacion})

        # 2. relacion en el modelo (lo que mdj_validar ya marca no se repite)
        if not rep and ts is not None and tt is not None and ts['_id'] != tt['_id']:
            r = idx.relacion(ts['_id'], tt['_id'])
            if not _lo_marca_validar(s['kind'], t['kind'], r, con_vistas):
                if r == 'ninguna':
                    hallazgo(probs, 'relacion', f'{ts.get("name")} y {tt.get("name")} no tienen ninguna relacion en '
                             'el modelo (asociacion, herencia, dependencia o realizacion) que permita este mensaje')
                elif r == 'contraria':
                    hallazgo(avisos, 'relacion', f'La asociacion entre {ts.get("name")} y {tt.get("name")} solo '
                             f'navega de {tt.get("name")} a {ts.get("name")}; el mensaje va al reves')
                elif r == 'cerrada':
                    hallazgo(avisos, 'relacion', f'La asociacion entre {ts.get("name")} y {tt.get("name")} no '
                             'navega en ningun sentido')

        # 3. operaciones del receptor
        elegidas = []
        if not rep and tt is not None and m.get('messageSort') not in NO_LLAMAN:
            ops = idx.operaciones(tt['_id'])
            exactas = [o for o in ops if _txt(o.get('name')) == op]
            elegidas = exactas or [o for o in ops if _txt(o.get('name')) and _norm(o.get('name')) == _norm(op)]
            sig = doc.ids.get(_ref(m.get('signature')))
            sig = sig if isinstance(sig, dict) and sig.get('_type') == 'UMLOperation' else None
            revisa = bool(ops) and (metodos == 'todos' or (metodos == 'control' and t['kind'] == 'control'))
            if t['kind'] == 'boundary' and _norm(op).startswith('mostrar'):
                revisa = False  # las boundary no llevan metodos: mostrarX no se exige
            if sig is not None and any(o['_id'] == sig['_id'] for o in ops):
                elegidas = exactas = [sig]
            elif sig is not None:
                elegidas = []
                if revisa:
                    hallazgo(probs, 'metodos', f'El mensaje apunta a la operacion '
                             f'{doc.name_of(doc.parent.get(sig["_id"]))}.{sig.get("name")}, que no es de '
                             f'{tt.get("name")}')
                    revisa = False
            k = len(args or [])
            mismas = [o for o in elegidas if len(_parametros_entrada(o)) == k]
            if revisa:
                if not elegidas:
                    # un get/set solo se sugiere si el mensaje tambien es get/set (crearX no es setIdX)
                    nombres = [_txt(o.get('name')) for o in ops]
                    if not _ACCESOR.match(op):
                        nombres = [x for x in nombres if not _ACCESOR.match(x)]
                    cerca = difflib.get_close_matches(op, nombres, n=1, cutoff=0.8)
                    hallazgo(probs, 'metodos', f'{tt.get("name")} no tiene una operacion {op or "(sin nombre)"}' +
                             (f'; la mas parecida es {cerca[0]}' if cerca else ''))
                elif not exactas:
                    hallazgo(avisos, 'metodos', f'{op} no se escribe igual que la operacion '
                             f'{elegidas[0].get("name")} de {tt.get("name")} (mayusculas o acentos)')
                if elegidas and not mismas:
                    lleva = f'Lleva {_cuantos(k)}' if args is not None else 'No muestra argumentos'
                    hallazgo(avisos, 'metodos', f'{lleva} y la operacion {tt.get("name")}.{elegidas[0].get("name")} '
                             f'recibe {_recibe_ops(elegidas)}')
            elegidas = mismas or elegidas  # la de los mismos parametros, para saber que nombres recibe
            usadas.update(o['_id'] for o in elegidas)

        # 4. argumentos que no salen de ningun lado
        if parametros and args and ts is not None and tt is not None and s['kind'] != 'actor':
            alc = idx.alcance(ts['_id'], tt['_id'])
            rec = recibidos[sid]
            cerca = idx.cerca(ts['_id'], tt['_id']) | palabras_ll
            completos = alc.completos | idx.globales | nombres_ll | rec.completos | cerca
            partes = alc.partes | rec.partes | cerca
            sueltas = rec.partes - idx.rotulos  # solicitado (de equipoSolicitado) si; renta (de diasRenta) no
            faltan, vistos = [], set()
            for a in args:
                for nm in _nombres_en(a):
                    if (_norm(nm) in idx.enum_literales or _norm(nm) in vistos
                            or _explicado(nm, completos, partes, sueltas)):
                        continue
                    vistos.add(_norm(nm))
                    faltan.append(nm)
            if faltan:
                hallazgo(avisos, 'argumentos', _sin_origen(faltan, es, ts, tt, rep, idx, alc.originales + rec.originales))

        # 5. la reply regresa a quien llamo (una reply a si misma ya la marca mdj_validar, si hay vistas)
        if rep and sid == tid and not con_vistas:
            hallazgo(probs, 'replies', f'La respuesta va de {es} a si misma; debe regresar a quien hizo la llamada')
        elif rep and sid != tid:
            i = next((k for k in range(len(pendientes) - 1, -1, -1)
                      if pendientes[k][1] == tid and pendientes[k][2] == sid), None)
            if i is not None:  # cierra la llamada y las que salieron de ella sin reply
                cerradas.append(pendientes.pop(i) + (m.get('_id'), n, True))
                _cerrar(pendientes, i, sid, cerradas, (m.get('_id'), n, False))
            else:
                otra = next((p for p in reversed(pendientes) if p[2] == sid and p[1] != sid), None)
                previa = next((c for c in reversed(cerradas) if c[1] == tid and c[2] == sid), None)
                rama = _otra_rama(ubic.get(m.get('_id')), ubic.get(previa[4])) if previa and hay_fragmentos else False
                if otra:
                    eo = lls[otra[1]]['etiqueta'] if otra[1] in lls else doc.name_of(otra[1])
                    hallazgo(probs, 'replies', f'La respuesta va a {et}, pero a {es} lo llamo {eo} (mensaje '
                             f'{otra[0]}); debe regresar a {eo}')
                elif previa is None:
                    hallazgo(probs, 'replies', f'No hay una llamada pendiente de {et} a {es} que esta respuesta '
                             'pueda cerrar')
                elif rama is None:  # hay fragmentos pero el dibujo no dice en que operando va cada mensaje
                    hallazgo(avisos, 'replies', f'La llamada de {et} a {es} (mensaje {previa[0]}) ya se habia '
                             f'cerrado en el mensaje {previa[5]}; solo esta bien si esta respuesta va en otra rama '
                             'de un fragmento (alt, par)')
                elif not rama:
                    cuando = (f'ya tuvo su respuesta en el mensaje {previa[5]}' if previa[6] else
                              f'ya habia regresado cuando se mando el mensaje {previa[5]} (la respuesta va antes)')
                    hallazgo(probs, 'replies', f'No hay una llamada pendiente de {et} a {es}: la del mensaje '
                             f'{previa[0]} {cuando}')
        elif not rep:
            # quien manda esta activo por la ultima llamada que recibio: lo que llamo despues ya regreso
            j = next((k for k in range(len(pendientes) - 1, -1, -1) if pendientes[k][2] == sid), None)
            _cerrar(pendientes, 0 if j is None else j + 1, None if j is None else sid, cerradas,
                    (m.get('_id'), n, False))
            if m.get('messageSort') != 'deleteMessage':
                pendientes.append((n, sid, tid, m.get('messageSort') in ASINCRONOS))

        # lo que cada lifeline sabe despues de este mensaje
        if tid in recibidos:
            for a in args or []:
                for x in _recibe(a):
                    recibidos[tid].agregar(x)
            if rep:
                recibidos[tid].agregar(op)
            else:
                for o in elegidas[:1]:
                    for p in _parametros_entrada(o):
                        recibidos[tid].agregar(p.get('name'))
        if sid in recibidos and asignacion:
            recibidos[sid].agregar(asignacion)

    return {'diagrama': nombre_dg, 'mensajes': len(msgs), 'problemas': probs, 'avisos': avisos}
