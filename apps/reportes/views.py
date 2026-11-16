import math
from datetime import date

from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.tecnicas.selection import (
    SESSION_KEY,
    obtener_proyecto_seleccionado,
    seleccionar_proyecto,
)

from .forms import MiembroProyectoFormSet, ProyectoForm, RangoFechasForm
from .models import (
    MiembroProyecto,
    Periodo,
    Persona,
    Proyecto,
    ResumenReporte,
    caidas_salud,
    registrar_salud,
    tendencia_salud,
)


class InicioView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        proyecto_id = request.GET.get('proyecto')
        if proyecto_id:
            proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        else:
            proyecto = obtener_proyecto_seleccionado(request)
        if proyecto is None:
            return redirect('reportes:lista')
        seleccionar_proyecto(request, proyecto)
        return redirect('reportes:tablero', proyecto_id=proyecto.pk)


class ListaProyectosView(View):
    template_name = 'reportes/lista_proyectos.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        accion = request.GET.get('ir')
        if accion == 'crear':
            return self.ir_a_crear()
        if accion in {'editar', 'tablero'}:
            proyecto = self._proyecto_de(request)
            if proyecto is not None:
                if accion == 'editar':
                    return self.ir_a_editar(proyecto)
                return self.ir_a_tablero(proyecto)

        try:
            periodo_seleccionado = Periodo.desde_parametro(
                request.GET.get('periodo')
            )
        except ValueError as error:
            raise Http404(str(error)) from error

        busqueda = (request.GET.get('q') or '').strip()

        proyectos = self.listar_proyectos(periodo_seleccionado, busqueda)
        todos = self.listar_proyectos(None, '')
        periodos = self.periodos_disponibles()
        grupos = self.agrupar_por_periodo(proyectos, periodos)
        if periodo_seleccionado is not None:
            grupos = [
                grupo
                for grupo in grupos
                if grupo['periodo'] == periodo_seleccionado
            ]

        opciones = [
            {'periodo': periodo, 'total': self._total(todos, periodo)}
            for periodo in periodos
        ]

        return render(
            request,
            self.template_name,
            {
                'proyectos': proyectos,
                'grupos': grupos,
                'periodos': periodos,
                'opciones': opciones,
                'periodo_seleccionado': periodo_seleccionado,
                'proyecto_seleccionado': self.seleccionar(request, proyectos),
                'hay_proyectos': bool(todos),
                'total_proyectos': len(todos),
                'busqueda': busqueda,
            },
        )

    # --- Métodos del diseño (hu7_clases / hu6_clases) -------------------

    def listar_proyectos(self, periodo=None, busqueda=''):
        """Proyectos del periodo indicado, ordenados por fecha de inicio."""
        consulta = Proyecto.objects.prefetch_related(
            'equipo__persona', 'seguimientos_tecnicas'
        )
        if busqueda:
            consulta = consulta.filter(nombre__icontains=busqueda)
        proyectos = list(consulta.order_by('-fecha_inicio', 'nombre'))
        for proyecto in proyectos:
            proyecto.periodo_actual = proyecto.periodo()
            proyecto.salud_actual = proyecto.indice_salud()
        if periodo is not None:
            proyectos = [
                proyecto
                for proyecto in proyectos
                if proyecto.esta_en_periodo(periodo.nombre)
            ]
        return proyectos

    def periodos_disponibles(self):
        """Los tres periodos, del más reciente al más antiguo."""
        maxima = {}
        for fecha, nombre in (
            (proyecto.fecha_inicio, proyecto.periodo())
            for proyecto in Proyecto.objects.only('fecha_inicio')
        ):
            if nombre not in maxima or fecha > maxima[nombre]:
                maxima[nombre] = fecha

        periodos = [Periodo(nombre) for nombre in Periodo.ESTADOS]
        periodos.sort(
            key=lambda periodo: (
                maxima.get(periodo.nombre) is not None,
                maxima.get(periodo.nombre) or date.min,
            ),
            reverse=True,
        )
        return periodos

    def agrupar_por_periodo(self, proyectos, periodos=None):
        """Siempre los tres grupos, con su lista vacía si no hay proyectos."""
        periodos = periodos if periodos is not None else self.periodos_disponibles()
        grupos = []
        for periodo in periodos:
            del_periodo = [
                proyecto
                for proyecto in proyectos
                if proyecto.periodo_actual == periodo.nombre
            ]
            grupos.append(
                {
                    'periodo': periodo,
                    'proyectos': del_periodo,
                    'total': len(del_periodo),
                }
            )
        return grupos

    def seleccionar(self, request, proyectos):
        """Proyecto del panel de previsualización, sin salir de la lista."""
        seleccionado_id = request.GET.get('seleccionado')
        if seleccionado_id:
            for proyecto in proyectos:
                if str(proyecto.pk) == str(seleccionado_id):
                    seleccionar_proyecto(request, proyecto)
                    return proyecto
            proyecto = get_object_or_404(Proyecto, pk=seleccionado_id)
            proyecto.periodo_actual = proyecto.periodo()
            proyecto.salud_actual = proyecto.indice_salud()
            seleccionar_proyecto(request, proyecto)
            return proyecto

        seleccionado_sesion = request.session.get(SESSION_KEY)
        if seleccionado_sesion:
            for proyecto in proyectos:
                if str(proyecto.pk) == str(seleccionado_sesion):
                    return proyecto
        return proyectos[0] if proyectos else None

    def ir_a_crear(self):
        return redirect('reportes:crear')

    def ir_a_editar(self, proyecto):
        return redirect('reportes:editar', proyecto_id=proyecto.pk)

    def ir_a_tablero(self, proyecto):
        return redirect('reportes:tablero', proyecto_id=proyecto.pk)

    # --- Auxiliares -----------------------------------------------------

    def _proyecto_de(self, request):
        proyecto_id = request.GET.get('proyecto')
        if not proyecto_id:
            return None
        return Proyecto.objects.filter(pk=proyecto_id).first()

    @staticmethod
    def _total(proyectos, periodo):
        return sum(
            1
            for proyecto in proyectos
            if proyecto.periodo_actual == periodo.nombre
        )


