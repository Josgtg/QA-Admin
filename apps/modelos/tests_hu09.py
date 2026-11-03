"""Pruebas de HU-09: catálogo base de métricas (solo lectura)."""

from django.test import TestCase
from django.urls import reverse

from .models import Caracteristica, Metrica, ModeloCalidad, ModeloMetrica
from .views import CatalogoMetricasView


class RangoEsperadoTests(TestCase):
    """``Metrica.rango_esperado()`` compone rango y unidad."""

    def setUp(self):
        self.caracteristica = Caracteristica.objects.get(nombre='Fiabilidad')

    def _metrica(self, **kwargs):
        datos = {
            'caracteristica': self.caracteristica,
            'nombre': 'Métrica de prueba',
            'unidad': '%',
        }
        datos.update(kwargs)
        return Metrica.objects.create(**datos)

    def test_rango_completo(self):
        metrica = self._metrica(valor_min=0, valor_max=100)

        self.assertEqual(metrica.rango_esperado(), '0 – 100 %')

    def test_solo_maximo(self):
        metrica = self._metrica(valor_max=24, unidad='horas')

        self.assertEqual(metrica.rango_esperado(), '≤ 24 horas')

    def test_solo_minimo(self):
        metrica = self._metrica(valor_min=90)

        self.assertEqual(metrica.rango_esperado(), '≥ 90 %')

    def test_sin_limites_devuelve_none(self):
        metrica = self._metrica()

        self.assertIsNone(metrica.rango_esperado())

    def test_decimales_se_conservan(self):
        metrica = self._metrica(valor_min=0.5, valor_max=2.5, unidad='s')

        self.assertEqual(metrica.rango_esperado(), '0.5 – 2.5 s')

    def test_metricas_sembradas_traen_forma_de_medicion(self):
        """La migración de datos completa ``forma_medicion`` del seed."""
        for metrica in Metrica.objects.all():
            self.assertTrue(
                metrica.forma_medicion.strip(),
                f'{metrica.nombre} no tiene forma de medición',
            )


