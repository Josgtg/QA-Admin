from django.db import migrations

CATALOGO = {
    'nombre': 'Catálogo base',
    'descripcion': 'Técnicas de QA de ejemplo para iniciar el seguimiento.',
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
            '¿El código es limpio, sigue las reglas y funciona sin romper nada?'
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


def crear_tecnicas_ejemplo(apps, schema_editor):
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


def borrar_tecnicas_ejemplo(apps, schema_editor):
    CatalogoTQA = apps.get_model('tecnicas', 'CatalogoTQA')
    TecnicaQA = apps.get_model('tecnicas', 'TecnicaQA')

    TecnicaQA.objects.filter(
        nombre__in=[tecnica['nombre'] for tecnica in TECNICAS]
    ).delete()
    CatalogoTQA.objects.filter(
        nombre=CATALOGO['nombre'],
        tecnicas__isnull=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tecnicas', '0003_proyecto_fechas'),
    ]

    operations = [
        migrations.RunPython(
            crear_tecnicas_ejemplo,
            borrar_tecnicas_ejemplo,
        ),
    ]
