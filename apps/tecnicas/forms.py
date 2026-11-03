from django import forms
from django.utils import timezone

from .models import Evidencia
from .validators import (
    EXTENSIONES_PERMITIDAS,
    FORMATOS_ACEPTADOS,
    TAMANO_MAXIMO_MB,
)


class EvidenciaForm(forms.ModelForm):
    """Datos que pide HU-10 para registrar la evidencia de un paso."""

    class Meta:
        model = Evidencia
        fields = ['enlace', 'archivo', 'fecha', 'comentario', 'autor']
        labels = {
            'enlace': 'Enlace',
            'archivo': 'Archivo',
            'fecha': 'Fecha de la evidencia',
            'comentario': 'Comentario (opcional)',
            'autor': 'Autor',
        }
        widgets = {
            'enlace': forms.URLInput(
                attrs={
                    'class': 'select-input',
                    'placeholder': 'https://...',
                }
            ),
            'archivo': forms.ClearableFileInput(
                attrs={
                    'class': 'file-input',
                    'accept': ','.join(EXTENSIONES_PERMITIDAS),
                }
            ),
            'fecha': forms.DateInput(
                attrs={'type': 'date', 'class': 'select-input'},
                format='%Y-%m-%d',
            ),
            'comentario': forms.Textarea(
                attrs={
                    'class': 'select-input textarea-input',
                    'rows': 3,
                    'placeholder': 'Notas sobre la evidencia (opcional)',
                }
            ),
            'autor': forms.TextInput(
                attrs={
                    'class': 'select-input',
                    'list': 'autores-proyecto',
                    'placeholder': 'Nombre de quien registra',
                }
            ),
        }
        error_messages = {
            'enlace': {
                'invalid': 'Escribe un enlace válido (https://...).',
            },
            'fecha': {
                'required': 'Indica la fecha de la evidencia.',
                'invalid': 'Introduce una fecha válida.',
            },
            'autor': {
                'required': 'Indica quién registra la evidencia.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].initial = timezone.localdate()
        self.fields['archivo'].help_text = (
            f'Formatos aceptados: {FORMATOS_ACEPTADOS}. '
            f'Tamaño máximo: {TAMANO_MAXIMO_MB} MB.'
        )

    def clean(self):
        """Exige un enlace o un archivo y normaliza el enlace escrito."""
        cleaned = super().clean()
        enlace = (cleaned.get('enlace') or '').strip()
        archivo = cleaned.get('archivo')
        if not enlace and not archivo:
            raise forms.ValidationError(
                'Registra un enlace o adjunta un archivo como evidencia.'
            )
        cleaned['enlace'] = enlace
        return cleaned
