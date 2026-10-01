# Catalogo de diagramas y simbolos

Generado con `herramientas/generar_catalogo.py` a partir de StarUML 6.3.1. Las descripciones son propias. Las secciones citadas son de la especificacion [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/PDF), que no se incluye en el repositorio.

Cada simbolo listado se puede dibujar con `mdj_dibujar` (por su etiqueta de paleta) y cada diagrama se puede crear con `mdj_diagrama_crear` (por su nombre corto o su tipo de StarUML). `mdj_catalogo` da la misma informacion en JSON. En las lineas, el ejemplo es el par de vistas con que StarUML la dibujo en la referencia; cualquier otro par que StarUML acepte tambien sirve.

| Diagrama | Nombre corto | Tipo StarUML | Familia | Especificacion | Simbolos |
|---|---|---|---|---|---|
| Clases | `clases` | `UMLClassDiagram` | UML estructura | 9 Classification, 10 Simple Classifiers, 11.5 Associations | 38 |
| Paquetes | `paquetes` | `UMLPackageDiagram` | UML estructura | 12.2 Packages | 10 |
| Objetos | `objetos` | `UMLObjectDiagram` | UML estructura | 9.8 Instances | 7 |
| Estructura compuesta | `estructura_compuesta` | `UMLCompositeStructureDiagram` | UML estructura | 11.2 Structured Classifiers, 11.3 Encapsulated Classifiers, 11.7 Collaborations | 24 |
| Componentes | `componentes` | `UMLComponentDiagram` | UML estructura | 11.6 Components | 24 |
| Despliegue | `despliegue` | `UMLDeploymentDiagram` | UML estructura | 19 Deployments | 17 |
| Perfil | `perfil` | `UMLProfileDiagram` | UML estructura | 12.3 Profiles | 5 |
| Casos de uso | `casos_de_uso` | `UMLUseCaseDiagram` | UML comportamiento | 18 Use Cases | 11 |
| Actividades | `actividades` | `UMLActivityDiagram` | UML comportamiento | 15 Activities, 16 Actions | 30 |
| Estados | `estados` | `UMLStatechartDiagram` | UML comportamiento | 14 State Machines | 19 |
| Secuencia | `secuencia` | `UMLSequenceDiagram` | UML interaccion | 17.8 Sequence Diagrams | 19 |
| Comunicacion | `comunicacion` | `UMLCommunicationDiagram` | UML interaccion | 17.9 Communication Diagrams | 6 |
| Tiempos | `tiempos` | `UMLTimingDiagram` | UML interaccion | 17.11 Timing Diagrams | 7 |
| Vista general de interaccion | `vista_general_interaccion` | `UMLInteractionOverviewDiagram` | UML interaccion | 17.10 Interaction Overview Diagrams | 9 |
| Flujo de informacion | `flujo_informacion` | `UMLInformationFlowDiagram` | UML | 20 Information Flows | 18 |
| Entidad-relacion (ERD) | `erd` | `ERDDiagram` | StarUML | no es UML | 4 |
| Diagrama de flujo | `flowchart` | `FCFlowchartDiagram` | StarUML | no es UML | 28 |
| Flujo de datos (DFD) | `dfd` | `DFDDiagram` | StarUML | no es UML | 4 |
| BPMN | `bpmn` | `BPMNDiagram` | StarUML | no es UML (BPMN 2.0, OMG) | 45 |
| C4 | `c4` | `C4Diagram` | StarUML | no es UML (modelo C4) | 10 |
| SysML requisitos | `sysml_requisitos` | `SysMLRequirementDiagram` | StarUML | no es UML (SysML 1.x, OMG) | 14 |
| SysML definicion de bloques | `sysml_bloques` | `SysMLBlockDefinitionDiagram` | StarUML | no es UML (SysML 1.x, OMG) | 22 |
| SysML bloque interno | `sysml_bloque_interno` | `SysMLInternalBlockDiagram` | StarUML | no es UML (SysML 1.x, OMG) | 6 |
| SysML parametrico | `sysml_parametrico` | `SysMLParametricDiagram` | StarUML | no es UML (SysML 1.x, OMG) | 7 |
| Wireframe | `wireframe` | `WFWireframeDiagram` | StarUML | no es UML | 19 |
| Mapa mental | `mindmap` | `MMMindmapDiagram` | StarUML | no es UML | 2 |
| AWS | `aws` | `AWSDiagram` | StarUML | no es UML | 9 |
| Google Cloud | `gcp` | `GCPDiagram` | StarUML | no es UML | 5 |

## Clases

`UMLClassDiagram` (nombre corto `clases`). Especificacion: 9 Classification, 10 Simple Classifiers, 11.5 Associations.

