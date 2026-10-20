from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
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


class Persona(models.Model):
    nombre = models.CharField(max_length=150, unique=True)

    class Meta:
        verbose_name = 'persona'
        verbose_name_plural = 'personas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class MiembroProyecto(models.Model):
    proyecto = models.ForeignKey(
        'tecnicas.Proyecto',
        on_delete=models.CASCADE,
        related_name='equipo',
    )
    persona = models.ForeignKey(
        Persona,
        on_delete=models.PROTECT,
        related_name='membresias',
    )
    rol = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'miembro de proyecto'
        verbose_name_plural = 'miembros de proyecto'
        ordering = ['persona__nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['proyecto', 'persona'],
                name='miembro_unico_por_proyecto_y_persona',
            ),
        ]

    def __str__(self):
        return f'{self.persona} · {self.proyecto} · {self.rol}'

    def clean(self):
        if not self.rol or not self.rol.strip():
            raise ValidationError({'rol': 'El rol no puede estar vacío.'})

    def desactivar(self):
        self.activo = False
        self.save(update_fields=['activo'])

    def reactivar(self):
        self.activo = True
        self.save(update_fields=['activo'])

    def cambiar_rol(self, nuevo_rol):
        self.rol = nuevo_rol
        self.full_clean()
        self.save(update_fields=['rol'])


class RegistroSalud(models.Model):
    proyecto = models.ForeignKey(
        'tecnicas.Proyecto',
        on_delete=models.CASCADE,
        related_name='registros_salud',
    )
    fecha = models.DateField(default=timezone.localdate)
    indice = models.FloatField()
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'registro de salud'
        verbose_name_plural = 'registros de salud'
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(
                fields=['proyecto', 'fecha'],
                name='salud_unica_por_proyecto_y_fecha',
            ),
        ]

    def __str__(self):
        return f'{self.proyecto} · {self.fecha} · {self.indice}'


def registrar_salud(proyecto):
    """Guarda o refresca el índice de salud del proyecto para hoy.

    Devuelve ``None`` cuando el proyecto todavía no tiene mediciones.
    """
    indice = proyecto.indice_salud()
    if indice is None:
        return None
    registro, _ = RegistroSalud.objects.update_or_create(
        proyecto=proyecto,
        fecha=timezone.localdate(),
        defaults={'indice': indice},
    )
    return registro


def tendencia_salud(proyecto, limite=6):
    """Devuelve los últimos registros de salud, del más antiguo al más nuevo."""
    registros = list(
        proyecto.registros_salud.order_by('-fecha')[:limite]
    )
    return list(reversed(registros))
