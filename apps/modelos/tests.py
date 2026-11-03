from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.reportes.models import MiembroProyecto, Persona, Proyecto

from .models import (
    Caracteristica,
    Metrica,
    MetricaAplicada,
    ModeloAplicado,
    ModeloCalidad,
    ModeloMetrica,
    RevisionMetrica,
    TipoUmbral,
)


def crear_proyecto(nombre='Proyecto'):
    hoy = timezone.localdate()
    return Proyecto.objects.create(
        nombre=nombre,
        fecha_inicio=hoy - timedelta(days=10),
        fecha_fin=hoy + timedelta(days=10),
    )


def crear_miembro(proyecto, nombre='Ana'):
    persona, _ = Persona.objects.get_or_create(nombre=nombre)
    return MiembroProyecto.objects.create(
        proyecto=proyecto,
        persona=persona,
        rol='QA',
    )


class ModelosBaseTests(TestCase):
    """Estado del seed tras el reset de migraciones."""

    def test_hay_cuatro_modelos_predefinidos(self):
        self.assertEqual(ModeloCalidad.obtener_predefinidos().count(), 4)

    def test_catalogo_global_de_caracteristicas(self):
        self.assertEqual(Caracteristica.objects.count(), 13)
        self.assertEqual(Metrica.objects.count(), 18)
        self.assertEqual(ModeloMetrica.objects.count(), 18)

    def test_cada_modelo_tiene_varias_metricas(self):
        for modelo in ModeloCalidad.obtener_predefinidos():
            self.assertGreater(
                modelo.obtener_modelo_metricas().count(),
                1,
                modelo.nombre,
            )

    def test_umbral_vive_en_modelo_metrica(self):
        mc_call = ModeloCalidad.objects.get(nombre='McCall')
        requisitos = mc_call.obtener_modelo_metricas().get(
            metrica__nombre='Requisitos implementados correctamente'
        )
        self.assertEqual(requisitos.umbral, 90)
        self.assertEqual(requisitos.tipo_umbral, TipoUmbral.MINIMO)

    def test_caracteristicas_se_infieren_de_las_metricas(self):
        furps = ModeloCalidad.objects.get(nombre='FURPS')
        nombres = {c.nombre for c in furps.obtener_caracteristicas()}
        self.assertEqual(
            nombres,
            {
                'Funcionalidad',
                'Usabilidad',
                'Fiabilidad',
                'Rendimiento',
                'Soporte',
            },
        )


class MetricaTests(TestCase):
    def setUp(self):
        self.caracteristica = Caracteristica.objects.get(nombre='Fiabilidad')
        self.metrica = Metrica.objects.create(
            caracteristica=self.caracteristica,
            nombre='Pruebas aprobadas',
            unidad='%',
        )

    def test_rango_sin_limites_no_valida(self):
        self.assertTrue(self.metrica.validar_rango(999))

    def test_rango_con_limites(self):
        self.metrica.valor_min = 0
        self.metrica.valor_max = 100
        self.assertTrue(self.metrica.validar_rango(50))
        self.assertFalse(self.metrica.validar_rango(101))
        self.assertFalse(self.metrica.validar_rango(-1))


class ModeloMetricaTests(TestCase):
    def test_cumplimiento_minimo(self):
        modelo_metrica = ModeloMetrica(umbral=90, tipo_umbral=TipoUmbral.MINIMO)
        self.assertTrue(modelo_metrica.evaluar_cumplimiento(95))
        self.assertFalse(modelo_metrica.evaluar_cumplimiento(80))

    def test_cumplimiento_maximo(self):
        modelo_metrica = ModeloMetrica(umbral=0, tipo_umbral=TipoUmbral.MAXIMO)
        self.assertTrue(modelo_metrica.evaluar_cumplimiento(0))
        self.assertFalse(modelo_metrica.evaluar_cumplimiento(2))


class CatalogoModelosViewTests(TestCase):
    def test_catalogo_muestra_los_cuatro_modelos(self):
        respuesta = self.client.get(reverse('modelos:catalogo'))
        self.assertEqual(respuesta.status_code, 200)
        for nombre in ['McCall', 'Boehm', 'FURPS', 'ISO/IEC 25010']:
            self.assertContains(respuesta, nombre)

    def test_catalogo_muestra_umbral_y_direccion(self):
        respuesta = self.client.get(reverse('modelos:catalogo'))
        self.assertContains(respuesta, 'Requisitos implementados correctamente')
        self.assertContains(respuesta, '≥')
        self.assertContains(respuesta, '≤')

    def test_catalogo_no_ofrece_aplicar(self):
        respuesta = self.client.get(reverse('modelos:catalogo'))
        self.assertNotContains(respuesta, 'Aplicar modelo')


class AplicarModeloTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto()
        self.miembro = crear_miembro(self.proyecto)
        self.modelo = ModeloCalidad.objects.get(nombre='McCall')
        self.otro = ModeloCalidad.objects.get(nombre='FURPS')

    def test_aplicar_crea_instantanea(self):
        aplicado = self.proyecto.aplicar_modelo(self.modelo)

        self.assertTrue(aplicado.vigente)
        self.assertEqual(aplicado.metricas_aplicadas().count(), 4)

    def test_aplicar_el_mismo_modelo_no_crea_otra(self):
        primero = self.proyecto.aplicar_modelo(self.modelo)
        segundo = self.proyecto.aplicar_modelo(self.modelo)

        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(ModeloAplicado.objects.count(), 1)

    def test_cambiar_modelo_cierra_el_anterior(self):
        primero = self.proyecto.aplicar_modelo(self.modelo)
        segundo = self.proyecto.aplicar_modelo(self.otro)
        primero.refresh_from_db()

        self.assertFalse(primero.vigente)
        self.assertIsNotNone(primero.fecha_cierre)
        self.assertTrue(segundo.vigente)
        self.assertEqual(ModeloAplicado.objects.count(), 2)

    def test_modelo_sin_metricas_se_rechaza(self):
        vacio = ModeloCalidad.objects.create(
            nombre='Vacío',
            descripcion='sin métricas',
            predefinido=True,
        )

        with self.assertRaises(ValidationError):
            self.proyecto.aplicar_modelo(vacio)

    def test_tiene_mediciones_solo_con_revisiones(self):
        aplicado = self.proyecto.aplicar_modelo(self.modelo)
        self.assertFalse(self.proyecto.tiene_mediciones())

        RevisionMetrica.objects.create(
            metrica_aplicada=aplicado.metricas_aplicadas().first(),
            miembro_proyecto=self.miembro,
            valor=90,
            enlace='https://ejemplo.test/evidencia',
        )

        self.assertTrue(self.proyecto.tiene_mediciones())


class RevisionMetricaTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto()
        self.miembro = crear_miembro(self.proyecto)
        self.aplicado = self.proyecto.aplicar_modelo(
            ModeloCalidad.objects.get(nombre='McCall')
        )
        self.instantanea = self.aplicado.metricas_aplicadas().get(
            metrica__nombre='Requisitos implementados correctamente'
        )

    def _revision(self, **kwargs):
        datos = {
            'metrica_aplicada': self.instantanea,
            'miembro_proyecto': self.miembro,
            'valor': 95,
            'enlace': 'https://ejemplo.test/evidencia',
        }
        datos.update(kwargs)
        return RevisionMetrica(**datos)

    def test_exige_evidencia(self):
        revision = self._revision(enlace='')

        with self.assertRaises(ValidationError):
            revision.full_clean()

    def test_exige_valor(self):
        revision = self._revision(valor=None)

        with self.assertRaises(ValidationError):
            revision.full_clean()

    def test_cumple_se_calcula_con_la_instantanea(self):
        revision = self._revision(valor=95)
        revision.save()
        self.assertTrue(revision.cumple)

        otra = self._revision(valor=50)
        otra.save()
        self.assertFalse(otra.cumple)

    def test_rechaza_valor_fuera_de_rango(self):
        self.instantanea.metrica.valor_min = 0
        self.instantanea.metrica.valor_max = 100
        self.instantanea.metrica.save(update_fields=['valor_min', 'valor_max'])

        revision = self._revision(valor=150)

        with self.assertRaises(ValidationError):
            revision.full_clean()

    def test_rechaza_autor_de_otro_proyecto(self):
        otro_proyecto = crear_proyecto('Otro')
        ajeno = crear_miembro(otro_proyecto, 'Luis')

        revision = self._revision(miembro_proyecto=ajeno)

        with self.assertRaises(ValidationError):
            revision.full_clean()

    def test_historial_y_ultimo_valor(self):
        self._revision(valor=90).save()
        self._revision(valor=95).save()
        metrica = self.instantanea.metrica

        self.assertEqual(metrica.revisiones(self.proyecto).count(), 2)
        self.assertEqual(metrica.ultimo_valor(self.proyecto), 95)

    def test_esta_aceptada_recalcula_con_el_umbral_vigente(self):
        metrica = self.instantanea.metrica
        self._revision(valor=95).save()

        self.assertTrue(metrica.esta_aceptada(self.proyecto))

        self.instantanea.umbral = 99
        self.instantanea.save(update_fields=['umbral'])

        self.assertFalse(metrica.esta_aceptada(self.proyecto))


