# QA Admin — Diseño HU-10 (revisión 2)

**Historia**: HU-10, subir la evidencia de que un paso de una TQA ha sido
llevado a cabo. **Prioridad**: alta. **Estimación**: 5 puntos.
**Release**: 2.
**Estado**: diseño rehecho sobre los **diseños corregidos** de
`documentacion-proyecto-calidad/Diseño/Diagramas corregidos/` (02/11/2026).
La construcción existente corresponde al modelo anterior y debe adaptarse
después de integrar `main` (ver sección 8).

## 1. Cambios de esta revisión

La revisión 1 se hizo con el modelo anterior: `Proyecto` en `tecnicas`,
`Evidencia.autor` de texto y una capa de servicio aparte. Los diseños
corregidos del equipo fijan otro modelo y otro estilo, así que esta revisión:

1. Adopta el modelo corregido: `Proyecto`, `Persona` y `MiembroProyecto`
   viven en **reportes**; `tecnicas` los referencia.
2. `Evidencia` guarda **`miembro_proyecto`** (autor) como llave foránea, más
   `enlace`, `archivo` y `fecha_registro`; el comentario opcional vive en
   `SeguimientoPaso.comentario`.
3. Añade `Evidencia.fecha` (fecha declarada por el usuario) porque el criterio
   de aceptación pide capturarla; `fecha_registro` sigue siendo automática.
4. Elimina la capa de servicio del diagrama: el alta y el cierre del paso se
   resuelven en `SeguimientoPaso.registrar_evidencia()`,
   `Evidencia.clean()` y `SeguimientoPaso.marcar_completado()`, como en los
   diagramas corregidos.
5. Unifica el estilo: paquetes `tecnicas` y `reportes`, operaciones en
   `snake_case` con tipos y retorno, relaciones con etiqueta, notas con las
   reglas y tres secciones en el diagrama de secuencia.

## 2. Criterios de aceptación y cobertura

| # | Criterio | Dónde se cumple |
| --- | --- | --- |
| CA-1 | Pide enlace o archivo, fecha y comentario opcional. | `EvidenciaForm` (`enlace`, `archivo`, `fecha`, `comentario`, `autor`) y `RegistroEvidenciaTemplate` |
| CA-2 | Un paso no se completa sin evidencia. | `SeguimientoPaso.marcar_completado()` exige evidencia; `EvidenciaForm.clean()` exige enlace o archivo |
| CA-3 | Rechaza formato o tamaño no permitido indicando qué se acepta. | Validadores del campo `archivo`: PDF, PNG, JPG, DOCX, XLSX y TXT; máximo 5 MB |
| CA-4 | El paso queda completado con fecha y autor; la evidencia se abre después. | `marcar_completado()` registra `fecha_completado`; el autor es `Evidencia.miembro_proyecto`; `AbrirEvidenciaView` sirve el archivo o redirige al enlace |

## 3. Diagrama de clases (`hu10_clases.puml`)

| Clase | Paquete | Responsabilidad |
| --- | --- | --- |
| `RegistroEvidenciaTemplate` | tecnicas.template | Muestra los pasos, su evidencia y el formulario; abre una evidencia. |
| `RegistrarEvidenciaView` | tecnicas.view | Recibe la petición, valida el formulario y que el paso pertenezca al seguimiento (404 si no), y delega el alta. |
| `AbrirEvidenciaView` | tecnicas.view | Devuelve el archivo con `FileResponse` o redirige al enlace. |
| `EvidenciaForm` | tecnicas.form | Valida enlace o archivo, fecha, comentario y autor; aplica los límites de formato y tamaño. |
| `TecnicaQA`, `Paso` | tecnicas.model | Catálogo de la técnica y sus pasos ordenados. |
| `SeguimientoTecnica` | tecnicas.model | Avance de la técnica y pasos del seguimiento. |
| `SeguimientoPaso` | tecnicas.model | Estado del paso; crea la evidencia y lo completa. |
| `Evidencia` | tecnicas.model | Enlace o archivo, fecha, fecha de registro y autor; valida su contenido. |
| `Proyecto`, `MiembroProyecto` | reportes.model | Proyecto y equipo; el autor de la evidencia es un miembro del proyecto. |

Relaciones con etiqueta, igual que en los diseños corregidos:

- `TecnicaQA 1 — 1..* Paso` («define») y `TecnicaQA 1 — 0..* SeguimientoTecnica` («aplica»).
- `SeguimientoTecnica 1 — 1..* SeguimientoPaso` («desglosa») y `* — 1 Proyecto` («sigue»).
- `SeguimientoPaso * — 1 Paso` («ejecuta») y `1 — 0..1 Evidencia` («se respalda con»).
- `Evidencia * — 1 MiembroProyecto` («autor»).

Reglas en notas:

1. `UNIQUE(seguimiento_paso_id)`: máximo una evidencia por paso.
2. `CHECK(enlace IS NOT NULL OR archivo IS NOT NULL)`.
3. El autor debe pertenecer al proyecto del paso; se valida en `clean()`.
4. Un paso no se completa sin evidencia.
5. `fecha` la declara el usuario; `fecha_registro` la sella el alta.

## 4. Diagrama de secuencia (`hu10_secuencia.puml`)

Tres secciones, con el mismo formato de los diagramas corregidos:

1. **Consulta**: `get` → `SeguimientoTecnica.obtener_pasos()` → lista de pasos y
   formulario.
2. **Registro**: `post` → `obtener_paso()` (404 si el paso es de otro
   seguimiento) → `EvidenciaForm.is_valid()`; si es inválido se responde 200
   con los errores (sin enlace/archivo, formato o tamaño). Si es válido:
   `SeguimientoPaso.registrar_evidencia()` crea la `Evidencia`, comprueba
   `tiene_enlace_o_archivo()`, ejecuta `clean()`, guarda, ejecuta
   `marcar_completado()` y `SeguimientoTecnica.calcular_avance()`; la vista
   redirige a los pasos.
