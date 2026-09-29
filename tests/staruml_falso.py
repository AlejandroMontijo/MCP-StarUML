# CLI de StarUML de prueba: "staruml image <mdj> -f svg -s <selector> -o <patron>".
# Entiende los selectores @UMLDiagram y @Tipo[name=Nombre] y escribe un SVG por diagrama con su nombre e id,
# asi las pruebas pueden verificar que se exporto el diagrama correcto. STARUML_FALSO_DORMIR simula un cuelgue.
import json
import os
import re
import sys
import time


def diagramas(o, res):
    if isinstance(o, dict):
        if 'Diagram' in o.get('_type', ''):
            res.append(o)
        for v in o.values():
            diagramas(v, res)
    elif isinstance(o, list):
        for v in o:
            diagramas(v, res)
    return res


def main(argv):
    if os.environ.get('STARUML_FALSO_DORMIR'):
        time.sleep(float(os.environ['STARUML_FALSO_DORMIR']))
    assert argv[0] == 'image', argv
    mdj = argv[1]
    formato = argv[argv.index('-f') + 1]
    selector = argv[argv.index('-s') + 1]
    patron = argv[argv.index('-o') + 1]
    with open(mdj, encoding='utf-8') as f:
        d = json.load(f)
    todos = diagramas(d, [])
    m = re.fullmatch(r'@(\w+)(?:\[name=(.*)\])?', selector)
    tipo, nombre = m.group(1), m.group(2)
    elegidos = [g for g in todos if (tipo == 'UMLDiagram' or g['_type'] == tipo) and (nombre is None or g.get('name') == nombre)]
    for g in elegidos:
        salida = patron.replace('<%=element.name%>', g.get('name', ''))
        os.makedirs(os.path.dirname(salida), exist_ok=True)
        with open(salida, 'w', encoding='utf-8') as f:
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" data-id="{g["_id"]}" data-formato="{formato}">'
                    f'<rect x="10" y="10" width="300" height="180" fill="#ffffff" stroke="#000000"/>'
                    f'<text x="20" y="40" font-size="13px">{g.get("name", "")}</text></svg>')
    print(f'Total {len(elegidos)} diagrams were exported')


if __name__ == '__main__':
    main(sys.argv[1:])
