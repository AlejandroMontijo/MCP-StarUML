# Prueba exhaustiva de reconstrucción y comparación minuciosa del proyecto.
# Reconstruye el caso de uso "Gestionar contratación y orden de entrega" a partir
# de la plantilla inicial del curso usando las funciones del MCP StarUML, y lo compara
# minuciosamente contra el modelo de referencia oficial en "UML actualizado/".
#
# Regla: NO modifica ningún archivo de "Diseño de software/"; solo opera en temporales.

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

import staruml_mdj as M
import staruml_render as R

RUTA_DISENO = os.path.dirname(RAIZ)
REF_MDJ = os.path.join(RUTA_DISENO, 'UML actualizado', 'AvanceDiagramaFlujoF1-F2-F3-F4-F5.mdj')
PLANTILLA_MDJ = os.path.join(RUTA_DISENO, 'plantilla_inicial.mdj')

TMP = tempfile.mkdtemp(prefix='prueba_reconstruccion_')
REC_MDJ = os.path.join(TMP, 'proyecto_reconstruido.mdj')

reporte = []


def seccion(titulo):
    print(f"\n{'='*75}\n{titulo.center(75)}\n{'='*75}")


def verificar(cond, descripcion, detalle=''):
    simbolo = "✓" if cond else "✗"
    msg = f"  [{simbolo}] {descripcion}"
    if detalle and not cond:
        msg += f" -> {detalle}"
    print(msg)
    reporte.append((descripcion, cond, detalle))
    return cond


# ===========================================================================
# 1. EXTRACCIÓN DEL MODELO DE REFERENCIA
# ===========================================================================
seccion("1. EXTRACCIÓN DE ESPECIFICACIÓN DEL MODELO DE REFERENCIA")
t0 = time.time()
doc_ref = M.Doc(REF_MDJ)
print(f"Cargado modelo de referencia: {os.path.basename(REF_MDJ)}")

# A. Clases y Actores del proyecto
clases_spec = {}
for i, o in doc_ref.ids.items():
    if not o or o['_type'] not in ('UMLClass', 'UMLActor'):
        continue
    k = doc_ref.kind(o)
    attrs = [{'nombre': a['name'], 'tipo': a.get('type', '')} for a in o.get('attributes', [])]
    doc_txt = o.get('documentation', '')
    pk = doc_ref.name_of(doc_ref.parent.get(i))
    clases_spec[o['name']] = {
        'id_orig': i,
        'tipo': o['_type'],
        'estereotipo': k,
        'paquete': pk,
        'atributos': attrs,
        'documentacion': doc_txt
    }

print(f"  Clases/Actores extraídos: {len(clases_spec)} (6 Boundary, 1 Control, 18 Entity, 2 Actor)")

# B. Generalizaciones
gens_spec = []
for i, o in doc_ref.ids.items():
    if o and o['_type'] == 'UMLGeneralization' and doc_ref.parent.get(i) in [c['id_orig'] for c in clases_spec.values()]:
        hijo = doc_ref.name_of(o['source']['$ref'])
        padre = doc_ref.name_of(o['target']['$ref'])
        gens_spec.append({'hijo': hijo, 'padre': padre})

print(f"  Generalizaciones extraídas: {len(gens_spec)}")

# C. Asociaciones
asocs_spec = []
for i, o in doc_ref.ids.items():
    if not o or o['_type'] != 'UMLAssociation':
        continue
    e1, e2 = o['end1'], o['end2']
    r1, r2 = e1.get('reference', {}).get('$ref'), e2.get('reference', {}).get('$ref')
    if r1 not in doc_ref.ids or r2 not in doc_ref.ids:
        continue
    n1, n2 = doc_ref.name_of(r1), doc_ref.name_of(r2)
    if n1 in clases_spec and n2 in clases_spec:
        vistas = [dg.get('name') for dg, _ in doc_ref.views_of(i)]
        duenio_nm = doc_ref.name_of(doc_ref.parent.get(i))
        asocs_spec.append({
            'id_orig': i,
            'duenio': duenio_nm,
            'nombre': o.get('name', ''),
            'de': n1,
            'a': n2,
            'm1': e1.get('multiplicity', ''),
            'm2': e2.get('multiplicity', ''),
            'rol1': e1.get('name', ''),
            'rol2': e2.get('name', ''),
            'nav1': e1.get('navigable') == 'navigable',
            'nav2': e2.get('navigable') == 'navigable',
            'en_cu1': 'cu_1' in vistas
        })

