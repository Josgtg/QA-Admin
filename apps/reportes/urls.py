from django.urls import path

from .views import CrearProyectoView, ListaProyectosView

app_name = 'reportes'

urlpatterns = [
    path('', ListaProyectosView.as_view(), name='lista'),
    path('crear/', CrearProyectoView.as_view(), name='crear'),
]
