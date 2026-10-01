# Utilidades compartidas por las pruebas: modelos .mdj sinteticos con la estructura que guarda StarUML,
# un cliente MCP por stdio y la llamada directa a las herramientas del servidor.
import base64
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import server as S  # noqa: E402
import staruml_mdj as M  # noqa: E402

_ts = [int(time.time() * 1000) - 900000]


def nid():
    _ts[0] += 3
    return base64.b64encode(b'\x00' * 4 + _ts[0].to_bytes(6, 'big') + os.urandom(4)).decode()


ref = M.ref


def compilar_csharp(fuentes_dir, trabajo_dir):
    """Compila los .cs de fuentes_dir con dotnet en un proyecto aparte (la carpeta de fuentes no se ensucia con bin/obj).
    None si no hay SDK de .NET; si no, (ok, salida)."""
    dotnet = shutil.which('dotnet')
    if not dotnet:
        return None
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT='1', DOTNET_NOLOGO='1', DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1')
    v = subprocess.run([dotnet, '--version'], capture_output=True, text=True, env=env)
    m = re.match(r'(\d+)\.', v.stdout.strip())
    if v.returncode or not m:
        return None
    os.makedirs(trabajo_dir, exist_ok=True)
    fuentes = os.path.join(os.path.abspath(fuentes_dir), '*.cs').replace('\\', '/')
    with open(os.path.join(trabajo_dir, 'Generado.csproj'), 'w', encoding='utf-8') as f:
        f.write(f'''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net{m.group(1)}.0</TargetFramework>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <ImplicitUsings>disable</ImplicitUsings>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
    <NoWarn>CS1591</NoWarn>
  </PropertyGroup>
  <ItemGroup><Compile Include="{fuentes}" /></ItemGroup>
</Project>
''')
    r = subprocess.run([dotnet, 'build', '-nologo', '-v', 'q'], capture_output=True, text=True, cwd=trabajo_dir, env=env)
    return r.returncode == 0, (r.stdout + r.stderr)[-2000:]


def proyecto_vacio(nombre='Fixture'):
    """Project > UMLProfile (boundary/control/entity) + UMLModel > diagrama de clases 'cu_1' (vacio, sin ownedViews,
    como lo guarda StarUML), paquete 'Analisis' con el actor 'Usuario' y colaboracion > interaccion > 'cu_1_FB'."""
    root, prof, model, pk, dcl, colab, inter, dsec, fv, fl1, fl2, actor = [nid() for _ in range(12)]
    st = {n: nid() for n in ('boundary', 'control', 'entity')}
    return {
        '_type': 'Project', '_id': root, 'name': nombre,
        'ownedElements': [
            {'_type': 'UMLProfile', '_id': prof, '_parent': ref(root), 'name': 'UMLStandardProfile',
             'ownedElements': [{'_type': 'UMLStereotype', '_id': st[n], '_parent': ref(prof), 'name': n} for n in st]},
            {'_type': 'UMLModel', '_id': model, '_parent': ref(root), 'name': 'Model',
             'ownedElements': [
                 {'_type': 'UMLClassDiagram', '_id': dcl, '_parent': ref(model), 'name': 'cu_1', 'defaultDiagram': True},
                 {'_type': 'UMLPackage', '_id': pk, '_parent': ref(model), 'name': 'Analisis',
                  'ownedElements': [{'_type': 'UMLActor', '_id': actor, '_parent': ref(pk), 'name': 'Usuario'}]},
                 {'_type': 'UMLCollaboration', '_id': colab, '_parent': ref(model), 'name': 'Collaboration1',
                  'ownedElements': [
                      {'_type': 'UMLInteraction', '_id': inter, '_parent': ref(colab), 'name': 'flujo basico',
                       'ownedElements': [
                           {'_type': 'UMLSequenceDiagram', '_id': dsec, '_parent': ref(inter), 'name': 'cu_1_FB',
                            'ownedViews': [
                                {'_type': 'UMLFrameView', '_id': fv, '_parent': ref(dsec), 'model': ref(dsec),
                                 'subViews': [
                                     {'_type': 'LabelView', '_id': fl1, '_parent': ref(fv), 'font': 'Arial;13;0',
                                      'left': 32.72998046875, 'top': 15, 'width': 60, 'height': 13, 'text': 'cu_1_FB'},
                                     {'_type': 'LabelView', '_id': fl2, '_parent': ref(fv), 'font': 'Arial;13;1',
                                      'left': 13, 'top': 15, 'width': 14.72, 'height': 13, 'text': 'sd'}],
                                 'font': 'Arial;13;0', 'left': 8, 'top': 10, 'width': 695, 'height': 595,
                                 'nameLabel': ref(fl1), 'frameTypeLabel': ref(fl2)}]}]}]}]}]}


