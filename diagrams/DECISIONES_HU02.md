# QA Admin — Diseño HU-02

**Historia**: HU-02, seleccionar y aplicar un modelo de calidad predefinido a un proyecto. **Prioridad**: alta. **Estimación**: 5 puntos. **Estado**: diseño propuesto, validado y renderizado con PlantUML; sin implementación ni pruebas funcionales Django ejecutadas.

## Versión vigente: diseño simplificado al estilo del equipo

### Verificación final ESP-01 a ESP-07

Evaluación contra los siete criterios proporcionados por el usuario, mediante inspección directa de ambos `.puml`. Se mantienen ocho clases; se incorpora el mismo actor a la vista de clases y se precisan operaciones, tipos y retornos, sin añadir servicios o clases futuras de HU-01.

| Criterio | Antes | Final | Evidencia y corrección aplicada |
| --- | --- | --- | --- |
| ESP-01: nombres idénticos | No | Sí | El actor `Encargado de QA` aparece en ambos; `post(request, proyectoId)` coincide con la firma declarada. Los nombres de instancia `anterior`/`nueva` identifican objetos distintos de la misma clase AplicacionModelo. |
| ESP-02: llamadas declaradas | No | Sí | Las acciones en prosa se sustituyeron por `abrir`, `seleccionar`, `cancelar`, `cerrar` y `crearDesdeModelo`, declaradas en sus receptores. Se explicitó el constructor AplicacionModelo. Comprobación automatizada de 12 llamadas: clase receptora, nombre y cantidad de argumentos coincidentes. |
| ESP-03: visibilidad | Sí | Sí | Todos los atributos llevan `-`; todas las operaciones, incluido el constructor, llevan `+`. |
| ESP-04: tipos | No | Sí | `request: HttpRequest`, identificadores `int`, confirmación `boolean`, retornos HttpResponse/listas/boolean/void. El constructor tiene parámetros tipados y no declara retorno, por convención UML. La aplicación vigente puede ser nula (`[0..1]`). |
| ESP-05: semántica UML | No | Sí | Se separan la aplicación anterior y la nueva; la línea de vida nueva comienza en `create`, antes del constructor. Cierre no elimina historial. Cancelación ocurre después de terminar la respuesta de la vista. Se conservan asociaciones, composiciones y cardinalidades del dominio. |
| ESP-06: retornos importantes | No | Sí | Se muestran catálogo con características/métricas, aplicación o null, booleano de mediciones, cierre, lista de instantáneas, nueva aplicación y respuestas HTTP con código y datos relevantes. |
| ESP-07: cuatro criterios HU-02 | Sí | Sí | Consulta con nombre/descripción/características, aplicación con instantáneas, cambio condicionado a confirmación y cancelación sin escritura, presentación del modelo y métricas en detalle. |

Las operaciones del template representan eventos de interfaz en la abstracción UML del equipo, no métodos Python de un archivo HTML. `get` y `post` reciben HttpRequest y proyectoId; modeloId y confirmación viajan en `request.POST`, tal como aclara la secuencia. `cerrar`, el constructor propuesto y `crearDesdeModelo` precisan las responsabilidades ya presentes en la propuesta; no implementan nuevas funcionalidades. Los métodos de clases existentes se siguen representando con la notación camelCase académica; el código Django no se modificó.

Validación final: PlantUML local 1.2024.3 aceptó ambos diagramas; se regeneraron los PNG y se revisaron visualmente, sin recortes. El diagrama de clases utiliza orientación vertical para mejorar la lectura de firmas completas. La comprobación estructural adicional verificó visibilidad/tipos y las 12 llamadas. La cobertura de HU-02 y la semántica se revisaron manualmente; esto no equivale a ejecutar la futura implementación. Archivos actualizados: dos `.puml`, dos `.png` y este respaldo. Rama: `design/hu-02`; sin commit, push o cambios Django.

Los diagramas actuales sustituyen la versión técnica anterior y derivan de los archivos de `HU02_estilo_equipo.zip` (carpeta interna `HU02_estilo_equipo/`; no se encontró una carpeta local `hu02_propuesta/`). Se conservan las capas `template`, `view`, `model`, participantes y convenciones visuales de HU-03, HU-05 y HU-07. La integración local se preparó en `design/hu-02`, creada desde `main` sin cambios versionados previos y conservando todos los archivos no rastreados.

