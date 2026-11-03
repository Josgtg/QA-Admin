from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.reportes.models import Proyecto
from apps.tecnicas.estado import EstadoTecnica
from apps.tecnicas.models import Dimension, SeguimientoTecnica, TecnicaQA
from apps.tecnicas.selection import (
    obtener_proyecto_seleccionado,
    seleccionar_proyecto,
)

from .forms import EvidenciaForm
from .models import Evidencia, SeguimientoPaso
from .services import aplicar_seleccion, dimensiones_sin_tecnicas

DIMENSION_META = {
    Dimension.ESPECIFICACION.value: {'color': 'blue', 'icon': 'i-file'},
    Dimension.DISENO.value: {'color': 'purple', 'icon': 'i-layers'},
    Dimension.DESARROLLO.value: {'color': 'green', 'icon': 'i-code'},
    Dimension.CONFORMIDAD.value: {'color': 'orange', 'icon': 'i-shield'},
}


def _ids_seleccionados(request):
    return {
        int(tecnica_id)
        for tecnica_id in request.POST.getlist('tecnicas')
        if tecnica_id.isdigit()
    }


class CatalogoTecnicasView(View):
    """Catálogo de técnicas con filtro por dimensión (HU-04).

    Las tarjetas llevan checkbox para seleccionar técnicas del proyecto activo
    (H4-4=b). Sin proyectos, el catálogo se muestra en modo consulta.
    """

    template_name = 'tecnicas/catalogo_tecnicas.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        proyecto = obtener_proyecto_seleccionado(request)
        if proyecto is not None:
            seleccionar_proyecto(request, proyecto)

        dimension = request.GET.get('dimension')
        if dimension not in Dimension.values:
            dimension = ''

        tecnicas = self.filtrar_por_dimension(dimension)
        seleccionadas = set()
        if proyecto is not None:
            seleccionadas = set(
                proyecto.seguimientos_tecnicas.filter(activa=True).values_list(
                    'tecnica_id', flat=True
                )
            )

        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
                'tecnicas': tecnicas,
                'dimensiones': Dimension.choices,
                'dimension_seleccionada': dimension,
                'seleccionadas_ids': seleccionadas,
                'dimensiones_disponibles': self.dimensiones_disponibles(),
                'sin_proyecto': proyecto is None,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        proyecto = obtener_proyecto_seleccionado(request)
        if proyecto is None:
            messages.error(
                request,
                'Registra un proyecto antes de seleccionar técnicas.',
            )
            return redirect('tecnicas:catalogo')

        seleccionar_proyecto(request, proyecto)
        aplicar_seleccion(proyecto, _ids_seleccionados(request))
        messages.success(request, 'Selección de técnicas guardada.')
        return redirect('tecnicas:catalogo')

    def listar_tecnicas(self):
        return TecnicaQA.objects.all()

    def filtrar_por_dimension(self, dimension=''):
        tecnicas = self.listar_tecnicas()
        if dimension:
            tecnicas = tecnicas.filter(dimension=dimension)
        return tecnicas

    def dimensiones_disponibles(self):
        return [
            {
                'valor': valor,
                'etiqueta': etiqueta,
                'total': TecnicaQA.objects.filter(dimension=valor).count(),
                **DIMENSION_META[valor],
            }
            for valor, etiqueta in Dimension.choices
        ]


class DetalleTecnicaView(View):
    template_name = 'tecnicas/detalle_tecnica.html'

    def get(self, request: HttpRequest, tecnica_id: int) -> HttpResponse:
        tecnica = self.obtener_tecnica(tecnica_id)
        proyecto = obtener_proyecto_seleccionado(request)
        seguimiento = None
        if proyecto is not None:
            seguimiento = proyecto.seguimientos_tecnicas.filter(
                tecnica=tecnica,
                activa=True,
            ).first()

        return render(
            request,
            self.template_name,
            {
                'tecnica': tecnica,
                'pasos': self.obtener_pasos(tecnica),
                'proyecto': proyecto,
                'seguimiento': seguimiento,
            },
        )

    def obtener_tecnica(self, tecnica_id):
        return get_object_or_404(TecnicaQA, pk=tecnica_id)

    def obtener_pasos(self, tecnica):
        return tecnica.obtener_pasos()