def guardar_json(d, path):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent='\t')
    return path


def tool(_herramienta, /, **a):
    """Llama la herramienta como lo hace el servidor (esquema + rutas); los errores vuelven como {'error': ...}."""
    r = S.llamar_herramienta({'name': _herramienta, 'arguments': a})
    assert r is not None, f'herramienta desconocida {_herramienta}'
    contenido = r['content'][0]
    texto = contenido.get('text', '') if contenido['type'] == 'text' else ''
    if r['isError']:
        return {'error': texto}
    try:
        return json.loads(texto)
    except ValueError:
        return {'texto': texto, 'content': r['content']}


def ok(r):
    assert 'error' not in r, r.get('error')
    return r


def poblar(path):
    """Caso de uso de ejemplo completo: 4 clases de robustez, vistas, asociaciones, una nota y la secuencia."""
    for nombre, est, attrs in (('Pantalla Autenticación', 'boundary', None), ('Control Autenticación', 'control', None),
                               ('Cuenta', 'entity', ['usuario', 'contraseña']), ('Sesión', 'entity', ['inicio', 'fin'])):
        a = dict(archivo=path, paquete='Analisis', nombre=nombre, estereotipo=est)
        if attrs:
            a['atributos'] = attrs
        ok(tool('mdj_clase_crear', **a))
    for el, x, y in (('Usuario', 40, 120), ('Pantalla Autenticación', 200, 110), ('Control Autenticación', 430, 125),
                     ('Cuenta', 680, 105), ('Sesión', 690, 330)):
        ok(tool('mdj_vista_agregar', archivo=path, diagrama='cu_1', elemento=el, x=x, y=y))
    for a_, b_, m1, m2 in (('Usuario', 'Pantalla Autenticación', '', ''), ('Pantalla Autenticación', 'Control Autenticación', '', ''),
                           ('Control Autenticación', 'Cuenta', '', ''), ('Control Autenticación', 'Sesión', '', ''),
                           ('Cuenta', 'Sesión', '1', '0..*')):
        ok(tool('mdj_asociacion_crear', archivo=path, desde=a_, hacia=b_, mult_desde=m1, mult_hacia=m2, diagrama='cu_1'))
    ok(tool('mdj_nota', archivo=path, diagrama='cu_1', texto='Responsabilidad: autenticar al usuario.', x=40, y=420, ancho=200))
    ok(tool('mdj_secuencia_generar', archivo=path, diagrama='cu_1_FB', lifelines=LIFELINES, mensajes=MENSAJES))
    return path


LIFELINES = [{'clave': 'usr', 'tipo': 'Usuario'}, {'clave': 'ui', 'tipo': 'Pantalla Autenticación'},
             {'clave': 'ctrl', 'tipo': 'Control Autenticación'}, {'clave': 'cta', 'tipo': 'Cuenta'}, {'clave': 'ses', 'tipo': 'Sesión'}]
MENSAJES = [
    {'de': 'usr', 'a': 'ui', 'nombre': 'ingresarCredenciales(usuario, contraseña)', 'flujo': 'F1'},
    {'de': 'ui', 'a': 'ctrl', 'nombre': 'autenticar(usuario, contraseña)', 'flujo': 'F1'},
    {'de': 'ctrl', 'a': 'cta', 'nombre': 'buscarCuenta(usuario)', 'flujo': 'F1'},
    {'de': 'cta', 'a': 'ctrl', 'nombre': 'cuenta', 'reply': True, 'flujo': 'F1'},
    {'de': 'ctrl', 'a': 'ses', 'nombre': 'crearSesion(cuenta)', 'flujo': 'F2'},
    {'de': 'ses', 'a': 'ctrl', 'nombre': 'sesion', 'reply': True, 'flujo': 'F2'},
    {'de': 'ctrl', 'a': 'ui', 'nombre': 'mostrarBienvenida()', 'flujo': 'F2'},
    {'de': 'ui', 'a': 'usr', 'nombre': 'verBienvenida()', 'flujo': 'F2'},
]


