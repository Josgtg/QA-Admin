from django.contrib import admin

from .models import (
    Caracteristica,
    Metrica,
    MetricaAplicada,
    ModeloAplicado,
    ModeloCalidad,
    ModeloMetrica,
    RevisionMetrica,
)

admin.site.register(ModeloCalidad)
admin.site.register(Caracteristica)
admin.site.register(Metrica)
admin.site.register(ModeloMetrica)
admin.site.register(ModeloAplicado)
admin.site.register(MetricaAplicada)
admin.site.register(RevisionMetrica)
