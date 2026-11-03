import os

from django.core.exceptions import ValidationError
from django.db import models, transaction
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


class Proyecto(models.Model):
    nombre = models.CharField(max_length=200)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    class Meta:
        verbose_name = 'proyecto'
        verbose_name_plural = 'proyectos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def clean(self):
        if (
            self.fecha_inicio
            and self.fecha_fin
            and self.fecha_fin < self.fecha_inicio
        ):
            raise ValidationError(
                {
                    'fecha_fin': (
                        'La fecha de fin no puede ser anterior a la de inicio.'
                    )
                }
            )

    def periodo(self):
        """Estado derivado de las fechas, según e-r.puml."""
        if not self.fecha_inicio or not self.fecha_fin:
            return 'Sin periodo'
        hoy = timezone.localdate()
        if hoy < self.fecha_inicio:
            return 'Futuro'
        if hoy > self.fecha_fin:
            return 'Terminado'
        return 'Activo'

    def indice_salud(self):
        """Promedio provisional del avance de las técnicas activas (0-100)."""
        avances = list(
            self.seguimientos.filter(activa=True).values_list(
                'porcentaje_avance', flat=True
            )
        )
        if not avances:
            return None
        return round(sum(avances) / len(avances), 1)

    def equipo_activo(self):
        return self.equipo.filter(activo=True).select_related('persona')

    def miembros_todos(self):
        return self.equipo.select_related('persona').order_by(
            '-activo', 'persona__nombre'
        )

    def agregar_miembro(self, persona, rol):
        miembro, creado = self.equipo.get_or_create(
            persona=persona,
            defaults={'rol': rol},
        )
        if not creado:
            miembro.rol = rol
            miembro.activo = True
            miembro.full_clean()
            miembro.save(update_fields=['rol', 'activo'])
        return miembro

    def seguimientos_activos(self):
        return self.seguimientos.filter(activa=True).select_related('tecnica')

    @transaction.atomic
    def seguir_tecnica(self, tqa):
        seguimiento, _ = SeguimientoTecnica.objects.get_or_create(
            proyecto=self,
            tecnica=tqa,
        )
        if not seguimiento.activa:
            seguimiento.activa = True
            seguimiento.save(update_fields=['activa'])
        pasos_registrados = set(
            seguimiento.pasos.values_list('paso_id', flat=True)
        )
        for paso in tqa.obtener_pasos():
            if paso.pk not in pasos_registrados:
                SeguimientoPaso.objects.create(
                    seguimiento=seguimiento,
                    paso=paso,
                )
        seguimiento.calcular_avance()
        return seguimiento

    def remover_tecnica(self, seguimiento_id):
        seguimiento = self.seguimientos.filter(pk=seguimiento_id).first()
        if not seguimiento:
            return
        if seguimiento.tiene_evidencias_registradas():
            seguimiento.activa = False
            seguimiento.save(update_fields=['activa'])
        else:
            seguimiento.delete()


class SeguimientoTecnica(models.Model):
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='seguimientos',
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

    def calcular_avance(self):
        total = self.pasos.count()
        completados = self.pasos.filter(completado=True).count()
        porcentaje = round(completados / total * 100, 2) if total else 0.0
        if self.porcentaje_avance != porcentaje:
            self.porcentaje_avance = porcentaje
            self.save(update_fields=['porcentaje_avance'])
        return self.porcentaje_avance

    def obtener_pasos(self):
        """Devuelve los pasos del seguimiento ordenados y con su evidencia."""
        return self.pasos.select_related('paso', 'evidencia').order_by(
            'paso__orden'
        )


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
    autor = models.CharField(max_length=150, blank=True)

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

    def evidencia_registrada(self):
        """Devuelve la evidencia del paso o ``None`` si todavía no existe."""
        try:
            return self.evidencia
        except Evidencia.DoesNotExist:
            return None

    def tiene_evidencia(self):
        """Indica si el paso ya cuenta con una evidencia con contenido."""
        evidencia = self.evidencia_registrada()
        return evidencia is not None and evidencia.tiene_contenido()

    def agregar_evidencia(self, evidencia):
        """Vincula una evidencia ya construida con este paso."""
        evidencia.seguimiento_paso = self
        evidencia.save()
        return evidencia

    def registrar_evidencia(
        self,
        *,
        enlace='',
        archivo=None,
        fecha=None,
        comentario='',
        autor='',
    ):
        """Crea la evidencia del paso y lo marca como completado (HU-10)."""
        if self.completado:
            raise ValidationError(
                'El paso ya está completado y tiene evidencia registrada.'
            )
        if not enlace and not archivo:
            raise ValidationError(
                'Registra un enlace o adjunta un archivo como evidencia.'
            )
        evidencia = Evidencia(
            seguimiento_paso=self,
            enlace=enlace or '',
            archivo=archivo or '',
            fecha=fecha or timezone.localdate(),
            comentario=comentario or '',
            autor=autor,
            tipo=self.seguimiento.tecnica.tipo_control,
        )
        evidencia.full_clean()
        evidencia.save()
        self.marcar_completado(autor)
        return evidencia

    def marcar_completado(self, autor=''):
        """Completa el paso solo si tiene evidencia y actualiza el avance."""
        if not self.tiene_evidencia():
            raise ValidationError(
                {'evidencia': 'Un paso no se puede completar sin evidencia.'}
            )
        self.completado = True
        self.fecha_completado = timezone.now()
        if autor:
            self.autor = autor
        self.save(update_fields=['completado', 'fecha_completado', 'autor'])
        self.seguimiento.calcular_avance()
        return self


def ruta_evidencia(instance, filename):
    """Guarda cada archivo en media/evidencias/<paso del seguimiento>/."""
    if instance.seguimiento_paso_id:
        return f'evidencias/paso_{instance.seguimiento_paso_id}/{filename}'
    return f'evidencias/sin_paso/{filename}'


class Evidencia(models.Model):
    seguimiento_paso = models.OneToOneField(
        SeguimientoPaso,
        on_delete=models.CASCADE,
        related_name='evidencia',
        null=True,
        blank=True,
    )
    enlace = models.URLField(max_length=500, blank=True)
    archivo = models.FileField(
        upload_to=ruta_evidencia,
        blank=True,
        max_length=255,
        validators=[validar_extension_evidencia, validar_tamano_evidencia],
    )
    fecha = models.DateField(
        default=timezone.localdate,
        verbose_name='fecha de la evidencia',
    )
    comentario = models.TextField(blank=True)
    tipo = models.CharField(
        max_length=20,
        choices=TipoControl.choices,
        blank=True,
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    autor = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'evidencia'
        verbose_name_plural = 'evidencias'
        ordering = ['-fecha_registro']

    def __str__(self):
        return self.descripcion()

    def descripcion(self):
        """Texto breve que identifica la evidencia en la interfaz."""
        if self.es_archivo():
            return self.nombre_archivo()
        return self.enlace or 'Evidencia sin contenido'

    def es_archivo(self):
        """Indica si la evidencia se guardó como archivo adjunto."""
        return bool(self.archivo)

    def nombre_archivo(self):
        """Devuelve el nombre del archivo sin la ruta de almacenamiento."""
        if not self.es_archivo():
            return ''
        return os.path.basename(self.archivo.name)

    def tiene_contenido(self):
        """Indica si la evidencia aporta un enlace o un archivo."""
        return self.es_archivo() or bool(self.enlace)

    def abrir_archivo(self):
        """Abre el archivo adjunto en modo lectura para servirlo."""
        return self.archivo.open('rb')
