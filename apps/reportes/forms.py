from django import forms
from django.core.exceptions import ValidationError

from apps.modelos.models import EstadoMetrica, Importancia

from .models import Proyecto


class FiltroMetricasForm(forms.Form):
    """Filtros de métricas por conformidad e importancia (HU-15).

    Los valores llegan por query string y se normalizan a los enums
    ``EstadoMetrica`` e ``Importancia``. Un valor no reconocido no rompe la
    pantalla: se descarta, se deja un aviso en ``avisos`` y el resto de los
    criterios se sigue aplicando, igual que en el catálogo de HU-09.
    """

    MAPA_CONFORMIDAD = {
        'cumple': EstadoMetrica.CUMPLE,
        'no_cumple': EstadoMetrica.NO_CUMPLE,
        'sin_medicion': EstadoMetrica.SIN_MEDICION,
    }
    MAPA_IMPORTANCIA = {
        'alta': Importancia.ALTA,
        'media': Importancia.MEDIA,
        'baja': Importancia.BAJA,
    }
    OPCIONES_CONFORMIDAD = (
        ('cumple', 'Cumple'),
        ('no_cumple', 'No cumple'),
        ('sin_medicion', 'Sin medición'),
    )
    OPCIONES_IMPORTANCIA = (
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja'),
    )

    conformidad = forms.CharField(
        required=False,
        widget=forms.Select(
            attrs={'class': 'select-input filter-compact'}
        ),
    )
    importancia = forms.CharField(
        required=False,
        widget=forms.Select(
            attrs={'class': 'select-input filter-compact'}
        ),
    )

    def __init__(self, data=None, **kwargs):
        super().__init__(data=data, **kwargs)
        self.fields['conformidad'].widget.choices = [
            ('', 'Todas'),
            *self.OPCIONES_CONFORMIDAD,
        ]
        self.fields['importancia'].widget.choices = [
            ('', 'Todas'),
            *self.OPCIONES_IMPORTANCIA,
        ]
        self.avisos = []

    def clean(self):
        datos = super().clean()
        datos['conformidad'] = self._normalizar(
            datos.get('conformidad'),
            self.MAPA_CONFORMIDAD,
            'El filtro de conformidad «{}» no es válido: se ignoró.',
        )
        datos['importancia'] = self._normalizar(
            datos.get('importancia'),
            self.MAPA_IMPORTANCIA,
            'El filtro de importancia «{}» no es válido: se ignoró.',
        )
        return datos

    def _normalizar(self, valor, mapa, plantilla_aviso):
        """Convierte el texto de la URL al enum o devuelve ``None``."""
        crudo = (valor or '').strip()
        if not crudo:
            return None
        normalizado = mapa.get(crudo.lower())
        if normalizado is None:
            self.avisos.append(plantilla_aviso.format(crudo))
        return normalizado

    def esta_activo(self):
        """Indica si al menos un filtro quedó seleccionado y válido."""
        if not self.is_valid():
            return False
        return bool(
            self.cleaned_data.get('conformidad')
            or self.cleaned_data.get('importancia')
        )

    def valores(self):
        """Valores normalizados listos para filtrar (``None`` = sin filtro)."""
        if not self.is_valid():
            return {'conformidad': None, 'importancia': None}
        return {
            'conformidad': self.cleaned_data.get('conformidad'),
            'importancia': self.cleaned_data.get('importancia'),
        }


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
