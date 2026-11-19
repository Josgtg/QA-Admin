"""Técnicas propias: crear, marcar, elegir y proteger las base (HU-17)."""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Evidencia, Paso, SeguimientoPaso, SeguimientoTecnica, TecnicaQA
from .selection import SESSION_KEY
from .services import (
    eliminar_tecnica_propia,
    guardar_tecnica_propia,
    seguir_tecnica,
)
from .tests import crear_miembro, crear_proyecto


def datos_tecnica(pasos=(('Revisar el plan', 'Plan firmado'),), **cambios):
    """POST válido del formulario de técnica con los pasos indicados."""
    datos = {
        'nombre': 'Auditoría de accesibilidad',
        'dimension': 'DISENO',
        'tipo_control': 'VERIFICACION',
        'descripcion': 'Revisión de contraste y lectores de pantalla.',
        'objetivo': '',
        'pregunta_clave': '',
        'pasos-TOTAL_FORMS': str(len(pasos)),
        'pasos-INITIAL_FORMS': '0',
        'pasos-MIN_NUM_FORMS': '0',
        'pasos-MAX_NUM_FORMS': '1000',
    }
    for indice, (instruccion, evidencia) in enumerate(pasos):
        datos[f'pasos-{indice}-instruccion'] = instruccion
        datos[f'pasos-{indice}-evidencia_esperada'] = evidencia
    datos.update(cambios)
    return datos


def crear_propia(nombre='Técnica propia', pasos=2):
    """Técnica propia (sin catálogo) con pasos numerados."""
    tecnica = TecnicaQA.objects.create(
        nombre=nombre,
        descripcion='Descripción',
        objetivo='',
        pregunta_clave='',
        dimension='DESARROLLO',
        tipo_control='VERIFICACION',
    )
    for orden in range(1, pasos + 1):
        Paso.objects.create(
            tecnica=tecnica,
            orden=orden,
            instruccion=f'Paso {orden}',
            evidencia_esperada=f'Evidencia {orden}',
        )
    return tecnica


def registrar_evidencia(seguimiento, proyecto):
    """Evidencia en el primer paso del seguimiento."""
    return Evidencia.objects.create(
        seguimiento_paso=seguimiento.pasos.first(),
        miembro_proyecto=crear_miembro(proyecto),
        enlace='https://ejemplo.test/evidencia',
    )


