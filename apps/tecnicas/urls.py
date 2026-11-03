from django.urls import path

from .views import AbrirEvidenciaView, RegistrarEvidenciaView, SeguirTecnicaView

app_name = 'tecnicas'

urlpatterns = [
    path('seguimiento/', SeguirTecnicaView.as_view(), name='seguimiento'),
    path(
        'seguimiento/<int:seguimiento_id>/pasos/',
        RegistrarEvidenciaView.as_view(),
        name='pasos',
    ),
    path(
        'evidencias/<int:evidencia_id>/abrir/',
        AbrirEvidenciaView.as_view(),
        name='abrir_evidencia',
    ),
]
