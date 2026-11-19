"""Pruebas de HU-11: pasos completados y faltantes de una TQA."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import formats, timezone

from apps.reportes.models import MiembroProyecto, Persona, Proyecto

from .estado import EstadoTecnica
from .models import (
    Evidencia,
    SeguimientoPaso,
    SeguimientoTecnica,
    TecnicaQA,
)
from .services import seguir_tecnica


def crear_proyecto(nombre='Proyecto HU11'):
    hoy = timezone.localdate()
    return Proyecto.objects.create(
        nombre=nombre,
        fecha_inicio=hoy - timedelta(days=5),
        fecha_fin=hoy + timedelta(days=5),
    )


def crear_miembro(proyecto, nombre='Ana HU11'):
    persona, _ = Persona.objects.get_or_create(nombre=nombre)
    return MiembroProyecto.objects.create(
        proyecto=proyecto,
        persona=persona,
        rol='QA',
    )


def crear_tecnica(nombre='Técnica HU11'):
    tecnica = TecnicaQA.objects.create(
        nombre=nombre,
        descripcion='Descripción',
        objetivo='Objetivo',
        pregunta_clave='¿Pregunta?',
        dimension='DESARROLLO',
        tipo_control='VERIFICACION',
    )
    for orden in (1, 2, 3):
        tecnica.pasos.create(
            orden=orden,
            instruccion=f'Instrucción {orden}',
            evidencia_esperada=f'Evidencia esperada {orden}',
        )
    return tecnica


class SeguimientoAvanceTests(TestCase):
    """Cálculo de avance y estado de cumplimiento (HU-11)."""

    def setUp(self):
        self.proyecto = crear_proyecto()
        self.miembro = crear_miembro(self.proyecto)
        self.tecnica = crear_tecnica()
        self.seguimiento = seguir_tecnica(self.proyecto, self.tecnica)

    def _completar(self, paso):
        Evidencia.objects.create(
            seguimiento_paso=paso,
            miembro_proyecto=self.miembro,
            enlace='https://ejemplo.test/evidencia',
        )
        paso.marcar_completado()

    def test_sin_pasos_completados_el_avance_es_cero(self):
        self.assertEqual(self.seguimiento.calcular_porcentaje_avance(), 0.0)
        self.assertFalse(self.seguimiento.esta_completada())

    def test_avance_es_completados_entre_totales(self):
        self._completar(self.seguimiento.pasos.first())

        self.assertEqual(
            self.seguimiento.calcular_porcentaje_avance(), 33.33
        )

    def test_todos_los_pasos_completados_la_marcan_cumplida(self):
        for paso in self.seguimiento.pasos.all():
            self._completar(paso)

        self.assertEqual(
            self.seguimiento.calcular_porcentaje_avance(), 100.0
        )
        self.assertTrue(self.seguimiento.esta_completada())

    def test_con_un_paso_pendiente_no_esta_cumplida(self):
        pasos = list(self.seguimiento.pasos.all())
        self._completar(pasos[0])
        self._completar(pasos[1])

        self.assertAlmostEqual(
            self.seguimiento.calcular_porcentaje_avance(), 66.67
        )
        self.assertFalse(self.seguimiento.esta_completada())

    def test_pasos_completados_y_pendientes(self):
        primero = self.seguimiento.pasos.first()
        self._completar(primero)

        self.assertEqual(
            list(self.seguimiento.pasos_completados()), [primero]
        )
        self.assertEqual(
            self.seguimiento.pasos_pendientes().count(), 2
        )

    def test_calcular_porcentaje_avance_no_escribe(self):
        self.seguimiento.porcentaje_avance = 0.0
        self.seguimiento.save(update_fields=['porcentaje_avance'])

        self.seguimiento.calcular_porcentaje_avance()

        self.seguimiento.refresh_from_db()
        self.assertEqual(self.seguimiento.porcentaje_avance, 0.0)

    def test_calcular_avance_si_persiste(self):
        self._completar(self.seguimiento.pasos.first())

        self.seguimiento.calcular_avance()

        self.seguimiento.refresh_from_db()
        self.assertEqual(self.seguimiento.porcentaje_avance, 33.33)

    def test_seguimiento_sin_pasos_no_esta_cumplido(self):
        vacia = crear_tecnica('Técnica sin pasos')
        vacia.pasos.all().delete()
        seguimiento = seguir_tecnica(self.proyecto, vacia)

        self.assertEqual(seguimiento.calcular_porcentaje_avance(), 0.0)
        self.assertFalse(seguimiento.esta_completada())


class EvidenciaSeguraTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto()
        self.miembro = crear_miembro(self.proyecto)
        self.tecnica = crear_tecnica()
        self.seguimiento = seguir_tecnica(self.proyecto, self.tecnica)
        self.paso = self.seguimiento.pasos.first()

    def test_sin_evidencia_devuelve_none(self):
        self.assertIsNone(self.paso.evidencia_segura())
        self.assertFalse(self.paso.tiene_evidencia())

    def test_con_evidencia_devuelve_la_evidencia(self):
        Evidencia.objects.create(
            seguimiento_paso=self.paso,
            miembro_proyecto=self.miembro,
            enlace='https://ejemplo.test/evidencia',
        )

        evidencia = self.paso.evidencia_segura()

        self.assertIsNotNone(evidencia)
        self.assertEqual(evidencia.enlace, 'https://ejemplo.test/evidencia')
        self.assertTrue(self.paso.tiene_evidencia())


class EstadoTecnicaDTOTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto()
        self.miembro = crear_miembro(self.proyecto)
        self.tecnica = crear_tecnica()
        self.seguimiento = seguir_tecnica(self.proyecto, self.tecnica)

    def _completar(self, paso):
        Evidencia.objects.create(
            seguimiento_paso=paso,
            miembro_proyecto=self.miembro,
            enlace='https://ejemplo.test/evidencia',
        )
        paso.marcar_completado()

    def test_completa_solo_con_el_cien_por_ciento(self):
        pasos = list(self.seguimiento.pasos.all())
        estado = EstadoTecnica(self.tecnica, pasos, porcentaje_avance=66.67)
        self.assertFalse(estado.completa)

        estado = EstadoTecnica(self.tecnica, pasos, porcentaje_avance=100)
        self.assertTrue(estado.completa)

    def test_sin_pasos_no_es_completa(self):
        estado = EstadoTecnica(self.tecnica, [])

        self.assertTrue(estado.sin_pasos)
        self.assertFalse(estado.completa)
        self.assertFalse(estado.esta_completa())

    def test_separa_completados_y_pendientes(self):
        primero = self.seguimiento.pasos.first()
        self._completar(primero)
        pasos = list(self.seguimiento.pasos.all())

        estado = EstadoTecnica(self.tecnica, pasos, porcentaje_avance=33.33)

        self.assertEqual(estado.conteo_completados(), 1)
        self.assertEqual(estado.conteo_pendientes(), 2)
        self.assertEqual(estado.total_pasos, 3)
        self.assertIn(primero, estado.pasos_completados())

    def test_delega_el_cumplimiento_en_el_seguimiento(self):
        """ESP-07: el DTO no mantiene su propia regla de cumplimiento."""
        pasos = list(self.seguimiento.pasos.all())
        estado = EstadoTecnica(
            self.tecnica,
            pasos,
            porcentaje_avance=100,
            seguimiento=self.seguimiento,
        )

        # El seguimiento real no está completado: manda él, no el 100 %.
        self.assertFalse(self.seguimiento.esta_completada())
        self.assertFalse(estado.esta_completa())
        self.assertFalse(estado.completa)

    def test_cumplimiento_coincide_con_el_seguimiento(self):
        for paso in self.seguimiento.pasos.all():
            self._completar(paso)
        pasos = list(self.seguimiento.pasos.all())

        estado = EstadoTecnica(
            self.tecnica,
            pasos,
            porcentaje_avance=100,
            seguimiento=self.seguimiento,
        )

        self.assertEqual(
            estado.esta_completa(), self.seguimiento.esta_completada()
        )
        self.assertTrue(estado.completa)


class EstadoTecnicaViewTests(TestCase):
    """HU-11: pantalla de pasos completados y faltantes."""

    def setUp(self):
        self.proyecto = crear_proyecto()
        self.miembro = crear_miembro(self.proyecto)
        self.tecnica = crear_tecnica()
        self.seguimiento = seguir_tecnica(self.proyecto, self.tecnica)
        self.url = reverse('tecnicas:estado', args=[self.tecnica.pk])

    def _completar(self, paso, enlace='https://ejemplo.test/evidencia'):
        Evidencia.objects.create(
            seguimiento_paso=paso,
            miembro_proyecto=self.miembro,
            enlace=enlace,
        )
        paso.marcar_completado()

    def test_get_responde_200(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.tecnica.nombre)

    def test_muestra_pasos_completados_y_pendientes(self):
        self._completar(self.seguimiento.pasos.first())

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.context['estado'].porcentaje_avance, 33.33)
        self.assertContains(respuesta, 'Pasos completados')
        self.assertContains(respuesta, 'Pasos pendientes')
        self.assertContains(respuesta, 'Completado')
        self.assertContains(respuesta, 'Pendiente')

    def test_muestra_el_porcentaje_de_avance(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.context['estado'].porcentaje_avance, 0.0)
        self.assertContains(respuesta, 'Avance de la técnica')
        avance = formats.localize(respuesta.context['estado'].porcentaje_avance)
        self.assertContains(respuesta, f'{avance}% de avance')

    def test_cada_paso_completado_da_acceso_a_su_evidencia(self):
        self._completar(
            self.seguimiento.pasos.first(),
            enlace='https://ejemplo.test/evidencia-visible',
        )

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Abrir evidencia')
        self.assertContains(
            respuesta, 'https://ejemplo.test/evidencia-visible'
        )

    def test_paso_pendiente_no_muestra_enlace_de_evidencia(self):
        respuesta = self.client.get(self.url)

        self.assertNotContains(respuesta, 'Abrir evidencia')
        self.assertContains(respuesta, 'Registrar evidencia')

    def test_todos_completados_aparece_como_cumplida(self):
        for paso in self.seguimiento.pasos.all():
            self._completar(paso)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.context['estado'].porcentaje_avance, 100.0)
        self.assertTrue(respuesta.context['estado'].completa)
        self.assertContains(respuesta, 'Cumplida')
        self.assertContains(respuesta, 'No quedan pasos pendientes')

    def test_tecnica_fuera_del_seguimiento_lo_avisa(self):
        otra = crear_tecnica('Técnica no seguida')

        respuesta = self.client.get(
            reverse('tecnicas:estado', args=[otra.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context['estado'])
        self.assertContains(
            respuesta, 'no está en el seguimiento del proyecto'
        )

    def test_seguimiento_inactivo_no_muestra_pasos(self):
        """ESP-04: una técnica retirada del seguimiento ya no se consulta."""
        self.seguimiento.desactivar()

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context['estado'])
        self.assertContains(
            respuesta, 'no está en el seguimiento del proyecto'
        )

    def test_tecnica_inexistente_404(self):
        respuesta = self.client.get(
            reverse('tecnicas:estado', args=[999999])
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_acepta_el_proyecto_por_parametro(self):
        otro = crear_proyecto('Otro proyecto HU11')

        respuesta = self.client.get(self.url, {'proyecto': otro.pk})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['proyecto'], otro)
        self.assertIsNone(respuesta.context['estado'])

    def test_get_con_query_guarda_el_proyecto_en_la_sesion(self):
        self.client.get(self.url, {'proyecto': self.proyecto.pk})

        self.assertEqual(
            self.client.session['ultimo_proyecto_id'], self.proyecto.pk
        )

    def test_es_solo_lectura(self):
        estado_antes = self.seguimiento.pasos.filter(
            completado=True
        ).count()

        respuesta = self.client.post(self.url, {})

        self.assertEqual(respuesta.status_code, 405)
        self.assertEqual(
            self.seguimiento.pasos.filter(completado=True).count(),
            estado_antes,
        )

    def test_orden_de_pasos_por_numero(self):
        respuesta = self.client.get(self.url)

        ordenes = [paso.paso.orden for paso in respuesta.context['pasos']]
        self.assertEqual(ordenes, sorted(ordenes))


class EstadoTecnicaEnlacesTests(TestCase):
    """HU-11 accesible desde el seguimiento y el tablero."""

    def setUp(self):
        self.proyecto = crear_proyecto()
        crear_miembro(self.proyecto)
        self.tecnica = crear_tecnica()
        seguir_tecnica(self.proyecto, self.tecnica)

    def test_el_seguimiento_enlaza_al_estado(self):
        respuesta = self.client.get(
            reverse('tecnicas:seguimiento'),
            {'proyecto': self.proyecto.pk},
        )

        self.assertContains(respuesta, 'Ver pasos y avance')
        self.assertContains(
            respuesta,
            reverse('tecnicas:estado', args=[self.tecnica.pk]),
        )

    def test_el_tablero_enlaza_al_estado(self):
        respuesta = self.client.get(
            reverse('reportes:tablero', args=[self.proyecto.pk])
        )

        self.assertContains(
            respuesta,
            reverse('tecnicas:estado', args=[self.tecnica.pk])
            + f'?proyecto={self.proyecto.pk}',
        )

    def test_el_menu_resalta_tecnicas(self):
        respuesta = self.client.get(
            reverse('tecnicas:estado', args=[self.tecnica.pk])
        )

        self.assertEqual(respuesta.context['nav_activo'], 'tecnicas')


class CuadreConSeguimientoPasoTests(TestCase):
    """El avance de HU-11 coincide con el guardado por HU-05."""

    def test_porcentaje_coincide_con_marcar_completado(self):
        proyecto = crear_proyecto()
        miembro = crear_miembro(proyecto)
        tecnica = crear_tecnica()
        seguimiento = seguir_tecnica(proyecto, tecnica)

        for paso in seguimiento.pasos.all():
            Evidencia.objects.create(
                seguimiento_paso=paso,
                miembro_proyecto=miembro,
                enlace='https://ejemplo.test/e',
            )
            paso.marcar_completado()

        seguimiento.refresh_from_db()
        self.assertEqual(seguimiento.porcentaje_avance, 100.0)
        self.assertEqual(seguimiento.calcular_porcentaje_avance(), 100.0)
        self.assertIsInstance(seguimiento, SeguimientoTecnica)
        self.assertIsInstance(paso, SeguimientoPaso)
