"""Datos de demostración para probar las funciones de la aplicación.

Uso::

    python manage.py seed_demo
    python manage.py seed_demo --reset

El comando es idempotente: si los proyectos demo ya existen no hace nada,
salvo que se indique ``--reset``, que borra únicamente esos proyectos y los
vuelve a crear. El resto de datos de la base no se toca.
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.modelos.models import ModeloCalidad, RevisionMetrica, TipoUmbral
from apps.reportes.models import Persona, Proyecto
from apps.tecnicas.models import Evidencia, TecnicaQA
from apps.tecnicas.services import seguir_tecnica

PREFIJO_DEMO = 'Demo QA · '

# (nombre, rol con el que participa en los proyectos)
PERSONAS = (
    ('Ana Torres', 'Líder de calidad'),
    ('Luis Gómez', 'Desarrollador'),
    ('María Ruiz', 'Analista de QA'),
)

# Cada proyecto muestra un estado distinto de la aplicación:
# - activo y saludable, con todo medido y evidenciado,
# - activo y a medias, con métricas que fallan y pasos pendientes,
# - futuro, con modelo aplicado pero sin datos todavía,
# - terminado, para probar el filtro por periodo.
PROYECTOS = (
    {
        'nombre': 'Demo QA · Tienda en línea',
        'inicio': date(2026, 10, 1),
        'fin': date(2026, 12, 15),
        'modelo': 'ISO/IEC 25010',
        'tecnicas': (
            'Revisión de requisitos',
            'Revisión de diseño',
            'Pruebas funcionales',
            'Revisión de conformidad',
        ),
        'equipo': (0, 1, 2),
        'pasos': 'todos',
        'revisiones': 'todas_cumplen',
        'fecha_evidencia': date(2026, 11, 10),
        'fecha_revision': date(2026, 11, 12),
    },
    {
        'nombre': 'Demo QA · App móvil',
        'inicio': date(2026, 11, 1),
        'fin': date(2027, 2, 28),
        'modelo': 'FURPS',
        'tecnicas': (
            'Validación de criterios de aceptación',
            'Revisión de código',
            'Revisión de evidencias QA',
        ),
        'equipo': (0, 1, 2),
        'pasos': 'uno',
        'revisiones': 'parcial',
        'fecha_evidencia': date(2026, 11, 15),
        'fecha_revision': date(2026, 11, 16),
    },
    {
        'nombre': 'Demo QA · Migración ERP',
        'inicio': date(2027, 3, 1),
        'fin': date(2027, 9, 30),
        'modelo': 'McCall',
        'tecnicas': (),
        'equipo': (0, 1),
        'pasos': 'ninguno',
        'revisiones': 'ninguna',
    },
    {
        'nombre': 'Demo QA · Auditoría 2026',
        'inicio': date(2026, 1, 15),
        'fin': date(2026, 6, 30),
        'modelo': 'Boehm',
        'tecnicas': (
            'Revisión de trazabilidad',
            'Revisión de evidencias QA',
        ),
        'equipo': (0, 2),
        'pasos': 'todos',
        'revisiones': 'todas_cumplen',
        'fecha_evidencia': date(2026, 5, 20),
        'fecha_revision': date(2026, 5, 25),
    },
)


class Command(BaseCommand):
    help = (
        'Crea proyectos de demostración con modelo, métricas, técnicas y '
        'evidencias para probar la aplicación.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help=(
                'Borra los proyectos que empiezan por "Demo QA · " y los '
                'vuelve a crear.'
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        existentes = Proyecto.objects.filter(nombre__startswith=PREFIJO_DEMO)

        if existentes.exists() and not options['reset']:
            self.stdout.write(
                self.style.WARNING(
                    f'Ya existen {existentes.count()} proyectos demo. '
                    'Usa --reset para recrearlos.'
                )
            )
            return

        if options['reset'] and existentes.exists():
            cantidad = existentes.count()
            existentes.delete()
            self.stdout.write(
                f'Proyectos demo eliminados: {cantidad}.'
            )

        personas = self._crear_personas()
        self.stdout.write('Creando proyectos de demostración...')

        for datos in PROYECTOS:
            proyecto = self._crear_proyecto(datos, personas)
            self.stdout.write(
                self.style.SUCCESS(
                    f'  · {proyecto.nombre} (id {proyecto.pk})'
                )
            )

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('Datos demo listos. Abre:')
        )
        for proyecto in Proyecto.objects.filter(
            nombre__startswith=PREFIJO_DEMO
        ):
            self.stdout.write(
                f'  /proyectos/{proyecto.pk}/  {proyecto.nombre}'
            )
        self.stdout.write('')
        self.stdout.write(
            'Inicia el servidor con: python manage.py runserver'
        )

    def _crear_personas(self):
        """Devuelve las personas demo y su rol, sin duplicarlas."""
        personas = []
        for nombre, rol in PERSONAS:
            persona, _ = Persona.objects.get_or_create(nombre=nombre)
            personas.append((persona, rol))
        return personas

    def _crear_proyecto(self, datos, personas):
        proyecto = Proyecto(
            nombre=datos['nombre'],
            fecha_inicio=datos['inicio'],
            fecha_fin=datos['fin'],
        )
        proyecto.full_clean()
        proyecto.save()

        for indice in datos['equipo']:
            persona, rol = personas[indice]
            proyecto.agregar_miembro(persona, rol)

        modelo = ModeloCalidad.objects.get(nombre=datos['modelo'])
        aplicado = proyecto.aplicar_modelo(modelo)

        for tecnica in TecnicaQA.objects.filter(
            nombre__in=datos['tecnicas']
        ):
            seguir_tecnica(proyecto, tecnica)

        self._registrar_evidencias(proyecto, datos)
        self._registrar_revisiones(proyecto, aplicado, datos)
        return proyecto

    def _registrar_evidencias(self, proyecto, datos):
        """Completa pasos con una evidencia, según el escenario pedido."""
        if datos['pasos'] == 'ninguno':
            return

        autor = proyecto.equipo_activo().first()
        for seguimiento in proyecto.seguimientos_activos():
            pasos = seguimiento.pasos.select_related('paso').order_by(
                'paso__orden'
            )
            if datos['pasos'] == 'uno':
                pasos = pasos[:1]

            for paso in pasos:
                Evidencia.objects.create(
                    seguimiento_paso=paso,
                    miembro_proyecto=autor,
                    enlace=(
                        f'https://ejemplo.test/proyecto-{proyecto.pk}/'
                        f'paso-{paso.pk}'
                    ),
                    fecha=datos['fecha_evidencia'],
                )
                paso.marcar_completado(
                    comentario='Evidencia revisada durante la demo.'
                )

    def _registrar_revisiones(self, proyecto, aplicado, datos):
        """Mide las métricas del modelo aplicado según el escenario pedido."""
        criterio = datos['revisiones']
        if criterio == 'ninguna':
            return

        autor = proyecto.equipo_activo().first()
        instantaneas = list(
            aplicado.metricas_aplicadas().filter(activa=True)
        )

        for indice, instantanea in enumerate(instantaneas):
            if criterio == 'parcial':
                # La última métrica queda sin medir y la penúltima falla.
                if indice == len(instantaneas) - 1:
                    continue
                cumple = indice < len(instantaneas) - 2
            else:
                cumple = True

            valor = self._valor_para(instantanea, cumple)
            revision = RevisionMetrica(
                metrica_aplicada=instantanea,
                miembro_proyecto=autor,
                valor=valor,
                fecha=datos['fecha_revision'],
                enlace=(
                    f'https://ejemplo.test/proyecto-{proyecto.pk}/'
                    f'metrica-{instantanea.metrica_id}'
                ),
                cumple=instantanea.evaluar_cumplimiento(valor),
            )
            revision.full_clean()
            revision.save()

    def _valor_para(self, instantanea, cumple):
        """Valor dentro del rango que cumple o incumple el umbral."""
        metrica = instantanea.metrica
        umbral = instantanea.umbral
        delta = self._delta(metrica, umbral)

        if instantanea.tipo_umbral == TipoUmbral.MINIMO:
            valor = umbral + delta if cumple else umbral - delta
        else:
            valor = umbral - delta if cumple else umbral + delta

        if metrica.valor_min is not None:
            valor = max(valor, metrica.valor_min)
        if metrica.valor_max is not None:
            valor = min(valor, metrica.valor_max)
        return round(valor, 1)

    def _delta(self, metrica, umbral):
        """Separación respecto al umbral, ajustada al rango de la métrica."""
        if metrica.valor_min is not None and metrica.valor_max is not None:
            return max((metrica.valor_max - metrica.valor_min) * 0.05, 0.1)
        return max(abs(umbral) * 0.1, 1.0)
