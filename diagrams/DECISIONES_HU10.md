# QA Admin — Diseño HU-10 (revisión 3)

**Historia**: HU-10, subir la evidencia de que un paso de una TQA ha sido
llevado a cabo. **Prioridad**: alta. **Estimación**: 5 puntos.
**Release**: 2.
**Estado**: diseño y construcción integrados sobre `main` (commit `97592e3`),
con los diseños corregidos del equipo. La rama `hu10` está en proceso de
merge; el commit y el PR los hace el responsable del repositorio.

## 1. Qué cambió respecto a la revisión 2

La revisión 2 se hizo contra el `main` viejo y proponía una capa de servicio y
un modelo de `Evidencia` distinto. Al integrar `main` apareció el refactor del
equipo, que ya implementa el registro de evidencia con el modelo corregido:

- `Evidencia` con `miembro_proyecto` (autor), `enlace`, `archivo` y
  `fecha_registro`; `UNIQUE(seguimiento_paso_id)` y
  `CHECK(enlace <> '' OR archivo <> '')`.
- `EvidenciaForm` con enlace, archivo, autor y comentario; `clean()` exige
  enlace o archivo.
- `RegistrarEvidenciaView` en `pasos/<id>/evidencia/`, que guarda o reemplaza
  la evidencia y después completa el paso.
- `SeguimientoPaso.marcar_completado(comentario)` exige evidencia.

Sobre esa base, la HU-10 se completó con lo que faltaba para los criterios de
aceptación:

1. **Fecha declarada por el usuario**: `Evidencia.fecha` (DateField con valor
   inicial de hoy) además de `fecha_registro`.
2. **Validación de formato y tamaño**: `apps/tecnicas/validators.py`
   (PDF, PNG, JPG, DOCX, XLSX y TXT; máximo 5 MB) aplicado al campo `archivo`
   y al formulario, con mensajes que indican qué se acepta.
3. **Apertura posterior**: `AbrirEvidenciaView` en
   `evidencias/<id>/abrir/`, que sirve el archivo con `FileResponse` o
   redirige al enlace; enlaces «Abrir evidencia» en el seguimiento y en el
   formulario.
4. Migración `0003_evidencia_fecha_alter_evidencia_archivo`.

## 2. Criterios de aceptación y cobertura

| # | Criterio | Dónde se cumple |
| --- | --- | --- |
| CA-1 | Pide enlace o archivo, fecha y comentario opcional. | `EvidenciaForm` (`enlace`, `archivo`, `fecha`, `comentario`, `miembro_proyecto`) y `RegistroEvidenciaTemplate` |
| CA-2 | Un paso no se completa sin evidencia. | `EvidenciaForm.clean()` y `SeguimientoPaso.marcar_completado()` |
| CA-3 | Rechaza formato o tamaño no permitido e indica qué se acepta. | `validators.py` en `Evidencia.archivo` y en el formulario; mensajes con formatos y 5 MB |
| CA-4 | El paso queda completado con fecha y autor; la evidencia se abre después. | `marcar_completado()` guarda `fecha_completado`; el autor es `miembro_proyecto`; `AbrirEvidenciaView` |

## 3. Diagrama de clases (`hu10_clases.puml`)

| Clase | Paquete | Responsabilidad |
| --- | --- | --- |
| `RegistroEvidenciaTemplate` | tecnicas.template | Muestra el paso, su evidencia y el formulario. |
| `RegistrarEvidenciaView` | tecnicas.view | Valida el formulario, guarda o reemplaza la evidencia y completa el paso. |
| `AbrirEvidenciaView` | tecnicas.view | Devuelve el archivo o redirige al enlace de la evidencia. |
| `EvidenciaForm` | tecnicas.form | Valida enlace o archivo, fecha, autor y comentario; aplica los límites del archivo. |
| `TecnicaQA`, `Paso` | tecnicas.model | Catálogo de la técnica y sus pasos. |
| `SeguimientoTecnica` | tecnicas.model | Avance de la técnica y evidencias registradas. |
| `SeguimientoPaso` | tecnicas.model | Estado del paso y cierre con evidencia. |
| `Evidencia` | tecnicas.model | Enlace o archivo, fecha, fecha de registro y autor; valida su contenido. |
| `Proyecto`, `MiembroProyecto` | reportes.model | Proyecto y equipo; el autor es un miembro del proyecto. |

