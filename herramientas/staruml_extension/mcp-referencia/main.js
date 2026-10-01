// Extension de apoyo para MCP StarUML. Registra el comando 'mcp:dibujar-todo', pensado para correr sin ventana:
//   StarUML exec semilla.mdj -c mcp:dibujar-todo
// Lee plan.json de la misma carpeta que semilla.mdj:
// plan.json = {"salida": "referencia.mdj", "reporte": "reporte.json", "paletas": {diagrama: [item de paleta]}}
// Por cada diagrama crea un paquete con el diagrama y dibuja cada simbolo de su paleta con la misma fabrica que usa
// la paleta de StarUML (factory:create-model-and-view o el comando propio del simbolo). Las lineas se prueban entre
// las cajas ya dibujadas hasta que StarUML acepta una pareja. Al final guarda el proyecto y un reporte por simbolo.
const fs = require('fs')

let bitacora = null

function log (msg) {
  try {
    require('electron').ipcRenderer.send('console-log', '[mcp] ' + msg)
  } catch (err) {
    // sin ipc (pruebas): solo archivo
  }
  if (bitacora) fs.appendFileSync(bitacora, new Date().toISOString().slice(11, 19) + ' ' + msg + '\n', 'utf8')
}

const ANCHO = 150
const ALTO = 90
const COLUMNAS = 6
const PASADAS = 6
const MAX_PAREJAS = 3000

// diagramas que StarUML solo admite dentro de cierto elemento (no de un paquete)
const DUENO_DE = {
  SysMLInternalBlockDiagram: 'SysMLBlock',
  SysMLParametricDiagram: 'SysMLBlock'
}

function esLinea (v) {
  return v instanceof type.EdgeView
}

function idsDe (diagrama) {
  // todas las vistas del diagrama, incluidas las anidadas (subViews y containedViews)
  const vistos = new Set()
  const pila = diagrama.ownedViews.slice()
  while (pila.length) {
    const v = pila.pop()
    if (!v || vistos.has(v._id)) continue
    vistos.add(v._id)
    for (const h of (v.subViews || []).concat(v.containedViews || [])) pila.push(h)
  }
  return vistos
}

function candidatos (diagrama) {
  // vistas principales (con modelo) a las que se puede anclar o conectar algo; las etiquetas no cuentan.
  // Una por tipo de vista y de modelo: basta para encontrar una pareja valida y mantiene el costo bajo.
  const vistos = new Map()
  // las lineas de una vista a si misma van al final: un mensaje sobre un conector se prueba primero en uno normal
  const auto = (v) => v instanceof type.EdgeView && v.tail && v.tail === v.head ? 1 : 0
  return diagrama.ownedViews.slice().sort((a, b) => auto(a) - auto(b)).filter(v => {
    if (!v || !v.model || v instanceof type.LabelView || v instanceof type.EdgeLabelView ||
        /CompartmentView$/.test(v.getClassName())) return false
    // hasta dos por tipo, para que las lineas unan dos vistas distintas del mismo tipo (include, conector...)
    const clave = v.getClassName() + '|' + v.model.getClassName()
    const n = vistos.get(clave) || 0
    if (n >= 2) return false
    vistos.set(clave, n + 1)
    return true
  })
}

function centro (v) {
  if (esLinea(v)) {
    const ps = (v.points && v.points.points) || []
    if (ps.length) {
      const a = ps[0]
      const b = ps[ps.length - 1]
      return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
    }
    return { x: 0, y: 0 }
  }
  return { x: v.left + v.width / 2, y: v.top + v.height / 2 }
}

// ids de los objetos que insertaron las operaciones (cada arg es el elemento serializado, con sus hijos)
let operaciones = []
// ids que ya existian: un arg puede traer serializado un elemento que ya estaba (la colaboracion de una lifeline...)
let conocidos = new Set()

function actualizarConocidos () {
  conocidos = new Set(Object.keys(app.repository.getIdMap()))
}