Clases, interfaces, tipos de datos, enumeraciones y senales con sus atributos y operaciones, y las relaciones entre ellos: asociacion (con agregacion o composicion), generalizacion, realizacion de interfaz, dependencia y clase asociacion. Es el diagrama del modelo de dominio y del diseno.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Aggregation | linea | `UMLAggregation` | `UMLAssociationView` | ejemplo: UMLClassView → UMLClassView |
| Artifact Instance | caja | `UMLArtifactInstance` | `UMLArtifactInstanceView` |  |
| Association Class | linea | `UMLAssociationClass` | `UMLAssociationClassLinkView` | ejemplo: UMLClassView → UMLClassView |
| Association | linea | `UMLAssociation` | `UMLAssociationView` | ejemplo: UMLClassView → UMLClassView |
| Boundary | caja | `UMLBoundary` | `UMLClassView` |  |
| Class | caja | `UMLClass` | `UMLClassView` |  |
| Collaboration Use | caja | `UMLCollaborationUse` | `UMLCollaborationUseView` |  |
| Collaboration | caja | `UMLCollaboration` | `UMLCollaborationView` |  |
| Component Instance | caja | `UMLComponentInstance` | `UMLComponentInstanceView` |  |
| Composition | linea | `UMLComposition` | `UMLAssociationView` | ejemplo: UMLClassView → UMLClassView |
| Connector | linea | `UMLConnector` | `UMLConnectorView` | ejemplo: UMLPortView → UMLPartView |
| Containment | linea | `UMLContainment` | `UMLContainmentView` | ejemplo: UMLClassView → UMLClassView |
| Control | caja | `UMLControl` | `UMLClassView` |  |
| DataType | caja | `UMLDataType` | `UMLDataTypeView` |  |
| Dependency | linea | `UMLDependency` | `UMLDependencyView` | ejemplo: UMLClassView → UMLClassView |
| Directed Association | linea | `UMLDirectedAssociation` | `UMLAssociationView` | ejemplo: UMLClassView → UMLClassView |
| Directed Link | linea | `UMLDirectedLink` | `UMLLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Entity | caja | `UMLEntity` | `UMLClassView` |  |
| Enumeration | caja | `UMLEnumeration` | `UMLEnumerationView` |  |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Generalization | linea | `UMLGeneralization` | `UMLGeneralizationView` | ejemplo: UMLClassView → UMLClassView |
| Interface Realization | linea | `UMLInterfaceRealization` | `UMLInterfaceRealizationView` | ejemplo: UMLClassView → UMLInterfaceView |
| Interface | caja | `UMLInterface` | `UMLInterfaceView` |  |
| Link Object | linea | `UMLLinkObject` | `UMLLinkObjectLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Link | linea | `UMLLink` | `UMLLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Model | caja | `UMLModel` | `UMLModelView` |  |
| N-ary Association Node | caja | `UMLNaryAssociationNode` | `UMLNaryAssociationNodeView` |  |
| Node Instance | caja | `UMLNodeInstance` | `UMLNodeInstanceView` |  |
| Object | caja | `UMLObject` | `UMLObjectView` |  |
| Package | caja | `UMLPackage` | `UMLPackageView` |  |
| Part | caja | `UMLPart` | `UMLPartView` | va sobre UMLClassView |
| Port | caja | `UMLPort` | `UMLPortView` | va sobre UMLClassView |
| PrimitiveType | caja | `UMLPrimitiveType` | `UMLPrimitiveTypeView` |  |
| Realization | linea | `UMLRealization` | `UMLRealizationView` | ejemplo: UMLClassView → UMLClassView |
| Role Binding | linea | `UMLRoleBinding` | `UMLRoleBindingView` | ejemplo: UMLCollaborationUseView → UMLPortView |
| Signal | caja | `UMLSignal` | `UMLSignalView` |  |
| Subsystem | caja | `UMLSubsystem` | `UMLSubsystemView` |  |
| Template Binding | linea | `UMLTemplateBinding` | `UMLTemplateBindingView` | ejemplo: UMLClassView → UMLClassView |

## Paquetes

`UMLPackageDiagram` (nombre corto `paquetes`). Especificacion: 12.2 Packages.

Paquetes, modelos y subsistemas y las dependencias, importaciones y fusiones entre ellos. Sirve para mostrar la organizacion en capas o modulos de un sistema.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Conform | linea | `SysMLConform` | `SysMLConformView` | ejemplo: SysMLStakeholderView → SysMLViewView |
| Containment | linea | `UMLContainment` | `UMLContainmentView` | ejemplo: SysMLStakeholderView → SysMLViewView |
| Dependency | linea | `UMLDependency` | `UMLDependencyView` | ejemplo: SysMLStakeholderView → SysMLViewView |
| Expose | linea | `SysMLExpose` | `SysMLExposeView` | ejemplo: SysMLStakeholderView → SysMLViewView |
| Model | caja | `UMLModel` | `UMLModelView` |  |
| Package | caja | `UMLPackage` | `UMLPackageView` |  |
| Stakeholder | caja | `SysMLStakeholder` | `SysMLStakeholderView` |  |
| Subsystem | caja | `UMLSubsystem` | `UMLSubsystemView` |  |
| Viewpoint | caja | `SysMLViewpoint` | `SysMLViewpointView` |  |
| View | caja | `SysMLView` | `SysMLViewView` |  |

## Objetos

`UMLObjectDiagram` (nombre corto `objetos`). Especificacion: 9.8 Instances.

Instancias (especificaciones de instancia) con valores en sus slots y los enlaces entre ellas: una foto del sistema en un momento dado.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Artifact Instance | caja | `UMLArtifactInstance` | `UMLArtifactInstanceView` |  |
| Component Instance | caja | `UMLComponentInstance` | `UMLComponentInstanceView` |  |
| Directed Link | linea | `UMLDirectedLink` | `UMLLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Link Object | linea | `UMLLinkObject` | `UMLLinkObjectLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Link | linea | `UMLLink` | `UMLLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Node Instance | caja | `UMLNodeInstance` | `UMLNodeInstanceView` |  |
| Object | caja | `UMLObject` | `UMLObjectView` |  |

## Estructura compuesta

`UMLCompositeStructureDiagram` (nombre corto `estructura_compuesta`). Especificacion: 11.2 Structured Classifiers, 11.3 Encapsulated Classifiers, 11.7 Collaborations.

La estructura interna de un clasificador: partes, puertos y conectores; y las colaboraciones con los roles que intervienen.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Aggregation | linea | `UMLAggregation` | `UMLAssociationView` | ejemplo: UMLClassView → UMLInterfaceView |
| Association Class | linea | `UMLAssociationClass` | `UMLAssociationClassLinkView` | ejemplo: UMLClassView → UMLInterfaceView |
| Association | linea | `UMLAssociation` | `UMLAssociationView` | ejemplo: UMLClassView → UMLInterfaceView |
| Class | caja | `UMLClass` | `UMLClassView` |  |
| Collaboration Use | caja | `UMLCollaborationUse` | `UMLCollaborationUseView` |  |
| Collaboration | caja | `UMLCollaboration` | `UMLCollaborationView` |  |
| Composition | linea | `UMLComposition` | `UMLAssociationView` | ejemplo: UMLClassView → UMLInterfaceView |
| Connector | linea | `UMLConnector` | `UMLConnectorView` | ejemplo: UMLPortView → UMLPartView |
| DataType | caja | `UMLDataType` | `UMLDataTypeView` |  |
| Dependency | linea | `UMLDependency` | `UMLDependencyView` | ejemplo: UMLClassView → UMLInterfaceView |
| Directed Association | linea | `UMLDirectedAssociation` | `UMLAssociationView` | ejemplo: UMLClassView → UMLInterfaceView |
| Enumeration | caja | `UMLEnumeration` | `UMLEnumerationView` |  |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Generalization | linea | `UMLGeneralization` | `UMLGeneralizationView` | ejemplo: UMLClassView → UMLInterfaceView |
| Interface Realization | linea | `UMLInterfaceRealization` | `UMLInterfaceRealizationView` | ejemplo: UMLClassView → UMLInterfaceView |
| Interface | caja | `UMLInterface` | `UMLInterfaceView` |  |
| N-ary Association Node | caja | `UMLNaryAssociationNode` | `UMLNaryAssociationNodeView` |  |
| Part | caja | `UMLPart` | `UMLPartView` | va sobre UMLClassView |
| Port | caja | `UMLPort` | `UMLPortView` | va sobre UMLClassView |
| PrimitiveType | caja | `UMLPrimitiveType` | `UMLPrimitiveTypeView` |  |
| Realization | linea | `UMLRealization` | `UMLRealizationView` | ejemplo: UMLClassView → UMLInterfaceView |
| Role Binding | linea | `UMLRoleBinding` | `UMLRoleBindingView` | ejemplo: UMLCollaborationUseView → UMLPortView |
| Signal | caja | `UMLSignal` | `UMLSignalView` |  |
| Template Binding | linea | `UMLTemplateBinding` | `UMLTemplateBindingView` | ejemplo: UMLClassView → UMLInterfaceView |

