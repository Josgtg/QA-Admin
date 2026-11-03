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
admin.site.register(RevisionMetrica)


@admin.register(MetricaAplicada)
class MetricaAplicadaAdmin(admin.ModelAdmin):
    """La instantánea es inmutable: se consulta, no se edita."""

    list_display = (
        'metrica',
        'modelo_aplicado',
        'umbral',
        'tipo_umbral',
        'activa',
    )
    list_filter = ('tipo_umbral', 'activa')
    search_fields = ('metrica__nombre', 'modelo_aplicado__proyecto__nombre')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