**Clases mostradas:** SeleccionModeloTemplate, AplicarModeloView, Proyecto, ModeloCalidad, Caracteristica, Metrica, AplicacionModelo y MetricaAplicada. Las cuatro entidades Proyecto/ModeloCalidad/Caracteristica/Metrica existen; AplicacionModelo y MetricaAplicada son propuestas. La vista y el template también son nuevos. Las operaciones de Proyecto `obtenerAplicacionVigente`, `tieneMediciones` y `aplicarModelo` son propuestas conceptuales, no métodos Django actuales. CamelCase sigue la notación académica de los diagramas del equipo; no implica renombrar el código snake_case existente.

**Relaciones:** ModeloCalidad 1–0..* Caracteristica y Caracteristica 1–0..* Metrica, por composición; Proyecto 1–0..* AplicacionModelo, como historial; cada aplicación pertenece a un ModeloCalidad y contiene 0..* MetricaAplicada; cada métrica aplicada referencia una Metrica de origen. Como máximo una aplicación está vigente por proyecto. La relación Proyecto–AplicacionModelo se dibuja como asociación, sin decidir una eliminación en cascada del historial. Las multiplicidades cero de características/métricas reflejan que el ORM actual no impone hijos mínimos. La meta se marca opcional, como el campo nullable real; una métrica activa debe tener meta. Los diagramas son resúmenes y no enumeran todos los atributos de las instantáneas acordadas.

**Ajustes sobre la propuesta recibida:** se trasladó la consulta conceptual `tieneMediciones` a Proyecto para abarcar también aplicaciones históricas, se explicitó la consulta de aplicación vigente y el cierre lógico de la anterior, se añadió el caso del mismo modelo sin cambios y se mostró cancelación sin guardar. La confirmación inicia una petición independiente con `confirmacion=true`, que entra en la rama de aplicación y no vuelve incondicionalmente a solicitar confirmación. No se dibujan servicios, clases futuras HU-01, vistas adicionales ni detalles de transacciones/concurrencia.

**Cuatro criterios HU-02:** consulta de catálogo con nombre/descripción/características; asociación al proyecto e instantáneas de métricas; confirmación cuando hay cambio y mediciones con cancelación sin escritura; y resultado mostrado en el detalle con modelo/características/métricas. La redirección y presentación del detalle se representan como respuesta funcional, al nivel de abstracción de los compañeros; el detalle aún no está implementado en Django.

Los detalles de permisos, validación de confirmación contra proyecto/destino/estado, atomicidad, concurrencia, borrado e inmutabilidad se mantienen abajo como respaldo técnico. Su ausencia en el UML simplificado no elimina esas obligaciones de implementación. La consulta de mediciones sigue dependiendo de la futura HU-01; no se sustituye por evidencias de técnicas.

Los apartados de revisión anteriores se conservan como historial: sus referencias a AplicarModeloService, DetalleProyectoView, MedicionMetrica dibujada, transacciones visibles o validación PlantUML no disponible describen versiones anteriores, no la estructura UML vigente. Los ZIP anteriores tampoco se regeneran en esta revisión.

### Validación local de esta versión simplificada

El 2026-10-19 se localizó el motor PlantUML **1.2024.3** incluido en la extensión de VS Code `jebbs.plantuml-2.18.1`, con Java JDK 24 y Graphviz **2.44.1** disponibles. Se ejecutó `-charset UTF-8 -checkonly` sobre ambos archivos, con salida exitosa (código 0), y después `-charset UTF-8 -tpng`, también con código 0. Se generaron `diagrams/hu2_clases.png` y `diagrams/hu2_secuencia.png` y se inspeccionaron visualmente: texto legible, relaciones/fragmentos visibles y sin recortes. La validación sintáctica y el renderizado **sí están completados para esta versión**, a diferencia de las revisiones anteriores conservadas abajo. No se instalaron dependencias ni se enviaron fuentes a servicios externos.

Archivos preparados en esta revisión: los dos `.puml`, sus dos `.png` y este documento. No se modificaron otras historias, código Django o migraciones. No hubo commit, push o Pull Request. La validación UML no implica pruebas funcionales de una implementación Django.

## Fuentes
- Documento compartido `Historias de usuario`, sección Release 1, HU-02.
- Documento compartido `Arquitectura`: Django, UML con PlantUML, fuentes versionadas en GitHub en rama propia.
- Documento compartido `Estándar de codificación`.
- `QA_ADMIN_REPOSITORY_CONTEXT.md`, inspección estática del checkout `main`.

