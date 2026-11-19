from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.modelos.models import (
    EstadoMetrica,
    Importancia,
    Metrica,
    ModeloCalidad,
    RevisionMetrica,
    TipoUmbral,
)

from .models import MiembroProyecto, Persona, Proyecto


def crear_proyecto(nombre='Proyecto', inicio=-10, fin=10):
    hoy = timezone.localdate()
    return Proyecto.objects.create(
        nombre=nombre,
        fecha_inicio=hoy + timedelta(days=inicio),
        fecha_fin=hoy + timedelta(days=fin),
    )


class Hu15BaseTests(TestCase):
    """Proyecto con el modelo McCall aplicado y sus cuatro instantáneas."""

    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.persona = Persona.objects.create(nombre='Ana')
        self.miembro = MiembroProyecto.objects.create(
            proyecto=self.proyecto,
            persona=self.persona,
            rol='QA',
        )
        self.aplicado = self.proyecto.aplicar_modelo(
            ModeloCalidad.objects.get(nombre='McCall')
        )
        self.instantaneas = list(
            self.aplicado.metricas_aplicadas().order_by('metrica_id')
        )
        self.url = reverse('reportes:metricas', args=[self.proyecto.pk])

    def medir(self, instantanea, cumple=True):
        """Crea una revisión que cumple o no el umbral de la instantánea."""
        if instantanea.tipo_umbral == TipoUmbral.MINIMO:
            valor = instantanea.umbral + 1
            if not cumple:
                valor = instantanea.umbral - 1
        else:
            valor = instantanea.umbral - 1
            if not cumple:
                valor = instantanea.umbral + 1
        return RevisionMetrica.objects.create(
            metrica_aplicada=instantanea,
            miembro_proyecto=self.miembro,
            valor=valor,
            enlace='https://ejemplo.test/evidencia',
        )

    def marcar_importancia(self, instantanea, importancia):
        """Cambia la importancia del catálogo para esa métrica aplicada."""
        Metrica.objects.filter(pk=instantanea.metrica_id).update(
            importancia=importancia
        )


class EstadoMetricaModelTests(Hu15BaseTests):
    def test_importancia_por_defecto_es_media(self):
        metrica = self.instantaneas[0].metrica
        self.assertEqual(metrica.importancia, Importancia.MEDIA)
        self.assertEqual(
            metrica.obtener_importancia(), Importancia.MEDIA
        )

    def test_sin_medicion_no_se_confunde_con_no_cumple(self):
        instantanea = self.instantaneas[0]

        self.assertEqual(
            instantanea.estado(None), EstadoMetrica.SIN_MEDICION
        )
        self.assertFalse(instantanea.metrica.esta_aceptada(self.proyecto))

        self.medir(instantanea, cumple=False)
        self.assertEqual(
            instantanea.estado(
                instantanea.metrica.ultima_revision(self.proyecto)
            ),
            EstadoMetrica.NO_CUMPLE,
        )
        self.assertFalse(instantanea.metrica.esta_aceptada(self.proyecto))

    def test_estado_cumple_con_ultima_revision(self):
        instantanea = self.instantaneas[0]
        self.medir(instantanea, cumple=True)

        ultima = instantanea.metrica.ultima_revision(self.proyecto)

        self.assertEqual(
            instantanea.estado(ultima), EstadoMetrica.CUMPLE
        )
        self.assertTrue(instantanea.metrica.esta_aceptada(self.proyecto))

    def test_estado_usa_el_umbral_de_la_instantanea(self):
        instantanea = self.instantaneas[0]
        revision = self.medir(instantanea, cumple=True)
        if instantanea.tipo_umbral == TipoUmbral.MINIMO:
            instantanea.umbral = revision.valor + 1
        else:
            instantanea.umbral = revision.valor - 1

        self.assertEqual(
            instantanea.estado(revision), EstadoMetrica.NO_CUMPLE
        )


