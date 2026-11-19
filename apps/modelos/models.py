from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


def _formatear_numero(valor):
    """Número sin decimales innecesarios: ``90.0`` → ``"90"``."""
    if float(valor).is_integer():
        return str(int(valor))
    return str(valor)


class TipoUmbral(models.TextChoices):
    MINIMO = 'MINIMO', 'Mínimo'
    MAXIMO = 'MAXIMO', 'Máximo'


class ModeloCalidad(models.Model):
    """Catálogo de modelos de calidad (``hu3_clases.puml``).

    Las características del modelo **se infieren** de sus métricas: no hay FK
    directa de ``Caracteristica`` a ``ModeloCalidad``.
    """

    nombre = models.CharField(max_length=200, unique=True)
    descripcion = models.TextField()
    predefinido = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'modelo de calidad'
        verbose_name_plural = 'modelos de calidad'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @classmethod
    def obtener_predefinidos(cls):
        return cls.objects.filter(predefinido=True).prefetch_related(
            'modelo_metricas__metrica__caracteristica'
        )

    @classmethod
    def disponibles(cls):
        return cls.objects.filter(
            models.Q(predefinido=True) | models.Q(modelo_metricas__activa=True)
        ).distinct()

    @transaction.atomic
    def guardar_con_metricas(self, filas):
        """Guarda el modelo y las métricas validadas en una única transacción."""
        self.save()
        for fila in filter(None, filas):
            caracteristica, _ = Caracteristica.objects.get_or_create(
                nombre=fila['caracteristica']
            )
            metrica = Metrica.objects.create(
                caracteristica=caracteristica, nombre=fila['nombre'],
                forma_medicion=fila['forma_medicion'], unidad=fila['unidad'],
            )
            ModeloMetrica.objects.create(
                modelo_calidad=self, metrica=metrica, umbral=fila['meta'],
                tipo_umbral=fila['tipo_umbral'],
            )

    def obtener_modelo_metricas(self):
        return self.modelo_metricas.select_related(
            'metrica__caracteristica'
        ).order_by('metrica__caracteristica__nombre', 'metrica__nombre')

    def obtener_caracteristicas(self):
        return Caracteristica.objects.filter(
            metricas__modelo_metricas__modelo_calidad=self
        ).distinct()

    def tiene_metricas(self):
        return self.modelo_metricas.exists()


