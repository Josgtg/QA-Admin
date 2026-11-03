"""Reglas de validación de los archivos de evidencia (HU-10).

Se mantienen en un módulo propio para que el modelo, el formulario y las
pruebas compartan los mismos límites y el mismo mensaje de error.
"""

import os

from django.core.exceptions import ValidationError

EXTENSIONES_PERMITIDAS = (
    '.pdf',
    '.png',
    '.jpg',
    '.jpeg',
    '.docx',
    '.xlsx',
    '.txt',
)

FORMATOS_ACEPTADOS = 'PDF, PNG, JPG, DOCX, XLSX y TXT'
TAMANO_MAXIMO_MB = 5
TAMANO_MAXIMO_BYTES = TAMANO_MAXIMO_MB * 1024 * 1024

MENSAJE_FORMATO = (
    'Formato no permitido (%(formato)s). Se aceptan: %(aceptados)s.'
)
MENSAJE_TAMANO = (
    'El archivo supera el tamaño máximo permitido de %(maximo)s MB.'
)


def validar_extension_evidencia(archivo):
    """Rechaza archivos cuya extensión no esté en la lista permitida."""
    extension = os.path.splitext(archivo.name)[1].lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ValidationError(
            MENSAJE_FORMATO,
            code='formato_no_permitido',
            params={
                'formato': extension or 'sin extensión',
                'aceptados': FORMATOS_ACEPTADOS,
            },
        )


def validar_tamano_evidencia(archivo):
    """Rechaza archivos que superen el tamaño máximo configurado."""
    if archivo.size > TAMANO_MAXIMO_BYTES:
        raise ValidationError(
            MENSAJE_TAMANO,
            code='tamano_no_permitido',
            params={'maximo': TAMANO_MAXIMO_MB},
        )
