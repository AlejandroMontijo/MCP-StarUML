# Correcciones del lado de codigo: importador (paquete pedido, sin quitar nada, ambiguedad), generador (get/set del
# modelo, tipos con precision), comparacion (BC_ frente a la clase, herencia, partial de C#, this.x de JavaScript) y
# programa_a_diagrama (anidadas, namespaces, modulos y carpetas como paquetes, imports, campos genericos). Tambien las
# clases anidadas de Python y los tipos con su tamano (char, short, byte, float, Long) de ida y vuelta.
import os
import shutil
import subprocess
import sys

import pytest

from staruml_mcp import codigo as C
from apoyo import M, fuentes, ids_integros, ok, tool


def clases_llamadas(doc, nombre, tipos=('UMLClass', 'UMLInterface', 'UMLEnumeration')):
    return [o for o in doc.ids.values() if o and o['_type'] in tipos and o.get('name') == nombre]


def atributos(el):
    return [(a['name'], a.get('type')) for a in el.get('attributes', [])]


def calificado(doc, el):
    """Nombre con sus paquetes y clases externas, sin el paquete raiz del programa: estructuras.Arbol.Nodo."""
    partes, actual = [], el
    while actual and doc.ids.get(doc.parent.get(actual['_id']), {}).get('_type') not in ('UMLModel', 'Project', None):
        partes.insert(0, actual.get('name', ''))
        actual = doc.ids.get(doc.parent.get(actual['_id']))
    return '.'.join(partes)


def por_calificado(doc, q):
    return next(o for o in doc.ids.values() if o and o['_type'] in ('UMLClass', 'UMLInterface', 'UMLEnumeration')
                and calificado(doc, o) == q)


def navegaciones(doc):
    """{(origen, destino, rol, multiplicidad)} de cada extremo navegable de las asociaciones."""
    res = set()
    for o in doc.ids.values():
        if o and o['_type'] == 'UMLAssociation':
            for desde, hacia in ((o['end1'], o['end2']), (o['end2'], o['end1'])):
                if hacia.get('navigable') == 'navigable':
                    res.add((calificado(doc, doc.ids[desde['reference']['$ref']]), calificado(doc, doc.ids[hacia['reference']['$ref']]),
                             hacia.get('name'), hacia.get('multiplicity')))
    return res


def programa(tmp_path, nombre, archivos, **op):
    src = fuentes(str(tmp_path / nombre), archivos)
    mdj = str(tmp_path / f'{nombre}.mdj')
    r = ok(tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=src, **op))
    assert ids_integros(mdj)
    return r, M.Doc(mdj)


def compilar_java(carpeta):
    javac = shutil.which('javac')
    if not javac:
        return None
    archivos = sorted(os.path.join(carpeta, f) for f in os.listdir(carpeta) if f.endswith('.java'))
    cp = subprocess.run([javac, '-d', os.path.join(carpeta, 'bin')] + archivos, capture_output=True, text=True)
    return cp.returncode == 0, cp.stderr[-1500:]


# --- importador ---

def test_importar_crea_la_clase_en_el_paquete_pedido_sin_tocar_la_de_otro(dominio, tmp_path):
    ok(tool('mdj_paquete_crear', archivo=dominio, nombre='Diseno'))
    antes = atributos(M.Doc(dominio).find('UMLClass:Cliente'))
    src = fuentes(str(tmp_path / 'src'), {'Cliente.java': '''
        package negocio;
        public class Cliente { private String rfc; private String razonSocial; public String getRfc() { return rfc; } }
        '''})
    r = ok(tool('staruml_codigo_a_diagrama', archivo=dominio, ruta_codigo=src, paquete='Diseno'))
    assert r['clases_creadas'] == ['Cliente'] and r['clases_actualizadas'] == [] and r['paquete'] == 'Diseno'
    r = ok(tool('staruml_codigo_a_diagrama', archivo=dominio, ruta_codigo=src, paquete='Diseno', modo='sincronizar'))
    assert r['clases_creadas'] == [] and r['clases_actualizadas'] == ['Cliente']
    doc = M.Doc(dominio)
    por_paquete = {doc.name_of(doc.parent[c['_id']]): atributos(c) for c in clases_llamadas(doc, 'Cliente')}
    assert por_paquete == {'Analisis': antes, 'Diseno': [('rfc', 'String'), ('razonSocial', 'String')]}
    assert ids_integros(dominio)


def test_importar_sincronizar_no_quita_nada_y_reporta_lo_que_falta_en_el_codigo(dominio, tmp_path):
    src = fuentes(str(tmp_path / 'src'), {'Pedido.java': '''
        import java.math.BigDecimal;
        public class Pedido { private BigDecimal total; private String folio; }
        '''})
    r = ok(tool('staruml_codigo_a_diagrama', archivo=dominio, ruta_codigo=src, paquete='Analisis'))
    assert atributos(M.Doc(dominio).find('UMLClass:Pedido')) == [('total', 'double'), ('items', 'List<Item>'), ('folio', 'String')]
    r = ok(tool('staruml_codigo_a_diagrama', archivo=dominio, ruta_codigo=src, paquete='Analisis', modo='sincronizar'))
    pedido = M.Doc(dominio).find('UMLClass:Pedido')
    assert atributos(pedido) == [('total', 'BigDecimal'), ('items', 'List<Item>'), ('folio', 'String')]
    assert [o['name'] for o in pedido['operations']] == ['calcularTotal']  # nada se quita
    assert r['tipos_cambiados'] == {'Pedido': ['total: double -> BigDecimal']}
    assert r['en_modelo_sin_codigo'] == {'Pedido': {'atributos': ['items']}}
    assert 'atributos_quitados' not in r


def test_importar_no_confunde_bc_cliente_con_cliente(dominio, tmp_path):
    ok(tool('mdj_clase_crear', archivo=dominio, paquete='Analisis', nombre='BC_Cliente', estereotipo='boundary'))
    src = fuentes(str(tmp_path / 'src'), {'Cliente.java': 'public class Cliente { private String telefono; }\n'})
    r = ok(tool('staruml_codigo_a_diagrama', archivo=dominio, ruta_codigo=src, paquete='Analisis'))
    assert r['clases_actualizadas'] == ['Cliente'] and r['atributos_agregados'] == {'Cliente': ['telefono']}
    assert 'BC_Cliente' not in str(r['atributos_agregados'])


def test_importar_ambiguo_da_error_claro_y_no_cambia_nada(dominio, tmp_path):
    ok(tool('mdj_clase_crear', archivo=dominio, paquete='Analisis', nombre='Orden de Compra'))
    ok(tool('mdj_clase_crear', archivo=dominio, paquete='Analisis', nombre='orden_de_compra'))
    antes = open(dominio, 'rb').read()
    src = fuentes(str(tmp_path / 'src'), {'OrdenDeCompra.java': 'public class OrdenDeCompra { private int folio; }\n',
                                          'Nueva.java': 'public class Nueva { private int x; }\n'})
    r = tool('staruml_codigo_a_diagrama', archivo=dominio, ruta_codigo=src, paquete='Analisis')
    assert 'error' in r and 'OrdenDeCompra' in r['error'] and "'Orden de Compra'" in r['error'] and 'no se cambio nada' in r['error']
    assert open(dominio, 'rb').read() == antes


