# Genera con el StarUML instalado un .mdj de referencia que tiene, por cada diagrama, cada simbolo de su paleta.
# Lo dibuja el propio StarUML (extension herramientas/staruml_extension/mcp-referencia, comando mcp:dibujar-todo,
# corrida con 'StarUML exec'), asi las vistas quedan exactamente como StarUML las crea. De ese archivo
# herramientas/extraer_plantillas.py saca plantillas_vistas.json.
#
# Uso: python herramientas/generar_referencia.py [carpeta_salida]   (por defecto pruebas/referencia, fuera de git)
# Necesita StarUML instalado y cerrado. La extension se copia a la carpeta de extensiones de usuario de StarUML;
# con --quitar-extension se borra al terminar.
import json
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, AQUI)

import staruml_mdj as M  # noqa: E402
import extraer_metamodelo as X  # noqa: E402

EXTENSION = os.path.join(AQUI, 'staruml_extension', 'mcp-referencia')

SEMILLA = {
    '_type': 'Project', '_id': 'AAAAAAFF+h6SjaM2Hec=', 'name': 'Referencia',
    'ownedElements': [{'_type': 'UMLModel', '_id': 'AAAAAAFF+qBWK6M3Z8Y=', '_parent': {'$ref': 'AAAAAAFF+h6SjaM2Hec='},
                       'name': 'Model'}],
}


def carpeta_extensiones():
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA') or os.path.expanduser('~\\AppData\\Roaming')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
    return os.path.join(base, 'StarUML', 'extensions', 'user')


def instalar_extension():
    destino = os.path.join(carpeta_extensiones(), 'mcp-referencia')
    if os.path.isdir(destino):
        shutil.rmtree(destino)
    shutil.copytree(EXTENSION, destino)
    return destino


def correr(cmd, limite):
    """Corre StarUML y, si se pasa del limite, termina solo su arbol de procesos (no otros StarUML abiertos)."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = p.communicate(timeout=limite)
    except subprocess.TimeoutExpired:
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/PID', str(p.pid), '/T', '/F'], capture_output=True)
        else:
            p.kill()
        out, err = p.communicate()
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def main(argv):
    quitar = '--quitar-extension' in argv
    args = [a for a in argv[1:] if not a.startswith('--')]
    salida = os.path.abspath(args[0] if args else os.path.join(RAIZ, 'pruebas', 'referencia'))
    cli = M.staruml_cli()
    if not cli:
        raise SystemExit('No encuentro StarUML (define STARUML_MCP_STARUML_BIN)')
    if M.staruml_gui_abierto():
        raise SystemExit('Cierra StarUML antes de generar la referencia')
    os.makedirs(salida, exist_ok=True)
    _, paletas, version = X.leer_staruml(X.ruta_asar(cli))
    plan = {'salida': os.path.join(salida, 'referencia.mdj'), 'reporte': os.path.join(salida, 'reporte.json'),
            'paletas': X.compactar_paletas(paletas)}
    semilla = os.path.join(salida, 'semilla.mdj')
    with open(semilla, 'w', encoding='utf-8') as f:
        json.dump(SEMILLA, f, ensure_ascii=False, indent='\t')
    ruta_plan = os.path.join(salida, 'plan.json')
    with open(ruta_plan, 'w', encoding='utf-8') as f:
        json.dump(plan, f, ensure_ascii=False, indent='\t')
    for p in (plan['salida'], plan['reporte']):
        if os.path.exists(p):
            os.remove(p)
    ext = instalar_extension()
    try:
        # el plan se lee de la carpeta de semilla.mdj: StarUML 6.3.1 se cae si 'exec' recibe -a
        r = correr([cli, 'exec', semilla, '-c', 'mcp:dibujar-todo'], 1800)
    finally:
        if quitar:
            shutil.rmtree(ext, ignore_errors=True)
    if not os.path.exists(plan['reporte']):
        raise SystemExit(f'StarUML no genero el reporte.\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}')
    with open(plan['reporte'], encoding='utf-8') as f:
        reporte = json.load(f)
    fallas = [e for e in reporte if not e.get('ok')]
    print(f'StarUML {version}: {len(reporte) - len(fallas)}/{len(reporte)} simbolos dibujados -> {plan["salida"]}')
    for e in fallas:
        print(f'  FALLA {e["diagrama"]}: {e.get("label", "")} ({e.get("id", "")}): {e.get("error")}')
    return 0 if os.path.exists(plan['salida']) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
