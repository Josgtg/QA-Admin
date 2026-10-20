from datetime import date

from django.utils import timezone

from apps.tecnicas.models import Proyecto


class Periodo:
    """Periodo derivado de las fechas del proyecto, según e-r.puml.

    No se persiste: cada proyecto obtiene su periodo a partir de
    ``fecha_inicio`` y ``fecha_fin``.
    """

    FUTURO = 'Futuro'
    ACTIVO = 'Activo'
    TERMINADO = 'Terminado'
    ESTADOS = (FUTURO, ACTIVO, TERMINADO)

    DESCRIPCIONES = {
        FUTURO: 'Proyectos que todavía no han iniciado.',
        ACTIVO: 'Proyectos que están en curso.',
        TERMINADO: 'Proyectos que ya finalizaron.',
    }

    ALIASES = {
        'futuro': FUTURO,
        'planificacion': FUTURO,
        'activo': ACTIVO,
        'activos': ACTIVO,
        'terminado': TERMINADO,
        'cerrado': TERMINADO,
        'cerrados': TERMINADO,
    }

    def __init__(self, nombre):
        if nombre not in self.ESTADOS:
            raise ValueError('Periodo no válido.')
        self.nombre = nombre
        self.id = nombre.lower()
        self.descripcion = self.DESCRIPCIONES[nombre]

    def __str__(self):
        return self.nombre

    def __eq__(self, other):
        return isinstance(other, Periodo) and self.nombre == other.nombre

    def __hash__(self):
        return hash(self.nombre)

    @classmethod
    def desde_parametro(cls, valor):
        if not valor:
            return None
        clave = valor.strip().lower()
        nombre = cls.ALIASES.get(clave)
        if nombre is None:
            raise ValueError('Periodo no válido.')
        return cls(nombre)

    def obtener_proyectos(self):
        hoy = timezone.localdate()
        if self.nombre == self.FUTURO:
            filtros = {'fecha_inicio__gt': hoy}
        elif self.nombre == self.ACTIVO:
            filtros = {
                'fecha_inicio__lte': hoy,
                'fecha_fin__gte': hoy,
            }
        else:
            filtros = {'fecha_fin__lt': hoy}
        return Proyecto.objects.filter(**filtros).order_by(
            '-fecha_inicio',
            'nombre',
        )

    def ultima_fecha(self):
        return (
            self.obtener_proyectos()
            .values_list('fecha_inicio', flat=True)
            .first()
        )

    @classmethod
    def obtener_recientes(cls):
        periodos = [cls(nombre) for nombre in cls.ESTADOS]

        def clave(periodo):
            fecha = periodo.ultima_fecha()
            return (fecha is not None, fecha or date.min)

        return sorted(periodos, key=clave, reverse=True)
