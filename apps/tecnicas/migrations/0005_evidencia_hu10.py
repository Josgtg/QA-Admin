import apps.tecnicas.models
import apps.tecnicas.validators
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tecnicas', '0004_tecnicas_ejemplo'),
    ]

    operations = [
        migrations.RenameField(
            model_name='evidencia',
            old_name='url_archivo',
            new_name='enlace',
        ),
        migrations.AlterField(
            model_name='evidencia',
            name='enlace',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='evidencia',
            name='archivo',
            field=models.FileField(
                blank=True,
                max_length=255,
                upload_to=apps.tecnicas.models.ruta_evidencia,
                validators=[
                    apps.tecnicas.validators.validar_extension_evidencia,
                    apps.tecnicas.validators.validar_tamano_evidencia,
                ],
            ),
        ),
        migrations.AddField(
            model_name='evidencia',
            name='fecha',
            field=models.DateField(
                default=django.utils.timezone.localdate,
                verbose_name='fecha de la evidencia',
            ),
        ),
        migrations.AddField(
            model_name='evidencia',
            name='comentario',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='evidencia',
            name='tipo',
            field=models.CharField(
                blank=True,
                choices=[
                    ('VERIFICACION', 'Verificación'),
                    ('VALIDACION', 'Validación'),
                ],
                max_length=20,
            ),
        ),
    ]