def test_importar_conserva_long_bigdecimal_y_fechas_y_el_generado_compila(vacio, tmp_path):
    src = fuentes(str(tmp_path / 'src'), {'Factura.java': '''
        package ventas;
        import java.math.BigDecimal;
        import java.time.*;
        import java.util.List;
        public class Factura {
            private long folio;
            private BigDecimal monto;
            private LocalDateTime emitida;
            private LocalTime hora;
            private java.util.List<ventas.Partida> partidas;
            public BigDecimal calcular(long base, LocalDate dia) { return monto; }
        }''', 'Partida.java': 'package ventas;\npublic class Partida { private int cantidad; }\n'})
    ok(tool('staruml_codigo_a_diagrama', archivo=vacio, ruta_codigo=src, paquete='Analisis', diagrama='cu_1'))
    doc = M.Doc(vacio)
    factura = doc.find('UMLClass:Factura')
    assert atributos(factura) == [('folio', 'long'), ('monto', 'BigDecimal'), ('emitida', 'LocalDateTime'),
                                  ('hora', 'LocalTime'), ('partidas', 'List<Partida>')]
    op = factura['operations'][0]
    assert [(p.get('name'), p.get('type')) for p in op['parameters']] == [('base', 'long'), ('dia', 'LocalDate'), (None, 'BigDecimal')]
    out = str(tmp_path / 'java')
    ok(tool('staruml_diagrama_a_codigo', archivo=vacio, diagrama='cu_1', lenguaje='java', carpeta_salida=out))
    java = open(os.path.join(out, 'Factura.java'), encoding='utf-8').read()
    for linea in ('private long folio;', 'private BigDecimal monto;', 'private LocalDateTime emitida;', 'private LocalTime hora;',
                  'import java.math.BigDecimal;', 'import java.time.LocalDateTime;', 'import java.time.LocalTime;',
                  'public BigDecimal calcular(long base, LocalDate dia)'):
        assert linea in java, linea
    compilado = compilar_java(out)
    assert compilado is None or compilado[0], compilado[1]
    esperados = {'python': ('folio: Optional[int]', 'monto: Optional[Decimal]', 'emitida: Optional[datetime]', 'hora: Optional[time]'),
                 'csharp': ('public long Folio', 'public decimal Monto', 'public DateTime Emitida', 'public TimeSpan Hora'),
                 'typescript': ('folio?: number', 'monto?: number', 'emitida?: Date', 'hora?: string')}
    for lenguaje, lineas in esperados.items():
        out = str(tmp_path / lenguaje)
        r = ok(tool('staruml_diagrama_a_codigo', archivo=vacio, diagrama='cu_1', lenguaje=lenguaje, carpeta_salida=out))
        texto = open(os.path.join(out, next(f for f in r['archivos'] if f.split('.')[0] == 'Factura')), encoding='utf-8').read()
        for linea in lineas:
            assert linea in texto, (lenguaje, linea)
        if lenguaje == 'python':
            cp = subprocess.run([sys.executable, 'Factura.py'], capture_output=True, text=True, cwd=out)
            assert cp.returncode == 0, cp.stderr[-500:]
        cmp = ok(tool('staruml_comparar_codigo', archivo=vacio, diagrama='cu_1', ruta_codigo=out, lenguaje=lenguaje))
        assert cmp['porcentaje_sincronizacion'] == 100.0, (lenguaje, cmp['detalles_por_clase'])


# --- generador ---

def _con_accesores_del_modelo(path):
    """Cliente con getNombre() y setNombre(nombre) sin tipos (como los deja StarUML) y Pedido con un metodo repetido."""
    doc = M.Doc(path)
    cli, ped = doc.find('UMLClass:Cliente'), doc.find('UMLClass:Pedido')

    def op(cls, nombre, params=(), ret=None):
        o = {'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': {'$ref': cls['_id']}, 'name': nombre}
        o['parameters'] = [{'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': {'$ref': o['_id']}, 'name': n, 'type': t}
                           for n, t in params]
        if ret:
            o['parameters'].append({'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': {'$ref': o['_id']}, 'type': ret,
                                    'direction': 'return'})
        cls.setdefault('operations', []).append(o)
    op(cli, 'getNombre')
    op(cli, 'setNombre', [('nombre', '')])
    op(cli, 'getEmail', ret='String')
    op(cli, 'nombre', ret='String')  # se llama como un campo
    op(ped, 'aplicar', [('', 'int'), ('', 'int')])
    op(ped, 'aplicar', [('a', 'int'), ('b', 'int')], ret='double')
    doc.reindex()
    doc.save(backup=False)


def test_java_no_repite_los_get_set_del_modelo_y_compila(dominio, tmp_path):
    _con_accesores_del_modelo(dominio)
    out = str(tmp_path / 'java')
    ok(tool('staruml_diagrama_a_codigo', archivo=dominio, diagrama='cu_1', lenguaje='java', carpeta_salida=out))
    cliente = open(os.path.join(out, 'Cliente.java'), encoding='utf-8').read()
    assert cliente.count('getNombre(') == 1 and 'public String getNombre() { return this.nombre; }' in cliente
    assert cliente.count('setNombre(') == 1 and cliente.count('getEmail(') == 1
    pedido = open(os.path.join(out, 'Pedido.java'), encoding='utf-8').read()
    assert pedido.count(' aplicar(') == 1 and 'aplicar(int p1, int p2)' in pedido  # sin nombres vacios ni repetidos
    compilado = compilar_java(out)
    assert compilado is None or compilado[0], compilado[1]
    cmp = ok(tool('staruml_comparar_codigo', archivo=dominio, diagrama='cu_1', ruta_codigo=out, lenguaje='java'))
    assert cmp['porcentaje_sincronizacion'] == 100.0, cmp['detalles_por_clase']


def test_metodo_que_se_llama_como_un_campo_no_choca(dominio, tmp_path):
    _con_accesores_del_modelo(dominio)
    for lenguaje, esperado in (('csharp', 'public string Nombre_()'), ('typescript', 'public nombre_(): string'),
                               ('python', 'def nombre_(self) -> str:')):
        out = str(tmp_path / lenguaje)
        r = ok(tool('staruml_diagrama_a_codigo', archivo=dominio, diagrama='cu_1', lenguaje=lenguaje, carpeta_salida=out))
        texto = open(os.path.join(out, next(f for f in r['archivos'] if f.split('.')[0] == 'Cliente')), encoding='utf-8').read()
        assert esperado in texto, (lenguaje, texto)
        cmp = ok(tool('staruml_comparar_codigo', archivo=dominio, diagrama='cu_1', ruta_codigo=out, lenguaje=lenguaje))
        assert cmp['porcentaje_sincronizacion'] == 100.0, (lenguaje, cmp['detalles_por_clase'])


# --- comparacion ---

