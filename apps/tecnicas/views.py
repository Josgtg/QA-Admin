from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .models import (
    CatalogoTQA,
    Dimension,
    Proyecto,
    SeguimientoTecnica,
    TecnicaQA,
)

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
            proyecto = proyectos.first()

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
        proyecto_id = request.POST.get('proyecto')
        if not proyecto_id:
            return HttpResponseBadRequest('Debe indicar el proyecto.')

        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)

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
