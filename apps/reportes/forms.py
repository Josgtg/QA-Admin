from django import forms
from django.core.exceptions import ValidationError

from .models import Proyecto


class RangoFechasForm(forms.Form):
    """Rango opcional de fechas para la gráfica de salud (HU-14)."""

    desde = forms.DateField(
        required=False,
        error_messages={'invalid': 'La fecha inicial no es válida.'},
        widget=forms.DateInput(
            attrs={'type': 'date', 'class': 'select-input'},
            format='%Y-%m-%d',
        ),
    )
    hasta = forms.DateField(
        required=False,
        error_messages={'invalid': 'La fecha final no es válida.'},
        widget=forms.DateInput(
            attrs={'type': 'date', 'class': 'select-input'},
            format='%Y-%m-%d',
        ),
    )

    def clean(self):
        datos = super().clean()
        desde = datos.get('desde')
        hasta = datos.get('hasta')
        if desde and hasta and hasta < desde:
            self.add_error(
                'hasta',
                'La fecha final no puede ser anterior a la inicial.',
            )
        return datos


class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['nombre', 'fecha_inicio', 'fecha_fin']
        labels = {
            'nombre': 'Nombre del proyecto',
            'fecha_inicio': 'Fecha de inicio',
            'fecha_fin': 'Fecha de fin',
        }
        error_messages = {
            'nombre': {
                'required': 'Escribe el nombre del proyecto.',
            },
            'fecha_inicio': {
                'required': 'Indica la fecha de inicio.',
                'invalid': 'Introduce una fecha válida.',
            },
            'fecha_fin': {
                'required': 'Indica la fecha de fin.',
                'invalid': 'Introduce una fecha válida.',
            },
        }
        widgets = {
            'nombre': forms.TextInput(
                attrs={
                    'class': 'select-input',
                    'placeholder': 'Ej. Portal de clientes',
                }
            ),
            'fecha_inicio': forms.DateInput(
                attrs={'type': 'date', 'class': 'select-input'},
                format='%Y-%m-%d',
            ),
            'fecha_fin': forms.DateInput(
                attrs={'type': 'date', 'class': 'select-input'},
                format='%Y-%m-%d',
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
