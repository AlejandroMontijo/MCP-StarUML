# Galeria: un diagrama de cada tipo de StarUML, cada uno con todos los simbolos de su paleta en un escenario
# coherente (una tienda en linea generica), hecho con mdj_diagrama_crear + mdj_diagrama_generar. Sirve de prueba de
# regresion (tests/test_galeria.py y tests/test_staruml_real.py) y de ejemplo de como describir cada tipo de diagrama.


def E(simbolo, nombre=None, **kw):
    return dict(simbolo=simbolo, **({'nombre': nombre} if nombre is not None else {}), **kw)


def R(simbolo, desde=None, hasta=None, **kw):
    return dict(simbolo=simbolo, **({'desde': desde} if desde is not None else {}),
                **({'hasta': hasta} if hasta is not None else {}), **kw)


GALERIA = [
    # ------------------------------------------------------------------ UML estructura
    dict(tipo='clases', nombre='G01 Clases', elementos=[
        E('Package', 'Ventas'), E('Model', 'Modelo de dominio'), E('Subsystem', 'Facturacion'),
        E('Frame', 'Clases de la tienda'),
        E('Class', 'Cliente'), E('Class', 'Pedido'), E('Class', 'LineaPedido'), E('Class', 'Producto'),
        E('Class', 'ProductoDigital'), E('Class', 'ServicioPedidos'), E('Class', 'ListaPedidos'),
        E('Class', 'Lista'), E('Class', 'Tarjeta'),
        E('Port', 'api', sobre='ServicioPedidos'), E('Part', 'repositorio', sobre='ServicioPedidos'),
        E('Interface', 'IPagable'), E('Enumeration', 'EstadoPedido'), E('DataType', 'Direccion'),
        E('PrimitiveType', 'Moneda'), E('Signal', 'PedidoConfirmado'),
        E('Collaboration', 'Observador'), E('Collaboration Use', 'avisosPedido'),
        E('N-ary Association Node', 'Envio'),
        E('Object', 'pedido1'), E('Object', 'cliente1'), E('Object', 'producto1'),
        E('Artifact Instance', 'tienda.war'), E('Component Instance', 'api1'), E('Node Instance', 'servidor1')],
        relaciones=[
        R('Aggregation', 'Cliente', 'Pedido'), R('Composition', 'Pedido', 'LineaPedido'),
        R('Directed Association', 'LineaPedido', 'Producto'), R('Association', 'Cliente', 'Direccion'),
        R('Association Class', 'Cliente', 'Tarjeta', nombre='MedioDePago'),
        R('Generalization', 'ProductoDigital', 'Producto'), R('Interface Realization', 'Pedido', 'IPagable'),
        R('Realization', 'ServicioPedidos', 'Pedido'), R('Dependency', 'Pedido', 'EstadoPedido'),
        R('Template Binding', 'ListaPedidos', 'Lista'), R('Containment', 'Ventas', 'Cliente'),
        R('Connector', 'api', 'repositorio'), R('Role Binding', 'avisosPedido', 'api'),
        R('Link', 'pedido1', 'cliente1'), R('Directed Link', 'pedido1', 'producto1'),
        R('Link Object', 'cliente1', 'producto1')]),

    dict(tipo='paquetes', nombre='G02 Paquetes', elementos=[
        E('Model', 'Tienda'), E('Package', 'Presentacion', dentro='Tienda'), E('Package', 'Negocio', dentro='Tienda'),
        E('Package', 'Datos', dentro='Tienda'), E('Subsystem', 'Pagos'),
        E('Stakeholder', 'Gerente de ventas'), E('Viewpoint', 'Operacion'), E('View', 'Vista de operacion')],
        relaciones=[
        R('Dependency', 'Presentacion', 'Negocio'), R('Dependency', 'Negocio', 'Datos'),
        R('Dependency', 'Tienda', 'Pagos'), R('Conform', 'Vista de operacion', 'Operacion'),
        R('Expose', 'Vista de operacion', 'Pagos'), R('Containment', 'Gerente de ventas', 'Operacion')]),

    dict(tipo='objetos', nombre='G03 Objetos', elementos=[
        E('Object', 'cliente: Cliente'), E('Object', 'pedido: Pedido'), E('Object', 'linea1: LineaPedido'),
        E('Object', 'libro: Producto'), E('Artifact Instance', 'tienda.war'), E('Component Instance', 'api: API'),
        E('Node Instance', 'web01: Servidor')],
        relaciones=[
        R('Link', 'cliente: Cliente', 'pedido: Pedido'), R('Directed Link', 'pedido: Pedido', 'linea1: LineaPedido'),
        R('Link Object', 'linea1: LineaPedido', 'libro: Producto')]),

    dict(tipo='estructura_compuesta', nombre='G04 Estructura compuesta', elementos=[
        E('Class', 'Tienda'), E('Part', 'catalogo', sobre='Tienda'), E('Part', 'carrito', sobre='Tienda'),
        E('Port', 'web', sobre='Tienda'), E('Class', 'Almacen'), E('Interface', 'IInventario'),
        E('Class', 'Base'), E('DataType', 'Dinero'), E('Enumeration', 'Moneda'), E('PrimitiveType', 'Cantidad'),
        E('Signal', 'StockBajo'), E('Collaboration', 'Reabasto'), E('Collaboration Use', 'reabastoAlmacen'),
        E('N-ary Association Node', 'Surtido'), E('Frame', 'Estructura de la tienda'),
        E('Class', 'Proveedor'), E('Class', 'Pedido proveedor'), E('Class', 'Plantilla')],
        relaciones=[
        R('Connector', 'web', 'carrito'), R('Interface Realization', 'Almacen', 'IInventario'),
        R('Dependency', 'Tienda', 'IInventario'), R('Generalization', 'Almacen', 'Base'),
        R('Association', 'Almacen', 'Proveedor'), R('Directed Association', 'Proveedor', 'Pedido proveedor'),
        R('Aggregation', 'Tienda', 'Almacen'), R('Composition', 'Almacen', 'Dinero'),
        R('Association Class', 'Tienda', 'Proveedor', nombre='Contrato'),
        R('Realization', 'Pedido proveedor', 'Base'), R('Template Binding', 'Pedido proveedor', 'Plantilla'),
        R('Role Binding', 'reabastoAlmacen', 'web')]),

    dict(tipo='componentes', nombre='G05 Componentes', elementos=[
        E('Component', 'Frontend web'), E('Artifact', 'frontend.js'),
        E('Component', 'API de Pedidos'), E('Component', 'Controlador', dentro='API de Pedidos'),
        E('Component', 'Servicio', dentro='API de Pedidos'), E('Port', 'rest', sobre='API de Pedidos'),
        E('Part', 'cache', sobre='API de Pedidos'), E('Artifact', 'pedidos-api.jar'),
        E('Component', 'Pagos'), E('Interface', 'IPedidos'), E('Interface', 'IPagos'),
        E('Node', 'Servidor de aplicaciones'), E('Node', 'Servidor web'),
        E('Collaboration', 'Cobro'), E('Collaboration Use', 'cobroPedido'),
        E('Object', 'config: Configuracion'), E('Object', 'perfil: Perfil'), E('Artifact Instance', 'api-v2.jar'),
        E('Component Instance', 'api1: API de Pedidos'), E('Node Instance', 'app01'), E('Frame', 'Componentes')],
        relaciones=[
        R('Interface Realization', 'API de Pedidos', 'IPedidos'), R('Dependency', 'Frontend web', 'IPedidos'),
        R('Interface Realization', 'Pagos', 'IPagos'), R('Dependency', 'API de Pedidos', 'IPagos'),
        R('Connector', 'rest', 'Controlador'), R('Component Realization', 'frontend.js', 'Frontend web'),
        R('Component Realization', 'pedidos-api.jar', 'API de Pedidos'),
        R('Realization', 'Pagos', 'pedidos-api.jar'), R('Deployment', 'pedidos-api.jar', 'Servidor de aplicaciones'),
        R('Communication Path', 'Servidor web', 'Servidor de aplicaciones'), R('Role Binding', 'cobroPedido', 'rest'),
        R('Link', 'config: Configuracion', 'perfil: Perfil'), R('Directed Link', 'perfil: Perfil', 'api-v2.jar'),
        R('Link Object', 'config: Configuracion', 'api-v2.jar')]),

    dict(tipo='despliegue', nombre='G06 Despliegue', elementos=[
        E('Node', 'Celular del cliente'), E('Node', 'Servidor de aplicaciones'),
        E('Node', 'Tomcat', dentro='Servidor de aplicaciones'), E('Artifact', 'tienda.war', dentro='Tomcat'),
        E('Node', 'Servidor de datos'), E('Artifact', 'esquema.sql', dentro='Servidor de datos'),
        E('Component', 'API de Pedidos'), E('Interface', 'IPedidos'),
        E('Node Instance', 'app01: Servidor'), E('Artifact Instance', 'tienda-1.4.war', dentro='app01: Servidor'),
        E('Component Instance', 'api1: API de Pedidos'),
        E('Object', 'config: Despliegue'), E('Object', 'ambiente: Ambiente'), E('Frame', 'Infraestructura')],
        relaciones=[
        R('Communication Path', 'Celular del cliente', 'Servidor de aplicaciones', nombre='HTTPS'),
        R('Communication Path', 'Servidor de aplicaciones', 'Servidor de datos', nombre='JDBC'),
        R('Deployment', 'API de Pedidos', 'Servidor de aplicaciones'),
        R('Component Realization', 'tienda.war', 'API de Pedidos'),
        R('Interface Realization', 'API de Pedidos', 'IPedidos'), R('Dependency', 'Celular del cliente', 'IPedidos'),
        R('Link', 'config: Despliegue', 'ambiente: Ambiente'), R('Directed Link', 'ambiente: Ambiente', 'app01: Servidor'),
        R('Link Object', 'config: Despliegue', 'api1: API de Pedidos')]),

    dict(tipo='perfil', nombre='G07 Perfil', elementos=[
        E('MetaClass', 'Class'), E('MetaClass', 'Component'), E('Stereotype', 'Entidad'),
        E('Stereotype', 'Servicio'), E('Stereotype', 'Base'), E('Enumeration', 'Persistencia')],
        relaciones=[
        R('Extension', 'Entidad', 'Class'), R('Extension', 'Servicio', 'Component'),
        R('Generalization', 'Entidad', 'Base'), R('Generalization', 'Servicio', 'Base')]),

    # ------------------------------------------------------------------ UML comportamiento
    dict(tipo='casos_de_uso', nombre='G08 Casos de uso', elementos=[
        E('Use Case Subject', 'Tienda en linea'), E('Actor', 'Cliente'), E('Actor', 'Cliente frecuente'),
        E('Actor', 'Banco'),
        E('Use Case', 'Realizar pedido', dentro='Tienda en linea'),
        E('Use Case', 'Pagar pedido', dentro='Tienda en linea'),
        E('Use Case', 'Aplicar cupon', dentro='Tienda en linea'), E('Package', 'Administracion'),
        E('Frame', 'Casos de uso')],
        relaciones=[
        R('Association', 'Cliente', 'Realizar pedido'), R('Directed Association', 'Pagar pedido', 'Banco'),
        R('Generalization', 'Cliente frecuente', 'Cliente'), R('Include', 'Realizar pedido', 'Pagar pedido'),
        R('Extend', 'Aplicar cupon', 'Realizar pedido'), R('Dependency', 'Administracion', 'Tienda en linea')]),

    dict(tipo='actividades', nombre='G09 Actividades', elementos=[
        E('Swimlane (Vertical)', 'Cliente'), E('Swimlane (Vertical)', 'Tienda'),
        E('Activity Parameter Node', 'Cliente registrado', dentro='Cliente'),
        E('Initial', clave='inicio', dentro='Cliente'), E('Action', 'Elegir productos', dentro='Cliente'),
        E('Output Pin', 'carrito', sobre='Elegir productos'),
        E('Accept Signal', 'Confirmacion', dentro='Cliente'), E('Final', clave='fin', dentro='Cliente'),
        E('Datastore', 'Inventario', dentro='Tienda'),
        E('Action', 'Revisar existencias', dentro='Tienda'), E('Input Pin', 'pedido', sobre='Revisar existencias'),
        E('Decision', clave='hay', dentro='Tienda'), E('Flow Final', clave='cancelado', dentro='Tienda'),
        E('Fork', clave='divide', dentro='Tienda'),
        E('Interruptible Activity Region', 'Cancelable', dentro='Tienda'),
        E('Action', 'Cobrar', dentro='Cancelable'), E('Action', 'Empacar', dentro='Tienda'),
        E('Join', clave='une', dentro='Tienda'), E('Accept Time Event', '24 horas', dentro='Tienda'),
        E('Merge', clave='junta', dentro='Tienda'),
        E('Structured Activity', 'Facturar', dentro='Tienda'), E('Action', 'Timbrar', dentro='Facturar'),
        E('Expansion Region', 'Por cada linea', dentro='Tienda'), E('Action', 'Apartar', dentro='Por cada linea'),
        E('Input Expansion Node', 'lineas', sobre='Por cada linea'),
        E('Output Expansion Node', 'apartadas', sobre='Por cada linea'),
        E('Object Node', 'Pedido', dentro='Tienda'), E('Central Buffer', 'Pedidos pendientes', dentro='Tienda'),
        E('Send Signal', 'Avisar envio', dentro='Tienda'), E('Activity Edge Connector', 'A', dentro='Tienda'),
        E('Swimlane (Horizontal)', 'Paqueteria'), E('Action', 'Entregar', dentro='Paqueteria'),
        E('Frame', 'Proceso de pedido')],
        relaciones=[
        R('Object Flow', 'Cliente registrado', 'Elegir productos'), R('Control Flow', 'inicio', 'Elegir productos'),
        R('Object Flow', 'carrito', 'pedido'), R('Object Flow', 'Inventario', 'Revisar existencias'),
        R('Control Flow', 'Revisar existencias', 'hay'), R('Control Flow', 'hay', 'divide', nombre='[hay]'),
        R('Control Flow', 'hay', 'cancelado', nombre='[no hay]'), R('Control Flow', 'divide', 'Cobrar'),
        R('Control Flow', 'divide', 'Empacar'), R('Control Flow', 'Cobrar', 'une'), R('Control Flow', 'Empacar', 'une'),
        R('Activity Interrupt', 'Cobrar', 'cancelado'), R('Control Flow', 'une', 'junta'),
        R('Control Flow', '24 horas', 'junta'), R('Control Flow', 'junta', 'Facturar'),
        R('Exception Handler', 'Timbrar', 'Facturar'), R('Control Flow', 'Facturar', 'Por cada linea'),
        R('Object Flow', 'Por cada linea', 'Pedido'), R('Object Flow', 'Pedido', 'Pedidos pendientes'),
        R('Control Flow', 'Pedidos pendientes', 'Avisar envio'), R('Control Flow', 'Avisar envio', 'A'),
        R('Control Flow', 'Avisar envio', 'Entregar'), R('Control Flow', 'Confirmacion', 'fin')]),

    dict(tipo='estados', nombre='G10 Estados', elementos=[
        E('Initial State', clave='inicio'), E('Simple State', 'Nuevo'),
        E('Composite State', 'En proceso'), E('Simple State', 'Empacando', dentro='En proceso'),
        E('Simple State', 'Enviado', dentro='En proceso'),
        E('Entry Point', 'reanudar', sobre='En proceso'), E('Exit Point', 'listo', sobre='En proceso'),
        E('Orthogonal State', 'Atendiendo'), E('Submachine State', 'Cobrando'),
        E('Connection Point Reference', 'cobrado', sobre='Cobrando'),
        E('Choice', clave='pagado?'), E('Junction', clave='union'), E('Fork', clave='divide'),
        E('Join', clave='junta'), E('Shallow History', clave='H'), E('Deep History', clave='H*'),
        E('Final State', clave='fin'), E('Terminate', clave='cancelado'), E('Frame', 'Ciclo de vida del pedido')],
        relaciones=[
        R('Transition', 'inicio', 'Nuevo'), R('Transition', 'Nuevo', 'pagado?', nombre='pagar'),
        R('Transition', 'pagado?', 'divide', nombre='[aprobado]'), R('Transition', 'pagado?', 'cancelado', nombre='[rechazado]'),
        R('Transition', 'divide', 'En proceso'), R('Transition', 'divide', 'Atendiendo'),
        R('Transition', 'En proceso', 'junta'), R('Transition', 'Atendiendo', 'junta'),
        R('Transition', 'junta', 'union'), R('Transition', 'union', 'fin'),
        R('Transition', 'Empacando', 'Enviado'), R('Transition', 'H', 'Cobrando'),
        R('Transition', 'H*', 'Nuevo'), R('Transition', 'cobrado', 'fin')],
        extra=[E('Self Transition', 'reintentar', sobre='Nuevo')]),

    # ------------------------------------------------------------------ UML interaccion
    dict(tipo='secuencia', nombre='G11 Secuencia', disposicion='secuencia', elementos=[
        E('Lifeline', 'cliente'), E('Lifeline', 'pantalla'), E('Lifeline', 'control'), E('Lifeline', 'pedido'),
        E('Lifeline', 'banco'),
        E('State Invariant', 'abierto', sobre='pedido'), E('Self Message', 'validar', sobre='control'),
        E('Combined Fragment', 'opt'), E('Interaction Use', 'Autenticar'), E('Continuation', 'Listo'),
        E('Duration Constraint', '{0..5s}'), E('Gate', 'g1'), E('Endpoint', 'e1'), E('Frame', 'Realizar pedido')],
        relaciones=[
        R('Found Message', hasta='cliente', nombre='abrir tienda'),
        R('Message', 'cliente', 'pantalla', nombre='elegir(productos)', clave='m1'),
        R('Async Message', 'pantalla', 'control', nombre='crearPedido()'),
        R('Create Message', 'control', 'pedido', nombre='new'),
        R('Async Signal Message', 'control', 'banco', nombre='cobrar'),
        R('Reply Message', 'banco', 'control', nombre='aprobado'),
        R('Delete Message', 'control', 'pedido', nombre='destroy'),
        R('Lost Message', 'control', nombre='bitacora')],
        extra=[E('Time Constraint', '{t < 2s}', sobre='m1')]),

    dict(tipo='comunicacion', nombre='G12 Comunicacion', disposicion='secuencia', elementos=[
        E('Lifeline', 'cliente'), E('Lifeline', 'pantalla'), E('Lifeline', 'control'),
        E('Self Connector', clave='self', sobre='control'), E('Frame', 'Pedido por comunicacion')],
        relaciones=[
        R('Connector', 'cliente', 'pantalla', clave='c1'), R('Connector', 'pantalla', 'control', clave='c2'),
        R('Forward Message', hasta='c1', nombre='elegir'), R('Forward Message', hasta='c2', nombre='crearPedido'),
        R('Reverse Message', hasta='self', nombre='registrar')]),

    dict(tipo='tiempos', nombre='G13 Tiempos', elementos=[
        E('Lifeline', 'Pedido', sobre='@marco'), E('State/Condition', 'Nuevo', sobre='Pedido'),
        E('State/Condition', 'Pagado', sobre='Pedido'),
        E('Time Segment', clave='s1', sobre='Nuevo'), E('Time Segment', clave='s2', sobre='Pagado'),
        E('Time Tick', 't0', sobre='@marco'), E('Duration Constraint', '{< 24h}')],
        relaciones=[R('Message', 's1', 's2', nombre='pagar')],
        extra=[E('Time Constraint', '{t = 0}', sobre='s1')]),

    dict(tipo='vista_general_interaccion', nombre='G14 Vista general de interaccion', elementos=[
        E('Initial', clave='inicio'), E('Interaction Use', 'Autenticar'), E('Decision', clave='es nuevo?'),
        E('Interaction (Inline)', 'Registrar cliente'), E('Merge', clave='junta'), E('Fork', clave='divide'),
        E('Interaction Use', 'Cobrar'), E('Interaction Use', 'Enviar'), E('Join', clave='une'), E('Final', clave='fin')],
        relaciones=[
        R('Control Flow', 'inicio', 'Autenticar'), R('Control Flow', 'Autenticar', 'es nuevo?'),
        R('Control Flow', 'es nuevo?', 'Registrar cliente', nombre='[si]'), R('Control Flow', 'es nuevo?', 'junta', nombre='[no]'),
        R('Control Flow', 'Registrar cliente', 'junta'), R('Control Flow', 'junta', 'divide'),
        R('Control Flow', 'divide', 'Cobrar'), R('Control Flow', 'divide', 'Enviar'),
        R('Control Flow', 'Cobrar', 'une'), R('Control Flow', 'Enviar', 'une'), R('Control Flow', 'une', 'fin')]),

    dict(tipo='flujo_informacion', nombre='G15 Flujo de informacion', elementos=[
        E('Actor', 'Cliente'), E('Use Case Subject', 'Tienda'), E('Use Case', 'Comprar', dentro='Tienda'),
        E('Use Case', 'Pagar', dentro='Tienda'), E('Use Case', 'Usar cupon', dentro='Tienda'),
        E('Class', 'Pedido'), E('Class', 'Factura'), E('Class', 'Base'), E('Interface', 'IFacturable'),
        E('Information Item', 'Datos de pago'), E('Package', 'Contabilidad'), E('Frame', 'Flujos de informacion')],
        relaciones=[
        R('Association', 'Cliente', 'Comprar'), R('Directed Association', 'Pedido', 'Factura'),
        R('Aggregation', 'Factura', 'Pedido'), R('Composition', 'Pedido', 'Datos de pago'),
        R('Generalization', 'Factura', 'Base'), R('Interface Realization', 'Factura', 'IFacturable'),
        R('Include', 'Comprar', 'Pagar'), R('Extend', 'Usar cupon', 'Comprar'),
        R('Information Flow', 'Datos de pago', 'Contabilidad'), R('Dependency', 'Contabilidad', 'Factura')]),

    # ------------------------------------------------------------------ extensiones de StarUML
    dict(tipo='erd', nombre='G16 ERD', elementos=[
        E('Entity', 'cliente'), E('Entity', 'pedido'), E('Entity', 'producto'), E('Entity', 'perfil')],
        relaciones=[
        R('One to Many Relationship', 'cliente', 'pedido'), R('Many to Many Relationship', 'pedido', 'producto'),
        R('One to One Relationship', 'cliente', 'perfil')]),

    dict(tipo='flowchart', nombre='G17 Diagrama de flujo', elementos=[
        E('Terminator', 'Inicio'), E('Manual Input', 'Capturar pedido'), E('Process', 'Validar'),
        E('Decision', 'Valido?'), E('Predefined Process', 'Cobrar'), E('Alternate Process', 'Cobro manual'),
        E('Data', 'Pedido'), E('Document', 'Factura'), E('Multi-Document', 'Copias'), E('Database', 'Ventas'),
        E('Stored Data', 'Bitacora'), E('Internal Storage', 'Cache'), E('Direct Access Storage', 'Disco'),
        E('Display', 'Pantalla'), E('Manual Operation', 'Empacar'), E('Preparation', 'Preparar envio'),
        E('Delay', 'Esperar'), E('Merge', clave='Juntar'), E('Extract', clave='Separar'), E('Sort', 'Ordenar'),
        E('Collate', 'Cotejar'), E('Card', 'Tarjeta'), E('Punched Tape', 'Cinta'), E('Summing Junction', clave='suma'),
        E('Or', clave='o'), E('Connector', 'A'), E('Off-Page Connector', 'B'), E('Terminator', 'Fin')],
        relaciones=[
        R('Flow', 'Inicio', 'Capturar pedido'), R('Flow', 'Capturar pedido', 'Validar'), R('Flow', 'Validar', 'Valido?'),
        R('Flow', 'Valido?', 'Cobrar'), R('Flow', 'Valido?', 'Cobro manual'), R('Flow', 'Cobrar', 'Factura'),
        R('Flow', 'Factura', 'Copias'), R('Flow', 'Copias', 'Ventas'), R('Flow', 'Cobro manual', 'suma'),
        R('Flow', 'suma', 'o'), R('Flow', 'o', 'Fin'), R('Flow', 'Pedido', 'Validar'),
        R('Flow', 'Ventas', 'Bitacora'), R('Flow', 'Empacar', 'Preparar envio'), R('Flow', 'Preparar envio', 'Esperar'),
        R('Flow', 'Esperar', 'Juntar'), R('Flow', 'Juntar', 'Separar'), R('Flow', 'Separar', 'Ordenar'),
        R('Flow', 'Ordenar', 'Cotejar'), R('Flow', 'Tarjeta', 'Cinta'), R('Flow', 'Cache', 'Disco'),
        R('Flow', 'Disco', 'Pantalla'), R('Flow', 'A', 'B')]),

    dict(tipo='dfd', nombre='G18 DFD', elementos=[
        E('External Entity', 'Cliente'), E('Process', 'Registrar pedido'), E('Process', 'Cobrar'),
        E('Data Store', 'Pedidos'), E('External Entity', 'Banco')],
        relaciones=[
        R('Data Flow', 'Cliente', 'Registrar pedido', nombre='pedido'), R('Data Flow', 'Registrar pedido', 'Pedidos'),
        R('Data Flow', 'Registrar pedido', 'Cobrar', nombre='monto'), R('Data Flow', 'Cobrar', 'Banco')]),

    dict(tipo='bpmn', nombre='G19 BPMN', elementos=[
        E('Pool', 'Tienda'), E('Lane', 'Ventas', dentro='Tienda'), E('Lane', 'Almacen', dentro='Tienda'),
        E('Start Event', 'Pedido recibido', dentro='Ventas'), E('User Task', 'Revisar pedido', dentro='Ventas'),
        E('Gateway (Exclusive)', 'Aprobado?', dentro='Ventas'), E('Service Task', 'Cobrar', dentro='Ventas'),
        E('Boundary Event', 'Fallo', sobre='Cobrar'), E('Script Task', 'Calcular envio', dentro='Almacen'),
        E('Manual Task', 'Empacar', dentro='Almacen'), E('Gateway (Parallel)', 'Divide', dentro='Almacen'),
        E('Send Task', 'Avisar cliente', dentro='Almacen'), E('Receive Task', 'Recibir guia', dentro='Almacen'),
        E('Gateway (Inclusive)', 'Junta', dentro='Almacen'), E('End Event', 'Enviado', dentro='Almacen'),
        E('Pool (Vert)', 'Paqueteria'), E('Lane (Vert)', 'Rutas', dentro='Paqueteria'),
        E('Task', 'Recoger', dentro='Rutas'), E('Business Rule Task', 'Asignar ruta'), E('Call Activity', 'Facturar'),
        E('Sub Process', 'Devolucion'), E('Ad-Hoc Sub Process', 'Atencion'), E('Transaction', 'Reembolso'),
        E('Intermediate Event (Catch)', 'Espera 24h'), E('Intermediate Event (Throw)', 'Notificar'),
        E('Gateway (Event-Based)', 'Respuesta'), E('Gateway (Complex)', 'Reglas'), E('Gateway', 'Otro'),
        E('Data Object', 'Pedido'), E('Data Input', 'Carrito'), E('Data Output', 'Guia'), E('Data Store', 'Ventas BD'),
        E('Message', 'Confirmacion'), E('Group', 'Cobranza'), E('Text Annotation', 'Max 2 dias'),
        E('Choreography Task', 'Cotizar envio'), E('Sub Choreography', 'Negociar'),
        E('Conversation', 'Seguimiento'), E('Call Conversation', 'Soporte'), E('Sub Conversation', 'Reclamos')],
        relaciones=[
        R('Sequence Flow', 'Pedido recibido', 'Revisar pedido'), R('Sequence Flow', 'Revisar pedido', 'Aprobado?'),
        R('Sequence Flow', 'Aprobado?', 'Cobrar'), R('Sequence Flow', 'Cobrar', 'Calcular envio'),
        R('Sequence Flow', 'Calcular envio', 'Empacar'), R('Sequence Flow', 'Empacar', 'Divide'),
        R('Sequence Flow', 'Divide', 'Avisar cliente'), R('Sequence Flow', 'Divide', 'Recibir guia'),
        R('Sequence Flow', 'Avisar cliente', 'Junta'), R('Sequence Flow', 'Recibir guia', 'Junta'),
        R('Sequence Flow', 'Junta', 'Enviado'), R('Message Flow', 'Recibir guia', 'Recoger'),
        R('Data Association', 'Carrito', 'Revisar pedido'), R('Association', 'Max 2 dias', 'Empacar'),
        R('Message Link', 'Cotizar envio', 'Negociar'), R('Conversation Link', 'Seguimiento', 'Soporte'),
        R('Sequence Flow', 'Espera 24h', 'Notificar')]),

    dict(tipo='c4', nombre='G20 C4', elementos=[
        E('Person', 'Cliente'), E('Software System', 'Tienda en linea'), E('Software System', 'Banco'),
        E('Container (Web App)', 'Sitio web'), E('Container (Mobile App)', 'App movil'),
        E('Container (Desktop App)', 'Back office'), E('Container', 'API'), E('Container (Database)', 'Base de datos'),
        E('Component', 'Servicio de pedidos'), E('Element', 'Correo')],
        relaciones=[
        R('Relationship', 'Cliente', 'Sitio web', nombre='compra en'), R('Relationship', 'Cliente', 'App movil'),
        R('Relationship', 'Sitio web', 'API'), R('Relationship', 'App movil', 'API'),
        R('Relationship', 'Back office', 'API'), R('Relationship', 'API', 'Servicio de pedidos'),
        R('Relationship', 'Servicio de pedidos', 'Base de datos'), R('Relationship', 'Servicio de pedidos', 'Banco'),
        R('Relationship', 'Tienda en linea', 'Correo')]),

    dict(tipo='sysml_requisitos', nombre='G21 SysML requisitos', elementos=[
        E('Package', 'Requisitos de la tienda'), E('Requirement', 'Pago seguro', dentro='Requisitos de la tienda'),
        E('Requirement', 'Cifrado TLS'), E('Requirement', 'Cifrado TLS 1.3'), E('Requirement', 'Tiempo de respuesta'),
        E('Requirement', 'Respuesta movil'), E('Stakeholder', 'Cliente'), E('Viewpoint', 'Seguridad'),
        E('View', 'Vista de seguridad'), E('Frame', 'Requisitos')],
        relaciones=[
        R('Containment', 'Pago seguro', 'Cifrado TLS'), R('DeriveReqt', 'Cifrado TLS 1.3', 'Cifrado TLS'),
        R('Copy', 'Respuesta movil', 'Tiempo de respuesta'), R('Refine', 'Cifrado TLS 1.3', 'Pago seguro'),
        R('Satisfy', 'Requisitos de la tienda', 'Tiempo de respuesta'), R('Verify', 'Vista de seguridad', 'Pago seguro'),
        R('Conform', 'Vista de seguridad', 'Seguridad'), R('Expose', 'Vista de seguridad', 'Requisitos de la tienda')]),

    dict(tipo='sysml_bloques', nombre='G22 SysML bloques', elementos=[
        E('Block', 'Tienda'), E('Block', 'Carrito'), E('Block', 'Catalogo'), E('Block', 'Producto'),
        E('Block', 'Producto fisico'), E('Interface Block', 'Puerto de pago'), E('Constraint Block', 'Total'),
        E('Value Type', 'Dinero'), E('Enumeration', 'Moneda'), E('Signal', 'Pagado'), E('Object', 'tienda1'),
        E('Port', 'pago', sobre='Tienda'), E('Stakeholder', 'Cliente'), E('Viewpoint', 'Compra'),
        E('View', 'Vista de compra'), E('Frame', 'Bloques')],
        relaciones=[
        R('Composition', 'Tienda', 'Carrito'), R('Aggregation', 'Tienda', 'Catalogo'),
        R('Association', 'Carrito', 'Producto'), R('Directed Association', 'Catalogo', 'Producto'),
        R('Generalization', 'Producto fisico', 'Producto'), R('Dependency', 'Producto', 'Dinero'),
        R('Containment', 'Tienda', 'Total'), R('Connector', 'pago', 'Puerto de pago'),
        R('Conform', 'Vista de compra', 'Compra'), R('Expose', 'Vista de compra', 'Tienda')]),

    dict(tipo='sysml_bloque_interno', nombre='G23 SysML bloque interno', elementos=[
        E('Frame', 'Tienda'), E('Part', 'carrito', dentro='Tienda'), E('Part', 'catalogo', dentro='Tienda'),
        E('Reference', 'banco', dentro='Tienda'), E('Value', 'iva', dentro='Tienda'), E('Port', 'web', sobre='Tienda')],
        relaciones=[R('Connector', 'carrito', 'catalogo'), R('Connector', 'web', 'carrito'), R('Connector', 'carrito', 'banco')]),

    dict(tipo='sysml_parametrico', nombre='G24 SysML parametrico', elementos=[
        E('Frame', 'Total del pedido'), E('Constraint Property', 'total = subtotal + iva', dentro='Total del pedido'),
        E('Part', 'pedido', dentro='Total del pedido'), E('Reference', 'tarifa', dentro='Total del pedido'),
        E('Value', 'iva', dentro='Total del pedido'), E('Port', 'entrada', sobre='Total del pedido')],
        relaciones=[R('Connector', 'pedido', 'total = subtotal + iva'), R('Connector', 'iva', 'total = subtotal + iva'),
                    R('Connector', 'entrada', 'pedido')]),

    dict(tipo='wireframe', nombre='G25 Wireframe', elementos=[
        E('Frame (Web)', 'Pagina de pago'), E('Text', 'Confirma tu pedido', dentro='Pagina de pago'),
        E('Image', 'Logo', dentro='Pagina de pago'), E('Avatar', 'Usuario', dentro='Pagina de pago'),
        E('Input', 'Correo', dentro='Pagina de pago'), E('Dropdown', 'Envio', dentro='Pagina de pago'),
        E('Checkbox', 'Factura', dentro='Pagina de pago'), E('Radio', 'Tarjeta', dentro='Pagina de pago'),
        E('Switch', 'Guardar datos', dentro='Pagina de pago'), E('Slider', 'Propina', dentro='Pagina de pago'),
        E('Tab List', 'Pasos', dentro='Pagina de pago'), E('Tab', 'Pago', dentro='Pagina de pago'),
        E('Separator', clave='linea', dentro='Pagina de pago'), E('Link', 'Terminos', dentro='Pagina de pago'),
        E('Button', 'Pagar', dentro='Pagina de pago'), E('Panel', 'Resumen', dentro='Pagina de pago'),
        E('Frame (Mobile)', 'App'), E('Button', 'Comprar', dentro='App'), E('Frame (Desktop)', 'Back office'),
        E('Frame', 'Ventana')]),

    dict(tipo='mindmap', nombre='G26 Mapa mental', elementos=[
        E('Node', 'Tienda en linea'), E('Node', 'Catalogo'), E('Node', 'Pagos'), E('Node', 'Envios'),
        E('Node', 'Tarjeta'), E('Node', 'Transferencia')],
        relaciones=[R('Edge', 'Tienda en linea', 'Catalogo'), R('Edge', 'Tienda en linea', 'Pagos'),
                    R('Edge', 'Tienda en linea', 'Envios'), R('Edge', 'Pagos', 'Tarjeta'),
                    R('Edge', 'Pagos', 'Transferencia')]),

    dict(tipo='aws', nombre='G27 AWS', elementos=[
        E('AWS Group', 'Nube de la tienda'), E('AWS Availability Zone', 'Zona A', dentro='Nube de la tienda'),
        E('AWS Security Group', 'Web', dentro='Zona A'), E('AWS Service', 'Balanceador'),
        E('AWS Resource', 'Servidor web', dentro='Web'), E('AWS General Resource', 'Usuarios'),
        E('AWS Generic Group', 'Datos'), E('AWS Resource', 'Base de datos', dentro='Datos'),
        E('AWS Callout', 'Respaldo diario')],
        relaciones=[R('AWS Arrow', 'Usuarios', 'Balanceador'), R('AWS Arrow', 'Balanceador', 'Nube de la tienda'),
                    R('AWS Arrow', 'Nube de la tienda', 'Datos')]),

    dict(tipo='gcp', nombre='G28 Google Cloud', elementos=[
        E('User', 'Cliente'), E('Zone', 'Proyecto tienda'), E('Product', 'Cloud Run', dentro='Proyecto tienda'),
        E('Service', 'Cloud SQL', dentro='Proyecto tienda'), E('Product', 'Pub/Sub')],
        relaciones=[R('Path', 'Cliente', 'Proyecto tienda'), R('Path', 'Proyecto tienda', 'Pub/Sub')]),
]


