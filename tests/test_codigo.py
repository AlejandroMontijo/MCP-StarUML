# Parsers de codigo (Java, C#, TypeScript/JavaScript, Python, Kotlin, Go), normalizacion y escaneo de carpetas.
import pytest

import staruml_compare as C
from apoyo import fuentes


@pytest.mark.parametrize('tipo,esperado', [
    ('List<Cliente>', 'List<Cliente>'), ('Item[]', 'List<Item>'), ('string[]', 'List<String>'), ('Array<Pedido>', 'List<Pedido>'),
    ('Set<Cliente>', 'Set<Cliente>'), ('HashSet<Item>', 'Set<Item>'), ('Map<String, List<Item>>', 'Map<String,List<Item>>'),
    ('Dict[str, int]', 'Map<String,int>'), ('Optional[List[Item]]', 'List<Item>'), ('int?', 'int'), ('Cliente | null', 'Cliente'),
    ('java.util.List<Pedido>', 'List<Pedido>'), ('String...', 'List<String>'), ('LocalDate', 'Date'), ('Integer', 'int'),
    ('number', 'double'), ('MutableList<Pedido>', 'List<Pedido>'), ('Long', 'int'), ('Unit', 'void'), ('float64', 'double'),
    ('', 'Object'), (None, 'Object'), ({'$ref': 'x'}, 'Object'), ('Promise<Cliente>', 'Promise<Cliente>'),
])
def test_normalizar_tipo(tipo, esperado):
    assert C._normalizar_tipo(tipo) == esperado


def test_normalizar_nombre():
    assert C._normalizar_nombre('Sesión') == C._normalizar_nombre('Sesion') == 'sesion'
    assert C._normalizar_nombre('BC_Registro Solicitud') == 'registrosolicitud'
    assert C._normalizar_nombre('fecha de entrega') == C._normalizar_nombre('fechaDeEntrega')


def test_java(tmp_path):
    src = fuentes(str(tmp_path), {'modelo/Pedido.java': '''
        package app.modelo;
        import java.util.*;

        /** Pedido { con llaves en el comentario } */
        @Entity
        public class Pedido extends Documento<Long> implements Comparable<Pedido>, java.io.Serializable {
            private String url = "http://example.com/api";   // '//' dentro del texto
            private int puerto;
            private final List<Item> items = new ArrayList<>();
            private Map<String, Integer> conteo, otro;
            private static final char LLAVE = '{';

            public Pedido(int puerto) { this.puerto = puerto; }

            public double calcularTotal() {
                double suma = 0;
                items.add(new Item(1));
                return redondear(suma);
            }
            private double redondear(double v) { return v; }
            public abstract void agregar(@NotNull Item i, String... extras);
            class Interna { private int oculto; }
        }
        public record Punto(int x, int y) { }
        interface PedidoRepo extends JpaRepository<Pedido, Long> { Pedido buscar(Long id); }
        enum Estado { ACTIVO, INACTIVO; public boolean activo() { return true; } }
        '''})
    r = C.escanear_codigo(src)
    assert sorted(r) == ['Estado', 'Interna', 'Pedido', 'PedidoRepo', 'Punto']
    p = r['Pedido']
    assert [a['nombre'] for a in p['atributos']] == ['url', 'puerto', 'items', 'conteo', 'otro', 'LLAVE']
    assert [a['tipo'] for a in p['atributos']][:4] == ['String', 'int', 'List<Item>', 'Map<String,int>']
    assert [m['nombre'] for m in p['metodos']] == ['calcularTotal', 'redondear', 'agregar']
    assert p['metodos'][2]['parametros'] == [{'nombre': 'i', 'tipo': 'Item'}, {'nombre': 'extras', 'tipo': 'List<String>'}]
    assert p['superclases'] == ['Documento'] and p['interfaces'] == ['Comparable', 'Serializable'] and p['anotaciones'] == ['Entity']
    assert p['paquete'] == 'app.modelo'
    assert [a['nombre'] for a in r['Punto']['atributos']] == ['x', 'y']
    assert [m['nombre'] for m in r['PedidoRepo']['metodos']] == ['buscar'] and r['PedidoRepo']['interfaces'] == ['JpaRepository']
    assert r['Estado']['literales'] == ['ACTIVO', 'INACTIVO'] and [m['nombre'] for m in r['Estado']['metodos']] == ['activo']
    assert {'objeto': 'items', 'metodo': 'add'} in p['llamadas']