def modelo_dominio(path, tipo_ref=False, nav_item='notNavigable'):
    """Diagrama 'cu_1' con Cliente, Direccion, Pedido, Item, ClienteVIP (generaliza a Cliente) y el actor Usuario."""
    guardar_json(proyecto_vacio(), path)
    doc = M.Doc(path)
    pk = doc.find('Analisis')
    dg = doc.diagram('cu_1')

    def clase(n, attrs=(), ops=()):
        c = {'_type': 'UMLClass', '_id': doc.new_id(), '_parent': ref(pk['_id']), 'name': n,
             'stereotype': ref(doc.stereotype_id('entity'))}
        c['attributes'] = [{'_type': 'UMLAttribute', '_id': doc.new_id(), '_parent': ref(c['_id']), 'name': a, 'type': t}
                           for a, t in attrs]
        if ops:
            c['operations'] = []
            for on, ret in ops:
                o = {'_type': 'UMLOperation', '_id': doc.new_id(), '_parent': ref(c['_id']), 'name': on}
                o['parameters'] = [{'_type': 'UMLParameter', '_id': doc.new_id(), '_parent': ref(o['_id']), 'type': ret,
                                    'direction': 'return'}]
                c['operations'].append(o)
        pk['ownedElements'].append(c)
        return c
    direc = clase('Direccion', [('calle', 'String')])
    cli = clase('Cliente', [('nombre', 'String'), ('email', 'String'),
                            ('direccion', ref(direc['_id']) if tipo_ref else 'Direccion')])
    ped = clase('Pedido', [('total', 'double'), ('items', 'List<Item>')], ops=[('calcularTotal', 'double')])
    item = clase('Item', [('cantidad', 'int')])
    vip = clase('ClienteVIP', [('descuento', 'double')])
    pk['ownedElements'].append({'_type': 'UMLGeneralization', '_id': doc.new_id(), '_parent': ref(pk['_id']),
                                'source': ref(vip['_id']), 'target': ref(cli['_id'])})
    doc.reindex()
    x = 40
    for el in (doc.find('Usuario'), direc, cli, ped, item, vip):
        M.vista_nueva(doc, dg, el, x, 100)
        x += 190
    M.asociacion_crear(doc, cli, ped, '1', '0..*')
    a2 = M.asociacion_crear(doc, ped, item, '1', '1..*', navegable='ninguno')
    if nav_item:
        a2['end2']['navigable'] = nav_item
    doc.save(backup=False)
    return path



