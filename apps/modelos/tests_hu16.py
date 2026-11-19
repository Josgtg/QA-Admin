from django.test import TestCase
from django.urls import reverse

from .models import ModeloCalidad


class ModelosPropiosTests(TestCase):
    def setUp(self):
        self.datos = {
            'nombre': 'Modelo de entrega', 'descripcion': 'Calidad del proyecto',
            'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '0',
            'form-0-caracteristica': 'Cobertura', 'form-0-nombre': 'Cobertura de pruebas',
            'form-0-forma_medicion': 'Dividir líneas cubiertas entre líneas totales',
            'form-0-unidad': '%', 'form-0-meta': '80', 'form-0-tipo_umbral': 'MINIMO',
        }

    def test_crear_consultar_y_eliminar(self):
        respuesta = self.client.post(reverse('modelos:crear'), self.datos, follow=True)
        self.assertContains(respuesta, 'Modelo de entrega')
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        self.assertEqual(modelo.modelo_metricas.get().umbral, 80)
        self.client.post(reverse('modelos:eliminar', args=[modelo.pk]))
        self.assertFalse(ModeloCalidad.objects.filter(pk=modelo.pk).exists())

    def test_falta_unidad(self):
        self.client.post(reverse('modelos:crear'), {**self.datos, 'form-0-unidad': ''})
        self.assertFalse(ModeloCalidad.objects.filter(nombre=self.datos['nombre']).exists())

    def test_nombre_duplicado(self):
        for intento in range(2):
            self.client.post(reverse('modelos:crear'), self.datos)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        self.assertEqual(modelo.modelo_metricas.count(), 1)

    def test_proyecto_puede_aplicarlo_y_protege_su_historial(self):
        from apps.reportes.tests import crear_proyecto

        proyecto = crear_proyecto('Proyecto demostrativo')
        self.client.post(reverse('modelos:crear'), self.datos)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        respuesta = self.client.post(reverse('reportes:aplicar_modelo', args=[proyecto.pk]),
                                     {'modelo_id': modelo.pk})
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(modelo.aplicaciones.filter(proyecto=proyecto, vigente=True).exists())
        respuesta = self.client.post(reverse('modelos:eliminar', args=[modelo.pk]), follow=True)
        self.assertContains(respuesta, proyecto.nombre)
        self.assertTrue(ModeloCalidad.objects.filter(pk=modelo.pk).exists())