def test_csharp(tmp_path):
    src = fuentes(str(tmp_path), {'Modelo.cs': '''
        namespace App.Dominio {
            [Serializable]
            public partial class Cliente : Entidad, IAuditable {
                public string Nombre { get; set; }
                public string? Email { get; private set; } = "";
                public List<Pedido> Pedidos { get; } = new();
                private readonly int _edad;
                public int Total => Pedidos.Count;
                public Cliente(string nombre) { Nombre = nombre; }
                public async Task<bool> GuardarAsync(string ruta = @"C:\\datos\\""x""") { return true; }
            }
            public class Entidad { public int Id { get; set; } }
            public record Persona(string Nombre, int Edad);
            public interface IAuditable { void Auditar(); }
        }'''})
    r = C.escanear_codigo(src)
    c = r['Cliente']
    assert c['superclases'] == ['Entidad'] and c['interfaces'] == ['IAuditable']
    assert [a['nombre'] for a in c['atributos']] == ['Nombre', 'Email', 'Pedidos', '_edad', 'Total']
    assert [a['tipo'] for a in c['atributos']][:3] == ['String', 'String', 'List<Pedido>']
    assert [m['nombre'] for m in c['metodos']] == ['GuardarAsync']
    assert [a['nombre'] for a in r['Entidad']['atributos']] == ['Id']
    assert [a['nombre'] for a in r['Persona']['atributos']] == ['Nombre', 'Edad']
    assert [m['nombre'] for m in r['IAuditable']['metodos']] == ['Auditar']



def test_kotlin(tmp_path):
    src = fuentes(str(tmp_path), {'Modelo.kt': '''
        package app.dominio

        import java.time.LocalDate

        /** Cliente con "comillas" y { llaves } en el comentario */
        @Entity
        data class Cliente(
            val nombre: String,
            var email: String? = null,
            edad: Int,
            private val alta: LocalDate = LocalDate.now(),
        ) : Persona(nombre), Auditable, Comparable<Cliente> {
            val pedidos: MutableList<Pedido> = mutableListOf()
            var direccion: Direccion? = null
            private var contador = 0
            val total: Double
                get() = pedidos.sumOf { it.total }
            lateinit var repo: Repo
            val etiquetas = listOf("a", "b")

            fun agregar(p: Pedido, vararg extras: String): Boolean {
                val s = "texto con fun falso(x: Int) { }"
                repo.guardar(p)
                return pedidos.add(p)
            }

            override fun auditar() = println("x")

            private suspend fun <T> cargar(id: Long): T? { return null }

            companion object {
                const val MAX = 10
                fun crear(): Cliente = Cliente("x", null, 1)
            }

            init { contador++ }

            constructor(n: String) : this(n, null, 0)
        }

        interface Auditable : Base {
            fun auditar()
            val ultimo: LocalDate?
        }

        enum class Estado(val codigo: Int) {
            ACTIVO(1), INACTIVO(2),
            SUSPENDIDO(3);

            fun activo() = this == ACTIVO
        }

        enum class Color { ROJO, VERDE }

        class Punto(val x: Int, val y: Int)

        object Registro {
            val items = mutableMapOf<String, Cliente>()
        }

        sealed class Resultado {
            data class Ok(val valor: String) : Resultado()
        }

        class Repo {
            fun guardar(p: Pedido) {}
        }
        val k = Cliente::class'''})
    r = C.escanear_codigo(src, 'kotlin')
    assert sorted(r) == ['Auditable', 'Cliente', 'Color', 'Estado', 'Ok', 'Punto', 'Registro', 'Repo', 'Resultado']
    c = r['Cliente']
    assert c['paquete'] == 'app.dominio' and c['anotaciones'] == ['Entity']
    assert c['superclases'] == ['Persona'] and c['interfaces'] == ['Auditable', 'Comparable']
    # propiedades del constructor primario (solo las val/var), del cuerpo y con tipo inferido del valor
    assert [(a['nombre'], a['tipo']) for a in c['atributos']] == [
        ('nombre', 'String'), ('email', 'String'), ('alta', 'Date'), ('pedidos', 'List<Pedido>'), ('direccion', 'Direccion'),
        ('contador', 'int'), ('total', 'double'), ('repo', 'Repo'), ('etiquetas', 'List<Object>')]
    assert [a['visibilidad'] for a in c['atributos']][2] == 'private'
    # sin los de companion object ni constructores secundarios
    assert [(m['nombre'], m['retorno']) for m in c['metodos']] == [('agregar', 'boolean'), ('auditar', 'Object'), ('cargar', 'T')]
    assert c['metodos'][0]['parametros'] == [{'nombre': 'p', 'tipo': 'Pedido'}, {'nombre': 'extras', 'tipo': 'List<String>'}]
    assert c['metodos'][2]['visibilidad'] == 'private'
    assert {'objeto': 'repo', 'metodo': 'guardar'} in c['llamadas']
    assert not any(ll['metodo'] in ('agregar', 'cargar', 'falso') for ll in c['llamadas'])  # declaraciones y textos no cuentan
    assert r['Auditable']['interfaces'] == ['Base'] and [m['nombre'] for m in r['Auditable']['metodos']] == ['auditar']
    assert r['Estado']['literales'] == ['ACTIVO', 'INACTIVO', 'SUSPENDIDO'] and r['Color']['literales'] == ['ROJO', 'VERDE']
    assert [m['nombre'] for m in r['Estado']['metodos']] == ['activo']
    assert [a['nombre'] for a in r['Punto']['atributos']] == ['x', 'y']
    assert r['Registro']['atributos'][0]['tipo'] == 'Map<String,Cliente>'
    assert r['Ok']['superclases'] == ['Resultado']