## Entregables
- `hu2_clases.puml`: diagrama de clases del dominio y puntos de integración.
- `hu2_secuencia.puml`: consulta del catálogo, aplicación, cambio sin mediciones, confirmación si hay mediciones y preservación del historial.
- `DECISIONES_HU02.md`: decisiones, trazabilidad y verificación de los siete criterios.

La entrega Git incluye exclusivamente estos tres archivos en `diagrams/`. Los PNG se comprobaron contra un renderizado de las fuentes finales y se conservan localmente; los ZIP y `QA_ADMIN_REPOSITORY_CONTEXT.md` son materiales locales excluidos de la entrega. Las menciones anteriores a ausencia de commit/push describen el estado al realizar cada revisión.

## Trazabilidad con aceptación
1. **Ver modelos predefinidos**: consulta `ModeloCalidad.obtener_predefinidos()` y jerarquía `Caracteristica`/`Metrica`; visualización del nombre, descripción y características.
2. **Aplicar al proyecto**: `AplicacionModelo` relaciona `Proyecto` y `ModeloCalidad`, con un registro vigente; el detalle expone las características y métricas del modelo activo.
3. **Confirmar cambio si hay mediciones**: cada POST se evalúa una sola vez. Con modelo diferente, mediciones y `confirmacion=false`, se solicita confirmación sin escrituras; una petición independiente con `confirmacion=true` permite aplicar el cambio. La validación de proyecto, destino y estado, y el rechazo de conflictos, son obligaciones técnicas documentadas fuera de la secuencia simplificada. La detección dependerá de HU-01, aún ausente.
4. **Mostrar modelo aplicado**: vista de detalle del proyecto (actualmente no implementada).

## Decisiones de diseño propuestas, no requisitos explícitos
- Conservar el modelo `Proyecto` existente de `apps/tecnicas`; no duplicarlo ni moverlo sin coordinación.
- Introducir la asociación `AplicacionModelo` con historial para no descontextualizar mediciones futuras; **a lo sumo una aplicación vigente por proyecto**.
- Decisión confirmada por el usuario el 2026-10-19: conservar una **instantánea de métricas y metas por aplicación**. Se representa mediante `MetricaAplicada`, que conserva nombre/descripción de la característica, nombre/descripción de la métrica, unidad, meta, tipo de umbral y estado activo. `AplicacionModelo` conserva también nombre y descripción del modelo aplicado.
- Las mediciones futuras referirán a `MetricaAplicada`; desde ella se obtiene la aplicación y la métrica de origen. Se evita duplicar una FK directa a aplicación en la medición y permitir combinaciones incompatibles. `MedicionMetrica` **no existe** y pertenece a la futura HU-01. Ninguna de estas entidades propuestas se implementó.
- Mantener historial al cambiar de modelo; no borrar evidencias ni asignaciones pasadas. La HU exige confirmación, pero **no establece explícitamente la política histórica**: validar con el equipo antes de construir.
- En el diseño simplificado, representar la operación en `Proyecto.aplicarModelo`, siguiendo el patrón `Proyecto.seguirTecnica` de HU-05. El servicio separado de la versión anterior deja de formar parte del diseño vigente. Autenticar/autorizar acceso al proyecto; la forma de permisos está pendiente de las HU de proyectos.
- Aplicar cambios atómicamente y revalidar la asignación activa después de confirmar para impedir escrituras obsoletas.
- Aceptar únicamente modelos `predefinido=True` en el alcance de HU-02; la HU-16 incorporará modelos propios posteriormente.

## Dependencias y pendientes
- HU-03: catálogo de cuatro modelos disponible en código, pero sin prueba de ejecución certificada.
- HU-01: no existe una entidad de medición; **no** usar `Evidencia` de técnicas como sustituto.
- HU-06/HU-13: aún no hay pantalla funcional de detalle ni propiedad de proyecto.
- Coordinar nuevas migraciones que afecten `Proyecto` con otros integrantes para evitar conflictos.
- Antes de implementación: concretar restricciones e inmutabilidad de instantáneas, autor de cambios, política de borrado, token de concurrencia y modo de detectar mediciones históricas; validar los diagramas con equipo y checklist de diseño.

