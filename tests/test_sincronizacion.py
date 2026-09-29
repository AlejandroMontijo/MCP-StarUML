# Comparar diagrama vs codigo, generar codigo desde el diagrama e importar codigo al diagrama.
import glob
import os
import shutil
import subprocess
import sys

import pytest

import staruml_compare as C
from apoyo import M, fuentes, guardar_json, ids_integros, modelo_dominio, ok, proyecto_vacio, tool


def compilar(lenguaje, carpeta):
    """(True, '') si el codigo generado compila/importa. Se omite la prueba si falta el compilador."""
    archivos = sorted(glob.glob(os.path.join(carpeta, '*.*')))
    if lenguaje == 'java':
        if not shutil.which('javac'):
            pytest.skip('sin javac')
        r = subprocess.run([shutil.which('javac'), '-d', os.path.join(carpeta, 'bin')] + archivos, capture_output=True, text=True)
        return r.returncode == 0, r.stderr[-800:]
    if lenguaje == 'typescript':
        if not shutil.which('tsc'):
            pytest.skip('sin tsc')
        r = subprocess.run([shutil.which('tsc'), '--noEmit', '--strict', '--target', 'es2020'] + archivos, capture_output=True, text=True)
        return r.returncode == 0, r.stdout[-800:]
    malos = [(f, r.stderr[-300:]) for f in archivos
             for r in [subprocess.run([sys.executable, f], capture_output=True, text=True, cwd=carpeta)] if r.returncode]
    return not malos, str(malos)


# --- comparar ---

def test_comparar_clases_completo(dominio, tmp_path):
    src = fuentes(str(tmp_path / 'src'), {'Dominio.java': '''
        import java.util.*;
        class Direccion { String calle; }
        class Cliente { String nombre; String email; Direccion direccion; List<Pedido> pedidos; }
        class Pedido { double total; List<Item> items; double calcularTotal() { return total; } }
        class Item { int cantidad; }
        class ClienteVIP extends Cliente { double descuento; }'''})
    r = ok(tool('staruml_comparar_codigo', archivo=dominio, diagrama='cu_1', ruta_codigo=src))
    assert r['porcentaje_sincronizacion'] == 100.0
    assert r['actores_omitidos'] == ['Usuario'] and r['clases_faltantes_en_codigo'] == []


def test_comparar_detecta_faltantes_tipos_y_multiplicidad(dominio, tmp_path):
    src = fuentes(str(tmp_path / 'src'), {'Cliente.java': '''
        class Cliente {
            String nombre;
            int email;
            Pedido pedido;
        }'''})
    r = ok(tool('staruml_comparar_codigo', archivo=dominio, diagrama='cu_1', ruta_codigo=src))
    d = r['detalles_por_clase']['Cliente']
    assert d['atributos']['faltan_en_codigo'] == ['direccion']
    assert d['atributos']['discrepancias_tipo'] == [{'atributo': 'email', 'tipo_uml': 'String', 'tipo_codigo': 'int'}]
    assert d['asociaciones']['verificadas_en_codigo'] == []
    assert d['asociaciones']['multiplicidad_incorrecta'][0]['esperado'] == 'coleccion'
    assert {c['nombre'] for c in r['clases_faltantes_en_codigo']} == {'Direccion', 'Pedido', 'Item', 'ClienteVIP'}
    assert 0 < r['porcentaje_sincronizacion'] < 50


def test_comparar_empareja_acentos_y_mayusculas(modelo, tmp_path):
    src = fuentes(str(tmp_path / 'src'), {'Sesion.cs': 'public class Sesion { public string Inicio { get; set; } public string Fin { get; set; } }'})
    r = ok(tool('staruml_comparar_codigo', archivo=modelo, diagrama='cu_1', ruta_codigo=src))
    assert 'Sesión' in [c['uml'] for c in r['clases_coincidentes']]
    assert r['detalles_por_clase']['Sesión']['atributos']['coincidentes'] == ['inicio', 'fin']


def test_comparar_atributo_tipado_con_referencia(tmp_path):
    p = modelo_dominio(str(tmp_path / 'ref.mdj'), tipo_ref=True)
    src = fuentes(str(tmp_path / 'src'), {'Cliente.java': 'class Cliente { String nombre; String email; Direccion direccion; }'})
    r = ok(tool('staruml_comparar_codigo', archivo=p, diagrama='cu_1', ruta_codigo=src))
    assert 'direccion' in r['detalles_por_clase']['Cliente']['atributos']['coincidentes']


