from django.contrib import admin

from .models import MiembroProyecto, Persona, RegistroSalud

admin.site.register(Persona)
admin.site.register(MiembroProyecto)
admin.site.register(RegistroSalud)
