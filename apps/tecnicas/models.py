from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


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

    def agregar_evidencia(self, evidencia):
        evidencia.seguimiento_paso = self
        evidencia.save(update_fields=['seguimiento_paso'])
        return evidencia

    def marcar_completado(self, autor=''):
        self.completado = True
        self.fecha_completado = timezone.now()
        if autor:
            self.autor = autor
        self.save(update_fields=['completado', 'fecha_completado', 'autor'])
        self.seguimiento.calcular_avance()
        return self


class Evidencia(models.Model):
    seguimiento_paso = models.OneToOneField(
        SeguimientoPaso,
        on_delete=models.CASCADE,
        related_name='evidencia',
        null=True,
        blank=True,
    )
    url_archivo = models.URLField(max_length=500)
    tipo = models.CharField(max_length=20, choices=TipoControl.choices)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    autor = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'evidencia'
        verbose_name_plural = 'evidencias'
        ordering = ['-fecha_registro']

    def __str__(self):
        return self.url_archivo
