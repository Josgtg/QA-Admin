from django import forms

from apps.reportes.models import MiembroProyecto

from .models import Evidencia


class EvidenciaForm(forms.ModelForm):
    """Evidencia de un paso: enlace o archivo, más el autor (HU-10)."""

    comentario = forms.CharField(
        required=False,
        label='Comentario',
        widget=forms.Textarea(
            attrs={'class': 'select-input', 'rows': 3}
        ),
    )

    class Meta:
        model = Evidencia
        fields = ['enlace', 'archivo', 'miembro_proyecto']
        labels = {
            'enlace': 'Enlace de la evidencia',
            'archivo': 'Archivo de la evidencia',
            'miembro_proyecto': 'Persona que registra',
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
