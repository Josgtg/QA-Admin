# Estandar de codificacion

Guia breve de buenas practicas para el proyecto QA-Admin (Django).

## 1. Idioma y nombres

- Codigo en ingles (clases, funciones, variables); textos de interfaz y documentacion en espanol.
- Usa `snake_case` para variables y funciones, `PascalCase` para clases y `UPPER_CASE` para constantes.
- Nombres descriptivos: `tecnicas_seleccionadas` en lugar de `lista` o `x`.
- Las clases de modelos y vistas deben terminar en `Model` o `View` segun corresponda (por ejemplo `SeguirTecnicaView`).

## 2. Estructura del proyecto

- Cada funcionalidad va en su propia app dentro de `apps/` (`modelos`, `reportes`, `tecnicas`).
- La logica de negocio vive en los modelos o en servicios, no en las vistas.
- Las vistas solo reciben la peticion, llaman la logica y devuelven la respuesta.
- Las plantillas van en `templates/<app>/` y los estaticos en `static/`.
- No subir `db.sqlite3`, `.venv/` ni archivos generados al repositorio.

## 3. Estilo de codigo

- Sigue PEP 8: 4 espacios de indentacion, lineas de maximo 79-100 caracteres.
- Deja dos lineas en blanco entre clases y funciones de nivel superior.
- Usa imports ordenados: primero la libreria estandar, luego Django, y al final los imports locales.
- Evita imports con `*`; importa solo lo que se usa.
- Usa comillas simples por convencion, salvo que el texto contenga comillas simples.
- No dejes codigo comentado ni prints de depuracion.

## 4. Django

- Toda vista basada en clase debe heredar de `View` y definir `template_name`.
- Usa `get_object_or_404` en lugar de capturar `DoesNotExist` manualmente.
- Define `related_name` en las relaciones `ForeignKey` y `ManyToManyField`.
- Agrega `__str__` a todos los modelos.
- Usa `Meta` para `ordering`, `verbose_name` y restricciones.
- Las migraciones se generan con `python manage.py makemigrations` y se versionan con el codigo.
- Usa el ORM de Django; evita SQL crudo salvo que sea necesario.
- Nunca dejes `DEBUG = True` ni claves secretas en produccion.

## 5. Plantillas y frontend

- Extiende siempre de `base.html`.
- Usa `{% url %}` para generar enlaces, nunca rutas escritas a mano.
- Escapa la salida por defecto; usa `|safe` solo con contenido confiable.
- Manten el HTML semantico y las clases CSS descriptivas.

## 6. Git

- Crea una rama nueva por cada historia de usuario (HU).
- Integra cada rama mediante un Pull Request (PR), con el fin de que sea verificado con el checklist de codigo.
- Mensajes de commit claros y en imperativo: `Agrega validador de dimension`.
- Un commit por cambio logico; no mezcles refactors con funcionalidad nueva.
- Revisa `git status` y `git diff` antes de confirmar.
- No subir credenciales, archivos `.env` ni la base de datos local.

## 7. Revision rapida antes de entregar

1. `python manage.py check`
2. `python manage.py test`
3. Revisar que no queden archivos temporales ni secretos.
