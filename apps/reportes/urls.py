from django.urls import path

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
]
