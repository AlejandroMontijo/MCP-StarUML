# staruml_compare.py
# Comparador de diagramas StarUML (.mdj) contra codigo fuente (Java, Python, TypeScript, C#)
# y generador bidireccional (diagrama <-> codigo).

import os
import re
import glob
from typing import Dict, List, Any, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Normalizacion de tipos y nombres
# ---------------------------------------------------------------------------

def _normalizar_tipo(tipo: str) -> str:
    """Normaliza tipos de datos comunes entre UML y lenguajes de programacion."""
    if not tipo:
        return 'Object'
    t = tipo.strip().lower()
    t = re.sub(r'^(java\.lang\.|java\.util\.|typing\.)', '', t)
    
    # Primitivos y texto
    if t in ('string', 'str', 'varchar', 'text', 'char'):
        return 'String'
    if t in ('int', 'integer', 'long', 'short', 'byte'):
        return 'int'
    if t in ('float', 'double', 'number', 'decimal', 'bigdecimal'):
        return 'double'
    if t in ('bool', 'boolean'):
        return 'boolean'
    if t in ('date', 'localdate', 'datetime', 'localdatetime', 'timestamp', 'fecha'):
        return 'Date'
    if t in ('void', 'none'):
        return 'void'
    
    # Colecciones
    m_col = re.search(r'(?:list|set|collection|arraylist|hashset|array)<([A-Za-z0-9_]+)>', t, re.IGNORECASE)
    if m_col:
        return f"List<{m_col.group(1)}>"
    if t.endswith('[]'):
        return f"List<{t[:-2]}>"
    
    return tipo.strip()

def _normalizar_nombre(nombre: str) -> str:
    """Elimina prefijos/sufijos y caracteres especiales para comparaciones flexibles."""
    if not nombre:
        return ''
    # Quitar estereotipos OOSE o prefijos de interfaz si aplica
    limpio = re.sub(r'^(bc_|ctrl_|ent_|i_|cls_)', '', nombre, flags=re.IGNORECASE)
    # Quitar espacios y guiones bajos
    limpio = re.sub(r'[\s_]+', '', limpio).lower()
    return limpio

# ---------------------------------------------------------------------------
# Extractor de UML desde .mdj
# ---------------------------------------------------------------------------

def extraer_elementos_diagrama(doc, nombre_diagrama: str) -> Dict[str, Any]:
    """Extrae clases, atributos, metodos, asociaciones y mensajes de un diagrama."""
    dg = doc.diagram(nombre_diagrama)
    tipo_dg = dg.get('_type')
    
    if tipo_dg == 'UMLClassDiagram':
        clases = {}
        asociaciones = []
        generalizaciones = []
        
        # Obtener elementos que tienen vista en este diagrama
        ids_en_diagrama = set()
        for v in dg.get('ownedViews', []):
            m = v.get('model')
            if isinstance(m, dict) and '$ref' in m:
                ids_en_diagrama.add(m['$ref'])
        
        for cid in ids_en_diagrama:
            el = doc.ids.get(cid)
            if not el or el.get('_type') not in ('UMLClass', 'UMLInterface', 'UMLActor'):
                continue
            
            nombre_clase = el.get('name', '')
            estereotipo = doc.kind(el)
            doc_texto = el.get('documentation', '')
            
            # Atributos
            attrs = []
            for a in el.get('attributes', []):
                attrs.append({
                    'nombre': a.get('name', ''),
                    'tipo': _normalizar_tipo(a.get('type', '')),
                    'visibilidad': a.get('visibility', 'public')
                })
            
            # Operaciones / Metodos
            metodos = []
            for op in el.get('operations', []):
                params = []
                ret_tipo = 'void'
                for p in op.get('parameters', []):
                    if p.get('direction') == 'return':
                        ret_tipo = _normalizar_tipo(p.get('type', ''))
                    else:
                        params.append({
                            'nombre': p.get('name', ''),
                            'tipo': _normalizar_tipo(p.get('type', ''))
                        })
                metodos.append({
                    'nombre': op.get('name', ''),
                    'retorno': ret_tipo,
                    'parametros': params,
                    'visibilidad': op.get('visibility', 'public')
                })
            
            clases[nombre_clase] = {
                'id': el['_id'],
                'nombre': nombre_clase,
                'tipo': el['_type'],
                'estereotipo': estereotipo,
                'documentacion': doc_texto,
                'atributos': attrs,
                'metodos': metodos,
                'superclases': [],
                'asociaciones': []
            }
        
        # Extraer asociaciones y generalizaciones que tocan estas clases
        for el in doc.ids.values():
            if el.get('_type') == 'UMLAssociation':
                e1 = el.get('end1', {})
                e2 = el.get('end2', {})
                ref1 = e1.get('reference', {}).get('$ref')
                ref2 = e2.get('reference', {}).get('$ref')
                if ref1 in doc.ids and ref2 in doc.ids:
                    c1 = doc.ids[ref1].get('name')
                    c2 = doc.ids[ref2].get('name')
                    if c1 in clases or c2 in clases:
                        asoc_info = {
                            'id': el['_id'],
                            'origen': c1,
                            'destino': c2,
                            'mult_origen': e1.get('multiplicity', ''),
                            'mult_destino': e2.get('multiplicity', ''),
                            'rol_origen': e1.get('name', ''),
                            'rol_destino': e2.get('name', ''),
                            'navegable': e2.get('navigable', True)
                        }
                        asociaciones.append(asoc_info)
                        if c1 in clases:
                            clases[c1]['asociaciones'].append(asoc_info)
            elif el.get('_type') == 'UMLGeneralization':
                sub_ref = el.get('source', {}).get('$ref')
                sup_ref = el.get('target', {}).get('$ref')
                if sub_ref in doc.ids and sup_ref in doc.ids:
                    sub = doc.ids[sub_ref].get('name')
                    sup = doc.ids[sup_ref].get('name')
                    generalizaciones.append({'subclase': sub, 'superclase': sup})
                    if sub in clases:
                        clases[sub]['superclases'].append(sup)
        
        return {
            'tipo_diagrama': 'UMLClassDiagram',
            'nombre': dg.get('name'),
            'clases': clases,
            'asociaciones': asociaciones,
            'generalizaciones': generalizaciones
        }
        
    elif tipo_dg == 'UMLSequenceDiagram':
        # Diagrama de secuencia
        import staruml_mdj as M
        sec = M.secuencia(doc, dg['_id'])
        return {
            'tipo_diagrama': 'UMLSequenceDiagram',
            'nombre': dg.get('name'),
            'lifelines': sec.get('lifelines', []),
            'mensajes': sec.get('mensajes', [])
        }
    
    return {'tipo_diagrama': tipo_dg, 'nombre': dg.get('name')}