## Componentes

`UMLComponentDiagram` (nombre corto `componentes`). Especificacion: 11.6 Components.

Componentes con sus interfaces provistas (lollipop) y requeridas (socket), puertos, artefactos que los manifiestan y las dependencias y conectores de ensamble entre ellos.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Artifact Instance | caja | `UMLArtifactInstance` | `UMLArtifactInstanceView` |  |
| Artifact | caja | `UMLArtifact` | `UMLArtifactView` |  |
| Collaboration Use | caja | `UMLCollaborationUse` | `UMLCollaborationUseView` |  |
| Collaboration | caja | `UMLCollaboration` | `UMLCollaborationView` |  |
| Communication Path | linea | `UMLCommunicationPath` | `UMLCommunicationPathView` | ejemplo: UMLNodeView → UMLNodeView |
| Component Instance | caja | `UMLComponentInstance` | `UMLComponentInstanceView` |  |
| Component Realization | linea | `UMLComponentRealization` | `UMLComponentRealizationView` | ejemplo: UMLArtifactView → UMLComponentView |
| Component | caja | `UMLComponent` | `UMLComponentView` |  |
| Connector | linea | `UMLConnector` | `UMLConnectorView` | ejemplo: UMLPortView → UMLPartView |
| Dependency | linea | `UMLDependency` | `UMLDependencyView` | ejemplo: UMLComponentView → UMLArtifactView |
| Deployment | linea | `UMLDeployment` | `UMLDeploymentView` | ejemplo: UMLComponentView → UMLNodeView |
| Directed Link | linea | `UMLDirectedLink` | `UMLLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Interface Realization | linea | `UMLInterfaceRealization` | `UMLInterfaceRealizationView` | ejemplo: UMLComponentView → UMLInterfaceView |
| Interface | caja | `UMLInterface` | `UMLInterfaceView` |  |
| Link Object | linea | `UMLLinkObject` | `UMLLinkObjectLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Link | linea | `UMLLink` | `UMLLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Node Instance | caja | `UMLNodeInstance` | `UMLNodeInstanceView` |  |
| Node | caja | `UMLNode` | `UMLNodeView` |  |
| Object | caja | `UMLObject` | `UMLObjectView` |  |
| Part | caja | `UMLPart` | `UMLPartView` | va sobre UMLComponentView |
| Port | caja | `UMLPort` | `UMLPortView` | va sobre UMLComponentView |
| Realization | linea | `UMLRealization` | `UMLRealizationView` | ejemplo: UMLComponentView → UMLArtifactView |
| Role Binding | linea | `UMLRoleBinding` | `UMLRoleBindingView` | ejemplo: UMLCollaborationUseView → UMLPortView |

## Despliegue

`UMLDeploymentDiagram` (nombre corto `despliegue`). Especificacion: 19 Deployments.

La arquitectura fisica: nodos, dispositivos y entornos de ejecucion (anidables), las rutas de comunicacion entre ellos, los artefactos desplegados en cada nodo (despliegue) y los componentes que cada artefacto manifiesta.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Artifact Instance | caja | `UMLArtifactInstance` | `UMLArtifactInstanceView` |  |
| Artifact | caja | `UMLArtifact` | `UMLArtifactView` |  |
| Communication Path | linea | `UMLCommunicationPath` | `UMLCommunicationPathView` | ejemplo: UMLNodeView → UMLNodeView |
| Component Instance | caja | `UMLComponentInstance` | `UMLComponentInstanceView` |  |
| Component Realization | linea | `UMLComponentRealization` | `UMLComponentRealizationView` | ejemplo: UMLArtifactView → UMLComponentView |
| Component | caja | `UMLComponent` | `UMLComponentView` |  |
| Dependency | linea | `UMLDependency` | `UMLDependencyView` | ejemplo: UMLComponentView → UMLArtifactView |
| Deployment | linea | `UMLDeployment` | `UMLDeploymentView` | ejemplo: UMLComponentView → UMLNodeView |
| Directed Link | linea | `UMLDirectedLink` | `UMLLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Interface Realization | linea | `UMLInterfaceRealization` | `UMLInterfaceRealizationView` | ejemplo: UMLComponentView → UMLInterfaceView |
| Interface | caja | `UMLInterface` | `UMLInterfaceView` |  |
| Link Object | linea | `UMLLinkObject` | `UMLLinkObjectLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Link | linea | `UMLLink` | `UMLLinkView` | ejemplo: UMLObjectView → UMLArtifactInstanceView |
| Node Instance | caja | `UMLNodeInstance` | `UMLNodeInstanceView` |  |
| Node | caja | `UMLNode` | `UMLNodeView` |  |
| Object | caja | `UMLObject` | `UMLObjectView` |  |

## Perfil

`UMLProfileDiagram` (nombre corto `perfil`). Especificacion: 12.3 Profiles.

Perfiles con sus estereotipos, las metaclases que extienden (extension) y las importaciones de metaclases. Sirve para definir vocabularios propios sobre UML.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Enumeration | caja | `UMLEnumeration` | `UMLEnumerationView` |  |
| Extension | linea | `UMLExtension` | `UMLExtensionView` | ejemplo: UMLStereotypeView → UMLMetaClassView |
| Generalization | linea | `UMLGeneralization` | `UMLGeneralizationView` | ejemplo: UMLStereotypeView → UMLEnumerationView |
| MetaClass | caja | `UMLMetaClass` | `UMLMetaClassView` |  |
| Stereotype | caja | `UMLStereotype` | `UMLStereotypeView` |  |

## Casos de uso

`UMLUseCaseDiagram` (nombre corto `casos_de_uso`). Especificacion: 18 Use Cases.

Actores, casos de uso y el sujeto (sistema) que los contiene, con asociaciones, include, extend (con puntos de extension) y generalizaciones.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Actor | caja | `UMLActor` | `UMLActorView` |  |
| Association | linea | `UMLAssociation` | `UMLAssociationView` | ejemplo: UMLUseCaseView → UMLActorView |
| Dependency | linea | `UMLDependency` | `UMLDependencyView` | ejemplo: UMLPackageView → UMLUseCaseSubjectView |
| Directed Association | linea | `UMLDirectedAssociation` | `UMLAssociationView` | ejemplo: UMLUseCaseView → UMLActorView |
| Extend | linea | `UMLExtend` | `UMLExtendView` | ejemplo: UMLUseCaseView → UMLUseCaseView |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Generalization | linea | `UMLGeneralization` | `UMLGeneralizationView` | ejemplo: UMLUseCaseView → UMLActorView |
| Include | linea | `UMLInclude` | `UMLIncludeView` | ejemplo: UMLUseCaseView → UMLUseCaseView |
| Package | caja | `UMLPackage` | `UMLPackageView` |  |
| Use Case Subject | caja | `UMLUseCaseSubject` | `UMLUseCaseSubjectView` |  |
| Use Case | caja | `UMLUseCase` | `UMLUseCaseView` |  |

## Actividades

`UMLActivityDiagram` (nombre corto `actividades`). Especificacion: 15 Activities, 16 Actions.

Flujos de acciones con nodos inicial y final, decisiones y fusiones, bifurcaciones y uniones, nodos de objeto, pines, particiones (carriles), regiones interrumpibles y de expansion, y flujos de control y de objetos.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Accept Signal | caja | `UMLAcceptSignal` | `UMLActionView` |  |
| Accept Time Event | caja | `UMLAcceptTimeEvent` | `UMLActionView` |  |
| Action | caja | `UMLAction` | `UMLActionView` |  |
| Activity Edge Connector | caja | `UMLActivityEdgeConnector` | `UMLActivityEdgeConnectorView` |  |
| Activity Interrupt | linea | `UMLActivityInterrupt` | `UMLActivityInterruptView` | ejemplo: UMLActionView → UMLControlNodeView |
| Activity Parameter Node | caja | `UMLActivityParameterNode` | `UMLActivityParameterNodeView` |  |
| Central Buffer | caja | `UMLCentralBufferNode` | `UMLCentralBufferNodeView` |  |
| Control Flow | linea | `UMLControlFlow` | `UMLControlFlowView` | ejemplo: UMLActionView → UMLControlNodeView |
| Datastore | caja | `UMLDataStoreNode` | `UMLDataStoreNodeView` |  |
| Decision | caja | `UMLDecisionNode` | `UMLControlNodeView` |  |
| Exception Handler | linea | `UMLExceptionHandler` | `UMLExceptionHandlerView` | ejemplo: UMLActionView → UMLStructuredActivityNodeView |
| Expansion Region | caja | `UMLExpansionRegion` | `UMLExpansionRegionView` |  |
| Final | caja | `UMLActivityFinalNode` | `UMLControlNodeView` |  |
| Flow Final | caja | `UMLFlowFinalNode` | `UMLControlNodeView` |  |
| Fork | caja | `UMLForkNode` | `UMLControlNodeView` |  |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Initial | caja | `UMLInitialNode` | `UMLControlNodeView` |  |
| Input Expansion Node | caja | `UMLInputExpansionNode` | `UMLExpansionNodeView` | va sobre UMLActionView |
| Input Pin | caja | `UMLInputPin` | `UMLInputPinView` | va sobre UMLActionView |
| Interruptible Activity Region | caja | `UMLInterruptibleActivityRegion` | `UMLInterruptibleActivityRegionView` |  |
| Join | caja | `UMLJoinNode` | `UMLControlNodeView` |  |
| Merge | caja | `UMLMergeNode` | `UMLControlNodeView` |  |
| Object Flow | linea | `UMLObjectFlow` | `UMLObjectFlowView` | ejemplo: UMLActionView → UMLControlNodeView |
| Object Node | caja | `UMLObjectNode` | `UMLObjectNodeView` |  |
| Output Expansion Node | caja | `UMLOutputExpansionNode` | `UMLExpansionNodeView` | va sobre UMLActionView |
| Output Pin | caja | `UMLOutputPin` | `UMLOutputPinView` | va sobre UMLActionView |
| Send Signal | caja | `UMLSendSignal` | `UMLActionView` |  |
| Structured Activity | caja | `UMLStructuredActivityNode` | `UMLStructuredActivityNodeView` |  |
| Swimlane (Horizontal) | caja | `UMLSwimlaneHorz` | `UMLSwimlaneView` |  |
| Swimlane (Vertical) | caja | `UMLSwimlaneVert` | `UMLSwimlaneView` |  |

## Estados

`UMLStatechartDiagram` (nombre corto `estados`). Especificacion: 14 State Machines.

Maquinas de estados: estados simples y compuestos (con regiones), pseudoestados (inicial, historia, eleccion, union, bifurcacion, punto de entrada y salida, terminacion), estados finales y transiciones con disparador, guarda y efecto.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Choice | caja | `UMLChoice` | `UMLPseudostateView` |  |
| Composite State | caja | `UMLCompositeState` | `UMLStateView` |  |
| Connection Point Reference | caja | `UMLConnectionPointReference` | `UMLConnectionPointReferenceView` | va sobre UMLStateView |
| Deep History | caja | `UMLDeepHistory` | `UMLPseudostateView` |  |
| Entry Point | caja | `UMLEntryPoint` | `UMLPseudostateView` |  |
| Exit Point | caja | `UMLExitPoint` | `UMLPseudostateView` |  |
| Final State | caja | `UMLFinalState` | `UMLFinalStateView` |  |
| Fork | caja | `UMLFork` | `UMLPseudostateView` |  |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Initial State | caja | `UMLInitialState` | `UMLPseudostateView` |  |
| Join | caja | `UMLJoin` | `UMLPseudostateView` |  |
| Junction | caja | `UMLJunction` | `UMLPseudostateView` |  |
| Orthogonal State | caja | `UMLOrthogonalState` | `UMLStateView` |  |
| Self Transition | caja | `UMLSelfTransition` | `UMLTransitionView` | va sobre UMLStateView |
| Shallow History | caja | `UMLShallowHistory` | `UMLPseudostateView` |  |
| Simple State | caja | `UMLState` | `UMLStateView` |  |
| Submachine State | caja | `UMLSubmachineState` | `UMLStateView` |  |
| Terminate | caja | `UMLTerminate` | `UMLPseudostateView` |  |
| Transition | linea | `UMLTransition` | `UMLTransitionView` | ejemplo: UMLStateView → UMLPseudostateView |

## Secuencia

`UMLSequenceDiagram` (nombre corto `secuencia`). Especificacion: 17.8 Sequence Diagrams.

Lifelines y los mensajes entre ellas en orden temporal (sincronos, asincronos, respuestas, creacion y destruccion), activaciones, fragmentos combinados (alt, opt, loop, par...), usos de interaccion, invariantes de estado y restricciones de tiempo y duracion.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Async Message | linea | `UMLAsyncMessage` | `UMLSeqMessageView` | ejemplo: UMLLinePartView → UMLEndpointView |
| Async Signal Message | linea | `UMLAsyncSignalMessage` | `UMLSeqMessageView` | ejemplo: UMLLinePartView → UMLEndpointView |
| Combined Fragment | caja | `UMLCombinedFragment` | `UMLCombinedFragmentView` |  |
| Continuation | caja | `UMLContinuation` | `UMLContinuationView` |  |
| Create Message | linea | `UMLCreateMessage` | `UMLSeqMessageView` | ejemplo: UMLLinePartView → UMLEndpointView |
| Delete Message | linea | `UMLDeleteMessage` | `UMLSeqMessageView` | ejemplo: UMLLinePartView → UMLEndpointView |
| Duration Constraint | caja | `UMLDurationConstraint` | `UMLDurationConstraintView` |  |
| Endpoint | caja | `UMLEndpoint` | `UMLEndpointView` |  |
| Found Message | linea | `UMLFoundMessage` | `UMLSeqMessageView` | ejemplo: (sin origen) → UMLLinePartView |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Gate | caja | `UMLGate` | `UMLGateView` |  |
| Interaction Use | caja | `UMLInteractionUse` | `UMLInteractionUseView` |  |
| Lifeline | caja | `UMLLifeline` | `UMLSeqLifelineView` |  |
| Lost Message | linea | `UMLLostMessage` | `UMLSeqMessageView` | ejemplo: UMLLinePartView → (sin destino) |
| Message | linea | `UMLMessage` | `UMLSeqMessageView` | ejemplo: UMLLinePartView → UMLEndpointView |
| Reply Message | linea | `UMLReplyMessage` | `UMLSeqMessageView` | ejemplo: UMLLinePartView → UMLEndpointView |
| Self Message | caja | `UMLSelfMessage` | `UMLSeqMessageView` | va sobre UMLLinePartView |
| State Invariant | caja | `UMLStateInvariant` | `UMLStateInvariantView` | va sobre UMLSeqLifelineView |
| Time Constraint | caja | `UMLTimeConstraint` | `UMLTimeConstraintView` | va sobre UMLSeqMessageView |

## Comunicacion

`UMLCommunicationDiagram` (nombre corto `comunicacion`). Especificacion: 17.9 Communication Diagrams.

La misma interaccion que una secuencia pero ordenada por enlaces: lifelines unidas por conectores con los mensajes numerados encima.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Connector | linea | `UMLConnector` | `UMLConnectorView` | ejemplo: UMLCommLifelineView → UMLCommLifelineView |
| Forward Message | linea | `UMLForwardMessage` | `UMLCommMessageView` | ejemplo: (sin origen) → UMLConnectorView |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Lifeline | caja | `UMLLifeline` | `UMLCommLifelineView` |  |
| Reverse Message | linea | `UMLReverseMessage` | `UMLCommMessageView` | ejemplo: (sin origen) → UMLConnectorView |
| Self Connector | caja | `UMLSelfConnector` | `UMLConnectorView` | va sobre UMLCommLifelineView |

## Tiempos

`UMLTimingDiagram` (nombre corto `tiempos`). Especificacion: 17.11 Timing Diagrams.

Lifelines en un eje de tiempo con sus estados o condiciones, segmentos de tiempo, marcas, mensajes entre segmentos y restricciones de tiempo y duracion.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Duration Constraint | caja | `UMLDurationConstraint` | `UMLDurationConstraintView` |  |
| Lifeline | caja | `UMLLifeline` | `UMLTimingLifelineView` | va sobre UMLTimingFrameView |
| Message | linea | `UMLMessage` | `UMLTimingMessageView` | ejemplo: UMLTimeSegmentView → UMLTimeSegmentView |
| State/Condition | caja | `UMLTimingState` | `UMLTimingStateView` | va sobre UMLTimingLifelineView |
| Time Constraint | caja | `UMLTimeConstraint` | `UMLTimeConstraintView` | va sobre UMLTimeSegmentView |
| Time Segment | caja | `UMLTimeSegment` | `UMLTimeSegmentView` | va sobre UMLTimingStateView |
| Time Tick | caja | `UMLTimeTick` | `UMLTimeTickView` | va sobre UMLTimingFrameView |

## Vista general de interaccion

`UMLInteractionOverviewDiagram` (nombre corto `vista_general_interaccion`). Especificacion: 17.10 Interaction Overview Diagrams.

Un diagrama de actividades cuyos nodos son interacciones o usos de interaccion: muestra el flujo de control entre escenarios.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Control Flow | linea | `UMLControlFlow` | `UMLControlFlowView` | ejemplo: UMLInteractionUseView → UMLInteractionInlineView |
| Decision | caja | `UMLDecisionNode` | `UMLControlNodeView` |  |
| Final | caja | `UMLActivityFinalNode` | `UMLControlNodeView` |  |
| Fork | caja | `UMLForkNode` | `UMLControlNodeView` |  |
| Initial | caja | `UMLInitialNode` | `UMLControlNodeView` |  |
| Interaction (Inline) | react | `UMLInteractionInOverview` | `UMLInteractionInlineView` |  |
| Interaction Use | react | `UMLInteractionUseInOverview` | `UMLInteractionUseView` |  |
| Join | caja | `UMLJoinNode` | `UMLControlNodeView` |  |
| Merge | caja | `UMLMergeNode` | `UMLControlNodeView` |  |

## Flujo de informacion

`UMLInformationFlowDiagram` (nombre corto `flujo_informacion`). Especificacion: 20 Information Flows.

Elementos de informacion y los flujos de informacion entre clasificadores, a un nivel mas abstracto que los mensajes.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Actor | caja | `UMLActor` | `UMLActorView` |  |
| Aggregation | linea | `UMLAggregation` | `UMLAssociationView` | ejemplo: UMLInformationItemView → UMLUseCaseView |
| Association | linea | `UMLAssociation` | `UMLAssociationView` | ejemplo: UMLInformationItemView → UMLUseCaseView |
| Class | caja | `UMLClass` | `UMLClassView` |  |
| Composition | linea | `UMLComposition` | `UMLAssociationView` | ejemplo: UMLInformationItemView → UMLUseCaseView |
| Dependency | linea | `UMLDependency` | `UMLDependencyView` | ejemplo: UMLInformationItemView → UMLPackageView |
| Directed Association | linea | `UMLDirectedAssociation` | `UMLAssociationView` | ejemplo: UMLInformationItemView → UMLUseCaseView |
| Extend | linea | `UMLExtend` | `UMLExtendView` | ejemplo: UMLUseCaseView → UMLUseCaseView |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Generalization | linea | `UMLGeneralization` | `UMLGeneralizationView` | ejemplo: UMLInformationItemView → UMLUseCaseView |
| Include | linea | `UMLInclude` | `UMLIncludeView` | ejemplo: UMLUseCaseView → UMLUseCaseView |
| Information Flow | linea | `UMLInformationFlow` | `UMLInformationFlowView` | ejemplo: UMLInformationItemView → UMLPackageView |
| Information Item | caja | `UMLInformationItem` | `UMLInformationItemView` |  |
| Interface Realization | linea | `UMLInterfaceRealization` | `UMLInterfaceRealizationView` | ejemplo: UMLInformationItemView → UMLInterfaceView |
| Interface | caja | `UMLInterface` | `UMLInterfaceView` |  |
| Package | caja | `UMLPackage` | `UMLPackageView` |  |
| Use Case Subject | caja | `UMLUseCaseSubject` | `UMLUseCaseSubjectView` |  |
| Use Case | caja | `UMLUseCase` | `UMLUseCaseView` |  |

## Entidad-relacion (ERD)

`ERDDiagram` (nombre corto `erd`). Especificacion: no es UML.

Entidades con sus columnas (llave primaria, foranea, tipo) y las relaciones entre ellas con su cardinalidad (pata de gallo).

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Entity | caja | `ERDEntity` | `ERDEntityView` |  |
| Many to Many Relationship | linea | `ERDRelationshipManyToMany` | `ERDRelationshipView` | ejemplo: ERDEntityView → ERDEntityView |
| One to Many Relationship | linea | `ERDRelationshipOneToMany` | `ERDRelationshipView` | ejemplo: ERDEntityView → ERDEntityView |
| One to One Relationship | linea | `ERDRelationship` | `ERDRelationshipView` | ejemplo: ERDEntityView → ERDEntityView |

## Diagrama de flujo

`FCFlowchartDiagram` (nombre corto `flowchart`). Especificacion: no es UML.

Notacion clasica de diagramas de flujo: terminador, proceso, decision, datos, documento, base de datos, conectores y flujos.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Alternate Process | caja | `FCAlternateProcess` | `FCAlternateProcessView` |  |
| Card | caja | `FCCard` | `FCCardView` |  |
| Collate | caja | `FCCollate` | `FCCollateView` |  |
| Connector | caja | `FCConnector` | `FCConnectorView` |  |
| Database | caja | `FCDatabase` | `FCDatabaseView` |  |
| Data | caja | `FCData` | `FCDataView` |  |
| Decision | caja | `FCDecision` | `FCDecisionView` |  |
| Delay | caja | `FCDelay` | `FCDelayView` |  |
| Direct Access Storage | caja | `FCDirectAccessStorage` | `FCDirectAccessStorageView` |  |
| Display | caja | `FCDisplay` | `FCDisplayView` |  |
| Document | caja | `FCDocument` | `FCDocumentView` |  |
| Extract | caja | `FCExtract` | `FCExtractView` |  |
| Flow | linea | `FCFlow` | `FCFlowView` | ejemplo: FCProcessView → FCTerminatorView |
| Internal Storage | caja | `FCInternalStorage` | `FCInternalStorageView` |  |
| Manual Input | caja | `FCManualInput` | `FCManualInputView` |  |
| Manual Operation | caja | `FCManualOperation` | `FCManualOperationView` |  |
| Merge | caja | `FCMerge` | `FCMergeView` |  |
| Multi-Document | caja | `FCMultiDocument` | `FCMultiDocumentView` |  |
| Off-Page Connector | caja | `FCOffPageConnector` | `FCOffPageConnectorView` |  |
| Or | caja | `FCOr` | `FCOrView` |  |
| Predefined Process | caja | `FCPredefinedProcess` | `FCPredefinedProcessView` |  |
| Preparation | caja | `FCPreparation` | `FCPreparationView` |  |
| Process | caja | `FCProcess` | `FCProcessView` |  |
| Punched Tape | caja | `FCPunchedTape` | `FCPunchedTapeView` |  |
| Sort | caja | `FCSort` | `FCSortView` |  |
| Stored Data | caja | `FCStoredData` | `FCStoredDataView` |  |
| Summing Junction | caja | `FCSummingJunction` | `FCSummingJunctionView` |  |
| Terminator | caja | `FCTerminator` | `FCTerminatorView` |  |

## Flujo de datos (DFD)

`DFDDiagram` (nombre corto `dfd`). Especificacion: no es UML.

Entidades externas, procesos, almacenes de datos y los flujos de datos entre ellos.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Data Flow | linea | `DFDDataFlow` | `DFDDataFlowView` | ejemplo: DFDExternalEntityView → DFDProcessView |
| Data Store | caja | `DFDDataStore` | `DFDDataStoreView` |  |
| External Entity | caja | `DFDExternalEntity` | `DFDExternalEntityView` |  |
| Process | caja | `DFDProcess` | `DFDProcessView` |  |

## BPMN

`BPMNDiagram` (nombre corto `bpmn`). Especificacion: no es UML (BPMN 2.0, OMG).

Procesos de negocio: eventos, tareas, subprocesos, compuertas, objetos y almacenes de datos, carriles y pools, flujos de secuencia y de mensajes, coreografias y conversaciones.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Ad-Hoc Sub Process | caja | `BPMNAdHocSubProcess` | `BPMNAdHocSubProcessView` |  |
| Association | linea | `BPMNAssociation` | `BPMNAssociationView` | ejemplo: BPMNTaskView → BPMNGatewayView |
| Boundary Event | caja | `BPMNBoundaryEvent` | `BPMNEventView` | va sobre BPMNTaskView |
| Business Rule Task | caja | `BPMNBusinessRuleTask` | `BPMNTaskView` |  |
| Call Activity | caja | `BPMNCallActivity` | `BPMNCallActivityView` |  |
| Call Conversation | caja | `BPMNCallConversation` | `BPMNConversationView` |  |
| Choreography Task | caja | `BPMNChoreographyTask` | `BPMNChoreographyTaskView` |  |
| Conversation Link | linea | `BPMNConversationLink` | `BPMNConversationLinkView` | ejemplo: BPMNTaskView → BPMNGatewayView |
| Conversation | caja | `BPMNConversation` | `BPMNConversationView` |  |
| Data Association | linea | `BPMNDataAssociation` | `BPMNDataAssociationView` | ejemplo: BPMNTaskView → BPMNGatewayView |
| Data Input | caja | `BPMNDataInput` | `BPMNDataInputView` |  |
| Data Object | caja | `BPMNDataObject` | `BPMNDataObjectView` |  |
| Data Output | caja | `BPMNDataOutput` | `BPMNDataOutputView` |  |
| Data Store | caja | `BPMNDataStore` | `BPMNDataStoreView` |  |
| End Event | caja | `BPMNEndEvent` | `BPMNEventView` |  |
| Gateway (Complex) | caja | `BPMNComplexGateway` | `BPMNGatewayView` |  |
| Gateway (Event-Based) | caja | `BPMNEventBasedGateway` | `BPMNGatewayView` |  |
| Gateway (Exclusive) | caja | `BPMNExclusiveGateway` | `BPMNGatewayView` |  |
| Gateway (Inclusive) | caja | `BPMNInclusiveGateway` | `BPMNGatewayView` |  |
| Gateway (Parallel) | caja | `BPMNParallelGateway` | `BPMNGatewayView` |  |
| Gateway | caja | `BPMNExclusiveGateway` | `BPMNGatewayView` |  |
| Group | caja | `BPMNGroup` | `BPMNGroupView` |  |
| Intermediate Event (Catch) | caja | `BPMNIntermediateCatchEvent` | `BPMNEventView` |  |
| Intermediate Event (Throw) | caja | `BPMNIntermediateThrowEvent` | `BPMNEventView` |  |
| Lane (Vert) | caja | `BPMNLaneVert` | `BPMNLaneView` |  |
| Lane | caja | `BPMNLane` | `BPMNLaneView` |  |
| Manual Task | caja | `BPMNManualTask` | `BPMNTaskView` |  |
| Message Flow | linea | `BPMNMessageFlow` | `BPMNMessageFlowView` | ejemplo: BPMNTaskView → BPMNGatewayView |
| Message Link | linea | `BPMNMessageLink` | `BPMNMessageLinkView` | ejemplo: BPMNTaskView → BPMNGatewayView |
| Message | caja | `BPMNMessage` | `BPMNMessageView` |  |
| Pool (Vert) | caja | `BPMNParticipantVert` | `BPMNPoolView` |  |
| Pool | caja | `BPMNParticipant` | `BPMNPoolView` |  |
| Receive Task | caja | `BPMNReceiveTask` | `BPMNTaskView` |  |
| Script Task | caja | `BPMNScriptTask` | `BPMNTaskView` |  |
| Send Task | caja | `BPMNSendTask` | `BPMNTaskView` |  |
| Sequence Flow | linea | `BPMNSequenceFlow` | `BPMNSequenceFlowView` | ejemplo: BPMNTaskView → BPMNGatewayView |
| Service Task | caja | `BPMNServiceTask` | `BPMNTaskView` |  |
| Start Event | caja | `BPMNStartEvent` | `BPMNEventView` |  |
| Sub Choreography | caja | `BPMNSubChoreography` | `BPMNSubChoreographyView` |  |
| Sub Conversation | caja | `BPMNSubConversation` | `BPMNConversationView` |  |
| Sub Process | caja | `BPMNSubProcess` | `BPMNSubProcessView` |  |
| Task | caja | `BPMNTask` | `BPMNTaskView` |  |
| Text Annotation | caja | `BPMNTextAnnotation` | `BPMNTextAnnotationView` |  |
| Transaction | caja | `BPMNTransaction` | `BPMNTransactionView` |  |
| User Task | caja | `BPMNUserTask` | `BPMNTaskView` |  |

## C4

`C4Diagram` (nombre corto `c4`). Especificacion: no es UML (modelo C4).

Personas, sistemas de software, contenedores y componentes con sus relaciones, en los niveles de contexto, contenedores y componentes del modelo C4.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Component | caja | `C4Component` | `C4ComponentView` |  |
| Container (Database) | caja | `C4ContainerDatabase` | `C4ContainerView` |  |
| Container (Desktop App) | caja | `C4ContainerDesktopApp` | `C4ContainerView` |  |
| Container (Mobile App) | caja | `C4ContainerMobileApp` | `C4ContainerView` |  |
| Container (Web App) | caja | `C4ContainerWebApp` | `C4ContainerView` |  |
| Container | caja | `C4Container` | `C4ContainerView` |  |
| Element | caja | `C4Element` | `C4ElementView` |  |
| Person | caja | `C4Person` | `C4PersonView` |  |
| Relationship | linea | `C4Relationship` | `C4RelationshipView` | ejemplo: C4PersonView → C4SoftwareSystemView |
| Software System | caja | `C4SoftwareSystem` | `C4SoftwareSystemView` |  |

## SysML requisitos

`SysMLRequirementDiagram` (nombre corto `sysml_requisitos`). Especificacion: no es UML (SysML 1.x, OMG).

Requisitos y sus relaciones de derivacion, satisfaccion, verificacion, refinamiento, copia y traza.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Conform | linea | `SysMLConform` | `SysMLConformView` | ejemplo: UMLPackageView → SysMLRequirementView |
| Containment | linea | `UMLContainment` | `UMLContainmentView` | ejemplo: UMLPackageView → SysMLRequirementView |
| Copy | linea | `SysMLCopy` | `SysMLCopyView` | ejemplo: UMLPackageView → SysMLRequirementView |
| DeriveReqt | linea | `SysMLDeriveReqt` | `SysMLDeriveReqtView` | ejemplo: UMLPackageView → SysMLRequirementView |
| Expose | linea | `SysMLExpose` | `SysMLExposeView` | ejemplo: UMLPackageView → SysMLRequirementView |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Package | caja | `UMLPackage` | `UMLPackageView` |  |
| Refine | linea | `SysMLRefine` | `SysMLRefineView` | ejemplo: UMLPackageView → SysMLRequirementView |
| Requirement | caja | `SysMLRequirement` | `SysMLRequirementView` |  |
| Satisfy | linea | `SysMLSatisfy` | `SysMLSatisfyView` | ejemplo: UMLPackageView → SysMLRequirementView |
| Stakeholder | caja | `SysMLStakeholder` | `SysMLStakeholderView` |  |
| Verify | linea | `SysMLVerify` | `SysMLVerifyView` | ejemplo: UMLPackageView → SysMLRequirementView |
| Viewpoint | caja | `SysMLViewpoint` | `SysMLViewpointView` |  |
| View | caja | `SysMLView` | `SysMLViewView` |  |

## SysML definicion de bloques

`SysMLBlockDefinitionDiagram` (nombre corto `sysml_bloques`). Especificacion: no es UML (SysML 1.x, OMG).

Bloques, bloques de interfaz, bloques de restriccion y tipos de valor con sus propiedades y relaciones.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Aggregation | linea | `UMLAggregation` | `UMLAssociationView` | ejemplo: SysMLBlockView → SysMLValueTypeView |
| Association | linea | `UMLAssociation` | `UMLAssociationView` | ejemplo: SysMLBlockView → SysMLValueTypeView |
| Block | caja | `SysMLBlock` | `SysMLBlockView` |  |
| Composition | linea | `UMLComposition` | `UMLAssociationView` | ejemplo: SysMLBlockView → SysMLValueTypeView |
| Conform | linea | `SysMLConform` | `SysMLConformView` | ejemplo: SysMLBlockView → SysMLValueTypeView |
| Connector | linea | `SysMLConnector` | `SysMLConnectorView` | ejemplo: SysMLPortView → UMLFrameView |
| Constraint Block | caja | `SysMLConstraintBlock` | `SysMLConstraintBlockView` |  |
| Containment | linea | `UMLContainment` | `UMLContainmentView` | ejemplo: SysMLBlockView → SysMLValueTypeView |
| Dependency | linea | `UMLDependency` | `UMLDependencyView` | ejemplo: SysMLBlockView → SysMLValueTypeView |
| Directed Association | linea | `UMLDirectedAssociation` | `UMLAssociationView` | ejemplo: SysMLBlockView → SysMLValueTypeView |
| Enumeration | caja | `UMLEnumeration` | `UMLEnumerationView` |  |
| Expose | linea | `SysMLExpose` | `SysMLExposeView` | ejemplo: SysMLBlockView → SysMLValueTypeView |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Generalization | linea | `UMLGeneralization` | `UMLGeneralizationView` | ejemplo: SysMLBlockView → SysMLValueTypeView |
| Interface Block | caja | `SysMLInterfaceBlock` | `SysMLInterfaceBlockView` |  |
| Object | caja | `UMLObject` | `UMLObjectView` |  |
| Port | caja | `SysMLPort` | `SysMLPortView` | va sobre SysMLBlockView |
| Signal | caja | `UMLSignal` | `UMLSignalView` |  |
| Stakeholder | caja | `SysMLStakeholder` | `SysMLStakeholderView` |  |
| Value Type | caja | `SysMLValueType` | `SysMLValueTypeView` |  |
| Viewpoint | caja | `SysMLViewpoint` | `SysMLViewpointView` |  |
| View | caja | `SysMLView` | `SysMLViewView` |  |

Sin plantilla (StarUML no los dibuja sin interaccion del usuario en este diagrama):

- Interface Realization: Invalid connection (Interface Realization)

## SysML bloque interno

`SysMLInternalBlockDiagram` (nombre corto `sysml_bloque_interno`). Especificacion: no es UML (SysML 1.x, OMG).

La estructura interna de un bloque: partes, referencias, valores, puertos y conectores.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Connector | linea | `SysMLConnector` | `SysMLConnectorView` | ejemplo: SysMLPartView → UMLFrameView |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Part | caja | `SysMLPart` | `SysMLPartView` |  |
| Port | caja | `SysMLPort` | `SysMLPortView` | va sobre UMLFrameView |
| Reference | caja | `SysMLReference` | `SysMLPartView` |  |
| Value | caja | `SysMLValue` | `SysMLPartView` |  |

## SysML parametrico

`SysMLParametricDiagram` (nombre corto `sysml_parametrico`). Especificacion: no es UML (SysML 1.x, OMG).

Propiedades de restriccion y sus parametros conectados a valores del sistema.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Connector | linea | `SysMLConnector` | `SysMLConnectorView` | ejemplo: SysMLPartView → UMLFrameView |
| Constraint Property | caja | `SysMLConstraintProperty` | `SysMLConstraintPropertyView` |  |
| Frame | caja | `UMLFrame` | `UMLFrameView` |  |
| Part | caja | `SysMLPart` | `SysMLPartView` |  |
| Port | caja | `SysMLPort` | `SysMLPortView` | va sobre UMLFrameView |
| Reference | caja | `SysMLReference` | `SysMLPartView` |  |
| Value | caja | `SysMLValue` | `SysMLPartView` |  |

Sin plantilla (StarUML no los dibuja sin interaccion del usuario en este diagrama):

- Constraint Parameter: Constraint Parameter should be placed in a block or a part

## Wireframe

`WFWireframeDiagram` (nombre corto `wireframe`). Especificacion: no es UML.

Bocetos de pantallas: marcos de ventana, botones, campos, listas, tablas y otros controles.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Avatar | caja | `WFAvatar` | `WFAvatarView` |  |
| Button | caja | `WFButton` | `WFButtonView` |  |
| Checkbox | caja | `WFCheckbox` | `WFCheckboxView` |  |
| Dropdown | caja | `WFDropdown` | `WFDropdownView` |  |
| Frame (Desktop) | caja | `WFDesktopFrame` | `WFDesktopFrameView` |  |
| Frame (Mobile) | caja | `WFMobileFrame` | `WFMobileFrameView` |  |
| Frame (Web) | caja | `WFWebFrame` | `WFWebFrameView` |  |
| Frame | caja | `WFFrame` | `WFFrameView` |  |
| Image | caja | `WFImage` | `WFImageView` |  |
| Input | caja | `WFInput` | `WFInputView` |  |
| Link | caja | `WFLink` | `WFLinkView` |  |
| Panel | caja | `WFPanel` | `WFPanelView` |  |
| Radio | caja | `WFRadio` | `WFRadioView` |  |
| Separator | caja | `WFSeparator` | `WFSeparatorView` |  |
| Slider | caja | `WFSlider` | `WFSliderView` |  |
| Switch | caja | `WFSwitch` | `WFSwitchView` |  |
| Tab List | caja | `WFTabList` | `WFTabListView` |  |
| Tab | caja | `WFTab` | `WFTabView` |  |
| Text | caja | `WFText` | `WFTextView` |  |

## Mapa mental

`MMMindmapDiagram` (nombre corto `mindmap`). Especificacion: no es UML.

Nodos de un mapa mental y sus ramas.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Edge | linea | `MMEdge` | `MMEdgeView` | ejemplo: MMNodeView → MMNodeView |
| Node | caja | `MMNode` | `MMNodeView` |  |

## AWS

`AWSDiagram` (nombre corto `aws`). Especificacion: no es UML.

Arquitectura en Amazon Web Services: grupos, servicios, recursos y flechas.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| AWS Arrow | linea | `AWSArrow` | `AWSArrowView` | ejemplo: AWSGroupView → AWSGenericGroupView |
| AWS Availability Zone | caja | `AWSAvailabilityZone` | `AWSAvailabilityZoneView` |  |
| AWS Callout | caja | `AWSCallout` | `AWSCalloutView` |  |
| AWS General Resource | caja | `AWSGeneralResource` | `AWSGeneralResourceView` |  |
| AWS Generic Group | caja | `AWSGenericGroup` | `AWSGenericGroupView` |  |
| AWS Group | caja | `AWSGroup` | `AWSGroupView` |  |
| AWS Resource | caja | `AWSResource` | `AWSResourceView` |  |
| AWS Security Group | caja | `AWSSecurityGroup` | `AWSSecurityGroupView` |  |
| AWS Service | caja | `AWSService` | `AWSServiceView` |  |

## Google Cloud

`GCPDiagram` (nombre corto `gcp`). Especificacion: no es UML.

Arquitectura en Google Cloud: zonas, productos, servicios y rutas.

| Simbolo | Forma | Elemento | Vista | Notas |
|---|---|---|---|---|
| Path | linea | `GCPPath` | `GCPPathView` | ejemplo: GCPZoneView → GCPUserView |
| Product | caja | `GCPProduct` | `GCPProductView` |  |
| Service | caja | `GCPService` | `GCPServiceView` |  |
| User | caja | `GCPUser` | `GCPUserView` |  |
| Zone | caja | `GCPZone` | `GCPZoneView` |  |
