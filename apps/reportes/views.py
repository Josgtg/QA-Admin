import math

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.tecnicas.models import Proyecto

from .forms import MiembroProyectoFormSet, ProyectoForm
from .models import (
    MiembroProyecto,
    Persona,
    registrar_salud,
    tendencia_salud,
)


class InicioView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        ultimo_id = request.session.get('ultimo_proyecto_id')
        proyecto = None
        if ultimo_id:
            proyecto = Proyecto.objects.filter(pk=ultimo_id).first()
        if proyecto is None:
            proyecto = Proyecto.objects.order_by('pk').first()
        if proyecto is None:
            return redirect('reportes:lista')
        return redirect('reportes:tablero', proyecto_id=proyecto.pk)


class ListaProyectosView(View):
    template_name = 'reportes/lista_proyectos.html'
    filtros = {
        'todos': None,
        'activos': 'Activo',
        'planificacion': 'Futuro',
        'cerrados': 'Terminado',
    }

    def get(self, request: HttpRequest) -> HttpResponse:
        proyectos = list(
            Proyecto.objects.prefetch_related(
                'equipo__persona', 'seguimientos'
            ).order_by('nombre')
        )
        for proyecto in proyectos:
            proyecto.periodo_actual = proyecto.periodo()
            proyecto.salud_actual = proyecto.indice_salud()

        busqueda = (request.GET.get('q') or '').strip()
        filtro = request.GET.get('filtro', 'todos')
        if filtro not in self.filtros:
            filtro = 'todos'

        conteos = self.contar_por_periodo(proyectos)
        visibles = self.filtrar(proyectos, filtro, busqueda)
        proyecto_seleccionado = self.seleccionar(request, visibles)
        return render(
            request,
            self.template_name,
            {
                'proyectos': visibles,
                'proyecto_seleccionado': proyecto_seleccionado,
                'hay_proyectos': self.hay_proyectos(proyectos),
                'filtro': filtro,
                'busqueda': busqueda,
                'conteos': conteos,
            },
        )

    def hay_proyectos(self, proyectos):
        return bool(proyectos)

    def contar_por_periodo(self, proyectos):
        conteos = {
            'todos': len(proyectos),
            'activos': 0,
            'planificacion': 0,
            'cerrados': 0,
        }
        for proyecto in proyectos:
            if proyecto.periodo_actual == 'Activo':
                conteos['activos'] += 1
            elif proyecto.periodo_actual == 'Futuro':
                conteos['planificacion'] += 1
            elif proyecto.periodo_actual == 'Terminado':
                conteos['cerrados'] += 1
        return conteos

    def filtrar(self, proyectos, filtro, busqueda):
        estado = self.filtros[filtro]
        visibles = proyectos
        if busqueda:
            termino = busqueda.lower()
            visibles = [
                proyecto
                for proyecto in visibles
                if termino in proyecto.nombre.lower()
            ]
        if estado:
            visibles = [
                proyecto
                for proyecto in visibles
                if proyecto.periodo_actual == estado
            ]
        return visibles

    def seleccionar(self, request, proyectos):
        seleccionado_id = request.GET.get('seleccionado')
        if seleccionado_id:
            for proyecto in proyectos:
                if str(proyecto.pk) == str(seleccionado_id):
                    return proyecto
            proyecto = get_object_or_404(Proyecto, pk=seleccionado_id)
            proyecto.periodo_actual = proyecto.periodo()
            proyecto.salud_actual = proyecto.indice_salud()
            return proyecto
        return proyectos[0] if proyectos else None


class CrearProyectoView(View):
    template_name = 'reportes/proyecto_form.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            self.template_name,
            {
                'modo': 'crear',
                'proyecto_form': ProyectoForm(),
                'equipo_formset': MiembroProyectoFormSet(prefix='equipo'),
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        proyecto_form = ProyectoForm(request.POST)
        equipo_formset = MiembroProyectoFormSet(
            request.POST, prefix='equipo'
        )
        if proyecto_form.is_valid() and equipo_formset.is_valid():
            with transaction.atomic():
                proyecto = proyecto_form.save()
                self._guardar_equipo(proyecto, equipo_formset)
            messages.success(request, 'Proyecto creado correctamente.')
            return redirect('reportes:lista')

        return render(
            request,
            self.template_name,
            {
                'modo': 'crear',
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
        return render(
            request,
            self.template_name,
            {
                'modo': 'editar',
                'proyecto': proyecto,
                'proyecto_form': ProyectoForm(instance=proyecto),
                'miembros': proyecto.miembros_todos(),
            },
        )

    def post(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
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

    def guardar_proyecto(self, request, proyecto):
        proyecto_form = ProyectoForm(request.POST, instance=proyecto)
        if proyecto_form.is_valid():
            proyecto_form.save()
            messages.success(request, 'Datos del proyecto actualizados.')
            return redirect(
                'reportes:editar_equipo', proyecto_id=proyecto.pk
            )
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
        proyecto.delete()
        messages.success(request, f'Proyecto "{nombre}" eliminado.')
        return redirect('reportes:lista')


class MetricasProyectoView(View):
    template_name = 'reportes/metricas_proyecto.html'

    def get(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
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
        request.session['ultimo_proyecto_id'] = proyecto.pk

        registro_actual = registrar_salud(proyecto)
        tendencia = tendencia_salud(proyecto)
        salud = registro_actual.indice if registro_actual else None
        ultima_actualizacion = tendencia[-1].actualizado if tendencia else None

        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
                'equipo': proyecto.equipo_activo(),
                'seguimientos': proyecto.seguimientos_activos(),
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
