# staruml_programa_a_diagrama: diagrama de clases de un programa ya hecho (Java en especial).
import json
import random
import time

import pytest

import staruml_compare as C
import staruml_programa as P
from apoyo import PROGRAMA_JAVA, M, fuentes, ids_integros, ok, tool


@pytest.fixture
def programa(tmp_path):
    return fuentes(str(tmp_path / 'tienda'), PROGRAMA_JAVA)


def por_nombre(doc, nombre, tipos=('UMLClass', 'UMLInterface', 'UMLEnumeration')):
    return next(o for o in doc.ids.values() if o and o['_type'] in tipos and o.get('name') == nombre)


def vistas_de_cajas(dg):
    return [v for v in dg['ownedViews'] if v['_type'] in ('UMLClassView', 'UMLInterfaceView', 'UMLEnumerationView')]


def geometria_limpia(doc, dg):
    """Ninguna caja encima de otra y ninguna linea cruzando una caja que no sea la suya."""
    cajas = {v['_id']: P._caja(v) for v in vistas_de_cajas(dg)}
    lista = list(cajas.values())
    for i, a in enumerate(lista):
        for b in lista[i + 1:]:
            assert not (a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]), ('cajas encimadas', a, b)
    for v in dg['ownedViews']:
        if 'points' not in v:
            continue
        pts = P._puntos(v)
        assert all(x >= 0 and y >= 0 for x, y in pts), ('linea fuera del lienzo', v['points'])
        propias = (v['tail']['$ref'], v['head']['$ref'])
        otras = [c for i, c in cajas.items() if i not in propias]
        assert P._cruces(pts, otras) == 0, ('linea que cruza una caja', doc.name_of(v['model']['$ref']), v['points'])


