# CLI de StarUML de prueba, con la misma forma que el real:
#   staruml image <mdj> -f svg -s <selector> -o <plantilla>   (un archivo por diagrama)
#   staruml pdf <mdj> -s <selector> -o <archivo.pdf>           (un PDF con una pagina por diagrama)
# Selectores: @Diagram (todos), @UMLDiagram (los de UML), @Tipo, y cualquiera de ellos con [atributo=valor]
# (p. ej. [name=cu_1] o [documentation=marca]); como en el real, un valor con '.', '@', '[', ']', '=' o '::' no
# encuentra nada y se le quitan los espacios de las orillas. En la plantilla de salida entiende <%=element.atributo%>
# y <%=element.atributo.replace(new RegExp('...', 'g'), function (c) { return '...' + c.charCodeAt(0).toString(16)
# + '...' })%>. Cada SVG lleva el nombre y el id del diagrama, asi las pruebas pueden verificar que se exporto el
# correcto. STARUML_FALSO_DORMIR simula un cuelgue.
import json
import os
import re
import sys
import time

_REEMPLAZO = re.compile(r"element\.(\w+)\.replace\(new RegExp\('((?:[^'\\]|\\.)*)', 'g'\), function \(c\) \{ "
                        r"return '([^']*)' \+ c\.charCodeAt\(0\)\.toString\(16\) \+ '([^']*)' \}\)")


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


def elegir(todos, selector):
    m = re.fullmatch(r'@(\w+)(?:\[(\w+)=(.*)\])?', selector)
    if not m:
        sys.exit(f'Selector no valido: {selector}')
    tipo, attr, valor = m.groups()
    if valor is not None and (re.search(r'[.@\[\]=]', valor) or '::' in valor):
        return []

    def del_tipo(g):
        return tipo == 'Diagram' or (tipo == 'UMLDiagram' and g['_type'].startswith('UML')) or g['_type'] == tipo
    return [g for g in todos if del_tipo(g) and (attr is None or str(g.get(attr, '')) == valor.strip())]


def evaluar(expr, g):
    expr = expr.strip()
    m = re.fullmatch(r'element\.(\w+)', expr)
    if m:
        return str(g.get(m.group(1), ''))
    m = _REEMPLAZO.fullmatch(expr)
    if m:
        attr, patron, antes, despues = m.groups()
        return re.sub(patron, lambda x: antes + format(ord(x.group()), 'x') + despues, str(g.get(attr, '')))
    sys.exit(f'Plantilla que el CLI de prueba no entiende: {expr}')


def svg(g, formato):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" data-id="{g["_id"]}" '
            f'data-formato="{formato}"><rect x="10" y="10" width="300" height="180" fill="#ffffff" stroke="#000000"/>'
            f'<text x="20" y="40" font-size="13px">{g.get("name", "")}</text></svg>')


def pdf(paginas):
    # PDF minimo valido; sin diagramas elegidos el CLI real deja una pagina en blanco
    n = max(1, paginas)
    objetos = ['<< /Type /Catalog /Pages 2 0 R >>',
               '<< /Type /Pages /Kids [' + ' '.join(f'{3 + i} 0 R' for i in range(n)) + f'] /Count {n} >>']
    objetos += ['<< /Type /Page /Parent 2 0 R /MediaBox [0 0 320 200] >>'] * n
    texto = '%PDF-1.4\n' + ''.join(f'{i + 1} 0 obj\n{o}\nendobj\n' for i, o in enumerate(objetos))
    return (texto + 'trailer\n<< /Root 1 0 R >>\n%%EOF\n').encode('ascii')


def main(argv):
    if os.environ.get('STARUML_FALSO_DORMIR'):
        time.sleep(float(os.environ['STARUML_FALSO_DORMIR']))
    comando = argv[0]
    assert comando in ('image', 'pdf'), argv
    mdj = argv[1]
    selector = argv[argv.index('-s') + 1]
    salida = argv[argv.index('-o') + 1]
    with open(mdj, encoding='utf-8') as f:
        d = json.load(f)
    elegidos = elegir(diagramas(d, []), selector)
    if comando == 'pdf':
        os.makedirs(os.path.dirname(salida) or '.', exist_ok=True)
        with open(salida, 'wb') as f:
            f.write(pdf(len(elegidos)))
        print('PDF document was exported')
        return
    formato = argv[argv.index('-f') + 1]
    for g in elegidos:
        destino = re.sub(r'<%=(.*?)%>', lambda m: evaluar(m.group(1), g), salida)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, 'w', encoding='utf-8') as f:
            f.write(svg(g, formato))
    print(f'Total {len(elegidos)} diagrams were exported')


if __name__ == '__main__':
    main(sys.argv[1:])
