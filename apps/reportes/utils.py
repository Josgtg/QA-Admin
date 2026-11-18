"""Utilidades de búsqueda de proyectos (HU-20)."""

import unicodedata


def normalizar_texto(texto):
    """Pasa a minúsculas y quita acentos para comparar nombres.

    ``normalizar_texto('Aplicación Móvil')`` devuelve ``'aplicacion movil'``.
    """
    if not texto:
        return ''
    descompuesto = unicodedata.normalize('NFKD', str(texto))
    sin_acentos = ''.join(
        caracter
        for caracter in descompuesto
        if not unicodedata.combining(caracter)
    )
    return sin_acentos.casefold().strip()


def coincide(nombre, termino):
    """True si el nombre contiene el término, sin mayúsculas ni acentos."""
    termino_normalizado = normalizar_texto(termino)
    if not termino_normalizado:
        return True
    return termino_normalizado in normalizar_texto(nombre)