class CrearTecnicaHU17Tests(TestCase):
    """CA1 y CA2: datos obligatorios y evidencia esperada en cada paso."""

    url = reverse('tecnicas:crear')

    def test_formulario_muestra_campos_y_agregar_paso(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        for texto in (
            'Nombre de la técnica', 'Dimensión', 'Tipo de control',
            'Descripción', 'Qué hay que hacer', 'Evidencia que se espera',
            'Agregar paso', 'Elige una dimensión', 'Elige el tipo de control',
        ):
            self.assertContains(respuesta, texto)
        self.assertNotContains(respuesta, 'Select an option')

    def test_crea_tecnica_propia_con_sus_pasos_en_orden(self):
        respuesta = self.client.post(self.url, datos_tecnica(pasos=(
            ('Revisar contraste', 'Captura del verificador'),
            ('Probar con lector de pantalla', 'Video de la prueba'),
        )))
        tecnica = TecnicaQA.objects.get(nombre='Auditoría de accesibilidad')
        self.assertRedirects(
            respuesta, reverse('tecnicas:detalle', args=[tecnica.pk])
        )
        self.assertTrue(tecnica.es_propia())
        self.assertEqual(
            [
                (p.orden, p.instruccion, p.evidencia_esperada)
                for p in tecnica.obtener_pasos()
            ],
            [
                (1, 'Revisar contraste', 'Captura del verificador'),
                (2, 'Probar con lector de pantalla', 'Video de la prueba'),
            ],
        )

    def test_campos_obligatorios_vacios_no_se_guardan(self):
        casos = {
            'nombre': ('   ', 'Escribe el nombre de la técnica.'),
            'dimension': ('', 'Elige la dimensión de la técnica.'),
            'tipo_control': ('', 'Elige el tipo de control.'),
            'descripcion': ('   ', 'Escribe la descripción de la técnica.'),
        }
        for campo, (valor, mensaje) in casos.items():
            with self.subTest(campo=campo):
                respuesta = self.client.post(
                    self.url, datos_tecnica(**{campo: valor})
                )
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, mensaje)
                self.assertEqual(TecnicaQA.objects.count(), 8)

    def test_sin_pasos_no_se_guarda(self):
        respuesta = self.client.post(self.url, datos_tecnica(pasos=(
            ('', ''), ('', ''),
        )))
        self.assertContains(respuesta, 'Agrega al menos un paso a la técnica.')
        self.assertEqual(TecnicaQA.objects.count(), 8)

    def test_paso_sin_evidencia_esperada_se_rechaza(self):
        respuesta = self.client.post(self.url, datos_tecnica(pasos=(
            ('Revisar contraste', ''),
        )))
        self.assertContains(
            respuesta, 'Indica qué evidencia se espera de este paso.'
        )
        self.assertEqual(TecnicaQA.objects.count(), 8)

    def test_evidencia_sin_instruccion_se_rechaza(self):
        respuesta = self.client.post(self.url, datos_tecnica(pasos=(
            ('', 'Captura del verificador'),
        )))
        self.assertContains(respuesta, 'Indica qué hay que hacer en este paso.')
        self.assertEqual(TecnicaQA.objects.count(), 8)

    def test_filas_vacias_se_ignoran_y_se_numeran_seguidas(self):
        self.client.post(self.url, datos_tecnica(pasos=(
            ('Primero', 'Evidencia A'),
            ('', ''),
            ('Segundo', 'Evidencia B'),
            ('Tercero', 'Evidencia C'),
        )))
        tecnica = TecnicaQA.objects.get(nombre='Auditoría de accesibilidad')
        self.assertEqual(
            [(p.orden, p.instruccion) for p in tecnica.obtener_pasos()],
            [(1, 'Primero'), (2, 'Segundo'), (3, 'Tercero')],
        )

    def test_objetivo_y_pregunta_clave_son_opcionales(self):
        self.client.post(self.url, datos_tecnica())
        tecnica = TecnicaQA.objects.get(nombre='Auditoría de accesibilidad')
        respuesta = self.client.get(
            reverse('tecnicas:detalle', args=[tecnica.pk])
        )
        self.assertContains(respuesta, 'Sin definir', count=2)

    def test_nombre_repetido_se_rechaza_sin_importar_mayusculas(self):
        respuesta = self.client.post(
            self.url, datos_tecnica(nombre='  revisión   DE código ')
        )
        self.assertContains(respuesta, 'Ya existe una técnica con ese nombre.')
        self.assertEqual(TecnicaQA.objects.count(), 8)

    def test_espacios_de_mas_en_el_nombre_se_quitan(self):
        self.client.post(
            self.url, datos_tecnica(nombre='  Auditoría   de accesibilidad ')
        )
        self.assertTrue(
            TecnicaQA.objects.filter(nombre='Auditoría de accesibilidad').exists()
        )

    def test_dimension_o_tipo_inexistente_se_rechaza_en_espanol(self):
        casos = {
            'dimension': 'Elige una dimensión de la lista.',
            'tipo_control': 'Elige un tipo de control de la lista.',
        }
        for campo, mensaje in casos.items():
            with self.subTest(campo=campo):
                respuesta = self.client.post(
                    self.url, datos_tecnica(**{campo: 'INVENTADA'})
                )
                self.assertContains(respuesta, mensaje)
                self.assertNotContains(respuesta, 'Select a valid choice')
                self.assertEqual(TecnicaQA.objects.count(), 8)


