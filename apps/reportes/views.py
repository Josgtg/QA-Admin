import math
from datetime import date

from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.tecnicas.selection import (
    SESSION_KEY,
    obtener_proyecto_seleccionado,
    seleccionar_proyecto,
)

from .forms import MiembroProyectoFormSet, ProyectoForm
from .models import (
    MiembroProyecto,
    Periodo,
    Persona,
    Proyecto,
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
    radio_anillo = 68

    def get(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        registro_actual = registrar_salud(proyecto)
        tendencia = tendencia_salud(proyecto)
        salud = registro_actual.indice if registro_actual else None
        ultima_actualizacion = tendencia[-1].actualizado if tendencia else None
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
                'puntos_tendencia': self.puntos_tendencia(tendencia),
                'ultima_actualizacion': ultima_actualizacion,
            },
        )

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

    def puntos_tendencia(self, registros):
        total = len(registros)
        if not total:
            return []

        util_ancho = self.ancho_grafica - 2 * self.margen_grafica
        util_alto = self.alto_grafica - 2 * self.margen_grafica
        paso = util_ancho / (total - 1) if total > 1 else 0
        centro = self.ancho_grafica / 2
        puntos = []
        for posicion, registro in enumerate(registros):
            valor = min(max(registro.indice, 0), 100)
            x = (
                self.margen_grafica + posicion * paso
                if total > 1
                else centro
            )
            y = (
                self.alto_grafica
                - self.margen_grafica
                - (valor / 100) * util_alto
            )
            puntos.append(
                {
                    'x': round(x, 1),
                    'y': round(y, 1),
                    'fecha': registro.fecha,
                    'indice': registro.indice,
                }
            )
        return puntos

    def volver_a_lista(self):
        return redirect('reportes:lista')
