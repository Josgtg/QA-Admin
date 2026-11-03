from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .forms import EvidenciaForm
from .models import (
    CatalogoTQA,
    Dimension,
    Evidencia,
    Proyecto,
    SeguimientoPaso,
    SeguimientoTecnica,
    TecnicaQA,
)
from .selection import (
    obtener_proyecto_seleccionado,
    seleccionar_proyecto,
)
from .services import RegistroEvidenciaError, RegistrarEvidenciaService
from .validators import FORMATOS_ACEPTADOS, TAMANO_MAXIMO_MB

DIMENSION_META = {
    Dimension.ESPECIFICACION.value: {'color': 'blue', 'icon': 'i-file'},
    Dimension.DISENO.value: {'color': 'purple', 'icon': 'i-layers'},
    Dimension.DESARROLLO.value: {'color': 'green', 'icon': 'i-code'},
    Dimension.CONFORMIDAD.value: {'color': 'orange', 'icon': 'i-shield'},
}


class SeguirTecnicaView(View):
    template_name = 'tecnicas/seguir_tecnica.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        catalogo = None
        tecnicas = TecnicaQA.objects.all()

        catalogo_id = request.GET.get('catalogo')
        if catalogo_id:
            catalogo = get_object_or_404(CatalogoTQA, pk=catalogo_id)
            tecnicas = catalogo.obtener_tecnicas_base()

        todas_las_tecnicas = list(tecnicas)

        dimension = request.GET.get('dimension')
        if dimension not in Dimension.values:
            dimension = ''
        else:
            tecnicas = tecnicas.filter(dimension=dimension)

        proyectos = Proyecto.objects.all()
        proyecto_id = request.GET.get('proyecto')
        if proyecto_id:
            proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        else:
            proyecto = obtener_proyecto_seleccionado(request)
        seleccionar_proyecto(request, proyecto)

        grupos, seguimientos = self._agrupar_por_dimension(
            proyecto,
            todas_las_tecnicas,
        )
        seleccionadas_ids = [
            seguimiento.tecnica_id for seguimiento in seguimientos
        ]
        tecnicas_visibles_ids = {tecnica.pk for tecnica in tecnicas}
        tecnicas_ocultas_seleccionadas = [
            tecnica_id
            for tecnica_id in seleccionadas_ids
            if tecnica_id not in tecnicas_visibles_ids
        ]
        tecnicas_con_evidencia = [
            seguimiento.tecnica_id
            for seguimiento in seguimientos
            if seguimiento.tiene_evidencias_registradas()
        ]
        dimensiones_sin_tecnicas = [
            grupo['label'] for grupo in grupos if grupo['sin_tecnicas']
        ]

        return render(
            request,
            self.template_name,
            {
                'catalogo': catalogo,
                'tecnicas': tecnicas,
                'proyecto': proyecto,
                'proyectos': proyectos,
                'grupos': grupos,
                'seguimientos': seguimientos,
                'seleccionadas_ids': seleccionadas_ids,
                'tecnicas_ocultas_seleccionadas': tecnicas_ocultas_seleccionadas,
                'tecnicas_con_evidencia': tecnicas_con_evidencia,
                'dimensiones': Dimension.choices,
                'dimension_seleccionada': dimension,
                'dimensiones_sin_tecnicas': dimensiones_sin_tecnicas,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        return self.seguir_tecnica(request)

    def seguir_tecnica(self, request: HttpRequest) -> HttpResponse:
        proyecto_id = (
            request.POST.get('proyecto_id')
            or request.POST.get('proyecto')
        )
        if not proyecto_id:
            return HttpResponseBadRequest('Debe indicar el proyecto.')

        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        quitar_id = request.POST.get('quitar')
        if quitar_id:
            seguimiento = get_object_or_404(
                SeguimientoTecnica,
                pk=quitar_id,
                proyecto=proyecto,
            )
            nombre = seguimiento.tecnica.nombre
            proyecto.remover_tecnica(seguimiento.pk)
            messages.success(
                request,
                f'La técnica "{nombre}" se quitó del seguimiento del proyecto.',
            )
            return self._volver_al_proyecto(proyecto)

        tecnicas_ids = {
            int(tecnica_id)
            for tecnica_id in request.POST.getlist('tecnicas')
            if tecnica_id.isdigit()
        }

        for tecnica in TecnicaQA.objects.filter(pk__in=tecnicas_ids):
            proyecto.seguir_tecnica(tecnica)

        for seguimiento in proyecto.seguimientos.filter(
            activa=True
        ).exclude(tecnica_id__in=tecnicas_ids):
            proyecto.remover_tecnica(seguimiento.pk)

        grupos, _ = self._agrupar_por_dimension(
            proyecto,
            list(TecnicaQA.objects.all()),
        )
        dimensiones_sin_tecnicas = [
            grupo['label'] for grupo in grupos if grupo['sin_tecnicas']
        ]

        if dimensiones_sin_tecnicas:
            messages.warning(
                request,
                'Dimensiones sin técnicas seleccionadas: '
                f'{", ".join(dimensiones_sin_tecnicas)}. '
                'La selección se guardó de todos modos.',
            )

        messages.success(request, 'Selección de técnicas guardada.')
        return self._volver_al_proyecto(proyecto)

    def _agrupar_por_dimension(self, proyecto, tecnicas):
        seguimientos = []
        if proyecto:
            seguimientos = list(
                proyecto.seguimientos.filter(activa=True)
                .select_related('tecnica')
                .order_by('tecnica__nombre')
            )

        grupos = []
        for valor, etiqueta in Dimension.choices:
            meta = DIMENSION_META[valor]
            seleccionadas = [
                seguimiento
                for seguimiento in seguimientos
                if seguimiento.tecnica.dimension == valor
            ]
            total = sum(1 for tecnica in tecnicas if tecnica.dimension == valor)
            grupos.append(
                {
                    'valor': valor,
                    'label': etiqueta,
                    'color': meta['color'],
                    'icon': meta['icon'],
                    'total': total,
                    'seleccionadas': seleccionadas,
                    'seleccionadas_count': len(seleccionadas),
                    'sin_tecnicas': not seleccionadas,
                    'porcentaje': (
                        round(len(seleccionadas) / total * 100) if total else 0
                    ),
                }
            )
        return grupos, seguimientos

    def _volver_al_proyecto(self, proyecto):
        return redirect(
            f'{reverse("tecnicas:seguimiento")}?proyecto={proyecto.pk}'
        )


class RegistrarEvidenciaView(View):
    """Registra la evidencia de un paso de una técnica (HU-10)."""

    template_name = 'tecnicas/registrar_evidencia.html'

    def get(
        self,
        request: HttpRequest,
        seguimiento_id: int,
    ) -> HttpResponse:
        """Muestra los pasos de la técnica y el formulario de evidencia."""
        seguimiento = self._obtener_seguimiento(request, seguimiento_id)
        if seguimiento is None:
            return redirect('tecnicas:seguimiento')
        return self._renderizar(request, seguimiento, EvidenciaForm())

    def post(
        self,
        request: HttpRequest,
        seguimiento_id: int,
    ) -> HttpResponse:
        """Registra la evidencia del paso elegido y lo completa."""
        seguimiento = self._obtener_seguimiento(request, seguimiento_id)
        if seguimiento is None:
            return redirect('tecnicas:seguimiento')

        paso_id = (request.POST.get('paso_id') or '').strip()
        if not paso_id.isdigit():
            raise Http404('Debe indicar el paso que recibe la evidencia.')

        seguimiento_paso = self._obtener_paso(seguimiento, int(paso_id))

        formulario = EvidenciaForm(request.POST, request.FILES)
        if formulario.is_valid():
            servicio = RegistrarEvidenciaService(seguimiento_paso)
            try:
                servicio.registrar(**formulario.cleaned_data)
            except RegistroEvidenciaError as error:
                messages.error(request, str(error))
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(
                    request,
                    'Evidencia registrada. El paso '
                    f'{seguimiento_paso.paso.orden} quedó completado.',
                )
                url = reverse(
                    'tecnicas:pasos',
                    args=[seguimiento.pk],
                )
                return redirect(f'{url}#paso-{seguimiento_paso.pk}')

        return self._renderizar(
            request,
            seguimiento,
            formulario,
            paso_id=seguimiento_paso.pk,
        )

    def _obtener_seguimiento(self, request, seguimiento_id):
        """Recupera el seguimiento y avisa si la técnica ya no está activa."""
        seguimiento = get_object_or_404(
            SeguimientoTecnica.objects.select_related('tecnica', 'proyecto'),
            pk=seguimiento_id,
        )
        seleccionar_proyecto(request, seguimiento.proyecto)
        if not seguimiento.activa:
            messages.warning(
                request,
                f'La técnica "{seguimiento.tecnica.nombre}" ya no está en '
                'seguimiento. Vuelve a seleccionarla para registrar '
                'evidencias.',
            )
            return None
        return seguimiento

    def _obtener_paso(self, seguimiento, paso_id):
        """Devuelve el paso solo si pertenece al seguimiento consultado."""
        return get_object_or_404(
            SeguimientoPaso,
            pk=paso_id,
            seguimiento=seguimiento,
        )

    def _renderizar(self, request, seguimiento, formulario, paso_id=None):
        """Prepara el contexto de la pantalla de pasos y evidencias."""
        pasos = list(seguimiento.obtener_pasos())
        total = len(pasos)
        completados = sum(1 for paso in pasos if paso.completado)
        pendientes = [paso for paso in pasos if not paso.completado]
        tecnica = seguimiento.tecnica
        if paso_id is None and pendientes:
            paso_id = pendientes[0].pk

        return render(
            request,
            self.template_name,
            {
                'proyecto': seguimiento.proyecto,
                'seguimiento': seguimiento,
                'tecnica': tecnica,
                'pasos': pasos,
                'pasos_pendientes': pendientes,
                'paso_seleccionado': paso_id,
                'completados': completados,
                'total_pasos': total,
                'porcentaje': (
                    round(completados / total * 100, 1) if total else 0
                ),
                'formulario': formulario,
                'dimension_meta': DIMENSION_META[tecnica.dimension],
                'formatos_aceptados': FORMATOS_ACEPTADOS,
                'tamano_maximo_mb': TAMANO_MAXIMO_MB,
                'autores': list(
                    seguimiento.proyecto.equipo_activo().values_list(
                        'persona__nombre',
                        flat=True,
                    )
                ),
            },
        )


class AbrirEvidenciaView(View):
    """Abre el archivo o el enlace de una evidencia registrada (HU-10)."""

    def get(self, request: HttpRequest, evidencia_id: int) -> HttpResponse:
        """Devuelve el archivo de la evidencia o redirige a su enlace."""
        evidencia = self.obtener_evidencia(evidencia_id)

        if evidencia.es_archivo():
            try:
                archivo = evidencia.abrir_archivo()
            except FileNotFoundError as error:
                raise Http404(
                    'El archivo de la evidencia no está disponible.'
                ) from error
            return FileResponse(
                archivo,
                as_attachment=False,
                filename=evidencia.nombre_archivo(),
            )

        if evidencia.enlace:
            return redirect(evidencia.enlace)

        raise Http404('La evidencia no tiene archivo ni enlace.')

    def obtener_evidencia(self, evidencia_id: int) -> Evidencia:
        """Recupera la evidencia con su paso, seguimiento y proyecto."""
        return get_object_or_404(
            Evidencia.objects.select_related(
                'seguimiento_paso__seguimiento__proyecto'
            ),
            pk=evidencia_id,
        )
