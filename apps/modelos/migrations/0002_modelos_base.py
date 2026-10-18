from django.db import migrations

MODELOS_BASE = [
    (
        'McCall',
        'Modelo de 1977 que agrupa la calidad en operación, revisión y '
        'transición del producto.',
        [
            ('Corrección', 'El software hace lo que piden los requisitos.', [
                ('Requisitos implementados correctamente',
                 'Requisitos que pasan sus pruebas entre requisitos totales.',
                 '%', 90, 'MINIMO'),
            ]),
            ('Fiabilidad', 'El software funciona sin fallar.', [
                ('Defectos críticos abiertos',
                 'Defectos críticos sin corregir al cierre del periodo.',
                 'defectos', 0, 'MAXIMO'),
            ]),
            ('Usabilidad', 'El software es fácil de aprender y usar.', [
                ('Tareas completadas sin ayuda',
                 'Tareas que el usuario termina sin ayuda entre tareas '
                 'probadas.',
                 '%', 80, 'MINIMO'),
            ]),
            ('Mantenibilidad', 'Los defectos se corrigen con poco esfuerzo.', [
                ('Tiempo medio de corrección',
                 'Horas promedio desde que se reporta un defecto hasta que '
                 'se corrige.',
                 'horas', 24, 'MAXIMO'),
            ]),
        ],
    ),
    (
        'Boehm',
        'Modelo de 1978 que mide la utilidad del producto, su '
        'mantenibilidad y su portabilidad.',
        [
            ('Portabilidad', 'El software funciona en distintos entornos.', [
                ('Navegadores soportados',
                 'Navegadores donde la aplicación funciona entre navegadores '
                 'probados.',
                 '%', 100, 'MINIMO'),
            ]),
            ('Eficiencia', 'El software responde rápido.', [
                ('Tiempo de respuesta',
                 'Segundos promedio que tarda una pantalla en cargar.',
                 'segundos', 2, 'MAXIMO'),
            ]),
            ('Comprensibilidad', 'El código se entiende con facilidad.', [
                ('Funciones documentadas',
                 'Funciones con docstring entre funciones públicas.',
                 '%', 90, 'MINIMO'),
            ]),
            ('Modificabilidad', 'El código se cambia con facilidad.', [
                ('Complejidad ciclomática máxima',
                 'Complejidad más alta encontrada en una función.',
                 'puntos', 10, 'MAXIMO'),
            ]),
        ],
    ),
    (
        'FURPS',
        'Modelo de Hewlett-Packard: funcionalidad, usabilidad, fiabilidad, '
        'rendimiento y soporte.',
        [
            ('Funcionalidad', 'El software cubre lo que se pidió.', [
                ('Criterios de aceptación cumplidos',
                 'Criterios que pasan entre criterios de las HU.',
                 '%', 100, 'MINIMO'),
            ]),
            ('Usabilidad', 'Los usuarios están conformes con el uso.', [
                ('Satisfacción de usuarios',
                 'Calificación promedio de una encuesta del 1 al 5.',
                 'puntos', 4, 'MINIMO'),
            ]),
            ('Fiabilidad', 'El software está disponible cuando se necesita.', [
                ('Disponibilidad',
                 'Tiempo en funcionamiento entre tiempo total.',
                 '%', 99, 'MINIMO'),
            ]),
            ('Rendimiento', 'El software responde rápido.', [
                ('Tiempo de respuesta',
                 'Segundos promedio que tarda una pantalla en cargar.',
                 'segundos', 2, 'MAXIMO'),
            ]),
            ('Soporte', 'El software se corrige y mantiene con facilidad.', [
                ('Tiempo medio de corrección',
                 'Horas promedio desde que se reporta un defecto hasta que '
                 'se corrige.',
                 'horas', 48, 'MAXIMO'),
            ]),
        ],
    ),
    (
        'ISO/IEC 25010',
        'Estándar internacional que define las características de calidad '
        'de un producto de software.',
        [
            ('Adecuación funcional', 'El software cumple los requisitos.', [
                ('Criterios de aceptación cumplidos',
                 'Criterios que pasan entre criterios de las HU.',
                 '%', 100, 'MINIMO'),
            ]),
            ('Fiabilidad', 'El software funciona sin errores.', [
                ('Pruebas aprobadas',
                 'Pruebas que pasan entre pruebas realizadas.',
                 '%', 100, 'MINIMO'),
            ]),
            ('Mantenibilidad', 'El código sigue el estándar del equipo.', [
                ('Cumplimiento del estándar de código',
                 'Ítems que cumplen entre ítems del checklist de revisión de '
                 'código.',
                 '%', 100, 'MINIMO'),
            ]),
            ('Usabilidad', 'El usuario entiende qué corregir.', [
                ('Errores con mensaje claro',
                 'Datos inválidos con mensaje entre datos inválidos probados.',
                 '%', 100, 'MINIMO'),
            ]),
            ('Seguridad', 'El software protege los datos.', [
                ('Vulnerabilidades abiertas',
                 'Vulnerabilidades sin corregir al cierre del periodo.',
                 'vulnerabilidades', 0, 'MAXIMO'),
            ]),
        ],
    ),
]


def crear_modelos_base(apps, schema_editor):
    ModeloCalidad = apps.get_model('modelos', 'ModeloCalidad')
    Caracteristica = apps.get_model('modelos', 'Caracteristica')
    Metrica = apps.get_model('modelos', 'Metrica')

    for nombre, descripcion, caracteristicas in MODELOS_BASE:
        modelo = ModeloCalidad.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            predefinido=True,
        )
        for nombre_car, descripcion_car, metricas in caracteristicas:
            caracteristica = Caracteristica.objects.create(
                modelo=modelo,
                nombre=nombre_car,
                descripcion=descripcion_car,
            )
            for nombre_met, descripcion_met, unidad, meta, tipo in metricas:
                Metrica.objects.create(
                    caracteristica=caracteristica,
                    nombre=nombre_met,
                    descripcion=descripcion_met,
                    unidad=unidad,
                    meta=meta,
                    tipo_umbral=tipo,
                )


def borrar_modelos_base(apps, schema_editor):
    ModeloCalidad = apps.get_model('modelos', 'ModeloCalidad')
    nombres = [nombre for nombre, _, _ in MODELOS_BASE]
    ModeloCalidad.objects.filter(nombre__in=nombres, predefinido=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('modelos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_modelos_base, borrar_modelos_base),
    ]
