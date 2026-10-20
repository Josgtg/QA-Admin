from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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
