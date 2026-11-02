# Cambios en los diagramas de clases — Fase 1 y cierre de puntos abiertos

**Fecha:** 2026-11-02  
**Alcance:** diagramas de clases de HU-01 a HU-07, E-R general y modelo
relacional formal.  
**Fuera de alcance:** diagramas de secuencia, código Django y migraciones.  
**Resultado:** siete diagramas de clases (se crean `hu1_clases.puml` y
`hu4_clases.puml`), E-R y relacional actualizados, PNG de verificación y este
documento.

---

## 1. Punto de partida y fuentes de verdad

La fase anterior corrigió cinco diagramas de clases y dejó cuatro puntos
abiertos en la sección 3.9. En esta fase se cierran esos puntos y se crean los
diagramas de clases que faltaban.

Las fuentes de verdad del diseño quedan actualizadas y siguen siendo:

| Archivo | Papel |
|---|---|
| `e-r.puml` | E-R general del MVP, notas de negocio y reglas de cálculo. |
| `diag-realacional.puml` | Modelo relacional formal, claves y restricciones. |
| `clases/hu6_clases.puml` | Diseño vigente de HU-06; se alinea con las nuevas relaciones. |
| `secuencia/hu6_secuencia_*.puml` | Flujos de HU-06. No se tocaron en esta fase. |

Los diagramas de secuencia **no se modificaron**. Todo cambio pendiente en
ellos se lista en la sección 6.

> `e-r.puml` y `diag-realacional.puml` viven ahora en la raíz de
> `QA-Admin/diagrams_corregidos/`. Los diagramas de clases vigentes están en
> `clases/` y los de secuencia en `secuencia/` dentro de `diagrams_corregidos/`.

---

## 2. Modelo canónico adoptado

### 2.1 Paquetes

| Paquete | Clases |
|---|---|
| `reportes.model` | `Persona`, `Proyecto`, `MiembroProyecto` |
| `modelos.model` | `ModeloCalidad`, `Caracteristica`, `Metrica`, `ModeloMetrica`, `ModeloAplicado`, `MetricaAplicada`, `RevisionMetrica` |
| `tecnicas.model` | `TecnicaQA`, `Paso`, `SeguimientoTecnica`, `SeguimientoPaso`, `Evidencia` |

`Proyecto` vive en `reportes.model` en todos los diagramas. En PlantUML los
paquetes con punto se dibujan anidados; por eso el PNG muestra `reportes` >
`model`, que equivale a `reportes.model`.

### 2.2 Relaciones canónicas

| Relación | Cardinalidad | Origen |
|---|---|---|
| `Persona` – `MiembroProyecto` | 1 : 0..* | E-R / relacional |
| `Proyecto` – `MiembroProyecto` | 1 : 0..* | E-R / relacional |
| `Caracteristica` – `Metrica` | 1 : 0..* | E-R / relacional |
| `ModeloCalidad` – `ModeloMetrica` | 1 : 0..* | E-R / relacional |
| `Metrica` – `ModeloMetrica` | 1 : 0..* | E-R / relacional |
| `Proyecto` – `ModeloAplicado` | 1 : 0..* | Historial de aplicaciones |
| `ModeloCalidad` – `ModeloAplicado` | 1 : 0..* | E-R / relacional |
| `ModeloAplicado` – `MetricaAplicada` | 1 : 1..* | Instantánea de la aplicación |
| `Metrica` – `MetricaAplicada` | 1 : 0..* | Identidad estable de la métrica |
| `MetricaAplicada` – `RevisionMetrica` | 1 : 0..* | Medición contra la instantánea |
| `MiembroProyecto` – `RevisionMetrica` | 1 : 0..* | Autor de la revisión |
| `Proyecto` – `SeguimientoTecnica` | 1 : 0..* | E-R / relacional |
| `TecnicaQA` – `SeguimientoTecnica` | 1 : 0..* | E-R / relacional |
| `TecnicaQA` – `Paso` | 1 : 1..* | Detalle HU-04/HU-12 |
| `SeguimientoTecnica` – `SeguimientoPaso` | 1 : 1..* | Detalle HU-05/HU-11 |
| `Paso` – `SeguimientoPaso` | 1 : 0..* | Detalle HU-05/HU-12 |
| `SeguimientoPaso` – `Evidencia` | 1 : 0..1 | Evidencia por paso (HU-10) |
| `MiembroProyecto` – `Evidencia` | 1 : 0..* | Autor de la evidencia |

