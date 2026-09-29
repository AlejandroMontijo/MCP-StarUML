# Pruebas con un .mdj real (el caso de uso del equipo). El archivo no se versiona: se toma de pruebas/*.mdj o de
# STARUML_MCP_MODELO_REAL, y si no existe estas pruebas se omiten. Todo se hace sobre copias.
import glob
import os
import shutil
import subprocess
import sys

import pytest

from apoyo import M, compilar_csharp, ids_integros, ok, tool


def diagramas(path, tipo):
    return [d for d in M.Doc(path).diagrams() if d['_type'] == tipo]


def test_guardar_reproduce_el_archivo_byte_a_byte(real):
    antes = open(real, 'rb').read()
    M.Doc(real).save(backup=False)
    assert open(real, 'rb').read() == antes


def test_integro_y_sin_problemas_oose(real):
    v = ok(tool('mdj_validar', archivo=real))
    assert v['n_duplicados'] == v['n_colgantes'] == v['n_parent_mismatch'] == 0
    assert v['oose']['problemas'] == [], v['oose']['problemas']
    assert v['oose']['avisos'] == [], v['oose']['avisos']


def test_reglas_de_robustez_del_caso_de_uso(real):
    """Un solo control por paquete de caso de uso, estereotipos como referencia al perfil, y en las secuencias:
    nada de control->actor ni replies de boundary a actor; a los actores solo les hablan las boundaries."""
    doc = M.Doc(real)
    controles = {}
    for o in doc.ids.values():
        if o and o['_type'] == 'UMLClass':
            assert not isinstance(o.get('stereotype'), str), f'{o.get("name")}: estereotipo como texto'
            if doc.kind(o) == 'control':
                controles.setdefault(doc.parent.get(o['_id']), []).append(o['name'])
    assert controles and all(len(v) == 1 for v in controles.values()), controles
    for dg in diagramas(real, 'UMLSequenceDiagram'):
        for m in M.secuencia(doc, dg['_id'])['mensajes']:
            ks, kt = m['tipos'].split('->')
            assert (ks, kt) != ('control', 'actor'), (dg.get('name'), m)
            assert not (m['reply'] and (ks, kt) == ('boundary', 'actor')), (dg.get('name'), m)
            if kt == 'actor' and not m['reply']:
                assert ks in ('boundary', 'actor'), (dg.get('name'), m)


def test_todas_las_lecturas_funcionan(real):
    r = ok(tool('mdj_resumen', archivo=real))
    for d in r['diagramas']:  # por id: hay diagramas homonimos (metodo1, metodo2...)
        ok(tool('mdj_geometria', archivo=real, diagrama=d['id']))
        if d['tipo'] == 'UMLSequenceDiagram':
            ok(tool('mdj_secuencia', archivo=real, diagrama=d['id']))
    m = ok(tool('mdj_modelo', archivo=real))
    assert m['total']['clases'] == len(m['clases']) or m['siguiente_desde']
    assert ok(tool('mdj_buscar', archivo=real, tipo='UMLAssociation', limite=500))


def _especificacion(doc, dg):
    """lifelines y mensajes de un diagrama de secuencia existente, en el formato de mdj_secuencia_generar."""
    it = M.interaction_of(doc, dg)
    lifelines, clave = [], {}
    for i, l in enumerate(it.get('participants', [])):
        rol = doc.ids.get(l.get('represent', {}).get('$ref'))
        tipo = rol.get('type') if rol else None
        if not isinstance(tipo, dict):
            return None, None
        clave[l['_id']] = rol.get('name') or f'l{i}'
        lifelines.append({'clave': clave[l['_id']], 'tipo': tipo['$ref']})
    if len(set(clave.values())) != len(clave):
        return None, None
    mensajes = []
    for m in it.get('messages', []):
        s, t = m['source']['$ref'], m['target']['$ref']
        if s == t or s not in clave or t not in clave:
            return None, None  # auto-mensajes o gates: el generador no los dibuja
        mensajes.append({'de': clave[s], 'a': clave[t], 'nombre': m.get('name') or '?', 'reply': m.get('messageSort') == 'reply'})
    return lifelines, mensajes


def test_regenerar_cada_secuencia_con_su_propia_especificacion(real):
    doc = M.Doc(real)
    probadas = 0
    for dg in diagramas(real, 'UMLSequenceDiagram'):
        lifelines, mensajes = _especificacion(doc, dg)
        if not mensajes:
            continue
        notas_antes = sum(1 for v in dg.get('ownedViews', []) if v['_type'] == 'UMLNoteView')
        r = ok(tool('mdj_secuencia_generar', archivo=real, diagrama=dg['_id'], lifelines=lifelines, mensajes=mensajes))
        assert r['mensajes'] == len(mensajes) and r['lifelines_quitadas'] == 0
        assert r['oose']['problemas'] == [], r['oose']['problemas']
        doc = M.Doc(real)
        sec = M.secuencia(doc, dg['_id'])
        assert [m['nombre'] for m in sec['mensajes']] == [m['nombre'] for m in mensajes]
        assert sum(1 for v in doc.get(dg['_id'])['ownedViews'] if v['_type'] == 'UMLNoteView') == notas_antes
        probadas += 1
    assert probadas >= 1
    assert ids_integros(real)