# boundary, control y entity de la paleta de clases van con mdj_robustez_generar (diagrama de analisis)
ROBUSTEZ = dict(nombre='G29 Robustez', paquete='Analisis de la tienda',
                actores=[{'nombre': 'Cliente'}],
                pantallas=[{'nombre': 'PantallaCatalogo'}, {'nombre': 'PantallaCarrito'}, {'nombre': 'PantallaPago'}],
                control={'nombre': 'ControlComprar'},
                entidades=[{'nombre': 'Carrito', 'atributos': ['fecha', 'total']},
                           {'nombre': 'Producto', 'atributos': ['clave', 'precio']},
                           {'nombre': 'Pedido', 'atributos': ['folio', 'estado']},
                           {'nombre': 'LineaCarrito', 'atributos': ['cantidad'], 'depende_de': 'Carrito'}],
                asociaciones=[{'desde': 'Carrito', 'hasta': 'LineaCarrito', 'mult_desde': '1', 'mult_hacia': '1..*'},
                              {'desde': 'LineaCarrito', 'hasta': 'Producto', 'mult_desde': '0..*', 'mult_hacia': '1'},
                              {'desde': 'Carrito', 'hasta': 'Pedido', 'mult_desde': '1', 'mult_hacia': '0..1'}])
SIMBOLOS_ROBUSTEZ = {'Boundary', 'Control', 'Entity'}


