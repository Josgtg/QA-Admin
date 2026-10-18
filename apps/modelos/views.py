from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views import View

from .models import ModeloCalidad


class CatalogoModelosView(View):
    template_name = 'modelos/catalogo_modelos.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            self.template_name,
            {'modelos': self.obtener_modelos_base()},
        )

    def obtener_modelos_base(self):
        return ModeloCalidad.obtener_predefinidos()