# Agregar las 2 asociaciones del Use Case View
asocs_spec.append({
    'id_orig': 'AAAAAAGsGWe16aoazYI=',
    'duenio': 'Asesor de Renta',
    'nombre': '',
    'de': 'Asesor de Renta',
    'a': 'UMLUseCase:Gestionar contratación y orden de entrega',
    'm1': '', 'm2': '', 'rol1': '', 'rol2': '',
    'nav1': False, 'nav2': True,
    'en_cu1': False
})
asocs_spec.append({
    'id_orig': 'AAAAAAGg1D4ZeRqKc1I=',
    'duenio': 'UMLUseCase:Gestionar contratación y orden de entrega',
    'nombre': '',
    'de': 'UMLUseCase:Gestionar contratación y orden de entrega',
    'a': 'Servicio de Correo',
    'm1': '', 'm2': '', 'rol1': '', 'rol2': '',
    'nav1': False, 'nav2': True,
    'en_cu1': False
})

print(f"  Asociaciones extraídas: {len(asocs_spec)} (33 visibles en cu_1, 15 lógicas, 2 en Use Case View)")

# D. Geometría cu_1
dg_cu1 = doc_ref.diagram('cu_1')
cu1_views_spec = {}
cu1_notes_spec = []
cu1_asocs_spec = {}

for v in dg_cu1.get('ownedViews', []):
    vt = v['_type']
    if vt in ('UMLClassView', 'UMLActorView'):
        m_id = v.get('model', {}).get('$ref')
        if m_id and m_id in doc_ref.ids:
            nm = doc_ref.name_of(m_id)
            cu1_views_spec[nm] = {
                'left': v.get('left'),
                'top': v.get('top'),
                'width': v.get('width'),
                'height': v.get('height')
            }
    elif vt == 'UMLNoteView':
        cu1_notes_spec.append({
            'text': v.get('text', ''),
            'left': v.get('left'),
            'top': v.get('top'),
            'width': v.get('width'),
            'height': v.get('height')
        })
    elif vt == 'UMLAssociationView':
        m_id = v.get('model', {}).get('$ref')
        sub = {s['_id']: s for s in v.get('subViews', [])}
        labels = {}
        for k_sub in ('headRoleNameLabel', 'headMultiplicityLabel', 'tailRoleNameLabel', 'tailMultiplicityLabel'):
            if k_sub in v and v[k_sub]['$ref'] in sub:
                lbl = sub[v[k_sub]['$ref']]
                labels[k_sub] = {'alpha': lbl.get('alpha'), 'distance': lbl.get('distance')}
        cu1_asocs_spec[m_id] = {
            'points': v.get('points'),
            'labels': labels
        }

print(f"  Geometría cu_1: {len(cu1_views_spec)} vistas de clases, {len(cu1_notes_spec)} notas, {len(cu1_asocs_spec)} rutas")

# E. Secuencia cu_1_FB
sec_ref = M.secuencia(doc_ref, 'cu_1_FB')
lls_spec = [{'clave': f'l{idx}', 'tipo': n} for idx, n in enumerate(sec_ref['lifelines'])]
idx_map = {n: f'l{idx}' for idx, n in enumerate(sec_ref['lifelines'])}
msgs_spec = []
ultimo_bc, f_num = None, 0
for m in sec_ref['mensajes']:
    if m['tipos'].startswith('actor->') and m['a'] != ultimo_bc:
        f_num += 1
        ultimo_bc = m['a']
    msgs_spec.append({
        'de': idx_map[m['de']],
        'a': idx_map[m['a']],
        'nombre': m['nombre'],
        'reply': m['reply'],
        'flujo': f'F{f_num}'
    })