**Regla de aplicación vigente:** un proyecto puede tener varias
`ModeloAplicado` a lo largo del tiempo, pero como máximo una con
`vigente = true`. La restricción se representa en el relacional con un índice
único parcial y se valida al aplicar el modelo.

---

## 3. Decisiones de diseño

### 3.1 `Proyecto` en `reportes.model` (se mantiene)

`Proyecto` se declara en `reportes.model` en todos los diagramas. Las apps
`modelos` y `tecnicas` lo referencian; no se duplica ni se mueve a otra app.

### 3.2 El periodo es un estado derivado, no una entidad (se mantiene)

`Proyecto` conserva `fecha_inicio` y `fecha_fin`. `periodo()` devuelve
`Futuro`, `Activo` o `Terminado`; no existe la clase `Periodo` ni se guarda el
estado en la base de datos.

### 3.3 Historial de aplicaciones e instantáneas (punto 3.9.1 resuelto)

**Problema:** la fase 1 eliminó el historial de aplicaciones y la instantánea
de métricas al adoptar `ModeloAplicado` con cardinalidad 0..1. Eso impedía
conservar el progreso cuando se cambia de modelo y las métricas son comunes.

**Decisión:** se restaura el historial y la instantánea con nombres canónicos:

- `ModeloAplicado`: una fila por aplicación, con `fecha_aplicacion`,
  `fecha_cierre` y `vigente`. Un proyecto acumula historial; solo una
  aplicación está vigente.
- `MetricaAplicada`: instantánea inmutable de `ModeloMetrica` al aplicar el
  modelo. Copia `umbral`, `tipo_umbral` y `activa`, y referencia la `Metrica`
  de origen. Hay una fila por métrica incluida en el modelo aplicado.
- `RevisionMetrica`: se registra contra una `MetricaAplicada` concreta y
  conserva el autor. No guarda FKs redundantes a `Proyecto` ni a `Metrica`: se
  obtienen a través de la instantánea.

**Cómo se conserva el progreso:**

- La identidad de la métrica es `Metrica.id`; no cambia entre aplicaciones.
- Si una métrica existe en el modelo anterior y en el nuevo, las dos
  instantáneas apuntan a la misma `Metrica`.
- `Metrica.ultima_revision(proyecto)` y `Metrica.ultimo_valor(proyecto)` buscan
  en todas las aplicaciones del proyecto, no solo en la vigente. Así una
  métrica común conserva su último valor medido.
- `Metrica.esta_aceptada(proyecto)` reevalúa ese último valor con el umbral y
  `tipo_umbral` de la instantánea vigente. El `cumple` guardado en cada
  `RevisionMetrica` es el resultado histórico de la instantánea con la que se
  midió; no se reutiliza si el umbral cambió.
- Las revisiones de métricas que no están en el nuevo modelo no se borran:
  quedan en el historial, pero dejan de contar para el seguimiento vigente.
- Cambiar de modelo cierra la aplicación anterior (`vigente = false`,
  `fecha_cierre`) y crea una nueva con su instantánea, en una transacción.

**Restricciones:**

- `UNIQUE(proyecto_id) WHERE vigente = true` (índice único parcial).
- `CHECK (vigente = (fecha_cierre IS NULL))`.
- `UNIQUE(modelo_aplicado_id, metrica_id)` en `MetricaAplicada`.
- La aplicación debe generar al menos una `MetricaAplicada`; se valida al
  aplicar el modelo.

### 3.4 Dirección del umbral (punto 3.9.3 resuelto)

`ModeloMetrica` incorpora `tipo_umbral` con el enum `TipoUmbral`:

- `MINIMO`: la métrica cumple si `valor >= umbral`.
- `MAXIMO`: la métrica cumple si `valor <= umbral`.

`MetricaAplicada` copia `tipo_umbral` en la instantánea para que el cálculo
histórico no dependa del catálogo actual. `RevisionMetrica.calcular_cumple()`
usa la instantánea, no `Metrica` ni `ModeloMetrica` directamente.