def modelo_comportamiento(path):
    """Maquina de estados 'Ciclo de pedido' (con un estado compuesto y un punto de decision) y actividad
    'Procesar pedido' (decision, bifurcacion, union y fusion), cada una con su diagrama. Sin problemas ni avisos."""
    guardar_json(proyecto_vacio(), path)
    doc = M.Doc(path)
    raiz = next(o for o in doc.ids.values() if o and o['_type'] == 'UMLModel')

    def el(tipo, padre, **kw):
        return {'_type': tipo, '_id': doc.new_id(), '_parent': ref(padre['_id']), **kw}

    sm = el('UMLStateMachine', raiz, name='Ciclo de pedido')
    reg = el('UMLRegion', sm)
    sm['regions'] = [reg]
    v = {}
    for clave, tipo, kw in (('ini', 'UMLPseudostate', {'kind': 'initial'}), ('creado', 'UMLState', {'name': 'Creado'}),
                            ('dec', 'UMLPseudostate', {'kind': 'choice'}), ('pagado', 'UMLState', {'name': 'Pagado'}),
                            ('prep', 'UMLState', {'name': 'En preparación'}), ('enviado', 'UMLState', {'name': 'Enviado'}),
                            ('fin', 'UMLFinalState', {})):
        v[clave] = el(tipo, reg, **kw)
    reg['vertices'] = list(v.values())
    sub = el('UMLRegion', v['prep'])
    v['prep']['regions'] = [sub]
    for clave, tipo, kw in (('ini2', 'UMLPseudostate', {'kind': 'initial'}), ('empacando', 'UMLState', {'name': 'Empacando'}),
                            ('etiquetando', 'UMLState', {'name': 'Etiquetando'})):
        v[clave] = el(tipo, sub, **kw)
    sub['vertices'] = [v['ini2'], v['empacando'], v['etiquetando']]
    v['pagado']['doActivities'] = [el('UMLOpaqueBehavior', v['pagado'], name='notificar al almacén')]

    def trans(region, a, b, disparador=None, guarda=None):
        t = el('UMLTransition', region, source=ref(v[a]['_id']), target=ref(v[b]['_id']))
        if disparador:
            t['triggers'] = [el('UMLEvent', t, name=disparador)]
        if guarda:
            t['guard'] = guarda
        region.setdefault('transitions', []).append(t)
        return t
    trans(reg, 'ini', 'creado')
    trans(reg, 'creado', 'dec', 'pagar')
    trans(reg, 'dec', 'pagado', guarda='pago válido')
    trans(reg, 'dec', 'creado', guarda='else')
    trans(reg, 'pagado', 'prep')
    trans(reg, 'prep', 'enviado', 'listo')
    trans(reg, 'enviado', 'fin', 'entregado')
    trans(sub, 'ini2', 'empacando')
    trans(sub, 'empacando', 'etiquetando', 'empacado')
    dge = el('UMLStatechartDiagram', sm, name='estados_pedido')
    dge['ownedViews'] = [
        el('UMLStateView', dge, model=ref(v['prep']['_id']), left=300, top=40, width=260, height=160),
        el('UMLStateView', dge, model=ref(v['empacando']['_id']), left=320, top=90, width=100, height=40),
        el('UMLStateView', dge, model=ref(v['creado']['_id']), left=40, top=40, width=100, height=40)]
    sm['ownedElements'] = [dge]

    act = el('UMLActivity', raiz, name='Procesar pedido')
    n = {}
    for clave, tipo, nombre in (('ini', 'UMLInitialNode', None), ('recibir', 'UMLAction', 'Recibir pedido'),
                                ('dec', 'UMLDecisionNode', None), ('rechazar', 'UMLAction', 'Rechazar pedido'),
                                ('cobrar', 'UMLAction', 'Cobrar'), ('fork', 'UMLForkNode', None),
                                ('empacar', 'UMLAction', 'Empacar'), ('facturar', 'UMLAction', 'Facturar'),
                                ('join', 'UMLJoinNode', None), ('merge', 'UMLMergeNode', None), ('fin', 'UMLActivityFinalNode', None)):
        n[clave] = el(tipo, act, **({'name': nombre} if nombre else {}))
    act['nodes'] = list(n.values())
    act['edges'] = []

    def flujo(a, b, guarda=None):
        f = el('UMLControlFlow', act, source=ref(n[a]['_id']), target=ref(n[b]['_id']))
        if guarda:
            f['guard'] = guarda
        act['edges'].append(f)
        return f
    for a, b, g in (('ini', 'recibir', None), ('recibir', 'dec', None), ('dec', 'rechazar', 'sin existencias'),
                    ('dec', 'cobrar', 'con existencias'), ('cobrar', 'fork', None), ('fork', 'empacar', None),
                    ('fork', 'facturar', None), ('empacar', 'join', None), ('facturar', 'join', None),
                    ('join', 'merge', None), ('rechazar', 'merge', None), ('merge', 'fin', None)):
        flujo(a, b, g)
    part = el('UMLActivityPartition', act, name='Almacén', nodes=[ref(n['empacar']['_id'])])
    act['groups'] = [part]
    dga = el('UMLActivityDiagram', act, name='actividad_pedido')
    dga['ownedViews'] = [el('UMLActionView', dga, model=ref(n['recibir']['_id']), left=40, top=80, width=120, height=40),
                         el('UMLActionView', dga, model=ref(n['cobrar']['_id']), left=40, top=160, width=120, height=40)]
    act['ownedElements'] = [dga]
    raiz['ownedElements'] += [sm, act]
    doc.reindex()
    doc.save(backup=False)
    return path

def fuentes(carpeta, archivos):
    """Escribe archivos de codigo (texto con sangria comun eliminada) y devuelve la carpeta."""
    for nombre, src in archivos.items():
        p = os.path.join(carpeta, nombre)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(src))
    return carpeta


def ids_integros(path):
    v = M.validar(M.Doc(path), oose=False)
    return v['n_duplicados'] == 0 and v['n_colgantes'] == 0 and v['n_parent_mismatch'] == 0