# ---------------------------------------------------------------------------
# Parsers de codigo fuente (Java, Python, TypeScript, C#)
# ---------------------------------------------------------------------------

class CodeParser:
    """Parser multilingue de codigo fuente para extraer clases, miembros y llamadas."""
    
    @staticmethod
    def parse_archivo(ruta_archivo: str, lenguaje: str = 'auto') -> Dict[str, Any]:
        ext = os.path.splitext(ruta_archivo)[1].lower()
        if lenguaje == 'auto':
            if ext == '.java':
                lenguaje = 'java'
            elif ext in ('.py', '.pyw'):
                lenguaje = 'python'
            elif ext in ('.ts', '.tsx', '.js', '.jsx'):
                lenguaje = 'typescript'
            elif ext == '.cs':
                lenguaje = 'csharp'
            else:
                return {}
        
        with open(ruta_archivo, 'r', encoding='utf-8', errors='ignore') as f:
            contenido = f.read()
            
        if lenguaje == 'java' or lenguaje == 'csharp':
            return CodeParser._parse_java_csharp(contenido, ruta_archivo, lenguaje)
        elif lenguaje == 'python':
            return CodeParser._parse_python(contenido, ruta_archivo)
        elif lenguaje == 'typescript':
            return CodeParser._parse_typescript(contenido, ruta_archivo)
        return {}

    @staticmethod
    def _parse_java_csharp(code: str, ruta: str, lang: str) -> Dict[str, Any]:
        clases = {}
        # Quitar comentarios para no hacer match con codigo comentado
        code_limpio = re.sub(r'//.*', '', code)
        code_limpio = re.sub(r'/\*.*?\*/', '', code_limpio, flags=re.DOTALL)
        
        # Buscar package
        m_pkg = re.search(r'\bpackage\s+([a-zA-Z0-9_.]+);', code_limpio)
        paquete = m_pkg.group(1) if m_pkg else ''
        
        # Buscar clases e interfaces
        # public class Nombre [extends Base] [implements I1, I2] { ... }
        patron_clase = re.compile(
            r'(?:(@[a-zA-Z0-9_]+(?:\([^)]*\))?\s*)*)'
            r'(?:public|protected|private|abstract|static|final|\s)*\b(class|interface|enum|record)\s+([a-zA-Z0-9_]+)'
            r'(?:<[^>]+>)?'
            r'(?:\s+extends\s+([a-zA-Z0-9_]+(?:\s*,\s*[a-zA-Z0-9_]+)?))?'
            r'(?:\s+implements\s+([a-zA-Z0-9_,\s]+))?'
            r'\s*\{',
            re.MULTILINE
        )
        
        for m in patron_clase.finditer(code_limpio):
            anotaciones_raw = m.group(1) or ''
            tipo_decl = m.group(2)
            nombre_clase = m.group(3)
            extends_raw = m.group(4) or ''
            implements_raw = m.group(5) or ''
            
            anotaciones = re.findall(r'@([a-zA-Z0-9_]+)', anotaciones_raw)
            superclases = [s.strip() for s in extends_raw.split(',') if s.strip()]
            interfaces = [i.strip() for i in implements_raw.split(',') if i.strip()]
            
            # Obtener el cuerpo de la clase buscando llaves balanceadas
            inicio = m.end() - 1
            nivel = 0
            fin = inicio
            for idx in range(inicio, len(code_limpio)):
                if code_limpio[idx] == '{':
                    nivel += 1
                elif code_limpio[idx] == '}':
                    nivel -= 1
                    if nivel == 0:
                        fin = idx
                        break
            cuerpo = code_limpio[inicio+1:fin]
            
            # Atributos: [visibilidad] [modificadores] Tipo nombre [= valor];
            patron_attr = re.compile(
                r'^\s*(?:(@[a-zA-Z0-9_]+(?:\([^)]*\))?\s*)*)'
                r'(?:(public|private|protected)\s+)?'
                r'(?:static\s+|final\s+|transient\s+|volatile\s+)*'
                r'([a-zA-Z0-9_<>,\s\[\]]+?)\s+([a-zA-Z0-9_]+)\s*(?:=[^;]+)?\s*;',
                re.MULTILINE
            )
            atributos = []
            for ma in patron_attr.finditer(cuerpo):
                tipo_attr = ma.group(3).strip()
                nombre_attr = ma.group(4).strip()
                vis = ma.group(2) or 'package'
                # Ignorar si parece metodo o constructor
                if '(' not in tipo_attr and 'return' not in tipo_attr:
                    atributos.append({
                        'nombre': nombre_attr,
                        'tipo': _normalizar_tipo(tipo_attr),
                        'tipo_original': tipo_attr,
                        'visibilidad': vis
                    })
            
            # Metodos: [visibilidad] [modificadores] Retorno nombre(params) { cuerpo }
            patron_metodo = re.compile(
                r'(?:(@[a-zA-Z0-9_]+(?:\([^)]*\))?\s*)*)'
                r'(?:(public|private|protected)\s+)?'
                r'(?:static\s+|final\s+|synchronized\s+|abstract\s+)*'
                r'([a-zA-Z0-9_<>\[\]]+)\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*(?:throws\s+[^{;]+)?\s*(\{)?',
                re.MULTILINE
            )
            metodos = []
            llamadas = []
            for mm in patron_metodo.finditer(cuerpo):
                ret = mm.group(3).strip()
                nom = mm.group(4).strip()
                params_raw = mm.group(5).strip()
                tiene_cuerpo = bool(mm.group(6))
                vis = mm.group(2) or 'package'
                
                # Ignorar if, for, while, switch
                if nom in ('if', 'for', 'while', 'switch', 'catch', 'new'):
                    continue
                # Si es constructor, el retorno suele ser el nombre de la clase
                if nom == nombre_clase:
                    ret = 'void'
                    
                params = []
                if params_raw:
                    for p in params_raw.split(','):
                        partes = p.strip().split()
                        if len(partes) >= 2:
                            p_tipo = partes[-2]
                            p_nom = partes[-1]
                            params.append({'nombre': p_nom, 'tipo': _normalizar_tipo(p_tipo)})
                            
                metodos.append({
                    'nombre': nom,
                    'retorno': _normalizar_tipo(ret),
                    'parametros': params,
                    'visibilidad': vis
                })
            
            # Extraer llamadas a metodos: objeto.metodo(...)
            for m_call in re.finditer(r'([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\s*\(', cuerpo):
                llamadas.append({
                    'objeto': m_call.group(1),
                    'metodo': m_call.group(2)
                })
            
            clases[nombre_clase] = {
                'nombre': nombre_clase,
                'paquete': paquete,
                'tipo_decl': tipo_decl,
                'archivo': ruta,
                'anotaciones': anotaciones,
                'superclases': superclases,
                'interfaces': interfaces,
                'atributos': atributos,
                'metodos': metodos,
                'llamadas': llamadas
            }
            
        return clases

    @staticmethod
    def _parse_python(code: str, ruta: str) -> Dict[str, Any]:
        clases = {}
        # Quitar comentarios
        code_limpio = re.sub(r'#.*', '', code)
        
        # Buscar clases: class Nombre(Super):
        patron_clase = re.compile(r'class\s+([a-zA-Z0-9_]+)(?:\(([^)]*)\))?:', re.MULTILINE)
        lineas = code_limpio.split('\n')
        
        clase_actual = None
        indent_clase = 0
        cuerpo_lineas = []
        
        def procesar_clase(info, lineas_cuerpo):
            nom = info['nombre']
            cuerpo = '\n'.join(lineas_cuerpo)
            attrs = []
            metodos = []
            llamadas = []
            
            # Atributos de clase o en __init__
            for m in re.finditer(r'(?:self\.|^\s*)([a-zA-Z0-9_]+)\s*:\s*([a-zA-Z0-9_\[\], ]+)(?:\s*=|$)', cuerpo, re.MULTILINE):
                attrs.append({'nombre': m.group(1), 'tipo': _normalizar_tipo(m.group(2)), 'visibilidad': 'public'})
            for m in re.finditer(r'self\.([a-zA-Z0-9_]+)\s*=\s*', cuerpo):
                nom_a = m.group(1)
                if not any(a['nombre'] == nom_a for a in attrs):
                    attrs.append({'nombre': nom_a, 'tipo': 'Object', 'visibilidad': 'public'})
                    
            # Metodos: def nombre(self, ...):
            for m in re.finditer(r'def\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)(?:\s*->\s*([a-zA-Z0-9_\[\], ]+))?:', cuerpo):
                nom_m = m.group(1)
                ret_m = m.group(3) or 'void'
                params_raw = m.group(2)
                params = []
                for p in params_raw.split(','):
                    p = p.strip()
                    if p and p != 'self' and p != 'cls':
                        if ':' in p:
                            pnom, ptip = p.split(':', 1)
                            params.append({'nombre': pnom.strip(), 'tipo': _normalizar_tipo(ptip)})
                        else:
                            params.append({'nombre': p, 'tipo': 'Object'})
                metodos.append({'nombre': nom_m, 'retorno': _normalizar_tipo(ret_m), 'parametros': params, 'visibilidad': 'public'})
                
            for m_call in re.finditer(r'([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\s*\(', cuerpo):
                if m_call.group(1) != 'self':
                    llamadas.append({'objeto': m_call.group(1), 'metodo': m_call.group(2)})
                    
            info['atributos'] = attrs
            info['metodos'] = metodos
            info['llamadas'] = llamadas
            clases[nom] = info

        for linea in lineas:
            m = patron_clase.match(linea)
            if m:
                if clase_actual:
                    procesar_clase(clase_actual, cuerpo_lineas)
                nombre_c = m.group(1)
                bases_raw = m.group(2) or ''
                bases = [b.strip() for b in bases_raw.split(',') if b.strip()]
                clase_actual = {
                    'nombre': nombre_c,
                    'paquete': '',
                    'tipo_decl': 'class',
                    'archivo': ruta,
                    'anotaciones': [],
                    'superclases': bases,
                    'interfaces': []
                }
                cuerpo_lineas = []
            elif clase_actual:
                cuerpo_lineas.append(linea)
                
        if clase_actual:
            procesar_clase(clase_actual, cuerpo_lineas)
            
        return clases

    @staticmethod
    def _parse_typescript(code: str, ruta: str) -> Dict[str, Any]:
        clases = {}
        code_limpio = re.sub(r'//.*', '', code)
        code_limpio = re.sub(r'/\*.*?\*/', '', code_limpio, flags=re.DOTALL)
        
        # Buscar export [default] class/interface Nombre [extends ...] [implements ...]
        patron = re.compile(
            r'(?:export\s+(?:default\s+)?)?(class|interface)\s+([a-zA-Z0-9_]+)'
            r'(?:\s+extends\s+([a-zA-Z0-9_]+))?'
            r'(?:\s+implements\s+([a-zA-Z0-9_,\s]+))?'
            r'\s*\{',
            re.MULTILINE
        )
        for m in patron.finditer(code_limpio):
            tipo_decl = m.group(1)
            nom = m.group(2)
            sup = [m.group(3).strip()] if m.group(3) else []
            imp = [i.strip() for i in (m.group(4) or '').split(',') if i.strip()]
            
            inicio = m.end() - 1
            nivel = 0
            fin = inicio
            for idx in range(inicio, len(code_limpio)):
                if code_limpio[idx] == '{':
                    nivel += 1
                elif code_limpio[idx] == '}':
                    nivel -= 1
                    if nivel == 0:
                        fin = idx
                        break
            cuerpo = code_limpio[inicio+1:fin]
            
            attrs = []
            metodos = []
            llamadas = []
            
            # Campos: [public|private] nom[: tipo][ = val];
            for ma in re.finditer(r'^\s*(?:(public|private|protected)\s+)?([a-zA-Z0-9_]+)\s*:\s*([^;=]+)', cuerpo, re.MULTILINE):
                attrs.append({
                    'nombre': ma.group(2),
                    'tipo': _normalizar_tipo(ma.group(3)),
                    'visibilidad': ma.group(1) or 'public'
                })
            # Metodos: [public|private] nom(params)[: tipo] {
            for mm in re.finditer(r'^\s*(?:(public|private|protected)\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*(?::\s*([^{]+))?\s*\{', cuerpo, re.MULTILINE):
                nom_m = mm.group(2)
                ret_m = mm.group(4) or 'void'
                params = []
                for p in mm.group(3).split(','):
                    p = p.strip()
                    if p:
                        pnom = p.split(':')[0].strip()
                        ptip = p.split(':')[1].strip() if ':' in p else 'any'
                        params.append({'nombre': pnom, 'tipo': _normalizar_tipo(ptip)})
                metodos.append({'nombre': nom_m, 'retorno': _normalizar_tipo(ret_m), 'parametros': params, 'visibilidad': mm.group(1) or 'public'})
                
            for m_call in re.finditer(r'([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\s*\(', cuerpo):
                if m_call.group(1) != 'this':
                    llamadas.append({'objeto': m_call.group(1), 'metodo': m_call.group(2)})
                    
            clases[nom] = {
                'nombre': nom,
                'paquete': '',
                'tipo_decl': tipo_decl,
                'archivo': ruta,
                'anotaciones': [],
                'superclases': sup,
                'interfaces': imp,
                'atributos': attrs,
                'metodos': metodos,
                'llamadas': llamadas
            }
        return clases