El E-R y el relacional incorporan `tipo_umbral`; ya no queda como pendiente de
HU-01.

### 3.5 Características del modelo y cálculo del seguimiento (punto 3.9.4 resuelto)

**Decisión:** las características forman parte del modelo de forma derivada.

- `Caracteristica` sigue siendo un catálogo global: agrupa métricas y no tiene
  FK directa a `ModeloCalidad`.
- `ModeloCalidad` incluye métricas mediante `ModeloMetrica`; cada `Metrica`
  pertenece a una `Caracteristica`.
- Las características de un modelo son las características distintas de las
  métricas activas incluidas en su `ModeloAplicado` vigente. No se guarda una
  tabla intermedia modelo–característica.

**Cálculo del seguimiento por característica (definido en HU-01):**

```
seguimiento(caracteristica, proyecto) =
    (métricas aceptadas en la característica /
     métricas activas de la característica en el modelo vigente) * 100
```

- Una métrica está aceptada si su última medición del proyecto cumple con el
  umbral y `tipo_umbral` de la instantánea vigente. No se reutiliza el `cumple`
  histórico si el umbral cambió.
- Se conserva el último valor aunque la métrica venga de una aplicación
  anterior. Si la métrica es común, su progreso se conserva al cambiar de
  modelo.
- Las métricas inactivas en la instantánea no entran en el denominador.
- El resultado es un porcentaje de 0 a 100 y no se almacena; se calcula.

La operación queda explícita en `hu1_clases.puml`:
`Caracteristica.metricas_aceptadas(proyecto)` y
`Caracteristica.calcular_seguimiento(proyecto)`.

Si el equipo decide que cada modelo tenga características propias (no
compartidas), el cambio debe empezar por el E-R y el relacional añadiendo la
FK correspondiente; no se introduce solo en un diagrama de clases.

### 3.6 Evidencia por paso (punto 3.9.2 resuelto)

**Decisión:** la evidencia se mantiene a nivel de paso y tiene FK explícita.

```
SeguimientoPaso 1 ── 0..1 Evidencia
Evidencia * ── 1 MiembroProyecto : autor
```

- `Evidencia.seguimiento_paso_id` es obligatorio y único: como máximo una
  evidencia por paso.
- Se elimina la asociación directa `SeguimientoTecnica – Evidencia`. La
  técnica llega a sus evidencias a través de sus `SeguimientoPaso`.
- Un paso no se marca completado sin evidencia. El autor de la evidencia es el
  autor del paso.
- `Evidencia` exige enlace o archivo. `SeguimientoTecnica` conserva
  `tiene_evidencias_registradas()` como operación derivada que recorre sus
  pasos.

El E-R y el relacional incluyen `Paso` y `SeguimientoPaso` para que la relación
sea trazable. `hu5_clases.puml` y `hu1_clases.puml` reflejan la misma regla.

### 3.7 `RevisionMetrica`: validación y cálculo

`RevisionMetrica` conserva:

- `valor`, `fecha`, `enlace`, `archivo` y `cumple`.
- FK a `MetricaAplicada` y a `MiembroProyecto` (autor).

Reglas:

- `valor`, `fecha` y al menos un enlace o archivo son obligatorios.
- `Metrica.validar_rango(valor)` rechaza valores fuera de
  `valor_min`/`valor_max`.
- `calcular_cumple()` usa `MetricaAplicada.umbral` y
  `MetricaAplicada.tipo_umbral`; el resultado se guarda en `cumple` para
  conservar el resultado histórico.
- El autor debe ser `MiembroProyecto` del mismo proyecto; se valida en
  `clean()`.
- El historial de una métrica se obtiene a través de sus instantáneas; no se
  duplican FKs en la revisión.

### 3.8 Jerarquía del catálogo y cardinalidades

La ruta canónica es:

```
ModeloCalidad 1 ── 0..* ModeloMetrica * ── 1 Metrica * ── 1 Caracteristica
```

