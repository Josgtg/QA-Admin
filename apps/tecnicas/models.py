from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .validators import (
    validar_extension_evidencia,
    validar_tamano_evidencia,
)


class Dimension(models.TextChoices):
    ESPECIFICACION = 'ESPECIFICACION', 'Especificación'
    DISENO = 'DISENO', 'Diseño'
    DESARROLLO = 'DESARROLLO', 'Desarrollo'
    CONFORMIDAD = 'CONFORMIDAD', 'Conformidad'


class TipoControl(models.TextChoices):
    VERIFICACION = 'VERIFICACION', 'Verificación'
    VALIDACION = 'VALIDACION', 'Validación'


class CatalogoTQA(models.Model):
    """Agrupador opcional de técnicas (H4-2=a: se conserva sin UI nueva)."""

    nombre = models.CharField(max_length=200, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = 'catálogo TQA'
        verbose_name_plural = 'catálogos TQA'

    def __str__(self):
        return self.nombre

    def obtener_tecnicas_base(self):
        return self.tecnicas.all()

    def filtrar_por_dimension(self, dimension):
        return self.tecnicas.filter(dimension=dimension)


class TecnicaQA(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    objetivo = models.TextField()
    pregunta_clave = models.TextField()
    dimension = models.CharField(max_length=20, choices=Dimension.choices)
    tipo_control = models.CharField(max_length=20, choices=TipoControl.choices)
    catalogo = models.ForeignKey(
        CatalogoTQA,
        on_delete=models.CASCADE,
        related_name='tecnicas',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'técnica QA'
        verbose_name_plural = 'técnicas QA'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def obtener_pasos(self):
        return self.pasos.all()

    def es_placeholder(self):
        """Contenido provisional mientras no exista el texto definitivo."""
        return self.descripcion.startswith('[PENDIENTE]')

    def es_base(self):
        """True si pertenece al catálogo base; esas no se editan ni se borran."""
        return self.catalogo_id is not None

    def es_propia(self):
        """True si la creó el encargado: no pertenece a ningún catálogo (HU-17)."""
        return not self.es_base()

    def proyectos_con_evidencias(self):
        """Proyectos donde algún paso de la técnica ya tiene evidencia."""
        from apps.reportes.models import Proyecto

        return Proyecto.objects.filter(
            seguimientos_tecnicas__tecnica=self,
            seguimientos_tecnicas__pasos__evidencia__isnull=False,
        ).distinct()

    def motivo_para_no_modificar(self):
        """Explica por qué la técnica no se puede editar ni borrar.

        Devuelve una cadena vacía cuando sí se puede.
        """
        if self.es_base():
            return 'Las técnicas base no se pueden editar ni borrar.'
        nombres = list(
            self.proyectos_con_evidencias().values_list('nombre', flat=True)
        )
        if nombres:
            return (
                f'La técnica ya tiene evidencias en: {", ".join(nombres)}. '
                'No se puede editar ni borrar para conservarlas.'
            )
        return ''

    def puede_modificarse(self):
        """True si es propia y aún no tiene evidencias registradas."""
        return not self.motivo_para_no_modificar()

    def validar_modificable(self):
        """Lanza ValidationError si la técnica no se puede modificar."""
        motivo = self.motivo_para_no_modificar()
        if motivo:
            raise ValidationError(motivo)


class Paso(models.Model):
    tecnica = models.ForeignKey(
        TecnicaQA,
        on_delete=models.CASCADE,
        related_name='pasos',
    )
    orden = models.PositiveIntegerField()
    instruccion = models.TextField()
    evidencia_esperada = models.TextField(blank=True)

    class Meta:
        verbose_name = 'paso'
        verbose_name_plural = 'pasos'
        ordering = ['orden']
        constraints = [
            models.UniqueConstraint(
                fields=['tecnica', 'orden'],
                name='paso_orden_unico_por_tecnica',
            ),
        ]

    def __str__(self):
        return f'{self.orden}. {self.instruccion[:60]}'


class SeguimientoTecnica(models.Model):
    """Técnica elegida dentro de un proyecto (``hu5_clases.puml``)."""

    proyecto = models.ForeignKey(
        'reportes.Proyecto',
        on_delete=models.CASCADE,
        related_name='seguimientos_tecnicas',
    )
    tecnica = models.ForeignKey(
        TecnicaQA,
        on_delete=models.PROTECT,
        related_name='seguimientos',
    )
    porcentaje_avance = models.FloatField(default=0.0)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'seguimiento de técnica'
        verbose_name_plural = 'seguimientos de técnicas'
        ordering = ['tecnica__nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['proyecto', 'tecnica'],
                name='seguimiento_unico_por_proyecto_y_tecnica',
            ),
        ]

    def __str__(self):
        return f'{self.proyecto} - {self.tecnica}'

    def tiene_evidencias_registradas(self):
        return self.pasos.filter(evidencia__isnull=False).exists()

    def pasos_completados(self):
        """``SeguimientoPaso`` del seguimiento marcados como completados."""
        return self.pasos.filter(completado=True)

    def pasos_pendientes(self):
        """``SeguimientoPaso`` del seguimiento que siguen pendientes."""
        return self.pasos.filter(completado=False)

    def total_pasos(self):
        """Cantidad de pasos que desglosa el seguimiento."""
        return self.pasos.count()

    def calcular_avance(self):
        """Recalcula el porcentaje y lo persiste si cambió.

        ``calcular_porcentaje_avance()`` no escribe; este método sí, porque
        HU-05 guarda el avance en ``porcentaje_avance``.
        """
        porcentaje = self.calcular_porcentaje_avance()
        if self.porcentaje_avance != porcentaje:
            self.porcentaje_avance = porcentaje
            self.save(update_fields=['porcentaje_avance'])
        return self.porcentaje_avance

    def calcular_porcentaje_avance(self):
        """Pasos completados entre pasos totales * 100 (HU-11).

        Deriva de los ``SeguimientoPaso`` reales en lugar de leer el valor
        almacenado, que puede quedar desfasado. No escribe en la base de
        datos.
        """
        total = self.total_pasos()
        if not total:
            return 0.0
        completados = self.pasos_completados().count()
        return round(completados / total * 100, 2)

    def esta_completada(self):
        """Técnica cumplida: todos sus pasos están completados (HU-11)."""
        if not self.total_pasos():
            return False
        return not self.pasos_pendientes().exists()

    def desactivar(self):
        """Baja lógica: conserva evidencias y pasos."""
        self.activa = False
        self.save(update_fields=['activa'])

    def reactivar(self):
        self.activa = True
        self.save(update_fields=['activa'])


class SeguimientoPaso(models.Model):
    seguimiento = models.ForeignKey(
        SeguimientoTecnica,
        on_delete=models.CASCADE,
        related_name='pasos',
    )
    paso = models.ForeignKey(
        Paso,
        on_delete=models.PROTECT,
        related_name='seguimientos',
    )
    completado = models.BooleanField(default=False)
    comentario = models.TextField(blank=True)
    fecha_completado = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'seguimiento de paso'
        verbose_name_plural = 'seguimientos de pasos'
        ordering = ['paso__orden']
        constraints = [
            models.UniqueConstraint(
                fields=['seguimiento', 'paso'],
                name='seguimiento_paso_unico',
            ),
        ]

    def __str__(self):
        return f'{self.seguimiento} - {self.paso}'

    def esta_completado(self):
        return self.completado

    def tiene_evidencia(self):
        """True si el paso tiene una ``Evidencia`` registrada.

        Comprueba la existencia en la base de datos: es fiable aunque la
        relación inversa no esté precargada.
        """
        if not self.pk:
            return False
        return Evidencia.objects.filter(seguimiento_paso_id=self.pk).exists()

    def evidencia_segura(self):
        """``Evidencia`` del paso si existe; ``None`` si no.

        A diferencia de ``self.evidencia``, no lanza
        ``RelatedObjectDoesNotExist`` cuando el paso no tiene evidencia. La
        usan las plantillas, donde capturar la excepción no es posible.
        """
        try:
            return self.evidencia
        except Evidencia.DoesNotExist:
            return None

    def marcar_completado(self, comentario=''):
        """Marca el paso como completado; exige evidencia registrada."""
        if not self.tiene_evidencia():
            raise ValidationError(
                'No se puede completar un paso sin evidencia.'
            )
        self.completado = True
        self.fecha_completado = timezone.now()
        if comentario:
            self.comentario = comentario
        self.save(
            update_fields=['completado', 'fecha_completado', 'comentario']
        )
        self.seguimiento.calcular_avance()
        return self


class Evidencia(models.Model):
    """Evidencia de un paso: enlace o archivo, con autor del proyecto."""

    seguimiento_paso = models.OneToOneField(
        SeguimientoPaso,
        on_delete=models.CASCADE,
        related_name='evidencia',
    )
    miembro_proyecto = models.ForeignKey(
        'reportes.MiembroProyecto',
        on_delete=models.CASCADE,
        related_name='evidencias',
    )
    enlace = models.URLField(max_length=500, blank=True)
    archivo = models.FileField(
        upload_to='evidencias/pasos/',
        blank=True,
        max_length=255,
        validators=[validar_extension_evidencia, validar_tamano_evidencia],
    )
    fecha = models.DateField(
        default=timezone.localdate,
        verbose_name='fecha de la evidencia',
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'evidencia'
        verbose_name_plural = 'evidencias'
        ordering = ['-fecha_registro']
        constraints = [
            models.CheckConstraint(
                condition=(~models.Q(enlace='') | ~models.Q(archivo='')),
                name='evidencia_con_enlace_o_archivo',
            ),
        ]

    def __str__(self):
        return self.enlace or (self.archivo.name if self.archivo else '')

    def tiene_enlace_o_archivo(self):
        return bool(self.enlace or self.archivo)

    def nombre_archivo(self):
        """Devuelve el nombre del archivo sin la ruta de almacenamiento."""
        if not self.archivo:
            return ''
        return self.archivo.name.rsplit('/', 1)[-1]

    def descripcion(self):
        """Texto breve que identifica la evidencia en la interfaz."""
        if self.archivo:
            return self.nombre_archivo()
        return self.enlace or 'Evidencia sin contenido'

    def abrir_archivo(self):
        """Abre el archivo adjunto en modo lectura para servirlo."""
        return self.archivo.open('rb')

    def clean(self):
        errores = {}
        if not self.tiene_enlace_o_archivo():
            errores['enlace'] = (
                'Adjunta un enlace o un archivo como evidencia.'
            )
        if self.miembro_proyecto_id and self.seguimiento_paso_id:
            proyecto_paso = self.seguimiento_paso.seguimiento.proyecto_id
            if self.miembro_proyecto.proyecto_id != proyecto_paso:
                errores['miembro_proyecto'] = (
                    'El autor debe pertenecer al proyecto del paso.'
                )
        if errores:
            raise ValidationError(errores)
