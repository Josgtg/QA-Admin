from django.core.exceptions import ValidationError
from django.db import models


class TipoUmbral(models.TextChoices):
    MINIMO = 'MINIMO', 'Mínimo'
    MAXIMO = 'MAXIMO', 'Máximo'


class ModeloCalidad(models.Model):
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
            'caracteristicas__metricas'
        )

    def obtener_caracteristicas(self):
        return self.caracteristicas.all()


class Caracteristica(models.Model):
    modelo = models.ForeignKey(
        ModeloCalidad,
        on_delete=models.CASCADE,
        related_name='caracteristicas',
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = 'característica'
        verbose_name_plural = 'características'
        ordering = ['id']

    def __str__(self):
        return f'{self.modelo} - {self.nombre}'

    def obtener_metricas(self):
        return self.metricas.all()


class Metrica(models.Model):
    caracteristica = models.ForeignKey(
        Caracteristica,
        on_delete=models.CASCADE,
        related_name='metricas',
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    unidad = models.CharField(max_length=50)
    meta = models.FloatField(null=True, blank=True)
    tipo_umbral = models.CharField(
        max_length=10,
        choices=TipoUmbral.choices,
        default=TipoUmbral.MINIMO,
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'métrica'
        verbose_name_plural = 'métricas'
        ordering = ['id']

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.activa and self.meta is None:
            raise ValidationError(
                {'meta': 'Una métrica activa debe tener una meta.'}
            )

    def cumple_meta(self, valor):
        if self.tipo_umbral == TipoUmbral.MINIMO:
            return valor >= self.meta
        return valor <= self.meta