- `Caracteristica 1 : 0..* Metrica`.
- `ModeloCalidad 1 : 0..* ModeloMetrica`.
- No hay composición directa `ModeloCalidad *-- Caracteristica`.
- `Metrica` conserva `unidad`, `valor_min` y `valor_max`.
- `ModeloCalidad` conserva `predefinido` por HU-03/HU-09/HU-16.

### 3.9 Notación y alcance de cada diagrama

- Operaciones en `snake_case`.
- Cada diagrama es una vista parcial: muestra las clases necesarias para su
  HU; las clases compartidas conservan paquete y relaciones estructurales.
- Composiciones (`*--`) para hijos propios del agregado; asociaciones (`-->`)
  para referencias entre agregados.
- Las dependencias (`..>`) representan uso desde vistas/templates, no
  relaciones de dominio.

### 3.10 Trazabilidad con los puntos 3.9 de la fase anterior

| Punto 3.9 de la fase anterior | Estado | Dónde se resolvió |
|---|---|---|
| Historial de aplicaciones e instantáneas | **Resuelto** | Decisión 3.3; `ModeloAplicado` 1:0..* y `MetricaAplicada` 1:1..* en E-R, relacional, HU-01 y HU-02. |
| Evidencia por paso con FK a `SeguimientoPaso` | **Resuelto** | Decisión 3.6; `SeguimientoPaso 1:0..1 Evidencia` y FK única en el relacional; HU-05 actualizado. |
| Dirección del umbral | **Resuelto** | Decisión 3.4; `tipo_umbral` en `ModeloMetrica` y `MetricaAplicada`. |
| Características del modelo y cálculo de seguimiento | **Resuelto** | Decisión 3.5; características derivadas y operaciones de cálculo en HU-01. |

---

## 4. Cambios archivo por archivo

### 4.1 `e-r.puml` — E-R general actualizado

| Antes | Después |
|---|---|
| `ModeloAplicado` sin historial ni instantánea. | `ModeloAplicado` con `fecha_aplicacion`, `fecha_cierre`, `vigente`; `MetricaAplicada` como instantánea. |
| `RevisionMetrica` relacionada con `Proyecto` y `Metrica`. | `RevisionMetrica` relacionada con `MetricaAplicada` y `MiembroProyecto`; proyecto y métrica se derivan. |
| Sin `tipo_umbral`. | `ModeloMetrica.tipo_umbral` y `MetricaAplicada.tipo_umbral`, con semántica MINIMO/MAXIMO. |
| Sin `Paso` ni `SeguimientoPaso`. | Se añaden; `Evidencia` se relaciona con `SeguimientoPaso` (1:0..1) y con `MiembroProyecto` como autor. |
| `Metrica` sin `unidad`; `ModeloCalidad` sin `predefinido`. | Se añaden para coincidir con HU-03/HU-09. |
| Nota de características sin cálculo. | Nota con características derivadas y seguimiento calculado. |

### 4.2 `diag-realacional.puml` — modelo relacional actualizado

Se actualizaron tablas, claves y restricciones:

- `modelo_aplicado`: `proyecto_id`, `modelo_calidad_id`, `fecha_aplicacion`,
  `fecha_cierre`, `vigente`; índice único parcial por proyecto vigente.
- `metrica_aplicada`: `modelo_aplicado_id`, `metrica_id`, `umbral`,
  `tipo_umbral`, `activa`; `UNIQUE(modelo_aplicado_id, metrica_id)`.
- `revision_metrica`: `metrica_aplicada_id`, `miembro_proyecto_id`, `valor`,
  `fecha`, `enlace`, `archivo`, `cumple`; check de evidencia.
- `paso`: `tecnica_qa_id`, `orden`, `instruccion`, `evidencia_esperada`;
  `UNIQUE(tecnica_qa_id, orden)`.
- `seguimiento_paso`: `seguimiento_tecnica_id`, `paso_id`, `completado`,
  `comentario`, `fecha_completado`; `UNIQUE(seguimiento_tecnica_id, paso_id)`.
- `evidencia`: `seguimiento_paso_id` (`FK,U`), `miembro_proyecto_id`,
  `enlace`, `archivo`, `fecha_registro`; check de enlace/archivo.

### 4.3 `hu1_clases.puml` — nuevo (HU-01)

Diagrama nuevo con:

