from django.contrib import admin

from .models import DetalleSalud, MiembroProyecto, Persona, RegistroSalud

admin.site.register(Persona)
admin.site.register(MiembroProyecto)
admin.site.register(RegistroSalud)
admin.site.register(DetalleSalud)