@pytest.mark.parametrize('lenguaje', ['java', 'python', 'typescript', 'csharp'])
def test_comparar_no_confunde_bc_cliente_con_cliente(dominio, tmp_path, lenguaje):
    ok(tool('mdj_clase_crear', archivo=dominio, paquete='Analisis', nombre='BC_Cliente', estereotipo='boundary'))
    ok(tool('mdj_vista_agregar', archivo=dominio, diagrama='cu_1', elemento='BC_Cliente', x=40, y=600))
    out = str(tmp_path / lenguaje)
    ok(tool('staruml_diagrama_a_codigo', archivo=dominio, diagrama='cu_1', lenguaje=lenguaje, carpeta_salida=out))
    r = ok(tool('staruml_comparar_codigo', archivo=dominio, diagrama='cu_1', ruta_codigo=out, lenguaje=lenguaje))
    pares = {c['uml']: c['codigo'] for c in r['clases_coincidentes']}
    assert pares['Cliente'] == 'Cliente' and pares['BC_Cliente'] == 'BC_Cliente'
    assert r['porcentaje_sincronizacion'] == 100.0, r['detalles_por_clase']


def test_clase_que_se_llama_igual_en_otro_paquete_no_toma_sus_relaciones(dominio, tmp_path):
    """Las asociaciones y la herencia de cada clase del diagrama se buscan por id: una clase de diseno que se llama
    como una del dominio (en otro paquete) no se queda con las de esa. Antes el codigo generado no las traia (su
    destino no esta en el diagrama) y la comparacion las pedia: menos de 100 %."""
    ok(tool('mdj_paquete_crear', archivo=dominio, nombre='Diseno'))
    ids = [ok(tool('mdj_clase_crear', archivo=dominio, paquete='Diseno', nombre=n))['clase'] for n in ('Cliente', 'ClienteVIP')]
    dg = ok(tool('mdj_diagrama_crear', archivo=dominio, tipo='clases', nombre='Pantallas', dentro_de='Diseno'))['diagrama']
    for x, cid in zip((40, 240), ids):
        ok(tool('mdj_vista_agregar', archivo=dominio, diagrama=dg, elemento=cid, x=x, y=100))
    doc = M.Doc(dominio)
    clases = C.extraer_elementos_diagrama(doc, dg)['clases']
    assert {n: (c['id'], c['asociaciones'], c['superclases']) for n, c in clases.items()} == {
        'Cliente': (ids[0], [], []), 'ClienteVIP': (ids[1], [], [])}
    del_dominio = C.extraer_elementos_diagrama(doc, 'cu_1')['clases']
    assert [a['destino'] for a in del_dominio['Cliente']['asociaciones']] == ['Pedido']
    assert del_dominio['ClienteVIP']['superclases'] == ['Cliente']
    out = str(tmp_path / 'java')
    ok(tool('staruml_diagrama_a_codigo', archivo=dominio, diagrama=dg, lenguaje='java', carpeta_salida=out))
    compilado = compilar_java(out)
    assert compilado is None or compilado[0], compilado
    r = ok(tool('staruml_comparar_codigo', archivo=dominio, diagrama=dg, ruta_codigo=out, lenguaje='java'))
    assert r['porcentaje_sincronizacion'] == 100.0, r['detalles_por_clase']


@pytest.mark.parametrize('nombre', ['Cliente', 'ClienteVIP'])
def test_clase_dibujada_sin_nombre_no_rompe_la_extraccion(dominio, nombre):
    """Un .mdj editado a mano puede traer una clase sin 'name'. Sus asociaciones y su herencia se guardan bajo la
    misma clave que la clase (''), sin KeyError."""
    doc = M.Doc(dominio)
    el = next(e for e in doc.ids.values() if e and e.get('_type') == 'UMLClass' and e.get('name') == nombre)
    del el['name']
    clases = C.extraer_elementos_diagrama(doc, 'cu_1')['clases']
    assert clases['']['id'] == el['_id']
    if nombre == 'Cliente':
        assert [a['destino'] for a in clases['']['asociaciones']] == ['Pedido']
    else:
        assert clases['']['superclases'] == ['Cliente']


def test_comparar_revisa_la_herencia(dominio, tmp_path):
    out = str(tmp_path / 'java')
    ok(tool('staruml_diagrama_a_codigo', archivo=dominio, diagrama='cu_1', lenguaje='java', carpeta_salida=out))
    r = ok(tool('staruml_comparar_codigo', archivo=dominio, diagrama='cu_1', ruta_codigo=out, lenguaje='java'))
    assert r['porcentaje_sincronizacion'] == 100.0 and r['detalles_por_clase']['ClienteVIP']['herencia']['coincidentes'] == ['Cliente']
    for archivo, viejo, nuevo in (('ClienteVIP.java', 'public class ClienteVIP extends Cliente', 'public class ClienteVIP'),
                                  ('Item.java', 'public class Item', 'public class Item extends Pedido')):
        p = os.path.join(out, archivo)
        texto = open(p, encoding='utf-8').read()
        assert viejo in texto
        open(p, 'w', encoding='utf-8').write(texto.replace(viejo, nuevo))
    r = ok(tool('staruml_comparar_codigo', archivo=dominio, diagrama='cu_1', ruta_codigo=out, lenguaje='java'))
    assert r['porcentaje_sincronizacion'] < 100.0
    assert r['detalles_por_clase']['ClienteVIP']['herencia'] == {'coincidentes': [], 'faltan_en_codigo': ['Cliente'],
                                                                  'sobran_en_codigo': []}
    assert r['detalles_por_clase']['Item']['herencia']['sobran_en_codigo'] == ['Pedido']


def test_herencia_por_medio_de_otra_clase_cuenta(tmp_path):
    uml = {'nombre': 'd', 'clases': {n: {'nombre': n, 'tipo': 'UMLClass', 'atributos': [], 'metodos': [], 'asociaciones': [],
                                         'superclases': s, 'interfaces': []}
                                     for n, s in (('A', []), ('C', ['A']))}}
    codigo = C.escanear_codigo(fuentes(str(tmp_path), {'A.java': 'class A {}', 'B.java': 'class B extends A {}',
                                                       'C.java': 'class C extends B {}'}))
    r = C._comparar_clases_con_codigo(uml, codigo)
    assert r['detalles_por_clase']['C']['herencia']['coincidentes'] == ['A'] and r['porcentaje_sincronizacion'] == 100.0


def test_csharp_partial_en_varios_archivos_se_junta(tmp_path):
    src = fuentes(str(tmp_path), {
        'Cotizacion.A.cs': '''
            namespace Renta {
                public partial class Cotizacion : Documento {
                    public string Folio { get; set; }
                    public double Subtotal { get; set; }
                    public double CalcularIva() { return 0; }
                    partial void Validar();
                }
            }''',
        'Cotizacion.B.cs': '''
            namespace Renta {
                public partial class Cotizacion : IAuditable {
                    public double Total { get; set; }
                    public double CalcularTotal() { return 0; }
                    partial void Validar() { }
                    partial void Revisar(int nivel);
                    partial void Revisar(int nivel) { }
                }
            }''',
        'Otra.cs': 'namespace Otra { public partial class Cotizacion { public int Ajena { get; set; } } }'})
    r = C.escanear_codigo(src, 'csharp')
    c = r['Cotizacion']
    assert [a['nombre'] for a in c['atributos']] == ['Folio', 'Subtotal', 'Total']
    # un metodo partial (declaracion e implementacion, en la misma parte o en otra) cuenta una sola vez
    assert [m['nombre'] for m in c['metodos']] == ['CalcularIva', 'Validar', 'CalcularTotal', 'Revisar']
    assert c['superclases'] == ['Documento'] and c['interfaces'] == ['IAuditable'] and len(c['archivos']) == 2
    assert c['repetida_en'] and c['repetida_en'][0].endswith('Otra.cs')  # la de otro namespace no se junta: se avisa