class MetricaCompartidaTests(TestCase):
    """`metricas_comunes()` y conservación del progreso (HU-02)."""

    def setUp(self):
        self.proyecto = crear_proyecto()
        self.miembro = crear_miembro(self.proyecto)
        self.metrica = Metrica.objects.create(
            caracteristica=Caracteristica.objects.get(nombre='Funcionalidad'),
            nombre='Cobertura de pruebas',
            unidad='%',
        )
        self.modelo_a = ModeloCalidad.objects.create(
            nombre='Modelo A',
            descripcion='a',
            predefinido=True,
        )
        self.modelo_b = ModeloCalidad.objects.create(
            nombre='Modelo B',
            descripcion='b',
            predefinido=True,
        )
        ModeloMetrica.objects.create(
            modelo_calidad=self.modelo_a,
            metrica=self.metrica,
            umbral=80,
            tipo_umbral=TipoUmbral.MINIMO,
        )
        ModeloMetrica.objects.create(
            modelo_calidad=self.modelo_b,
            metrica=self.metrica,
            umbral=90,
            tipo_umbral=TipoUmbral.MINIMO,
        )

    def test_metrica_comun_conserva_el_ultimo_valor(self):
        aplicado_a = self.proyecto.aplicar_modelo(self.modelo_a)
        RevisionMetrica.objects.create(
            metrica_aplicada=aplicado_a.metricas_aplicadas().first(),
            miembro_proyecto=self.miembro,
            valor=85,
            enlace='https://ejemplo.test/a',
        )

        aplicado_b = self.proyecto.aplicar_modelo(self.modelo_b)

        self.assertEqual(
            set(aplicado_b.metricas_comunes(aplicado_a)),
            {self.metrica},
        )
        self.assertEqual(self.metrica.ultimo_valor(self.proyecto), 85)
        # El umbral cambió de 80 a 90: el cumplimiento vigente se recalcula.
        self.assertTrue(self.metrica.esta_aceptada(self.proyecto) is False)

    def test_calcular_seguimiento_de_la_caracteristica(self):
        aplicado = self.proyecto.aplicar_modelo(self.modelo_a)
        RevisionMetrica.objects.create(
            metrica_aplicada=aplicado.metricas_aplicadas().first(),
            miembro_proyecto=self.miembro,
            valor=85,
            enlace='https://ejemplo.test/a',
        )

        caracteristica = self.metrica.caracteristica

        self.assertEqual(caracteristica.metricas_aceptadas(self.proyecto), 1)
        self.assertEqual(caracteristica.calcular_seguimiento(self.proyecto), 100.0)


class MetricaAplicadaTests(TestCase):
    def test_revisiones_devuelve_las_de_la_instantanea(self):
        proyecto = crear_proyecto()
        miembro = crear_miembro(proyecto)
        aplicado = proyecto.aplicar_modelo(
            ModeloCalidad.objects.get(nombre='McCall')
        )
        instantanea = aplicado.metricas_aplicadas().first()
        RevisionMetrica.objects.create(
            metrica_aplicada=instantanea,
            miembro_proyecto=miembro,
            valor=90,
            enlace='https://ejemplo.test/a',
        )

        self.assertIsInstance(instantanea, MetricaAplicada)
        self.assertEqual(instantanea.revisiones().count(), 1)