def _vistas_de(dg):
    res = []

    def walk(v):
        res.append(v)
        for s in v.get('subViews', []):
            walk(s)
    for v in dg.get('ownedViews', []):
        walk(v)
    return res


def poblar_paleta(doc, dg):
    """Dibuja en el diagrama cada simbolo de su paleta con staruml_uml.dibujar: primero las cajas sueltas, luego las
    que van sobre otra vista y al final las lineas, conectando vistas del tipo que espera cada plantilla. Devuelve
    (dibujados, {simbolo: motivo de lo que no se pudo})."""
    import staruml_uml as U
    pl = U.plantillas()['plantillas'][dg['_type']]
    hechos, fallas = [], {}
    pend = [c for c, p in pl.items() if p['forma'] != 'line' and not any(U.necesita(p))] + \
           [c for c, p in pl.items() if p['forma'] != 'line' and any(U.necesita(p))] + \
           [c for c, p in pl.items() if p['forma'] == 'line']
    for _ in range(4):  # lo que va sobre algo que todavia no se dibujo se reintenta
        siguen = []
        for c in pend:
            p = pl[c]
            uc, uh = U.necesita(p)
            vs = [v for v in _vistas_de(dg) if v.get('_id') and isinstance(v.get('model'), dict)]
            if p['forma'] == 'line':
                a = next((v for v in vs if v['_type'] == p.get('cola')), None) if uc else None
                b = (next((v for v in vs if v['_type'] == p.get('cabeza') and v is not a), None) or
                     next((v for v in vs if v['_type'] == p.get('cabeza')), None)) if uh else None
                if (uc and not a) or (uh and not b):
                    fallas[c] = f'no hay {p.get("cola")} / {p.get("cabeza")}'
                    siguen.append(c)
                    continue
                U.dibujar(doc, dg['_id'], c, desde=a and a['_id'], hasta=b and b['_id'])
            elif uc or uh:
                t = p.get('cabeza') or p.get('cola')
                b = next((v for v in vs if v['_type'] == t), None)
                if not b:
                    fallas[c] = f'no hay {t}'
                    siguen.append(c)
                    continue
                U.dibujar(doc, dg['_id'], c, sobre=b['_id'])
            else:
                U.dibujar(doc, dg['_id'], c, nombre=c.split('|')[0].replace(' ', '') + 'X')
            hechos.append(c)
            fallas.pop(c, None)
        if len(siguen) == len(pend):
            break
        pend = siguen
    return hechos, fallas


def modelo_real():
    """El .mdj real del caso de uso (no se versiona): STARUML_MCP_MODELO_REAL o el primer pruebas/*.mdj."""
    p = os.environ.get('STARUML_MCP_MODELO_REAL')
    if p and os.path.exists(p):
        return p
    cands = sorted(glob.glob(os.path.join(RAIZ, 'pruebas', '*.mdj')))
    return cands[0] if cands else None


class ClienteMCP:
    """Cliente MCP minimo por stdio."""

    def __init__(self, env=None, cwd=None):
        entorno = dict(os.environ)
        entorno.update(env or {})
        self.p = subprocess.Popen([sys.executable, os.path.join(RAIZ, 'server.py')], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=entorno, cwd=cwd or RAIZ)
        self.n = 0

    def crudo(self, linea):
        self.p.stdin.write((linea if linea.endswith('\n') else linea + '\n').encode('utf-8'))
        self.p.stdin.flush()

    def leer(self):
        linea = self.p.stdout.readline()
        if not linea:
            raise RuntimeError('el servidor cerro stdout: ' + self.p.stderr.read().decode('utf-8', 'replace')[-2000:])
        return json.loads(linea.decode('utf-8'))

    def pedir(self, metodo, params=None):
        self.n += 1
        msg = {'jsonrpc': '2.0', 'id': self.n, 'method': metodo}
        if params is not None:
            msg['params'] = params
        self.crudo(json.dumps(msg, ensure_ascii=False))
        return self.leer()

    def llamar(self, _herramienta, /, **args):
        r = self.pedir("tools/call", {"name": _herramienta, "arguments": args})
        res = r['result']
        texto = res['content'][0].get('text', '')
        try:
            datos = json.loads(texto)
        except ValueError:
            datos = texto
        return res['isError'], datos

    def cerrar(self):
        try:
            self.p.stdin.close()
        except OSError:
            pass
        self.p.wait(15)
        return self.p.stderr.read().decode('utf-8', 'replace')

    def salida_restante(self):
        """Todo lo que queda en stdout (tras cerrar stdin)."""
        self.p.stdin.close()
        out = self.p.stdout.read().decode('utf-8').splitlines()
        self.p.wait(15)
        return out