def _secuencia_ascii(path):
    guardar_json(proyecto_vacio(), path)
    doc = M.Doc(path)
    pk = doc.find('Analisis')
    for n, st in (('A', 'boundary'), ('B', 'control'), ('E', 'entity')):
        pk['ownedElements'].append({'_type': 'UMLClass', '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': n,
                                    'stereotype': M.ref(doc.stereotype_id(st))})
    doc.reindex()
    M.generar_secuencia(doc, 'cu_1_FB', [{'clave': 'u', 'tipo': 'Usuario'}, {'clave': 'a', 'tipo': 'A'}, {'clave': 'b', 'tipo': 'B'},
                                          {'clave': 'e', 'tipo': 'E'}],
                        [{'de': 'u', 'a': 'a', 'nombre': 'pedir()'}, {'de': 'a', 'a': 'b', 'nombre': 'procesar()'},
                         {'de': 'b', 'a': 'e', 'nombre': 'consultar datos'}, {'de': 'e', 'a': 'b', 'nombre': 'datos', 'reply': True},
                         {'de': 'b', 'a': 'a', 'nombre': 'mostrar()'}, {'de': 'a', 'a': 'u', 'nombre': 'ver()'}])
    doc.save(backup=False)
    return path


def test_comparar_secuencia_metricas(tmp_path):
    p = _secuencia_ascii(str(tmp_path / 's.mdj'))
    vacio = fuentes(str(tmp_path / 'v'), {'X.java': 'class A { }\nclass B { }\nclass E { }\n'})
    lleno = fuentes(str(tmp_path / 'l'), {'X.java': '''
        class A { B b; void pedir() { b.procesar(); } void mostrar() {} }
        class B { E e; A a; void procesar() { e.consultarDatos(); a.mostrar(); } }
        class E { void consultarDatos() {} }'''})
    r0 = ok(tool('staruml_comparar_codigo', archivo=p, diagrama='cu_1_FB', ruta_codigo=vacio))
    r1 = ok(tool('staruml_comparar_codigo', archivo=p, diagrama='cu_1_FB', ruta_codigo=lleno))
    assert r0['porcentaje_sincronizacion'] == 0.0 and r1['porcentaje_sincronizacion'] == 100.0
    assert r1['resumen']['mensajes_que_aplican'] == 4 and r1['resumen']['mensajes_no_aplican'] == 2
    assert r1['porcentaje_flujo'] == 100.0  # cada emisor invoca el metodo del receptor
    assert r0['lifelines'][0] == {'tipo_uml': 'Usuario', 'estereotipo': 'actor', 'aplica': False}


# --- generar ---

@pytest.mark.parametrize('lenguaje', ['java', 'python', 'typescript'])
def test_generar_compila_y_vuelve_al_100(dominio, tmp_path, lenguaje):
    out = str(tmp_path / lenguaje)
    r = ok(tool('staruml_diagrama_a_codigo', archivo=dominio, diagrama='cu_1', lenguaje=lenguaje, carpeta_salida=out))
    assert len(r['escritos']) == 5  # sin el actor
    compila, errores = compilar(lenguaje, out)
    assert compila, errores
    cmp = ok(tool('staruml_comparar_codigo', archivo=dominio, diagrama='cu_1', ruta_codigo=out, lenguaje=lenguaje))
    assert cmp['porcentaje_sincronizacion'] == 100.0, cmp['detalles_por_clase']


def test_generar_sin_carpeta_devuelve_el_codigo(dominio):
    r = ok(tool('staruml_diagrama_a_codigo', archivo=dominio, diagrama='cu_1', lenguaje='java', paquete_codigo=''))
    assert 'public class Pedido' in r['codigo']['Pedido.java'] and not r['codigo']['Pedido.java'].startswith('package')


def test_generar_no_sobrescribe_sin_permiso(dominio, tmp_path):
    out = tmp_path / 'src'
    out.mkdir()
    (out / 'Pedido.java').write_text('// mio\n')
    r = ok(tool('staruml_diagrama_a_codigo', archivo=dominio, diagrama='cu_1', carpeta_salida=str(out)))
    assert (out / 'Pedido.java').read_text() == '// mio\n' and r['omitidos_por_existir'] == ['Pedido.java'] and 'nota' in r
    ok(tool('staruml_diagrama_a_codigo', archivo=dominio, diagrama='cu_1', carpeta_salida=str(out), sobrescribir=True))
    assert 'class Pedido' in (out / 'Pedido.java').read_text()


def test_generar_nunca_escribe_fuera_de_la_carpeta(dominio, tmp_path):
    doc = M.Doc(dominio)
    pk = doc.find('Analisis')
    for nom in ('../fuera', 'a\\b', 'C:x', 'Orden de Compra'):
        c = {'_type': 'UMLClass', '_id': doc.new_id(), '_parent': M.ref(pk['_id']), 'name': nom}
        pk['ownedElements'].append(c)
        doc.reindex()
        M.vista_nueva(doc, doc.diagram('cu_1'), c, 10, 700)
    doc.save(backup=False)
    out = tmp_path / 'caja' / 'src'
    r = ok(tool('staruml_diagrama_a_codigo', archivo=dominio, diagrama='cu_1', carpeta_salida=str(out)))
    escritos = [f for f in glob.glob(str(tmp_path / 'caja' / '**'), recursive=True) if os.path.isfile(f)]
    assert not os.path.exists(tmp_path / 'caja' / 'fuera.java')
    assert all(os.path.dirname(f) == str(out) for f in escritos)
    assert 'OrdenDeCompra.java' in r['escritos'] and 'Fuera.java' in r['escritos']  # nombres saneados
    src = (out / 'OrdenDeCompra.java').read_text()
    assert 'public class OrdenDeCompra' in src