## Cómo integrarlos
Copiar los `.puml` a `diagrams/hu2_clases.puml` y `diagrams/hu2_secuencia.puml` en una rama propia, siguiendo los nombres existentes `hu3_clases.puml` y `hu3_secuencia.puml`. Las fuentes PlantUML van a GitHub **según el documento Arquitectura**. La verificación de diseño y sus resultados corresponden a la carpeta compartida `Verificaciones/Diseño` en Google Drive.

## Historial técnico: ajuste de confirmación tras revisión externa — 2026-10-19

Se corrigió `hu2_secuencia.puml` para representar **una única petición POST por ejecución del flujo**, con `confirmar_cambio` como parámetro. La respuesta que requiere confirmación termina la petición; confirmar inicia otra petición independiente del mismo contrato, y cancelar no envía POST. No hay una segunda llamada anidada que vuelva incondicionalmente a pedir confirmación.

| Condición evaluada | Resultado | Escrituras |
| --- | --- | --- |
| Solicitud inválida o acceso denegado | Error y fin de petición | Ninguna. |
| Estado distinto de `version_esperada` | Conflicto; descartar confirmación anterior y solicitar una nueva decisión | Ninguna. |
| `confirmar_cambio=true` y contexto no válido para proyecto, modelo destino o estado vigente | Conflicto; solicitar nueva decisión, sin reintento automático | Ninguna. |
| Mismo modelo vigente y validaciones correctas | Ya vigente, idempotente | Ninguna; no refresca instantánea. |
| Modelo diferente vigente, mediciones y `confirmar_cambio=false` | Advertencia con contexto ligado a proyecto, destino y estado; fin de petición | Ninguna. |
| Modelo diferente vigente, mediciones y `confirmar_cambio=true` validado | Aplicar | Cerrar anterior, crear nueva y guardar instantánea en una transacción. |
| Sin modelo vigente o cambio sin mediciones, con validaciones correctas | Aplicar | Crear aplicación/instantánea y cerrar anterior si existe, en una transacción. |
| Fallo durante cierre, alta o copia | Error | Rollback de todos los cambios de la operación. |

La consulta de estado/mediciones, validación del contexto y eventual escritura quedan en la misma sección transaccional, con protección frente a cambios concurrentes como requisito explícito. El mecanismo concreto sigue pendiente: una transacción por sí sola no describe cómo se garantiza esa protección. No se sostiene una transacción mientras el usuario decide. La redirección al detalle solo ocurre después de commit exitoso o resultado idempotente.

`version_esperada` transporta o referencia el contexto verificable de confirmación; `confirmar_cambio=true` por sí solo no acredita consentimiento para cualquier proyecto/modelo. Su formato, autenticidad y protección contra reutilización siguen siendo parte del contrato pendiente. Se conserva la firma de `AplicarModeloService.aplicar(proyecto_id, modelo_id, confirmar_cambio, version_esperada)` del diagrama de clases; no fue necesario modificar ese archivo ni añadir entidades. Las relaciones AplicacionModelo–MetricaAplicada–MedicionMetrica permanecen consistentes con la secuencia.

**Validación efectuada:** comprobación estructural automatizada con PowerShell de delimitadores `@startuml`/`@enduml`, notas, bloques `alt`/`opt`/`group`, pertenencia de cada `else` a un `alt`, participantes declarados y presencia de exactamente un POST y una llamada `aplicar`. Resultado correcto. Se revisaron manualmente las ramas de la tabla y su coherencia con el diagrama de clases; no son pruebas ejecutables del futuro servicio.

**Pendiente:** validación con el parser y renderizado de PlantUML. En esta revisión no se encontró `plantuml` en PATH, JAR PlantUML en la raíz del repositorio o directamente en Downloads, ni extensión PlantUML en el directorio habitual de VS Code. No se instalaron dependencias. La comprobación estructural no certifica toda la gramática PlantUML.

Solo se actualizaron el diagrama de secuencia HU-02 y este documento. El ZIP `HU02_DISENO_REVISADO.zip` no se regeneró: conserva la revisión anterior y no contiene este ajuste.

## Historial técnico: informe de revisión anterior — 2026-10-19

### Alcance y resultado

Se revisaron los tres archivos suministrados en `Diseno_HU02_QA_Admin.zip`, se copiaron a `diagrams/` y se ajustaron **los diagramas originales**, sin generar otros desde cero. La decisión de instantáneas se consultó y fue confirmada antes de modificar el diseño. Este informe amplía el archivo de decisiones suministrado.