function idsInsertados (ops) {
  const ids = []
  const walk = (x) => {
    if (Array.isArray(x)) {
      x.forEach(walk)
    } else if (x && typeof x === 'object') {
      if (typeof x._id === 'string') ids.push(x._id)
      for (const k of Object.keys(x)) {
        if (k !== '_parent') walk(x[k])
      }
    }
  }
  for (const op of ops) {
    for (const o of op.ops || []) walk(o.arg)
  }
  return [...new Set(ids)].filter(id => app.repository.get(id))
}

function intentar (editor, diagrama, item, o) {
  // corre el comando de la paleta; cuenta como dibujado si aparecieron vistas nuevas en el diagrama.
  // Se anotan los ids creados (vistas y modelos) para que extraer_plantillas.py saque el simbolo exacto.
  const antes = idsDe(diagrama)
  operaciones = []
  Object.assign(o, { id: item.id, editor: editor, diagram: diagrama, parent: diagrama._parent }, item.arg || {})
  let comando = item.command || 'factory:create-model-and-view'
  if (comando === 'uml:create-model-and-view.frame') {
    // el comando de la paleta pregunta con un dialogo que elemento representa el marco: aqui, el dueno del diagrama
    comando = 'factory:create-model-and-view'
    o.id = 'UMLFrame'
    o.viewInitializer = (v) => { v.model = diagrama._parent }
  }
  try {
    const r = app.commands.execute(comando, o)
    const nuevas = [...idsDe(diagrama)].filter(id => !antes.has(id))
    if (nuevas.length) {
      const creados = idsInsertados(operaciones).filter(id => !conocidos.has(id))
      actualizarConocidos()
      const principal = r && r._id ? r : app.repository.get(nuevas.find(id => {
        const v = app.repository.get(id)
        return v && diagrama.ownedViews.includes(v)
      }) || nuevas[0])
      return {
        ok: true,
        vista: principal && principal.getClassName ? principal.getClassName() : null,
        vista_id: principal ? principal._id : null,
        vistas_nuevas: creados.filter(id => app.repository.get(id) instanceof type.View),
        modelos_nuevos: creados.filter(id => !(app.repository.get(id) instanceof type.View)),
        cola_id: o.tailView ? o.tailView._id : null,
        cabeza_id: o.headView ? o.headView._id : null
      }
    }
    return { ok: false, error: 'el comando no creo vistas' }
  } catch (err) {
    return { ok: false, error: String(err && err.message ? err.message : err) }
  }
}

function dibujarCaja (editor, diagrama, item, i) {
  const x1 = 40 + (i % COLUMNAS) * (ANCHO + 60)
  const y1 = 60 + Math.floor(i / COLUMNAS) * (ALTO + 90)
  // un clic (sin arrastrar), como en la paleta: cada vista toma el tamano por omision que le da StarUML
  let r = intentar(editor, diagrama, item, { x1: x1, y1: y1, x2: x1, y2: y1 })
  if (r.ok) return r
  // dentro o encima de otra vista (puertos, particiones, regiones, pines, lifelines de tiempos, restricciones...)
  for (const c of candidatos(diagrama)) {
    const m = centro(c)
    let caja
    if (esLinea(c)) {
      caja = { x1: m.x - 10, y1: m.y - 10, x2: m.x + 10, y2: m.y + 10 }
    } else {
      caja = { x1: m.x, y1: m.y, x2: m.x, y2: m.y }
    }
    const intento = intentar(editor, diagrama, item, Object.assign(caja,
      { tailView: c, headView: c, tailModel: c.model, headModel: c.model }))
    if (intento.ok) return Object.assign(intento, { sobre: c.getClassName() })
    r = intento
  }
  return r
}

