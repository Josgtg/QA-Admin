import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tecnicas', '0002_seguimientotecnica_activa'),
    ]

    operations = [
        migrations.AddField(
            model_name='proyecto',
            name='fecha_inicio',
            field=models.DateField(default=datetime.date(2026, 1, 1)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='proyecto',
            name='fecha_fin',
            field=models.DateField(default=datetime.date(2026, 12, 31)),
            preserve_default=False,
        ),
    ]
