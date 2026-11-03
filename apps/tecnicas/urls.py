from django.urls import path

from .views import (
    CatalogoTecnicasView,
    DetalleTecnicaView,
    RegistrarEvidenciaView,
    SeguirTecnicaView,
)

app_name = 'tecnicas'

urlpatterns = [
    path('catalogo/', CatalogoTecnicasView.as_view(), name='catalogo'),
    path('seguimiento/', SeguirTecnicaView.as_view(), name='seguimiento'),
    path(
        'detalle/<int:tecnica_id>/',
        DetalleTecnicaView.as_view(),
        name='detalle',
    ),
    path(
        'pasos/<int:seguimiento_paso_id>/evidencia/',
        RegistrarEvidenciaView.as_view(),
        name='registrar_evidencia',
    ),
]