function dibujarLinea (editor, diagrama, item) {
  const vs = candidatos(diagrama)
  let r = { ok: false, error: 'no hay vistas que conectar' }
  // primero parejas distintas; una vista consigo misma solo al final (auto-mensaje, auto-transicion). Una contencion
  // de un elemento en si mismo lo saca del arbol del proyecto y StarUML ya no lo guarda.
  const parejas = []
  for (const cola of vs) {
    for (const cabeza of vs) {
      if (cola !== cabeza) parejas.push([cola, cabeza])
    }
  }
  for (const v of vs) parejas.push([v, v])
  for (const [cola, cabeza] of parejas.slice(0, MAX_PAREJAS)) {
    const a = centro(cola)
    const b = centro(cabeza)
    const intento = intentar(editor, diagrama, item, {
      x1: a.x, y1: a.y, x2: b.x, y2: b.y,
      tailView: cola, headView: cabeza, tailModel: cola.model, headModel: cabeza.model
    })
    if (intento.ok) return Object.assign(intento, { cola: cola.getClassName(), cabeza: cabeza.getClassName() })
    r = intento
  }
  return r
}

function crearDiagrama (tipo, modelo, reporte) {
  const paquete = app.factory.createModel({ id: 'UMLPackage', parent: modelo })
  paquete.name = 'Ref_' + tipo
  const padres = []
  if (DUENO_DE[tipo]) {
    const dueno = app.factory.createModel({ id: DUENO_DE[tipo], parent: paquete })
    if (dueno) {
      dueno.name = 'Dueno_' + tipo
      padres.push(dueno)
    }
  }
  actualizarConocidos()
  padres.push(paquete, modelo, app.project.getProject())
  for (const padre of padres) {
    operaciones = []
    try {
      const d = app.factory.createDiagram({ id: tipo, parent: padre })
      if (d) {
        d.name = tipo
        // lo que StarUML crea junto con el diagrama (colaboracion e interaccion, maquina de estados, marco...)
        const creados = idsInsertados(operaciones).filter(id => !conocidos.has(id))
        actualizarConocidos()
        reporte.push({ diagrama: tipo, forma: 'diagrama', ok: true, vista: tipo, vista_id: d._id, padre_id: padre._id,
          padre_tipo: padre.getClassName(), vistas_nuevas: creados.filter(id => app.repository.get(id) instanceof type.View),
          modelos_nuevos: creados.filter(id => !(app.repository.get(id) instanceof type.View)) })
        return d
      }
    } catch (err) {
      // se intenta con el siguiente contenedor
    }
  }
  return null
}

