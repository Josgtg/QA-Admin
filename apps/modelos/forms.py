from django import forms
from django.core.exceptions import ValidationError

from apps.reportes.models import MiembroProyecto

from .models import ModeloCalidad, RevisionMetrica, TipoUmbral


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


class ModeloCalidadForm(forms.ModelForm):
    """Datos de un modelo propio de calidad (HU-16)."""

    class Meta:
        model = ModeloCalidad
        fields = ['nombre', 'descripcion']
        labels = {
            'nombre': 'Nombre del modelo',
            'descripcion': 'Descripción',
        }
        widgets = {
            'nombre': forms.TextInput(
                attrs={
                    'class': 'select-input',
                    'placeholder': 'Ej. Calidad del portal de clientes',
                }
            ),
            'descripcion': forms.Textarea(
                attrs={
                    'class': 'select-input',
                    'rows': 3,
                    'placeholder': 'Describe el propósito del modelo.',
                }
            ),
        }

    def clean_nombre(self):
        """Recorta el nombre y rechaza los duplicados sin distinguir mayúsculas."""
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if not nombre:
            raise ValidationError('Escribe el nombre del modelo.')
        existentes = ModeloCalidad.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise ValidationError('Ya existe un modelo con este nombre.')
        return nombre


class MetricaPropiaForm(forms.Form):
    """Métrica nueva con su forma de medición, unidad y meta (HU-16)."""

    caracteristica = forms.CharField(
        max_length=200,
        label='Característica',
        widget=forms.TextInput(
            attrs={
                'class': 'select-input',
                'placeholder': 'Ej. Mantenibilidad',
            }
        ),
    )
    nombre = forms.CharField(
        max_length=200,
        label='Nombre de la métrica',
        widget=forms.TextInput(
            attrs={
                'class': 'select-input',
                'placeholder': 'Ej. Cobertura de pruebas',
            }
        ),
    )
    descripcion = forms.CharField(
        required=False,
        label='Descripción',
        widget=forms.Textarea(
            attrs={
                'class': 'select-input',
                'rows': 2,
                'placeholder': 'Opcional: qué mide la métrica.',
            }
        ),
    )
    forma_medicion = forms.CharField(
        label='Forma de medir',
        widget=forms.Textarea(
            attrs={
                'class': 'select-input',
                'rows': 2,
                'placeholder': 'Ej. Líneas cubiertas entre líneas totales.',
            }
        ),
    )
    unidad = forms.CharField(
        max_length=50,
        label='Unidad',
        widget=forms.TextInput(
            attrs={
                'class': 'select-input',
                'placeholder': 'Ej. %, horas, defectos',
            }
        ),
    )
    meta = forms.FloatField(
        label='Meta',
        widget=forms.NumberInput(
            attrs={'class': 'select-input', 'step': 'any'}
        ),
    )
    tipo_umbral = forms.ChoiceField(
        choices=TipoUmbral.choices,
        label='Tipo de umbral',
        initial=TipoUmbral.MINIMO,
        widget=forms.Select(attrs={'class': 'select-input'}),
    )


class MetricasFormSet(forms.BaseFormSet):
    """Formset que exige al menos una métrica por modelo (HU-16).

    Reúne la configuración que ``formset_factory`` aplicaría a
    ``MetricaPropiaForm`` y añade el mensaje de mínimo en español.
    """

    form = MetricaPropiaForm
    extra = 0
    min_num = 1
    max_num = 1000
    absolute_max = 2000
    validate_min = True
    validate_max = False
    can_order = False
    can_delete = False
    can_delete_extra = True
    renderer = None
    default_error_messages = {
        **forms.BaseFormSet.default_error_messages,
        'too_few_forms': 'Agrega al menos una métrica al modelo.',
    }
