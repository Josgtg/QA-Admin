from django.contrib import admin

from .models import (
    CatalogoTQA,
    Evidencia,
    Paso,
    SeguimientoPaso,
    SeguimientoTecnica,
    TecnicaQA,
)

admin.site.register(CatalogoTQA)
admin.site.register(TecnicaQA)
admin.site.register(Paso)
admin.site.register(SeguimientoTecnica)
admin.site.register(SeguimientoPaso)
admin.site.register(Evidencia)
