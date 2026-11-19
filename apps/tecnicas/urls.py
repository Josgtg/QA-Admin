from django.urls import path

from .views import (
    AbrirEvidenciaView,
    CatalogoTecnicasView,
    CrearTecnicaView,
    DetalleTecnicaView,
    EditarTecnicaView,
    EliminarTecnicaView,
    EstadoTecnicaView,
    RegistrarEvidenciaView,
    SeguirTecnicaView,
)

app_name = 'tecnicas'

urlpatterns = [
    path('catalogo/', CatalogoTecnicasView.as_view(), name='catalogo'),
    path('nueva/', CrearTecnicaView.as_view(), name='crear'),
    path(
        '<int:tecnica_id>/editar/',
        EditarTecnicaView.as_view(),
        name='editar',
    ),
    path(
        '<int:tecnica_id>/eliminar/',
        EliminarTecnicaView.as_view(),
        name='eliminar',
    ),
    path('seguimiento/', SeguirTecnicaView.as_view(), name='seguimiento'),
    path(
        'detalle/<int:tecnica_id>/',
        DetalleTecnicaView.as_view(),
        name='detalle',
    ),
    path(
        'estado/<int:tecnica_id>/',
        EstadoTecnicaView.as_view(),
        name='estado',
    ),
    path(
        'pasos/<int:seguimiento_paso_id>/evidencia/',
        RegistrarEvidenciaView.as_view(),
        name='registrar_evidencia',
    ),
    path(
        'evidencias/<int:evidencia_id>/abrir/',
        AbrirEvidenciaView.as_view(),
        name='abrir_evidencia',
    ),
]