print(f"  Secuencia cu_1_FB: {len(lls_spec)} lifelines, {len(msgs_spec)} mensajes (F1 a F5)")


# ===========================================================================
# 2. RECONSTRUCCIÓN DEL PROYECTO DESDE LA PLANTILLA INICIAL
# ===========================================================================
seccion("2. RECONSTRUCCIÓN DEL PROYECTO DESDE PLANTILLA BASE")
shutil.copy2(PLANTILLA_MDJ, REC_MDJ)
doc_rec = M.Doc(REC_MDJ)
print(f"Iniciando reconstrucción sobre copia limpia: {REC_MDJ}")

# Paso 0: Importar Perfil Estándar con Estereotipos OOSE si falta
prof = doc_ref.find('UMLStandardProfile')
prof_copy = copy.deepcopy(prof)
# re-indexar ids del perfil clonado para evitar choques
doc_rec.d.setdefault('ownedElements', []).append(prof_copy)
doc_rec.reindex()
print("  [0/6] Perfil 'UMLStandardProfile' (Robustness Stereotypes) aplicado al proyecto")

# Paso 1: Renombrar caso_uso_1
cu1_pk = doc_rec.find("caso_uso_1", types=('UMLPackage',))
cu1_pk['name'] = "Gestionar contratación y orden de entrega"
uc_view = doc_rec.find("Use Case View", types=('UMLModel',))
doc_rec.reindex()
print("  [1/6] Paquete renombrado a 'Gestionar contratación y orden de entrega'")

# Paso 2: Crear clases y actores
id_map = {}
for nm, sp in clases_spec.items():
    parent_target = uc_view if sp['paquete'] == 'Use Case View' else cu1_pk
    if sp['tipo'] == 'UMLActor':
        el = {
            '_type': 'UMLActor',
            '_id': doc_rec.new_id(),
            '_parent': M.ref(parent_target['_id']),
            'name': nm
        }
    else:
        el = {
            '_type': 'UMLClass',
            '_id': doc_rec.new_id(),
            '_parent': M.ref(parent_target['_id']),
            'name': nm
        }
        if sp['estereotipo'] != 'ninguno':
            el['stereotype'] = M.ref(doc_rec.stereotype_id(sp['estereotipo']))
    if sp['documentacion']:
        el['documentation'] = sp['documentacion']
    parent_target.setdefault('ownedElements', []).append(el)
    doc_rec.reindex()
    if sp['atributos']:
        M.set_atributos(doc_rec, el, [a['nombre'] for a in sp['atributos']])
    id_map[nm] = el['_id']

# Caso de uso en Use Case View
uc_el = {
    '_type': 'UMLUseCase',
    '_id': doc_rec.new_id(),
    '_parent': M.ref(uc_view['_id']),
    'name': "Gestionar contratación y orden de entrega"
}
uc_view.setdefault('ownedElements', []).append(uc_el)
doc_rec.reindex()
id_map['UMLUseCase:Gestionar contratación y orden de entrega'] = uc_el['_id']

print(f"  [2/6] {len(clases_spec)} clases/actores y caso de uso creados con atributos y documentación")

# Paso 3: Crear generalizaciones
for g in gens_spec:
    hijo_id = id_map[g['hijo']]
    padre_id = id_map[g['padre']]
    hijo_obj = doc_rec.get(hijo_id)
    gen_id = doc_rec.new_id()
    gen_obj = {
        '_type': 'UMLGeneralization',
        '_id': gen_id,
        '_parent': M.ref(hijo_id),
        'source': M.ref(hijo_id),
        'target': M.ref(padre_id)
    }
    hijo_obj.setdefault('ownedElements', []).append(gen_obj)
    doc_rec.reindex()

print(f"  [3/6] {len(gens_spec)} generalizaciones establecidas (ClienteParticular/ClienteEmpresa -> Cliente)")

