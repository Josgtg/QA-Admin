"""Señales de la app de técnicas.

``FileField`` no borra el archivo del disco al borrar la fila: sin esto,
``media/`` acumula huérfanos cada vez que se reemplaza una evidencia.
"""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Evidencia


@receiver(post_delete, sender=Evidencia)
def borrar_archivo_evidencia(sender, instance, **kwargs):
    archivo = getattr(instance, 'archivo', None)
    if not archivo:
        return
    try:
        archivo.delete(save=False)
    except (ValueError, OSError):
        pass