class CrearProyectoView(View):
    template_name = 'reportes/proyecto_form.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return self._renderizar(
            request,
            ProyectoForm(),
            MiembroProyectoFormSet(prefix='equipo'),
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        proyecto_form = ProyectoForm(request.POST)
        tiene_equipo = 'equipo-TOTAL_FORMS' in request.POST
        if tiene_equipo:
            equipo_formset = MiembroProyectoFormSet(
                request.POST, prefix='equipo'
            )
            equipo_valido = equipo_formset.is_valid()
        else:
            equipo_formset = MiembroProyectoFormSet(prefix='equipo')
            equipo_valido = True

        if proyecto_form.is_valid() and equipo_valido:
            with transaction.atomic():
                proyecto = proyecto_form.save()
                if tiene_equipo:
                    self._guardar_equipo(proyecto, equipo_formset)
            messages.success(
                request,
                f'Proyecto "{proyecto.nombre}" creado correctamente.',
            )
            return redirect('reportes:lista')

        return self._renderizar(request, proyecto_form, equipo_formset)

    def _renderizar(self, request, proyecto_form, equipo_formset):
        return render(
            request,
            self.template_name,
            {
                'modo': 'crear',
                'form': proyecto_form,
                'proyecto_form': proyecto_form,
                'equipo_formset': equipo_formset,
            },
        )

    def _guardar_equipo(self, proyecto, equipo_formset):
        for form in equipo_formset:
            nombre = form.cleaned_data.get('persona_nombre')
            rol = form.cleaned_data.get('rol')
            if not nombre and not rol:
                continue
            persona, _ = Persona.objects.get_or_create(
                nombre__iexact=nombre,
                defaults={'nombre': nombre},
            )
            proyecto.agregar_miembro(persona, rol)