Relaciones con etiqueta, como en los diseños corregidos: «define», «aplica»,
«desglosa», «ejecuta», «se respalda con», «sigue» y «autor».

Reglas en notas:

1. Una evidencia por paso (`UNIQUE(seguimiento_paso_id)`).
2. Debe tener enlace o archivo (`CHECK`).
3. El autor debe pertenecer al proyecto del paso; se valida en `clean()`.
4. Un paso no se completa sin evidencia.
5. `fecha` la declara el usuario; `fecha_registro` la sella el alta.
6. Formatos y tamaño máximo del archivo.

## 4. Diagrama de secuencia (`hu10_secuencia.puml`)

1. **Consulta**: `get` → `obtener_paso()` → formulario.
2. **Registro**: `post` → `obtener_paso()` → `EvidenciaForm.is_valid()`; si es
   inválido, 200 con errores. Si es válido: `save(commit=False)`,
   `seguimiento_paso = sp`, `full_clean()` (valida contenido y autor),
   `delete(evidencia anterior)` si existía, `save()`,
   `SeguimientoPaso.marcar_completado(comentario)` y
   `SeguimientoTecnica.calcular_avance()`; la vista redirige al seguimiento.
3. **Apertura**: `AbrirEvidenciaView.obtener_evidencia()` →
   `abrir_archivo()` con `FileResponse`, o redirección al enlace, o 404.

## 5. Decisiones

| Decisión | Alternativa | Motivo |
| --- | --- | --- |
| Partir del modelo del refactor (`miembro_proyecto`, `fecha_registro`). | Mantener la propuesta de la revisión 2. | Es el modelo vigente en `main` y de los diagramas corregidos. |
| Añadir `Evidencia.fecha`. | Usar solo `fecha_registro`. | El criterio pide que el sistema solicite la fecha; el sello automático no es editable. |
| Comentario en `SeguimientoPaso.comentario`. | Campo nuevo en `Evidencia`. | Ya existe en el modelo del equipo y evita duplicarlo. |
| Validadores en `validators.py`, aplicados al campo. | Validar solo en la vista. | Vale también para el admin y las pruebas, sin duplicar reglas. |
| `AbrirEvidenciaView` que sirve el archivo. | Enlace directo a `MEDIA_URL`. | Controla el 404 del archivo ausente y funciona sin servidor de estáticos. |
| Permitir reemplazar la evidencia de un paso. | Bloquear un segundo registro. | Es el comportamiento del refactor y no contradice la HU. |

## 6. Verificación del diseño

| Criterio | Resultado | Detalle |
| --- | --- | --- |
| ESP-01 nombres idénticos | Sí | Vistas, formulario, modelo y operaciones coinciden en ambos diagramas. |
| ESP-02 llamadas declaradas | Sí | `get`, `post`, `obtener_paso`, `is_valid`, `save`, `full_clean`, `marcar_completado`, `calcular_avance`, `abrir_archivo` y `obtener_evidencia` están declaradas o son del ORM; `delete` es del ORM. |
| ESP-03 visibilidad | Sí | Atributos con `-`; operaciones con `+`. |
| ESP-04 tipos | Sí | `HttpRequest`, `HttpResponse`, `int`, `String`, `Date`, `DateTime`, `File`, `boolean`, `Float`, `List`, `Map`. |
| ESP-05 semántica UML | Sí | Asociaciones con cardinalidad y etiqueta; `alt` para las ramas de validación. |
| ESP-06 retornos | Sí | `SeguimientoPaso`, `Evidencia`, `boolean`, `porcentaje_avance`, `FileResponse`, 302 y 404. |
| ESP-07 criterios de la HU | Sí | Los cuatro criterios aparecen en el flujo, las notas y el formulario. |

## 7. Construcción y pruebas

- `python manage.py check`: sin incidencias.
- `python manage.py makemigrations --check --dry-run`: sin cambios.
- `python manage.py test`: **159 pruebas en verde** (37 de la app técnicas,
  7 nuevas para fecha, archivo y apertura de la evidencia).
- Base local recreada (`db.sqlite3` borrada y `migrate` aplicado), como pidió
  el equipo por el cambio de esquema.

## 8. Pendientes

- Terminar el merge de `hu10` sobre `main` y abrir el PR.
- Regenerar la captura de interfaz, la revisión de código y el reporte de
  pruebas con la pantalla y el código definitivos.
