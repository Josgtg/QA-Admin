import shutil
import tempfile
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.reportes.models import MiembroProyecto, Persona, Proyecto

from .models import (
    CatalogoTQA,
    Dimension,
    Evidencia,
    SeguimientoPaso,
    SeguimientoTecnica,
    TecnicaQA,
)
from .selection import SESSION_KEY
from .services import seguir_tecnica
from .validators import TAMANO_MAXIMO_BYTES


def crear_proyecto(nombre='Proyecto de prueba'):
    hoy = timezone.localdate()
    return Proyecto.objects.create(
        nombre=nombre,
        fecha_inicio=hoy - timedelta(days=5),
        fecha_fin=hoy + timedelta(days=5),
    )


def crear_miembro(proyecto, nombre='Ana'):
    persona, _ = Persona.objects.get_or_create(nombre=nombre)
    return MiembroProyecto.objects.create(
        proyecto=proyecto,
        persona=persona,
        rol='QA',
    )


def crear_tecnica(nombre='Técnica de prueba', dimension='DESARROLLO'):
    return TecnicaQA.objects.create(
        nombre=nombre,
        descripcion='Descripción',
        objetivo='Objetivo',
        pregunta_clave='¿Pregunta?',
        dimension=dimension,
        tipo_control='VERIFICACION',
    )


class TecnicasBaseTests(TestCase):
    """Catálogo base tras el reset de migraciones (HU-04)."""

    def test_catalogo_base_tiene_ocho_tecnicas(self):
        catalogo = CatalogoTQA.objects.get(nombre='Catálogo base')

        self.assertEqual(catalogo.tecnicas.count(), 8)

    def test_dos_tecnicas_por_dimension(self):
        for dimension, _ in Dimension.choices:
            self.assertEqual(
                TecnicaQA.objects.filter(dimension=dimension).count(),
                2,
                dimension,
            )

    def test_todas_las_tecnicas_tienen_pasos(self):
        for tecnica in TecnicaQA.objects.all():
            self.assertGreater(tecnica.pasos.count(), 0, tecnica.nombre)

    def test_tecnicas_base_tienen_contenido_definitivo(self):
        """Cada técnica base tiene instrucciones y evidencia esperada completas."""
        for tecnica in TecnicaQA.objects.all():
            with self.subTest(tecnica=tecnica.nombre):
                for texto in (
                    tecnica.nombre, tecnica.descripcion, tecnica.objetivo,
                    tecnica.pregunta_clave,
                ):
                    self.assertTrue(texto.strip())
                    self.assertNotIn('[PENDIENTE]', texto)
                for paso in tecnica.obtener_pasos():
                    self.assertTrue(paso.evidencia_esperada.strip())
                    self.assertNotIn('[PENDIENTE]', paso.instruccion)
                    self.assertNotIn('[PENDIENTE]', paso.evidencia_esperada)


class CatalogoTecnicasViewTests(TestCase):
    def setUp(self):
        self.url = reverse('tecnicas:catalogo')

    def test_catalogo_muestra_las_ocho_tecnicas(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['tecnicas']), 8)

    def test_filtra_por_dimension(self):
        respuesta = self.client.get(self.url, {'dimension': 'DISENO'})

        tecnicas = list(respuesta.context['tecnicas'])
        self.assertEqual(len(tecnicas), 2)
        self.assertTrue(
            all(tecnica.dimension == 'DISENO' for tecnica in tecnicas)
        )

    def test_dimension_sin_tecnicas_muestra_estado_vacio(self):
        TecnicaQA.objects.filter(dimension='CONFORMIDAD').delete()

        respuesta = self.client.get(self.url, {'dimension': 'CONFORMIDAD'})

        self.assertContains(respuesta, 'No hay técnicas en esta dimensión')

    def test_sin_proyectos_queda_en_modo_consulta(self):
        respuesta = self.client.get(self.url)

        self.assertTrue(respuesta.context['sin_proyecto'])
        self.assertContains(respuesta, 'No hay proyectos registrados')

    def test_muestra_etiqueta_por_definir(self):
        tecnica = crear_tecnica()
        tecnica.descripcion = '[PENDIENTE] Contenido propio sin completar.'
        tecnica.save()
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Por definir')


