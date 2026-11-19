import time
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import formats, timezone

from apps.tecnicas.models import Evidencia, SeguimientoTecnica, TecnicaQA
from apps.tecnicas.selection import SESSION_KEY
from apps.tecnicas.services import seguir_tecnica
from apps.modelos.models import (
    ModeloAplicado,
    ModeloCalidad,
    ModeloMetrica,
    RevisionMetrica,
)

from .forms import ProyectoForm
from .models import (
    MiembroProyecto,
    Periodo,
    Persona,
    Proyecto,
    RegistroSalud,
    caidas_salud,
    registrar_salud,
    tendencia_salud,
)
from .views import ListaProyectosView


def crear_proyecto(nombre='Proyecto', inicio=-10, fin=10):
    hoy = timezone.localdate()
    return Proyecto.objects.create(
        nombre=nombre,
        fecha_inicio=hoy + timedelta(days=inicio),
        fecha_fin=hoy + timedelta(days=fin),
    )


def crear_tecnica(nombre='Revisión de código'):
    return TecnicaQA.objects.create(
        nombre=nombre,
        descripcion='d',
        objetivo='o',
        pregunta_clave='p',
        dimension='DESARROLLO',
        tipo_control='VERIFICACION',
    )


class PeriodoTests(TestCase):
    def test_proyecto_periodo_derivado_de_fechas(self):
        futuro = crear_proyecto('Futuro', 5, 20)
        activo = crear_proyecto('Activo', -5, 5)
        terminado = crear_proyecto('Terminado', -20, -5)

        self.assertEqual(futuro.periodo(), Periodo.FUTURO)
        self.assertEqual(activo.periodo(), Periodo.ACTIVO)
        self.assertEqual(terminado.periodo(), Periodo.TERMINADO)

    def test_esta_en_periodo(self):
        futuro = crear_proyecto('Futuro', 5, 20)
        activo = crear_proyecto('Activo', -5, 5)
        terminado = crear_proyecto('Terminado', -20, -5)

        self.assertTrue(futuro.esta_en_periodo(Periodo.FUTURO))
        self.assertFalse(futuro.esta_en_periodo(Periodo.ACTIVO))
        self.assertTrue(activo.esta_en_periodo(Periodo.ACTIVO))
        self.assertTrue(terminado.esta_en_periodo(Periodo.TERMINADO))

    def test_periodos_disponibles_ordena_del_mas_reciente_al_mas_antiguo(self):
        crear_proyecto('Terminado', -20, -5)
        crear_proyecto('Activo', -5, 5)
        crear_proyecto('Futuro', 5, 20)

        nombres = [
            periodo.nombre
            for periodo in ListaProyectosView().periodos_disponibles()
        ]

        self.assertEqual(
            nombres,
            [Periodo.FUTURO, Periodo.ACTIVO, Periodo.TERMINADO],
        )

    def test_desde_parametro_acepta_alias(self):
        self.assertEqual(
            Periodo.desde_parametro('activos').nombre,
            Periodo.ACTIVO,
        )
        self.assertIsNone(Periodo.desde_parametro(None))
        with self.assertRaises(ValueError):
            Periodo.desde_parametro('invalido')


class ProyectoModelTests(TestCase):
    def test_periodo_futuro_activo_terminado(self):
        hoy = timezone.localdate()
        futuro = Proyecto.objects.create(
            nombre='Futuro',
            fecha_inicio=hoy + timedelta(days=1),
            fecha_fin=hoy + timedelta(days=30),
        )
        activo = Proyecto.objects.create(
            nombre='Activo',
            fecha_inicio=hoy - timedelta(days=1),
            fecha_fin=hoy + timedelta(days=1),
        )
        terminado = Proyecto.objects.create(
            nombre='Terminado',
            fecha_inicio=hoy - timedelta(days=30),
            fecha_fin=hoy - timedelta(days=1),
        )
        self.assertEqual(futuro.periodo(), 'Futuro')
        self.assertEqual(activo.periodo(), 'Activo')
        self.assertEqual(terminado.periodo(), 'Terminado')

    def test_indice_salud_sin_datos(self):
        proyecto = crear_proyecto()
        self.assertIsNone(proyecto.indice_salud())

    def test_indice_salud_promedio(self):
        proyecto = crear_proyecto()
        tecnica_a = TecnicaQA.objects.create(
            nombre='Revisión de código',
            descripcion='d',
            objetivo='o',
            pregunta_clave='p',
            dimension='DESARROLLO',
            tipo_control='VERIFICACION',
        )
        tecnica_b = TecnicaQA.objects.create(
            nombre='Pruebas de aceptación',
            descripcion='d',
            objetivo='o',
            pregunta_clave='p',
            dimension='CONFORMIDAD',
            tipo_control='VALIDACION',
        )
        SeguimientoTecnica.objects.create(
            proyecto=proyecto, tecnica=tecnica_a, porcentaje_avance=50.0
        )
        SeguimientoTecnica.objects.create(
            proyecto=proyecto, tecnica=tecnica_b, porcentaje_avance=30.0
        )
        self.assertEqual(proyecto.indice_salud(), 40.0)


class PersonaMiembroTests(TestCase):
    def test_str_persona(self):
        persona = Persona.objects.create(nombre='Ana')
        self.assertEqual(str(persona), 'Ana')

    def test_str_miembro(self):
        proyecto = crear_proyecto()
        persona = Persona.objects.create(nombre='Luis')
        miembro = MiembroProyecto.objects.create(
            proyecto=proyecto, persona=persona, rol='QA'
        )
        self.assertEqual(str(miembro), 'Luis · Proyecto · QA')

    def test_equipo_activo_y_miembros_todos(self):
        proyecto = crear_proyecto()
        ana = Persona.objects.create(nombre='Ana')
        luis = Persona.objects.create(nombre='Luis')
        MiembroProyecto.objects.create(proyecto=proyecto, persona=ana, rol='Dev')
        MiembroProyecto.objects.create(
            proyecto=proyecto, persona=luis, rol='QA', activo=False
        )
        self.assertEqual(proyecto.equipo_activo().count(), 1)
        self.assertEqual(proyecto.miembros_todos().count(), 2)