@pytest.mark.parametrize('lenguaje', ['java', 'python', 'typescript', 'csharp'])
def test_codigo_generado_del_diagrama_de_clases_compila_y_vuelve_al_100(real, tmp_path, lenguaje):
    clases = [d for d in diagramas(real, 'UMLClassDiagram') if d.get('ownedViews')]
    assert clases
    dg = max(clases, key=lambda d: len(d['ownedViews']))
    out = str(tmp_path / lenguaje)
    r = ok(tool('staruml_diagrama_a_codigo', archivo=real, diagrama=dg['_id'], lenguaje=lenguaje, carpeta_salida=out))
    assert r['escritos'] and not r['omitidos_por_nombre_invalido']
    archivos = sorted(glob.glob(os.path.join(out, '*.*')))
    if lenguaje == 'java' and shutil.which('javac'):
        cp = subprocess.run([shutil.which('javac'), '-d', os.path.join(out, 'bin')] + archivos, capture_output=True, text=True)
        assert cp.returncode == 0, cp.stderr[-1500:]
    elif lenguaje == 'typescript' and shutil.which('tsc'):
        cp = subprocess.run([shutil.which('tsc'), '--noEmit', '--strict', '--target', 'es2020'] + archivos, capture_output=True, text=True)
        assert cp.returncode == 0, cp.stdout[-1500:]
    elif lenguaje == 'csharp':
        cp = compilar_csharp(out, str(tmp_path / 'proyecto'))
        assert cp is None or cp[0], cp[1]
    elif lenguaje == 'python':
        for f in archivos:
            cp = subprocess.run([sys.executable, f], capture_output=True, text=True, cwd=out)
            assert cp.returncode == 0, (f, cp.stderr[-500:])
    cmp = ok(tool('staruml_comparar_codigo', archivo=real, diagrama=dg['_id'], ruta_codigo=out, lenguaje=lenguaje))
    assert cmp['porcentaje_sincronizacion'] == 100.0


def test_ediciones_mantienen_la_integridad(real, tmp_path):
    doc = M.Doc(real)
    dg = max((d for d in doc.diagrams() if d['_type'] == 'UMLClassDiagram'), key=lambda d: len(d.get('ownedViews', [])))
    control = next(o for o in doc.ids.values() if o and o['_type'] == 'UMLClass' and doc.kind(o) == 'control')
    pk = doc.name_of(doc.parent[control['_id']])
    base = str(tmp_path / 'antes.mdj')
    shutil.copy(real, base)
    ok(tool('mdj_clase_crear', archivo=real, paquete=doc.parent[control['_id']], nombre='EntidadDePrueba', estereotipo='entity',
            atributos=['folio', 'fecha']))
    ok(tool('mdj_vista_agregar', archivo=real, diagrama=dg['_id'], elemento='EntidadDePrueba', x=40, y=2000))
    ok(tool('mdj_asociacion_crear', archivo=real, desde=control['_id'], hacia='EntidadDePrueba', mult_hacia='0..*', diagrama=dg['_id']))
    ok(tool('mdj_renombrar', archivo=real, elemento='EntidadDePrueba', nuevo_nombre='Entidad de Prueba'))
    ok(tool('mdj_atributos', archivo=real, clase='Entidad de Prueba', atributos=['folio', 'estado']))
    d = ok(tool('mdj_diff', archivo_a=base, archivo_b=real))
    assert d['agregados'].get('UMLClass') == 1 and d['agregados'].get('UMLAssociation') == 1
    ok(tool('mdj_borrar', archivo=real, elemento='Entidad de Prueba'))
    assert ids_integros(real)
    v = ok(tool('mdj_validar', archivo=real))
    assert v['oose']['problemas'] == [] and pk


def test_exportar_diagrama_homonimo_por_id(real, tmp_path, staruml_falso):
    doc = M.Doc(real)
    nombres = [d.get('name') for d in doc.diagrams()]
    repetidos = sorted({n for n in nombres if nombres.count(n) > 1})
    if not repetidos:
        pytest.skip('el modelo no tiene diagramas homonimos')
    for d in (d for d in doc.diagrams() if d.get('name') == repetidos[0]):
        r = ok(tool('staruml_exportar', archivo=real, carpeta=str(tmp_path / d['_id'].replace('/', '_')), diagrama=d['_id']))
        assert f'data-id="{d["_id"]}"' in open(r['archivos'][0], encoding='utf-8').read()
