from django import forms
from django.utils import timezone

from apps.reportes.models import MiembroProyecto

from .models import Evidencia
from .validators import (
    EXTENSIONES_PERMITIDAS,
    FORMATOS_ACEPTADOS,
    TAMANO_MAXIMO_MB,
)


class EvidenciaForm(forms.ModelForm):
    """Evidencia de un paso: enlace o archivo, fecha, autor y comentario."""

    comentario = forms.CharField(
        required=False,
        label='Comentario',
        widget=forms.Textarea(
            attrs={'class': 'select-input', 'rows': 3}
        ),
    )

    class Meta:
        model = Evidencia
        fields = ['enlace', 'archivo', 'fecha', 'miembro_proyecto']
        labels = {
            'enlace': 'Enlace de la evidencia',
            'archivo': 'Archivo de la evidencia',
            'fecha': 'Fecha de la evidencia',
            'miembro_proyecto': 'Persona que registra',
        }
        widgets = {
            'fecha': forms.DateInput(
                attrs={'type': 'date', 'class': 'select-input'},
                format='%Y-%m-%d',
            ),
            'archivo': forms.ClearableFileInput(
                attrs={
                    'class': 'select-input',
                    'accept': ','.join(EXTENSIONES_PERMITIDAS),
                }
            ),
        }

    def __init__(self, *args, proyecto=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.proyecto = proyecto
        equipos = MiembroProyecto.objects.none()
        if proyecto is not None:
            equipos = proyecto.equipo_activo()
        self.fields['miembro_proyecto'].queryset = equipos
        self.fields['miembro_proyecto'].required = True
        self.fields['enlace'].required = False
        self.fields['archivo'].required = False
        self.fields['fecha'].required = False
        self.fields['fecha'].initial = timezone.localdate()
        self.fields['archivo'].help_text = (
            f'Formatos aceptados: {FORMATOS_ACEPTADOS}. '
            f'Tamaño máximo: {TAMANO_MAXIMO_MB} MB.'
        )
        self.fields['enlace'].widget.attrs['class'] = 'select-input'
        self.fields['miembro_proyecto'].widget.attrs['class'] = (
            'select-input'
        )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('enlace') and not cleaned.get('archivo'):
            self.add_error(
                'enlace',
                'Adjunta un enlace o un archivo como evidencia.',
            )
        if not cleaned.get('fecha'):
            cleaned['fecha'] = timezone.localdate()
        return cleaned