def test_programa_java_en_proyecto_nuevo(programa, tmp_path):
    mdj = str(tmp_path / 'tienda.mdj')
    r = ok(tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=programa))
    assert r['archivo_nuevo'] and r['guardado_en'] == mdj and r['respaldo'] is None
    assert (r['clases'], r['interfaces'], r['enumeraciones']) == (8, 2, 1)  # PedidoTest (pruebas) no entra
    assert (r['generalizaciones'], r['realizaciones'], r['asociaciones']) == (2, 1, 7)
    assert r['paquetes_del_programa'] == ['com', 'com.tienda', 'com.tienda.modelo', 'com.tienda.servicio']
    assert r['diagramas'][0]['lineas_que_cruzan_cajas'] == [] and r['diagramas'][0]['cajas'] == 11
    assert ids_integros(mdj)
    doc = M.Doc(mdj)
    # paquetes anidados como en Java, dentro del paquete del programa
    raiz = next(o for o in M.modelo_raiz(doc)['ownedElements'] if o.get('name') == 'tienda')
    modelo_pk = doc.ids[doc.parent[por_nombre(doc, 'Cliente')['_id']]]
    tienda_pk = doc.parent[modelo_pk['_id']]
    assert (modelo_pk['name'], doc.name_of(tienda_pk), doc.name_of(doc.parent[tienda_pk])) == ('modelo', 'tienda', 'com')
    assert doc.parent[doc.parent[tienda_pk]] == raiz['_id']  # raiz (tienda) > com > tienda > modelo
    # clasificadores y miembros
    persona = por_nombre(doc, 'Persona')
    assert persona.get('isAbstract') and [a['name'] for a in persona['attributes']] == ['nombre', 'email']
    assert [a.get('visibility') for a in persona['attributes']] == ['protected', 'private']
    assert next(o for o in persona['operations'] if o['name'] == 'describir').get('isAbstract')
    assert [l['name'] for l in por_nombre(doc, 'EstadoPedido')['literals']] == ['NUEVO', 'PAGADO', 'ENVIADO', 'ENTREGADO']
    assert [a['name'] for a in por_nombre(doc, 'Direccion')['attributes']] == ['calle', 'ciudad', 'cp']
    pedido = por_nombre(doc, 'Pedido')
    assert {a['name']: a.get('type') for a in pedido['attributes']} == {'folio': 'int', 'fecha': 'LocalDate'}
    linea = next(o for o in pedido['operations'] if o['name'] == 'agregarLinea')
    assert linea['parameters'][0]['type'] == {'$ref': por_nombre(doc, 'Producto')['_id']}  # tipo del programa: referencia
    cliente = por_nombre(doc, 'Cliente')
    assert [a['name'] for a in cliente['attributes']] == ['contador'] and cliente['attributes'][0].get('isStatic')
    # relaciones
    tipos = {(o['_type'], doc.name_of(o['source']['$ref']), doc.name_of(o['target']['$ref']))
             for o in doc.ids.values() if o and o['_type'] in ('UMLGeneralization', 'UMLInterfaceRealization')}
    assert tipos == {('UMLGeneralization', 'Cliente', 'Persona'), ('UMLGeneralization', 'Empleado', 'Persona'),
                     ('UMLInterfaceRealization', 'Cliente', 'Notificable')}
    asocs = [o for o in doc.ids.values() if o and o['_type'] == 'UMLAssociation']
    ida_y_vuelta = [a for a in asocs if {doc.name_of(a['end1']['reference']['$ref']), doc.name_of(a['end2']['reference']['$ref'])}
                    == {'Cliente', 'Pedido'}]
    assert len(ida_y_vuelta) == 1  # un campo en cada lado: una sola asociacion navegable en ambos sentidos
    extremos = {doc.name_of(e['reference']['$ref']): e for e in (ida_y_vuelta[0]['end1'], ida_y_vuelta[0]['end2'])}
    assert (extremos['Pedido'].get('name'), extremos['Pedido'].get('multiplicity')) == ('pedidos', '0..*')
    assert (extremos['Cliente'].get('name'), extremos['Cliente'].get('multiplicity')) == ('cliente', '1')
    assert all(e.get('navigable') == 'navigable' for e in extremos.values())
    mapa = next(a for a in asocs if doc.name_of(a['end1']['reference']['$ref']) == 'ServicioPedidos'
                and doc.name_of(a['end2']['reference']['$ref']) == 'Pedido')
    assert mapa['end2']['multiplicity'] == '0..*' and mapa['end2']['name'] == 'pedidos'  # Map<Integer, Pedido>
    # diagrama: por defecto al abrir, vistas de cada tipo, sin encimar ni cruzar
    dg = doc.diagram('Diagrama de clases')
    assert dg.get('defaultDiagram') and doc.parent[dg['_id']] == raiz['_id']
    tipos_vista = sorted(v['_type'] for v in dg['ownedViews'])
    assert tipos_vista.count('UMLInterfaceView') == 2 and tipos_vista.count('UMLEnumerationView') == 1
    assert tipos_vista.count('UMLClassView') == 8 and tipos_vista.count('UMLGeneralizationView') == 2
    assert tipos_vista.count('UMLInterfaceRealizationView') == 1 and tipos_vista.count('UMLAssociationView') == 7
    geometria_limpia(doc, dg)
    # la clase base arriba de sus derivadas, y la que tiene el campo arriba de la referida
    top = {doc.name_of(v['model']['$ref']): v['top'] for v in vistas_de_cajas(dg)}
    assert top['Persona'] < top['Cliente'] and top['Persona'] < top['Empleado'] and top['Notificable'] < top['Cliente']
    assert top['Pedido'] < top['LineaPedido'] < top['Producto']
    # el diagrama coincide al 100 % con el programa y el archivo se guarda como StarUML
    cmp = C.comparar_diagrama_con_codigo(doc, 'Diagrama de clases', programa, 'java')
    assert cmp['porcentaje_sincronizacion'] == 100.0, cmp['detalles_por_clase']
    antes = open(mdj, 'rb').read()
    M.Doc(mdj).save(backup=False)
    assert open(mdj, 'rb').read() == antes


def test_paquete_existente_y_reemplazar(programa, tmp_path):
    mdj = str(tmp_path / 't.mdj')
    ok(tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=programa))
    assert 'reemplazar=true' in tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=programa)['error']
    r = ok(tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=programa, reemplazar=True))
    assert not r['archivo_nuevo'] and r['respaldo']
    doc = M.Doc(mdj)
    assert [o['name'] for o in M.modelo_raiz(doc)['ownedElements'] if o['_type'] == 'UMLPackage'] == ['tienda']
    assert [d['name'] for d in doc.diagrams()] == ['Diagrama de clases']
    assert sum(1 for o in doc.ids.values() if o and o['_type'] == 'UMLClass') == 8
    ok(tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=programa, paquete='Otra copia', diagrama='Otra'))
    assert ids_integros(mdj)


def test_en_un_proyecto_existente_no_toca_lo_demas(modelo, programa):
    antes = M.Doc(modelo)
    vistas_cu1 = len(antes.diagram('cu_1')['ownedViews'])
    r = ok(tool('staruml_programa_a_diagrama', archivo=modelo, ruta_codigo=programa, paquete='Diseño'))
    assert not r['archivo_nuevo'] and r['respaldo']
    doc = M.Doc(modelo)
    assert len(doc.diagram('cu_1')['ownedViews']) == vistas_cu1 and not doc.diagram('Diagrama de clases').get('defaultDiagram')
    assert ids_integros(modelo)
    v = ok(tool('mdj_validar', archivo=modelo))
    assert v['n_duplicados'] == v['n_colgantes'] == v['n_parent_mismatch'] == 0


