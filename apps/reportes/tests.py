from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tecnicas.models import Proyecto, SeguimientoTecnica, TecnicaQA
from apps.tecnicas.selection import SESSION_KEY

from .forms import ProyectoForm
from .models import (
    MiembroProyecto,
    Periodo,
    Persona,
    RegistroSalud,
    registrar_salud,
    tendencia_salud,
)


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

    def test_periodo_obtener_proyectos(self):
        futuro = crear_proyecto('Futuro', 5, 20)
        activo = crear_proyecto('Activo', -5, 5)
        terminado = crear_proyecto('Terminado', -20, -5)

        self.assertEqual(
            list(Periodo(Periodo.FUTURO).obtener_proyectos()),
            [futuro],
        )
        self.assertEqual(
            list(Periodo(Periodo.ACTIVO).obtener_proyectos()),
            [activo],
        )
        self.assertEqual(
            list(Periodo(Periodo.TERMINADO).obtener_proyectos()),
            [terminado],
        )

    def test_obtener_recientes_ordena_del_mas_reciente_al_mas_antiguo(self):
        crear_proyecto('Terminado', -20, -5)
        crear_proyecto('Activo', -5, 5)
        crear_proyecto('Futuro', 5, 20)

        nombres = [
            periodo.nombre for periodo in Periodo.obtener_recientes()
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
            reverse('reportes:lista'), {'filtro': 'activos'}
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
        self.assertContains(respuesta, 'Sin métricas registradas')

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