def test_go(tmp_path):
    src = fuentes(str(tmp_path), {'modelo.go': '''
        package dominio

        import "time"

        // Cliente es un "cliente" { con llaves }
        type Cliente struct {
        	Entidad
        	Nombre, Apellido string `json:"nombre"`
        	Email     *string
        	Pedidos   []*Pedido
        	Direccion *Direccion
        	precios   map[string]float64
        	Alta      time.Time
        }

        type (
        	Pedido struct {
        		Total float64
        		Items []Item
        	}
        	Repo interface {
        		Buscar(id string) (*Cliente, error)
        		Guardar(c *Cliente) error
        		fmt.Stringer
        	}
        )

        type Estado int

        const (
        	Activo Estado = iota
        	Inactivo
        	_
        	Suspendido
        )

        const Limite = 10

        type Lista[T any] struct {
        	elems []T
        }

        func (c *Cliente) CalcularTotal(desc, iva float64, notas ...string) float64 {
        	c.validar()
        	c.repo.Guardar(c)
        	return 0
        }

        func (c Cliente) validar() {}

        func NuevoCliente(n string) *Cliente { return &Cliente{} }

        func (p *Pedido) Agregar(i Item) (int, error) {
        	type local struct{ x int }
        	return len(p.Items), nil
        }''', 'modelo_test.go': 'package dominio\n\ntype Falso struct { X int }\n'})
    r = C.escanear_codigo(src, 'go')
    assert sorted(r) == ['Cliente', 'Estado', 'Lista', 'Pedido', 'Repo']  # sin los _test.go ni tipos locales
    c = r['Cliente']
    assert c['paquete'] == 'dominio' and c['superclases'] == ['Entidad']  # campo embebido
    assert [(a['nombre'], a['tipo']) for a in c['atributos']] == [
        ('Nombre', 'String'), ('Apellido', 'String'), ('Email', 'String'), ('Pedidos', 'List<Pedido>'),
        ('Direccion', 'Direccion'), ('precios', 'Map<String,double>'), ('Alta', 'Date')]
    assert c['atributos'][5]['visibilidad'] == 'package'
    assert [(m['nombre'], m['retorno']) for m in c['metodos']] == [('CalcularTotal', 'double'), ('validar', 'void')]
    assert c['metodos'][0]['parametros'] == [{'nombre': 'desc', 'tipo': 'double'}, {'nombre': 'iva', 'tipo': 'double'},
                                             {'nombre': 'notas', 'tipo': 'List<String>'}]
    assert {'objeto': 'this', 'metodo': 'validar'} in c['llamadas'] and {'objeto': 'repo', 'metodo': 'Guardar'} in c['llamadas']
    assert [(m['nombre'], m['retorno']) for m in r['Pedido']['metodos']] == [('Agregar', 'int')]
    repo = r['Repo']
    assert repo['tipo_decl'] == 'interface' and repo['interfaces'] == ['Stringer']
    assert [(m['nombre'], m['retorno']) for m in repo['metodos']] == [('Buscar', 'Cliente'), ('Guardar', 'error')]
    assert r['Estado']['tipo_decl'] == 'enum' and r['Estado']['literales'] == ['Activo', 'Inactivo', 'Suspendido']
    assert r['Lista']['atributos'][0]['tipo'] == 'List<T>'

