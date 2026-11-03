"""Contenido, consulta y actualización de pasos del catálogo base (HU-12)."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .models import Evidencia, Paso, SeguimientoPaso, TecnicaQA
from .selection import SESSION_KEY
from .services import seguir_tecnica
from .tests import crear_miembro, crear_proyecto, crear_tecnica


class ConsultaPasosHU12Tests(TestCase):
    """La consulta expone pregunta, instrucciones y evidencia en orden."""

    def test_todas_las_tecnicas_muestran_su_contenido(self):
        """Las ocho técnicas tienen contenido consultable y pasos definidos."""
        for tecnica in TecnicaQA.objects.filter(catalogo__nombre='Catálogo base'):
            with self.subTest(tecnica=tecnica.nombre):
                respuesta = self.client.get(
                    reverse('tecnicas:detalle', args=[tecnica.pk])
                )
                self.assertContains(respuesta, tecnica.pregunta_clave)
                self.assertContains(respuesta, tecnica.objetivo)
                self.assertNotContains(respuesta, '[PENDIENTE]')
                pasos = list(respuesta.context['pasos'])
                self.assertGreater(len(pasos), 0)
                for paso in pasos:
                    self.assertContains(respuesta, paso.instruccion)
                    self.assertContains(respuesta, paso.evidencia_esperada)

    def test_orden_de_pasos_y_seguimiento_del_proyecto(self):
        """La consulta ordena los pasos aunque se crearan en otro orden."""
        tecnica = crear_tecnica()
        for orden in (3, 1, 2):
            Paso.objects.create(
                tecnica=tecnica, orden=orden,
                instruccion=f'Acción {orden}', evidencia_esperada=f'Reporte {orden}',
            )
        proyecto = crear_proyecto()
        seguimiento = seguir_tecnica(proyecto, tecnica)
        sesion = self.client.session
        sesion[SESSION_KEY] = proyecto.pk
        sesion.save()
        respuesta = self.client.get(
            reverse('tecnicas:detalle', args=[tecnica.pk])
        )
        self.assertEqual([p.orden for p in respuesta.context['pasos']], [1, 2, 3])
        self.assertEqual(respuesta.context['seguimiento'].pk, seguimiento.pk)
        html = respuesta.content.decode()
        self.assertLess(html.index('Acción 1'), html.index('Acción 2'))
        self.assertLess(html.index('Acción 2'), html.index('Acción 3'))

    def test_tecnica_sin_pasos_muestra_estado_vacio(self):
        """Una técnica propia incompleta muestra su estado vacío."""
        tecnica = crear_tecnica()
        respuesta = self.client.get(
            reverse('tecnicas:detalle', args=[tecnica.pk])
        )
        self.assertContains(respuesta, 'todavía no tiene pasos definidos')


class ContenidoBaseMigrationTests(TransactionTestCase):
    """La migración conserva identidades y protege evidencia previa."""

    def setUp(self):
        """Reconstruye únicamente la app de técnicas en su estado anterior."""
        executor = MigrationExecutor(connection)
        self.finales = executor.loader.graph.leaf_nodes()
        executor.migrate([('tecnicas', None)])
        MigrationExecutor(connection).migrate([
            ('tecnicas', '0003_evidencia_fecha_alter_evidencia_archivo'),
        ])
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        """Restaura las hojas actuales incluso al probar un rechazo de datos."""
        MigrationExecutor(connection).migrate([('tecnicas', None)])
        MigrationExecutor(connection).migrate(self.finales)

    def _migrar(self):
        """Aplica la actualización del contenido base."""
        MigrationExecutor(connection).migrate([
            ('tecnicas', '0004_contenido_tecnicas_base'),
        ])

    def test_conserva_seguimientos_y_evidencia_de_tecnicas_definitivas(self):
        """Amplía seguimientos pendientes sin perder identidades ni evidencia."""
        tecnica = TecnicaQA.objects.get(
            nombre='Técnica por definir · Especificación'
        )
        proyecto = crear_proyecto()
        miembro = crear_miembro(proyecto)
        seguimiento = seguir_tecnica(proyecto, tecnica)
        paso_previo = seguimiento.pasos.get()
        inactivo = seguir_tecnica(crear_proyecto('Otro'), tecnica)
        inactivo.activa = False
        inactivo.save()
        codigo = seguir_tecnica(
            proyecto, TecnicaQA.objects.get(nombre='Revisión de código')
        )
        evidencia = Evidencia.objects.create(
            seguimiento_paso=codigo.pasos.first(), miembro_proyecto=miembro,
            enlace='https://ejemplo.test/evidencia',
        )
        self._migrar()
        tecnica.refresh_from_db()
        seguimiento.refresh_from_db()
        inactivo.refresh_from_db()
        paso_previo.refresh_from_db()
        evidencia.refresh_from_db()
        self.assertEqual(tecnica.nombre, 'Validación de criterios de aceptación')
        self.assertEqual(seguimiento.pasos.count(), 3)
        self.assertEqual(inactivo.pasos.count(), 3)
        self.assertFalse(inactivo.activa)
        self.assertEqual(seguimiento.porcentaje_avance, 0)
        self.assertEqual(paso_previo.paso.orden, 1)
        self.assertEqual(paso_previo.seguimiento_id, seguimiento.pk)
        self.assertEqual(evidencia.enlace, 'https://ejemplo.test/evidencia')
        self.assertEqual(TecnicaQA.objects.count(), 8)

    def test_provisional_con_evidencia_bloquea_toda_la_actualizacion(self):
        """Una evidencia previa provoca rollback sin redefinir su actividad."""
        tecnica = TecnicaQA.objects.get(
            nombre='Técnica por definir · Conformidad (2)'
        )
        proyecto = crear_proyecto()
        seguimiento = seguir_tecnica(proyecto, tecnica)
        paso = seguimiento.pasos.get()
        evidencia = Evidencia.objects.create(
            seguimiento_paso=paso, miembro_proyecto=crear_miembro(proyecto),
            enlace='https://ejemplo.test/provisional',
        )
        with self.assertRaisesMessage(RuntimeError, 'Revisa su historial'):
            self._migrar()
        tecnica.refresh_from_db()
        evidencia.refresh_from_db()
        self.assertTrue(tecnica.es_placeholder())
        self.assertEqual(TecnicaQA.objects.filter(
            descripcion__startswith='[PENDIENTE]'
        ).count(), 6)
        self.assertEqual(SeguimientoPaso.objects.filter(
            seguimiento=seguimiento
        ).count(), 1)
        self.assertEqual(evidencia.enlace, 'https://ejemplo.test/provisional')
