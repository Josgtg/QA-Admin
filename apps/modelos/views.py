from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.reportes.models import Proyecto
from apps.tecnicas.selection import (
    obtener_proyecto_seleccionado,
    seleccionar_proyecto,
)

from .forms import RevisionMetricaForm
from .models import MetricaAplicada, ModeloCalidad


class CatalogoModelosView(View):
    """Catálogo detallado de los modelos predefinidos (HU-03)."""

    template_name = 'modelos/catalogo_modelos.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            self.template_name,
            {'modelos': self.obtener_modelos_base()},
        )

    def obtener_modelos_base(self):
        return ModeloCalidad.obtener_predefinidos()

    def obtener_detalle(self, modelo_id):
        return get_object_or_404(
            ModeloCalidad,
            pk=modelo_id,
            predefinido=True,
        )


class ModeloDelProyectoView(View):
    """Entrada del menú lateral al modelo del proyecto activo (HU-02).

    El enlace del sidebar no conoce el identificador del proyecto, así que se
    resuelve con el proyecto seleccionado en la sesión. No renderiza nada: la
    pantalla es ``AplicarModeloView``, y el catálogo detallado (HU-03) se
    consulta desde un botón de esa misma pantalla.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        proyecto = obtener_proyecto_seleccionado(request)
        if proyecto is None:
            messages.info(
                request,
                'Registra un proyecto para consultar su modelo de calidad.',
            )
            return redirect('reportes:lista')
        seleccionar_proyecto(request, proyecto)
        return redirect(
            'reportes:aplicar_modelo', proyecto_id=proyecto.pk
        )


class AplicarModeloView(View):
    """Aplica un modelo predefinido al proyecto (HU-02)."""

    template_name = 'modelos/seleccion_modelo.html'

    def get(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)
        return self._render(request, proyecto)

    def post(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        modelo_id = request.POST.get('modelo_id')
        if not modelo_id:
            return HttpResponseBadRequest('Debe indicar el modelo.')

        modelo = get_object_or_404(
            ModeloCalidad,
            pk=modelo_id,
            predefinido=True,
        )
        confirmado = request.POST.get('confirmacion') == '1'

        vigente = self.obtener_modelo_aplicado_vigente(proyecto)
        if vigente is not None and vigente.modelo_calidad_id == modelo.pk:
            return self._render(request, proyecto)

        if self.solicitar_confirmacion(proyecto, modelo) and not confirmado:
            return self._render(
                request,
                proyecto,
                modelo=modelo,
                requiere_confirmacion=True,
            )

        try:
            proyecto.aplicar_modelo(modelo)
        except ValidationError as error:
            return self._render(
                request,
                proyecto,
                modelo=modelo,
                error=error.messages[0],
            )

        messages.success(
            request,
            f'Modelo "{modelo.nombre}" aplicado al proyecto.',
        )
        return redirect('reportes:tablero', proyecto_id=proyecto.pk)

    def obtener_modelo_aplicado_vigente(self, proyecto):
        return proyecto.modelo_aplicado_vigente()

    def solicitar_confirmacion(self, proyecto, modelo):
        """Pide confirmación si cambia el modelo y ya hay mediciones."""
        vigente = self.obtener_modelo_aplicado_vigente(proyecto)
        if vigente is None:
            return False
        if vigente.modelo_calidad_id == modelo.pk:
            return False
        return proyecto.tiene_mediciones()

    def _render(
        self,
        request,
        proyecto,
        modelo=None,
        requiere_confirmacion=False,
        error=None,
    ):
        vigente = self.obtener_modelo_aplicado_vigente(proyecto)
        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
                'modelos': ModeloCalidad.obtener_predefinidos(),
                'modelo': modelo,
                'vigente': vigente,
                'requiere_confirmacion': requiere_confirmacion,
                'error': error,
                'tiene_mediciones': proyecto.tiene_mediciones(),
            },
        )


class RegistrarRevisionMetricaView(View):
    """Registro de una revisión de métrica y su historial (HU-01)."""

    template_name = 'modelos/revision_metrica.html'

    def get(
        self, request: HttpRequest, proyecto_id: int, metrica_id: int
    ) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        instantanea = self.obtener_metrica_aplicada(proyecto, metrica_id)
        if instantanea is None:
            return self._sin_modelo(request, proyecto)

        return self._render(
            request,
            proyecto,
            instantanea,
            RevisionMetricaForm(proyecto=proyecto),
        )

    def post(
        self, request: HttpRequest, proyecto_id: int, metrica_id: int
    ) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        instantanea = self.obtener_metrica_aplicada(proyecto, metrica_id)
        if instantanea is None:
            return self._sin_modelo(request, proyecto)

        form = RevisionMetricaForm(
            request.POST,
            request.FILES,
            proyecto=proyecto,
        )
        if not form.is_valid():
            return self._render(request, proyecto, instantanea, form)

        revision = form.save(commit=False)
        revision.metrica_aplicada = instantanea
        try:
            revision.full_clean()
        except ValidationError as error:
            for campo, mensajes_error in error.message_dict.items():
                if campo in form.fields:
                    form.add_error(campo, mensajes_error)
                else:
                    form.add_error(None, mensajes_error)
            return self._render(request, proyecto, instantanea, form)

        revision.save()
        messages.success(request, 'Revisión de métrica registrada.')
        return redirect('reportes:metricas', proyecto_id=proyecto.pk)

    def obtener_metrica_aplicada(self, proyecto, metrica):
        """Instantánea vigente de la métrica en el proyecto."""
        aplicado = proyecto.modelo_aplicado_vigente()
        if aplicado is None:
            return None
        if hasattr(metrica, 'pk'):
            return aplicado.metrica_aplicada(metrica)
        return MetricaAplicada.objects.filter(
            metrica_id=metrica,
            modelo_aplicado=aplicado,
        ).first()

    def obtener_historial(self, proyecto, metrica):
        return metrica.revisiones(proyecto)

    def _sin_modelo(self, request, proyecto):
        messages.warning(
            request,
            'Aplica un modelo de calidad al proyecto antes de registrar '
            'métricas.',
        )
        return redirect(
            'reportes:aplicar_modelo', proyecto_id=proyecto.pk
        )

    def _render(self, request, proyecto, instantanea, form):
        metrica = instantanea.metrica
        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
                'instantanea': instantanea,
                'metrica': metrica,
                'form': form,
                'ultima': metrica.ultima_revision(proyecto),
                'valor_ultimo': metrica.ultimo_valor(proyecto),
                'historial': self.obtener_historial(proyecto, metrica),
                'aceptada': metrica.esta_aceptada(proyecto),
                'seguimiento': metrica.caracteristica.calcular_seguimiento(
                    proyecto
                ),
            },
        )