# ---------------------------------------------------------------------------
# Escaneo recursivo de directorios de codigo
# ---------------------------------------------------------------------------

def escanear_codigo(ruta: str, lenguaje: str = 'auto') -> Dict[str, Any]:
    """Escanea un archivo o directorio completo y devuelve el mapa de clases encontradas."""
    ruta = os.path.abspath(os.path.expanduser(ruta))
    archivos = []
    
    if os.path.isfile(ruta):
        archivos = [ruta]
    elif os.path.isdir(ruta):
        for root, _, files in os.walk(ruta):
            # Ignorar carpetas comunes de build y vcs
            if any(p in root.split(os.sep) for p in ('.git', 'target', 'build', 'node_modules', '__pycache__', '.idea', '.vscode')):
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in ('.java', '.py', '.ts', '.tsx', '.cs'):
                    archivos.append(os.path.join(root, f))
    else:
        raise FileNotFoundError(f"La ruta de codigo no existe: {ruta}")
        
    resultado_clases = {}
    for a in archivos:
        res = CodeParser.parse_archivo(a, lenguaje)
        resultado_clases.update(res)
        
    return resultado_clases

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
    elif tipo_dg == 'UMLSequenceDiagram':
        return _comparar_secuencia_con_codigo(uml_info, codigo_clases)
    else:
        return {
            'error': f'Tipo de diagrama no soportado para comparacion con codigo: {tipo_dg}',
            'diagrama': nombre_diagrama
        }