def test_javascript_campos_del_constructor(dominio, tmp_path):
    src = fuentes(str(tmp_path / 'src'), {'cliente.js': '''
        export class Cliente {
          #secreto;
          constructor(idCliente, nombre, opciones = {}) {
            this.idCliente = idCliente;
            this.nombre = nombre;
            this.activo = true;
            this.pedidos = [];
            this.alta = new Date();
            this.#secreto = 'x';
            if (this.activo === true) { this.contador = 0; }
          }
          saludar() { this.saludo = 'hola'; return this.nombre; }
        }''', 'pedido.ts': '''
        export class Pedido {
          total: number = 0;
          constructor(folio: string);
          constructor(public folio: string, total?: number) { this.total = total; this.notas = ''; }
        }'''})
    r = C.escanear_codigo(src)
    assert [(a['nombre'], a['tipo']) for a in r['Cliente']['atributos']] == [
        ('secreto', 'Object'), ('idCliente', 'Object'), ('nombre', 'Object'), ('activo', 'boolean'), ('pedidos', 'List<Object>'),
        ('alta', 'Date'), ('contador', 'int')]
    assert r['Cliente']['atributos'][0]['visibilidad'] == 'private'  # #secreto
    assert [m['nombre'] for m in r['Cliente']['metodos']] == ['saludar']  # this.saludo fuera del constructor no cuenta
    # la sobrecarga sin cuerpo no confunde: los campos salen del constructor que tiene cuerpo
    assert [(a['nombre'], a['tipo']) for a in r['Pedido']['atributos']] == [('total', 'double'), ('folio', 'String'), ('notas', 'String')]
    # contra el modelo: los campos del constructor cuentan como atributos de Cliente
    cliente = fuentes(str(tmp_path / 'js'), {'Cliente.js': '''
        export class Cliente {
          constructor(nombre, email, direccion) {
            this.nombre = nombre;
            this.email = email;
            this.direccion = direccion;
          }
        }'''})
    cmp = C.comparar_diagrama_con_codigo(M.Doc(dominio), 'cu_1', cliente, 'typescript')
    assert cmp['detalles_por_clase']['Cliente']['atributos']['coincidentes'] == ['nombre', 'email', 'direccion']


# --- programa_a_diagrama ---

def test_programa_no_pierde_clases_anidadas_ni_de_otro_namespace(tmp_path):
    r, doc = programa(tmp_path, 'uno', {'estructuras/Arbol.java': '''
        package estructuras;
        public class Arbol {
            private Nodo raiz;
            static class Nodo { int valor; Nodo izq; Nodo der; }
        }
        class Lista {
            private Nodo cabeza;
            static class Nodo { String dato; Nodo siguiente; }
        }'''})
    assert r['clases'] == 4 and r['clases_repetidas_omitidas'] == []
    nodo_a, nodo_l = por_calificado(doc, 'estructuras.Arbol.Nodo'), por_calificado(doc, 'estructuras.Lista.Nodo')
    assert atributos(nodo_a) == [('valor', 'int')] and atributos(nodo_l) == [('dato', 'String')]
    assert navegaciones(doc) == {
        ('estructuras.Arbol', 'estructuras.Arbol.Nodo', 'raiz', '1'), ('estructuras.Lista', 'estructuras.Lista.Nodo', 'cabeza', '1'),
        ('estructuras.Arbol.Nodo', 'estructuras.Arbol.Nodo', 'izq', '1'), ('estructuras.Arbol.Nodo', 'estructuras.Arbol.Nodo', 'der', '1'),
        ('estructuras.Lista.Nodo', 'estructuras.Lista.Nodo', 'siguiente', '1')}
    vista = next(v for v in doc.diagram('Diagrama de clases')['ownedViews'] if v.get('model', {}).get('$ref') == nodo_a['_id'])
    assert vista.get('showNamespace') and '(from Arbol)' in [l.get('text') for l in vista['subViews'][0]['subViews']]
    lazos = [v for v in doc.diagram('Diagrama de clases')['ownedViews'] if v['_type'] == 'UMLAssociationView'
             and v['head']['$ref'] == v['tail']['$ref'] == vista['_id']]
    assert len(lazos) == 2 and lazos[0]['points'] != lazos[1]['points']  # dos lazos en la misma caja, sin encimarse

    r, doc = programa(tmp_path, 'cs', {'Modelos.cs': '''
        namespace Tienda.Ventas
        {
            public class Pedido { public Cliente Cliente { get; set; } }
            public class Cliente { public string Nombre { get; set; } }
        }
        namespace Tienda.Admin
        {
            public class Cliente { public string Usuario { get; set; } }
        }'''}, lenguaje='csharp')
    assert r['clases'] == 3 and r['clases_repetidas_omitidas'] == []
    assert atributos(por_calificado(doc, 'Tienda.Ventas.Cliente')) == [('Nombre', 'string')]
    assert atributos(por_calificado(doc, 'Tienda.Admin.Cliente')) == [('Usuario', 'string')]
    assert navegaciones(doc) == {('Tienda.Ventas.Pedido', 'Tienda.Ventas.Cliente', 'Cliente', '1')}

    r, doc = programa(tmp_path, 'builders', {
        'modelo/Pedido.java': 'package modelo;\npublic class Pedido { public static class Builder { private Cliente cliente; } }\n',
        'modelo/Cliente.java': 'package modelo;\npublic class Cliente { public static class Builder { private String nombre; } }\n',
        'Modelos.kt': 'package kt\nclass A { class Nodo(val x: Int) }\nclass B { class Nodo(val y: String) }\n'}, lenguaje='auto')
    assert r['clases_repetidas_omitidas'] == [] and r['clases'] == 8
    assert navegaciones(doc) == {('modelo.Pedido.Builder', 'modelo.Cliente', 'cliente', '1')}
    assert atributos(por_calificado(doc, 'kt.B.Nodo')) == [('y', 'String')]

    # la misma clase (mismo paquete y nombre) dos veces no se junta en silencio: se avisa
    r, doc = programa(tmp_path, 'dobles', {'a/X.java': 'package p;\nclass X { int a; }\n', 'b/X.java': 'package p;\nclass X { int b; }\n',
                                           'Y.cs': 'namespace q { class Y { } class Y { } }'}, lenguaje='auto')
    assert sorted(r['clases_repetidas_omitidas']) == ['p.X', 'q.Y'] and r['clases'] == 2