class SeguirTecnicaView(View):
    """Selección y seguimiento de las técnicas del proyecto (HU-05)."""

    template_name = 'tecnicas/seguir_tecnica.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        proyectos = Proyecto.objects.all()
        proyecto = self._proyecto(request)
        seleccionar_proyecto(request, proyecto)

        seguimientos = []
        if proyecto is not None:
            seguimientos = list(
                proyecto.seguimientos_tecnicas.filter(activa=True)
                .select_related('tecnica')
                .order_by('tecnica__nombre')
            )

        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
                'proyectos': proyectos,
                'seguimientos': seguimientos,
                'grupos': self._agrupar_por_dimension(seguimientos),
                'dimensiones_sin_tecnicas': (
                    dimensiones_sin_tecnicas(proyecto) if proyecto else []
                ),
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        proyecto_id = (
            request.POST.get('proyecto_id') or request.POST.get('proyecto')
        )
        if not proyecto_id:
            return HttpResponseBadRequest('Debe indicar el proyecto.')

        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        if request.POST.get('quitar'):
            return self.remover_tecnica(request, proyecto)

        return self.seguir_tecnica(request, proyecto)

    def seguir_tecnica(self, request, proyecto):
        aplicar_seleccion(proyecto, _ids_seleccionados(request))

        sin_tecnicas = dimensiones_sin_tecnicas(proyecto)
        if sin_tecnicas:
            messages.warning(
                request,
                'Dimensiones sin técnicas seleccionadas: '
                f'{", ".join(sin_tecnicas)}. '
                'La selección se guardó de todos modos.',
            )
        messages.success(request, 'Selección de técnicas guardada.')
        return self._volver_al_proyecto(proyecto)

    def remover_tecnica(self, request, proyecto):
        seguimiento = get_object_or_404(
            proyecto.seguimientos_tecnicas,
            pk=request.POST.get('quitar'),
        )
        nombre = seguimiento.tecnica.nombre
        seguimiento.desactivar()
        messages.success(
            request,
            f'La técnica "{nombre}" se quitó del seguimiento del proyecto.',
        )
        return self._volver_al_proyecto(proyecto)

    def _proyecto(self, request):
        proyecto_id = request.GET.get('proyecto')
        if proyecto_id:
            return get_object_or_404(Proyecto, pk=proyecto_id)
        return obtener_proyecto_seleccionado(request)

    def _agrupar_por_dimension(self, seguimientos):
        grupos = []
        for valor, etiqueta in Dimension.choices:
            meta = DIMENSION_META[valor]
            seleccionadas = [
                seguimiento
                for seguimiento in seguimientos
                if seguimiento.tecnica.dimension == valor
            ]
            grupos.append(
                {
                    'valor': valor,
                    'label': etiqueta,
                    'color': meta['color'],
                    'icon': meta['icon'],
                    'seleccionadas': seleccionadas,
                    'seleccionadas_count': len(seleccionadas),
                    'sin_tecnicas': not seleccionadas,
                }
            )
        return grupos

    def _volver_al_proyecto(self, proyecto):
        return redirect(
            f'{reverse("tecnicas:seguimiento")}?proyecto={proyecto.pk}'
        )


