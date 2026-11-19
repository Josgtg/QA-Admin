from django.urls import path

from .views import (
    CatalogoModelosView,
    CrearModeloPropioView,
    EliminarModeloPropioView,
    ModeloDelProyectoView,
)

app_name = 'modelos'

urlpatterns = [
    path('crear/', CrearModeloPropioView.as_view(), name='crear'),
    path(
        '<int:pk>/eliminar/',
        EliminarModeloPropioView.as_view(),
        name='eliminar',
    ),
    path('', CatalogoModelosView.as_view(), name='catalogo'),
    path(
        'proyecto/',
        ModeloDelProyectoView.as_view(),
        name='modelo_proyecto',
    ),
]