def test_programa_modulos_y_carpetas_cuentan_como_paquete(tmp_path):
    r, doc = programa(tmp_path, 'py', {
        'app/__init__.py': '', 'app/ventas/__init__.py': '', 'app/inventario/__init__.py': '',
        'app/ventas/modelos.py': '''
            from enum import Enum
            class Estado(Enum):
                NUEVO = 1
            class Venta:
                estado: Estado
            ''',
        'app/ventas/servicio.py': '''
            from .modelos import Estado
            from app.inventario import modelos as inv
            class Servicio:
                def __init__(self, estado: Estado, otro: "inv.Estado"):
                    self.estado = estado
                    self.otro = otro
            ''',
        'app/inventario/modelos.py': '''
            from enum import Enum
            class Estado(Enum):
                DISPONIBLE = 1
            class Producto:
                def __init__(self, estado: Estado):
                    self.estado = estado
            '''}, lenguaje='python', diagrama_por='paquete')
    assert r['clases_repetidas_omitidas'] == [] and r['enumeraciones'] == 2
    assert r['paquetes_con_clases'] == ['app.inventario.modelos', 'app.ventas.modelos', 'app.ventas.servicio']
    assert [d['diagrama'] for d in r['diagramas']] == r['paquetes_con_clases']
    assert navegaciones(doc) == {
        ('app.ventas.modelos.Venta', 'app.ventas.modelos.Estado', 'estado', '1'),
        ('app.ventas.servicio.Servicio', 'app.ventas.modelos.Estado', 'estado', '1'),
        ('app.ventas.servicio.Servicio', 'app.inventario.modelos.Estado', 'otro', '1'),
        ('app.inventario.modelos.Producto', 'app.inventario.modelos.Estado', 'estado', '1')}

    r, doc = programa(tmp_path, 'ts', {
        'src/shop/cart.ts': '''
            import { User } from './user';
            export class Cart { owner?: User; }''',
        'src/shop/user.ts': '''
            import { Cart } from './cart';
            export class User { cart: Cart = new Cart(); }''',
        'src/admin/user.ts': 'export class User { constructor(public name: string) {} }\n'}, lenguaje='typescript')
    assert r['clases_repetidas_omitidas'] == [] and r['paquetes_con_clases'] == ['src.admin', 'src.shop']
    assert navegaciones(doc) == {('src.shop.Cart', 'src.shop.User', 'owner', '0..1'), ('src.shop.User', 'src.shop.Cart', 'cart', '1')}

    r, doc = programa(tmp_path, 'go', {
        'ventas/models/user.go': 'package models\n\ntype User struct {\n\tCart *Cart\n}\n\ntype Cart struct {\n\tItems []string\n}\n',
        'admin/models/user.go': 'package models\n\nimport m "app/ventas/models"\n\ntype User struct {\n\tRole string\n\tVentas *m.User\n}\n'},
        lenguaje='go')
    assert r['clases_repetidas_omitidas'] == [] and r['paquetes_con_clases'] == ['admin.models', 'ventas.models']
    assert navegaciones(doc) == {('ventas.models.User', 'ventas.models.Cart', 'Cart', '1'),
                                 ('admin.models.User', 'ventas.models.User', 'Ventas', '1')}


JAVA_DOS_CLIENTES = {
    'modelo/Cliente.java': 'package com.tienda.modelo;\npublic class Cliente { private String nombre; }\n',
    'admin/Cliente.java': 'package com.tienda.admin;\npublic class Cliente {\n    private String usuario;\n'
                          '    private com.tienda.modelo.Cliente datos;\n}\n',
    'servicio/PedidoServicio.java': 'package com.tienda.servicio;\nimport com.tienda.modelo.Cliente;\n'
                                    'public class PedidoServicio { private Cliente actual; }\n',
    'otro/Reporte.java': 'package com.tienda.otro;\npublic class Reporte { private Cliente cliente; private java.util.Date fecha; }\n',
    'otro/Date.java': 'package com.tienda.util;\npublic class Date { }\n',
}


def test_programa_resuelve_los_tipos_con_imports_y_nombres_calificados(tmp_path):
    r, doc = programa(tmp_path, 'java', JAVA_DOS_CLIENTES)
    assert navegaciones(doc) == {('com.tienda.admin.Cliente', 'com.tienda.modelo.Cliente', 'datos', '1'),
                                 ('com.tienda.servicio.PedidoServicio', 'com.tienda.modelo.Cliente', 'actual', '1')}
    # sin import no se puede saber cual Cliente es: no se elige uno, se deja el atributo y se avisa
    reporte = por_calificado(doc, 'com.tienda.otro.Reporte')
    assert atributos(reporte) == [('cliente', 'Cliente'), ('fecha', 'java.util.Date')]
    assert r['tipos_ambiguos'] == ['Reporte: Cliente (com.tienda.admin.Cliente, com.tienda.modelo.Cliente)']


def test_programa_python_objeto_creado_con_su_modulo(tmp_path):
    """self.x = modulo.Clase() se resuelve con el modulo (no con la unica clase que se llame igual en el programa)."""
    r, doc = programa(tmp_path, 'pyval', {
        'app/__init__.py': '',
        'app/handler.py': 'class ErrorHandler:\n    pass\n',
        'app/otro.py': 'class ErrorHandler:\n    pass\n\n\nclass Lock:\n    pass\n',
        'app/lector.py': '''
            import threading
            from . import handler
            class Lector:
                def __init__(self):
                    self.manejador = handler.ErrorHandler()
                    self.candado = threading.Lock()
            '''}, lenguaje='python')
    assert navegaciones(doc) == {('app.lector.Lector', 'app.handler.ErrorHandler', 'manejador', '1')}
    assert atributos(por_calificado(doc, 'app.lector.Lector')) == [('candado', 'threading.Lock')]
    assert 'tipos_ambiguos' not in r

def test_programa_campos_genericos_y_multiplicidades(tmp_path):
    r, doc = programa(tmp_path, 'gen', {
        'app/Servicio.java': '''
            package app;
            import java.util.*;
            import java.util.concurrent.CompletableFuture;
            public class Servicio {
                private Repositorio<Pedido, Long> repo;
                private List<Pedido> pedidos;
                private Optional<Cliente> cliente;
                private Map<String, Producto> productos;
                private Pedido[] historial;
                private CompletableFuture<Cliente> futuro;
            }''',
        'app/Repositorio.java': 'package app;\npublic interface Repositorio<T, ID> { }\n',
        'app/Pedido.java': 'package app;\npublic class Pedido { }\n',
        'app/Cliente.java': 'package app;\npublic class Cliente { }\n',
        'app/Producto.java': 'package app;\npublic class Producto { }\n'})
    assert navegaciones(doc) == {('app.Servicio', 'app.Repositorio', 'repo', '1'), ('app.Servicio', 'app.Pedido', 'pedidos', '0..*'),
                                 ('app.Servicio', 'app.Cliente', 'cliente', '0..1'),
                                 ('app.Servicio', 'app.Producto', 'productos', '0..*'),
                                 ('app.Servicio', 'app.Pedido', 'historial', '0..*')}
    assert atributos(por_calificado(doc, 'app.Servicio')) == [('futuro', 'CompletableFuture<Cliente>')]

    r, doc = programa(tmp_path, 'pygen', {'modelo.py': '''
        from dataclasses import dataclass, field
        from typing import Dict, List, Optional

        class Equipo:
            pass

        @dataclass
        class Renta:
            equipo: Optional[Equipo] = None
            otros: List["Equipo"] = field(default_factory=list)
            por_clave: Dict[str, Equipo] = field(default_factory=dict)
            principal: Equipo | None = None
        '''}, lenguaje='python')
    assert navegaciones(doc) == {('modelo.Renta', 'modelo.Equipo', 'equipo', '0..1'), ('modelo.Renta', 'modelo.Equipo', 'otros', '0..*'),
                                 ('modelo.Renta', 'modelo.Equipo', 'por_clave', '0..*'),
                                 ('modelo.Renta', 'modelo.Equipo', 'principal', '0..1')}