class FiltrosMetricasViewTests(Hu15BaseTests):
    def test_sin_filtros_muestra_todas_las_metricas(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            len(respuesta.context['metricas']), len(self.instantaneas)
        )
        self.assertFalse(respuesta.context['hay_filtros'])

    def test_filtra_por_conformidad_cumple(self):
        self.medir(self.instantaneas[0])
        self.medir(self.instantaneas[1], cumple=False)

        respuesta = self.client.get(self.url, {'conformidad': 'cumple'})

        metricas = respuesta.context['metricas']
        self.assertEqual(len(metricas), 1)
        self.assertEqual(
            metricas[0]['metrica'].pk, self.instantaneas[0].metrica_id
        )
        self.assertTrue(respuesta.context['hay_filtros'])

    def test_filtra_por_conformidad_no_cumple(self):
        self.medir(self.instantaneas[0])
        self.medir(self.instantaneas[1], cumple=False)

        respuesta = self.client.get(
            self.url, {'conformidad': 'no_cumple'}
        )

        metricas = respuesta.context['metricas']
        self.assertEqual(len(metricas), 1)
        self.assertEqual(
            metricas[0]['metrica'].pk, self.instantaneas[1].metrica_id
        )

    def test_filtra_por_conformidad_sin_medicion(self):
        self.medir(self.instantaneas[0])

        respuesta = self.client.get(
            self.url, {'conformidad': 'sin_medicion'}
        )

        self.assertEqual(
            len(respuesta.context['metricas']), len(self.instantaneas) - 1
        )
        for fila in respuesta.context['metricas']:
            self.assertEqual(fila['estado'], EstadoMetrica.SIN_MEDICION)

    def test_filtra_por_importancia(self):
        self.marcar_importancia(self.instantaneas[0], Importancia.ALTA)
        self.marcar_importancia(self.instantaneas[1], Importancia.BAJA)

        respuesta = self.client.get(self.url, {'importancia': 'alta'})

        metricas = respuesta.context['metricas']
        self.assertEqual(len(metricas), 1)
        self.assertEqual(
            metricas[0]['metrica'].pk, self.instantaneas[0].metrica_id
        )
        self.assertEqual(metricas[0]['importancia'], Importancia.ALTA)

    def test_combina_ambos_filtros_con_and(self):
        # Cumple + alta, no cumple + alta, cumple + media.
        self.marcar_importancia(self.instantaneas[0], Importancia.ALTA)
        self.marcar_importancia(self.instantaneas[1], Importancia.ALTA)
        self.medir(self.instantaneas[0], cumple=True)
        self.medir(self.instantaneas[1], cumple=False)

        respuesta = self.client.get(
            self.url,
            {'conformidad': 'cumple', 'importancia': 'alta'},
        )

        metricas = respuesta.context['metricas']
        self.assertEqual(len(metricas), 1)
        self.assertEqual(
            metricas[0]['metrica'].pk, self.instantaneas[0].metrica_id
        )

    def test_conserva_la_seleccion_en_la_barra_de_filtros(self):
        respuesta = self.client.get(
            self.url, {'conformidad': 'no_cumple'}
        )

        self.assertContains(
            respuesta, '<option value="no_cumple" selected>'
        )

    def test_filtro_invalido_se_descarta_con_aviso(self):
        respuesta = self.client.get(self.url, {'conformidad': 'quizas'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            len(respuesta.context['metricas']), len(self.instantaneas)
        )
        self.assertFalse(respuesta.context['hay_filtros'])
        self.assertEqual(len(respuesta.context['avisos']), 1)
        self.assertContains(respuesta, 'no es válido')
        self.assertContains(respuesta, 'notice-warning')

    def test_filtro_invalido_no_impide_el_otro_criterio(self):
        self.marcar_importancia(self.instantaneas[0], Importancia.ALTA)

        respuesta = self.client.get(
            self.url,
            {'conformidad': 'quizas', 'importancia': 'alta'},
        )

        metricas = respuesta.context['metricas']
        self.assertEqual(len(metricas), 1)
        self.assertEqual(
            metricas[0]['metrica'].pk, self.instantaneas[0].metrica_id
        )
        self.assertEqual(len(respuesta.context['avisos']), 1)

    def test_sin_resultados_muestra_quitar_filtros(self):
        respuesta = self.client.get(self.url, {'conformidad': 'cumple'})

        self.assertEqual(respuesta.context['metricas'], [])
        self.assertContains(respuesta, 'Sin resultados')
        self.assertContains(respuesta, 'Quitar filtros')

    def test_quitar_filtros_vuelve_a_todas_las_metricas(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(
            len(respuesta.context['metricas']), len(self.instantaneas)
        )
        self.assertFalse(respuesta.context['hay_filtros'])

    def test_sin_modelo_aplicado_no_muestra_los_filtros(self):
        proyecto = crear_proyecto('Beta')

        respuesta = self.client.get(
            reverse('reportes:metricas', args=[proyecto.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'name="conformidad"')
        self.assertNotContains(respuesta, 'name="importancia"')

    def test_consulta_no_escribe_en_la_base(self):
        self.medir(self.instantaneas[0])
        revisiones = RevisionMetrica.objects.count()
        aplicadas = self.aplicado.metricas_aplicadas().count()

        self.client.get(
            self.url,
            {'conformidad': 'cumple', 'importancia': 'media'},
        )

        self.assertEqual(RevisionMetrica.objects.count(), revisiones)
        self.assertEqual(
            self.aplicado.metricas_aplicadas().count(), aplicadas
        )

    def test_muestra_la_importancia_en_la_tarjeta(self):
        self.marcar_importancia(self.instantaneas[0], Importancia.ALTA)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Importancia alta')