class DetalleTecnicaViewTests(TestCase):
    def test_detalle_muestra_pasos_ordenados(self):
        tecnica = TecnicaQA.objects.get(nombre='Revisión de código')

        respuesta = self.client.get(
            reverse('tecnicas:detalle', args=[tecnica.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Objetivo')
        self.assertContains(respuesta, 'Pregunta clave')
        self.assertEqual(
            [paso.orden for paso in respuesta.context['pasos']],
            [1, 2, 3],
        )

    def test_tecnica_inexistente_404(self):
        respuesta = self.client.get(
            reverse('tecnicas:detalle', args=[9999])
        )

        self.assertEqual(respuesta.status_code, 404)


class SeguirTecnicaViewTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto()
        self.tecnica = crear_tecnica()
        self.url = reverse('tecnicas:seguimiento')

    def test_post_guarda_la_tecnica_con_proyecto_id(self):
        respuesta = self.client.post(
            self.url,
            {
                'proyecto_id': self.proyecto.pk,
                'tecnicas': [self.tecnica.pk],
            },
        )

        self.assertRedirects(
            respuesta,
            f'{self.url}?proyecto={self.proyecto.pk}',
        )
        self.assertTrue(
            SeguimientoTecnica.objects.filter(
                proyecto=self.proyecto,
                tecnica=self.tecnica,
                activa=True,
            ).exists()
        )

    def test_post_acepta_el_campo_proyecto(self):
        respuesta = self.client.post(
            self.url,
            {
                'proyecto': self.proyecto.pk,
                'tecnicas': [self.tecnica.pk],
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            SeguimientoTecnica.objects.filter(
                proyecto=self.proyecto,
                tecnica=self.tecnica,
            ).exists()
        )

    def test_post_sin_proyecto_devuelve_400(self):
        respuesta = self.client.post(
            self.url,
            {'tecnicas': [self.tecnica.pk]},
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_get_sin_parametro_usa_el_proyecto_de_la_sesion(self):
        otro = crear_proyecto('Otro proyecto')
        sesion = self.client.session
        sesion[SESSION_KEY] = otro.pk
        sesion.save()

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.context['proyecto'], otro)

    def test_get_con_parametro_guarda_el_proyecto_en_la_sesion(self):
        self.client.get(self.url, {'proyecto': self.proyecto.pk})

        self.assertEqual(
            self.client.session[SESSION_KEY], self.proyecto.pk
        )

    def test_post_guarda_el_proyecto_en_la_sesion(self):
        self.client.post(
            self.url,
            {
                'proyecto_id': self.proyecto.pk,
                'tecnicas': [self.tecnica.pk],
            },
        )

        self.assertEqual(
            self.client.session[SESSION_KEY], self.proyecto.pk
        )

    def test_quitar_tecnica_la_desactiva_y_conserva_pasos(self):
        self.tecnica.pasos.create(orden=1, instruccion='Hacer algo')
        seguimiento = seguir_tecnica(self.proyecto, self.tecnica)

        self.client.post(
            self.url,
            {'proyecto_id': self.proyecto.pk, 'quitar': seguimiento.pk},
        )

        seguimiento.refresh_from_db()
        self.assertFalse(seguimiento.activa)
        self.assertGreater(seguimiento.pasos.count(), 0)


class SeguirTecnicaServiceTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto()
        self.tecnica = crear_tecnica()

    def test_crea_un_seguimiento_paso_por_paso(self):
        self.tecnica.pasos.create(orden=1, instruccion='a')
        self.tecnica.pasos.create(orden=2, instruccion='b')

        seguimiento = seguir_tecnica(self.proyecto, self.tecnica)

        self.assertEqual(seguimiento.pasos.count(), 2)

    def test_no_duplica_pasos_ni_seguimientos(self):
        self.tecnica.pasos.create(orden=1, instruccion='a')

        seguir_tecnica(self.proyecto, self.tecnica)
        seguir_tecnica(self.proyecto, self.tecnica)

        self.assertEqual(
            SeguimientoTecnica.objects.filter(
                proyecto=self.proyecto,
                tecnica=self.tecnica,
            ).count(),
            1,
        )
        self.assertEqual(
            SeguimientoPaso.objects.filter(
                seguimiento__proyecto=self.proyecto
            ).count(),
            1,
        )


class RegistrarEvidenciaTests(TestCase):
    def setUp(self):
        self.proyecto = crear_proyecto()
        self.miembro = crear_miembro(self.proyecto)
        self.tecnica = crear_tecnica()
        self.tecnica.pasos.create(
            orden=1,
            instruccion='Hacer algo',
            evidencia_esperada='Enlace o archivo',
        )
        self.seguimiento = seguir_tecnica(self.proyecto, self.tecnica)
        self.paso = self.seguimiento.pasos.first()
        self.url = reverse(
            'tecnicas:registrar_evidencia', args=[self.paso.pk]
        )

    def test_get_muestra_el_formulario(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Registrar evidencia del paso')

    def test_paso_no_se_completa_sin_evidencia(self):
        with self.assertRaises(ValidationError):
            self.paso.marcar_completado()

    def test_registrar_evidencia_completa_el_paso(self):
        respuesta = self.client.post(
            self.url,
            {
                'enlace': 'https://ejemplo.test/evidencia',
                'comentario': 'Listo',
                'miembro_proyecto': self.miembro.pk,
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.paso.refresh_from_db()
        self.assertTrue(self.paso.completado)
        self.assertIsNotNone(self.paso.fecha_completado)
        self.assertEqual(self.paso.comentario, 'Listo')
        self.assertTrue(Evidencia.objects.filter(seguimiento_paso=self.paso).exists())

    def test_registrar_sin_evidencia_no_completa(self):
        respuesta = self.client.post(
            self.url,
            {'miembro_proyecto': self.miembro.pk},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.paso.refresh_from_db()
        self.assertFalse(self.paso.completado)

    def test_autor_de_otro_proyecto_se_rechaza(self):
        ajeno = crear_miembro(crear_proyecto('Otro'), 'Luis')

        respuesta = self.client.post(
            self.url,
            {
                'enlace': 'https://ejemplo.test/evidencia',
                'miembro_proyecto': ajeno.pk,
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.paso.refresh_from_db()
        self.assertFalse(self.paso.completado)

    def test_reemplaza_la_evidencia_anterior(self):
        self.client.post(
            self.url,
            {
                'enlace': 'https://ejemplo.test/uno',
                'miembro_proyecto': self.miembro.pk,
            },
        )
        self.client.post(
            self.url,
            {
                'enlace': 'https://ejemplo.test/dos',
                'miembro_proyecto': self.miembro.pk,
            },
        )

        self.assertEqual(
            Evidencia.objects.filter(seguimiento_paso=self.paso).count(),
            1,
        )
        self.assertEqual(
            Evidencia.objects.get(seguimiento_paso=self.paso).enlace,
            'https://ejemplo.test/dos',
        )

    def test_avance_se_recalcula(self):
        self.client.post(
            self.url,
            {
                'enlace': 'https://ejemplo.test/evidencia',
                'miembro_proyecto': self.miembro.pk,
            },
        )

        self.seguimiento.refresh_from_db()
        self.assertEqual(self.seguimiento.porcentaje_avance, 100.0)


class CatalogoSeleccionTests(TestCase):
    """Selección de técnicas desde el catálogo (H4-4=b)."""

    def setUp(self):
        self.proyecto = crear_proyecto()
        crear_miembro(self.proyecto)
        self.url = reverse('tecnicas:catalogo')
        self.tecnica = TecnicaQA.objects.get(nombre='Revisión de código')
        sesion = self.client.session
        sesion[SESSION_KEY] = self.proyecto.pk
        sesion.save()

    def test_post_selecciona_tecnicas_del_proyecto_en_sesion(self):
        respuesta = self.client.post(
            self.url,
            {'tecnicas': [self.tecnica.pk]},
        )

        self.assertRedirects(respuesta, self.url)
        self.assertTrue(
            SeguimientoTecnica.objects.filter(
                proyecto=self.proyecto,
                tecnica=self.tecnica,
                activa=True,
            ).exists()
        )

    def test_post_desmarcar_desactiva(self):
        self.client.post(self.url, {'tecnicas': [self.tecnica.pk]})

        self.client.post(self.url, {})

        self.assertFalse(
            SeguimientoTecnica.objects.get(
                proyecto=self.proyecto,
                tecnica=self.tecnica,
            ).activa
        )

    def test_post_sin_proyectos_no_crea_nada(self):
        Proyecto.objects.all().delete()

        respuesta = self.client.post(
            self.url,
            {'tecnicas': [self.tecnica.pk]},
        )

        self.assertRedirects(respuesta, self.url)
        self.assertFalse(SeguimientoTecnica.objects.exists())


MEDIA_TEMPORAL = tempfile.mkdtemp(prefix='qa-admin-evidencias-')


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class EvidenciaArchivoTests(TestCase):
    """Archivo, fecha y apertura de la evidencia (HU-10)."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)

    def setUp(self):
        self.proyecto = crear_proyecto()
        self.miembro = crear_miembro(self.proyecto)
        self.tecnica = crear_tecnica()
        self.tecnica.pasos.create(
            orden=1,
            instruccion='Revisar el estándar',
            evidencia_esperada='Archivo o enlace',
        )
        self.seguimiento = seguir_tecnica(self.proyecto, self.tecnica)
        self.paso = self.seguimiento.pasos.first()
        self.url = reverse(
            'tecnicas:registrar_evidencia', args=[self.paso.pk]
        )

    def _datos(self, **extra):
        datos = {
            'miembro_proyecto': self.miembro.pk,
            'fecha': timezone.localdate().isoformat(),
            'comentario': 'Con comentario',
        }
        datos.update(extra)
        return datos

    def test_guarda_la_fecha_declarada(self):
        fecha = timezone.localdate() - timedelta(days=2)

        self.client.post(
            self.url,
            self._datos(
                enlace='https://ejemplo.test/evidencia',
                fecha=fecha.isoformat(),
            ),
        )

        self.assertEqual(Evidencia.objects.get().fecha, fecha)

    def test_sin_fecha_usa_la_de_hoy(self):
        self.client.post(
            self.url,
            {
                'miembro_proyecto': self.miembro.pk,
                'enlace': 'https://ejemplo.test/evidencia',
            },
        )

        self.assertEqual(Evidencia.objects.get().fecha, timezone.localdate())

    def test_rechaza_un_formato_no_permitido(self):
        archivo = SimpleUploadedFile(
            'evidencia.exe',
            b'contenido',
            content_type='application/octet-stream',
        )

        respuesta = self.client.post(self.url, self._datos(archivo=archivo))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Formato no permitido')
        self.assertContains(respuesta, 'PDF')
        self.assertFalse(Evidencia.objects.exists())

    def test_rechaza_un_archivo_demasiado_grande(self):
        archivo = SimpleUploadedFile(
            'reporte.pdf',
            b'x' * (TAMANO_MAXIMO_BYTES + 1),
            content_type='application/pdf',
        )

        respuesta = self.client.post(self.url, self._datos(archivo=archivo))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'tamaño máximo')
        self.assertFalse(Evidencia.objects.exists())

    def test_archivo_valido_se_guarda_y_se_abre(self):
        archivo = SimpleUploadedFile(
            'evidencia.png',
            b'\x89PNG\r\n\x1a\n',
            content_type='image/png',
        )

        respuesta = self.client.post(self.url, self._datos(archivo=archivo))

        self.assertEqual(respuesta.status_code, 302)
        evidencia = Evidencia.objects.get()
        self.assertTrue(evidencia.archivo)

        apertura = self.client.get(
            reverse('tecnicas:abrir_evidencia', args=[evidencia.pk])
        )
        self.assertEqual(apertura.status_code, 200)
        self.assertEqual(
            b''.join(apertura.streaming_content),
            b'\x89PNG\r\n\x1a\n',
        )

    def test_el_enlace_se_abre_redirigiendo(self):
        self.client.post(
            self.url,
            self._datos(enlace='https://ejemplo.test/evidencia'),
        )
        evidencia = Evidencia.objects.get()

        respuesta = self.client.get(
            reverse('tecnicas:abrir_evidencia', args=[evidencia.pk])
        )

        self.assertRedirects(
            respuesta,
            'https://ejemplo.test/evidencia',
            fetch_redirect_response=False,
        )

    def test_abrir_evidencia_inexistente_da_404(self):
        respuesta = self.client.get(
            reverse('tecnicas:abrir_evidencia', args=[999999])
        )

        self.assertEqual(respuesta.status_code, 404)
