from django import forms

from apps.reportes.models import MiembroProyecto

from .models import RevisionMetrica


class RevisionMetricaForm(forms.ModelForm):
    """Registro de una revisión de métrica con su evidencia (HU-01)."""

    class Meta:
        model = RevisionMetrica
        fields = ['valor', 'fecha', 'enlace', 'archivo', 'miembro_proyecto']
        labels = {
            'valor': 'Valor medido',
            'fecha': 'Fecha de la medición',
            'enlace': 'Enlace de la evidencia',
            'archivo': 'Archivo de la evidencia',
            'miembro_proyecto': 'Persona que registra',
        }
        widgets = {
            'valor': forms.NumberInput(
                attrs={'class': 'select-input', 'step': 'any'}
            ),
            'fecha': forms.DateInput(
                attrs={'type': 'date', 'class': 'select-input'},
                format='%Y-%m-%d',
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
        self.fields['enlace'].widget.attrs['class'] = 'select-input'
        self.fields['archivo'].widget.attrs['class'] = 'select-input'
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
        return cleaned