def _comparar_clases_con_codigo(uml: Dict[str, Any], codigo: Dict[str, Any]) -> Dict[str, Any]:
    clases_uml = uml.get('clases', {})
    asociaciones_uml = uml.get('asociaciones', [])
    
    mapa_codigo_norm = {_normalizar_nombre(k): (k, v) for k, v in codigo.items()}
    
    clases_coincidentes = []
    clases_faltan_en_codigo = []
    detalles_clases = {}
    
    total_checks = 0
    checks_exitosos = 0
    
    for nom_uml, c_uml in clases_uml.items():
        total_checks += 10 # Peso de presencia de clase
        norm = _normalizar_nombre(nom_uml)
        
        if norm in mapa_codigo_norm:
            checks_exitosos += 10
            nom_cod, c_cod = mapa_codigo_norm[norm]
            clases_coincidentes.append({'uml': nom_uml, 'codigo': nom_cod, 'archivo': c_cod.get('archivo')})
            
            # Comparar Atributos
            attrs_uml = {a['nombre']: a for a in c_uml.get('atributos', [])}
            attrs_cod = {a['nombre']: a for a in c_cod.get('atributos', [])}
            
            attrs_ok = []
            attrs_faltan = []
            attrs_discrepancia_tipo = []
            
            for anom, ainfo in attrs_uml.items():
                total_checks += 3
                if anom in attrs_cod:
                    cod_tipo = attrs_cod[anom]['tipo']
                    uml_tipo = ainfo['tipo']
                    if uml_tipo and uml_tipo != 'Object' and uml_tipo != cod_tipo:
                        attrs_discrepancia_tipo.append({
                            'atributo': anom,
                            'tipo_uml': uml_tipo,
                            'tipo_codigo': cod_tipo
                        })
                        checks_exitosos += 1.5 # Coincidio en nombre pero no en tipo
                    else:
                        attrs_ok.append(anom)
                        checks_exitosos += 3
                else:
                    attrs_faltan.append(anom)
                    
            attrs_sobran = [a for a in attrs_cod if a not in attrs_uml]
            
            # Comparar Metodos
            mets_uml = {m['nombre']: m for m in c_uml.get('metodos', [])}
            mets_cod = {m['nombre']: m for m in c_cod.get('metodos', [])}
            
            mets_ok = []
            mets_faltan = []
            for mnom in mets_uml:
                total_checks += 3
                if mnom in mets_cod:
                    mets_ok.append(mnom)
                    checks_exitosos += 3
                else:
                    mets_faltan.append(mnom)
                    
            mets_sobran = [m for m in mets_cod if m not in mets_uml]
            
            # Verificar Asociaciones en campos de la clase en codigo
            asocs_verificadas = []
            asocs_faltantes = []
            for asoc in c_uml.get('asociaciones', []):
                if asoc['origen'] == nom_uml and asoc.get('navegable'):
                    destino = asoc['destino']
                    mult = asoc.get('mult_destino', '')
                    es_coleccion = '*' in mult or '..' in mult and mult.split('..')[1] not in ('0', '1')
                    
                    # Buscar en codigo si hay un campo de tipo destino o List<destino>
                    total_checks += 2
                    encontrado = False
                    for ca in c_cod.get('atributos', []):
                        ct = ca['tipo']
                        if destino.lower() in ct.lower():
                            encontrado = True
                            break
                    if encontrado:
                        checks_exitosos += 2
                        asocs_verificadas.append(f"{asoc['origen']} -> {destino} ({mult})")
                    else:
                        asocs_faltantes.append(f"{asoc['origen']} -> {destino} ({mult})")
            
            detalles_clases[nom_uml] = {
                'archivo': c_cod.get('archivo'),
                'estereotipo': c_uml.get('estereotipo'),
                'atributos': {
                    'coincidentes': attrs_ok,
                    'faltan_en_codigo': attrs_faltan,
                    'sobran_en_codigo': attrs_sobran,
                    'discrepancias_tipo': attrs_discrepancia_tipo
                },
                'metodos': {
                    'coincidentes': mets_ok,
                    'faltan_en_codigo': mets_faltan,
                    'sobran_en_codigo': mets_sobran
                },
                'asociaciones': {
                    'verificadas_en_codigo': asocs_verificadas,
                    'faltantes_en_codigo': asocs_faltantes
                }
            }
        else:
            clases_faltan_en_codigo.append({
                'nombre': nom_uml,
                'estereotipo': c_uml.get('estereotipo'),
                'tipo': c_uml.get('tipo'),
                'atributos_pendientes': [a['nombre'] for a in c_uml.get('atributos', [])],
                'documentacion': c_uml.get('documentacion')
            })
            
    # Clases que sobran en codigo (no estan en el diagrama)
    mapa_uml_norm = {_normalizar_nombre(k): k for k in clases_uml}
    clases_sobran_en_codigo = []
    for nom_cod, c_cod in codigo.items():
        if _normalizar_nombre(nom_cod) not in mapa_uml_norm:
            clases_sobran_en_codigo.append({
                'nombre': nom_cod,
                'archivo': c_cod.get('archivo')
            })
            
    porcentaje = round((checks_exitosos / max(1, total_checks)) * 100, 1)
    
    return {
        'tipo_diagrama': 'UMLClassDiagram',
        'diagrama': uml.get('nombre'),
        'porcentaje_sincronizacion': porcentaje,
        'resumen': {
            'total_clases_uml': len(clases_uml),
            'clases_implementadas': len(clases_coincidentes),
            'clases_faltantes': len(clases_faltan_en_codigo),
            'clases_extras_en_codigo': len(clases_sobran_en_codigo)
        },
        'clases_coincidentes': clases_coincidentes,
        'clases_faltantes_en_codigo': clases_faltan_en_codigo,
        'clases_sobrantes_en_codigo': clases_sobran_en_codigo,
        'detalles_por_clase': detalles_clases
    }

