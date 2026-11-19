"""Vista del tablero del proyecto."""

import math
from datetime import date

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from apps.tecnicas.selection import seleccionar_proyecto

from ..forms import RangoFechasForm
from ..models import (
    Proyecto,
    caidas_salud,
    registrar_salud,
    tendencia_salud,
)
from .metricas import resumen_metricas


class TableroProyectoView(View):
    template_name = 'reportes/tablero_proyecto.html'
    ancho_grafica = 320
    alto_grafica = 150
    margen_grafica = 12
    margen_eje_y = 28
    separacion_etiquetas = 44
    radio_anillo = 68
    registros_por_defecto = 30

    def get(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        registro_actual = registrar_salud(proyecto)
        rango_form = RangoFechasForm(request.GET or None)
        tendencia = self.obtener_tendencia(proyecto, rango_form)
        salud = registro_actual.indice if registro_actual else None
        ultimo_registro = proyecto.registros_salud.order_by('-fecha').first()
        ultima_actualizacion = (
            ultimo_registro.actualizado if ultimo_registro else None
        )
        caidas = caidas_salud(tendencia)
        aplicado = proyecto.modelo_aplicado_vigente()

        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
                'proyectos': Proyecto.objects.all(),
                'equipo': proyecto.equipo_activo(),
                'seguimientos': proyecto.seguimientos_activos(),
                'aplicado': aplicado,
                'metricas_aplicadas': resumen_metricas(proyecto, aplicado),
                'revisiones': proyecto.revisiones()[:10],
                'salud': salud,
                'tono_salud': self.tono_salud(salud),
                'riesgo_salud': self.riesgo_salud(salud),
                'desplazamiento_anillo': self.desplazamiento_anillo(salud),
                'tendencia': tendencia,
                'puntos_tendencia': self.puntos_tendencia(tendencia, caidas),
                'hay_historial': ultimo_registro is not None,
                'historial_recortado': (
                    len(tendencia) == self.registros_por_defecto
                    and not rango_form.has_changed()
                ),
                'rango_form': rango_form,
                'datos_insuficientes': len(tendencia) < 2,
                'caidas': caidas,
                'ultima_actualizacion': ultima_actualizacion,
            },
        )

    def obtener_tendencia(self, proyecto, rango_form):
        """Registros del rango pedido o, sin rango, los más recientes."""
        if rango_form.is_bound and rango_form.is_valid():
            desde = rango_form.cleaned_data['desde']
            hasta = rango_form.cleaned_data['hasta']
            if desde or hasta:
                return tendencia_salud(
                    proyecto, limite=None, desde=desde, hasta=hasta
                )
        return tendencia_salud(proyecto, limite=self.registros_por_defecto)

    def tono_salud(self, salud):
        if salud is None:
            return 'gray'
        if salud >= 80:
            return 'green'
        if salud >= 60:
            return 'amber'
        if salud >= 40:
            return 'orange'
        return 'gray'

    def riesgo_salud(self, salud):
        if salud is None:
            return 'Sin datos'
        if salud >= 80:
            return 'Bajo'
        if salud >= 60:
            return 'Medio'
        if salud >= 40:
            return 'Alto'
        return 'Crítico'

    def desplazamiento_anillo(self, salud):
        perimetro = 2 * math.pi * self.radio_anillo
        valor = 0 if salud is None else min(max(salud, 0), 100)
        return round(perimetro * (1 - valor / 100), 1)

    def puntos_tendencia(self, registros, caidas=()):
        """Ubica cada registro en la gráfica según su fecha y su índice."""
        if not registros:
            return []

        fechas_caida = {caida['fecha'] for caida in caidas}
        primero = registros[0].fecha
        dias = (registros[-1].fecha - primero).days
        util_ancho = (
            self.ancho_grafica - self.margen_eje_y - self.margen_grafica
        )
        util_alto = self.alto_grafica - 2 * self.margen_grafica
        puntos = []
        for registro in registros:
            valor = min(max(registro.indice, 0), 100)
            avance = (registro.fecha - primero).days / dias if dias else 0.5
            puntos.append(
                {
                    'x': round(self.margen_eje_y + avance * util_ancho, 1),
                    'y': round(
                        self.alto_grafica
                        - self.margen_grafica
                        - (valor / 100) * util_alto,
                        1,
                    ),
                    'fecha': registro.fecha,
                    'indice': registro.indice,
                    'es_caida': registro.fecha in fechas_caida,
                    'con_etiqueta': False,
                }
            )
        self.marcar_etiquetas(puntos)
        return puntos

    def marcar_etiquetas(self, puntos):
        """Marca las fechas visibles del eje sin que se encimen."""
        visibles = []
        for punto in puntos:
            if (
                not visibles
                or punto['x'] - visibles[-1]['x'] >= self.separacion_etiquetas
            ):
                visibles.append(punto)
        ultimo = puntos[-1]
        if visibles[-1] is not ultimo:
            if (
                len(visibles) > 1
                and ultimo['x'] - visibles[-1]['x'] < self.separacion_etiquetas
            ):
                visibles.pop()
            visibles.append(ultimo)
        for punto in visibles:
            punto['con_etiqueta'] = True

    def volver_a_lista(self):
        return redirect('reportes:lista')