class Caracteristica(models.Model):
    """Catálogo global de características de calidad.

    Agrupa métricas (``1:N``). No pertenece a ningún modelo: un modelo incluye
    métricas mediante ``ModeloMetrica``.
    """

    nombre = models.CharField(max_length=200, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = 'característica'
        verbose_name_plural = 'características'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def obtener_metricas(self):
        return self.metricas.all()

    def metricas_aplicadas(self, proyecto):
        """Métricas de la característica activas en el modelo vigente."""
        return MetricaAplicada.objects.filter(
            metrica__caracteristica=self,
            modelo_aplicado__proyecto=proyecto,
            modelo_aplicado__vigente=True,
            activa=True,
        ).select_related('metrica')

    def metricas_aceptadas(self, proyecto):
        return sum(
            1
            for aplicada in self.metricas_aplicadas(proyecto)
            if aplicada.metrica.esta_aceptada(proyecto)
        )

    def calcular_seguimiento(self, proyecto):
        """Aceptadas / activas de la característica en el modelo vigente * 100."""
        aplicadas = list(self.metricas_aplicadas(proyecto))
        total = len(aplicadas)
        if not total:
            return None
        aceptadas = sum(
            1
            for aplicada in aplicadas
            if aplicada.metrica.esta_aceptada(proyecto)
        )
        return round(aceptadas / total * 100, 2)


class Metrica(models.Model):
    """Métrica de calidad con su rango admisible (``hu1_clases.puml``).

    La meta o umbral **no** vive aquí: vive en ``ModeloMetrica`` (y en su
    instantánea ``MetricaAplicada``), porque un mismo ``Metrica`` puede tener
    umbrales distintos en modelos distintos.
    """

    caracteristica = models.ForeignKey(
        Caracteristica,
        on_delete=models.PROTECT,
        related_name='metricas',
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    forma_medicion = models.TextField(
        blank=True,
        verbose_name='forma de medición',
        help_text='Cómo se obtiene el valor de la métrica.',
    )
    unidad = models.CharField(max_length=50)
    valor_min = models.FloatField(null=True, blank=True)
    valor_max = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = 'métrica'
        verbose_name_plural = 'métricas'
        ordering = ['caracteristica__nombre', 'nombre']

    def __str__(self):
        return self.nombre

    def rango_esperado(self):
        """Rango admisible con su unidad (HU-09).

        Devuelve ``None`` cuando la métrica no declara ningún límite; con un
        solo límite devuelve ese límite como mínimo o como máximo.
        """
        if self.valor_min is None and self.valor_max is None:
            return None
        if self.valor_max is None:
            texto = f'≥ {_formatear_numero(self.valor_min)}'
        elif self.valor_min is None:
            texto = f'≤ {_formatear_numero(self.valor_max)}'
        else:
            texto = (
                f'{_formatear_numero(self.valor_min)} – '
                f'{_formatear_numero(self.valor_max)}'
            )
        return f'{texto} {self.unidad}'.strip()

    def umbrales_por_modelo(self):
        """Umbral informativo de la métrica en cada modelo que la incluye.

        El catálogo de HU-09 es de solo lectura: se consulta, nunca se edita.
        Se omiten las configuraciones inactivas (``activa=False``), porque su
        umbral no aplica al modelo.
        """
        return self.modelo_metricas.filter(activa=True).select_related(
            'modelo_calidad'
        ).order_by('modelo_calidad__nombre')

    def validar_rango(self, valor):
        """Valida el valor contra ``valor_min``/``valor_max``.

        Con ambos límites en ``NULL`` el rango no se valida y el valor se
        acepta (H3-1).
        """
        if valor is None:
            return False
        if self.valor_min is not None and valor < self.valor_min:
            return False
        if self.valor_max is not None and valor > self.valor_max:
            return False
        return True

    @classmethod
    def revisiones_de_proyecto(cls, proyecto):
        """Revisiones de todas las métricas en las aplicaciones del proyecto."""
        return RevisionMetrica.objects.filter(
            metrica_aplicada__modelo_aplicado__proyecto=proyecto,
        )

    @classmethod
    def ultimos_valores_por_metrica(cls, proyecto):
        """Último valor de cada métrica, buscando en todas las aplicaciones."""
        ultimos = {}
        for metrica_id, valor in cls.revisiones_de_proyecto(proyecto).order_by(
            '-fecha', '-pk'
        ).values_list('metrica_aplicada__metrica_id', 'valor'):
            ultimos.setdefault(metrica_id, valor)
        return ultimos

    def revisiones(self, proyecto):
        """Revisiones de la métrica en **todas** las aplicaciones del proyecto."""
        return self.revisiones_de_proyecto(proyecto).filter(
            metrica_aplicada__metrica=self,
        ).select_related('metrica_aplicada', 'miembro_proyecto__persona')

    def ultima_revision(self, proyecto):
        return self.revisiones(proyecto).order_by('-fecha', '-pk').first()

    def ultimo_valor(self, proyecto):
        revision = self.ultima_revision(proyecto)
        return revision.valor if revision is not None else None

    def instantanea_vigente(self, proyecto):
        return MetricaAplicada.objects.filter(
            metrica=self,
            modelo_aplicado__proyecto=proyecto,
            modelo_aplicado__vigente=True,
        ).first()

    def esta_aceptada(self, proyecto):
        """Reevalúa el último valor con el umbral de la instantánea vigente."""
        instantanea = self.instantanea_vigente(proyecto)
        if instantanea is None:
            return False
        valor = self.ultimo_valor(proyecto)
        if valor is None:
            return False
        return instantanea.evaluar_cumplimiento(valor)


class ModeloMetrica(models.Model):
    """Configuración de una métrica dentro de un modelo de calidad."""

    modelo_calidad = models.ForeignKey(
        ModeloCalidad,
        on_delete=models.CASCADE,
        related_name='modelo_metricas',
    )
    metrica = models.ForeignKey(
        Metrica,
        on_delete=models.PROTECT,
        related_name='modelo_metricas',
    )
    umbral = models.FloatField()
    tipo_umbral = models.CharField(
        max_length=10,
        choices=TipoUmbral.choices,
        default=TipoUmbral.MINIMO,
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'métrica de modelo'
        verbose_name_plural = 'métricas de modelo'
        ordering = ['metrica__caracteristica__nombre', 'metrica__nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['modelo_calidad', 'metrica'],
                name='modelo_metrica_unica_por_modelo',
            ),
            models.CheckConstraint(
                condition=models.Q(tipo_umbral__in=['MINIMO', 'MAXIMO']),
                name='modelo_metrica_tipo_umbral_valido',
            ),
        ]

    def __str__(self):
        return f'{self.modelo_calidad} · {self.metrica}'

    def evaluar_cumplimiento(self, valor):
        if valor is None:
            return False
        if self.tipo_umbral == TipoUmbral.MINIMO:
            return valor >= self.umbral
        return valor <= self.umbral

    def esta_activa(self):
        return self.activa


class ModeloAplicado(models.Model):
    """Aplicación de un modelo a un proyecto (historial, ``hu2_clases.puml``)."""

    proyecto = models.ForeignKey(
        'reportes.Proyecto',
        on_delete=models.CASCADE,
        related_name='modelos_aplicados',
    )
    modelo_calidad = models.ForeignKey(
        ModeloCalidad,
        on_delete=models.PROTECT,
        related_name='aplicaciones',
    )
    fecha_aplicacion = models.DateField(default=timezone.localdate)
    fecha_cierre = models.DateField(null=True, blank=True)
    vigente = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'modelo aplicado'
        verbose_name_plural = 'modelos aplicados'
        ordering = ['-fecha_aplicacion', '-pk']
        constraints = [
            models.UniqueConstraint(
                fields=['proyecto'],
                condition=models.Q(vigente=True),
                name='modelo_aplicado_vigente_unico_por_proyecto',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(vigente=True, fecha_cierre__isnull=True)
                    | models.Q(vigente=False, fecha_cierre__isnull=False)
                ),
                name='modelo_aplicado_cierre_coherente',
            ),
        ]

    def __str__(self):
        return f'{self.proyecto} · {self.modelo_calidad}'

    def es_vigente(self):
        return self.vigente

    def cerrar(self):
        self.vigente = False
        self.fecha_cierre = timezone.localdate()
        self.save(update_fields=['vigente', 'fecha_cierre'])

    def crear_instantanea(self):
        """Copia cada ``ModeloMetrica`` a una ``MetricaAplicada`` inmutable."""
        for modelo_metrica in self.modelo_calidad.modelo_metricas.all():
            MetricaAplicada.objects.get_or_create(
                modelo_aplicado=self,
                metrica=modelo_metrica.metrica,
                defaults={
                    'umbral': modelo_metrica.umbral,
                    'tipo_umbral': modelo_metrica.tipo_umbral,
                    'activa': modelo_metrica.activa,
                },
            )
        return self.metricas_aplicadas()

    def metricas_aplicadas(self):
        return self.instantaneas.select_related('metrica')

    def metrica_aplicada(self, metrica):
        return self.instantaneas.filter(metrica=metrica).first()

    def metricas_por_caracteristica(self, caracteristica):
        return self.instantaneas.filter(
            metrica__caracteristica=caracteristica
        ).select_related('metrica')

    def metricas_comunes(self, otro):
        """Métricas que también están en otra aplicación (identidad estable)."""
        if otro is None:
            return Metrica.objects.none()
        propias = set(self.instantaneas.values_list('metrica_id', flat=True))
        ajenas = set(otro.instantaneas.values_list('metrica_id', flat=True))
        return Metrica.objects.filter(pk__in=propias & ajenas)


class MetricaAplicada(models.Model):
    """Instantánea inmutable de ``ModeloMetrica`` al aplicar el modelo."""

    modelo_aplicado = models.ForeignKey(
        ModeloAplicado,
        on_delete=models.CASCADE,
        related_name='instantaneas',
    )
    metrica = models.ForeignKey(
        Metrica,
        on_delete=models.PROTECT,
        related_name='aplicaciones',
    )
    umbral = models.FloatField()
    tipo_umbral = models.CharField(
        max_length=10,
        choices=TipoUmbral.choices,
        default=TipoUmbral.MINIMO,
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'métrica aplicada'
        verbose_name_plural = 'métricas aplicadas'
        ordering = ['metrica__caracteristica__nombre', 'metrica__nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['modelo_aplicado', 'metrica'],
                name='metrica_aplicada_unica_por_aplicacion',
            ),
            models.CheckConstraint(
                condition=models.Q(tipo_umbral__in=['MINIMO', 'MAXIMO']),
                name='metrica_aplicada_tipo_umbral_valido',
            ),
        ]

    def __str__(self):
        return f'{self.modelo_aplicado} · {self.metrica}'

    def save(self, *args, **kwargs):
        """La instantánea no se modifica tras crearse (HU-02/HU-08)."""
        if not self._state.adding:
            raise ValidationError(
                'La instantánea de una métrica no se puede modificar.'
            )
        return super().save(*args, **kwargs)

    def evaluar_cumplimiento(self, valor):
        if valor is None:
            return False
        if self.tipo_umbral == TipoUmbral.MINIMO:
            return valor >= self.umbral
        return valor <= self.umbral

    def esta_activa(self):
        return self.activa

    def revisiones(self):
        return self.revisiones_metrica.order_by('-fecha', '-pk')


class RevisionMetrica(models.Model):
    """Medición de una métrica aplicada, con evidencia y autor (HU-01)."""

    metrica_aplicada = models.ForeignKey(
        MetricaAplicada,
        on_delete=models.CASCADE,
        related_name='revisiones_metrica',
    )
    miembro_proyecto = models.ForeignKey(
        'reportes.MiembroProyecto',
        on_delete=models.CASCADE,
        related_name='revisiones',
    )
    valor = models.FloatField()
    fecha = models.DateField(default=timezone.localdate)
    enlace = models.URLField(max_length=500, blank=True)
    archivo = models.FileField(upload_to='evidencias/metricas/', blank=True)
    cumple = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'revisión de métrica'
        verbose_name_plural = 'revisiones de métricas'
        ordering = ['-fecha', '-pk']
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~models.Q(enlace='') | ~models.Q(archivo='')
                ),
                name='revision_metrica_con_evidencia',
            ),
        ]

    def __str__(self):
        return f'{self.metrica_aplicada} · {self.valor}'

    def clean(self):
        errores = {}
        if self.valor is None:
            errores['valor'] = 'Indica el valor medido.'
        if not self.fecha:
            errores['fecha'] = 'Indica la fecha de la medición.'
        if not self.tiene_evidencia():
            errores['enlace'] = (
                'Adjunta un enlace o un archivo como evidencia.'
            )

        if self.valor is not None and self.metrica_aplicada_id:
            metrica = self.metrica_aplicada.metrica
            if not metrica.validar_rango(self.valor):
                errores['valor'] = (
                    'El valor está fuera del rango admisible de la métrica.'
                )

        if self.miembro_proyecto_id and self.metrica_aplicada_id:
            if (
                self.miembro_proyecto.proyecto_id
                != self.metrica_aplicada.modelo_aplicado.proyecto_id
            ):
                errores['miembro_proyecto'] = (
                    'El autor debe pertenecer al proyecto de la métrica.'
                )

        if errores:
            raise ValidationError(errores)

    def tiene_evidencia(self):
        return bool(self.enlace or self.archivo)

    def calcular_cumple(self):
        if self.valor is None or self.metrica_aplicada_id is None:
            return False
        return self.metrica_aplicada.evaluar_cumplimiento(self.valor)

    def save(self, *args, **kwargs):
        self.cumple = self.calcular_cumple()
        super().save(*args, **kwargs)
