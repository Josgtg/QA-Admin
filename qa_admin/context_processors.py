"""Contexto compartido por todas las plantillas."""

# Pantallas de `reportes` que pertenecen a la sección de modelos de calidad:
# el modelo vigente y sus métricas (aplicar, listar y registrar revisiones).
URLS_DE_MODELOS = frozenset(
    {'aplicar_modelo', 'metricas', 'registrar_revision'}
)


def navegacion(request):
    """Expone ``nav_activo``: el ítem del menú lateral que se resalta."""
    return {'nav_activo': item_activo(request.resolver_match)}


def item_activo(match):
    """Nombre del ítem del sidebar que corresponde a la vista resuelta."""
    if match is None:
        return ''

    if match.url_name in ('tablero', 'inicio'):
        return 'dashboard'
    if match.url_name == 'catalogo_metricas':
        return 'catalogo_metricas'
    if match.namespace == 'modelos':
        return 'modelos'
    if match.app_name == 'reportes':
        if match.url_name in URLS_DE_MODELOS:
            return 'modelos'
        return 'proyectos'
    if match.namespace == 'tecnicas':
        return 'tecnicas'
    return ''
