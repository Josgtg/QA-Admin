from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tecnicas.models import Proyecto

from .forms import ProyectoForm
from .models import Periodo


def crear_proyecto(nombre, inicio, fin):
    hoy = timezone.localdate()
    return Proyecto.objects.create(
        nombre=nombre,
        fecha_inicio=hoy + timedelta(days=inicio),
        fecha_fin=hoy + timedelta(days=fin),
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


class ListaProyectosViewTests(TestCase):
    def setUp(self):
        self.url = reverse('reportes:lista')

    def test_sin_proyectos_muestra_invitacion(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No hay proyectos registrados todavía')

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

    def test_get_muestra_formulario(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Nuevo Proyecto')
        self.assertContains(respuesta, 'Nombre del proyecto')

    def test_post_crea_proyecto_y_redirige_al_listado(self):
        respuesta = self.client.post(self.url, self._datos())

        self.assertRedirects(respuesta, reverse('reportes:lista'))
        proyecto = Proyecto.objects.get(nombre='Proyecto creado')
        self.assertEqual(proyecto.periodo(), Periodo.ACTIVO)

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