def _comparar_secuencia_con_codigo(uml: Dict[str, Any], codigo: Dict[str, Any]) -> Dict[str, Any]:
    lifelines = uml.get('lifelines', [])
    mensajes = uml.get('mensajes', [])
    
    mapa_codigo = {_normalizar_nombre(k): (k, v) for k, v in codigo.items()}
    
    # 1. Verificar lifelines
    lifelines_analisis = []
    for lf in lifelines:
        nom_tipo = lf.get('tipo', lf.get('clave', '')) if isinstance(lf, dict) else str(lf)
        norm = _normalizar_nombre(nom_tipo)
        if norm in mapa_codigo:
            nom_cod, c_cod = mapa_codigo[norm]
            lifelines_analisis.append({'tipo_uml': nom_tipo, 'en_codigo': True, 'archivo': c_cod.get('archivo')})
        else:
            lifelines_analisis.append({'tipo_uml': nom_tipo, 'en_codigo': False})
            
    # 2. Verificar mensajes
    mensajes_analisis = []
    total_msgs = len(mensajes)
    msgs_verificados = 0
    
    for m in mensajes:
        de_lf = m.get('de')
        a_lf = m.get('a')
        nom_msg = m.get('nombre', '')
        flujo = m.get('flujo', '')
        es_reply = m.get('reply', False)
        
        # Extraer nombre del metodo sin parametros: metodo(a,b) -> metodo
        nom_metodo = nom_msg.split('(')[0].strip()
        
        # El receptor es a_lf
        tipo_receptor = a_lf
        norm_rec = _normalizar_nombre(tipo_receptor) if tipo_receptor else ''
        
        if norm_rec in mapa_codigo:
            _, c_cod = mapa_codigo[norm_rec]
            # Verificar si la clase receptora tiene implementado este metodo
            metodos_rec = [met['nombre'] for met in c_cod.get('metodos', [])]
            metodo_existe = nom_metodo in metodos_rec or es_reply
            
            mensajes_analisis.append({
                'mensaje': nom_msg,
                'de': de_lf,
                'a': a_lf,
                'flujo': flujo,
                'reply': es_reply,
                'clase_destino': tipo_receptor,
                'metodo_implementado_en_destino': metodo_existe
            })
            if metodo_existe:
                msgs_verificados += 1
        else:
            mensajes_analisis.append({
                'mensaje': nom_msg,
                'de': de_lf,
                'a': a_lf,
                'flujo': flujo,
                'reply': es_reply,
                'clase_destino': tipo_receptor,
                'metodo_implementado_en_destino': False,
                'nota': f'Clase receptora "{tipo_receptor}" no encontrada en codigo'
            })
            
    porcentaje = round((msgs_verificados / max(1, total_msgs)) * 100, 1)
    
    return {
        'tipo_diagrama': 'UMLSequenceDiagram',
        'diagrama': uml.get('nombre'),
        'porcentaje_sincronizacion': porcentaje,
        'resumen': {
            'total_mensajes': total_msgs,
            'mensajes_verificados_en_codigo': msgs_verificados,
            'mensajes_pendientes': total_msgs - msgs_verificados
        },
        'lifelines': lifelines_analisis,
        'mensajes': mensajes_analisis
    }

