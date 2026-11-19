from django import forms
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Caracteristica, Metrica, ModeloCalidad, ModeloMetrica, TipoUmbral


class ModeloForm(forms.ModelForm):
    class Meta:
        model = ModeloCalidad
        fields = ['nombre', 'descripcion']


class MetricaPropiaForm(forms.Form):
    caracteristica = forms.CharField(max_length=200, label='Característica')
    nombre = forms.CharField(max_length=200, label='Nombre de la métrica')
    forma_medicion = forms.CharField(label='Forma de medir')
    unidad = forms.CharField(max_length=50)
    meta = forms.FloatField()
    tipo_umbral = forms.ChoiceField(choices=TipoUmbral.choices)


MetricasFormSet = forms.formset_factory(MetricaPropiaForm, min_num=1, validate_min=True, extra=0)


def crear_modelo(request):
    datos = request.POST if request.method == 'POST' else None
    modelo = ModeloForm(datos)
    metricas = MetricasFormSet(datos)
    if datos is not None and modelo.is_valid() and metricas.is_valid():
        try:
            with transaction.atomic():
                nuevo = modelo.save()
                for fila in metricas.cleaned_data:
                    if not fila:
                        continue
                    caracteristica, _ = Caracteristica.objects.get_or_create(nombre=fila['caracteristica'])
                    metrica = Metrica.objects.create(
                        caracteristica=caracteristica, nombre=fila['nombre'],
                        forma_medicion=fila['forma_medicion'], unidad=fila['unidad'],
                    )
                    ModeloMetrica.objects.create(modelo_calidad=nuevo, metrica=metrica,
                                                umbral=fila['meta'], tipo_umbral=fila['tipo_umbral'])
        except IntegrityError:
            if not ModeloCalidad.objects.filter(nombre=modelo.cleaned_data['nombre']).exists():
                raise
            modelo.add_error('nombre', 'Ya existe un modelo con este nombre.')
        else:
            return redirect('modelos:catalogo')
    return render(request, 'modelos/crear.html', {'modelo': modelo, 'metricas': metricas})


@require_POST
def eliminar_modelo(request, pk):
    modelo = get_object_or_404(ModeloCalidad, pk=pk, predefinido=False)
    try:
        modelo.delete()
    except ProtectedError:
        proyectos = modelo.aplicaciones.order_by('proyecto__nombre').values_list('proyecto__nombre', flat=True).distinct()
        messages.error(request, 'El modelo se utiliza en estos proyectos: ' + ', '.join(proyectos))
    return redirect('modelos:catalogo')