def test_programa_en_go_coincide_con_su_codigo(tmp_path):
    """Los tipos de Go quedan en el modelo como se escribieron ([]string, *Cart, map[string]*Item, time.Time) y la
    comparacion los entiende."""
    archivos = {'ventas/models/cart.go': '''
        package models

        import "time"

        type Item struct {
            Sku    string
            Precio float64
        }

        type Cart struct {
            Items  []string
            Dueno  *User
            Partes map[string]*Item
            Creado time.Time
            Notas  []*Item
        }

        type User struct {
            Nombre string
        }
        '''}
    r, doc = programa(tmp_path, 'go', archivos, lenguaje='go')
    carrito = por_calificado(doc, 'ventas.models.Cart')
    assert atributos(carrito) == [('Items', '[]string'), ('Creado', 'time.Time')]
    assert navegaciones(doc) >= {('ventas.models.Cart', 'ventas.models.User', 'Dueno', '1'),
                                 ('ventas.models.Cart', 'ventas.models.Item', 'Partes', '0..*'),
                                 ('ventas.models.Cart', 'ventas.models.Item', 'Notas', '0..*')}
    mdj = str(tmp_path / 'go.mdj')
    cmp = ok(tool('staruml_comparar_codigo', archivo=mdj, diagrama=r['diagramas'][0]['id'], ruta_codigo=str(tmp_path / 'go'),
                  lenguaje='go'))
    assert cmp['porcentaje_sincronizacion'] == 100.0, cmp['detalles_por_clase']


def test_java_de_cada_diagrama_de_clases_del_modelo_real_compila(real, tmp_path):
    """Con el modelo real (STARUML_MCP_MODELO_REAL o pruebas/*.mdj; sin el se omite), el Java de cada diagrama de clases
    compila aunque las entidades traigan sus get/set como operaciones, y vuelve al 100 %. El modelo no se modifica."""
    if not shutil.which('javac'):
        pytest.skip('sin javac')
    antes = open(real, 'rb').read()
    probados = 0
    for dg in M.Doc(real).diagrams():
        if dg['_type'] != 'UMLClassDiagram' or not dg.get('ownedViews'):
            continue
        out = str(tmp_path / f'java{probados}')
        r = ok(tool('staruml_diagrama_a_codigo', archivo=real, diagrama=dg['_id'], lenguaje='java', carpeta_salida=out))
        if not r['escritos']:
            continue
        compilado = compilar_java(out)
        assert compilado[0], (dg.get('name'), compilado[1])
        cmp = ok(tool('staruml_comparar_codigo', archivo=real, diagrama=dg['_id'], ruta_codigo=out, lenguaje='java'))
        assert cmp['porcentaje_sincronizacion'] == 100.0, (dg.get('name'), cmp['detalles_por_clase'])
        probados += 1
    assert probados
    assert open(real, 'rb').read() == antes


# --- clases anidadas de Python ---

PY_ANIDADAS = {'app/__init__.py': '', 'app/arbol.py': '''
    from enum import Enum
    from typing import List


    class Arbol:
        raiz: "Arbol.Nodo"

        class Nodo:
            valor: int
            hijos: List["Arbol.Nodo"]

            class Etiqueta:
                texto: str

        class Color(Enum):
            ROJO = 1
            NEGRO = 2

        def insertar(self, valor: int) -> None:
            class Paso:  # local del metodo: no es parte del modelo
                def __init__(self):
                    self.ajeno = 0
            self.ultimo = valor


    class Lista:
        cabeza: "Lista.Nodo"

        class Nodo:
            dato: str
    '''}


def test_python_lee_las_clases_anidadas(tmp_path):
    r = C.escanear_codigo(fuentes(str(tmp_path / 'src'), PY_ANIDADAS), 'python')
    assert {n: c['externa'] for n, c in r.items()} == {'Arbol': '', 'Nodo': 'Arbol', 'Etiqueta': 'Arbol.Nodo', 'Color': 'Arbol',
                                                        'Lista': ''}
    assert r['Color']['tipo_decl'] == 'enum' and r['Color']['literales'] == ['ROJO', 'NEGRO']
    assert [a['nombre'] for a in r['Etiqueta']['atributos']] == ['texto']
    # la clase local del metodo no aparece y su self.ajeno no es de Arbol
    assert 'Paso' not in r and [a['nombre'] for a in r['Arbol']['atributos']] == ['raiz', 'ultimo']
    # dos anidadas que se llaman igual en clases distintas: se avisa, como en Java
    assert list(C._repetidas(r)) == ['Nodo']


def test_python_anidadas_en_programa_a_diagrama(tmp_path):
    r, doc = programa(tmp_path, 'py', PY_ANIDADAS, lenguaje='python')
    assert r['clases'] == 5 and r['enumeraciones'] == 1 and r['clases_repetidas_omitidas'] == []
    nodo = por_calificado(doc, 'app.arbol.Arbol.Nodo')
    assert doc.ids[doc.parent[nodo['_id']]]['name'] == 'Arbol'  # dentro de su clase externa, como en StarUML
    assert atributos(nodo) == [('valor', 'int')]
    assert atributos(por_calificado(doc, 'app.arbol.Arbol.Nodo.Etiqueta')) == [('texto', 'str')]
    assert atributos(por_calificado(doc, 'app.arbol.Lista.Nodo')) == [('dato', 'str')]
    assert por_calificado(doc, 'app.arbol.Arbol.Color')['_type'] == 'UMLEnumeration'
    assert atributos(por_calificado(doc, 'app.arbol.Arbol')) == [('ultimo', 'int')]
    assert not clases_llamadas(doc, 'Paso')
    assert navegaciones(doc) == {('app.arbol.Arbol', 'app.arbol.Arbol.Nodo', 'raiz', '1'),
                                 ('app.arbol.Arbol.Nodo', 'app.arbol.Arbol.Nodo', 'hijos', '0..*'),
                                 ('app.arbol.Lista', 'app.arbol.Lista.Nodo', 'cabeza', '1')}