class CatalogoTecnicaPropiaHU17Tests(TestCase):
    """CA3: aparece marcada como propia y se puede elegir en un proyecto."""

    def setUp(self):
        self.tecnica = crear_propia('Auditoría de accesibilidad')

    def test_catalogo_marca_solo_la_propia(self):
        respuesta = self.client.get(reverse('tecnicas:catalogo'))
        self.assertContains(respuesta, 'Auditoría de accesibilidad')
        self.assertContains(
            respuesta, '<span class="status blue">Propia</span>', count=1
        )
        self.assertContains(respuesta, f'href="{reverse("tecnicas:crear")}"')

    def test_las_ocho_tecnicas_base_no_son_propias(self):
        base = TecnicaQA.objects.filter(catalogo__nombre='Catálogo base')
        self.assertEqual(base.count(), 8)
        self.assertFalse(any(tecnica.es_propia() for tecnica in base))

    def test_filtro_por_dimension_incluye_la_propia(self):
        respuesta = self.client.get(
            reverse('tecnicas:catalogo'), {'dimension': 'DESARROLLO'}
        )
        self.assertIn(self.tecnica, respuesta.context['tecnicas'])

    def test_se_puede_elegir_en_un_proyecto(self):
        proyecto = crear_proyecto()
        sesion = self.client.session
        sesion[SESSION_KEY] = proyecto.pk
        sesion.save()

        self.client.post(
            reverse('tecnicas:catalogo'), {'tecnicas': [self.tecnica.pk]}
        )

        seguimiento = SeguimientoTecnica.objects.get(
            proyecto=proyecto, tecnica=self.tecnica, activa=True
        )
        self.assertEqual(seguimiento.pasos.count(), 2)
        respuesta = self.client.get(
            reverse('tecnicas:seguimiento'), {'proyecto': proyecto.pk}
        )
        self.assertContains(respuesta, 'Auditoría de accesibilidad')


class TecnicasBaseProtegidasHU17Tests(TestCase):
    """CA4: las técnicas base no se pueden editar ni borrar."""

    def setUp(self):
        self.base = TecnicaQA.objects.filter(catalogo__nombre='Catálogo base')

    def test_detalle_de_cada_base_no_ofrece_editar_ni_eliminar(self):
        for tecnica in self.base:
            with self.subTest(tecnica=tecnica.nombre):
                respuesta = self.client.get(
                    reverse('tecnicas:detalle', args=[tecnica.pk])
                )
                self.assertNotContains(
                    respuesta, reverse('tecnicas:editar', args=[tecnica.pk])
                )
                self.assertNotContains(
                    respuesta, reverse('tecnicas:eliminar', args=[tecnica.pk])
                )
                self.assertContains(
                    respuesta, 'Las técnicas base no se pueden editar ni borrar.'
                )

    def test_editar_base_por_url_se_rechaza(self):
        tecnica = self.base.first()
        url = reverse('tecnicas:editar', args=[tecnica.pk])
        detalle = reverse('tecnicas:detalle', args=[tecnica.pk])

        self.assertRedirects(self.client.get(url), detalle)
        respuesta = self.client.post(
            url, datos_tecnica(nombre='Cambiada'), follow=True
        )

        self.assertRedirects(respuesta, detalle)
        self.assertContains(
            respuesta, 'Las técnicas base no se pueden editar ni borrar.'
        )
        tecnica.refresh_from_db()
        self.assertNotEqual(tecnica.nombre, 'Cambiada')

    def test_edicion_invalida_de_una_base_se_rechaza_sin_mostrar_formulario(self):
        tecnica = self.base.first()
        respuesta = self.client.post(
            reverse('tecnicas:editar', args=[tecnica.pk]),
            datos_tecnica(nombre=''),
        )
        self.assertRedirects(
            respuesta, reverse('tecnicas:detalle', args=[tecnica.pk])
        )

    def test_el_servicio_tambien_protege_las_base(self):
        tecnica = self.base.first()
        nombre = tecnica.nombre
        tecnica.nombre = 'Cambiada desde el servicio'
        with self.assertRaisesMessage(
            ValidationError, 'Las técnicas base no se pueden editar ni borrar.'
        ):
            guardar_tecnica_propia(tecnica, [('Paso', 'Evidencia')])
        with self.assertRaises(ValidationError):
            eliminar_tecnica_propia(tecnica)
        tecnica.refresh_from_db()
        self.assertEqual(tecnica.nombre, nombre)
        self.assertEqual(self.base.count(), 8)

    def test_eliminar_base_por_url_se_rechaza(self):
        tecnica = self.base.first()
        pasos = tecnica.pasos.count()

        respuesta = self.client.post(
            reverse('tecnicas:eliminar', args=[tecnica.pk]), follow=True
        )

        self.assertContains(
            respuesta, 'Las técnicas base no se pueden editar ni borrar.'
        )
        self.assertEqual(self.base.count(), 8)
        self.assertEqual(tecnica.pasos.count(), pasos)

    def test_eliminar_por_get_no_esta_permitido(self):
        tecnica = crear_propia()
        respuesta = self.client.get(
            reverse('tecnicas:eliminar', args=[tecnica.pk])
        )
        self.assertEqual(respuesta.status_code, 405)
        self.assertTrue(TecnicaQA.objects.filter(pk=tecnica.pk).exists())

    def test_tecnica_inexistente_responde_404(self):
        for nombre in ('tecnicas:editar', 'tecnicas:eliminar'):
            with self.subTest(url=nombre):
                respuesta = self.client.post(reverse(nombre, args=[9999]))
                self.assertEqual(respuesta.status_code, 404)