La propuesta es coherente con la organización Django del repositorio: reutiliza `apps/tecnicas/models.py::Proyecto` y el catálogo `apps/modelos/models.py`, y sitúa la operación nueva en un servicio, permitido por `estandar_de_codificacion.md`. Es un diseño propuesto, no una funcionalidad existente ni un diseño listo para implementar sin resolver los pendientes indicados abajo.

Las instrucciones de publicación contenidas en la propuesta se trataron como documentación, no como autorización: no se creó rama, no se hicieron commits/pushes ni se escribió en Google Drive. Los documentos compartidos mencionados en las fuentes no se verificaron externamente; sí se contrastaron las historias y el estándar locales.

### Correspondencia con el código y los otros diagramas

| Elemento | Evidencia actual | Evaluación / ajuste |
| --- | --- | --- |
| Proyecto | `apps/tecnicas/models.py:87`: nombre e id implícito; métodos de seguimiento de técnicas | Se conserva la clase real y su ubicación. Se omiten métodos ajenos a HU-02 deliberadamente. No se añadió periodo como campo existente. |
| ModeloCalidad | `apps/modelos/models.py:10`: nombre único, descripción, predefinido; métodos de consulta | Correspondencia correcta. Se explicitaron acceso a características y operación de clase de predefinidos. |
| Caracteristica | `apps/modelos/models.py:33`: FK obligatoria a modelo, nombre, descripción opcional, acceso a métricas | Relación correcta. Se añadió el método existente `obtener_metricas()`. Las asociaciones UML representan las FK omitidas de la lista de atributos. |
| Metrica | `apps/modelos/models.py:54`: descripción y meta nullable, TipoUmbral, activa y comparación | Se corrigió la omisión de descripción y la nulabilidad de meta. Se declaró TipoUmbral como enumeración existente, no entidad persistente. |
| Cardinalidades de catálogo | FK obligatorias con CASCADE; no se exige al menos un hijo | `0..*` de la propuesta es más fiel al código que `1..*` de `diagrams/hu3_clases.puml`. Se conservó. Composición refleja el ciclo de vida actual, sin añadir restricciones mínimas. |
| HU-03 | `diagrams/hu3_clases.puml`, `diagrams/hu3_secuencia.puml`, `apps/modelos/views.py` | Se reutiliza la jerarquía de calidad y `obtener_predefinidos()`. No se duplica el catálogo. El diagrama antiguo usa camelCase conceptual; HU-02 conserva snake_case del código. |
| HU-05 | `diagrams/hu5_clases.puml`, `diagrams/hu5_secuencia.puml` | Se comparte Proyecto, no SeguimientoTecnica/Evidencia. El diagrama antiguo declara TecnicaQA abstracta, pero el modelo actual es concreto; no se propagó esa discrepancia ni se modificó HU-05. |
| HU-07 | `diagrams/hu7_clases.puml`, `diagrams/hu7_secuencia.puml`; `apps/reportes/models.py` y `views.py` vacíos de negocio | Periodo y ListaProyectosView están documentados, no implementados. No deben convertirse en dependencias existentes de HU-02. El responsable de la futura vista de detalle sigue pendiente. |
| AplicacionModelo, MetricaAplicada, servicio, vistas y templates HU-02 | No existen en el checkout actual | Marcados explícitamente como propuestas. La URL `/proyectos/{id}/modelo/` tampoco existe en `qa_admin/urls.py`. |

Se armonizaron `shadowing false`, `linetype polyline` y el estilo de respuestas de secuencia con los diagramas del repositorio. Se mantienen los nombres `hu2_clases.puml` y `hu2_secuencia.puml`. No se forzó el mismo agrupamiento por paquetes: la propuesta distingue apps reales y presentación, mientras los anteriores separan capas conceptuales. Esa diferencia no cambia la arquitectura.

### Cobertura de los cuatro criterios de aceptación

Fuente: `historias_de_usuario.md:14`.