def test_python_anidadas_en_la_comparacion(tmp_path):
    archivos = {'modelo.py': '''
        from dataclasses import dataclass
        from enum import Enum
        from typing import List


        class Pedido:
            folio: int
            lineas: List["Pedido.Linea"]
            estado: "Pedido.Estado"

            class Estado(Enum):
                NUEVO = 1

            @dataclass
            class Linea:
                cantidad: int
                precio: float

                def subtotal(self) -> float:
                    return self.cantidad * self.precio
        '''}
    r, _ = programa(tmp_path, 'ped', archivos, lenguaje='python')
    mdj, src = str(tmp_path / 'ped.mdj'), str(tmp_path / 'ped')
    cmp = ok(tool('staruml_comparar_codigo', archivo=mdj, diagrama=r['diagramas'][0]['id'], ruta_codigo=src, lenguaje='python'))
    assert cmp['clases_faltantes_en_codigo'] == [] and cmp['porcentaje_sincronizacion'] == 100.0, cmp['detalles_por_clase']
    assert cmp['detalles_por_clase']['Linea']['atributos']['coincidentes'] == ['cantidad', 'precio']
    p = os.path.join(src, 'modelo.py')
    texto = open(p, encoding='utf-8').read()
    assert '        precio: float\n' in texto
    open(p, 'w', encoding='utf-8').write(texto.replace('        precio: float\n', ''))
    cmp = ok(tool('staruml_comparar_codigo', archivo=mdj, diagrama=r['diagramas'][0]['id'], ruta_codigo=src, lenguaje='python'))
    assert cmp['detalles_por_clase']['Linea']['atributos']['faltan_en_codigo'] == ['precio']


# --- tipos con su tamano: char, short, byte, float y las clases envoltorio ---

TIPOS = [('letra', 'char'), ('corto', 'short'), ('octeto', 'byte'), ('peso', 'float'), ('folio', 'Long'), ('cuenta', 'int'),
         ('grande', 'long'), ('monto', 'BigDecimal'), ('precio', 'double'), ('veces', 'Integer')]


def _clase_con_tipos(path):
    """Medida con un atributo de cada tipo de TIPOS y convertir(c: char, f: float, b: byte, s: short): Long."""
    doc = M.Doc(path)
    pk, dg = doc.find('Analisis'), doc.diagram('cu_1')
    c = {'_type': 'UMLClass', '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': 'Medida'}
    c['attributes'] = [{'_type': 'UMLAttribute', '_id': doc.new_id(), '_parent': M.ref(c['_id']), 'name': n, 'type': t}
                       for n, t in TIPOS]
    o = {'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': M.ref(c['_id']), 'name': 'convertir'}
    o['parameters'] = [{'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': M.ref(o['_id']), 'name': n, 'type': t}
                       for n, t in (('c', 'char'), ('f', 'float'), ('b', 'byte'), ('s', 'short'))]
    o['parameters'].append({'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': M.ref(o['_id']), 'type': 'Long',
                            'direction': 'return'})
    c['operations'] = [o]
    pk['ownedElements'].append(c)
    doc.reindex()
    M.vista_nueva(doc, dg, c, 40, 40)
    doc.save(backup=False)


GENERADO = {
    'java': ('private char letra;', 'private short corto;', 'private byte octeto;', 'private float peso;', 'private Long folio;',
             'private int cuenta;', 'private long grande;', 'private BigDecimal monto;', 'private double precio;',
             'private Integer veces;', 'public Long convertir(char c, float f, byte b, short s)'),
    'csharp': ('public char Letra', 'public short Corto', 'public byte Octeto', 'public float Peso', 'public long Folio',
               'public int Cuenta', 'public long Grande', 'public decimal Monto', 'public double Precio', 'public int Veces',
               'public long Convertir(char c, float f, byte b, short s)'),
    'python': ('letra: Optional[str]', 'corto: Optional[int]', 'octeto: Optional[int]', 'peso: Optional[float]',
               'folio: Optional[int]', 'monto: Optional[Decimal]', 'precio: Optional[float]',
               'def convertir(self, c: str, f: float, b: int, s: int) -> int:'),
    'typescript': ('letra?: string', 'corto?: number', 'octeto?: number', 'peso?: number', 'folio?: number', 'veces?: number',
                   'convertir(c: string, f: number, b: number, s: number): number'),
}
# (texto generado, texto cambiado, discrepancia esperada o None si el lenguaje no distingue los dos tipos)
CAMBIOS = {
    'java': [('private int cuenta;', 'private long cuenta;', ('cuenta', 'int', 'long')),
             ('private BigDecimal monto;', 'private double monto;', ('monto', 'decimal', 'double')),
             ('private float peso;', 'private double peso;', ('peso', 'float', 'double')),
             ('private char letra;', 'private String letra;', ('letra', 'char', 'String')),
             ('private Long folio;', 'private long folio;', None), ('private Integer veces;', 'private int veces;', None)],
    'csharp': [('public int Cuenta', 'public long Cuenta', ('cuenta', 'int', 'long')),
               ('public decimal Monto', 'public double Monto', ('monto', 'decimal', 'double')),
               ('public short Corto', 'public int Corto', ('corto', 'short', 'int')),
               ('public long Folio', 'public long? Folio', None)],
    'python': [('monto: Optional[Decimal]', 'monto: Optional[float]', ('monto', 'decimal', 'float')),
               ('precio: Optional[float]', 'precio: Optional[int]', ('precio', 'double', 'int')),
               ('cuenta: Optional[int]', 'cuenta: int', None), ('peso: Optional[float]', 'peso: float', None)],
    'typescript': [('public letra?: string', 'public letra?: number', ('letra', 'char', 'double')),
                   ('public cuenta?: number', 'public cuenta?: bigint', None)],
}


@pytest.mark.parametrize('lenguaje', ['java', 'csharp', 'python', 'typescript'])
def test_generadores_conservan_char_short_byte_float_y_long(vacio, tmp_path, lenguaje):
    _clase_con_tipos(vacio)
    out = str(tmp_path / lenguaje)
    r = ok(tool('staruml_diagrama_a_codigo', archivo=vacio, diagrama='cu_1', lenguaje=lenguaje, carpeta_salida=out))
    archivo = os.path.join(out, r['archivos'][0])
    texto = open(archivo, encoding='utf-8').read()
    for linea in GENERADO[lenguaje]:
        assert linea in texto, (lenguaje, linea, texto)
    if lenguaje == 'java':
        compilado = compilar_java(out)
        assert compilado is None or compilado[0], compilado[1]
    if lenguaje == 'python':
        cp = subprocess.run([sys.executable, os.path.basename(archivo)], capture_output=True, text=True, cwd=out)
        assert cp.returncode == 0, cp.stderr[-500:]
    cmp = ok(tool('staruml_comparar_codigo', archivo=vacio, diagrama='cu_1', ruta_codigo=out, lenguaje=lenguaje))
    assert cmp['porcentaje_sincronizacion'] == 100.0, cmp['detalles_por_clase']
    # el codigo cambia de tipo: int contra long y double contra BigDecimal son discrepancias (Long y long no; en Python
    # int no tiene tamano y en TypeScript todo es number)
    for viejo, nuevo, _ in CAMBIOS[lenguaje]:
        assert viejo in texto, viejo
        texto = texto.replace(viejo, nuevo)
    open(archivo, 'w', encoding='utf-8').write(texto)
    cmp = ok(tool('staruml_comparar_codigo', archivo=vacio, diagrama='cu_1', ruta_codigo=out, lenguaje=lenguaje))
    esperado = [{'atributo': d[0], 'tipo_uml': d[1], 'tipo_codigo': d[2]} for _, _, d in CAMBIOS[lenguaje] if d]
    obtenido = cmp['detalles_por_clase']['Medida']['atributos']['discrepancias_tipo']
    assert sorted(obtenido, key=str) == sorted(esperado, key=str)