class EditarEliminarPropiaHU17Tests(TestCase):
    """Una técnica propia se edita o borra mientras no tenga evidencias."""

    def setUp(self):
        self.tecnica = crear_propia('Auditoría de accesibilidad')
        self.url_editar = reverse('tecnicas:editar', args=[self.tecnica.pk])
        self.url_eliminar = reverse('tecnicas:eliminar', args=[self.tecnica.pk])

    def test_formulario_de_edicion_trae_los_pasos_actuales(self):
        respuesta = self.client.get(self.url_editar)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Paso 1')
        self.assertContains(respuesta, 'Evidencia 2')

    def test_editar_reemplaza_datos_y_pasos(self):
        respuesta = self.client.post(self.url_editar, datos_tecnica(
            nombre='Auditoría de accesibilidad',
            pasos=(('Nuevo paso', 'Nueva evidencia'),),
        ))
        self.assertRedirects(
            respuesta, reverse('tecnicas:detalle', args=[self.tecnica.pk])
        )
        self.tecnica.refresh_from_db()
        self.assertEqual(self.tecnica.dimension, 'DISENO')
        self.assertEqual(
            [(p.orden, p.instruccion) for p in self.tecnica.obtener_pasos()],
            [(1, 'Nuevo paso')],
        )

    def test_editar_actualiza_los_pasos_de_los_proyectos_que_la_siguen(self):
        proyecto = crear_proyecto()
        seguimiento = seguir_tecnica(proyecto, self.tecnica)

        self.client.post(self.url_editar, datos_tecnica(pasos=(
            ('A', 'Evidencia A'), ('B', 'Evidencia B'), ('C', 'Evidencia C'),
        )))

        self.assertEqual(
            [sp.paso.instruccion for sp in seguimiento.pasos.all()],
            ['A', 'B', 'C'],
        )
        seguimiento.refresh_from_db()
        self.assertEqual(seguimiento.porcentaje_avance, 0)

    def test_edicion_invalida_no_cambia_nada(self):
        self.client.post(self.url_editar, datos_tecnica(
            nombre='', pasos=(('', ''),)
        ))
        self.tecnica.refresh_from_db()
        self.assertEqual(self.tecnica.nombre, 'Auditoría de accesibilidad')
        self.assertEqual(self.tecnica.pasos.count(), 2)

    def test_eliminar_la_quita_del_catalogo_y_de_los_proyectos(self):
        proyecto = crear_proyecto()
        seguir_tecnica(proyecto, self.tecnica)

        respuesta = self.client.post(self.url_eliminar)

        self.assertRedirects(respuesta, reverse('tecnicas:catalogo'))
        self.assertFalse(TecnicaQA.objects.filter(pk=self.tecnica.pk).exists())
        self.assertFalse(proyecto.seguimientos_tecnicas.exists())
        self.assertEqual(TecnicaQA.objects.count(), 8)

    def test_con_evidencias_no_se_edita_ni_se_borra(self):
        proyecto = crear_proyecto('Portal Alumnos')
        seguimiento = seguir_tecnica(proyecto, self.tecnica)
        evidencia = registrar_evidencia(seguimiento, proyecto)
        aviso = 'La técnica ya tiene evidencias en: Portal Alumnos.'

        detalle = self.client.get(
            reverse('tecnicas:detalle', args=[self.tecnica.pk])
        )
        self.assertContains(detalle, aviso)
        self.assertNotContains(detalle, self.url_editar)

        editar = self.client.post(
            self.url_editar, datos_tecnica(nombre='Otra'), follow=True
        )
        borrar = self.client.post(self.url_eliminar, follow=True)

        # El aviso sale una sola vez: el mensaje reemplaza al texto fijo.
        self.assertContains(editar, aviso, count=1)
        self.assertContains(borrar, aviso, count=1)
        self.tecnica.refresh_from_db()
        self.assertEqual(self.tecnica.nombre, 'Auditoría de accesibilidad')
        self.assertTrue(Evidencia.objects.filter(pk=evidencia.pk).exists())
        self.assertEqual(SeguimientoPaso.objects.count(), 2)

    def test_el_servicio_tambien_protege_las_que_tienen_evidencias(self):
        proyecto = crear_proyecto()
        registrar_evidencia(seguir_tecnica(proyecto, self.tecnica), proyecto)
        with self.assertRaises(ValidationError):
            guardar_tecnica_propia(self.tecnica, [('Paso', 'Evidencia')])
        self.assertEqual(self.tecnica.pasos.count(), 2)

    def test_si_gana_evidencias_mientras_se_edita_no_se_guarda(self):
        proyecto = crear_proyecto('Portal Alumnos')
        registrar_evidencia(seguir_tecnica(proyecto, self.tecnica), proyecto)
        aviso = 'La técnica ya tiene evidencias en: Portal Alumnos.'

        # La vista la dio por modificable justo antes de que llegara la evidencia.
        with patch.object(TecnicaQA, 'puede_modificarse', return_value=True):
            respuesta = self.client.post(
                self.url_editar, datos_tecnica(nombre='Otra'), follow=True
            )

        self.assertContains(respuesta, aviso)
        self.tecnica.refresh_from_db()
        self.assertEqual(self.tecnica.nombre, 'Auditoría de accesibilidad')
        self.assertEqual(self.tecnica.pasos.count(), 2)

    def test_evidencia_en_un_seguimiento_inactivo_tambien_protege(self):
        proyecto = crear_proyecto()
        seguimiento = seguir_tecnica(proyecto, self.tecnica)
        registrar_evidencia(seguimiento, proyecto)
        seguimiento.desactivar()

        self.client.post(self.url_eliminar)

        self.assertTrue(TecnicaQA.objects.filter(pk=self.tecnica.pk).exists())

    def test_puede_conservar_su_propio_nombre(self):
        respuesta = self.client.post(self.url_editar, datos_tecnica(
            nombre='auditoría de accesibilidad'
        ))
        self.assertEqual(respuesta.status_code, 302)

    def test_nombre_con_html_se_muestra_como_texto(self):
        self.tecnica.nombre = '<script>alert(1)</script>'
        self.tecnica.save()
        for url in (
            reverse('tecnicas:catalogo'),
            reverse('tecnicas:detalle', args=[self.tecnica.pk]),
        ):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertNotContains(respuesta, '<script>alert(1)</script>')
