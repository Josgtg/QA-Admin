from django.urls import path

from .views import CatalogoModelosView, ModeloDelProyectoView

app_name = 'modelos'

urlpatterns = [
    path('', CatalogoModelosView.as_view(), name='catalogo'),
    path(
        'proyecto/',
        ModeloDelProyectoView.as_view(),
        name='modelo_proyecto',
    ),
]
