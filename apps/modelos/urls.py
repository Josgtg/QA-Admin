from django.urls import path

from .views import CatalogoModelosView, ModeloDelProyectoView

app_name = 'modelos'

from .propios import crear_modelo, eliminar_modelo

urlpatterns = [
    path('crear/', crear_modelo, name='crear'),
    path('<int:pk>/eliminar/', eliminar_modelo, name='eliminar'),
    path('', CatalogoModelosView.as_view(), name='catalogo'),
    path(
        'proyecto/',
        ModeloDelProyectoView.as_view(),
        name='modelo_proyecto',
    ),
]