# ---------------------------------------------------------------------------
# Generador de esqueletos de codigo (Diagrama -> Codigo)
# ---------------------------------------------------------------------------

def generar_codigo_desde_diagrama(doc, nombre_diagrama: str, lenguaje: str = 'java', carpeta_salida: str = None) -> Dict[str, Any]:
    """Genera archivos de codigo fuente limpios a partir de las clases de un diagrama."""
    uml = extraer_elementos_diagrama(doc, nombre_diagrama)
    if uml.get('tipo_diagrama') != 'UMLClassDiagram':
        raise ValueError('Solo se puede generar codigo a partir de diagramas de clases')
        
    archivos_generados = {}
    clases = uml.get('clases', {})
    
    for nom, c in clases.items():
        if c.get('tipo') == 'UMLActor':
            continue # Los actores no suelen mapearse a clases de dominio directamente
            
        est = c.get('estereotipo')
        doc_texto = c.get('documentacion', '')
        
        if lenguaje == 'java':
            codigo = _generar_clase_java(c)
            nom_archivo = f"{nom}.java"
        elif lenguaje == 'python':
            codigo = _generar_clase_python(c)
            nom_archivo = f"{nom}.py"
        elif lenguaje == 'typescript':
            codigo = _generar_clase_typescript(c)
            nom_archivo = f"{nom}.ts"
        else:
            raise ValueError(f"Lenguaje no soportado: {lenguaje}")
            
        archivos_generados[nom_archivo] = codigo
        
        if carpeta_salida:
            os.makedirs(carpeta_salida, exist_ok=True)
            ruta_dest = os.path.join(carpeta_salida, nom_archivo)
            with open(ruta_dest, 'w', encoding='utf-8') as f:
                f.write(codigo)
                
    return {
        'diagrama': nombre_diagrama,
        'lenguaje': lenguaje,
        'total_archivos': len(archivos_generados),
        'archivos': list(archivos_generados.keys()),
        'guardado_en': carpeta_salida
    }

