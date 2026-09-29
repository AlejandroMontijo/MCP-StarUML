# Deteccion de StarUML abierto (macOS, Linux, Windows) y busqueda de ejecutables.
import os
import shutil
import stat
import subprocess
import sys
import time

import pytest

from apoyo import M, ok, tool


@pytest.mark.parametrize('cmd,es_gui', [
    ('/Applications/StarUML.app/Contents/MacOS/StarUML', True),
    ('/Applications/StarUML.app/Contents/MacOS/StarUML -psn_0_123', True),
    ('/Applications/StarUML.app/Contents/MacOS/StarUML image /x/m.mdj -f svg -s @UMLDiagram', False),
    ('/Applications/StarUML.app/Contents/Frameworks/StarUML Helper (Renderer).app/Contents/MacOS/StarUML Helper (Renderer) --type=renderer', False),
    ('/opt/StarUML/staruml', True),
    ('/opt/StarUML/staruml /home/u/modelo.mdj', True),
    ('/opt/StarUML/staruml --no-sandbox', True),
    ('/opt/StarUML/staruml --type=zygote --no-zygote-sandbox', False),
    ('/opt/StarUML/chrome_crashpad_handler --monitor-self', False),
    ('/home/u/Descargas/StarUML-6.2.2.AppImage', True),
    ('/tmp/.mount_StarUMx1/staruml', True),
    ('/usr/bin/staruml ejs plantilla.ejs', False),
    ('python3 /home/u/MCP-StarUML/server.py', False),
    ('vim /home/u/staruml/notas.txt', False),
])
def test_reconoce_la_aplicacion_de_staruml(cmd, es_gui):
    assert M.es_gui_staruml(cmd) is es_gui


@pytest.mark.deteccion_real
def test_sin_ps_ni_tasklist_bloquea_la_escritura(modelo, monkeypatch):
    def sin_programa(*a, **k):
        raise FileNotFoundError('ps')
    monkeypatch.setattr(M.subprocess, 'run', sin_programa)
    assert M.staruml_gui_abierto() is None
    assert 'No se pudo saber' in tool('mdj_documentacion', archivo=modelo, elemento='Cuenta', texto='x')['error']
    ok(tool('mdj_documentacion', archivo=modelo, elemento='Cuenta', texto='x', forzar=True))


@pytest.mark.deteccion_real
@pytest.mark.skipif(os.name == 'nt' or not shutil.which('ps'), reason='usa ps y un proceso con ruta de Linux')
def test_detecta_staruml_abierto_en_linux(modelo, tmp_path):
    # ruta larga a proposito: ps no debe recortarla
    falso = tmp_path / ('instalacion_con_un_nombre_de_carpeta_bastante_largo_' * 2) / 'opt' / 'StarUML' / 'staruml'
    falso.parent.mkdir(parents=True)
    shutil.copy(shutil.which('sleep'), falso)
    p = subprocess.Popen([str(falso), '30'])
    try:
        time.sleep(0.3)
        assert M.staruml_gui_abierto() is True
        assert 'StarUML esta abierto' in tool('mdj_documentacion', archivo=modelo, elemento='Cuenta', texto='x')['error']
    finally:
        p.kill()
        p.wait()
    assert M.staruml_gui_abierto() is False


def test_busca_staruml_y_chrome_en_el_path(tmp_path, monkeypatch):
    for nombre in ('staruml', 'chromium'):
        f = tmp_path / nombre
        f.write_text('#!/bin/sh\n')
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    monkeypatch.delenv('STARUML_MCP_STARUML_BIN', raising=False)
    monkeypatch.delenv('STARUML_MCP_CHROME_BIN', raising=False)
    monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ.get('PATH', ''))
    monkeypatch.setattr(os.path, 'exists', lambda p, _e=os.path.exists: _e(p) and not p.startswith(('/Applications', '/opt/StarUML', '/usr/lib/staruml')))
    if os.name != 'nt':
        assert M.staruml_cli() == str(tmp_path / 'staruml')
        assert M.chrome_bin() in (str(tmp_path / 'chromium'), shutil.which('google-chrome'), shutil.which('chromium'))


def test_variable_de_entorno_manda(tmp_path, monkeypatch):
    monkeypatch.setenv('STARUML_MCP_STARUML_BIN', sys.executable)
    assert M.staruml_cli() == sys.executable
    monkeypatch.setenv('STARUML_MCP_STARUML_BIN', str(tmp_path / 'no_existe'))
    assert M.staruml_cli() is None