class ModeloDelProyectoViewTests(TestCase):
    """El ítem del sidebar abre el modelo del proyecto seleccionado (HU-02)."""

    def setUp(self):
        self.url = reverse('modelos:modelo_proyecto')

    def test_redirige_al_modelo_del_proyecto_en_sesion(self):
        primera = crear_proyecto('Alpha')
        segunda = crear_proyecto('Beta')
        sesion = self.client.session
        sesion['ultimo_proyecto_id'] = segunda.pk
        sesion.save()

        respuesta = self.client.get(self.url)

        self.assertRedirects(
            respuesta,
            reverse('reportes:aplicar_modelo', args=[segunda.pk]),
        )
        self.assertNotEqual(primera.pk, segunda.pk)

    def test_sin_seleccion_cae_al_primer_proyecto(self):
        primera = crear_proyecto('Alpha')
        crear_proyecto('Beta')

        respuesta = self.client.get(self.url)

        self.assertRedirects(
            respuesta,
            reverse('reportes:aplicar_modelo', args=[primera.pk]),
        )

    def test_sin_proyectos_redirige_a_la_lista(self):
        respuesta = self.client.get(self.url)

        self.assertRedirects(respuesta, reverse('reportes:lista'))


class NavegacionModelosTests(TestCase):
    """Pestaña resaltada del sidebar y accesos de la pantalla de modelos."""

    def setUp(self):
        self.proyecto = crear_proyecto('Alpha')
        self.url_modelo = reverse(
            'reportes:aplicar_modelo', args=[self.proyecto.pk]
        )

    @staticmethod
    def _nav_activo(url):
        return f'class="nav-link active" href="{url}"'

    def test_pantalla_de_modelo_resalta_modelos_de_calidad(self):
        respuesta = self.client.get(self.url_modelo)

        self.assertContains(
            respuesta, self._nav_activo(reverse('modelos:modelo_proyecto'))
        )
        self.assertNotContains(
            respuesta, self._nav_activo(reverse('reportes:lista'))
        )

    def test_catalogo_resalta_modelos_de_calidad(self):
        respuesta = self.client.get(reverse('modelos:catalogo'))

        self.assertContains(
            respuesta, self._nav_activo(reverse('modelos:modelo_proyecto'))
        )
        self.assertNotContains(
            respuesta, self._nav_activo(reverse('reportes:lista'))
        )

    def test_tablero_resalta_el_dashboard(self):
        respuesta = self.client.get(
            reverse('reportes:tablero', args=[self.proyecto.pk])
        )

        self.assertContains(respuesta, self._nav_activo(reverse('inicio')))

    def test_metricas_resalta_modelos_de_calidad(self):
        respuesta = self.client.get(
            reverse('reportes:metricas', args=[self.proyecto.pk])
        )

        self.assertEqual(respuesta.context['nav_activo'], 'modelos')
        self.assertContains(
            respuesta, self._nav_activo(reverse('modelos:modelo_proyecto'))
        )
        self.assertNotContains(
            respuesta, self._nav_activo(reverse('reportes:lista'))
        )

    def test_revision_de_metrica_resalta_modelos_de_calidad(self):
        aplicado = self.proyecto.aplicar_modelo(
            ModeloCalidad.objects.get(nombre='McCall')
        )
        metrica = aplicado.metricas_aplicadas().first().metrica

        respuesta = self.client.get(
            reverse(
                'reportes:registrar_revision',
                args=[self.proyecto.pk, metrica.pk],
            )
        )

        self.assertEqual(respuesta.context['nav_activo'], 'modelos')
        self.assertNotContains(
            respuesta, self._nav_activo(reverse('reportes:lista'))
        )

    def test_lista_de_proyectos_resalta_registro_de_proyectos(self):
        respuesta = self.client.get(reverse('reportes:lista'))

        self.assertEqual(respuesta.context['nav_activo'], 'proyectos')
        self.assertContains(
            respuesta, self._nav_activo(reverse('reportes:lista'))
        )

    def test_pantalla_de_modelo_enlaza_al_catalogo(self):
        respuesta = self.client.get(self.url_modelo)

        self.assertContains(respuesta, 'Ver catálogo de modelos')

    def test_pantalla_de_modelo_muestra_el_modelo_aplicado(self):
        self.proyecto.aplicar_modelo(
            ModeloCalidad.objects.get(nombre='McCall')
        )

        respuesta = self.client.get(self.url_modelo)

        self.assertContains(respuesta, 'Modelo aplicado')
        self.assertContains(respuesta, 'McCall')
        self.assertNotContains(respuesta, 'Sin modelo de calidad aplicado')

    def test_pantalla_de_modelo_sin_aplicar_lo_avisa(self):
        respuesta = self.client.get(self.url_modelo)

        self.assertContains(respuesta, 'Sin modelo de calidad aplicado')