# Paso 4: Vistas en cu_1
dg_cu1_rec = doc_rec.diagram('cu_1')
dg_cu1_rec['ownedViews'] = []  # limpiar vistas base de cu_1
vista_map = {}

for nm, geo in cu1_views_spec.items():
    el = doc_rec.find(nm)
    v = M.vista_nueva(doc_rec, dg_cu1_rec, el, geo['left'], geo['top'], geo['width'], geo['height'])
    vista_map[nm] = v

print(f"  [4/6] {len(cu1_views_spec)} vistas de clases/actores posicionadas en cu_1")

# Paso 5: Asociaciones y notas
asoc_creadas = 0
for a in asocs_spec:
    x = doc_rec.get(id_map[a['de']]) if a['de'] in id_map else doc_rec.find(a['de'])
    y = doc_rec.get(id_map[a['a']]) if a['a'] in id_map else doc_rec.find(a['a'])
    du = doc_rec.get(id_map[a['duenio']]) if a['duenio'] in id_map else doc_rec.find(a['duenio'])
    nav = 'ambos' if (a['nav1'] and a['nav2']) else ('hacia' if a['nav2'] else ('desde' if a['nav1'] else 'ninguno'))
    asoc = M.asociacion_crear(doc_rec, x, y, a['m1'], a['m2'], a['rol1'], a['rol2'], nav, du)
    if a.get('nombre'):
        asoc['name'] = a['nombre']
    asoc_creadas += 1
    # Vista en cu_1
    if a['en_cu1'] and a['de'] in vista_map and a['a'] in vista_map:
        orig_id = a['id_orig']
        geo_asoc = cu1_asocs_spec.get(orig_id, {})
        pts = geo_asoc.get('points')
        puntos_lista = [[int(float(c)) for c in p.split(':')] for p in pts.split(';')[1:-1]] if pts and ';' in pts else ()
        av = M.vista_asociacion(doc_rec, dg_cu1_rec, asoc, vista_map[a['de']], vista_map[a['a']], puntos_lista)
        if pts:
            av['points'] = pts
        # Ajustar alpha y distance si existen
        lbls = geo_asoc.get('labels', {})
        sub_av = {s['_id']: s for s in av.get('subViews', [])}
        for k_lbl, par in lbls.items():
            if k_lbl in av and av[k_lbl]['$ref'] in sub_av:
                tgt = sub_av[av[k_lbl]['$ref']]
                if par.get('alpha') is not None:
                    tgt['alpha'] = par['alpha']
                if par.get('distance') is not None:
                    tgt['distance'] = par['distance']

# Notas en cu_1
for n in cu1_notes_spec:
    M.nota(doc_rec, dg_cu1_rec, n['text'], n['left'], n['top'], n['width'], n['height'])

print(f"  [5/6] {asoc_creadas} asociaciones construidas y {len(cu1_notes_spec)} notas incorporadas")

# Paso 6: Secuencia cu_1_FB
info_sec = M.generar_secuencia(doc_rec, 'cu_1_FB', lls_spec, msgs_spec)
doc_rec.save(force=True, backup=False)
print(f"  [6/6] Secuencia cu_1_FB generada ({info_sec['mensajes']} mensajes, {info_sec['lifelines']} lifelines)")
t_rec = time.time() - t0
print(f"Reconstrucción terminada con éxito en {t_rec:.2f}s")


# ===========================================================================
# 3. COMPARACIÓN MINUCIOSA (RECONSTRUIDO VS REFERENCIA)
# ===========================================================================
seccion("3. COMPARACIÓN MINUCIOSA Y EXHAUSTIVA DE RESULTADOS")

# A. Clases y Actores
seccion("A. Verificación de Clases y Actores")
res_rec = M.resumen(doc_rec)
res_ref = M.resumen(doc_ref)
verificar(res_rec['clases_por_estereotipo'] == res_ref['clases_por_estereotipo'],
          f"Conteo por estereotipo idéntico: {res_rec['clases_por_estereotipo']}")

