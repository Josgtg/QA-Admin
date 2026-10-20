from django import forms

from apps.tecnicas.models import Proyecto


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