class RegistrarEvidenciaView(View):
    """Registra la evidencia de un paso y lo marca completado (HU-05/HU-10)."""

    template_name = 'tecnicas/registrar_evidencia.html'

    def get(self, request: HttpRequest, seguimiento_paso_id: int):
        paso = self._paso(seguimiento_paso_id)
        proyecto = paso.seguimiento.proyecto
        seleccionar_proyecto(request, proyecto)
        return self._render(request, paso, EvidenciaForm(proyecto=proyecto))

    def post(self, request: HttpRequest, seguimiento_paso_id: int):
        paso = self._paso(seguimiento_paso_id)
        proyecto = paso.seguimiento.proyecto
        seleccionar_proyecto(request, proyecto)

        form = EvidenciaForm(
            request.POST,
            request.FILES,
            proyecto=proyecto,
            instance=self._evidencia_existente(paso) or None,
        )
        if not form.is_valid():
            return self._render(request, paso, form)

        try:
            evidencia = form.save(commit=False)
            evidencia.seguimiento_paso = paso
            evidencia.full_clean()
            # Reemplazo: se borra la evidencia anterior (y su archivo, vía
            # post_delete) antes de insertar la nueva.
            Evidencia.objects.filter(seguimiento_paso=paso).delete()
            evidencia.pk = None
            evidencia._state.adding = True
            evidencia.save()
            paso.marcar_completado(form.cleaned_data.get('comentario') or '')
        except ValidationError as error:
            form.add_error(None, error)
            return self._render(request, paso, form)

        messages.success(request, 'Evidencia registrada y paso completado.')
        return redirect(
            f'{reverse("tecnicas:seguimiento")}'
            f'?proyecto={paso.seguimiento.proyecto_id}'
        )

    def _paso(self, seguimiento_paso_id):
        return get_object_or_404(
            SeguimientoPaso.objects.select_related(
                'paso', 'seguimiento__proyecto', 'seguimiento__tecnica'
            ),
            pk=seguimiento_paso_id,
        )

    def _evidencia_existente(self, paso):
        return getattr(paso, 'evidencia', None)

    def _render(self, request, paso, form):
        return render(
            request,
            self.template_name,
            {
                'paso': paso,
                'seguimiento': paso.seguimiento,
                'proyecto': paso.seguimiento.proyecto,
                'form': form,
            },
        )


class EstadoTecnicaView(View):
    """Pasos completados y faltantes de una técnica en el proyecto (HU-11).

    Solo lectura: muestra el estado de los pasos, el porcentaje de avance y
    la evidencia de cada paso completado. Registrar evidencia es HU-10.
    """

    template_name = 'tecnicas/estado_tecnica.html'

    def get(
        self, request: HttpRequest, tecnica_id: int
    ) -> HttpResponse:
        tecnica = get_object_or_404(TecnicaQA, pk=tecnica_id)
        proyecto = self._proyecto(request)
        seleccionar_proyecto(request, proyecto)

        estado = self.obtener_estado_tecnica(proyecto, tecnica)

        return render(
            request,
            self.template_name,
            {
                'tecnica': tecnica,
                'proyecto': proyecto,
                'proyectos': Proyecto.objects.all(),
                'seguimiento': estado.seguimiento if estado else None,
                'estado': estado,
                'pasos': estado.pasos if estado else [],
            },
        )

    def _proyecto(self, request):
        """Proyecto a consultar: el de la query (``?proyecto=``) o el activo.

        El parámetro explícito tiene prioridad para que el enlace desde el
        tablero abra el proyecto correcto; sin él se usa el proyecto
        seleccionado en la sesión.
        """
        proyecto_id = request.GET.get('proyecto')
        if proyecto_id:
            return get_object_or_404(Proyecto, pk=proyecto_id)
        return obtener_proyecto_seleccionado(request)

    def obtener_estado_tecnica(self, proyecto, tecnica):
        """Construye el DTO con los pasos y el avance de la técnica.

        Devuelve ``None`` cuando el proyecto no sigue la técnica: sin
        seguimiento no hay pasos que mostrar. Se consideran solo los
        seguimientos activos, porque una técnica retirada (HU-05) conserva sus
        pasos pero ya no forma parte del seguimiento del proyecto.
        """
        if proyecto is None:
            return None
        seguimiento = (
            SeguimientoTecnica.objects.filter(
                proyecto=proyecto,
                tecnica=tecnica,
                activa=True,
            )
            .prefetch_related('pasos__paso', 'pasos__evidencia')
            .first()
        )
        if seguimiento is None:
            return None
        return EstadoTecnica(
            tecnica=tecnica,
            pasos=seguimiento.pasos.all(),
            porcentaje_avance=self.calcular_porcentaje_avance(seguimiento),
            seguimiento=seguimiento,
        )

    def calcular_porcentaje_avance(self, seguimiento):
        """Deriva el avance de los pasos; no lo persiste."""
        return seguimiento.calcular_porcentaje_avance()
