from django.contrib import admin

from .models import Caracteristica, Metrica, ModeloCalidad

admin.site.register(ModeloCalidad)
admin.site.register(Caracteristica)
admin.site.register(Metrica)
