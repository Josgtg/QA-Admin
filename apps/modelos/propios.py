from django import forms
from django.contrib import messages
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import override
from django.views.decorators.http import require_POST

from .models import ModeloCalidad, TipoUmbral


class ModeloForm(forms.ModelForm):
    """Valida la identidad y la descripción de un modelo propio."""

    class Meta:
        model = ModeloCalidad
        fields = ['nombre', 'descripcion']


class MetricaPropiaForm(forms.Form):
    """Valida una métrica y su umbral antes de crear el modelo."""

    caracteristica = forms.CharField(max_length=200, label='Característica')
    nombre = forms.CharField(max_length=200, label='Nombre de la métrica')
    forma_medicion = forms.CharField(label='Forma de medir')
    unidad = forms.CharField(max_length=50)
    meta = forms.FloatField()
    tipo_umbral = forms.ChoiceField(choices=TipoUmbral.choices)


MetricasFormSet = forms.formset_factory(
    MetricaPropiaForm, min_num=1, validate_min=True, extra=0
)


@override("es")
def crear_modelo(request):
    """Valida el formulario de alta y presenta los errores de captura."""
    datos = request.POST if request.method == 'POST' else None
    modelo = ModeloForm(datos)
    metricas = MetricasFormSet(
        datos, error_messages={'too_few_forms': 'Agrega al menos una métrica.'}
    )
    if datos is not None and modelo.is_valid() and metricas.is_valid():
        try:
            modelo.instance.guardar_con_metricas(metricas.cleaned_data)
        except IntegrityError:
            nombre = modelo.cleaned_data['nombre']
            if not ModeloCalidad.objects.filter(nombre=nombre).exists():
                raise
            modelo.add_error('nombre', 'Ya existe un modelo con este nombre.')
        else:
            return redirect('modelos:catalogo')
    contexto = {'modelo': modelo, 'metricas': metricas}
    return render(request, 'modelos/crear.html', contexto)


@require_POST
def eliminar_modelo(request, pk):
    """Elimina un modelo propio libre o informa los proyectos que lo usan."""
    modelo = get_object_or_404(ModeloCalidad, pk=pk, predefinido=False)
    try:
        modelo.delete()
    except ProtectedError:
        proyectos = modelo.aplicaciones.order_by('proyecto__nombre').values_list(
            'proyecto__nombre', flat=True
        ).distinct()
        aviso = 'El modelo se utiliza en estos proyectos: ' + ', '.join(proyectos)
        messages.error(request, aviso)
    return redirect('modelos:catalogo')