# Programa Java de ejemplo para staruml_programa_a_diagrama: dos paquetes, clase abstracta, interfaz, enum, record,
# asociacion en ambos sentidos, colecciones, un Map, un campo static y una clase de pruebas (que se omite).
PROGRAMA_JAVA = {
    'src/main/java/com/tienda/modelo/Cliente.java': '''\
package com.tienda.modelo;

import java.util.ArrayList;
import java.util.List;

public class Cliente extends Persona implements Notificable {
    private List<Pedido> pedidos = new ArrayList<>();
    private Direccion direccion;
    private static int contador = 0;

    public Cliente(String nombre) { this.nombre = nombre; }

    @Override
    public String describir() { return "Cliente " + nombre; }

    public void agregarPedido(Pedido p) { pedidos.add(p); }

    public void notificar(String mensaje) { }
}
''',
    'src/main/java/com/tienda/modelo/Direccion.java': '''\
package com.tienda.modelo;

public record Direccion(String calle, String ciudad, String cp) { }
''',
    'src/main/java/com/tienda/modelo/Empleado.java': '''\
package com.tienda.modelo;

public class Empleado extends Persona {
    private double salario;
    public String describir() { return "Empleado " + nombre; }
}
''',
    'src/main/java/com/tienda/modelo/EstadoPedido.java': '''\
package com.tienda.modelo;

public enum EstadoPedido { NUEVO, PAGADO, ENVIADO, ENTREGADO }
''',
    'src/main/java/com/tienda/modelo/LineaPedido.java': '''\
package com.tienda.modelo;

public class LineaPedido {
    private Producto producto;
    private int cantidad;
    public LineaPedido(Producto producto, int cantidad) { this.producto = producto; this.cantidad = cantidad; }
    public double subtotal() { return producto.getPrecio() * cantidad; }
}
''',
    'src/main/java/com/tienda/modelo/Notificable.java': '''\
package com.tienda.modelo;

public interface Notificable {
    void notificar(String mensaje);
}
''',
    'src/main/java/com/tienda/modelo/Pedido.java': '''\
package com.tienda.modelo;

import java.time.LocalDate;
import java.util.List;
import java.util.ArrayList;

public class Pedido {
    private int folio;
    private LocalDate fecha;
    private EstadoPedido estado = EstadoPedido.NUEVO;
    private Cliente cliente;
    private final List<LineaPedido> lineas = new ArrayList<>();

    public double calcularTotal() {
        double total = 0;
        for (LineaPedido l : lineas) total += l.subtotal();
        return total;
    }
    public void agregarLinea(Producto producto, int cantidad) { lineas.add(new LineaPedido(producto, cantidad)); }
}
''',
    'src/main/java/com/tienda/modelo/Persona.java': '''\
package com.tienda.modelo;

public abstract class Persona {
    protected String nombre;
    private String email;

    public String getNombre() { return nombre; }
    public void setNombre(String nombre) { this.nombre = nombre; }
    public abstract String describir();
}
''',
    'src/main/java/com/tienda/modelo/Producto.java': '''\
package com.tienda.modelo;

public class Producto {
    private String clave;
    private double precio;
    public double getPrecio() { return precio; }
}
''',
    'src/main/java/com/tienda/servicio/RepositorioPedidos.java': '''\
package com.tienda.servicio;

import com.tienda.modelo.Pedido;
import java.util.List;

public interface RepositorioPedidos {
    void guardar(Pedido pedido);
    List<Pedido> todos();
}
''',
    'src/main/java/com/tienda/servicio/ServicioPedidos.java': '''\
package com.tienda.servicio;

import com.tienda.modelo.*;
import java.util.Map;
import java.util.HashMap;

public class ServicioPedidos {
    private final Map<Integer, Pedido> pedidos = new HashMap<>();
    private RepositorioPedidos repositorio;

    public Pedido crearPedido(Cliente cliente) { return new Pedido(); }
    public Pedido buscar(int folio) { return pedidos.get(folio); }
}
''',
    'src/test/java/com/tienda/PedidoTest.java': '''\
package com.tienda;
public class PedidoTest { private int x; }
''',
}
