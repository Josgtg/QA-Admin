import shutil
import tempfile
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    CatalogoTQA,
    Evidencia,
    Paso,
    Proyecto,
    SeguimientoTecnica,
    TecnicaQA,
)
from .selection import SESSION_KEY
from .validators import TAMANO_MAXIMO_BYTES, TAMANO_MAXIMO_MB

MEDIA_TEMPORAL = tempfile.mkdtemp(prefix='qa-admin-evidencias-')


class TecnicasEjemploTests(TestCase):
    def test_catalogo_base_tiene_las_tecnicas_de_ejemplo(self):
        catalogo = CatalogoTQA.objects.get(nombre='Catálogo base')

        self.assertEqual(
            set(catalogo.tecnicas.values_list('nombre', flat=True)),
            {'Revisión de código', 'Revisión de requisitos'},
        )

    def test_tecnicas_de_ejemplo_tienen_pasos(self):
        tecnicas = TecnicaQA.objects.filter(
            nombre__in=['Revisión de código', 'Revisión de requisitos']
        )

        self.assertEqual(tecnicas.count(), 2)
        for tecnica in tecnicas:
            self.assertGreater(tecnica.pasos.count(), 0)


class SeguirTecnicaViewTests(TestCase):
    def setUp(self):
        hoy = timezone.localdate()
        self.proyecto = Proyecto.objects.create(
            nombre='Proyecto de prueba',
            fecha_inicio=hoy - timedelta(days=5),
            fecha_fin=hoy + timedelta(days=5),
        )
        self.tecnica = TecnicaQA.objects.create(
            nombre='Técnica de prueba',
            descripcion='Descripción',
            objetivo='Objetivo',
            pregunta_clave='¿Pregunta?',
            dimension='DESARROLLO',
            tipo_control='VERIFICACION',
        )
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
        hoy = timezone.localdate()
        otro = Proyecto.objects.create(
            nombre='Otro proyecto',
            fecha_inicio=hoy - timedelta(days=5),
            fecha_fin=hoy + timedelta(days=5),
        )
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


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class RegistrarEvidenciaViewTests(TestCase):
    """Criterios de aceptación de HU-10."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)

    def setUp(self):
        hoy = timezone.localdate()
        self.proyecto = Proyecto.objects.create(
            nombre='Proyecto con evidencias',
            fecha_inicio=hoy - timedelta(days=5),
            fecha_fin=hoy + timedelta(days=5),
        )
        self.tecnica = TecnicaQA.objects.create(
            nombre='Revisión de código',
            descripcion='Descripción',
            objetivo='Objetivo',
            pregunta_clave='¿El código es limpio?',
            dimension='DESARROLLO',
            tipo_control='VERIFICACION',
        )
        self.paso_uno = Paso.objects.create(
            tecnica=self.tecnica,
            orden=1,
            instruccion='Revisar que el código cumpla el estándar.',
            evidencia_esperada='Checklist de revisión.',
        )
        self.paso_dos = Paso.objects.create(
            tecnica=self.tecnica,
            orden=2,
            instruccion='Ejecutar las pruebas automatizadas.',
            evidencia_esperada='Reporte de pruebas.',
        )
        self.seguimiento = self.proyecto.seguir_tecnica(self.tecnica)
        self.paso_seguimiento = self.seguimiento.pasos.get(paso=self.paso_uno)
        self.url = reverse('tecnicas:pasos', args=[self.seguimiento.pk])

    def _datos(self, **extra):
        datos = {
            'paso_id': self.paso_seguimiento.pk,
            'enlace': 'https://ejemplo.com/checklist',
            'fecha': timezone.localdate().isoformat(),
            'comentario': 'Se adjunta la checklist del pull request.',
            'autor': 'Ana Delgado',
        }
        datos.update(extra)
        return datos

    def test_get_muestra_los_pasos_y_el_formulario(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Revisión de código')
        self.assertContains(respuesta, 'Checklist de revisión.')
        self.assertContains(respuesta, 'Registrar evidencia')
        self.assertEqual(respuesta.context['total_pasos'], 2)
        self.assertEqual(respuesta.context['completados'], 0)

    def test_no_completa_el_paso_sin_enlace_ni_archivo(self):
        respuesta = self.client.post(self.url, self._datos(enlace=''))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            'Registra un enlace o adjunta un archivo como evidencia',
        )
        self.paso_seguimiento.refresh_from_db()
        self.assertFalse(self.paso_seguimiento.completado)
        self.assertFalse(Evidencia.objects.exists())

    def test_registra_evidencia_con_enlace_y_completa_el_paso(self):
        respuesta = self.client.post(self.url, self._datos())

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            respuesta['Location'],
            f'{self.url}#paso-{self.paso_seguimiento.pk}',
        )

        evidencia = Evidencia.objects.get()
        self.assertEqual(evidencia.enlace, 'https://ejemplo.com/checklist')
        self.assertEqual(evidencia.fecha, timezone.localdate())
        self.assertEqual(evidencia.autor, 'Ana Delgado')
        self.assertEqual(
            evidencia.comentario,
            'Se adjunta la checklist del pull request.',
        )
        self.assertEqual(evidencia.tipo, 'VERIFICACION')

        self.paso_seguimiento.refresh_from_db()
        self.assertTrue(self.paso_seguimiento.completado)
        self.assertIsNotNone(self.paso_seguimiento.fecha_completado)
        self.assertEqual(self.paso_seguimiento.autor, 'Ana Delgado')

        self.seguimiento.refresh_from_db()
        self.assertEqual(self.seguimiento.porcentaje_avance, 50.0)

    def test_rechaza_un_formato_no_permitido(self):
        archivo = SimpleUploadedFile(
            'evidencia.exe',
            b'contenido no permitido',
            content_type='application/octet-stream',
        )

        respuesta = self.client.post(
            self.url,
            self._datos(enlace='', archivo=archivo),
        )

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

        respuesta = self.client.post(
            self.url,
            self._datos(enlace='', archivo=archivo),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'supera el tamaño máximo')
        self.assertContains(respuesta, str(TAMANO_MAXIMO_MB))
        self.assertFalse(Evidencia.objects.exists())

    def test_archivo_valido_se_guarda_y_se_puede_abrir(self):
        archivo = SimpleUploadedFile(
            'evidencia.png',
            b'\x89PNG\r\n\x1a\n',
            content_type='image/png',
        )

        respuesta = self.client.post(
            self.url,
            self._datos(enlace='', archivo=archivo),
        )

        self.assertEqual(respuesta.status_code, 302)
        evidencia = Evidencia.objects.get()
        self.assertTrue(evidencia.es_archivo())
        self.assertTrue(
            evidencia.archivo.name.startswith('evidencias/paso_')
        )
        self.assertTrue(evidencia.tiene_contenido())

        apertura = self.client.get(
            reverse('tecnicas:abrir_evidencia', args=[evidencia.pk])
        )
        self.assertEqual(apertura.status_code, 200)
        self.assertEqual(
            b''.join(apertura.streaming_content),
            b'\x89PNG\r\n\x1a\n',
        )

    def test_la_evidencia_con_enlace_se_abre_redirigiendo(self):
        self.client.post(self.url, self._datos())
        evidencia = Evidencia.objects.get()

        respuesta = self.client.get(
            reverse('tecnicas:abrir_evidencia', args=[evidencia.pk])
        )

        self.assertRedirects(
            respuesta,
            'https://ejemplo.com/checklist',
            fetch_redirect_response=False,
        )

    def test_no_permite_evidencia_de_un_paso_de_otro_proyecto(self):
        hoy = timezone.localdate()
        otro_proyecto = Proyecto.objects.create(
            nombre='Otro proyecto',
            fecha_inicio=hoy - timedelta(days=5),
            fecha_fin=hoy + timedelta(days=5),
        )
        otro_seguimiento = otro_proyecto.seguir_tecnica(self.tecnica)
        otro_paso = otro_seguimiento.pasos.first()

        respuesta = self.client.post(
            self.url,
            self._datos(paso_id=otro_paso.pk),
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(Evidencia.objects.exists())

    def test_avisa_cuando_el_paso_ya_esta_completado(self):
        self.client.post(self.url, self._datos())

        respuesta = self.client.post(self.url, self._datos())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ya está completado')
        self.assertEqual(Evidencia.objects.count(), 1)

    def test_queda_registrada_la_fecha_de_la_evidencia(self):
        fecha = timezone.localdate() - timedelta(days=2)

        self.client.post(self.url, self._datos(fecha=fecha.isoformat()))

        self.assertEqual(Evidencia.objects.get().fecha, fecha)


class MarcarCompletadoTests(TestCase):
    """La regla 'sin evidencia no hay paso completado' vive en el modelo."""

    def setUp(self):
        hoy = timezone.localdate()
        self.proyecto = Proyecto.objects.create(
            nombre='Proyecto sin evidencias',
            fecha_inicio=hoy - timedelta(days=5),
            fecha_fin=hoy + timedelta(days=5),
        )
        self.tecnica = TecnicaQA.objects.create(
            nombre='Técnica de prueba',
            descripcion='Descripción',
            objetivo='Objetivo',
            pregunta_clave='¿Pregunta?',
            dimension='DESARROLLO',
            tipo_control='VERIFICACION',
        )
        Paso.objects.create(
            tecnica=self.tecnica,
            orden=1,
            instruccion='Revisar.',
        )
        self.seguimiento = self.proyecto.seguir_tecnica(self.tecnica)
        self.paso_seguimiento = self.seguimiento.pasos.first()

    def test_no_marca_completado_sin_evidencia(self):
        with self.assertRaises(ValidationError):
            self.paso_seguimiento.marcar_completado('Ana Delgado')

        self.paso_seguimiento.refresh_from_db()
        self.assertFalse(self.paso_seguimiento.completado)

    def test_no_registra_una_evidencia_sin_contenido(self):
        with self.assertRaises(ValidationError):
            self.paso_seguimiento.registrar_evidencia(
                enlace='',
                archivo=None,
                autor='Ana Delgado',
            )

        self.assertFalse(Evidencia.objects.exists())
        self.paso_seguimiento.refresh_from_db()
        self.assertFalse(self.paso_seguimiento.completado)
