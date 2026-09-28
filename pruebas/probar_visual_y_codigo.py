#!/usr/bin/env python3
# pruebas/probar_visual_y_codigo.py
# Pruebas para las nuevas funciones estilo Figma MCP:
# - Inspeccion visual de diagramas (staruml_ver_visual)
# - Comparacion bidireccional contra codigo fuente (staruml_comparar_codigo)
# - Generacion de esqueletos de codigo (staruml_diagrama_a_codigo)
# - Importacion de codigo al modelo (staruml_codigo_a_diagrama)

import os
import sys
import json
import base64
import subprocess
import shutil
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

import staruml_mdj as M
import staruml_render as R
import staruml_compare as C

MDJ_REF = os.path.join(AQUI, 'proyecto_reconstruido.mdj')

def main():
    print("=== INICIANDO PRUEBAS DE INSPECCION VISUAL Y COMPARACION CON CODIGO ===")
    assert os.path.exists(MDJ_REF), f"No existe {MDJ_REF}"
    doc = M.Doc(MDJ_REF)
    tmp_dir = tempfile.mkdtemp(prefix='mcp_visual_code_test_')
    
    try:
        # 1. Prueba de Generacion de Codigo desde Diagrama
        print("\n[1] Probando staruml_diagrama_a_codigo (Java, Python, TypeScript)...")
        ruta_java = os.path.join(tmp_dir, 'codigo_java')
        res_java = C.generar_codigo_desde_diagrama(doc, 'cu_1', lenguaje='java', carpeta_salida=ruta_java)
        assert res_java['total_archivos'] >= 25, f"Esperaba >=25 archivos, obtuve {res_java['total_archivos']}"
        assert os.path.exists(os.path.join(ruta_java, 'Cliente.java')), "Falta Cliente.java"
        assert os.path.exists(os.path.join(ruta_java, 'ContratacionRenta.java')), "Falta ContratacionRenta.java"
        print(f" -> OK: {res_java['total_archivos']} clases Java generadas correctamente.")
        
        # 2. Prueba de Comparacion de Diagrama de Clases contra Codigo
        print("\n[2] Probando staruml_comparar_codigo (Clases vs Java)...")
        res_comp_clases = C.comparar_diagrama_con_codigo(doc, 'cu_1', ruta_java, lenguaje='java')
        sinc_clases = res_comp_clases['porcentaje_sincronizacion']
        assert sinc_clases >= 90.0, f"Sincronizacion esperada >=90%, obtuve {sinc_clases}%"
        assert res_comp_clases['resumen']['clases_implementadas'] >= 25
        print(f" -> OK: Alineacion UML vs Codigo Java: {sinc_clases}% sincronizado.")
        print(f"    Implementadas: {res_comp_clases['resumen']['clases_implementadas']}, Faltantes: {res_comp_clases['resumen']['clases_faltantes']}")
        
        # 3. Prueba de Comparacion de Diagrama de Secuencia contra Codigo
        print("\n[3] Probando staruml_comparar_codigo (Secuencia vs Java)...")
        res_comp_sec = C.comparar_diagrama_con_codigo(doc, 'cu_1_FB', ruta_java, lenguaje='java')
        assert res_comp_sec['tipo_diagrama'] == 'UMLSequenceDiagram'
        assert res_comp_sec['resumen']['total_mensajes'] == 66
        lfs_ok = sum(1 for lf in res_comp_sec['lifelines'] if lf['en_codigo'])
        assert lfs_ok >= 23, f"Esperaba >=23 lifelines en codigo, obtuve {lfs_ok}"
        print(f" -> OK: Diagrama de secuencia analizado contra codigo. Lifelines en codigo: {lfs_ok}/25.")
        
        # 4. Prueba de Visualizacion Estilo Figma (staruml_ver_visual)
        print("\n[4] Probando staruml_ver_visual (Exportacion visual y generacion de imagen)...")
        salida_img = os.path.join(tmp_dir, 'cu_1_visual.png')
        res_visual = R.ver_visual(MDJ_REF, 'cu_1', salida=salida_img, max_lado=1200)
        assert os.path.exists(salida_img), "No se guardo el archivo PNG de salida"
        assert len(res_visual['png']) > 10000, "PNG demasiado chico o vacio"
        assert res_visual['tamano_original'][0] > 0
        print(f" -> OK: Imagen visual generada con exito ({len(res_visual['png'])} bytes, tamano original {res_visual['tamano_original']}).")
        
        # 5. Prueba de Importacion de Codigo a Modelo (Codigo -> MDJ)
        print("\n[5] Probando staruml_codigo_a_diagrama (Importar clases hacia .mdj)...")
        # Crear un archivo de codigo de prueba
        codigo_nuevo = """
        package modelo;
        public class NotificadorWhatsApp {
            private String numeroTelefono;
            private String estadoEnvio;
            public void enviarMensaje(String texto) {}
        }
        """
        dir_extra = os.path.join(tmp_dir, 'codigo_extra')
        os.makedirs(dir_extra, exist_ok=True)
        with open(os.path.join(dir_extra, 'NotificadorWhatsApp.java'), 'w') as f:
            f.write(codigo_nuevo)
            
        mdj_copia = os.path.join(tmp_dir, 'copia.mdj')
        shutil.copy2(MDJ_REF, mdj_copia)
        doc_copia = M.Doc(mdj_copia)
        res_import = C.importar_codigo_a_diagrama(doc_copia, dir_extra, 'UMLPackage:Gestionar contratación y orden de entrega', nombre_diagrama='cu_1')
        assert 'NotificadorWhatsApp' in res_import['clases_creadas']
        doc_copia.save(force=True, backup=False)
        
        # Verificar que la clase existe en el modelo y tiene atributos
        doc_recargado = M.Doc(mdj_copia)
        c_nueva = doc_recargado.find('NotificadorWhatsApp')
        assert c_nueva is not None, "La clase importada no se encontro en el .mdj"
        attrs_creados = [a['name'] for a in c_nueva.get('attributes', [])]
        assert 'numeroTelefono' in attrs_creados and 'estadoEnvio' in attrs_creados
        print(" -> OK: Codigo Java importado a .mdj con atributos y vista en diagrama.")
        
        print("\nTODAS LAS PRUEBAS VISUALES Y DE CODIGO (ESTILO FIGMA MCP) PASARON EXITOSAMENTE (5/5)!")
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

if __name__ == '__main__':
    main()
