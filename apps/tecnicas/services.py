"""Servicios de la app técnicas (lógica de negocio fuera de las vistas)."""

from django.db import transaction
from django.utils import timezone

from .models import Evidencia, SeguimientoPaso


class RegistroEvidenciaError(Exception):
    """Error de negocio al registrar la evidencia de un paso."""


class RegistrarEvidenciaService:
    """Registra la evidencia de un paso y lo marca como completado (HU-10)."""

    def __init__(self, seguimiento_paso: SeguimientoPaso):
        self.seguimiento_paso = seguimiento_paso

    @transaction.atomic
    def registrar(
        self,
        *,
        enlace='',
        archivo=None,
        fecha=None,
        comentario='',
        autor='',
    ) -> Evidencia:
        """Crea la evidencia y completa el paso en una sola transacción."""
        if self.seguimiento_paso.completado:
            raise RegistroEvidenciaError(
                'Este paso ya está completado y tiene evidencia registrada.'
            )
        return self.seguimiento_paso.registrar_evidencia(
            enlace=enlace,
            archivo=archivo,
            fecha=fecha or timezone.localdate(),
            comentario=comentario,
            autor=autor,
        )