def construir(tool, archivo):
    """Crea cada diagrama de la galeria en el archivo con las herramientas MCP (tool(nombre, **args)). Devuelve
    {nombre: resultado de mdj_diagrama_generar (+ los extra)}."""
    res = {}
    for g in GALERIA:
        dg = tool('mdj_diagrama_crear', archivo=archivo, tipo=g['tipo'], nombre=g['nombre'])['diagrama']
        r = tool('mdj_diagrama_generar', archivo=archivo, diagrama=dg, elementos=g['elementos'],
                 relaciones=g.get('relaciones', []), disposicion=g.get('disposicion', 'capas'))
        if g.get('extra'):
            # lo que va sobre una linea o algo dibujado: se agrega con las claves que devolvio la primera llamada
            ex = []
            for e in g['extra']:
                e = dict(e)
                e['sobre'] = r['vistas'].get(e['sobre'], e['sobre'])
                ex.append(e)
            r2 = tool('mdj_diagrama_generar', archivo=archivo, diagrama=dg, elementos=ex)
            r['vistas'].update(r2['vistas'])
            r.setdefault('avisos', []).extend(r2.get('avisos', []))
            r['lineas_que_cruzan_cajas'] += r2['lineas_que_cruzan_cajas']
        res[g['nombre']] = r
    rb = dict(ROBUSTEZ)
    tool('mdj_paquete_crear', archivo=archivo, nombre=rb['paquete'])
    dg = tool('mdj_diagrama_crear', archivo=archivo, tipo='clases', nombre=rb.pop('nombre'),
              dentro_de=rb['paquete'])['diagrama']
    res[ROBUSTEZ['nombre']] = tool('mdj_robustez_generar', archivo=archivo, diagrama=dg, **rb)
    return res


def simbolos_usados(g):
    usados = {e['simbolo'] for e in g['elementos'] + g.get('extra', [])} | {r['simbolo'] for r in g.get('relaciones', [])}
    return usados