function dibujarTodo (rutaPlan) {
  bitacora = rutaPlan.replace(/\.json$/, '') + '.log'
  fs.writeFileSync(bitacora, '', 'utf8')
  const plan = JSON.parse(fs.readFileSync(rutaPlan, 'utf8'))
  log('plan con ' + Object.keys(plan.paletas).length + ' diagramas')
  const reporte = []
  // sin ventana nadie contesta los dialogos: los de confirmacion dicen que si y los avisos se anotan
  app.dialogs.showConfirmDialog = (msg) => { log('  dialogo: ' + msg); return 'ok' }
  for (const f of ['showAlertDialog', 'showInfoDialog', 'showErrorDialog']) {
    app.dialogs[f] = (msg) => { log('  dialogo: ' + msg) }
  }
  // robustez y estereotipos necesitan el perfil estandar de UML (StarUML lo pide con un dialogo)
  app.commands.execute('uml:apply-profile.uml-standard')
  const modelo = app.project.getProject().ownedElements.find(e => e instanceof type.UMLModel)
  for (const tipo of Object.keys(plan.paletas)) {
    const diagrama = crearDiagrama(tipo, modelo, reporte)
    if (!diagrama) {
      reporte.push({ diagrama: tipo, ok: false, error: 'no se pudo crear el diagrama' })
      continue
    }
    log('diagrama ' + tipo + ' en ' + diagrama._parent.getClassName())
    app.diagrams.setCurrentDiagram(diagrama)
    const editor = app.diagrams.getEditor()
    // cajas antes que lineas; lo que falla se reintenta en otra pasada porque puede depender de algo dibujado despues
    // (lifeline de tiempos dentro de un marco, estado dentro de la lifeline, mensaje entre segmentos...)
    let pendientes = plan.paletas[tipo].filter(it => it.forma !== 'line').concat(plan.paletas[tipo].filter(it => it.forma === 'line'))
    const ultimo = {}
    const visto = {}
    let n = 0

    for (let pasada = 0; pasada < PASADAS && pendientes.length; pasada++) {
      const siguen = []
      for (const item of pendientes) {
        // se reintenta solo si desde el ultimo intento aparecieron vistas nuevas a las que anclarse
        const firma = candidatos(diagrama).map(v => v._id).join(',')
        const clave = item.label + '|' + item.id
        if (visto[clave] === firma) {
          siguen.push(item)
          continue
        }
        visto[clave] = firma
        log('  ' + pasada + ' ' + clave)
        const r = item.forma === 'line' ? dibujarLinea(editor, diagrama, item) : dibujarCaja(editor, diagrama, item, n++)
        if (r.ok) {
          reporte.push(Object.assign({ diagrama: tipo, label: item.label, id: item.id, forma: item.forma, pasada: pasada }, r))
        } else {
          ultimo[clave] = r
          siguen.push(item)
        }
      }
      if (siguen.length === pendientes.length) break
      pendientes = siguen
      log('  pasada ' + pasada + ': faltan ' + pendientes.length)
    }

    for (const item of pendientes) {
      reporte.push(Object.assign({ diagrama: tipo, label: item.label, id: item.id, forma: item.forma },
        ultimo[item.label + '|' + item.id]))
    }
    // una segunda copia de cada caja: asi las lineas se prueban entre dos vistas distintas del mismo tipo
    // (las copias no son plantillas)
    const cajas = plan.paletas[tipo].filter(it => it.forma !== 'line')
    for (const item of cajas) {
      const r = dibujarCaja(editor, diagrama, item, n++)
      if (r.ok) reporte.push(Object.assign({ diagrama: tipo, label: item.label, id: item.id, forma: item.forma, copia: true }, r))
    }
    // una linea es "consigo misma" si une una vista con ella misma o si se engancho a una linea asi
    const autoVista = (id) => {
      const v = id && app.repository.get(id)
      return !!(v && v instanceof type.EdgeView && v.tail && v.tail === v.head)
    }
    const auto = (r) => r.cola_id === r.cabeza_id || autoVista(r.cola_id) || autoVista(r.cabeza_id)
    const lineas = reporte.filter(e => e.diagrama === tipo && e.forma === 'line' && !e.copia)
    for (const e of lineas) {
      // se vuelve a dibujar cada linea ya con las copias, y si ahora une dos vistas distintas, esa es la plantilla
      if (e.ok && !auto(e)) continue
      const item = plan.paletas[tipo].find(it => it.label === e.label && it.id === e.id)
      const r = dibujarLinea(editor, diagrama, item)
      if (r.ok && !auto(r)) {
        e.copia = true
        reporte.push(Object.assign({ diagrama: tipo, label: item.label, id: item.id, forma: item.forma, segunda: true }, r))
      }
    }
  }
  app.project.save(plan.salida)
  fs.writeFileSync(plan.reporte, JSON.stringify(reporte, null, '\t'), 'utf8')
  log('listo')
}

function init () {
  app.repository.on('operationExecuted', (op) => { operaciones.push(op) })
  app.commands.register('mcp:dibujar-todo', (arg) => {
    try {
      // StarUML 6.3.1 se cae (codigo 127) si 'exec' recibe -a, asi que el plan va junto al .mdj abierto
      dibujarTodo(arg || require('path').join(require('path').dirname(app.project.getFilename()), 'plan.json'))
    } catch (err) {
      log('ERROR ' + (err && err.stack ? err.stack : err))
    }
  })
}

exports.init = init