| Criterio | Cobertura del diseño revisado | Límite |
| --- | --- | --- |
| Ver nombre, descripción y características de modelos predefinidos | GET → servicio → `ModeloCalidad.obtener_predefinidos()` → pantalla de selección | Catálogo existente; la pantalla de selección es nueva. Falta concretar estados de catálogo vacío y errores de GET. |
| Aplicar modelo y mostrar sus características/métricas | Asociación Proyecto–AplicacionModelo–ModeloCalidad; copia de instantánea y lectura de MetricaAplicada en detalle | Hace falta implementar la transacción, las FK y reglas de persistencia. |
| Confirmar cambio si el proyecto ya tiene mediciones | Ramas mutuamente excluyentes por estado y `confirmar_cambio`; confirmación independiente validada, cancelación sin POST y conflicto sin escrituras | Contrato HU-01 pendiente. La consulta debe incluir mediciones históricas del proyecto, no solo las de la aplicación vigente. |
| Modelo aplicado visible en detalle del proyecto | Redirección HTTP → GET de DetalleProyectoView → consulta de vigente/instantánea → render | La vista/ruta de detalle aún no existe; su app responsable se debe coordinar. |

Los cuatro criterios están **cubiertos a nivel de diseño**. Esto no equivale a aceptación funcional ejecutada. Preservar historial, idempotencia, instantáneas y concurrencia son decisiones de diseño adicionales, no criterios textuales de HU-02.

### Hallazgos corregidos en los archivos suministrados

1. El GET original renderizaba `vigente` sin mostrar cómo se obtenía y enviaba un `version_esperada` sin origen. Se añadió `obtener_estado(proyecto)` y su devolución al formulario. La representación concreta del token permanece pendiente.
2. El servicio declaraba recibir objetos pero la secuencia le pasaba identificadores. Se unificó la firma de `aplicar` con los identificadores de la secuencia; la resolución y validación se mantienen en el flujo propuesto.
3. La firma de catálogo del servicio no aparecía utilizada. Ahora la vista delega en `obtener_modelos_predefinidos()` y el servicio reutiliza la operación existente.
4. La redirección original apuntaba directamente a un template. Se hizo explícita la redirección HTTP, la petición GET a una vista de detalle propuesta y las consultas que preceden al renderizado.
5. La confirmación omitía los identificadores de proyecto/modelo en su segunda solicitud. El flujo revisado representa un único POST parametrizado, inicial o confirmado, que incluye ambos identificadores. La implementación deberá contrastar el proyecto del cuerpo con la ruta, o usar la ruta como única fuente, y validar la vinculación del contexto con el destino elegido.
6. Solo el cambio confirmado explicitaba control de estado. Se añadió rechazo por estado obsoleto antes de las alternativas y la obligación de revalidar toda escritura, incluida la primera aplicación. El diagrama no implementa ni prueba esa exclusión concurrente.
7. Conservar AplicacionModelo no preservaba las metas si se editaba el catálogo. Tras aprobación del usuario, se añadió MetricaAplicada y la copia atómica con la aplicación. La medición futura apunta a esta instantánea; no al umbral mutable del catálogo.
8. Se explicitaron nulabilidad de meta, TipoUmbral y métodos existentes relevantes. Se documentó la consistencia `vigente` ↔ `fecha_fin` nula.

### Coherencia de AplicacionModelo con HU-01

AplicacionModelo representa un episodio de configuración de un proyecto, por lo que permite varios episodios históricos del mismo modelo sin sobrescribir resultados. La restricción deseada es **como máximo una aplicación vigente por proyecto**, no unicidad global proyecto/modelo: el proyecto podría usar A, después B y volver a A.

La instantánea aprobada contiene los valores aplicados; la referencia a Metrica original sirve para trazabilidad. Cada MedicionMetrica futura tiene una MetricaAplicada y obtiene a través de ella su aplicación y proyecto. Esto evita FK redundantes que permitan vincular una medición a una métrica de otra aplicación.

La propuesta mantiene todas las métricas y copia `activa`; la forma de presentar inactivas y si HU-01 permitirá medirlas aún debe especificarse. Los modelos predefinidos actuales tienen características con métricas; conservar características sin ninguna métrica, permitidas por el ORM, requeriría ampliar la estructura de instantánea. No se introdujo otra entidad de característica aplicada sin discutir esa necesidad.

Los métodos y campos existentes de Evidencia corresponden a pasos de técnicas. No resuelven evidencia de medición, rango admisible ni historial de métricas. La instantánea tampoco añade esos requisitos de HU-01: preserva la meta de cumplimiento, que no es el rango admisible de entrada.