3. **Apertura**: `AbrirEvidenciaView.obtener_evidencia()` →
   `Evidencia.abrir_archivo()` con `FileResponse`, o redirección al enlace, o
   404 si no hay contenido.

## 5. Decisiones de diseño

| Decisión | Alternativa | Motivo |
| --- | --- | --- |
| `Evidencia.miembro_proyecto` como FK al equipo. | `autor` de texto. | Es el modelo del E-R corregido y permite validar en `clean()` que el autor pertenece al proyecto. |
| `Evidencia.fecha` además de `fecha_registro`. | Usar solo el sello automático. | El criterio pide que el sistema solicite la fecha; `fecha_registro` no es editable. |
| Comentario en `SeguimientoPaso.comentario`. | Campo nuevo en `Evidencia`. | El modelo corregido ya tiene `comentario` en el paso; no se duplica. |
| Lógica en el modelo (`registrar_evidencia`, `clean`, `marcar_completado`). | Servicio aparte como en la revisión 1. | Es el estilo de los diseños corregidos y deja la vista delgada. |
| Vista propia `RegistrarEvidenciaView`. | Registrar dentro de `SeguirTecnicaView`, como en la secuencia corregida de HU-05. | La pantalla de evidencias es independiente de la selección de técnicas; el modelo y los contratos sí siguen los diagramas corregidos. Si el equipo prefiere concentrarlo en `SeguirTecnicaView`, solo cambia la vista. |
| Una evidencia por paso (`UNIQUE`). | Varias evidencias por paso. | Es la regla del E-R corregido y de la HU-05. |
| Formatos y 5 MB en validadores del campo. | Validar solo en la vista. | Vale también para el admin y las pruebas, sin duplicar reglas. |
| Abrir con una vista que sirve el archivo. | Enlace directo a `MEDIA_URL`. | Controla el 404 del archivo ausente y funciona sin servidor de estáticos. |
| `Proyecto` y `MiembroProyecto` en `reportes`. | Mantenerlos en `tecnicas`. | Es la ubicación del E-R corregido; `tecnicas` los referencia. |

## 6. Verificación del diseño

Inspección de los dos `.puml` con los criterios del formato del curso:

| Criterio | Resultado | Detalle |
| --- | --- | --- |
| ESP-01 nombres idénticos | Sí | `RegistrarEvidenciaView`, `AbrirEvidenciaView`, `EvidenciaForm`, `SeguimientoPaso`, `Evidencia` y sus operaciones coinciden en ambos diagramas. |
| ESP-02 llamadas declaradas | Sí | `get`, `post`, `obtener_paso`, `is_valid`, `registrar_evidencia`, `tiene_enlace_o_archivo`, `clean`, `save`, `marcar_completado`, `calcular_avance`, `abrir_archivo` y `obtener_evidencia` están declaradas o son operaciones del ORM; `new` es el constructor. |
| ESP-03 visibilidad | Sí | Atributos con `-`; operaciones con `+`. |
| ESP-04 tipos | Sí | `HttpRequest`, `HttpResponse`, `int`, `String`, `Date`, `DateTime`, `File`, `boolean`, `Float`, `List`, `Map`, `Evidencia`. |
| ESP-05 semántica UML | Sí | Composición/asociación con cardinalidades y etiquetas («se respalda con», «sigue», «autor»); `alt` para las ramas de validación. |
| ESP-06 retornos | Sí | `List<SeguimientoPaso>`, `Evidencia`, `boolean`, `porcentaje_avance`, `FileResponse`, redirección y 404. |
| ESP-07 criterios de la HU | Sí | Los cuatro criterios aparecen en el flujo, en las notas y en el formulario. |

El formato `Verificación de Diseño HU10.xlsx` se actualizó con el resultado
7/7.

## 7. Estado de la construcción

La construcción actual (revisión 1) implementa el modelo anterior y **no
coincide** con esta revisión. Al integrar `main` hay que adaptarla:

- `Evidencia.autor` (texto) → `miembro_proyecto` (FK), con validación en
  `clean()`.
- Retirar `Evidencia.tipo` y `Evidencia.comentario`; conservar el comentario en
  `SeguimientoPaso.comentario`.
- Añadir `Evidencia.fecha` y mantener `fecha_registro`.
- Mover `Proyecto` a `reportes` si `main` ya lo hizo, y ajustar importaciones.
- Actualizar `EvidenciaForm` (autor como selector de miembros), la plantilla,
  las pruebas y la migración; regenerar la captura de interfaz.
- Borrar `db.sqlite3`, ejecutar `migrate` y volver a correr la suite.

Mientras tanto, la verificación de código y el reporte de pruebas de la
revisión 1 quedan **obsoletos** y deben rehacerse tras la adaptación.

## 8. Entregables de esta revisión

- `diagrams/hu10_clases.puml` y `diagrams/hu10_secuencia.puml`.
- `documentacion-proyecto-calidad/Diseño/Diagramas de clases/hu10_clases.png`
  y `.../Diagramas de secuencia/hu10_secuencia.png` (PlantUML 1.2024.3,
  `-checkonly` sin errores).
- `documentacion-proyecto-calidad/Verificaciones/Diseño/Verificación de Diseño
  HU10.xlsx` (revisión 2).

**Git.** No se hicieron commits. La recomendación es integrar `main` antes de
versionar la HU-10, porque el refactor de `main` y esta revisión de diseño
cambian el mismo modelo.