def test_generar_respeta_navegabilidad(tmp_path):
    p = modelo_dominio(str(tmp_path / 'n.mdj'), nav_item='notNavigable')
    uml = C.extraer_elementos_diagrama(M.Doc(p), 'cu_1')
    assert [a['destino'] for a in uml['clases']['Pedido']['asociaciones']] == []
    assert [a['destino'] for a in uml['clases']['Cliente']['asociaciones']] == ['Pedido']


def test_generar_identificadores_y_roles():
    c = {'nombre': 'Orden de Compra', 'tipo': 'UMLClass', 'atributos': [{'nombre': 'fecha de entrega', 'tipo': 'Date'}], 'metodos': [],
         'asociaciones': [{'origen': 'Orden de Compra', 'destino': 'Sesion', 'mult_destino': '0..*', 'rol_destino': 'sesiones', 'navegable': True}]}
    src = C._generar_clase_java(c, {'Orden de Compra': c, 'Sesion': {'tipo': 'UMLClass'}})
    assert 'public class OrdenDeCompra' in src and 'private LocalDate fechaDeEntrega;' in src
    assert 'private List<Sesion> sesiones = new ArrayList<>();' in src and 'sesioness' not in src


# --- importar ---

def test_importar_agrega_sin_quitar(dominio, tmp_path):
    src = fuentes(str(tmp_path / 'src'), {'Cliente.java': 'public class Cliente {\n    private String nombre;\n    private String telefono;\n}\n'})
    r = ok(tool('staruml_codigo_a_diagrama', archivo=dominio, ruta_codigo=src, paquete='Analisis'))
    assert [a['name'] for a in M.Doc(dominio).find('Cliente')['attributes']] == ['nombre', 'email', 'direccion', 'telefono']
    assert r['atributos_agregados'] == {'Cliente': ['telefono']} and r['modo'] == 'agregar'
    r = ok(tool('staruml_codigo_a_diagrama', archivo=dominio, ruta_codigo=src, paquete='Analisis', modo='sincronizar'))
    assert [a['name'] for a in M.Doc(dominio).find('Cliente')['attributes']] == ['nombre', 'telefono']
    assert r['atributos_quitados'] == {'Cliente': ['email', 'direccion']}


def test_importar_tipos_metodos_y_vistas_sin_encimar(modelo, tmp_path):
    src = fuentes(str(tmp_path / 'src'), {'Factura.java': '''
        public class Factura {
            private double monto;
            private String folio;
            public double calcularIva(double tasa) { return monto * tasa; }
        }''', 'Pago.py': 'class Pago:\n    importe: float\n    def aplicar(self) -> bool:\n        return True\n',
        'Cuenta.ts': 'export class Cuenta { saldo: number = 0; depositar(x: number): void {} }'})
    r = ok(tool('staruml_codigo_a_diagrama', archivo=modelo, ruta_codigo=src, paquete='Analisis', diagrama='cu_1'))
    doc = M.Doc(modelo)
    f = doc.find('Factura')
    assert [(a['name'], a['type']) for a in f['attributes']] == [('monto', 'double'), ('folio', 'String')]
    op = f['operations'][0]
    assert op['name'] == 'calcularIva' and [(p.get('name'), p['type'], p.get('direction')) for p in op['parameters']] == \
        [('tasa', 'double', None), (None, 'double', 'return')]
    assert r['metodos_omitidos_por_robustez'] == {'Cuenta': ['depositar']}  # Cuenta es entity: sin metodos
    assert 'saldo' in [a['name'] for a in doc.find('Cuenta')['attributes']]
    dg = doc.diagram('cu_1')
    cajas = [v for v in dg['ownedViews'] if v['_type'] in ('UMLClassView', 'UMLActorView', 'UMLNoteView')]
    nuevas = {v['vista'] for v in r['vistas_creadas']}
    for a in cajas:
        for b in cajas:
            if a['_id'] in nuevas and a is not b:
                assert not (a['left'] < b['left'] + b['width'] and b['left'] < a['left'] + a['width'] and
                            a['top'] < b['top'] + b['height'] and b['top'] < a['top'] + a['height']), 'vistas encimadas'
    assert all(not doc.get(v).get('suppressAttributes') for v in nuevas)
    assert ids_integros(modelo)
    assert ok(tool('mdj_validar', archivo=modelo, oose=False))['n_colgantes'] == 0