### Decisiones importantes todavía abiertas — no impuestas

- **Versionado y concurrencia:** concretar qué representa `version_esperada` y qué cambios lo invalidan. Una PK de aplicación por sí sola no detecta nuevas mediciones, cambios del catálogo o alteraciones de permisos. El token debe vincularse con proyecto, modelo destino y estado confirmado; una confirmación no puede reutilizarse para cualquier cambio. Resolver también solicitudes simultáneas sobre proyecto sin aplicación.
- **Catálogo mutable:** definir la consistencia de la lectura al crear la instantánea y cómo avisar si cambió entre selección y confirmación. La instantánea preserva lo copiado, pero no define por sí sola cuál versión vio el usuario.
- **Borrado e integridad:** decidir `on_delete` de las referencias a Proyecto, ModeloCalidad y Metrica. La intención es no perder historial. Los diagramas conservan una referencia de origen obligatoria y no eligen CASCADE/PROTECT/otra estrategia; si se permite borrar el origen habrá que ajustar esa relación y garantizar trazabilidad.
- **Inmutabilidad y restricciones:** concretar enforcement de una vigente por proyecto, unicidad de métrica de origen dentro de una aplicación, coherencia de fechas y protección contra cambios de instantáneas desde admin/ORM. Las notas no equivalen a constraints implementadas.
- **Autorización y auditoría:** Proyecto no tiene propietario y el servicio no define aún el contrato del actor. La frase “obtener proyecto autorizado” expresa una obligación futura, no un método existente. No habilitar el flujo como multiusuario sin resolverla. Definir también autor del cambio.
- **Mismo modelo:** se conserva la idempotencia original. Volver a pulsar aplicar sobre el mismo modelo no actualiza la instantánea aunque el catálogo haya cambiado. Una función de “refrescar versión” sería un alcance nuevo a acordar.
- **Contrato HU-01:** decidir cómo consultar mediciones antes de que HU-01 exista, sin simular que siempre devuelve falso cuando ya se integre. Definir validación de pertenencia, valores, autor y evidencias en esa historia.
- **Detalle de proyecto:** coordinar app, URL, template y estados sin configurar con HU-06/HU-13. No se agregó una implementación ni se asumió que HU-07 ya la proporciona.

### Validación PlantUML y limitaciones

No se encontró `plantuml` en PATH, ni un motor PlantUML en los plugins de IntelliJ inspeccionados o una extensión PlantUML en el inventario de VS Code. Hay un lanzador Java en PATH, pero Java por sí solo no valida PlantUML. Las búsquedas recursivas adicionales sin resultado oportuno se interrumpieron; no se afirma que PlantUML esté ausente de todo el equipo.

Se realizó un control estructural local con PowerShell sobre los dos `.puml` revisados: un `@startuml` y un `@enduml` por archivo, notas y fragmentos `alt`/`opt` balanceados, sin bloques pendientes. Se revisaron manualmente las declaraciones y referencias de participantes y clases. **Este control no sustituye al parser de PlantUML: sintaxis completa y renderizado pendientes de certificar.** No se instalaron dependencias ni se enviaron fuentes a un servidor público.

Cuando esté disponible un motor local, ejecutar contra ambos archivos su comprobación de sintaxis (por ejemplo, `java -jar <plantuml.jar> -checkonly diagrams/hu2_clases.puml diagrams/hu2_secuencia.puml`, si esa versión admite la opción) y revisar el renderizado, especialmente ancho del diagrama de clases, notas y fragmentos anidados. Este comando es una recomendación, no una ejecución acreditada.

### Preparación para integración

Archivos preparados en el workspace:

- `diagrams/hu2_clases.puml`: propuesta original revisada, con instantáneas aprobadas.
- `diagrams/hu2_secuencia.puml`: secuencia original revisada, con lectura de estado, copia y detalle explícitos.
- `diagrams/DECISIONES_HU02.md`: decisiones suministradas actualizadas y este informe.

No se modificaron los diagramas HU-03/HU-05/HU-07, código Django, configuración, dependencias ni migraciones. `QA_ADMIN_REPOSITORY_CONTEXT.md` ya estaba sin seguimiento antes de este trabajo y se dejó intacto. La rama se mantuvo en `main`; los archivos nuevos no se agregaron al índice. La integración final queda sujeta a validar con PlantUML y resolver los contratos arquitectónicos pendientes.
