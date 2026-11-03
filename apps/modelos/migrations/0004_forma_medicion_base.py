"""Completa ``forma_medicion`` de las métricas sembradas (HU-09).

El catálogo de HU-09 debe mostrar, además de nombre, descripción, unidad y
rango, **cómo se mide** cada métrica. Las métricas del seed nacieron antes de
que existiera el campo, así que aquí se rellenan por nombre.

Las métricas creadas por el encargado después de esta migración no se tocan:
``forma_medicion`` es opcional y la pantalla muestra "Sin definir" si falta.
"""

from django.db import migrations

FORMAS_DE_MEDICION = {
    'Requisitos implementados correctamente': (
        '% de requisitos que pasan sus pruebas sobre el total de requisitos '
        'del proyecto.'
    ),
    'Defectos críticos abiertos': (
        'Conteo de defectos de severidad crítica sin corregir al cierre del '
        'periodo, según el registro de incidencias.'
    ),
    'Tiempo de respuesta': (
        'Mediana del tiempo entre la petición y la respuesta en las pruebas '
        'de carga del proyecto.'
    ),
    'Funciones documentadas': (
        '% de funciones públicas con documentación sobre el total de '
        'funciones del código fuente.'
    ),
    'Complejidad ciclomática máxima': (
        'Complejidad ciclomática del método más complejo, medida con una '
        'herramienta de análisis estático.'
    ),
    'Criterios de aceptación cumplidos': (
        '% de criterios de aceptación verificados sobre el total de '
        'criterios comprometidos en el alcance.'
    ),
    'Satisfacción de usuarios': (
        'Promedio de la encuesta de satisfacción aplicada a los usuarios '
        'piloto, en una escala de 1 a 5.'
    ),
    'Disponibilidad': (
        '% del tiempo que el servicio estuvo disponible sobre el tiempo '
        'total del periodo observado.'
    ),
    'Pruebas aprobadas': (
        '% de casos de prueba aprobados sobre el total de casos ejecutados '
        'en la última corrida.'
    ),
    'Errores con mensaje claro': (
        '% de errores mostrados al usuario con un mensaje comprensible sobre '
        'el total de errores revisados.'
    ),
    'Vulnerabilidades abiertas': (
        'Conteo de vulnerabilidades de severidad alta o crítica sin mitigar, '
        'según el último análisis de seguridad.'
    ),
    'Tiempo medio de corrección': (
        'Promedio de horas entre el reporte de un defecto y su corrección, '
        'sobre los defectos cerrados del periodo.'
    ),
    'Cumplimiento del estándar de código': (
        '% de archivos revisados que respetan la guía de estilo del proyecto, '
        'según la revisión de código.'
    ),
    'Tareas completadas sin ayuda': (
        '% de tareas que el usuario termina sin asistencia sobre el total de '
        'tareas evaluadas en las pruebas de usabilidad.'
    ),
    'Navegadores soportados': (
        '% de navegadores objetivo en los que la aplicación funciona sin '
        'errores, según la matriz de compatibilidad.'
    ),
}


def completar_formas_de_medicion(apps, schema_editor):
    """Rellena ``forma_medicion`` en las métricas del seed que la tienen vacía.

    Solo afecta a las métricas cuyo ``nombre`` está en
    ``FORMAS_DE_MEDICION`` y cuya ``forma_medicion`` sigue en blanco, así que
    no sobrescribe textos ya escritos por el encargado.
    """
    Metrica = apps.get_model('modelos', 'Metrica')
    for nombre, forma in FORMAS_DE_MEDICION.items():
        Metrica.objects.filter(nombre=nombre, forma_medicion='').update(
            forma_medicion=forma
        )


def revertir(apps, schema_editor):
    """Vacía ``forma_medicion`` de las métricas que completó esta migración."""
    Metrica = apps.get_model('modelos', 'Metrica')
    Metrica.objects.filter(
        nombre__in=FORMAS_DE_MEDICION.keys(),
        forma_medicion__in=FORMAS_DE_MEDICION.values(),
    ).update(forma_medicion='')


class Migration(migrations.Migration):

    dependencies = [
        ('modelos', '0003_metrica_forma_medicion'),
    ]

    operations = [
        migrations.RunPython(
            completar_formas_de_medicion,
            revertir,
        ),
    ]