def test_opciones_de_miembros_y_relaciones(programa, tmp_path):
    def generar(nombre, **op):
        mdj = str(tmp_path / f'{nombre}.mdj')
        r = ok(tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=programa, **op))
        return r, M.Doc(mdj)
    r, doc = generar('sin_metodos', metodos=False)
    assert not any(o.get('operations') for o in doc.ids.values() if o and o['_type'] == 'UMLClass')
    assert r['asociaciones'] == 7
    r, doc = generar('publicos', solo_publicos=True)
    assert not por_nombre(doc, 'Pedido').get('attributes') and r['asociaciones'] == 7  # los campos privados siguen como asociaciones
    assert [o['name'] for o in por_nombre(doc, 'Pedido')['operations']] == ['calcularTotal', 'agregarLinea']
    r, doc = generar('accesores', omitir_accesores=True)
    assert [o['name'] for o in por_nombre(doc, 'Persona')['operations']] == ['describir']
    r, doc = generar('atributos', asociaciones=False)
    assert r['asociaciones'] == 0
    cliente = por_nombre(doc, 'Cliente')
    tipos = {a['name']: a.get('type') for a in cliente['attributes']}
    assert tipos['direccion'] == {'$ref': por_nombre(doc, 'Direccion')['_id']} and tipos['pedidos'] == 'List<Pedido>'
    r, doc = generar('dependencias', dependencias=True)
    deps = {(doc.name_of(o['source']['$ref']), doc.name_of(o['target']['$ref'])) for o in doc.ids.values()
            if o and o['_type'] == 'UMLDependency'}
    # por parametros y retornos, salvo entre clases que ya estan asociadas (Cliente.agregarPedido(Pedido))
    assert {('ServicioPedidos', 'Cliente'), ('Pedido', 'Producto')} <= deps
    assert ('Cliente', 'Pedido') not in deps and ('ServicioPedidos', 'Pedido') not in deps
    assert all(v['_type'] != 'UMLDependencyView' or v['model']['$ref'] for v in doc.diagram('Diagrama de clases')['ownedViews'])
    r, doc = generar('pruebas', incluir_pruebas=True)
    assert r['clases'] == 9


def test_un_diagrama_por_paquete(programa, tmp_path):
    mdj = str(tmp_path / 'pk.mdj')
    r = ok(tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=programa, diagrama_por='paquete'))
    assert [d['diagrama'] for d in r['diagramas']] == ['com.tienda.modelo', 'com.tienda.servicio']
    doc = M.Doc(mdj)
    servicio = doc.diagram('com.tienda.servicio')
    assert doc.name_of(doc.parent[servicio['_id']]) == 'servicio'
    assert sorted(doc.name_of(v['model']['$ref']) for v in vistas_de_cajas(servicio)) == ['RepositorioPedidos', 'ServicioPedidos']
    assert len([v for v in servicio['ownedViews'] if v['_type'] == 'UMLAssociationView']) == 1  # la de otro paquete no se dibuja
    for d in doc.diagrams():
        geometria_limpia(doc, d)


