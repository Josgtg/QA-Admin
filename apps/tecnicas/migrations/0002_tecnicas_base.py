"""Seed del catálogo base de técnicas QA (HU-04).

Incluye las dos técnicas ya redactadas y **seis con contenido placeholder**
marcado ``[PENDIENTE]`` hasta que llegue el texto definitivo (deuda H4-1-1,
§7.4 del plan de refactorización). Con ellas el catálogo cumple el CA1 de HU-04:
8 técnicas, dos por dimensión, con al menos un paso cada una.
"""

from django.db import migrations

CATALOGO = {
    'nombre': 'Catálogo base',
    'descripcion': 'Técnicas de QA del catálogo base del proyecto.',
}

TECNICAS = [
    {
        'nombre': 'Revisión de código',
        'descripcion': (
            'Revisión sistemática de los cambios de código para detectar '
            'defectos, incumplimientos del estándar y posibles regresiones.'
        ),
        'objetivo': (
            'Verificar que el código es comprensible, sigue las reglas del '
            'equipo y funciona sin romper funcionalidad existente.'
        ),
        'pregunta_clave': (
            '¿El código es limpio, sigue las reglas y funciona sin romper '
            'nada?'
        ),
        'dimension': 'DESARROLLO',
        'tipo_control': 'VERIFICACION',
        'pasos': [
            (
                'Revisar que el código cumpla el estándar de codificación '
                'del equipo.',
                'Checklist de revisión o enlace al pull request.',
            ),
            (
                'Ejecutar las pruebas automatizadas y confirmar que no hay '
                'regresiones.',
                'Reporte de pruebas o salida de la suite.',
            ),
            (
                'Revisar legibilidad, duplicación y manejo de errores en '
                'los cambios.',
                'Comentarios de revisión o enlace al commit corregido.',
            ),
        ],
    },
    {
        'nombre': 'Revisión de requisitos',
        'descripcion': (
            'Validación de los requisitos del proyecto para confirmar que '
            'son claros, completos y verificables.'
        ),
        'objetivo': (
            'Asegurar que cada requisito tiene criterios de aceptación y '
            'que cubre las necesidades del proyecto.'
        ),
        'pregunta_clave': (
            '¿Los requisitos cubren lo que el proyecto necesita y se pueden '
            'verificar?'
        ),
        'dimension': 'ESPECIFICACION',
        'tipo_control': 'VALIDACION',
        'pasos': [
            (
                'Verificar que cada requisito tenga criterios de aceptación '
                'claros y verificables.',
                'Documento de requisitos con criterios resaltados.',
            ),
            (
                'Confirmar con el encargado que los requisitos cubren las '
                'necesidades del proyecto.',
                'Acta, correo o comentario de validación.',
            ),
        ],
    },
]

# Contenido provisional (deuda H4-1-1): (dimensión visible, valor).
PLACEHOLDERS = [
    ('Especificación', 'ESPECIFICACION'),
    ('Diseño (1)', 'DISENO'),
    ('Diseño (2)', 'DISENO'),
    ('Desarrollo', 'DESARROLLO'),
    ('Conformidad (1)', 'CONFORMIDAD'),
    ('Conformidad (2)', 'CONFORMIDAD'),
]


def crear_tecnicas_base(apps, schema_editor):
    CatalogoTQA = apps.get_model('tecnicas', 'CatalogoTQA')
    TecnicaQA = apps.get_model('tecnicas', 'TecnicaQA')
    Paso = apps.get_model('tecnicas', 'Paso')

    catalogo, _ = CatalogoTQA.objects.get_or_create(
        nombre=CATALOGO['nombre'],
        defaults={'descripcion': CATALOGO['descripcion']},
    )

    for datos in TECNICAS:
        tecnica, _ = TecnicaQA.objects.get_or_create(
            nombre=datos['nombre'],
            defaults={
                'descripcion': datos['descripcion'],
                'objetivo': datos['objetivo'],
                'pregunta_clave': datos['pregunta_clave'],
                'dimension': datos['dimension'],
                'tipo_control': datos['tipo_control'],
                'catalogo': catalogo,
            },
        )
        for orden, (instruccion, evidencia) in enumerate(
            datos['pasos'],
            start=1,
        ):
            Paso.objects.get_or_create(
                tecnica=tecnica,
                orden=orden,
                defaults={
                    'instruccion': instruccion,
                    'evidencia_esperada': evidencia,
                },
            )

    for etiqueta, dimension in PLACEHOLDERS:
        tecnica, _ = TecnicaQA.objects.get_or_create(
            nombre=f'Técnica por definir · {etiqueta}',
            defaults={
                'descripcion': '[PENDIENTE] Contenido por definir.',
                'objetivo': '[PENDIENTE] Contenido por definir.',
                'pregunta_clave': '[PENDIENTE] Contenido por definir.',
                'dimension': dimension,
                'tipo_control': 'VERIFICACION',
                'catalogo': catalogo,
            },
        )
        Paso.objects.get_or_create(
            tecnica=tecnica,
            orden=1,
            defaults={
                'instruccion': (
                    '[PENDIENTE] Definir los pasos de esta técnica.'
                ),
                'evidencia_esperada': (
                    '[PENDIENTE] Definir la evidencia esperada.'
                ),
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('tecnicas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            crear_tecnicas_base,
            migrations.RunPython.noop,
        ),
    ]
