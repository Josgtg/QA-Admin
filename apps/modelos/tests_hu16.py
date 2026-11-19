"""Pruebas de HU-16: modelos propios de calidad."""

from django.test import TestCase
from django.urls import reverse

from apps.reportes.tests import crear_proyecto

from .models import Metrica, ModeloCalidad


class ModelosDisponiblesTests(TestCase):
    """Selección de modelos que ofrece el catálogo y la aplicación."""

    def test_incluye_predefinidos_y_propios_con_metricas_activas(self):
        self.client.post(
            reverse('modelos:crear'),
            {
                'nombre': 'Modelo propio',
                'descripcion': 'Con una métrica',
                'form-TOTAL_FORMS': '1',
                'form-INITIAL_FORMS': '0',
                'form-0-caracteristica': 'Fiabilidad',
                'form-0-nombre': 'Disponibilidad',
                'form-0-forma_medicion': 'Tiempo disponible entre el total.',
                'form-0-unidad': '%',
                'form-0-meta': '99',
                'form-0-tipo_umbral': 'MINIMO',
            },
        )
        vacio = ModeloCalidad.objects.create(
            nombre='Modelo vacío',
            descripcion='Sin métricas',
        )

        disponibles = set(ModeloCalidad.disponibles())

        self.assertEqual(len(disponibles), 5)
        self.assertIn(vacio, ModeloCalidad.objects.all())
        self.assertNotIn(vacio, disponibles)