def _generar_clase_java(c: Dict[str, Any]) -> str:
    nom = c['nombre']
    est = c.get('estereotipo')
    doc_t = c.get('documentacion', '')
    
    lineas = []
    lineas.append("package modelo;")
    lineas.append("")
    lineas.append("import java.util.*;")
    lineas.append("import java.time.LocalDate;")
    lineas.append("")
    if doc_t:
        lineas.append("/**")
        lineas.append(f" * {doc_t}")
        lineas.append(" */")
        
    lineas.append(f"public class {nom} {{")
    
    # Atributos
    for a in c.get('atributos', []):
        anom = a['nombre']
        atip = a.get('tipo') or 'String'
        if atip == 'Date':
            atip = 'LocalDate'
        lineas.append(f"    private {atip} {anom};")
        
    # Asociaciones
    for asoc in c.get('asociaciones', []):
        if asoc['origen'] == nom and asoc.get('navegable'):
            dest = asoc['destino']
            mult = asoc.get('mult_destino', '')
            rol = asoc.get('rol_destino') or dest[0].lower() + dest[1:]
            if '*' in mult or '..' in mult and mult.split('..')[1] not in ('0', '1'):
                lineas.append(f"    private List<{dest}> {rol}s = new ArrayList<>();")
            else:
                lineas.append(f"    private {dest} {rol};")
                
    lineas.append("")
    # Constructor por defecto
    lineas.append(f"    public {nom}() {{}}")
    lineas.append("")
    
    # Getters y Setters para atributos
    for a in c.get('atributos', []):
        anom = a['nombre']
        atip = a.get('tipo') or 'String'
        if atip == 'Date':
            atip = 'LocalDate'
        cap = anom[0].upper() + anom[1:] if len(anom) > 1 else anom.upper()
        lineas.append(f"    public {atip} get{cap}() {{ return this.{anom}; }}")
        lineas.append(f"    public void set{cap}({atip} {anom}) {{ this.{anom} = {anom}; }}")
        lineas.append("")
        
    # Metodos
    for m in c.get('metodos', []):
        mnom = m['nombre']
        mret = m.get('retorno') or 'void'
        mparams = ", ".join(f"{p['tipo']} {p['nombre']}" for p in m.get('parametros', []))
        lineas.append(f"    public {mret} {mnom}({mparams}) {{")
        if mret != 'void':
            lineas.append("        return null;")
        lineas.append("    }")
        lineas.append("")
        
    lineas.append("}")
    return "\n".join(lineas)

