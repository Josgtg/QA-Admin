from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    CatalogoTQA,
    Proyecto,
    SeguimientoTecnica,
    TecnicaQA,
)


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