- `RevisionMetricaTemplate` y `RegistrarRevisionMetricaView`.
- `Proyecto`, `Persona` y `MiembroProyecto` en `reportes.model`.
- `TipoUmbral`, `ModeloCalidad`, `Caracteristica`, `Metrica`,
  `ModeloMetrica`, `ModeloAplicado`, `MetricaAplicada` y `RevisionMetrica`.
- Relaciones de historial, instantánea, revisión y autoría.
- Operaciones de cálculo:
  `Metrica.ultima_revision(proyecto)`, `Metrica.ultimo_valor(proyecto)`,
  `Metrica.esta_aceptada(proyecto)`,
  `Caracteristica.metricas_aceptadas(proyecto)` y
  `Caracteristica.calcular_seguimiento(proyecto)`.
- Notas con validaciones de valor, fecha, evidencia, rango y autor.

### 4.4 `hu2_clases.puml` — aplicar modelo (HU-02)

| Antes | Después |
|---|---|
| `ModeloAplicado` 0..1 sin historial. | `ModeloAplicado` 0..* con `vigente`, `fecha_aplicacion` y `fecha_cierre`. |
| Sin instantánea. | `MetricaAplicada` con `umbral`, `tipo_umbral` y `activa`; copia desde `ModeloMetrica`. |
| `ModeloMetrica` sin dirección de umbral. | `TipoUmbral` y `ModeloMetrica.tipo_umbral`. |
| Nota: el E-R no modela historial. | Nota: el historial se conserva; cambiar de modelo cierra la aplicación anterior y crea una nueva. |
| `Proyecto` sin historial. | `historial_modelos()`, `modelo_aplicado_vigente()` y `aplicar_modelo()`. |

### 4.5 `hu3_clases.puml` — catálogo de modelos (HU-03)

- Se añade `TipoUmbral` y `ModeloMetrica.tipo_umbral`.
- `ModeloMetrica` expone `evaluar_cumplimiento(valor)`.
- `ModeloAplicado` se muestra con historial (`fecha_aplicacion`, `vigente`).
- Se actualizan las notas: el catálogo no crea aplicaciones; el historial y
  las instantáneas pertenecen a HU-02/HU-01.
- Se mantiene la nota de que las características del modelo se infieren de sus
  métricas.

### 4.6 `hu4_clases.puml` — nuevo (HU-04)

Diagrama nuevo del catálogo de técnicas:

- `CatalogoTecnicasTemplate`, `DetalleTecnicaTemplate`.
- `CatalogoTecnicasView` con listado, filtro por dimensión y dimensiones
  disponibles.
- `DetalleTecnicaView` con consulta de técnica y pasos ordenados.
- `TecnicaQA`, `Paso`, `Dimension` y `TipoControl`.
- Notas con los criterios: 8 técnicas base, dos por dimensión; filtro;
  detalle con objetivo, pregunta clave y evidencia esperada; catálogo de solo
  lectura en HU-04.

### 4.7 `hu5_clases.puml` — catálogo y seguimiento (HU-04/HU-05)

| Antes | Después |
|---|---|
| `SeguimientoTecnica 1 : 0..* Evidencia`. | `SeguimientoPaso 1 : 0..1 Evidencia`; `Evidencia * : 1 MiembroProyecto` autor. |
| `Evidencia` sin validación explícita. | `tiene_enlace_o_archivo()` y `clean()`. |
| `SeguimientoPaso` sin regla de evidencia. | Nota: no se completa sin evidencia; `marcar_completado()` valida. |
| `SeguimientoTecnica.tiene_evidencias_registradas()` sin aclaración. | Se indica que recorre sus pasos. |

### 4.8 `hu6_clases.puml` — seguimiento multi-proyecto (HU-06)

- Se añaden `ModeloCalidad`, `ModeloAplicado`, `MetricaAplicada` y
  `TipoUmbral` al paquete `modelos.model`.
- `RevisionMetrica` se relaciona con `MetricaAplicada` y `MiembroProyecto`;
  proyecto y métrica se derivan.
- `Proyecto → ModeloAplicado` pasa a 1:0..* (historial).
- Notas actualizadas: una aplicación vigente como máximo; cambiar de modelo no
  borra revisiones; `Proyecto.revisiones()` se deriva del historial.

