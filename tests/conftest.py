import glob
import os
import shutil
import stat
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoyo  # noqa: E402
from apoyo import M  # noqa: E402


@pytest.fixture(autouse=True)
def entorno_aislado(tmp_path, monkeypatch, request):
    """Respaldos en una carpeta temporal y, salvo en las pruebas de deteccion, StarUML 'cerrado' (quien corre la
    suite puede tener StarUML abierto y eso no debe bloquear las escrituras de prueba)."""
    respaldos = tmp_path / 'respaldos'
    monkeypatch.setenv('STARUML_MCP_BACKUP_DIR', str(respaldos))
    monkeypatch.setattr(M, 'BACKUP_DIR', str(respaldos))
    monkeypatch.delenv('STARUML_MCP_ALLOWED_DIRS', raising=False)
    if 'deteccion_real' not in request.keywords:
        monkeypatch.setattr(M, 'staruml_gui_abierto', lambda: False)
    yield


@pytest.fixture(scope='session')
def _modelo_base(tmp_path_factory):
    import pytest as _p
    mp = _p.MonkeyPatch()
    carpeta = tmp_path_factory.mktemp('base')
    mp.setattr(M, 'BACKUP_DIR', str(carpeta / 'respaldos'))
    mp.setattr(M, 'staruml_gui_abierto', lambda: False)
    try:
        vacio = apoyo.guardar_json(apoyo.proyecto_vacio(), str(carpeta / 'vacio.mdj'))
        poblado = apoyo.poblar(apoyo.guardar_json(apoyo.proyecto_vacio(), str(carpeta / 'modelo.mdj')))
        dominio = apoyo.modelo_dominio(str(carpeta / 'dominio.mdj'))
    finally:
        mp.undo()
    return {'vacio': vacio, 'modelo': poblado, 'dominio': dominio}


def _copia(origen, tmp_path, nombre):
    destino = tmp_path / nombre
    shutil.copy(origen, destino)
    return str(destino)


@pytest.fixture
def vacio(_modelo_base, tmp_path):
    """Proyecto sin clases: diagrama de clases sin ownedViews y secuencia solo con su marco."""
    return _copia(_modelo_base['vacio'], tmp_path, 'vacio.mdj')


@pytest.fixture
def modelo(_modelo_base, tmp_path):
    """Caso de uso de ejemplo completo (clases, vistas, asociaciones, nota y secuencia)."""
    return _copia(_modelo_base['modelo'], tmp_path, 'modelo.mdj')


@pytest.fixture
def dominio(_modelo_base, tmp_path):
    """Diagrama de clases de dominio con atributos tipados, metodo, generalizacion y asociaciones."""
    return _copia(_modelo_base['dominio'], tmp_path, 'dominio.mdj')


@pytest.fixture
def real(tmp_path):
    """Copia del .mdj real del caso de uso (pruebas/*.mdj o STARUML_MCP_MODELO_REAL). Se omite si no existe."""
    p = apoyo.modelo_real()
    if not p:
        pytest.skip('sin modelo real: copia tu .mdj a pruebas/ o define STARUML_MCP_MODELO_REAL')
    return _copia(p, tmp_path, 'real.mdj')


@pytest.fixture
def chrome(monkeypatch):
    """Chrome/Chromium para rasterizar. Se omite la prueba si no hay ninguno."""
    ruta = M.chrome_bin() or next(iter(sorted(glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome'))), None)
    if not ruta:
        pytest.skip('sin Chrome/Chromium')
    monkeypatch.setenv('STARUML_MCP_CHROME_BIN', ruta)
    return ruta


@pytest.fixture
def staruml_falso(tmp_path, monkeypatch):
    """Un CLI de StarUML de prueba (tests/staruml_falso.py) que exporta un SVG por diagrama seleccionado."""
    if os.name == 'nt':
        pytest.skip('el CLI de prueba es un script de shell')
    envoltorio = tmp_path / 'staruml'
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'staruml_falso.py')
    envoltorio.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    envoltorio.chmod(envoltorio.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv('STARUML_MCP_STARUML_BIN', str(envoltorio))
    return str(envoltorio)


def pytest_configure(config):
    config.addinivalue_line('markers', 'deteccion_real: usa la deteccion real de "StarUML abierto" (sin simularla)')