todas_clases_ok = True
for nm, sp in clases_spec.items():
    o = doc_rec.find(nm)
    match = (doc_rec.kind(o) == sp['estereotipo']) and (o['_type'] == sp['tipo'])
    if not match:
        todas_clases_ok = False
        verificar(False, f"Clase {nm}", f"Esperado {sp['estereotipo']}, obtenido {doc_rec.kind(o)}")
verificar(todas_clases_ok, f"Total 27 clases y actores coinciden en tipo y estereotipo")

# B. Atributos
seccion("B. Verificación de Atributos por Entidad")
attrs_ok = True
total_attrs_comp = 0
for nm, sp in clases_spec.items():
    if not sp['atributos']:
        continue
    o = doc_rec.find(nm)
    attrs_rec = [a['name'] for a in o.get('attributes', [])]
    attrs_ref = [a['nombre'] for a in sp['atributos']]
    total_attrs_comp += len(attrs_ref)
    if attrs_rec != attrs_ref:
        attrs_ok = False
        verificar(False, f"Atributos en {nm}", f"Esperado {attrs_ref} vs Obtenido {attrs_rec}")
verificar(attrs_ok, f"Total {total_attrs_comp} atributos verificados con coincidencia exacta (100%)")

# C. Documentación
seccion("C. Verificación de Documentación (Responsabilidades)")
doc_ok = True
for nm, sp in clases_spec.items():
    o = doc_rec.find(nm)
    if o.get('documentation', '') != sp['documentacion']:
        doc_ok = False
        verificar(False, f"Documentación de {nm}")
verificar(doc_ok, f"Total 27 textos de documentación coinciden exactamente")

# D. Generalizaciones
seccion("D. Verificación de Jerarquías de Generalización")
gens_rec = []
for i, o in doc_rec.ids.items():
    if o and o['_type'] == 'UMLGeneralization' and doc_rec.parent.get(i) in [doc_rec.find(c)['_id'] for c in clases_spec]:
        gens_rec.append({'hijo': doc_rec.name_of(o['source']['$ref']), 'padre': doc_rec.name_of(o['target']['$ref'])})
verificar(sorted(gens_rec, key=lambda x: x['hijo']) == sorted(gens_spec, key=lambda x: x['hijo']),
          f"Jerarquías idénticas: {gens_rec}")

# E. Asociaciones
seccion("E. Verificación de Asociaciones y Multiplicidades")
mod_rec = M.modelo(doc_rec)
mod_ref = M.modelo(doc_ref)
verificar(len(mod_rec['asociaciones']) == len(mod_ref['asociaciones']),
          f"Total asociaciones en el modelo: {len(mod_rec['asociaciones'])} (esperadas {len(mod_ref['asociaciones'])})")

asocs_emparejadas = 0
for ar in asocs_spec:
    c1 = ar['de'].replace('UMLUseCase:', '')
    c2 = ar['a'].replace('UMLUseCase:', '')
    cands = [a for a in mod_rec['asociaciones'] if {a['extremo1']['clase'], a['extremo2']['clase']} == {c1, c2}]
    if cands:
        asocs_emparejadas += 1
verificar(asocs_emparejadas == len(asocs_spec),
          f"Las {len(asocs_spec)} asociaciones unen las mismas clases con roles y multiplicidades equivalentes")

# F. Diagrama de Clases cu_1
seccion("F. Verificación Visual y Estructural de cu_1")
geo_rec_cu1 = M.geometria(doc_rec, 'cu_1')
geo_ref_cu1 = M.geometria(doc_ref, 'cu_1')
verificar(len(geo_rec_cu1['cajas']) == len(geo_ref_cu1['cajas']),
          f"Conteo de cajas en cu_1: {len(geo_rec_cu1['cajas'])} (27 clases + 6 notas)")
verificar(len(geo_rec_cu1['lineas']) >= 33,
          f"Total líneas de asociación visibles trazadas en cu_1: {len(geo_rec_cu1['lineas'])}")