### 4.9 `hu7_clases.puml` — proyectos por periodo (HU-07)

Sin cambios. Se mantiene `Proyecto` en `reportes.model`, `periodo()` derivado y
la ausencia de la entidad `Periodo`.

---

## 5. Verificación contra el criterio de éxito

| Criterio | Estado | Evidencia |
|---|---|---|
| `e-r`, `diag-relacional`, `hu1`, `hu2`, `hu5`, `hu6` y `hu7` ubican `Proyecto` en `reportes`/`reportes.model`. | **Cumplido** | La definición `class Proyecto` solo aparece en `package "reportes.model"` / `package "reportes"`. |
| Ningún diagrama define `Periodo` como entidad. | **Cumplido** | No hay `class Periodo` en los archivos actualizados. |
| Historial de aplicaciones e instantáneas presente. | **Cumplido** | `ModeloAplicado` 1:0..* y `MetricaAplicada` 1:1..* en E-R, relacional, HU-01 y HU-02. |
| Dirección del umbral definida. | **Cumplido** | `tipo_umbral` en `ModeloMetrica` y `MetricaAplicada`; enum `TipoUmbral` en HU-01/HU-02/HU-03/HU-06. |
| Evidencia por paso con FK. | **Cumplido** | `SeguimientoPaso 1:0..1 Evidencia`; `seguimiento_paso_id` único en el relacional; HU-05 actualizado. |
| Características del modelo y cálculo de seguimiento. | **Cumplido** | Características derivadas de las métricas; operaciones de cálculo en HU-01. |
| `RevisionMetrica` con relaciones completas. | **Cumplido** | Se relaciona con `MetricaAplicada` y `MiembroProyecto`; HU-06 actualizado. |
| Diagramas de clases de HU-01 y HU-04 creados. | **Cumplido** | `hu1_clases.puml` y `hu4_clases.puml` con PNG. |
| Diagramas de secuencia sin tocar. | **Cumplido** | Se listan como pendientes en la sección 6. |

---

## 6. Fase 2 completada (diagramas de secuencia)

Estos cambios se ejecutaron en la fase 2 (2026-11-02) y ahora coinciden con el
diseño vigente de clases, E-R y relacional.

| Archivo | Qué se hizo | Estado |
|---|---|---|
| `secuencia/hu1_secuencia.puml` | Creado: registro de revisión de métrica con `MetricaAplicada` (instantánea), `calcular_cumple()`, `esta_aceptada()` y `calcular_seguimiento()`. | Completo |
| `secuencia/hu2_secuencia.puml` | Reemplazados `AplicacionModelo`/`MetricaAplicada`/`obtenerAplicacionVigente()`/`aplicarModelo()` por `ModeloAplicado`, `MetricaAplicada`, `modelo_aplicado_vigente()`, `aplicar_modelo()` y `tiene_mediciones()`. Se mantiene la rama de confirmación y el cierre de la aplicación anterior en transacción. | Completo |
| `secuencia/hu3_secuencia.puml` | Cambiado a `obtener_modelo_metricas()`; por cada `ModeloMetrica` se lee `metrica` → `metrica.caracteristica`; se muestra `tipo_umbral` (MINIMO/MAXIMO). | Completo |
| `secuencia/hu4_secuencia.puml` | Creado: catálogo y detalle de técnicas QA, 8 técnicas, dos por dimensión, filtro por dimensión y detalle con pasos ordenados. | Completo |
| `secuencia/hu5_secuencia.puml` | Separado `reportes.model` (Proyecto) de `tecnicas.model`; evidencia registrada contra `SeguimientoPaso` (no contra `SeguimientoTecnica`) con FK autor `MiembroProyecto`; normalizado a `snake_case`. | Completo |
| `secuencia/hu6_secuencia_*.puml` (5 archivos) | Confirmado que `RevisionMetrica` se obtiene vía `MetricaAplicada`; normalizado `equipoActivo()` a `equipo_activo()`. | Completo |
| `secuencia/hu7_secuencia.puml` | Eliminada la entidad `Periodo`; consulta sobre `Proyecto` filtrada por fechas o por `periodo()`, agrupada y ordenada por `fecha_inicio` descendente. | Completo |

