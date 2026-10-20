from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.tecnicas.models import Proyecto

from .forms import ProyectoForm
from .models import Periodo


class ListaProyectosView(View):
    template_name = 'reportes/lista_proyectos.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        try:
            periodo_seleccionado = Periodo.desde_parametro(
                request.GET.get('periodo')
            )
        except ValueError as error:
            raise Http404(str(error)) from error

        periodos = Periodo.obtener_recientes()
        if periodo_seleccionado and periodo_seleccionado not in periodos:
            periodos.append(periodo_seleccionado)

        grupos = {periodo.id: self._grupo(periodo) for periodo in periodos}
        opciones = [
            {'periodo': periodo, 'total': grupos[periodo.id]['total']}
            for periodo in periodos
        ]

        if periodo_seleccionado:
            grupos_visibles = [grupos[periodo_seleccionado.id]]
        else:
            grupos_visibles = [grupos[periodo.id] for periodo in periodos]

        total_proyectos = sum(opcion['total'] for opcion in opciones)

        return render(
            request,
            self.template_name,
            {
                'grupos': grupos_visibles,
                'periodos': periodos,
                'opciones': opciones,
                'periodo_seleccionado': periodo_seleccionado,
                'hay_proyectos': Proyecto.objects.exists(),
                'total_proyectos': total_proyectos,
            },
        )

    def listar_proyectos(self, periodo_id):
        if not periodo_id:
            return Proyecto.objects.none()
        return Periodo.desde_parametro(periodo_id).obtener_proyectos()

    def _grupo(self, periodo):
        proyectos = list(periodo.obtener_proyectos())
        return {
            'periodo': periodo,
            'proyectos': proyectos,
            'total': len(proyectos),
        }


class CrearProyectoView(View):
    template_name = 'reportes/proyecto_form.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return self._renderizar(request, ProyectoForm())

    def post(self, request: HttpRequest) -> HttpResponse:
        form = ProyectoForm(request.POST)
        if form.is_valid():
            proyecto = form.save()
            messages.success(
                request,
                f'Proyecto "{proyecto.nombre}" creado correctamente.',
            )
            return redirect('reportes:lista')
        return self._renderizar(request, form)

    def _renderizar(self, request, form):
        return render(
            request,
            self.template_name,
            {
                'form': form,
            },
        )
