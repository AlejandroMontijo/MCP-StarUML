# Contexto del Proyecto: MCP StarUML (Guía para Claude Code)

Este documento proporciona el contexto completo del repositorio, arquitectura, historial de cambios recientes, decisiones de diseño y convenciones para sesiones de trabajo con Claude Code.

---

## 1. Visión General del Proyecto

**MCP StarUML** es un servidor Model Context Protocol (**MCP**) autónomo desarrollado en Python 3.9+ (sin frameworks pesados, basado en JSON-RPC 2.0 por `stdio`) que permite a asistentes de IA interactuar con proyectos StarUML (`.mdj`) sin abrir la interfaz gráfica:
- **Inspección visual:** Exporta diagramas a imágenes PNG de alta fidelidad y las entrega directamente en el protocolo MCP (`staruml_ver_visual`).
- **Sincronización con código:** Compara diagramas de clases y de secuencia contra código fuente (**Java, Python, TypeScript/JavaScript y C#**), calculando porcentaje de alineación y reportando discrepancias (`staruml_comparar_codigo`).
- **Ingeniería inversa y generación:** Genera esqueletos de código limpios a partir del modelo (`staruml_diagrama_a_codigo`) e importa código fuente a diagramas `.mdj` (`staruml_codigo_a_diagrama`).
- **Edición segura:** Respaldos automáticos verificados byte a byte, prevención de sobreescritura si StarUML tiene el archivo abierto, y validación estricta de reglas OOSE (Boundary-Control-Entity).

---

## 2. Estructura de Archivos del Repositorio

El repositorio Git en `main` contiene exclusivamente el código fuente oficial y agnóstico:

```text
MCP StarUML/
├── server.py              # Servidor MCP central (30 herramientas registradas)
├── staruml_mdj.py         # Motor de lectura, manipulación JSON, validación y edición segura
├── staruml_render.py      # Exportación CLI de StarUML, revisión de SVG y recorte a PNG (Chrome)
├── staruml_compare.py     # Comparador de diagramas vs código y generador bidireccional
├── reglas.md              # Convenciones de modelado, OOSE, secuencias y arquitectura
├── README.md              # Documentación genérica y profesional para open source
├── CLAUDE.md              # Este archivo de memoria y contexto para Claude Code
└── .gitignore             # Configuración de exclusión (ignora pruebas/, scratch/, respaldos/)
```

> **Nota sobre `pruebas/`:**
> La carpeta `pruebas/` existe **únicamente en local** y está estrictamente desindexada e ignorada en Git. Contiene los scripts de prueba (`probar_todo.py`, `probar_visual_y_codigo.py`, `probar_servidor.py`, `probar_reconstruccion_completa.py`) y el modelo reconstruido `proyecto_reconstruido.mdj`. **NUNCA debe ser comiteada ni pusheada al repositorio remoto.**

---

## 3. Resumen de lo Realizado en la Sesión Anterior

1. **Reconstrucción y Verificación Completa del Modelo:**
   - Se reconstruyó desde la plantilla inicial el caso de uso *"Gestionar contratación y orden de entrega"*.
   - **Diagrama de Clases (`cu_1`):** 27 clases/actores (6 boundary, 1 control, 18 entity, 2 actores), 50 asociaciones, 92 atributos y 6 notas de especificación.
   - **Diagrama de Secuencia Básico (`cu_1_FB`):** 25 lifelines y 66 mensajes cubriendo los flujos F1 a F5.
   - Se configuró `defaultDiagram: true` en `cu_1_FB` para que StarUML lo abra directamente.
   - Puntuación de comparación contra el modelo de referencia: **20/20 (100.0% match)** con **0 violaciones OOSE**.

2. **Generación de los Flujos Alternativos (`cu_1_FA`):**
   - Se creó el diagrama de secuencia para los flujos alternativos en la interacción `flujos alternativos` del `.mdj`:
     - **FA1:** Búsqueda de cliente no registrado y captura de datos.
     - **FA2:** Evaluación técnica negativa y selección de equipo alternativo (CAT 336).
     - **FA3:** Unidad no disponible en periodo y selección de unidad/fechas alternativas.
     - **FA4:** Cancelación de la solicitud antes de formalizar.
     - **FA5:** Rechazo de la propuesta final en F5 (sin generación de contrato ni orden de entrega).
   - Métricas de `cu_1_FA`: **14 lifelines**, **40 mensajes**, activaciones anidadas correctas y 0 errores OOSE.

3. **Nuevas Capacidades de Inspección Visual y Sincronización:**
   - Creación de `staruml_compare.py`: parser políglota (Java, Python, TypeScript, C#) para comparar entidades, métodos, atributos, multiplicidades de asociaciones y flujo de llamadas en secuencias.
   - Creación de `staruml_ver_visual`: genera y entrega imágenes PNG de alta resolución en tiempo real vía MCP.
   - Creación de herramientas de generación de esqueletos e importación de código hacia el `.mdj`.

4. **Reglas de Git y Limpieza:**
   - **Prohibido mencionar "Figma"** en los commits, código o documentación.
   - **Prohibido subir la carpeta `pruebas/`** al repositorio remoto (ya fue desindexada con `git rm -r --cached`).
   - El `README.md` y `reglas.md` fueron reescritos para ser **100% genéricos y agnósticos** de cualquier proyecto o curso particular.

---

## 4. Convenciones y Reglas Inquebrantables

1. **Reglas de Git:**
   - Mensajes de commit claros, concisos y sin mencionar herramientas externas no relacionadas.
   - Mantener `pruebas/` fuera del control de versiones.
2. **Seguridad en `.mdj`:**
   - Antes de escribir en un `.mdj`, verificar que StarUML no esté corriendo con ese archivo abierto para evitar que sobreescriba cambios (usar `forzar: true` solo si se sabe seguro).
   - Siempre respaldar antes de guardar (`doc.save(backup=True)`).
   - Indentación por tabuladores y `ensure_ascii=False` para mantener paridad byte a byte con StarUML.
3. **Reglas de Robustez OOSE (Jacobson):**
   - Exactamente **1 clase control** por caso de uso.
   - Actores solo interactúan con Boundary.
   - Boundary solo interactúa con Actores y Control (nunca boundary con boundary ni boundary con entity).
   - Control interactúa con Boundary y Entity.
   - Entity solo interactúa con Entity si existe asociación explícita.
   - Boundary y Control **sin atributos ni métodos** en fase de análisis.

---

## 5. Comandos de Verificación Local

Para verificar el correcto funcionamiento del servidor y herramientas en local:

```bash
# 1. Probar suite completa del servidor (41 pruebas de integridad, OOSE, lectura, escritura y CLI)
python3 pruebas/probar_todo.py pruebas/proyecto_reconstruido.mdj cu_1 cu_1_FB

# 2. Probar inspección visual y comparación con código Java/Python/TS
python3 pruebas/probar_visual_y_codigo.py

# 3. Probar protocolo MCP por stdio de punta a punta
python3 pruebas/probar_servidor.py pruebas/proyecto_reconstruido.mdj cu_1 cu_1_FB
```