`../diagrams/DECISIONES_HU02.md` ya quedó marcado como documento histórico en
su encabezado, con remisión al diseño vigente de HU-02; no requiere cambios.


### Decisión pendiente sobre eliminación y auditoría

El E-R y el relacional no eligen `on_delete` para `MetricaAplicada`,
`RevisionMetrica`, `ModeloAplicado` ni `Evidencia`. La intención es no perder
historial. Antes de implementar hay que definir:

- si una aplicación histórica se puede borrar o solo cerrar;
- si una métrica aplicada se puede eliminar cuando ya tiene revisiones;
- si la evidencia se puede reemplazar o solo agregar;
- el `on_delete` de cada FK y las restricciones de inmutabilidad.

Estas decisiones no cambian la estructura de clases, pero sí la integridad del
historial.

---

## 7. Diagramas faltantes (estado actual)

| HU | Diagrama | Estado |
|---|---|---|
| HU-01 | Clases de `RevisionMetrica` / evidencia de métrica. | **Creado:** `clases/hu1_clases.puml`. |
| HU-01 | Secuencia de revisión de métrica. | **Creado:** `secuencia/hu1_secuencia.puml`. |
| HU-04 | Clases del catálogo de técnicas. | **Creado:** `clases/hu4_clases.puml`. |
| HU-04 | Secuencia propia del catálogo de técnicas. | **Creado:** `secuencia/hu4_secuencia.puml`. |

---

## 8. Verificación técnica

- **Motor:** PlantUML 1.2024.3 (`jebbs.plantuml-2.18.1`), Java 21.
- **Sintaxis:** `-checkonly` ejecutado sobre los siete `.puml` de clases y
  sobre `e-r.puml`/`diag-realacional.puml`; sin errores (código de salida 0).
- **Renderizado:** PNG generados con `-tpng`. Los de clases están en
  `diags_pngs/clases/`, los de secuencia en `diags_pngs/secuencia/`, y el E-R
  y el relacional en `diags_pngs/` (raíz del proyecto).
- **Auditoría manual:**
  - No hay `class Periodo` en los archivos actualizados.
  - `Proyecto` solo se declara en `reportes.model`/`reportes`.
  - `Evidencia` no tiene asociación directa con `SeguimientoTecnica`; su FK es
    `SeguimientoPaso`.
  - `ModeloAplicado` es 1:0..* desde `Proyecto` y `MetricaAplicada` es 1:1..*
    desde `ModeloAplicado`.
  - `tipo_umbral` aparece en `ModeloMetrica` y `MetricaAplicada`.
  - `RevisionMetrica` se relaciona con `MetricaAplicada` y
    `MiembroProyecto`.
  - Las características conservan la ruta `Metrica → Caracteristica` y el
    cálculo de seguimiento está en HU-01.
- **Sin cambios de código:** no se modificó Django, migraciones, plantillas ni
  base de datos.
- **Fuentes de verdad:** `e-r.puml` y `diag-realacional.puml` se actualizaron
  intencionalmente; `hu6_secuencia_*.puml` no se tocaron.

Comandos usados (desde `QA-Admin/diagrams_corregidos`):

```powershell
java -jar "C:\Users\rodri\.vscode\extensions\jebbs.plantuml-2.18.1\plantuml.jar" `
  -charset UTF-8 -checkonly `
  "clases/hu1_clases.puml" "clases/hu2_clases.puml" "clases/hu3_clases.puml" `
  "clases/hu4_clases.puml" "clases/hu5_clases.puml" "clases/hu6_clases.puml" "clases/hu7_clases.puml"

java -jar "C:\Users\rodri\.vscode\extensions\jebbs.plantuml-2.18.1\plantuml.jar" `
  -charset UTF-8 -tpng -o ../../diags_pngs/clases `
  "clases/hu1_clases.puml" "clases/hu2_clases.puml" "clases/hu3_clases.puml" `
  "clases/hu4_clases.puml" "clases/hu5_clases.puml" "clases/hu6_clases.puml" "clases/hu7_clases.puml"
```
Comandos usados para render de secuencia (desde `QA-Admin/diagrams_corregidos`):