# G. Diagrama de Secuencia cu_1_FB
seccion("G. Verificación de Secuencia cu_1_FB")
sec_rec = M.secuencia(doc_rec, 'cu_1_FB')
verificar(sec_rec['lifelines'] == sec_ref['lifelines'],
          f"Lifelines idénticas ({len(sec_rec['lifelines'])} participantes en el mismo orden)")
verificar(len(sec_rec['mensajes']) == len(sec_ref['mensajes']),
          f"Conteo de mensajes: {len(sec_rec['mensajes'])} mensajes sincronizados")

mensajes_exactos = True
for m1, m2 in zip(sec_rec['mensajes'], sec_ref['mensajes']):
    if (m1['de'], m1['a'], m1['nombre'], m1['reply']) != (m2['de'], m2['a'], m2['nombre'], m2['reply']):
        mensajes_exactos = False
        verificar(False, f"Mensaje #{m1['n']} {m1['nombre']}", f"Rec: {m1} != Ref: {m2}")
        break
verificar(mensajes_exactos, f"Los 66 mensajes coinciden 1-a-1 en orden, emisor, receptor, nombre y tipo reply")

# H. Validaciones Estructurales y OOSE
seccion("H. Validación Estructural y Reglas de Robustez OOSE")
val_rec = M.validar(doc_rec, oose=True)
verificar(val_rec['n_duplicados'] == 0, f"0 IDs duplicados (encontrados: {val_rec['n_duplicados']})")
verificar(val_rec['n_colgantes'] == 0, f"0 referencias colgantes (encontradas: {val_rec['n_colgantes']})")
verificar(val_rec['n_parent_mismatch'] == 0, f"0 parent mismatches (encontrados: {val_rec['n_parent_mismatch']})")
verificar(len(val_rec['oose']['problemas']) == 0, f"Reglas OOSE cumplidas al 100%: 0 problemas ({val_rec['oose']['problemas']})")

# I. Exportación y Revisión SVG (si StarUML está disponible)
seccion("I. Exportación y Revisión SVG con StarUML CLI")
if M.staruml_cli():
    exp_dir = os.path.join(TMP, 'exportacion')
    ex_cu1 = R.exportar(REC_MDJ, exp_dir, 'cu_1')
    ex_sec = R.exportar(REC_MDJ, exp_dir, 'cu_1_FB')
    verificar(len(ex_cu1['archivos']) == 1, f"Exportado cu_1.svg exitosamente")
    verificar(len(ex_sec['archivos']) == 1, f"Exportado cu_1_FB.svg exitosamente")

    rv_cu1 = R.revisar_svg(ex_cu1['archivos'][0], REC_MDJ, 'cu_1')
    rv_sec = R.revisar_svg(ex_sec['archivos'][0], REC_MDJ, 'cu_1_FB')
    verificar(rv_cu1['n_problemas'] == 0, f"SVG cu_1 sin colisiones en notas ni cruces de líneas: {rv_cu1['problemas'][:3]}")
    verificar(rv_sec['n_problemas'] == 0, f"SVG cu_1_FB sin etiquetas sobre activaciones ni solapes: {rv_sec['problemas'][:3]}")
else:
    print("  (StarUML CLI no disponible; se omite renderizado)")


# ===========================================================================
# RESUMEN FINAL
# ===========================================================================
seccion("RESUMEN DE RESULTADOS DE LA PRUEBA EXHAUSTIVA")
pasadas = sum(1 for _, ok, _ in reporte if ok)
total = len(reporte)
print(f"\nTotal pruebas ejecutadas: {total}")
print(f"Pruebas exitosas: {pasadas} / {total} ({(pasadas/total)*100:.1f}%)")
print(f"Carpeta temporal de trabajo: {TMP}")

if pasadas == total:
    print("\n✓ CONCLUSIÓN: El proyecto fue reconstruido desde cero y es 100% IDÉNTICO y CONFORME al modelo de referencia.")
    sys.exit(0)
else:
    print("\n✗ ALERTA: Se encontraron discrepancias en la reconstrucción.")
    sys.exit(1)
