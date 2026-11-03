"""DTO de consulta del estado de una técnica en un proyecto (HU-11).

``EstadoTecnica`` agrupa el resultado de la consulta para la plantilla. Es de
**solo lectura** y no se persiste: lo construye ``EstadoTecnicaView`` a partir
de un ``SeguimientoTecnica`` (``hu11_clases.puml``).

Las reglas de negocio (qué es un paso completado, cuándo la técnica está
cumplida y cómo se reparten los pasos) son de ``SeguimientoTecnica``. El DTO no
las reimplementa: delega en el seguimiento cuando lo tiene, para no mantener
dos versiones de la misma regla.
"""


class EstadoTecnica:
    """Pasos completados y pendientes de una técnica (HU-11).

    ``pasos`` son ``SeguimientoPaso`` ordenados por el orden del ``Paso``.
    ``porcentaje_avance`` se recibe ya calculado por el seguimiento.
    """

    def __init__(
        self,
        tecnica,
        pasos,
        porcentaje_avance=0.0,
        seguimiento=None,
    ):
        self.tecnica = tecnica
        self.pasos = list(pasos)
        self.porcentaje_avance = porcentaje_avance
        self.seguimiento = seguimiento

    def __repr__(self):
        return (
            f'<EstadoTecnica {self.tecnica!r} '
            f'{self.porcentaje_avance}% completa={self.completa}>'
        )

    @property
    def total_pasos(self):
        """Cantidad de pasos del seguimiento."""
        return len(self.pasos)

    @property
    def completa(self):
        """Técnica cumplida: delega en ``SeguimientoTecnica`` (HU-11)."""
        return self.esta_completa()

    @property
    def sin_pasos(self):
        """True si el seguimiento no tiene ningún paso registrado."""
        return not self.pasos

    def esta_completa(self):
        """True si la técnica está cumplida.

        Usa ``SeguimientoTecnica.esta_completada()`` cuando el DTO tiene el
        seguimiento; sin él (DTO construido a mano) se exige que haya pasos y
        un avance del 100 %.
        """
        if self.seguimiento is not None:
            return self.seguimiento.esta_completada()
        return bool(self.pasos) and self.porcentaje_avance == 100

    def pasos_completados(self):
        """Pasos del seguimiento marcados como completados."""
        return [paso for paso in self.pasos if paso.esta_completado()]

    def pasos_pendientes(self):
        """Pasos del seguimiento que siguen pendientes."""
        return [paso for paso in self.pasos if not paso.esta_completado()]

    def conteo_completados(self):
        """Cuántos pasos están completados."""
        return len(self.pasos_completados())

    def conteo_pendientes(self):
        """Cuántos pasos siguen pendientes."""
        return len(self.pasos_pendientes())
