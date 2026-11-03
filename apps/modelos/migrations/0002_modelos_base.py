"""Seed de los 4 modelos de calidad predefinidos (HU-03).

Escrito directamente sobre el esquema final: ``Caracteristica`` es un catálogo
global (una sola fila por nombre), la meta vive en ``ModeloMetrica`` y el rango
admisible en ``Metrica.valor_min``/``valor_max`` (que se dejan en ``NULL``,
H3-1).

Sustituye a la migración incremental que convertía ``Metrica.meta``.
"""

from django.db import migrations

CATALOGO_CARACTERISTICAS = {
    'Corrección': 'El software hace lo que piden los requisitos.',
    'Fiabilidad': (
        'El software funciona de forma fiable y disponible cuando se necesita.'
    ),
    'Usabilidad': 'El software es fácil de usar y de aprender.',
    'Mantenibilidad': 'El código se corrige y mantiene con poco esfuerzo.',
    'Portabilidad': 'El software funciona en distintos entornos.',
    'Eficiencia': 'El software aprovecha bien los recursos.',
    'Comprensibilidad': 'El código se entiende con facilidad.',
    'Modificabilidad': 'El código se cambia con facilidad.',
    'Funcionalidad': 'El software cubre lo que se pidió.',
    'Rendimiento': 'El software responde rápido.',
    'Soporte': 'El software se corrige y mantiene con facilidad.',
    'Adecuación funcional': 'El software cumple los requisitos.',
    'Seguridad': 'El software protege los datos.',
}

# (nombre, descripción, [(característica, métrica, descripción, unidad,
#                          umbral, tipo_umbral)])
MODELOS_BASE = [
    (
        'McCall',
        'Modelo de 1977 que agrupa la calidad en operación, revisión y '
        'transición del producto.',
        [
            (
                'Corrección',
                'Requisitos implementados correctamente',
                'Requisitos que pasan sus pruebas entre requisitos totales.',
                '%',
                90,
                'MINIMO',
            ),
            (
                'Fiabilidad',
                'Defectos críticos abiertos',
                'Defectos críticos sin corregir al cierre del periodo.',
                'defectos',
                0,
                'MAXIMO',
            ),
            (
                'Usabilidad',
                'Tareas completadas sin ayuda',
                'Tareas que el usuario termina sin ayuda entre tareas '
                'probadas.',
                '%',
                80,
                'MINIMO',
            ),
            (
                'Mantenibilidad',
                'Tiempo medio de corrección',
                'Horas promedio desde que se reporta un defecto hasta que '
                'se corrige.',
                'horas',
                24,
                'MAXIMO',
            ),
        ],
    ),
    (
        'Boehm',
        'Modelo de 1978 que mide la utilidad del producto, su '
        'mantenibilidad y su portabilidad.',
        [
            (
                'Portabilidad',
                'Navegadores soportados',
                'Navegadores donde la aplicación funciona entre navegadores '
                'probados.',
                '%',
                100,
                'MINIMO',
            ),
            (
                'Eficiencia',
                'Tiempo de respuesta',
                'Segundos promedio que tarda una pantalla en cargar.',
                'segundos',
                2,
                'MAXIMO',
            ),
            (
                'Comprensibilidad',
                'Funciones documentadas',
                'Funciones con docstring entre funciones públicas.',
                '%',
                90,
                'MINIMO',
            ),
            (
                'Modificabilidad',
                'Complejidad ciclomática máxima',
                'Complejidad más alta encontrada en una función.',
                'puntos',
                10,
                'MAXIMO',
            ),
        ],
    ),
    (
        'FURPS',
        'Modelo de Hewlett-Packard: funcionalidad, usabilidad, fiabilidad, '
        'rendimiento y soporte.',
        [
            (
                'Funcionalidad',
                'Criterios de aceptación cumplidos',
                'Criterios que pasan entre criterios de las HU.',
                '%',
                100,
                'MINIMO',
            ),
            (
                'Usabilidad',
                'Satisfacción de usuarios',
                'Calificación promedio de una encuesta del 1 al 5.',
                'puntos',
                4,
                'MINIMO',
            ),
            (
                'Fiabilidad',
                'Disponibilidad',
                'Tiempo en funcionamiento entre tiempo total.',
                '%',
                99,
                'MINIMO',
            ),
            (
                'Rendimiento',
                'Tiempo de respuesta',
                'Segundos promedio que tarda una pantalla en cargar.',
                'segundos',
                2,
                'MAXIMO',
            ),
            (
                'Soporte',
                'Tiempo medio de corrección',
                'Horas promedio desde que se reporta un defecto hasta que '
                'se corrige.',
                'horas',
                48,
                'MAXIMO',
            ),
        ],
    ),
    (
        'ISO/IEC 25010',
        'Estándar internacional que define las características de calidad '
        'de un producto de software.',
        [
            (
                'Adecuación funcional',
                'Criterios de aceptación cumplidos',
                'Criterios que pasan entre criterios de las HU.',
                '%',
                100,
                'MINIMO',
            ),
            (
                'Fiabilidad',
                'Pruebas aprobadas',
                'Pruebas que pasan entre pruebas realizadas.',
                '%',
                100,
                'MINIMO',
            ),
            (
                'Mantenibilidad',
                'Cumplimiento del estándar de código',
                'Ítems que cumplen entre ítems del checklist de revisión de '
                'código.',
                '%',
                100,
                'MINIMO',
            ),
            (
                'Usabilidad',
                'Errores con mensaje claro',
                'Datos inválidos con mensaje entre datos inválidos probados.',
                '%',
                100,
                'MINIMO',
            ),
            (
                'Seguridad',
                'Vulnerabilidades abiertas',
                'Vulnerabilidades sin corregir al cierre del periodo.',
                'vulnerabilidades',
                0,
                'MAXIMO',
            ),
        ],
    ),
]


def crear_modelos_base(apps, schema_editor):
    ModeloCalidad = apps.get_model('modelos', 'ModeloCalidad')
    Caracteristica = apps.get_model('modelos', 'Caracteristica')
    Metrica = apps.get_model('modelos', 'Metrica')
    ModeloMetrica = apps.get_model('modelos', 'ModeloMetrica')

    caracteristicas = {}
    for nombre, descripcion in CATALOGO_CARACTERISTICAS.items():
        caracteristica, _ = Caracteristica.objects.get_or_create(
            nombre=nombre,
            defaults={'descripcion': descripcion},
        )
        caracteristicas[nombre] = caracteristica

    for nombre_modelo, descripcion, filas in MODELOS_BASE:
        modelo, _ = ModeloCalidad.objects.get_or_create(
            nombre=nombre_modelo,
            defaults={'descripcion': descripcion, 'predefinido': True},
        )
        for (
            nombre_caracteristica,
            nombre_metrica,
            descripcion_metrica,
            unidad,
            umbral,
            tipo_umbral,
        ) in filas:
            caracteristica = caracteristicas[nombre_caracteristica]
            metrica, _ = Metrica.objects.get_or_create(
                caracteristica=caracteristica,
                nombre=nombre_metrica,
                defaults={
                    'descripcion': descripcion_metrica,
                    'unidad': unidad,
                },
            )
            ModeloMetrica.objects.get_or_create(
                modelo_calidad=modelo,
                metrica=metrica,
                defaults={
                    'umbral': umbral,
                    'tipo_umbral': tipo_umbral,
                    'activa': True,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ('modelos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            crear_modelos_base,
            migrations.RunPython.noop,
        ),
    ]