def _programa_aleatorio(carpeta, n, semilla):
    rnd = random.Random(semilla)
    nombres = [f'Clase{i:02d}' for i in range(n)]
    interfaces = [f'Servicio{i}' for i in range(max(2, n // 8))]
    archivos = {f'app/{i}.java': f'package app;\npublic interface {i} {{ void ejecutar{i}(); }}\n' for i in interfaces}
    for i, nom in enumerate(nombres):
        base = f' extends {nombres[rnd.randrange(i)]}' if i > 3 and rnd.random() < 0.35 else ''
        impl = f' implements {rnd.choice(interfaces)}' if rnd.random() < 0.3 else ''
        campos = []
        for k in range(rnd.randint(0, 4)):
            otro = rnd.choice(nombres)
            campos.append(f'    private {"java.util.List<" + otro + ">" if rnd.random() < 0.4 else otro} campo{k};')
        campos += [f'    private int dato{k};' for k in range(rnd.randint(0, 3))]
        metodos = [f'    public void ejecutar{impl.split()[-1]}() {{}}'] if impl else []
        metodos += [f'    public int calcular{k}(String texto) {{ return 0; }}' for k in range(rnd.randint(0, 3))]
        archivos[f'app/{nom}.java'] = f'package app;\npublic class {nom}{base}{impl} {{\n' + '\n'.join(campos + metodos) + '\n}\n'
    return fuentes(carpeta, archivos)


@pytest.mark.parametrize('semilla', [1, 7, 42])
def test_programa_grande_sin_encimar_ni_cruzar(tmp_path, semilla):
    codigo = _programa_aleatorio(str(tmp_path / 'app'), 45, semilla)
    mdj = str(tmp_path / 'grande.mdj')
    inicio = time.monotonic()
    r = ok(tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=codigo))
    assert time.monotonic() - inicio < 30
    assert r['diagramas'][0]['lineas_que_cruzan_cajas'] == []
    doc = M.Doc(mdj)
    dg = doc.diagram('Diagrama de clases')
    modelos = [v['model']['$ref'] for v in vistas_de_cajas(dg)]
    assert len(modelos) == len(set(modelos)) == r['clases'] + r['interfaces']
    geometria_limpia(doc, dg)
    assert ids_integros(mdj)
    cmp = C.comparar_diagrama_con_codigo(doc, 'Diagrama de clases', codigo, 'java')
    assert cmp['porcentaje_sincronizacion'] == 100.0


def test_otro_lenguaje_y_errores(tmp_path):
    py = fuentes(str(tmp_path / 'py'), {'modelo.py': '''
        from dataclasses import dataclass, field
        from typing import List

        class Figura:
            def area(self) -> float:
                raise NotImplementedError

        @dataclass
        class Circulo(Figura):
            radio: float = 1.0

        @dataclass
        class Lienzo:
            figuras: List[Figura] = field(default_factory=list)
        '''})
    r = ok(tool('staruml_programa_a_diagrama', archivo=str(tmp_path / 'py.mdj'), ruta_codigo=py, lenguaje='python'))
    assert (r['clases'], r['generalizaciones'], r['asociaciones']) == (3, 1, 1)
    vacio = tmp_path / 'vacio'
    vacio.mkdir()
    assert 'No se encontraron clases' in tool('staruml_programa_a_diagrama', archivo=str(tmp_path / 'v.mdj'), ruta_codigo=str(vacio))['error']
    assert 'no existe' in tool('staruml_programa_a_diagrama', archivo=str(tmp_path / 'v.mdj'), ruta_codigo=str(tmp_path / 'nada'))['error']
    assert '.mdj' in tool('staruml_programa_a_diagrama', archivo=str(tmp_path / 'v.txt'), ruta_codigo=py, lenguaje='python')['error']
    assert not (tmp_path / 'v.mdj').exists()  # un error no deja un archivo a medias


def test_ruta_relativa_al_mdj(programa, tmp_path):
    mdj = tmp_path / 'tienda.mdj'
    r = ok(tool('staruml_programa_a_diagrama', archivo=str(mdj), ruta_codigo='tienda'))
    assert r['clases'] == 8 and json.loads(mdj.read_text(encoding='utf-8'))['_type'] == 'Project'


def test_clases_que_parecen_pruebas_y_constantes_de_interfaz(tmp_path):
    codigo = fuentes(str(tmp_path / 'escuela'), {
        'Test.java': 'public class Test { private Alumno alumno; }\n',  # un examen, no una prueba
        'ProductoSpec.java': 'public class ProductoSpec { }\n',
        'Alumno.java': 'public class Alumno { }\n',
        'Config.java': 'public interface Config { Alumno PREDETERMINADO = null; int MAX = 5; }\n',
        'AlumnoTest.java': 'public class AlumnoTest { }\n',
    })
    r = ok(tool('staruml_programa_a_diagrama', archivo=str(tmp_path / 'e.mdj'), ruta_codigo=codigo))
    doc = M.Doc(str(tmp_path / 'e.mdj'))
    assert sorted(o['name'] for o in doc.ids.values() if o and o['_type'] in ('UMLClass', 'UMLInterface')) == \
        ['Alumno', 'Config', 'ProductoSpec', 'Test']
    assert r['asociaciones'] == 1  # Test -> Alumno; la constante de la interfaz no es asociacion
    config = por_nombre(doc, 'Config')
    assert [(a['name'], a.get('isStatic')) for a in config['attributes']] == [('PREDETERMINADO', True), ('MAX', True)]


def test_clases_de_diseno_con_metodos_no_son_problema_oose(programa, modelo, tmp_path):
    mdj = str(tmp_path / 'diseno.mdj')
    ok(tool('staruml_programa_a_diagrama', archivo=mdj, ruta_codigo=programa))
    assert ok(tool('mdj_validar', archivo=mdj))['oose']['problemas'] == []
    # en las clases de analisis la regla sigue
    doc = M.Doc(modelo)
    cuenta = doc.find('Cuenta')
    cuenta['operations'] = [{'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': {'$ref': cuenta['_id']}, 'name': 'validar'}]
    doc.reindex()
    doc.save(backup=False)
    assert any('Cuenta (entity) tiene metodos' in p for p in ok(tool('mdj_validar', archivo=modelo))['oose']['problemas'])