def _generar_clase_python(c: Dict[str, Any]) -> str:
    nom = c['nombre']
    doc_t = c.get('documentacion', '')
    
    lineas = []
    lineas.append("from dataclasses import dataclass, field")
    lineas.append("from typing import List, Optional")
    lineas.append("from datetime import date")
    lineas.append("")
    lineas.append("@dataclass")
    lineas.append(f"class {nom}:")
    if doc_t:
        lineas.append(f'    """{doc_t}"""')
        
    attrs = c.get('atributos', [])
    if not attrs:
        lineas.append("    pass")
    else:
        for a in attrs:
            anom = a['nombre']
            atip = a.get('tipo', 'str')
            if atip == 'Date':
                atip = 'date'
            elif atip in ('int', 'double'):
                atip = 'int' if atip == 'int' else 'float'
            lineas.append(f"    {anom}: Optional[{atip}] = None")
            
    for m in c.get('metodos', []):
        mnom = m['nombre']
        mret = m.get('retorno', 'None')
        lineas.append("")
        lineas.append(f"    def {mnom}(self) -> {mret}:")
        lineas.append("        pass")
        
    return "\n".join(lineas)

def _generar_clase_typescript(c: Dict[str, Any]) -> str:
    nom = c['nombre']
    doc_t = c.get('documentacion', '')
    
    lineas = []
    if doc_t:
        lineas.append("/**")
        lineas.append(f" * {doc_t}")
        lineas.append(" */")
    lineas.append(f"export class {nom} {{")
    for a in c.get('atributos', []):
        anom = a['nombre']
        atip = 'string'
        if a.get('tipo') in ('int', 'double'):
            atip = 'number'
        elif a.get('tipo') == 'boolean':
            atip = 'boolean'
        elif a.get('tipo') == 'Date':
            atip = 'Date'
        lineas.append(f"  public {anom}?: {atip};")
        
    lineas.append("")
    lineas.append("  constructor(init?: Partial<" + nom + ">) {")
    lineas.append("    Object.assign(this, init);")
    lineas.append("  }")
    lineas.append("}")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Importador de codigo hacia .mdj (Codigo -> Diagrama)
# ---------------------------------------------------------------------------

def importar_codigo_a_diagrama(doc, ruta_codigo: str, paquete_nombre: str, nombre_diagrama: str = None, lenguaje: str = 'auto') -> Dict[str, Any]:
    """Importa clases, atributos y metodos desde codigo hacia el modelo .mdj y opcionalmente a un diagrama."""
    clases_codigo = escanear_codigo(ruta_codigo, lenguaje)
    if not clases_codigo:
        raise ValueError(f"No se encontraron clases en {ruta_codigo}")
        
    pk = doc.find(paquete_nombre, types=('UMLPackage', 'UMLModel', 'UMLSubsystem'))
    
    clases_creadas = []
    clases_actualizadas = []
    
    for nom, c_cod in clases_codigo.items():
        try:
            c_existente = doc.find(nom, types=('UMLClass', 'UMLInterface'))
        except Exception:
            c_existente = None

        
        if c_existente is None:
            c_elem = {
                '_type': 'UMLClass',
                '_id': doc.new_id(),
                '_parent': {'$ref': pk['_id']},
                'name': nom
            }
            pk.setdefault('ownedElements', []).append(c_elem)
            doc.reindex()
            target_clase = c_elem
            clases_creadas.append(nom)
        else:
            target_clase = c_existente
            clases_actualizadas.append(nom)
            
        attrs_nombres = [a['nombre'] for a in c_cod.get('atributos', [])]
        if attrs_nombres:
            import staruml_mdj as M
            if doc.kind(target_clase) not in ('boundary', 'control'):
                M.set_atributos(doc, target_clase, attrs_nombres)
                
    vistas_creadas = []
    if nombre_diagrama:
        import staruml_mdj as M
        dg = doc.diagram(nombre_diagrama)
        x_base, y_base = 60, 80
        col_w, row_h = 240, 160
        cols = 4
        
        for i, nom in enumerate(clases_creadas):
            el = doc.find(nom)
            r = i // cols
            c = i % cols
            x = x_base + c * col_w
            y = y_base + r * row_h
            if not doc.views_of(el['_id'], dg):
                v = M.vista_nueva(doc, dg, el, x, y, 180, 100)
                vistas_creadas.append({'clase': nom, 'vista': v['_id']})
                
    return {
        'paquete': paquete_nombre,
        'diagrama': nombre_diagrama,
        'total_clases_codigo': len(clases_codigo),
        'clases_creadas': clases_creadas,
        'clases_actualizadas': clases_actualizadas,
        'vistas_creadas': vistas_creadas
    }

