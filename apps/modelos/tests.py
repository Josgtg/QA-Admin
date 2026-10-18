from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Caracteristica, Metrica, ModeloCalidad, TipoUmbral


class ModelosBaseTests(TestCase):

    def test_hay_cuatro_modelos_predefinidos(self):
        self.assertEqual(ModeloCalidad.obtener_predefinidos().count(), 4)

    def test_cada_modelo_tiene_varias_metricas(self):
        for modelo in ModeloCalidad.obtener_predefinidos():
            metricas = Metrica.objects.filter(caracteristica__modelo=modelo)
            self.assertGreater(metricas.count(), 1, modelo.nombre)

    def test_cada_metrica_activa_tiene_meta(self):
        metricas_sin_meta = Metrica.objects.filter(activa=True, meta=None)
        self.assertFalse(metricas_sin_meta.exists())


class MetricaTests(TestCase):

    def setUp(self):
        modelo = ModeloCalidad.objects.create(nombre='Prueba', descripcion='x')
        self.caracteristica = Caracteristica.objects.create(
            modelo=modelo,
            nombre='Fiabilidad',
        )

    def test_metrica_activa_sin_meta_no_es_valida(self):
        metrica = Metrica(
            caracteristica=self.caracteristica,
            nombre='Pruebas aprobadas',
            unidad='%',
        )
        with self.assertRaises(ValidationError):
            metrica.full_clean()

    def test_cumple_meta_minima(self):
        metrica = Metrica(meta=90, tipo_umbral=TipoUmbral.MINIMO)
        self.assertTrue(metrica.cumple_meta(95))
        self.assertFalse(metrica.cumple_meta(80))

    def test_cumple_meta_maxima(self):
        metrica = Metrica(meta=0, tipo_umbral=TipoUmbral.MAXIMO)
        self.assertTrue(metrica.cumple_meta(0))
        self.assertFalse(metrica.cumple_meta(2))


class CatalogoModelosViewTests(TestCase):

    def test_catalogo_muestra_los_cuatro_modelos(self):
        respuesta = self.client.get(reverse('modelos:catalogo'))
        self.assertEqual(respuesta.status_code, 200)
        for nombre in ['McCall', 'Boehm', 'FURPS', 'ISO/IEC 25010']:
            self.assertContains(respuesta, nombre)

    def test_catalogo_muestra_las_metas(self):
        respuesta = self.client.get(reverse('modelos:catalogo'))
        self.assertContains(respuesta, 'Requisitos implementados correctamente')
        self.assertContains(respuesta, '≥')
        self.assertContains(respuesta, '≤')