def test_typescript(tmp_path):
    src = fuentes(str(tmp_path), {'cliente.ts': '''
        import { Repo } from './repo';
        export interface Repositorio<T> extends Base, Otra {
          buscar(id: string): Promise<T>;
          total?: number
        }
        export abstract class Cliente extends Persona<string> implements Repositorio<Cliente> {
          nombre?: string;
          readonly id: string = '1';
          private static contador: number = 0;
          etiquetas: string[] = []
          #secreto = 'x'
          constructor(private repo: Repo, public readonly alias: string) { super(); }
          async guardar(): Promise<void> {
            if (this.nombre) { this.repo.guardar(this); }
            const datos = { clave: 'valor' };
          }
          get edad(): number { return 1; }
          calcular = (x: number): number => x * 2;
          toJSON() { return { nombre: this.nombre }; }
        }
        export enum Estado { Activo = 'A', Inactivo = 'I' }
        '''}, )
    r = C.escanear_codigo(src)
    c = r['Cliente']
    assert [a['nombre'] for a in c['atributos']] == ['nombre', 'id', 'contador', 'etiquetas', 'secreto', 'repo', 'alias', 'edad']
    assert [a['tipo'] for a in c['atributos']][:4] == ['String', 'String', 'double', 'List<String>']
    assert [m['nombre'] for m in c['metodos']] == ['guardar', 'calcular', 'toJSON']
    assert c['superclases'] == ['Persona'] and c['interfaces'] == ['Repositorio']
    assert [m['nombre'] for m in r['Repositorio']['metodos']] == ['buscar'] and r['Repositorio']['interfaces'] == ['Base', 'Otra']
    assert [a['nombre'] for a in r['Repositorio']['atributos']] == ['total']
    assert r['Estado']['literales'] == ['Activo', 'Inactivo']
    assert {'objeto': 'repo', 'metodo': 'guardar'} in c['llamadas']


def test_python(tmp_path):
    src = fuentes(str(tmp_path), {'cliente.py': '''
        from dataclasses import dataclass, field
        from enum import Enum
        from typing import List, Optional
        import modelos

        @dataclass
        class Cliente(modelos.Persona):
            """Cliente # con numeral"""
            nombre: str
            color: str = "#fff"
            pedidos: List["Pedido"] = field(default_factory=list)

            def __init__(self, nombre: str, edad: int):
                self.nombre = nombre
                self.edad = edad
                self.repo = modelos.Repo()

            def saludar(self) -> str:
                try:
                    pass
                except Exception:
                    return None
                else:
                    return None

            def direccion(self) -> modelos.Direccion:
                return self.repo.buscar(self.nombre)

            @property
            def total(self) -> float:
                return 0.0

            async def guardar(self, destino: "Ruta", *args, **kw) -> None:
                pass


        def funcion_de_modulo(x):
            return x

        CONSTANTE: int = 5

        class Estado(Enum):
            ACTIVO = 'A'
            INACTIVO = 'I'
        '''})
    r = C.escanear_codigo(src)
    c = r['Cliente']
    assert [a['nombre'] for a in c['atributos']] == ['nombre', 'color', 'pedidos', 'edad', 'repo', 'total']  # orden del codigo
    assert [a['tipo'] for a in c['atributos']] == ['String', 'String', 'List<Pedido>', 'int', 'Repo', 'double']
    assert [m['nombre'] for m in c['metodos']] == ['saludar', 'direccion', 'guardar']
    assert c['metodos'][2]['parametros'][0] == {'nombre': 'destino', 'tipo': 'Ruta'}
    assert c['superclases'] == ['Persona']
    assert {'objeto': 'repo', 'metodo': 'buscar'} in c['llamadas']
    assert r['Estado']['literales'] == ['ACTIVO', 'INACTIVO']
    assert 'funcion_de_modulo' not in str(c['metodos'])


def test_python_con_error_de_sintaxis_no_revienta(tmp_path):
    src = fuentes(str(tmp_path), {'roto.py': 'class A(:\n  pass\n', 'bien.py': 'class B:\n    x: int = 1\n'})
    assert sorted(C.escanear_codigo(src)) == ['B']


def test_escaneo_filtra_por_lenguaje_y_carpetas(tmp_path):
    src = fuentes(str(tmp_path), {
        'A.java': 'public class A { }', 'b.py': 'class B:\n    pass\n', 'c.ts': 'export class C { }', 'd.js': 'class D { }\n',
        'e.cs': 'class E { }', 'lib.min.js': 'class Min{}', 'tipos.d.ts': 'declare class Decl {}',
        '.venv/lib/python3.11/site-packages/lib.py': 'class LibreriaExterna:\n    pass\n', 'node_modules/x/y.js': 'class NM {}',
        'obj/Debug/Generado.cs': 'public class Generado { }', 'dist/salida.js': 'class Dist {}'})
    assert sorted(C.escanear_codigo(src)) == ['A', 'B', 'C', 'D', 'E']
    assert sorted(C.escanear_codigo(src, 'java')) == ['A']
    assert sorted(C.escanear_codigo(src, 'typescript')) == ['C', 'D']
    assert sorted(C.escanear_codigo(src, 'csharp')) == ['E']
    with pytest.raises(FileNotFoundError):
        C.escanear_codigo(str(tmp_path / 'no_existe'))