class CatalogoMetricasViewTests(TestCase):
    """HU-09: listado, filtros y solo lectura."""

    def setUp(self):
        self.view = CatalogoMetricasView()
        self.url = reverse('catalogo_metricas')

    def test_la_url_es_metricas_catalogo(self):
        self.assertEqual(self.url, '/metricas/catalogo/')

    def test_get_responde_200(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)

    def test_listar_metricas_incluye_todo_el_catalogo(self):
        self.assertEqual(
            self.view.listar_metricas().count(),
            Metrica.objects.count(),
        )

    def test_catalogo_muestra_los_datos_exigidos_por_el_ca(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Catálogo base de métricas')
        self.assertContains(respuesta, 'Forma de medición')
        self.assertContains(respuesta, 'Rango esperado')
        # Una métrica concreta del seed y su unidad.
        self.assertContains(respuesta, 'Disponibilidad')
        self.assertContains(respuesta, 'Sin límites definidos')

    def test_catalogo_agrupa_por_caracteristica(self):
        respuesta = self.client.get(self.url)

        agrupadas = respuesta.context['agrupadas']
        self.assertGreater(len(agrupadas), 0)
        for _, grupo in agrupadas:
            self.assertTrue(grupo['metricas'])
            for metrica in grupo['metricas']:
                self.assertEqual(metrica.caracteristica.nombre, grupo['nombre'])

    def test_filtra_por_caracteristica(self):
        caracteristica = Caracteristica.objects.get(nombre='Fiabilidad')

        respuesta = self.client.get(
            self.url, {'caracteristica': caracteristica.pk}
        )

        self.assertEqual(respuesta.status_code, 200)
        metricas = list(respuesta.context['metricas'])
        self.assertTrue(metricas)
        self.assertTrue(
            all(m.caracteristica_id == caracteristica.pk for m in metricas)
        )

    def test_filtrar_por_caracteristica_devuelve_subconjunto(self):
        caracteristica = Caracteristica.objects.get(nombre='Fiabilidad')

        filtradas = self.view.filtrar_por_caracteristica(caracteristica.pk)

        self.assertLess(filtradas.count(), self.view.listar_metricas().count())
        self.assertTrue(filtradas.exists())

    def test_caracteristica_inexistente_avisa_sin_404(self):
        """ESP-06: un id inexistente avisa en vez de dar un 404 genérico."""
        respuesta = self.client.get(self.url, {'caracteristica': 999999})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'La característica indicada no existe')
        self.assertEqual(
            respuesta.context['metricas'].count(),
            Metrica.objects.count(),
        )

    def test_caracteristica_ilegible_no_rompe(self):
        respuesta = self.client.get(self.url, {'caracteristica': 'abc'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.context['metricas'].count(),
            Metrica.objects.count(),
        )

    def test_caracteristicas_disponibles_solo_con_metricas(self):
        disponibles = self.view.caracteristicas_disponibles()

        for caracteristica in disponibles:
            self.assertTrue(caracteristica.metricas.exists())

    def test_filtro_sin_coincidencias_muestra_estado_vacio(self):
        Caracteristica.objects.create(nombre='Vacía', descripcion='sin métricas')

        respuesta = self.client.get(
            self.url,
            {'caracteristica': Caracteristica.objects.get(nombre='Vacía').pk},
        )

        self.assertContains(respuesta, 'No hay métricas para este filtro')

    def test_es_solo_lectura_no_acepta_post(self):
        total_antes = Metrica.objects.count()

        respuesta = self.client.post(self.url, {})

        self.assertEqual(respuesta.status_code, 405)
        self.assertEqual(Metrica.objects.count(), total_antes)

    def test_no_ofrece_acciones_de_edicion(self):
        respuesta = self.client.get(self.url)
        contenido = respuesta.content.decode()

        for accion in ['Crear métrica', 'Editar métrica', 'Eliminar métrica']:
            self.assertNotIn(accion, contenido)


class CatalogoMetricasConformidadTests(TestCase):
    """El filtro de conformidad es informativo y exige un valor medido."""

    def setUp(self):
        self.view = CatalogoMetricasView()
        self.url = reverse('catalogo_metricas')
        self.modelo = ModeloCalidad.objects.get(nombre='McCall')

    def test_filtrar_por_conformidad_minimo(self):
        # McCall: «Requisitos implementados correctamente» es ≥ 90 %.
        cumplen = self.view.filtrar_por_conformidad(self.modelo, True, 95)

        self.assertTrue(
            cumplen.filter(nombre='Requisitos implementados correctamente')
            .exists()
        )

    def test_filtrar_por_no_conformidad(self):
        no_cumplen = self.view.filtrar_por_conformidad(self.modelo, False, 95)

        self.assertFalse(
            no_cumplen.filter(
                nombre='Requisitos implementados correctamente'
            ).exists()
        )

    def test_umbral_maximo_se_evalua_al_reves(self):
        # «Defectos críticos abiertos» es ≤ 0: con 0 cumple.
        cumplen = self.view.filtrar_por_conformidad(self.modelo, True, 0)

        self.assertTrue(
            cumplen.filter(nombre='Defectos críticos abiertos').exists()
        )

    def test_sin_valor_no_filtra(self):
        """Sin valor medido no hay comparación: se devuelven todas."""
        resultado = self.view.filtrar_por_conformidad(self.modelo, True, None)

        self.assertEqual(resultado.count(), self.view.listar_metricas().count())

    def test_get_con_modelo_y_conformidad_responde(self):
        respuesta = self.client.get(
            self.url,
            {'modelo': self.modelo.pk, 'cumple': '1', 'valor': '95'},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['con_formula'])
        self.assertContains(respuesta, 'Filtro informativo')

    def test_validacion_de_entradas_tolerante(self):
        respuesta = self.client.get(
            self.url,
            {'modelo': 'x', 'cumple': 'quizá', 'valor': 'no-numero'},
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_valor_con_coma_decimal(self):
        respuesta = self.client.get(
            self.url,
            {'modelo': self.modelo.pk, 'cumple': '1', 'valor': '95,5'},
        )

        self.assertEqual(respuesta.status_code, 200)


class CatalogoMetricasEntradasInvalidasTests(TestCase):
    """ESP-06: las entradas inválidas se avisan, no se ignoran en silencio."""

    def setUp(self):
        self.url = reverse('catalogo_metricas')
        self.modelo = ModeloCalidad.objects.get(nombre='McCall')

    def test_valor_no_numerico_avisa(self):
        respuesta = self.client.get(
            self.url,
            {'modelo': self.modelo.pk, 'cumple': '1', 'valor': 'abc'},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'El valor medido no es un número')

    def test_conformidad_invalida_avisa(self):
        respuesta = self.client.get(self.url, {'cumple': 'quizá'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta, 'El filtro de conformidad debe ser'
        )

    def test_modelo_inexistente_avisa(self):
        respuesta = self.client.get(
            self.url, {'modelo': 999999, 'cumple': '1'}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'El modelo indicado no existe')

    def test_conformidad_sin_modelo_avisa(self):
        respuesta = self.client.get(self.url, {'cumple': '1'})

        self.assertContains(
            respuesta, 'El filtro de conformidad necesita un modelo'
        )

    def test_conformidad_sin_valor_avisa(self):
        respuesta = self.client.get(
            self.url, {'modelo': self.modelo.pk, 'cumple': '1'}
        )

        self.assertContains(
            respuesta, 'Indica un valor medido para comparar'
        )

    def test_entrada_valida_no_muestra_avisos(self):
        respuesta = self.client.get(
            self.url,
            {'modelo': self.modelo.pk, 'cumple': '1', 'valor': '95'},
        )

        self.assertEqual(respuesta.context['avisos'], [])


class UmbralesPorModeloTests(TestCase):
    """ESP-04: el catálogo no muestra umbrales de configuraciones inactivas."""

    def test_omite_modelo_metrica_inactiva(self):
        metrica = Metrica.objects.get(nombre='Disponibilidad')
        modelo_metrica = metrica.umbrales_por_modelo().first()
        self.assertIsNotNone(modelo_metrica)

        modelo_metrica.activa = False
        modelo_metrica.save(update_fields=['activa'])

        self.assertNotIn(
            modelo_metrica,
            list(metrica.umbrales_por_modelo()),
        )

    def test_el_catalogo_no_muestra_umbrales_inactivos(self):
        metrica = Metrica.objects.get(nombre='Disponibilidad')
        modelo_metrica = metrica.umbrales_por_modelo().first()
        nombre_modelo = modelo_metrica.modelo_calidad.nombre
        modelo_metrica.activa = False
        modelo_metrica.save(update_fields=['activa'])

        respuesta = self.client.get(
            reverse('catalogo_metricas'),
            {'caracteristica': metrica.caracteristica_id},
        )

        self.assertNotContains(
            respuesta,
            f'{nombre_modelo}:',
        )


class MenuCatalogoMetricasTests(TestCase):
    def test_el_menu_enlaza_al_catalogo_de_metricas(self):
        respuesta = self.client.get(reverse('catalogo_metricas'))

        self.assertEqual(respuesta.context['nav_activo'], 'catalogo_metricas')
        self.assertContains(respuesta, 'Catálogo de Métricas')

    def test_el_catalogo_muestra_umbrales_por_modelo(self):
        respuesta = self.client.get(reverse('catalogo_metricas'))

        self.assertContains(respuesta, 'Umbral por modelo')
        self.assertTrue(ModeloMetrica.objects.exists())