class ModelosPropiosTests(TestCase):
    """Ciclo de vida de un modelo propio desde las rutas públicas."""

    def setUp(self):
        self.url_crear = reverse('modelos:crear')
        self.url_catalogo = reverse('modelos:catalogo')
        self.datos = {
            'nombre': 'Modelo de entrega',
            'descripcion': 'Modelo propio para el proyecto',
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-0-caracteristica': 'Mantenibilidad',
            'form-0-nombre': 'Cobertura de pruebas',
            'form-0-descripcion': 'Porcentaje de líneas cubiertas.',
            'form-0-forma_medicion': (
                'Dividir líneas cubiertas entre líneas totales.'
            ),
            'form-0-unidad': '%',
            'form-0-meta': '80',
            'form-0-tipo_umbral': 'MINIMO',
        }

    def test_get_muestra_el_formulario(self):
        respuesta = self.client.get(self.url_crear)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Crear modelo propio')
        self.assertContains(respuesta, 'Agregar métrica')

    def test_crear_modelo_con_una_metrica(self):
        respuesta = self.client.post(self.url_crear, self.datos)

        self.assertRedirects(respuesta, self.url_catalogo)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        self.assertFalse(modelo.predefinido)
        modelo_metrica = modelo.modelo_metricas.select_related(
            'metrica__caracteristica'
        ).get()
        self.assertEqual(modelo_metrica.umbral, 80)
        self.assertEqual(modelo_metrica.tipo_umbral, 'MINIMO')
        self.assertEqual(
            modelo_metrica.metrica.caracteristica.nombre,
            'Mantenibilidad',
        )
        self.assertEqual(modelo_metrica.metrica.unidad, '%')
        self.assertTrue(modelo_metrica.metrica.forma_medicion)

    def test_modelo_propio_aparece_en_catalogo_y_se_puede_aplicar(self):
        self.client.post(self.url_crear, self.datos)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        proyecto = crear_proyecto('Proyecto con modelo propio')

        catalogo = self.client.get(self.url_catalogo)
        self.assertContains(catalogo, self.datos['nombre'])
        self.assertContains(catalogo, 'Propio')

        aplicar = reverse(
            'reportes:aplicar_modelo',
            args=[proyecto.pk],
        )
        seleccion = self.client.get(aplicar)
        self.assertContains(seleccion, self.datos['nombre'])

        respuesta = self.client.post(
            aplicar,
            {'modelo_id': modelo.pk},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            modelo.aplicaciones.filter(
                proyecto=proyecto,
                vigente=True,
            ).exists()
        )

    def test_nombre_duplicado_no_guarda_metricas_extra(self):
        self.client.post(self.url_crear, self.datos)

        respuesta = self.client.post(self.url_crear, self.datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ya existe un modelo con este nombre')
        self.assertEqual(
            ModeloCalidad.objects.filter(
                nombre=self.datos['nombre']
            ).count(),
            1,
        )
        self.assertEqual(
            ModeloCalidad.objects.get(
                nombre=self.datos['nombre']
            ).modelo_metricas.count(),
            1,
        )

    def test_sin_metricas_muestra_error_y_no_guarda(self):
        datos = {
            'nombre': 'Modelo sin métricas',
            'descripcion': 'No debe guardarse',
            'form-TOTAL_FORMS': '0',
            'form-INITIAL_FORMS': '0',
        }

        respuesta = self.client.post(self.url_crear, datos)

        errores = respuesta.context['metricas_formset'].non_form_errors()
        self.assertEqual(errores.as_data()[0].code, 'too_few_forms')
        self.assertContains(respuesta, errores[0])
        self.assertFalse(
            ModeloCalidad.objects.filter(
                nombre=datos['nombre']
            ).exists()
        )

    def test_metrica_sin_unidad_no_guarda_el_modelo(self):
        datos = {**self.datos, 'form-0-unidad': ''}

        respuesta = self.client.post(self.url_crear, datos)

        self.assertContains(respuesta, 'Este campo es obligatorio.')
        self.assertFalse(
            ModeloCalidad.objects.filter(
                nombre=self.datos['nombre']
            ).exists()
        )

    def test_nombre_vacio_muestra_mensaje_claro(self):
        respuesta = self.client.post(
            self.url_crear,
            {**self.datos, 'nombre': ''},
        )

        self.assertContains(respuesta, 'Este campo es obligatorio.')
        self.assertFalse(
            ModeloCalidad.objects.filter(
                descripcion=self.datos['descripcion']
            ).exists()
        )

    def test_descripcion_vacia_muestra_mensaje_claro(self):
        respuesta = self.client.post(
            self.url_crear,
            {**self.datos, 'descripcion': ''},
        )

        self.assertContains(respuesta, 'Este campo es obligatorio.')
        self.assertFalse(
            ModeloCalidad.objects.filter(
                nombre=self.datos['nombre']
            ).exists()
        )

    def test_forma_de_medir_vacia_no_guarda(self):
        datos = {**self.datos, 'form-0-forma_medicion': ''}

        respuesta = self.client.post(self.url_crear, datos)

        self.assertContains(respuesta, 'Este campo es obligatorio.')
        self.assertFalse(
            ModeloCalidad.objects.filter(
                nombre=self.datos['nombre']
            ).exists()
        )

    def test_meta_vacia_no_guarda(self):
        datos = {**self.datos, 'form-0-meta': ''}

        respuesta = self.client.post(self.url_crear, datos)

        self.assertContains(respuesta, 'Este campo es obligatorio.')
        self.assertFalse(
            ModeloCalidad.objects.filter(
                nombre=self.datos['nombre']
            ).exists()
        )

    def test_duplicado_ignora_mayusculas(self):
        self.client.post(self.url_crear, self.datos)

        respuesta = self.client.post(
            self.url_crear,
            {**self.datos, 'nombre': self.datos['nombre'].upper()},
        )

        self.assertContains(respuesta, 'Ya existe un modelo con este nombre.')
        self.assertEqual(
            ModeloCalidad.objects.filter(
                nombre__iexact=self.datos['nombre']
            ).count(),
            1,
        )

    def test_modelo_sin_metricas_activas_no_se_ofrece(self):
        self.client.post(self.url_crear, self.datos, follow=True)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        modelo.modelo_metricas.update(activa=False)

        self.assertNotIn(modelo, ModeloCalidad.disponibles())
        catalogo = self.client.get(self.url_catalogo)
        self.assertNotContains(catalogo, self.datos['nombre'])

    def test_proyectos_que_lo_usan_no_repite_nombres(self):
        self.client.post(self.url_crear, self.datos)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        otro = ModeloCalidad.objects.get(nombre='McCall')
        proyecto = crear_proyecto('Proyecto que cambia de modelo')

        proyecto.aplicar_modelo(modelo)
        proyecto.aplicar_modelo(otro)
        proyecto.aplicar_modelo(modelo)

        self.assertEqual(modelo.aplicaciones.count(), 2)
        self.assertEqual(
            modelo.proyectos_que_lo_usan(),
            [proyecto.nombre],
        )

    def test_catalogo_sin_modelos_muestra_estado_vacio(self):
        ModeloCalidad.objects.all().delete()

        respuesta = self.client.get(self.url_catalogo)

        self.assertContains(
            respuesta,
            'No hay modelos de calidad disponibles',
        )

    def test_modelo_en_uso_conserva_sus_metricas(self):
        self.client.post(self.url_crear, self.datos)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        metrica_id = modelo.modelo_metricas.get().metrica_id
        proyecto = crear_proyecto('Proyecto que conserva el modelo')
        proyecto.aplicar_modelo(modelo)
        url = reverse('modelos:eliminar', args=[modelo.pk])

        respuesta = self.client.post(url)

        self.assertRedirects(respuesta, self.url_catalogo)
        self.assertTrue(ModeloCalidad.objects.filter(pk=modelo.pk).exists())
        self.assertTrue(Metrica.objects.filter(pk=metrica_id).exists())

    def test_eliminar_modelo_propio_libre(self):
        self.client.post(self.url_crear, self.datos)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        metrica_id = modelo.modelo_metricas.get().metrica_id
        url = reverse('modelos:eliminar', args=[modelo.pk])

        respuesta = self.client.post(url)

        self.assertRedirects(respuesta, self.url_catalogo)
        self.assertFalse(ModeloCalidad.objects.filter(pk=modelo.pk).exists())
        self.assertFalse(Metrica.objects.filter(pk=metrica_id).exists())

    def test_no_elimina_modelo_usado_e_indica_los_proyectos(self):
        self.client.post(self.url_crear, self.datos)
        modelo = ModeloCalidad.objects.get(nombre=self.datos['nombre'])
        proyecto = crear_proyecto('Proyecto que usa el modelo')
        proyecto.aplicar_modelo(modelo)
        url = reverse('modelos:eliminar', args=[modelo.pk])

        respuesta = self.client.post(url, follow=True)

        self.assertContains(respuesta, proyecto.nombre)
        self.assertTrue(ModeloCalidad.objects.filter(pk=modelo.pk).exists())

    def test_no_elimina_un_modelo_predefinido(self):
        modelo = ModeloCalidad.objects.get(nombre='McCall')
        url = reverse('modelos:eliminar', args=[modelo.pk])

        respuesta = self.client.post(url)

        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(ModeloCalidad.objects.filter(pk=modelo.pk).exists())