class ListaProyectosViewTests(TestCase):
    def setUp(self):
        self.url = reverse('reportes:lista')

    def test_sin_proyectos_muestra_invitacion(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No hay proyectos registrados todavía')

    def test_lista_muestra_proyectos(self):
        crear_proyecto('Alpha')
        crear_proyecto('Beta')
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Alpha')
        self.assertContains(respuesta, 'Beta')
        self.assertContains(respuesta, 'Activo')

    def test_sin_filtro_agrupa_por_periodo(self):
        crear_proyecto('Proyecto terminado', -20, -5)
        crear_proyecto('Proyecto activo', -5, 5)
        crear_proyecto('Proyecto futuro', 5, 20)

        respuesta = self.client.get(self.url)
        grupos = respuesta.context['grupos']

        self.assertEqual(
            [grupo['periodo'].nombre for grupo in grupos],
            [Periodo.FUTURO, Periodo.ACTIVO, Periodo.TERMINADO],
        )
        self.assertContains(respuesta, 'Proyecto futuro')
        self.assertContains(respuesta, 'Proyecto activo')
        self.assertContains(respuesta, 'Proyecto terminado')

    def test_filtro_muestra_solo_el_periodo_elegido(self):
        crear_proyecto('Proyecto terminado', -20, -5)
        crear_proyecto('Proyecto activo', -5, 5)
        crear_proyecto('Proyecto futuro', 5, 20)

        respuesta = self.client.get(self.url, {'periodo': 'activo'})

        self.assertContains(respuesta, 'Proyecto activo')
        self.assertNotContains(respuesta, 'Proyecto futuro')
        self.assertNotContains(respuesta, 'Proyecto terminado')
        self.assertEqual(
            [grupo['periodo'].nombre for grupo in respuesta.context['grupos']],
            [Periodo.ACTIVO],
        )

    def test_periodo_sin_proyectos_muestra_lista_vacia(self):
        crear_proyecto('Proyecto activo', -5, 5)

        respuesta = self.client.get(self.url, {'periodo': 'futuro'})

        self.assertContains(respuesta, 'No hay proyectos en este periodo.')
        self.assertEqual(
            [grupo['periodo'].nombre for grupo in respuesta.context['grupos']],
            [Periodo.FUTURO],
        )

    def test_parametro_de_periodo_invalido_devuelve_404(self):
        respuesta = self.client.get(self.url, {'periodo': 'invalido'})

        self.assertEqual(respuesta.status_code, 404)

    def test_seleccionado_muestra_equipo(self):
        proyecto = crear_proyecto('Alpha')
        persona = Persona.objects.create(nombre='Ana')
        MiembroProyecto.objects.create(
            proyecto=proyecto, persona=persona, rol='Dev'
        )
        respuesta = self.client.get(
            reverse('reportes:lista'), {'seleccionado': proyecto.pk}
        )
        self.assertContains(respuesta, 'Ana')

    def test_seleccionado_guarda_el_proyecto_en_la_sesion(self):
        proyecto = crear_proyecto('Alpha')

        self.client.get(
            reverse('reportes:lista'), {'seleccionado': proyecto.pk}
        )

        self.assertEqual(
            self.client.session[SESSION_KEY], proyecto.pk
        )

    def test_lista_usa_el_proyecto_seleccionado_en_la_sesion(self):
        crear_proyecto('Alpha')
        proyecto = crear_proyecto('Beta')
        sesion = self.client.session
        sesion[SESSION_KEY] = proyecto.pk
        sesion.save()

        respuesta = self.client.get(reverse('reportes:lista'))

        self.assertEqual(
            respuesta.context['proyecto_seleccionado'], proyecto
        )

    def test_filtro_activos_oculta_proyectos_futuros(self):
        crear_proyecto('Alpha')
        hoy = timezone.localdate()
        Proyecto.objects.create(
            nombre='Beta',
            fecha_inicio=hoy + timedelta(days=5),
            fecha_fin=hoy + timedelta(days=20),
        )
        respuesta = self.client.get(
            reverse('reportes:lista'), {'periodo': 'activos'}
        )
        self.assertContains(respuesta, 'Alpha')
        self.assertNotContains(respuesta, 'Beta')

    def test_busqueda_filtra_por_nombre(self):
        crear_proyecto('Alpha')
        crear_proyecto('Beta')
        respuesta = self.client.get(
            reverse('reportes:lista'), {'q': 'alp'}
        )
        self.assertContains(respuesta, 'Alpha')
        self.assertNotContains(respuesta, 'Beta')


class ProyectoFormTests(TestCase):
    def test_formulario_valido_guarda_fechas(self):
        hoy = timezone.localdate()
        form = ProyectoForm(
            {
                'nombre': 'Proyecto nuevo',
                'fecha_inicio': hoy.isoformat(),
                'fecha_fin': (hoy + timedelta(days=30)).isoformat(),
            }
        )

        self.assertTrue(form.is_valid())
        proyecto = form.save()
        self.assertEqual(proyecto.nombre, 'Proyecto nuevo')
        self.assertEqual(proyecto.fecha_inicio, hoy)

    def test_formulario_rechaza_fecha_fin_anterior(self):
        hoy = timezone.localdate()
        form = ProyectoForm(
            {
                'nombre': 'Proyecto inválido',
                'fecha_inicio': hoy.isoformat(),
                'fecha_fin': (hoy - timedelta(days=1)).isoformat(),
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('fecha_fin', form.errors)

    def test_formulario_exige_nombre_y_fechas(self):
        form = ProyectoForm(
            {
                'nombre': '',
                'fecha_inicio': '',
                'fecha_fin': '',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('nombre', form.errors)
        self.assertIn('fecha_inicio', form.errors)
        self.assertIn('fecha_fin', form.errors)


class CrearProyectoViewTests(TestCase):
    def setUp(self):
        self.url = reverse('reportes:crear')

    def _datos(self):
        hoy = timezone.localdate()
        return {
            'nombre': 'Proyecto creado',
            'fecha_inicio': hoy.isoformat(),
            'fecha_fin': (hoy + timedelta(days=30)).isoformat(),
        }

    def _datos_equipo(self, total=1):
        return {
            'equipo-TOTAL_FORMS': str(total),
            'equipo-INITIAL_FORMS': '0',
            'equipo-MIN_NUM_FORMS': '0',
            'equipo-MAX_NUM_FORMS': '1000',
        }

    def test_get_muestra_formulario(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Nuevo Proyecto')
        self.assertContains(respuesta, 'Nombre del proyecto')

    def test_get_formulario_muestra_labels_de_equipo(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, '>Persona<')
        self.assertContains(respuesta, '>Rol<')

    def test_post_crea_proyecto_y_equipo(self):
        datos = {
            'nombre': 'Nuevo',
            'fecha_inicio': '2026-01-01',
            'fecha_fin': '2026-12-31',
        }
        datos.update(self._datos_equipo(total=2))
        datos['equipo-0-persona_nombre'] = 'Ana'
        datos['equipo-0-rol'] = 'Desarrolladora'
        datos['equipo-1-persona_nombre'] = 'Luis'
        datos['equipo-1-rol'] = 'QA'
        respuesta = self.client.post(reverse('reportes:crear'), datos)
        self.assertRedirects(respuesta, reverse('reportes:lista'))
        self.assertEqual(Proyecto.objects.count(), 1)
        self.assertEqual(Persona.objects.count(), 2)
        self.assertEqual(
            MiembroProyecto.objects.filter(activo=True).count(), 2
        )

    def test_post_crea_proyecto_y_redirige_al_listado(self):
        respuesta = self.client.post(self.url, self._datos())

        self.assertRedirects(respuesta, reverse('reportes:lista'))
        proyecto = Proyecto.objects.get(nombre='Proyecto creado')
        self.assertEqual(proyecto.periodo(), Periodo.ACTIVO)

    def test_post_sin_nombre(self):
        datos = {
            'nombre': '',
            'fecha_inicio': '2026-01-01',
            'fecha_fin': '2026-12-31',
        }
        datos.update(self._datos_equipo())
        respuesta = self.client.post(reverse('reportes:crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Proyecto.objects.count(), 0)

    def test_post_invalido_no_crea_proyecto(self):
        datos = self._datos()
        datos['nombre'] = ''

        respuesta = self.client.post(self.url, datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('nombre', respuesta.context['form'].errors)
        self.assertEqual(Proyecto.objects.count(), 0)

    def test_post_con_fecha_fin_anterior_no_crea_proyecto(self):
        datos = self._datos()
        datos['fecha_fin'] = (timezone.localdate() - timedelta(days=1)).isoformat()

        respuesta = self.client.post(self.url, datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no puede ser anterior')
        self.assertEqual(Proyecto.objects.count(), 0)

    def test_post_fecha_invalida(self):
        datos = {
            'nombre': 'X',
            'fecha_inicio': '2026-12-31',
            'fecha_fin': '2026-01-01',
        }
        datos.update(self._datos_equipo())
        respuesta = self.client.post(reverse('reportes:crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Proyecto.objects.count(), 0)
        self.assertContains(respuesta, 'no puede ser anterior')

    def test_post_persona_duplicada(self):
        datos = {
            'nombre': 'X',
            'fecha_inicio': '2026-01-01',
            'fecha_fin': '2026-12-31',
        }
        datos.update(self._datos_equipo(total=2))
        datos['equipo-0-persona_nombre'] = 'Ana'
        datos['equipo-0-rol'] = 'Dev'
        datos['equipo-1-persona_nombre'] = 'ana'
        datos['equipo-1-rol'] = 'QA'
        respuesta = self.client.post(reverse('reportes:crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Proyecto.objects.count(), 0)

    def test_proyecto_creado_aparece_en_el_listado(self):
        self.client.post(self.url, self._datos())

        respuesta = self.client.get(reverse('reportes:lista'))

        self.assertContains(respuesta, 'Proyecto creado')
        self.assertEqual(
            [grupo['periodo'].nombre for grupo in respuesta.context['grupos']],
            [Periodo.ACTIVO, Periodo.FUTURO, Periodo.TERMINADO],
        )

    def test_proyecto_creado_esta_disponible_en_tecnicas(self):
        self.client.post(self.url, self._datos())
        proyecto = Proyecto.objects.get(nombre='Proyecto creado')

        respuesta = self.client.get(
            reverse('tecnicas:seguimiento'),
            {'proyecto': proyecto.pk},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Proyecto creado')


class EditarProyectoViewTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.persona = Persona.objects.create(nombre='Ana')
        self.miembro = MiembroProyecto.objects.create(
            proyecto=self.proyecto, persona=self.persona, rol='Dev'
        )

    def _url(self, proyecto=None):
        proyecto = proyecto or self.proyecto
        return reverse('reportes:editar_equipo', args=[proyecto.pk])

    def test_get_muestra_miembros(self):
        respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ana')

    def test_get_muestra_datos_del_proyecto(self):
        respuesta = self.client.get(self._url())
        self.assertContains(respuesta, 'Datos del proyecto')
        self.assertContains(respuesta, 'Alpha')
        self.assertContains(respuesta, 'Guardar cambios')

    def test_actualizar_datos_proyecto(self):
        respuesta = self.client.post(
            self._url(),
            {
                'accion': 'guardar_proyecto',
                'nombre': 'Alpha renovado',
                'fecha_inicio': '2026-02-01',
                'fecha_fin': '2026-06-30',
            },
        )
        self.assertRedirects(respuesta, self._url())
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.nombre, 'Alpha renovado')
        self.assertEqual(str(self.proyecto.fecha_fin), '2026-06-30')

    def test_actualizar_datos_invalidos_no_guarda(self):
        respuesta = self.client.post(
            self._url(),
            {
                'accion': 'guardar_proyecto',
                'nombre': 'Alpha renovado',
                'fecha_inicio': '2026-06-30',
                'fecha_fin': '2026-02-01',
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no puede ser anterior')
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.nombre, 'Alpha')

    def test_agregar_miembro(self):
        respuesta = self.client.post(
            self._url(),
            {'accion': 'agregar', 'persona_nombre': 'Luis', 'rol': 'QA'},
        )
        self.assertRedirects(respuesta, self._url())
        self.assertTrue(
            MiembroProyecto.objects.filter(
                persona__nombre='Luis', proyecto=self.proyecto, activo=True
            ).exists()
        )

    def test_cambiar_rol(self):
        self.client.post(
            self._url(),
            {'accion': 'cambiar_rol', 'miembro_id': self.miembro.pk, 'rol': 'QA Lead'},
        )
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.rol, 'QA Lead')

    def test_desactivar_y_reactivar(self):
        self.client.post(
            self._url(),
            {'accion': 'desactivar', 'miembro_id': self.miembro.pk},
        )
        self.miembro.refresh_from_db()
        self.assertFalse(self.miembro.activo)

        self.client.post(
            self._url(),
            {'accion': 'reactivar', 'miembro_id': self.miembro.pk},
        )
        self.miembro.refresh_from_db()
        self.assertTrue(self.miembro.activo)
        self.assertEqual(
            MiembroProyecto.objects.filter(
                persona=self.persona, proyecto=self.proyecto
            ).count(),
            1,
        )

    def test_miembro_otro_proyecto_404(self):
        otro = crear_proyecto('Beta')
        respuesta = self.client.post(
            self._url(otro),
            {'accion': 'cambiar_rol', 'miembro_id': self.miembro.pk, 'rol': 'X'},
        )
        self.assertEqual(respuesta.status_code, 404)


class EliminarProyectoViewTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.url = reverse('reportes:eliminar', args=[self.proyecto.pk])

    def test_eliminar_por_post(self):
        respuesta = self.client.post(self.url)
        self.assertRedirects(respuesta, reverse('reportes:lista'))
        self.assertFalse(
            Proyecto.objects.filter(pk=self.proyecto.pk).exists()
        )

    def test_eliminar_por_get_no_permitido(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 405)

    def test_eliminar_proyecto_inexistente_404(self):
        respuesta = self.client.post(
            reverse('reportes:eliminar', args=[9999])
        )
        self.assertEqual(respuesta.status_code, 404)


class MetricasProyectoViewTests(TestCase):
    def test_get_muestra_proyecto(self):
        proyecto = crear_proyecto('Alpha')
        respuesta = self.client.get(
            reverse('reportes:metricas', args=[proyecto.pk])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Alpha')
        self.assertContains(respuesta, 'Sin métricas configuradas')

    def test_muestra_metricas_del_modelo_aplicado(self):
        from apps.modelos.models import ModeloCalidad

        proyecto = crear_proyecto('Alpha')
        proyecto.aplicar_modelo(ModeloCalidad.objects.get(nombre='McCall'))

        respuesta = self.client.get(
            reverse('reportes:metricas', args=[proyecto.pk])
        )

        self.assertEqual(len(respuesta.context['metricas']), 4)
        self.assertContains(respuesta, 'Requisitos implementados correctamente')
        self.assertContains(respuesta, 'Sin medición')

    def test_metricas_se_muestran_en_tarjetas_independientes(self):
        from apps.modelos.models import ModeloCalidad

        proyecto = crear_proyecto('Alpha')
        proyecto.aplicar_modelo(ModeloCalidad.objects.get(nombre='McCall'))

        respuesta = self.client.get(
            reverse('reportes:metricas', args=[proyecto.pk])
        )

        self.assertContains(respuesta, 'class="metric-cards"')
        self.assertContains(
            respuesta,
            'class="card metric-card"',
            count=4,
        )
        self.assertContains(respuesta, 'Ver historial (', count=4)

    def test_proyecto_inexistente_404(self):
        respuesta = self.client.get(
            reverse('reportes:metricas', args=[9999])
        )
        self.assertEqual(respuesta.status_code, 404)


class InicioViewTests(TestCase):
    def test_sin_proyectos_redirige_a_lista(self):
        respuesta = self.client.get(reverse('inicio'))
        self.assertRedirects(respuesta, reverse('reportes:lista'))

    def test_sin_sesion_redirige_al_primer_proyecto(self):
        primero = crear_proyecto('Alpha')
        crear_proyecto('Beta')
        respuesta = self.client.get(reverse('inicio'))
        self.assertRedirects(
            respuesta,
            reverse('reportes:tablero', args=[primero.pk]),
        )

    def test_usa_ultimo_proyecto_abierto(self):
        crear_proyecto('Alpha')
        segundo = crear_proyecto('Beta')
        self.client.get(
            reverse('reportes:tablero', args=[segundo.pk])
        )
        respuesta = self.client.get(reverse('inicio'))
        self.assertRedirects(
            respuesta,
            reverse('reportes:tablero', args=[segundo.pk]),
        )

    def test_parametro_proyecto_redirige_a_su_tablero(self):
        crear_proyecto('Alpha')
        segundo = crear_proyecto('Beta')

        respuesta = self.client.get(
            reverse('inicio'), {'proyecto': segundo.pk}
        )

        self.assertRedirects(
            respuesta,
            reverse('reportes:tablero', args=[segundo.pk]),
        )
        self.assertEqual(
            self.client.session['ultimo_proyecto_id'], segundo.pk
        )

    def test_sesion_invalida_redirige_al_primer_proyecto(self):
        primero = crear_proyecto('Alpha')
        sesion = self.client.session
        sesion['ultimo_proyecto_id'] = 9999
        sesion.save()
        respuesta = self.client.get(reverse('inicio'))
        self.assertRedirects(
            respuesta,
            reverse('reportes:tablero', args=[primero.pk]),
        )

    def test_tablero_guarda_ultimo_proyecto(self):
        proyecto = crear_proyecto('Alpha')
        self.client.get(
            reverse('reportes:tablero', args=[proyecto.pk])
        )
        self.assertEqual(
            self.client.session['ultimo_proyecto_id'], proyecto.pk
        )

    def test_proyecto_del_tablero_se_usa_en_tecnicas(self):
        crear_proyecto('Alpha')
        proyecto = crear_proyecto('Beta')
        self.client.get(
            reverse('reportes:tablero', args=[proyecto.pk])
        )

        respuesta = self.client.get(reverse('tecnicas:seguimiento'))

        self.assertEqual(respuesta.context['proyecto'], proyecto)


class TableroProyectoViewTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        ana = Persona.objects.create(nombre='Ana')
        MiembroProyecto.objects.create(
            proyecto=self.proyecto, persona=ana, rol='Dev'
        )
        otro = crear_proyecto('Beta')
        luis = Persona.objects.create(nombre='Luis')
        MiembroProyecto.objects.create(
            proyecto=otro, persona=luis, rol='QA'
        )

    def test_muestra_equipo_propio(self):
        respuesta = self.client.get(
            reverse('reportes:tablero', args=[self.proyecto.pk])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ana')
        self.assertNotContains(respuesta, 'Luis')

    def test_muestra_selector_de_proyectos(self):
        respuesta = self.client.get(
            reverse('reportes:tablero', args=[self.proyecto.pk])
        )

        self.assertContains(respuesta, 'id="proyecto-select"')
        self.assertContains(respuesta, 'Beta')

    def test_proyecto_inexistente_404(self):
        respuesta = self.client.get(
            reverse('reportes:tablero', args=[9999])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_boton_volver(self):
        respuesta = self.client.get(
            reverse('reportes:tablero', args=[self.proyecto.pk])
        )
        self.assertContains(respuesta, 'Volver a la lista')


class RegistroSaludTests(TestCase):
    def test_sin_datos_no_crea_registro(self):
        proyecto = crear_proyecto()
        self.assertIsNone(registrar_salud(proyecto))
        self.assertEqual(RegistroSalud.objects.count(), 0)

    def test_guarda_indice_del_dia(self):
        proyecto = crear_proyecto()
        tecnica = crear_tecnica()
        SeguimientoTecnica.objects.create(
            proyecto=proyecto, tecnica=tecnica, porcentaje_avance=75.0
        )
        registro = registrar_salud(proyecto)
        self.assertEqual(registro.indice, 75.0)
        self.assertEqual(registro.fecha, timezone.localdate())
        self.assertEqual(
            RegistroSalud.objects.filter(proyecto=proyecto).count(), 1
        )

    def test_actualiza_el_registro_del_mismo_dia(self):
        proyecto = crear_proyecto()
        tecnica = crear_tecnica()
        seguimiento = SeguimientoTecnica.objects.create(
            proyecto=proyecto, tecnica=tecnica, porcentaje_avance=40.0
        )
        registrar_salud(proyecto)
        seguimiento.porcentaje_avance = 80.0
        seguimiento.save(update_fields=['porcentaje_avance'])
        registro = registrar_salud(proyecto)
        self.assertEqual(registro.indice, 80.0)
        self.assertEqual(
            RegistroSalud.objects.filter(proyecto=proyecto).count(), 1
        )

    def test_tendencia_ordena_y_limita(self):
        proyecto = crear_proyecto()
        hoy = timezone.localdate()
        for dias in range(8):
            RegistroSalud.objects.create(
                proyecto=proyecto,
                fecha=hoy - timedelta(days=dias),
                indice=float(dias * 10),
            )
        tendencia = tendencia_salud(proyecto)
        self.assertEqual(len(tendencia), 6)
        self.assertEqual(
            [registro.fecha for registro in tendencia],
            sorted(registro.fecha for registro in tendencia),
        )


class TableroSaludTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.tecnica = crear_tecnica()
        SeguimientoTecnica.objects.create(
            proyecto=self.proyecto,
            tecnica=self.tecnica,
            porcentaje_avance=70.0,
        )

    def test_tablero_guarda_registro_de_salud(self):
        self.client.get(
            reverse('reportes:tablero', args=[self.proyecto.pk])
        )
        registro = RegistroSalud.objects.get(proyecto=self.proyecto)
        self.assertEqual(registro.indice, 70.0)

    def test_tablero_muestra_indice_y_tendencia(self):
        respuesta = self.client.get(
            reverse('reportes:tablero', args=[self.proyecto.pk])
        )
        self.assertContains(respuesta, 'Índice de Salud del Proyecto')
        self.assertContains(respuesta, 'Tendencia de Salud')
        self.assertContains(respuesta, 'line-blue')
        self.assertContains(respuesta, 'Última actualización')

    def test_tablero_sin_datos_muestra_placeholders(self):
        otro = crear_proyecto('Beta')
        respuesta = self.client.get(
            reverse('reportes:tablero', args=[otro.pk])
        )
        self.assertContains(respuesta, 'Sin historial de salud todavía')
        self.assertContains(respuesta, 'Sin métricas configuradas')

    def test_registros_de_salud_estan_aislados_por_proyecto(self):
        otro = crear_proyecto('Beta')
        self.client.get(
            reverse('reportes:tablero', args=[self.proyecto.pk])
        )
        self.client.get(
            reverse('reportes:tablero', args=[otro.pk])
        )
        self.assertEqual(
            RegistroSalud.objects.filter(proyecto=self.proyecto).count(), 1
        )
        self.assertFalse(
            RegistroSalud.objects.filter(proyecto=otro).exists()
        )


class ListaProyectosAccionesTests(TestCase):
    """Métodos ir_a_* del diseño (hu6_clases.puml)."""

    def test_ir_a_crear_redirige(self):
        respuesta = self.client.get(
            reverse('reportes:lista'), {'ir': 'crear'}
        )

        self.assertRedirects(respuesta, reverse('reportes:crear'))

    def test_ir_a_tablero_redirige(self):
        proyecto = crear_proyecto('Alpha')

        respuesta = self.client.get(
            reverse('reportes:lista'),
            {'ir': 'tablero', 'proyecto': proyecto.pk},
        )

        self.assertRedirects(
            respuesta,
            reverse('reportes:tablero', args=[proyecto.pk]),
        )

    def test_ir_a_editar_redirige(self):
        proyecto = crear_proyecto('Alpha')

        respuesta = self.client.get(
            reverse('reportes:lista'),
            {'ir': 'editar', 'proyecto': proyecto.pk},
        )

        self.assertRedirects(
            respuesta,
            reverse('reportes:editar', args=[proyecto.pk]),
        )


class AplicarModeloViewTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.modelo = ModeloCalidad.objects.get(nombre='McCall')
        self.otro = ModeloCalidad.objects.get(nombre='FURPS')
        self.url = reverse(
            'reportes:aplicar_modelo', args=[self.proyecto.pk]
        )

    def test_get_lista_los_modelos_predefinidos(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['modelos']), 4)

    def test_post_aplica_y_redirige_al_tablero(self):
        respuesta = self.client.post(
            self.url, {'modelo_id': self.modelo.pk}
        )

        self.assertRedirects(
            respuesta,
            reverse('reportes:tablero', args=[self.proyecto.pk]),
        )
        self.assertTrue(
            ModeloAplicado.objects.filter(
                proyecto=self.proyecto, vigente=True
            ).exists()
        )

    def test_post_sin_modelo_devuelve_400(self):
        respuesta = self.client.post(self.url, {})

        self.assertEqual(respuesta.status_code, 400)

    def test_post_modelo_no_predefinido_404(self):
        propio = ModeloCalidad.objects.create(
            nombre='Propio',
            descripcion='x',
            predefinido=False,
        )

        respuesta = self.client.post(
            self.url, {'modelo_id': propio.pk}
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_cambio_con_mediciones_pide_confirmacion(self):
        aplicado = self.proyecto.aplicar_modelo(self.modelo)
        persona = Persona.objects.create(nombre='Ana')
        miembro = MiembroProyecto.objects.create(
            proyecto=self.proyecto, persona=persona, rol='QA'
        )
        RevisionMetrica.objects.create(
            metrica_aplicada=aplicado.metricas_aplicadas().first(),
            miembro_proyecto=miembro,
            valor=90,
            enlace='https://ejemplo.test/a',
        )

        respuesta = self.client.post(
            self.url, {'modelo_id': self.otro.pk}
        )

        self.assertTrue(respuesta.context['requiere_confirmacion'])
        self.assertEqual(
            ModeloAplicado.objects.filter(
                proyecto=self.proyecto, vigente=True
            ).count(),
            1,
        )
        self.assertEqual(
            ModeloAplicado.objects.get(
                proyecto=self.proyecto, vigente=True
            ).modelo_calidad_id,
            self.modelo.pk,
        )

    def test_confirmacion_aplica_el_cambio(self):
        aplicado = self.proyecto.aplicar_modelo(self.modelo)
        persona = Persona.objects.create(nombre='Ana')
        miembro = MiembroProyecto.objects.create(
            proyecto=self.proyecto, persona=persona, rol='QA'
        )
        RevisionMetrica.objects.create(
            metrica_aplicada=aplicado.metricas_aplicadas().first(),
            miembro_proyecto=miembro,
            valor=90,
            enlace='https://ejemplo.test/a',
        )

        aviso = self.client.post(self.url, {'modelo_id': self.otro.pk})
        respuesta = self.client.post(
            self.url,
            {
                'modelo_id': self.otro.pk,
                'confirmacion': '1',
                'contexto_confirmacion': aviso.context['contexto_confirmacion'],
            },
        )

        self.assertRedirects(
            respuesta,
            reverse('reportes:tablero', args=[self.proyecto.pk]),
        )
        self.assertEqual(
            ModeloAplicado.objects.get(
                proyecto=self.proyecto, vigente=True
            ).modelo_calidad_id,
            self.otro.pk,
        )
        self.assertEqual(
            ModeloAplicado.objects.filter(proyecto=self.proyecto).count(),
            2,
        )


class ConfirmacionModeloViewTests(TestCase):
    """El consentimiento solo se aplica al proyecto, destino y estado vistos."""

    def setUp(self):
        """Prepara un proyecto con modelo vigente y una medición histórica."""
        self.proyecto = crear_proyecto('Alpha')
        self.modelo = ModeloCalidad.objects.get(nombre='McCall')
        self.destino = ModeloCalidad.objects.get(nombre='FURPS')
        self.tercero = ModeloCalidad.objects.get(nombre='Boehm')
        self.aplicado = self.proyecto.aplicar_modelo(self.modelo)
        persona = Persona.objects.create(nombre='Ana')
        miembro = MiembroProyecto.objects.create(
            proyecto=self.proyecto, persona=persona, rol='QA'
        )
        self.revision = RevisionMetrica.objects.create(
            metrica_aplicada=self.aplicado.metricas_aplicadas().first(),
            miembro_proyecto=miembro,
            valor=90,
            enlace='https://ejemplo.test/evidencia',
        )
        self.url = reverse('reportes:aplicar_modelo', args=[self.proyecto.pk])

    def _contexto(self):
        """Obtiene el contexto que el formulario envía al confirmar."""
        aviso = self.client.post(self.url, {'modelo_id': self.destino.pk})
        self.assertTrue(aviso.context['requiere_confirmacion'])
        contexto = aviso.context['contexto_confirmacion']
        self.assertContains(aviso, f'value="{contexto}"')
        return contexto

    def _confirmar(self, contexto, modelo=None, url=None):
        """Envía la confirmación desde una pantalla previamente consultada."""
        return self.client.post(url or self.url, {
            'modelo_id': (modelo or self.destino).pk,
            'confirmacion': '1',
            'contexto_confirmacion': contexto,
        })

    def _assert_sin_cambio(self, respuesta, aplicado, cantidad):
        """Comprueba nueva confirmación y ausencia de cambios en el historial."""
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['requiere_confirmacion'])
        self.assertTrue(respuesta.context['contexto_confirmacion'])
        self.assertEqual(self.proyecto.modelo_aplicado_vigente().pk, aplicado.pk)
        self.assertEqual(self.proyecto.modelos_aplicados.count(), cantidad)
        self.revision.refresh_from_db()

    def test_bandera_sin_contexto_no_confirma(self):
        """El parámetro confirmacion=1 por sí solo no acredita consentimiento."""
        respuesta = self._confirmar('')
        self._assert_sin_cambio(respuesta, self.aplicado, 1)

    def test_contexto_modificado_no_confirma(self):
        """Un contexto alterado devuelve una decisión nueva sin escrituras."""
        respuesta = self._confirmar(self._contexto() + 'alterado')
        self._assert_sin_cambio(respuesta, self.aplicado, 1)

    def test_contexto_vencido_pide_confirmacion_nueva(self):
        """La confirmación expira después de los treinta minutos permitidos."""
        contexto = self._contexto()
        with patch('django.core.signing.time.time', return_value=time.time() + 1801):
            respuesta = self._confirmar(contexto)
        self._assert_sin_cambio(respuesta, self.aplicado, 1)

    def test_contexto_no_se_reutiliza_para_otro_destino(self):
        """La aprobación para FURPS no autoriza aplicar Boehm."""
        respuesta = self._confirmar(self._contexto(), modelo=self.tercero)
        self._assert_sin_cambio(respuesta, self.aplicado, 1)

    def test_contexto_no_se_reutiliza_para_otro_proyecto(self):
        """Un proyecto con el mismo modelo exige su propio consentimiento."""
        contexto = self._contexto()
        otro = crear_proyecto('Beta')
        aplicado = otro.aplicar_modelo(self.modelo)
        miembro = MiembroProyecto.objects.create(
            proyecto=otro,
            persona=self.revision.miembro_proyecto.persona,
            rol='QA',
        )
        RevisionMetrica.objects.create(
            metrica_aplicada=aplicado.metricas_aplicadas().first(),
            miembro_proyecto=miembro,
            valor=90,
            enlace='https://ejemplo.test/otro',
        )
        url = reverse('reportes:aplicar_modelo', args=[otro.pk])
        respuesta = self._confirmar(contexto, url=url)
        self.assertTrue(respuesta.context['requiere_confirmacion'])
        self.assertEqual(otro.modelo_aplicado_vigente().pk, aplicado.pk)
        self.assertEqual(otro.modelos_aplicados.count(), 1)

    def test_cambio_entre_aviso_y_confirmacion_exige_decision_nueva(self):
        """Una confirmación de McCall no reemplaza silenciosamente a Boehm."""
        contexto = self._contexto()
        tercero = self.proyecto.aplicar_modelo(self.tercero)
        respuesta = self._confirmar(contexto)
        self._assert_sin_cambio(respuesta, tercero, 2)
        self.assertContains(respuesta, 'la configuración cambió')
        nuevo_contexto = respuesta.context['contexto_confirmacion']
        self.assertEqual(self._confirmar(nuevo_contexto).status_code, 302)
        self.assertEqual(
            self.proyecto.modelo_aplicado_vigente().modelo_calidad_id,
            self.destino.pk,
        )

    def test_volver_al_mismo_modelo_no_rehabilita_el_contexto_anterior(self):
        """La identidad de la aplicación distingue el ciclo McCall-Boehm-McCall."""
        contexto = self._contexto()
        self.proyecto.aplicar_modelo(self.tercero)
        nuevo = self.proyecto.aplicar_modelo(self.modelo)
        respuesta = self._confirmar(contexto)
        self._assert_sin_cambio(respuesta, nuevo, 3)

    def test_repetir_confirmacion_no_duplica_aplicaciones(self):
        """Reenviar una confirmación ya aplicada conserva el resultado vigente."""
        contexto = self._contexto()
        self.assertEqual(self._confirmar(contexto).status_code, 302)
        aplicado = self.proyecto.modelo_aplicado_vigente()
        respuesta = self._confirmar(contexto)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.proyecto.modelo_aplicado_vigente().pk, aplicado.pk)
        self.assertEqual(self.proyecto.modelos_aplicados.count(), 2)

    def test_fallo_al_crear_instantanea_revierte_el_cambio(self):
        """Un fallo tras cerrar el modelo anterior conserva toda su aplicación."""
        contexto = self._contexto()
        with patch.object(
            ModeloAplicado, 'crear_instantanea', side_effect=RuntimeError('fallo')
        ):
            with self.assertRaises(RuntimeError):
                self._confirmar(contexto)
        self.assertEqual(
            self.proyecto.modelo_aplicado_vigente().pk, self.aplicado.pk
        )
        self.assertEqual(self.proyecto.modelos_aplicados.count(), 1)
        self.revision.refresh_from_db()


class RegistrarRevisionMetricaViewTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.persona = Persona.objects.create(nombre='Ana')
        self.miembro = MiembroProyecto.objects.create(
            proyecto=self.proyecto, persona=self.persona, rol='QA'
        )
        self.aplicado = self.proyecto.aplicar_modelo(
            ModeloCalidad.objects.get(nombre='McCall')
        )
        self.instantanea = self.aplicado.metricas_aplicadas().get(
            metrica__nombre='Requisitos implementados correctamente'
        )
        self.metrica = self.instantanea.metrica
        self.url = reverse(
            'reportes:registrar_revision',
            args=[self.proyecto.pk, self.metrica.pk],
        )

    def test_get_muestra_el_formulario(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Registrar revisión de métrica')

    def test_resuelve_la_metrica_por_su_id_no_por_la_instantanea(self):
        """El id de la URL es el de `Metrica`, no el de `MetricaAplicada`."""
        otro = crear_proyecto('Beta')
        aplicado = otro.aplicar_modelo(
            ModeloCalidad.objects.get(nombre='FURPS')
        )
        instantanea = aplicado.metricas_aplicadas().order_by(
            'metrica_id'
        ).first()
        self.assertNotEqual(instantanea.pk, instantanea.metrica_id)

        respuesta = self.client.get(
            reverse(
                'reportes:registrar_revision',
                args=[otro.pk, instantanea.metrica_id],
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.context['instantanea'].pk,
            instantanea.pk,
        )

    def test_post_registra_y_redirige_a_metricas(self):
        respuesta = self.client.post(
            self.url,
            {
                'valor': 95,
                'fecha': timezone.localdate().isoformat(),
                'enlace': 'https://ejemplo.test/a',
                'miembro_proyecto': self.miembro.pk,
            },
        )

        self.assertRedirects(
            respuesta,
            reverse('reportes:metricas', args=[self.proyecto.pk]),
        )
        self.assertEqual(self.metrica.revisiones(self.proyecto).count(), 1)
        self.assertEqual(self.metrica.ultimo_valor(self.proyecto), 95)
        self.assertTrue(self.metrica.esta_aceptada(self.proyecto))

    def test_post_sin_evidencia_no_registra(self):
        respuesta = self.client.post(
            self.url,
            {
                'valor': 95,
                'fecha': timezone.localdate().isoformat(),
                'miembro_proyecto': self.miembro.pk,
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.metrica.revisiones(self.proyecto).count(), 0)

    def test_post_fuera_de_rango_no_registra(self):
        self.metrica.valor_min = 0
        self.metrica.valor_max = 100
        self.metrica.save(update_fields=['valor_min', 'valor_max'])

        respuesta = self.client.post(
            self.url,
            {
                'valor': 150,
                'fecha': timezone.localdate().isoformat(),
                'enlace': 'https://ejemplo.test/a',
                'miembro_proyecto': self.miembro.pk,
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.metrica.revisiones(self.proyecto).count(), 0)

    def test_sin_modelo_aplicado_redirige_a_aplicar(self):
        proyecto = crear_proyecto('Beta')

        respuesta = self.client.get(
            reverse(
                'reportes:registrar_revision',
                args=[proyecto.pk, self.metrica.pk],
            )
        )

        self.assertRedirects(
            respuesta,
            reverse('reportes:aplicar_modelo', args=[proyecto.pk]),
        )


class IndiceSaludHU14Tests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.seguimiento = SeguimientoTecnica.objects.create(
            proyecto=self.proyecto,
            tecnica=crear_tecnica(),
            porcentaje_avance=80.0,
        )

    def aplicar_modelo(self):
        modelo = ModeloCalidad.obtener_predefinidos().first()
        return self.proyecto.aplicar_modelo(modelo)

    def test_sin_metricas_el_indice_son_las_tecnicas(self):
        self.assertEqual(self.proyecto.indice_salud(), 80.0)

    def test_metricas_sin_medicion_no_cuentan_como_cumplidas(self):
        self.aplicar_modelo()
        self.assertEqual(self.proyecto.cumplimiento_metricas(), 0.0)
        self.assertEqual(self.proyecto.indice_salud(), 40.0)

    def test_solo_metricas_sin_tecnicas(self):
        self.seguimiento.desactivar()
        self.aplicar_modelo()
        self.assertEqual(self.proyecto.indice_salud(), 0.0)

    def test_registro_guarda_detalle_de_tecnicas_y_metricas(self):
        self.aplicar_modelo()
        registro = registrar_salud(self.proyecto)
        tipos = set(registro.detalles.values_list('tipo', flat=True))
        self.assertEqual(tipos, {'TECNICA', 'METRICA'})

    def test_registrar_dos_veces_no_duplica_detalles(self):
        registrar_salud(self.proyecto)
        registro = registrar_salud(self.proyecto)
        self.assertEqual(registro.detalles.count(), 1)


class TendenciaHU14Tests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.tecnica = crear_tecnica()
        self.url = reverse('reportes:tablero', args=[self.proyecto.pk])
        self.hoy = timezone.localdate()

    def registro(self, dias, indice, avance=None):
        registro = RegistroSalud.objects.create(
            proyecto=self.proyecto,
            fecha=self.hoy - timedelta(days=dias),
            indice=indice,
        )
        registro.detalles.create(
            tipo='TECNICA',
            nombre=self.tecnica.nombre,
            valor=indice if avance is None else avance,
        )
        return registro

    def test_grafica_muestra_fecha_y_valor_al_pasar_el_cursor(self):
        self.registro(2, 50.0)
        self.registro(1, 70.0)
        respuesta = self.client.get(self.url)
        fecha = (self.hoy - timedelta(days=1)).strftime('%d/%m/%Y')
        valor = formats.localize(70.0)
        self.assertContains(respuesta, f'<title>{fecha}: {valor}</title>')

    def test_grafica_muestra_mas_de_seis_registros(self):
        for dias in range(1, 10):
            self.registro(dias, 50.0)
        respuesta = self.client.get(self.url)
        self.assertEqual(len(respuesta.context['tendencia']), 9)

    def test_rango_limita_los_registros(self):
        self.registro(10, 40.0)
        self.registro(5, 50.0)
        self.registro(1, 60.0)
        respuesta = self.client.get(
            self.url,
            {
                'desde': (self.hoy - timedelta(days=6)).isoformat(),
                'hasta': (self.hoy - timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(
            [r.indice for r in respuesta.context['tendencia']], [50.0]
        )

    def test_rango_invertido_muestra_error_y_no_filtra(self):
        self.registro(5, 50.0)
        self.registro(1, 60.0)
        respuesta = self.client.get(
            self.url,
            {
                'desde': self.hoy.isoformat(),
                'hasta': (self.hoy - timedelta(days=9)).isoformat(),
            },
        )
        self.assertContains(respuesta, 'no puede ser anterior a la inicial')
        self.assertEqual(len(respuesta.context['tendencia']), 2)

    def test_fecha_invalida_muestra_error(self):
        respuesta = self.client.get(self.url, {'desde': 'ayer'})
        self.assertContains(respuesta, 'La fecha inicial no es válida.')

    def test_una_medicion_avisa_datos_insuficientes(self):
        self.registro(1, 60.0)
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Aún no hay datos suficientes')

    def test_sin_mediciones_avisa_datos_insuficientes(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Aún no hay datos suficientes')

    def test_dos_mediciones_no_avisan(self):
        self.registro(2, 60.0)
        self.registro(1, 70.0)
        respuesta = self.client.get(self.url)
        self.assertNotContains(respuesta, 'Aún no hay datos suficientes')

    def test_caida_muestra_la_tecnica_que_bajo(self):
        self.registro(2, 80.0)
        self.registro(1, 40.0)
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Caídas del índice')
        self.assertContains(respuesta, 'bajó de 80 % a 40 %')
        self.assertContains(respuesta, self.tecnica.nombre)

    def test_caida_por_metrica_nueva_que_no_cumple(self):
        anterior = self.registro(2, 80.0)
        actual = self.registro(1, 40.0, avance=80.0)
        actual.detalles.create(tipo='METRICA', nombre='Cobertura', valor=0.0)
        causas = actual.causas_de_caida(anterior)
        self.assertEqual([c['nombre'] for c in causas], ['Cobertura'])

    def test_caida_por_tecnica_quitada(self):
        anterior = self.registro(2, 90.0)
        actual = RegistroSalud.objects.create(
            proyecto=self.proyecto, fecha=self.hoy, indice=30.0
        )
        causas = actual.causas_de_caida(anterior)
        self.assertEqual(causas[0]['despues'], None)
        self.assertEqual(causas[0]['antes'], 90.0)

    def test_subida_no_es_caida(self):
        registros = [self.registro(2, 40.0), self.registro(1, 80.0)]
        self.assertEqual(caidas_salud(registros), [])

    def test_caida_de_otro_proyecto_no_aparece(self):
        otro = crear_proyecto('Beta')
        self.registro(2, 80.0)
        self.registro(1, 40.0)
        respuesta = self.client.get(
            reverse('reportes:tablero', args=[otro.pk])
        )
        self.assertNotContains(respuesta, 'Caídas del índice')

    def test_eje_x_respeta_la_distancia_entre_fechas(self):
        for dias in (30, 29, 1):
            self.registro(dias, 50.0)
        puntos = self.client.get(self.url).context['puntos_tendencia']
        primera = puntos[1]['x'] - puntos[0]['x']
        segunda = puntos[2]['x'] - puntos[1]['x']
        self.assertAlmostEqual(segunda / primera, 28, delta=0.5)

    def test_eje_x_siempre_muestra_primera_y_ultima_fecha(self):
        for cantidad in range(2, 32):
            RegistroSalud.objects.all().delete()
            for dias in range(1, cantidad + 1):
                self.registro(dias, 50.0)
            puntos = self.client.get(self.url).context['puntos_tendencia']
            self.assertTrue(puntos[0]['con_etiqueta'], cantidad)
            self.assertTrue(puntos[-1]['con_etiqueta'], cantidad)
            visibles = [p['x'] for p in puntos if p['con_etiqueta']]
            for izquierda, derecha in zip(visibles, visibles[1:]):
                self.assertGreaterEqual(derecha - izquierda, 44, cantidad)

    def test_grafica_muestra_la_escala_de_0_a_100(self):
        self.registro(2, 60.0)
        self.registro(1, 70.0)
        respuesta = self.client.get(self.url)
        for valor in ('>100<', '>50<', '>0<'):
            self.assertContains(respuesta, valor)

    def test_el_valor_extremo_queda_dentro_de_la_grafica(self):
        self.registro(2, 0.0)
        self.registro(1, 100.0)
        puntos = self.client.get(self.url).context['puntos_tendencia']
        self.assertEqual([p['y'] for p in puntos], [138.0, 12.0])

    def test_rango_vacio_no_dice_que_no_hay_historial(self):
        self.registro(1, 60.0)
        respuesta = self.client.get(
            self.url, {'desde': '2000-01-01', 'hasta': '2000-01-02'}
        )
        self.assertContains(respuesta, 'No hay mediciones en este rango')
        self.assertNotContains(respuesta, 'Sin historial de salud')

    def test_rango_incluye_sus_dos_extremos(self):
        self.registro(3, 40.0)
        self.registro(2, 50.0)
        self.registro(1, 60.0)
        respuesta = self.client.get(
            self.url,
            {
                'desde': (self.hoy - timedelta(days=3)).isoformat(),
                'hasta': (self.hoy - timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(len(respuesta.context['tendencia']), 2)

    def test_avisa_cuando_recorta_el_historial(self):
        for dias in range(1, 41):
            self.registro(dias, 50.0)
        respuesta = self.client.get(self.url)
        self.assertEqual(len(respuesta.context['tendencia']), 30)
        self.assertContains(respuesta, 'Se muestran las 30 mediciones')

    def test_rango_permite_ver_mediciones_viejas(self):
        for dias in range(1, 41):
            self.registro(dias, 50.0)
        respuesta = self.client.get(
            self.url, {'hasta': (self.hoy - timedelta(days=35)).isoformat()}
        )
        self.assertEqual(len(respuesta.context['tendencia']), 6)

    def test_registro_anterior_sin_detalle_no_inventa_causas(self):
        anterior = RegistroSalud.objects.create(
            proyecto=self.proyecto,
            fecha=self.hoy - timedelta(days=2),
            indice=90.0,
        )
        actual = self.registro(1, 40.0)
        self.assertEqual(actual.causas_de_caida(anterior), [])
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'No hay detalle guardado')

    def test_metrica_que_deja_de_cumplir_se_explica_con_palabras(self):
        anterior = self.registro(2, 80.0)
        anterior.detalles.create(tipo='METRICA', nombre='Cobertura', valor=100.0)
        actual = self.registro(1, 40.0, avance=80.0)
        actual.detalles.create(tipo='METRICA', nombre='Cobertura', valor=0.0)
        causas = actual.causas_de_caida(anterior)
        self.assertEqual(causas[0]['texto'], 'dejó de cumplir su meta')

    def test_nombre_con_html_se_escapa(self):
        anterior = RegistroSalud.objects.create(
            proyecto=self.proyecto,
            fecha=self.hoy - timedelta(days=2),
            indice=90.0,
        )
        actual = RegistroSalud.objects.create(
            proyecto=self.proyecto,
            fecha=self.hoy - timedelta(days=1),
            indice=10.0,
        )
        nombre = '<img src=x onerror=alert(1)>'
        anterior.detalles.create(tipo='TECNICA', nombre=nombre, valor=90.0)
        actual.detalles.create(tipo='TECNICA', nombre=nombre, valor=10.0)
        respuesta = self.client.get(self.url)
        self.assertNotContains(respuesta, '<img src=x')


class EstadoMetricasHU14Tests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.autor = self.proyecto.agregar_miembro(
            Persona.objects.create(nombre='Ana'), 'QA'
        )
        modelo = ModeloCalidad.obtener_predefinidos().first()
        self.aplicado = self.proyecto.aplicar_modelo(modelo)
        self.metricas = list(self.aplicado.metricas_aplicadas())

    def medir(self, instantanea, cumple, fecha=None):
        umbral = instantanea.umbral
        if instantanea.tipo_umbral == 'MINIMO':
            valor = umbral if cumple else umbral - 1
        else:
            valor = umbral if cumple else umbral + 1
        return RevisionMetrica.objects.create(
            metrica_aplicada=instantanea,
            miembro_proyecto=self.autor,
            valor=valor,
            enlace='https://ejemplo.test/evidencia',
            fecha=fecha or timezone.localdate(),
        )

    def test_indice_igual_no_es_caida(self):
        hoy = timezone.localdate()
        registros = [
            RegistroSalud.objects.create(
                proyecto=self.proyecto,
                fecha=hoy - timedelta(days=dias),
                indice=50.0,
            )
            for dias in (2, 1)
        ]
        self.assertEqual(caidas_salud(registros), [])

    def test_tecnica_nueva_con_buen_avance_no_es_causa(self):
        hoy = timezone.localdate()
        anterior = RegistroSalud.objects.create(
            proyecto=self.proyecto,
            fecha=hoy - timedelta(days=2),
            indice=60.0,
        )
        anterior.detalles.create(tipo='TECNICA', nombre='A', valor=60.0)
        actual = RegistroSalud.objects.create(
            proyecto=self.proyecto,
            fecha=hoy - timedelta(days=1),
            indice=50.0,
        )
        actual.detalles.create(tipo='TECNICA', nombre='A', valor=20.0)
        actual.detalles.create(tipo='TECNICA', nombre='B', valor=80.0)
        causas = actual.causas_de_caida(anterior)
        self.assertEqual([causa['nombre'] for causa in causas], ['A'])

    def test_causas_explican_cada_tipo_de_cambio(self):
        registro = RegistroSalud.objects.create(
            proyecto=self.proyecto, indice=50.0
        )
        metrica = registro.detalles.create(
            tipo='METRICA', nombre='M', valor=0.0
        )
        tecnica = registro.detalles.create(
            tipo='TECNICA', nombre='T', valor=20.0
        )
        casos = (
            (metrica, None, 0.0, 'se agregó sin cumplir su meta'),
            (metrica, 100.0, None, 'se quitó cuando cumplía su meta'),
            (metrica, 100.0, 0.0, 'dejó de cumplir su meta'),
            (tecnica, None, 20.0, 'se agregó con 20 % de avance'),
            (tecnica, 80.0, None, 'se quitó cuando tenía 80 % de avance'),
            (tecnica, 80.0, 20.5, 'bajó de 80 % a 20.5 % de avance'),
        )
        for detalle, antes, despues, texto in casos:
            causa = detalle.describir_cambio(antes, despues)
            self.assertEqual(causa['texto'], texto)

    def test_coincide_con_el_cumplimiento_de_cada_metrica(self):
        self.medir(self.metricas[0], True)
        self.medir(self.metricas[1], False)
        estados = self.proyecto.estado_metricas()
        for (nombre, valor), instantanea in zip(estados, self.metricas):
            self.assertEqual(nombre, instantanea.metrica.nombre)
            self.assertEqual(
                valor == 100.0,
                instantanea.metrica.esta_aceptada(self.proyecto),
            )

    def test_usa_la_medicion_mas_reciente(self):
        hoy = timezone.localdate()
        self.medir(self.metricas[0], False, hoy)
        self.medir(self.metricas[0], True, hoy - timedelta(days=5))
        self.assertEqual(self.proyecto.estado_metricas()[0][1], 0.0)

    def test_metrica_inactiva_no_cuenta(self):
        total = len(self.metricas)
        modelo = ModeloCalidad.objects.create(
            nombre='Modelo con métrica inactiva',
            descripcion='una métrica desactivada',
            predefinido=True,
        )
        for indice, instantanea in enumerate(self.metricas):
            ModeloMetrica.objects.create(
                modelo_calidad=modelo,
                metrica=instantanea.metrica,
                umbral=instantanea.umbral,
                tipo_umbral=instantanea.tipo_umbral,
                activa=indice != 0,
            )
        self.proyecto.aplicar_modelo(modelo)
        self.assertEqual(len(self.proyecto.estado_metricas()), total - 1)

    def test_nombres_repetidos_cuentan_por_separado(self):
        total = len(self.metricas)
        self.metricas[1].metrica.nombre = self.metricas[0].metrica.nombre
        self.metricas[1].metrica.save()
        self.assertEqual(len(self.proyecto.estado_metricas()), total)

    def test_consultas_no_crecen_con_las_mediciones(self):
        for instantanea in self.metricas:
            self.medir(instantanea, True)
        with self.assertNumQueries(3):
            self.proyecto.estado_metricas()

    def test_tablero_registra_una_caida_real_de_metrica(self):
        url = reverse('reportes:tablero', args=[self.proyecto.pk])
        hoy = timezone.localdate()
        self.medir(self.metricas[0], True, hoy - timedelta(days=4))
        self.client.get(url)
        registro = self.proyecto.registros_salud.get(fecha=hoy)
        registro.fecha = hoy - timedelta(days=3)
        registro.save()
        self.medir(self.metricas[0], False, hoy)
        respuesta = self.client.get(url)
        caida = respuesta.context['caidas'][0]
        self.assertEqual(
            caida['causas'][0]['nombre'], self.metricas[0].metrica.nombre
        )
        self.assertContains(respuesta, 'dejó de cumplir su meta')


class ReporteProyectoViewTests(TestCase):
    """Reporte rápido del estado del proyecto (HU-18)."""

    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.persona = Persona.objects.create(nombre='Ana')
        self.miembro = MiembroProyecto.objects.create(
            proyecto=self.proyecto,
            persona=self.persona,
            rol='QA',
        )
        self.tecnica = crear_tecnica()
        self.tecnica.pasos.create(
            orden=1,
            instruccion='Revisar el estandar',
            evidencia_esperada='Enlace o archivo',
        )
        self.tecnica.pasos.create(
            orden=2,
            instruccion='Ejecutar las pruebas',
            evidencia_esperada='Reporte de pruebas',
        )
        self.seguimiento = seguir_tecnica(self.proyecto, self.tecnica)
        self.url = reverse('reportes:reporte', args=[self.proyecto.pk])

    def _aplicar_modelo(self):
        aplicado = self.proyecto.modelo_aplicado_vigente()
        if aplicado is None:
            aplicado = self.proyecto.aplicar_modelo(
                ModeloCalidad.obtener_predefinidos().first()
            )
        return aplicado

    def _medir(self, cumple=True, fecha=None):
        aplicado = self._aplicar_modelo()
        instantanea = aplicado.metricas_aplicadas().first()
        umbral = instantanea.umbral
        if instantanea.tipo_umbral == 'MINIMO':
            valor = umbral if cumple else umbral - 1
        else:
            valor = umbral if cumple else umbral + 1
        RevisionMetrica.objects.create(
            metrica_aplicada=instantanea,
            miembro_proyecto=self.miembro,
            valor=valor,
            enlace='https://ejemplo.test/medicion',
            fecha=fecha or timezone.localdate(),
        )
        return instantanea

    def _registrar_evidencia(self, fecha=None):
        paso = self.seguimiento.pasos.order_by('paso__orden').first()
        Evidencia.objects.create(
            seguimiento_paso=paso,
            miembro_proyecto=self.miembro,
            enlace='https://ejemplo.test/evidencia',
            fecha=fecha or timezone.localdate(),
        )
        paso.marcar_completado()
        return paso

    def test_proyecto_inexistente_devuelve_404(self):
        respuesta = self.client.get(
            reverse('reportes:reporte', args=[999999])
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_sin_datos_dice_que_falta_configurar(self):
        vacio = crear_proyecto('Vacío')

        respuesta = self.client.get(
            reverse('reportes:reporte', args=[vacio.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'todavía no tiene datos')
        self.assertContains(respuesta, 'Qué falta configurar o registrar')
        self.assertContains(respuesta, 'Aplicar modelo')

    def test_muestra_salud_cumplimiento_y_avance(self):
        self._medir(cumple=True)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Índice de salud')
        self.assertContains(respuesta, 'Cumplimiento de métricas')
        self.assertContains(respuesta, 'Avance de técnicas')
        self.assertIsNotNone(respuesta.context['resumen'].salud)
        self.assertIsNotNone(respuesta.context['resumen'].cumplimiento)
        self.assertIsNotNone(respuesta.context['resumen'].avance)

    def test_lo_que_necesita_atencion_va_primero(self):
        self._medir(cumple=False)

        respuesta = self.client.get(self.url)
        contenido = respuesta.content.decode()

        self.assertIn('Requiere atención', contenido)
        self.assertLess(
            contenido.index('Requiere atención'),
            contenido.index('Estado de métricas'),
        )

    def test_metrica_sin_medicion_aparece_en_atencion(self):
        self._aplicar_modelo()

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Sin medición')
        self.assertGreaterEqual(
            len(respuesta.context['metricas_atencion']),
            1,
        )

    def test_muestra_ultima_medicion_y_evidencia(self):
        hoy = timezone.localdate()
        self._medir(cumple=True, fecha=hoy - timedelta(days=2))
        self._registrar_evidencia(fecha=hoy)

        respuesta = self.client.get(self.url)

        self.assertEqual(
            respuesta.context['ultima_medicion'],
            hoy - timedelta(days=2),
        )
        self.assertEqual(respuesta.context['ultima_evidencia'], hoy)
        self.assertContains(respuesta, 'Última evidencia registrada')

    def test_tecnicas_con_pasos_pendientes(self):
        respuesta = self.client.get(self.url)

        filas = respuesta.context['tecnicas_pendientes']
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['completados'], 0)
        self.assertEqual(filas[0]['total'], 2)
        self.assertContains(respuesta, '0 de 2 pasos')
        self.assertContains(respuesta, 'Requiere atención')

    def test_faltantes_incluye_evidencias_sin_registrar(self):
        self._aplicar_modelo()

        respuesta = self.client.get(self.url)

        claves = [falta['clave'] for falta in respuesta.context['faltantes']]
        self.assertIn('evidencias', claves)

    def test_guarda_el_proyecto_en_la_sesion(self):
        self.client.get(self.url)

        self.assertEqual(self.client.session[SESSION_KEY], self.proyecto.pk)
