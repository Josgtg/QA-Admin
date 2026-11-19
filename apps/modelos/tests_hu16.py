from django.test import TestCase
from django.urls import reverse

from .models import ModeloCalidad


class ModelosPropiosTests(TestCase):
    """Comprueba el ciclo de vida de modelos propios desde las rutas públicas."""
    def setUp(self):
        """Prepara una captura válida con una métrica."""
        self.datos = {
            'nombre': 'Modelo de entrega', 'descripcion': 'Calidad del proyecto',
            'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '0',
            'form-0-caracteristica': 'Cobertura',
            'form-0-nombre': 'Cobertura de pruebas',
            'form-0-forma_medicion': 'Dividir líneas cubiertas entre líneas totales',
            'form-0-unidad': '%', 'form-0-meta': '80', 'form-0-tipo_umbral': 'MINIMO',
        }

    def test_crear_consultar_y_eliminar(self):
        """Comprueba el alta, el umbral y el borrado de un modelo libre."""
        respuesta = self.client.post(reverse('modelos:crear'), self.datos, follow=True)
        self.assertContains(respuesta, 'Modelo de entrega')
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        self.assertEqual(modelo.modelo_metricas.get().umbral, 80)
        self.client.post(reverse('modelos:eliminar', args=[modelo.pk]))
        self.assertFalse(ModeloCalidad.objects.filter(pk=modelo.pk).exists())

    def test_falta_unidad(self):
        """Comprueba el rechazo de una métrica sin unidad."""
        self.client.post(reverse('modelos:crear'), {**self.datos, 'form-0-unidad': ''})
        modelos = ModeloCalidad.objects.filter(nombre=self.datos['nombre'])
        self.assertFalse(modelos.exists())

    def test_nombre_duplicado(self):
        """Evita duplicar el modelo y sus métricas al reenviar los datos."""
        for intento in range(2):
            self.client.post(reverse('modelos:crear'), self.datos)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        self.assertEqual(modelo.modelo_metricas.count(), 1)

    def test_proyecto_puede_aplicarlo_y_protege_su_historial(self):
        """Verifica la aplicación y la identificación del proyecto al intentar borrar."""
        from apps.reportes.tests import crear_proyecto

        proyecto = crear_proyecto('Proyecto demostrativo')
        self.client.post(reverse('modelos:crear'), self.datos)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        aplicar = reverse('reportes:aplicar_modelo', args=[proyecto.pk])
        respuesta = self.client.post(aplicar, {'modelo_id': modelo.pk})
        self.assertEqual(respuesta.status_code, 302)
        vigentes = modelo.aplicaciones.filter(proyecto=proyecto, vigente=True)
        self.assertTrue(vigentes.exists())
        eliminar = reverse('modelos:eliminar', args=[modelo.pk])
        respuesta = self.client.post(eliminar, follow=True)
        self.assertContains(respuesta, proyecto.nombre)
        self.assertTrue(ModeloCalidad.objects.filter(pk=modelo.pk).exists())

    def test_sin_filas_de_metricas_muestra_error_y_no_guarda(self):
        """Comprueba el mensaje visible y la ausencia de un registro parcial."""
        datos = {
            'nombre': 'Sin métricas',
            'descripcion': 'Modelo de prueba',
            'form-TOTAL_FORMS': '0',
            'form-INITIAL_FORMS': '0',
        }
        respuesta = self.client.post(reverse('modelos:crear'), datos)
        errores = respuesta.context['metricas'].non_form_errors()
        self.assertEqual(errores.as_data()[0].code, 'too_few_forms')
        self.assertContains(respuesta, errores[0])
        self.assertFalse(ModeloCalidad.objects.filter(nombre=datos['nombre']).exists())
