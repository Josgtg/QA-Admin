from django.urls import path

from apps.modelos.views import (
    AplicarModeloView,
    DescargarEvidenciaMetricaView,
    RegistrarRevisionMetricaView,
)

from .views import (
    CrearProyectoView,
    EditarProyectoView,
    EliminarProyectoView,
    ListaProyectosView,
    MetricasProyectoView,
    TableroProyectoView,
)

app_name = 'reportes'

urlpatterns = [
    path('', ListaProyectosView.as_view(), name='lista'),
    path('crear/', CrearProyectoView.as_view(), name='crear'),
    path('<int:proyecto_id>/', TableroProyectoView.as_view(), name='tablero'),
    path(
        '<int:proyecto_id>/modelo/',
        AplicarModeloView.as_view(),
        name='aplicar_modelo',
    ),
    path(
        '<int:proyecto_id>/editar/',
        EditarProyectoView.as_view(),
        name='editar',
    ),
    path(
        '<int:proyecto_id>/equipo/',
        EditarProyectoView.as_view(),
        name='editar_equipo',
    ),
    path(
        '<int:proyecto_id>/eliminar/',
        EliminarProyectoView.as_view(),
        name='eliminar',
    ),
    path(
        '<int:proyecto_id>/metricas/',
        MetricasProyectoView.as_view(),
        name='metricas',
    ),
    path(
        '<int:proyecto_id>/metricas/<int:metrica_id>/revisar/',
        RegistrarRevisionMetricaView.as_view(),
        name='registrar_revision',
    ),
    path(
        '<int:proyecto_id>/revisiones/<int:revision_id>/evidencia/',
        DescargarEvidenciaMetricaView.as_view(),
        name='descargar_evidencia_metrica',
    ),
]