class EditarProyectoView(View):
    template_name = 'reportes/proyecto_form.html'

    def get(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)
        return self._renderizar(request, proyecto, ProyectoForm(instance=proyecto))

    def post(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)
        accion = request.POST.get('accion')

        if accion == 'guardar_proyecto':
            return self.guardar_proyecto(request, proyecto)
        if accion == 'agregar':
            self.agregar_miembro(request, proyecto)
        elif accion == 'cambiar_rol':
            self.actualizar_rol(request, proyecto)
        elif accion == 'desactivar':
            self.desactivar_miembro(request, proyecto)
        elif accion == 'reactivar':
            self.reactivar_miembro(request, proyecto)
        else:
            messages.warning(request, 'Acción no reconocida.')

        return redirect('reportes:editar_equipo', proyecto_id=proyecto.pk)

    def _renderizar(self, request, proyecto, proyecto_form):
        return render(
            request,
            self.template_name,
            {
                'modo': 'editar',
                'proyecto': proyecto,
                'proyecto_form': proyecto_form,
                'miembros': proyecto.miembros_todos(),
            },
        )

    def guardar_proyecto(self, request, proyecto):
        proyecto_form = ProyectoForm(request.POST, instance=proyecto)
        if proyecto_form.is_valid():
            proyecto_form.save()
            messages.success(request, 'Datos del proyecto actualizados.')
            return redirect(
                'reportes:editar_equipo', proyecto_id=proyecto.pk
            )
        return self._renderizar(request, proyecto, proyecto_form)

    def agregar_miembro(self, request, proyecto):
        nombre = (request.POST.get('persona_nombre') or '').strip()
        rol = (request.POST.get('rol') or '').strip()
        if not nombre or not rol:
            messages.error(request, 'Indica el nombre y el rol del miembro.')
            return
        persona, _ = Persona.objects.get_or_create(
            nombre__iexact=nombre,
            defaults={'nombre': nombre},
        )
        proyecto.agregar_miembro(persona, rol)
        messages.success(request, f'Miembro "{persona.nombre}" agregado.')

    def actualizar_rol(self, request, proyecto):
        miembro = self._obtener_miembro(request, proyecto)
        rol = (request.POST.get('rol') or '').strip()
        if not rol:
            messages.error(request, 'El rol no puede estar vacío.')
            return
        miembro.cambiar_rol(rol)
        messages.success(
            request, f'Rol de "{miembro.persona.nombre}" actualizado.'
        )

    def desactivar_miembro(self, request, proyecto):
        miembro = self._obtener_miembro(request, proyecto)
        miembro.desactivar()
        messages.success(request, f'"{miembro.persona.nombre}" desactivado.')

    def reactivar_miembro(self, request, proyecto):
        miembro = self._obtener_miembro(request, proyecto)
        miembro.reactivar()
        messages.success(request, f'"{miembro.persona.nombre}" reactivado.')

    def _obtener_miembro(self, request, proyecto):
        return get_object_or_404(
            MiembroProyecto,
            pk=request.POST.get('miembro_id'),
            proyecto=proyecto,
        )


