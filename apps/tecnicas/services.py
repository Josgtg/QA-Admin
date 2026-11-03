"""Servicios de seguimiento de técnicas (compartidos por las vistas).

La lógica vive aquí para que ``SeguirTecnicaView`` y ``CatalogoTecnicasView``
hagan exactamente lo mismo al aplicar una selección (H4-4=b).
"""

from django.db import transaction

from .models import SeguimientoPaso, SeguimientoTecnica, TecnicaQA


@transaction.atomic
def seguir_tecnica(proyecto, tecnica):
    """Crea (o reactiva) el seguimiento y sus pasos, sin duplicarlos."""
    seguimiento, _ = SeguimientoTecnica.objects.get_or_create(
        proyecto=proyecto,
        tecnica=tecnica,
    )
    if not seguimiento.activa:
        seguimiento.reactivar()

    registrados = set(
        seguimiento.pasos.values_list('paso_id', flat=True)
    )
    for paso in tecnica.obtener_pasos():
        if paso.pk not in registrados:
            SeguimientoPaso.objects.create(
                seguimiento=seguimiento,
                paso=paso,
            )
    seguimiento.calcular_avance()
    return seguimiento


def remover_tecnica(seguimiento):
    """Baja lógica: conserva pasos y evidencias (``hu5_clases.puml``)."""
    seguimiento.desactivar()


@transaction.atomic
def aplicar_seleccion(proyecto, tecnicas_ids):
    """Sincroniza los seguimientos activos del proyecto con la selección."""
    tecnicas_ids = set(tecnicas_ids)

    for tecnica in TecnicaQA.objects.filter(pk__in=tecnicas_ids):
        seguir_tecnica(proyecto, tecnica)

    for seguimiento in proyecto.seguimientos_tecnicas.filter(
        activa=True
    ).exclude(tecnica_id__in=tecnicas_ids):
        remover_tecnica(seguimiento)


def dimensiones_sin_tecnicas(proyecto):
    """Etiquetas de dimensión sin ninguna técnica en seguimiento."""
    from .models import Dimension

    activas = set(
        proyecto.seguimientos_tecnicas.filter(activa=True).values_list(
            'tecnica__dimension', flat=True
        )
    )
    return [
        etiqueta
        for valor, etiqueta in Dimension.choices
        if valor not in activas
    ]