```powershell
java -jar "C:\Users\rodri\.vscode\extensions\jebbs.plantuml-2.18.1\plantuml.jar" `
  -charset UTF-8 -tpng -o ../../diags_pngs/secuencia `
  "secuencia/hu1_secuencia.puml" "secuencia/hu2_secuencia.puml" "secuencia/hu3_secuencia.puml" `
  "secuencia/hu4_secuencia.puml" "secuencia/hu5_secuencia.puml" `
  "secuencia/hu6_secuencia_crear_proyecto.puml" "secuencia/hu6_secuencia_editar_equipo.puml" `
  "secuencia/hu6_secuencia_lista_y_seleccion.puml" "secuencia/hu6_secuencia_tablero.puml" `
  "secuencia/hu6_secuencia_volver_lista.puml" "secuencia/hu7_secuencia.puml"
```
Comandos usados (desde `QA-Admin/diagrams_corregidos`):

```powershell
java -jar "C:\Users\rodri\.vscode\extensions\jebbs.plantuml-2.18.1\plantuml.jar" `
  -charset UTF-8 -checkonly "e-r.puml" "diag-realacional.puml"

java -jar "C:\Users\rodri\.vscode\extensions\jebbs.plantuml-2.18.1\plantuml.jar" `
  -charset UTF-8 -tpng -o ../../diags_pngs/ "e-r.puml" "diag-realacional.puml"
```

---

## 9. Archivos entregados

| Archivo | Contenido |
|---|---|
| `clases/hu1_clases.puml` | Clases de HU-01: revisión de métrica, instantánea, cálculo de cumplimiento y seguimiento por característica. |
| `clases/hu2_clases.puml` | Aplicación de modelo con historial, instantánea y dirección de umbral. |
| `clases/hu3_clases.puml` | Catálogo de modelos con `ModeloMetrica`, `tipo_umbral` y `ModeloAplicado`. |
| `clases/hu4_clases.puml` | Catálogo y detalle de técnicas QA. |
| `clases/hu5_clases.puml` | Catálogo y seguimiento de técnicas con evidencia por paso. |
| `clases/hu6_clases.puml` | Multi-proyecto con historial de aplicaciones e instantáneas. |
| `clases/hu7_clases.puml` | Proyectos por periodo sin entidad `Periodo`. |
| `e-r.puml` | E-R actualizado con historial, instantánea, umbral y evidencia por paso. |
| `diag-realacional.puml` | Relacional actualizado con tablas, FKs y restricciones. |
| `diags_pngs/clases/hu1_clases.png` … `diags_pngs/clases/hu7_clases.png` | Render de verificación de los siete diagramas de clases. |
| `diags_pngs/secuencia/hu1_secuencia.png` … `diags_pngs/secuencia/seq_hu06_05_volver.png` | Render de verificación de los once diagramas de secuencia. |
| `diags_pngs/e-r.png` | Render actualizado del E-R. |
| `diags_pngs/diag_relacional.png` | Render actualizado del relacional. |
| `CAMBIOS_DIAGRAMAS_CLASES.md` | Este documento. |

Los PNG son de verificación local; se pueden regenerar con los comandos de la
sección 8.

---

## 10. Resumen de la fase

- Se cerraron los cuatro puntos abiertos de la sección 3.9:
  historial/instantáneas, evidencia por paso, dirección del umbral y
  características con cálculo de seguimiento.
- Se restauró el historial de aplicaciones con `ModeloAplicado` 1:0..* y la
  instantánea `MetricaAplicada`.
- `RevisionMetrica` ahora se registra contra la instantánea y conserva el
  autor; el progreso de métricas comunes sobrevive al cambio de modelo.
- `Evidencia` tiene FK a `SeguimientoPaso` (1:0..1) y autor
  `MiembroProyecto`.
- `ModeloMetrica` y `MetricaAplicada` incluyen `tipo_umbral`
  (`MINIMO`/`MAXIMO`).
- Las características del modelo se infieren de sus métricas; el seguimiento
  por característica se calcula en HU-01 contando métricas aceptadas.
- Se crearon los diagramas de clases de HU-01 y HU-04.
- **No se modificaron los diagramas de secuencia.** La fase 2 queda pendiente
  de instrucción.