class EliminarProyectoView(View):
    def post(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        nombre = proyecto.nombre
        if str(request.session.get(SESSION_KEY)) == str(proyecto.pk):
            request.session.pop(SESSION_KEY, None)
        proyecto.delete()
        messages.success(request, f'Proyecto "{nombre}" eliminado.')
        return redirect('reportes:lista')


def resumen_metricas(proyecto, aplicado):
    """Filas de métricas aplicadas con su último valor y estado."""
    if aplicado is None:
        return []
    filas = []
    for instantanea in aplicado.metricas_aplicadas():
        metrica = instantanea.metrica
        ultima = metrica.ultima_revision(proyecto)
        filas.append(
            {
                'instantanea': instantanea,
                'metrica': metrica,
                'ultima': ultima,
                'valor': ultima.valor if ultima is not None else None,
                'aceptada': metrica.esta_aceptada(proyecto),
                'revisiones': list(metrica.revisiones(proyecto)[:10]),
            }
        )
    return filas


def tono_salud(salud):
    """Color del semáforo de salud (compartido por tablero y reporte)."""
    if salud is None:
        return 'gray'
    if salud >= 80:
        return 'green'
    if salud >= 60:
        return 'amber'
    if salud >= 40:
        return 'orange'
    return 'gray'


def riesgo_salud(salud):
    """Etiqueta del riesgo asociado al índice de salud."""
    if salud is None:
        return 'Sin datos'
    if salud >= 80:
        return 'Bajo'
    if salud >= 60:
        return 'Medio'
    if salud >= 40:
        return 'Alto'
    return 'Crítico'


DIMENSIONES_REPORTE = (
    ('ESPECIFICACION', 'Especificación', 'blue'),
    ('DISENO', 'Diseño', 'purple'),
    ('DESARROLLO', 'Desarrollo', 'green'),
    ('CONFORMIDAD', 'Conformidad', 'orange'),
)


class ReporteProyectoView(View):
    """Reporte rápido del estado del proyecto (HU-18).

    Reúne en una pantalla el índice de salud, el cumplimiento de métricas y el
    avance de técnicas por dimensión. Primero muestra lo que requiere atención
    (métricas que no cumplen y técnicas con pasos pendientes) y, si faltan
    datos, indica qué configurar o registrar.
    """

    template_name = 'reportes/reporte_rapido.html'

    def get(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        aplicado = proyecto.modelo_aplicado_vigente()
        metricas = resumen_metricas(proyecto, aplicado)
        resumen = self.obtener_resumen(proyecto)
        ultima_medicion = proyecto.ultima_medicion()
        ultima_evidencia = proyecto.ultima_evidencia()

        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
                'resumen': resumen,
                'aplicado': aplicado,
                'metricas': metricas,
                'metricas_atencion': self.metricas_de_atencion(metricas),
                'tecnicas_pendientes': self.tecnicas_con_pendientes(proyecto),
                'dimensiones': self.avance_por_dimension(proyecto),
                'ultima_medicion': ultima_medicion,
                'ultima_evidencia': ultima_evidencia,
                'faltantes': self.faltantes(proyecto),
                'tono_salud': tono_salud(resumen.salud),
                'riesgo_salud': riesgo_salud(resumen.salud),
            },
        )

    def obtener_resumen(self, proyecto):
        """Construye el DTO con los tres indicadores y la última actividad."""
        fechas = [
            fecha
            for fecha in (
                proyecto.ultima_medicion(),
                proyecto.ultima_evidencia(),
            )
            if fecha is not None
        ]
        return ResumenReporte(
            salud=proyecto.indice_salud(),
            cumplimiento=proyecto.cumplimiento_metricas(),
            avance=proyecto.avance_tecnicas(),
            ultima_actividad=max(fechas) if fechas else None,
        )

    def metricas_de_atencion(self, metricas):
        """Métricas que no cumplen o que todavía no tienen medición."""
        return [
            fila
            for fila in metricas
            if fila['valor'] is None or not fila['aceptada']
        ]

    def tecnicas_con_pendientes(self, proyecto):
        """Técnicas activas con pasos pendientes y su primer pendiente."""
        filas = []
        for seguimiento in proyecto.seguimientos_activos():
            pendientes = list(
                seguimiento.pasos_pendientes().select_related('paso')
            )
            if not pendientes:
                continue
            total = seguimiento.total_pasos()
            filas.append(
                {
                    'seguimiento': seguimiento,
                    'completados': total - len(pendientes),
                    'total': total,
                    'pendientes': pendientes[:3],
                    'pendientes_total': len(pendientes),
                }
            )
        return filas

    def avance_por_dimension(self, proyecto):
        """Avance agregado (pasos completados / totales) por dimensión."""
        seguimientos = list(proyecto.seguimientos_activos())
        filas = []
        for valor, etiqueta, color in DIMENSIONES_REPORTE:
            del_grupo = [
                seguimiento
                for seguimiento in seguimientos
                if seguimiento.tecnica.dimension == valor
            ]
            total = sum(
                seguimiento.total_pasos() for seguimiento in del_grupo
            )
            completados = sum(
                seguimiento.pasos_completados().count()
                for seguimiento in del_grupo
            )
            filas.append(
                {
                    'valor': valor,
                    'etiqueta': etiqueta,
                    'color': color,
                    'tecnicas': len(del_grupo),
                    'completados': completados,
                    'total': total,
                    'porcentaje': (
                        round(completados / total * 100) if total else 0
                    ),
                }
            )
        return filas

    def faltantes(self, proyecto):
        """Convierte las claves de ``Proyecto.faltantes()`` en acciones."""
        acciones = {
            'modelo': (
                'Aplicar un modelo de calidad para tener métricas.',
                'Aplicar modelo',
                reverse('reportes:aplicar_modelo', args=[proyecto.pk]),
            ),
            'metricas': (
                'El modelo aplicado no tiene métricas activas.',
                'Revisar métricas',
                reverse('reportes:metricas', args=[proyecto.pk]),
            ),
            'mediciones': (
                'Registrar al menos una medición de métricas.',
                'Ir a métricas',
                reverse('reportes:metricas', args=[proyecto.pk]),
            ),
            'tecnicas': (
                'Seleccionar las técnicas QA del proyecto.',
                'Elegir técnicas',
                reverse('tecnicas:catalogo'),
            ),
            'evidencias': (
                'Registrar la evidencia de un paso de las técnicas.',
                'Ir al seguimiento',
                reverse('tecnicas:seguimiento'),
            ),
        }
        return [
            {
                'clave': clave,
                'texto': acciones[clave][0],
                'accion': acciones[clave][1],
                'url': acciones[clave][2],
            }
            for clave in proyecto.faltantes()
        ]


class MetricasProyectoView(View):
    template_name = 'reportes/metricas_proyecto.html'

    def get(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)
        aplicado = proyecto.modelo_aplicado_vigente()

        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
                'aplicado': aplicado,
                'metricas': resumen_metricas(proyecto, aplicado),
            },
        )


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
        return tono_salud(salud)

    def riesgo_salud(self, salud):
        return riesgo_salud(salud)

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