def test_tipos_del_codigo_al_modelo_y_de_vuelta(vacio, tmp_path):
    src = fuentes(str(tmp_path / 'src'), {'Lectura.java': '''
        package lab;
        public class Lectura {
            private char clave;
            private short canal;
            private byte nivel;
            private float temperatura;
            private Long id;
            private Integer intentos;
            public Long registrar(char c, float f) { return id; }
        }'''})
    ok(tool('staruml_codigo_a_diagrama', archivo=vacio, ruta_codigo=src, paquete='Analisis', diagrama='cu_1'))
    lectura = M.Doc(vacio).find('UMLClass:Lectura')
    assert atributos(lectura) == [('clave', 'char'), ('canal', 'short'), ('nivel', 'byte'), ('temperatura', 'float'),
                                  ('id', 'Long'), ('intentos', 'Integer')]
    esperados = {'java': ('private char clave;', 'private short canal;', 'private byte nivel;', 'private float temperatura;',
                          'private Long id;', 'private Integer intentos;', 'public Long registrar(char c, float f)'),
                 'csharp': ('public char Clave', 'public short Canal', 'public byte Nivel', 'public float Temperatura',
                            'public long Id', 'public int Intentos', 'public long Registrar(char c, float f)')}
    for lenguaje, lineas in esperados.items():
        out = str(tmp_path / lenguaje)
        r = ok(tool('staruml_diagrama_a_codigo', archivo=vacio, diagrama='cu_1', lenguaje=lenguaje, carpeta_salida=out))
        texto = open(os.path.join(out, r['archivos'][0]), encoding='utf-8').read()
        for linea in lineas:
            assert linea in texto, (lenguaje, linea)
        cmp = ok(tool('staruml_comparar_codigo', archivo=vacio, diagrama='cu_1', ruta_codigo=out, lenguaje=lenguaje))
        assert cmp['porcentaje_sincronizacion'] == 100.0, (lenguaje, cmp['detalles_por_clase'])
    compilado = compilar_java(str(tmp_path / 'java'))
    assert compilado is None or compilado[0], compilado[1]
    # del C# generado a otro modelo: los tipos siguen igual
    otro = str(tmp_path / 'otro.mdj')
    shutil.copy(vacio, otro)
    ok(tool('mdj_borrar', archivo=otro, elemento='Lectura'))
    ok(tool('staruml_codigo_a_diagrama', archivo=otro, ruta_codigo=str(tmp_path / 'csharp'), paquete='Analisis'))
    assert atributos(M.Doc(otro).find('UMLClass:Lectura')) == [('Clave', 'char'), ('Canal', 'short'), ('Nivel', 'byte'),
                                                              ('Temperatura', 'float'), ('Id', 'long'), ('Intentos', 'int')]

    # Python: del codigo al modelo y de vuelta, sin cambiar float por otra cosa
    py = fuentes(str(tmp_path / 'py'), {'sensor.py': '''
        from decimal import Decimal


        class Sensor:
            codigo: str
            nivel: int
            lectura: float
            monto: Decimal
        '''})
    ok(tool('staruml_codigo_a_diagrama', archivo=vacio, ruta_codigo=py, paquete='Analisis', diagrama='cu_1'))
    assert atributos(M.Doc(vacio).find('UMLClass:Sensor')) == [('codigo', 'str'), ('nivel', 'int'), ('lectura', 'float'),
                                                              ('monto', 'Decimal')]
    out = str(tmp_path / 'py_gen')
    ok(tool('staruml_diagrama_a_codigo', archivo=vacio, diagrama='cu_1', lenguaje='python', carpeta_salida=out))
    texto = open(os.path.join(out, 'Sensor.py'), encoding='utf-8').read()
    for linea in ('codigo: Optional[str]', 'nivel: Optional[int]', 'lectura: Optional[float]', 'monto: Optional[Decimal]'):
        assert linea in texto, linea
    cmp = ok(tool('staruml_comparar_codigo', archivo=vacio, diagrama='cu_1', ruta_codigo=out, lenguaje='python'))
    assert cmp['porcentaje_sincronizacion'] == 100.0, cmp['detalles_por_clase']


def test_sincronizar_no_cambia_lo_que_el_lenguaje_escribe_de_otra_forma(vacio, tmp_path):
    _clase_con_tipos(vacio)
    kt = fuentes(str(tmp_path / 'kt'), {'Medida.kt': '''
        class Medida {
            var grande: Long = 0
            var precio: Double = 0.0
            var cuenta: Long = 0
        }'''})
    r = ok(tool('staruml_codigo_a_diagrama', archivo=vacio, ruta_codigo=kt, paquete='Analisis', modo='sincronizar'))
    assert r['tipos_cambiados'] == {'Medida': ['cuenta: int -> Long']}  # Long es long; Double es double
    py = fuentes(str(tmp_path / 'py'), {'medida.py': '''
        class Medida:
            grande: int
            peso: float
            precio: float
            monto: float
        '''})
    r = ok(tool('staruml_codigo_a_diagrama', archivo=vacio, ruta_codigo=py, paquete='Analisis', modo='sincronizar'))
    # en Python int no tiene tamano y float es de doble precision; Decimal si es otro tipo
    assert r['tipos_cambiados'] == {'Medida': ['monto: BigDecimal -> float']}


@pytest.mark.parametrize('uml,codigo,lenguaje,igual', [
    ('int', 'long', 'java', False), ('BigDecimal', 'double', 'java', False), ('long', 'Long', 'java', True),
    ('int', 'Integer', 'java', True), ('char', 'String', 'java', False), ('char', 'Character', 'java', True),
    ('float', 'double', 'csharp', False), ('short', 'Int16', 'csharp', True), ('decimal', 'decimal?', 'csharp', True),
    ('byte', 'sbyte', 'csharp', True), ('long', 'Long?', 'kotlin', True), ('int', 'Long', 'kotlin', False),
    ('int', 'int64', 'go', False), ('double', 'float64', 'go', True), ('float', 'float32', 'go', True),
    ('int', 'number', 'typescript', True), ('BigDecimal', 'number', 'typescript', True), ('char', 'string', 'typescript', True),
    ('long', 'int', 'python', True), ('double', 'float', 'python', True), ('BigDecimal', 'float', 'python', False),
    ('BigDecimal', 'Decimal', 'python', True), ('Date', 'LocalDateTime', 'java', True), ('List<int>', 'List<Long>', 'java', False),
    ('List<Long>', 'ArrayList<Long>', 'java', True), ('Map<String, BigDecimal>', 'Map<String, Double>', 'java', False),
])
def test_clave_de_tipo_por_lenguaje(uml, codigo, lenguaje, igual):
    assert (C._clave_tipo(uml, lenguaje) == C._clave_tipo(codigo, lenguaje)) is igual
