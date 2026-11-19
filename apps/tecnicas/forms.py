from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.reportes.models import MiembroProyecto

from .models import Dimension, Evidencia, TecnicaQA, TipoControl
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


class TecnicaPropiaForm(forms.ModelForm):
    """Datos de una técnica creada por el encargado (HU-17)."""

    class Meta:
        model = TecnicaQA
        fields = [
            'nombre',
            'dimension',
            'tipo_control',
            'descripcion',
            'objetivo',
            'pregunta_clave',
        ]
        labels = {
            'nombre': 'Nombre de la técnica',
            'dimension': 'Dimensión',
            'tipo_control': 'Tipo de control',
            'descripcion': 'Descripción',
            'objetivo': 'Objetivo (opcional)',
            'pregunta_clave': 'Pregunta clave (opcional)',
        }
        error_messages = {
            'nombre': {'required': 'Escribe el nombre de la técnica.'},
            'dimension': {
                'required': 'Elige la dimensión de la técnica.',
                'invalid_choice': 'Elige una dimensión de la lista.',
            },
            'tipo_control': {
                'required': 'Elige el tipo de control.',
                'invalid_choice': 'Elige un tipo de control de la lista.',
            },
            'descripcion': {'required': 'Escribe la descripción de la técnica.'},
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'select-input'}),
            'dimension': forms.Select(attrs={'class': 'select-input'}),
            'tipo_control': forms.Select(attrs={'class': 'select-input'}),
            'descripcion': forms.Textarea(
                attrs={'class': 'select-input', 'rows': 3}
            ),
            'objetivo': forms.Textarea(attrs={'class': 'select-input', 'rows': 2}),
            'pregunta_clave': forms.Textarea(
                attrs={'class': 'select-input', 'rows': 2}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['objetivo'].required = False
        self.fields['pregunta_clave'].required = False
        # Django pone «- Select an option -» en inglés como opción vacía.
        self.fields['dimension'].choices = [
            ('', 'Elige una dimensión'), *Dimension.choices
        ]
        self.fields['tipo_control'].choices = [
            ('', 'Elige el tipo de control'), *TipoControl.choices
        ]

    def clean_nombre(self):
        """Rechaza un nombre que ya use otra técnica, sin importar mayúsculas."""
        nombre = ' '.join(self.cleaned_data['nombre'].split())
        otras = TecnicaQA.objects.exclude(pk=self.instance.pk).values_list(
            'nombre', flat=True
        )
        if nombre.casefold() in {otra.casefold() for otra in otras}:
            raise ValidationError('Ya existe una técnica con ese nombre.')
        return nombre


class PasoForm(forms.Form):
    """Un paso de una técnica propia: qué hacer y qué evidencia se espera."""

    instruccion = forms.CharField(
        label='Qué hay que hacer',
        required=False,
        widget=forms.Textarea(attrs={'class': 'select-input', 'rows': 2}),
    )
    evidencia_esperada = forms.CharField(
        label='Evidencia que se espera',
        required=False,
        widget=forms.Textarea(attrs={'class': 'select-input', 'rows': 2}),
    )

    def clean(self):
        datos = super().clean()
        instruccion = datos.get('instruccion')
        evidencia = datos.get('evidencia_esperada')
        if instruccion and not evidencia:
            self.add_error(
                'evidencia_esperada',
                'Indica qué evidencia se espera de este paso.',
            )
        elif evidencia and not instruccion:
            self.add_error('instruccion', 'Indica qué hay que hacer en este paso.')
        return datos


class BasePasoFormSet(forms.BaseFormSet):
    """Pasos de una técnica propia; las filas vacías se ignoran."""

    def clean(self):
        if any(self.errors):
            return
        if not self.pasos():
            raise ValidationError('Agrega al menos un paso a la técnica.')

    def pasos(self):
        """Pares (instrucción, evidencia esperada) en el orden de las filas."""
        return [
            (form.cleaned_data['instruccion'], form.cleaned_data['evidencia_esperada'])
            for form in self.forms
            if form.cleaned_data.get('instruccion')
        ]


PasoFormSet = forms.formset_factory(
    PasoForm,
    formset=BasePasoFormSet,
    extra=2,
)
