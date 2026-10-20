from django import forms
from django.core.exceptions import ValidationError

from apps.tecnicas.models import Proyecto


class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['nombre', 'fecha_inicio', 'fecha_fin']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'select-input'}),
            'fecha_inicio': forms.DateInput(
                attrs={'type': 'date', 'class': 'select-input'}
            ),
            'fecha_fin': forms.DateInput(
                attrs={'type': 'date', 'class': 'select-input'}
            ),
        }


class MiembroProyectoForm(forms.Form):
    persona_nombre = forms.CharField(
        max_length=150,
        label='Persona',
        required=False,
        widget=forms.TextInput(attrs={'class': 'select-input'}),
    )
    rol = forms.CharField(
        max_length=100,
        label='Rol',
        required=False,
        widget=forms.TextInput(attrs={'class': 'select-input'}),
    )

    def clean(self):
        cleaned = super().clean()
        nombre = (cleaned.get('persona_nombre') or '').strip()
        rol = (cleaned.get('rol') or '').strip()
        if nombre and not rol:
            self.add_error('rol', 'Indica el rol de la persona.')
        elif rol and not nombre:
            self.add_error('persona_nombre', 'Indica el nombre de la persona.')
        cleaned['persona_nombre'] = nombre
        cleaned['rol'] = rol
        return cleaned


class BaseMiembroProyectoFormSet(forms.BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        nombres = []
        for form in self.forms:
            nombre = form.cleaned_data.get('persona_nombre')
            if nombre:
                nombres.append(nombre.strip().lower())
        if len(nombres) != len(set(nombres)):
            raise ValidationError(
                'No puede repetirse la misma persona en el mismo proyecto.'
            )


MiembroProyectoFormSet = forms.formset_factory(
    MiembroProyectoForm,
    formset=BaseMiembroProyectoFormSet,
    extra=1,
)
