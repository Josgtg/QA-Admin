from pathlib import Path

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.reportes.models import Proyecto
from apps.tecnicas.selection import (
    obtener_proyecto_seleccionado,
    seleccionar_proyecto,
)

from .forms import RevisionMetricaForm
from .models import (
    Caracteristica,
    Metrica,
    MetricaAplicada,
    ModeloCalidad,
    RevisionMetrica,
)


class CatalogoModelosView(View):
    """Catálogo detallado de los modelos predefinidos (HU-03)."""

    template_name = 'modelos/catalogo_modelos.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            self.template_name,
            {'modelos': self.obtener_modelos_base()},
        )

    def obtener_modelos_base(self):
        return ModeloCalidad.obtener_predefinidos()

    def obtener_detalle(self, modelo_id):
        return get_object_or_404(
            ModeloCalidad,
            pk=modelo_id,
            predefinido=True,
        )


class ModeloDelProyectoView(View):
    """Entrada del menú lateral al modelo del proyecto activo (HU-02).

    El enlace del sidebar no conoce el identificador del proyecto, así que se
    resuelve con el proyecto seleccionado en la sesión. No renderiza nada: la
    pantalla es ``AplicarModeloView``, y el catálogo detallado (HU-03) se
    consulta desde un botón de esa misma pantalla.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        proyecto = obtener_proyecto_seleccionado(request)
        if proyecto is None:
            messages.info(
                request,
                'Registra un proyecto para consultar su modelo de calidad.',
            )
            return redirect('reportes:lista')
        seleccionar_proyecto(request, proyecto)
        return redirect(
            'reportes:aplicar_modelo', proyecto_id=proyecto.pk
        )


class AplicarModeloView(View):
    """Aplica un modelo predefinido al proyecto (HU-02)."""

    template_name = 'modelos/seleccion_modelo.html'

    def get(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)
        return self._render(request, proyecto)

    def post(self, request: HttpRequest, proyecto_id: int) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        modelo_id = request.POST.get('modelo_id')
        if not modelo_id:
            return HttpResponseBadRequest('Debe indicar el modelo.')

        modelo = get_object_or_404(
            ModeloCalidad,
            pk=modelo_id,
            predefinido=True,
        )
        confirmado = request.POST.get('confirmacion') == '1'

        vigente = self.obtener_modelo_aplicado_vigente(proyecto)
        if vigente is not None and vigente.modelo_calidad_id == modelo.pk:
            return self._render(request, proyecto)

        if self.solicitar_confirmacion(proyecto, modelo) and not confirmado:
            return self._render(
                request,
                proyecto,
                modelo=modelo,
                requiere_confirmacion=True,
            )

        try:
            proyecto.aplicar_modelo(modelo)
        except ValidationError as error:
            return self._render(
                request,
                proyecto,
                modelo=modelo,
                error=error.messages[0],
            )

        messages.success(
            request,
            f'Modelo "{modelo.nombre}" aplicado al proyecto.',
        )
        return redirect('reportes:tablero', proyecto_id=proyecto.pk)

    def obtener_modelo_aplicado_vigente(self, proyecto):
        return proyecto.modelo_aplicado_vigente()

    def solicitar_confirmacion(self, proyecto, modelo):
        """Pide confirmación si cambia el modelo y ya hay mediciones."""
        vigente = self.obtener_modelo_aplicado_vigente(proyecto)
        if vigente is None:
            return False
        if vigente.modelo_calidad_id == modelo.pk:
            return False
        return proyecto.tiene_mediciones()

    def _render(
        self,
        request,
        proyecto,
        modelo=None,
        requiere_confirmacion=False,
        error=None,
    ):
        vigente = self.obtener_modelo_aplicado_vigente(proyecto)
        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
                'modelos': ModeloCalidad.obtener_predefinidos(),
                'modelo': modelo,
                'vigente': vigente,
                'requiere_confirmacion': requiere_confirmacion,
                'error': error,
                'tiene_mediciones': proyecto.tiene_mediciones(),
            },
        )


class DescargarEvidenciaMetricaView(View):
    """Descarga el archivo de una revisión del proyecto, incluso histórica."""

    def get(
        self, request: HttpRequest, proyecto_id: int, revision_id: int
    ) -> HttpResponse:
        """Resuelve la revisión y entrega el archivo desde su almacenamiento."""
        revision = get_object_or_404(
            RevisionMetrica,
            pk=revision_id,
            metrica_aplicada__modelo_aplicado__proyecto_id=proyecto_id,
        )
        if not revision.archivo:
            raise Http404('Esta revisión no tiene un archivo de evidencia.')
        try:
            archivo = revision.archivo.open('rb')
        except FileNotFoundError as error:
            raise Http404(
                'El archivo de evidencia ya no está disponible.'
            ) from error
        return FileResponse(
            archivo,
            as_attachment=True,
            filename=Path(revision.archivo.name).name,
        )


class RegistrarRevisionMetricaView(View):
    """Registro de una revisión de métrica y su historial (HU-01)."""

    template_name = 'modelos/revision_metrica.html'

    def get(
        self, request: HttpRequest, proyecto_id: int, metrica_id: int
    ) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        instantanea = self.obtener_metrica_aplicada(proyecto, metrica_id)
        if instantanea is None:
            return self._sin_modelo(request, proyecto)

        return self._render(
            request,
            proyecto,
            instantanea,
            RevisionMetricaForm(proyecto=proyecto),
        )

    def post(
        self, request: HttpRequest, proyecto_id: int, metrica_id: int
    ) -> HttpResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        seleccionar_proyecto(request, proyecto)

        instantanea = self.obtener_metrica_aplicada(proyecto, metrica_id)
        if instantanea is None:
            return self._sin_modelo(request, proyecto)

        form = RevisionMetricaForm(
            request.POST,
            request.FILES,
            proyecto=proyecto,
        )
        if not form.is_valid():
            return self._render(request, proyecto, instantanea, form)

        revision = form.save(commit=False)
        revision.metrica_aplicada = instantanea
        try:
            revision.full_clean()
        except ValidationError as error:
            for campo, mensajes_error in error.message_dict.items():
                if campo in form.fields:
                    form.add_error(campo, mensajes_error)
                else:
                    form.add_error(None, mensajes_error)
            return self._render(request, proyecto, instantanea, form)

        revision.save()
        messages.success(request, 'Revisión de métrica registrada.')
        return redirect('reportes:metricas', proyecto_id=proyecto.pk)

    def obtener_metrica_aplicada(self, proyecto, metrica):
        """Instantánea vigente de la métrica en el proyecto."""
        aplicado = proyecto.modelo_aplicado_vigente()
        if aplicado is None:
            return None
        if hasattr(metrica, 'pk'):
            return aplicado.metrica_aplicada(metrica)
        return MetricaAplicada.objects.filter(
            metrica_id=metrica,
            modelo_aplicado=aplicado,
        ).first()

    def obtener_historial(self, proyecto, metrica):
        return metrica.revisiones(proyecto)

    def _sin_modelo(self, request, proyecto):
        messages.warning(
            request,
            'Aplica un modelo de calidad al proyecto antes de registrar '
            'métricas.',
        )
        return redirect(
            'reportes:aplicar_modelo', proyecto_id=proyecto.pk
        )

    def _render(self, request, proyecto, instantanea, form):
        metrica = instantanea.metrica
        return render(
            request,
            self.template_name,
            {
                'proyecto': proyecto,
                'instantanea': instantanea,
                'metrica': metrica,
                'form': form,
                'ultima': metrica.ultima_revision(proyecto),
                'valor_ultimo': metrica.ultimo_valor(proyecto),
                'historial': self.obtener_historial(proyecto, metrica),
                'aceptada': metrica.esta_aceptada(proyecto),
                'seguimiento': metrica.caracteristica.calcular_seguimiento(
                    proyecto
                ),
            },
        )


class CatalogoMetricasView(View):
    """Catálogo base de métricas de calidad (HU-09).

    Solo lectura: expone únicamente consultas. El encargado estudia aquí las
    métricas para crear su propio modelo (HU-16); no crea ni edita nada.

    Filtros por query string:
    - ``caracteristica``: id de ``Caracteristica``.
    - ``cumple``: ``1``/``0``. Consulta informativa del umbral; requiere
      ``modelo`` (id del modelo) para saber contra qué umbral se compara.
    """

    template_name = 'modelos/catalogo_metricas.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        caracteristica_id = self._entero(request.GET.get('caracteristica'))
        modelo_id = self._entero(request.GET.get('modelo'))
        cumple = self._booleano(request.GET.get('cumple'))
        valor = self._flotante(request.GET.get('valor'))
        avisos = []

        if request.GET.get('valor') and valor is None:
            avisos.append(
                'El valor medido no es un número: revisa el formato. '
                'Usa un punto o una coma decimal, por ejemplo 95.5.'
            )
        if request.GET.get('cumple') and cumple is None:
            avisos.append(
                'El filtro de conformidad debe ser "Cumple" o "No cumple": '
                'se ignoró el valor enviado.'
            )

        caracteristica = self._caracteristica(caracteristica_id, avisos)
        modelo = self._modelo(modelo_id, avisos)
        caracteristica_id = caracteristica.pk if caracteristica else None

        metricas = self.filtrar_por_caracteristica(caracteristica_id)

        # El filtro de conformidad solo aplica con modelo, decisión y valor.
        conformidad_pedida = request.GET.get('cumple') in ('0', '1')
        if cumple is not None and modelo is not None and valor is not None:
            metricas = self._filtrar_por_conformidad(
                metricas, modelo, cumple, valor
            )
            contexto_conformidad = True
        else:
            contexto_conformidad = False
            if conformidad_pedida and modelo is None:
                avisos.append(
                    'El filtro de conformidad necesita un modelo: '
                    'no se aplicó.'
                )
            elif conformidad_pedida and valor is None:
                avisos.append(
                    'Indica un valor medido para comparar con el umbral: '
                    'sin ese dato no se aplica el filtro de conformidad.'
                )
            cumple = None

        return render(
            request,
            self.template_name,
            {
                'caracteristicas': self.caracteristicas_disponibles(),
                'caracteristica_seleccionada': caracteristica,
                'metricas': metricas,
                'agrupadas': self.agrupar_por_caracteristica(metricas),
                'modelos': ModeloCalidad.obtener_predefinidos(),
                'modelo_seleccionado': modelo,
                'cumple': cumple,
                'valor': request.GET.get('valor', ''),
                'avisos': avisos,
                'con_formula': self._formula_conformidad(
                    contexto_conformidad, valor
                ),
            },
        )

    # -- Consultas (operaciones del diagrama de clases) --------------------

    def listar_metricas(self):
        """Métricas del catálogo base con su característica."""
        return Metrica.objects.select_related('caracteristica').order_by(
            'caracteristica__nombre', 'nombre'
        )

    def filtrar_por_caracteristica(self, caracteristica_id=None):
        """Subconjunto de métricas de una característica."""
        metricas = self.listar_metricas()
        if caracteristica_id not in (None, ''):
            metricas = metricas.filter(caracteristica_id=caracteristica_id)
        return metricas

    def filtrar_por_conformidad(self, modelo, cumple, valor=None):
        """Métricas del modelo cuyo umbral se cumple (o no) con ``valor``."""
        return self._filtrar_por_conformidad(
            self.listar_metricas(),
            modelo,
            cumple,
            valor,
        )

    def caracteristicas_disponibles(self):
        """Características del catálogo que agrupan al menos una métrica."""
        return Caracteristica.objects.filter(
            metricas__isnull=False
        ).distinct()

    def agrupar_por_caracteristica(self, metricas):
        """Agrupa las métricas por característica, en orden de nombre.

        Devuelve ``[(caracteristica_id, grupo), ...]`` donde ``grupo`` expone
        ``nombre``, ``descripcion`` y ``metricas``; la plantilla lo recorre sin
        necesidad de consultas adicionales.
        """
        grupos = {}
        for metrica in metricas:
            caracteristica = metrica.caracteristica
            grupo = grupos.setdefault(
                caracteristica.pk,
                {
                    'nombre': caracteristica.nombre,
                    'descripcion': caracteristica.descripcion,
                    'metricas': [],
                },
            )
            grupo['metricas'].append(metrica)
        return sorted(grupos.items(), key=lambda par: par[1]['nombre'])

    # -- Internos ----------------------------------------------------------

    def _filtrar_por_conformidad(self, metricas, modelo, cumple, valor):
        """Filtro informativo: comparar ``valor`` con el umbral del modelo.

        Sin valor medido no hay punto de comparación, así que no se filtra
        (se devuelven todas las métricas del modelo). Esto protege el
        catálogo de una lectura engañosa.
        """
        if valor is None:
            return metricas
        modelo_metricas = modelo.obtener_modelo_metricas()
        ids = [
            modelo_metrica.metrica_id
            for modelo_metrica in modelo_metricas
            if modelo_metrica.evaluar_cumplimiento(valor) == cumple
        ]
        return metricas.filter(pk__in=ids)

    def _formula_conformidad(self, contexto_conformidad, valor):
        """Texto del aviso que explica contra qué se comparó el umbral."""
        if not contexto_conformidad:
            return ''
        if valor is None:
            return 'Indica un valor medido para comparar con el umbral.'
        return f'valor medido = {valor:g}'

    def _caracteristica(self, caracteristica_id, avisos):
        """Devuelve la característica pedida o ``None`` si no es válida.

        Cuando el filtro llega mal formado o apunta a un id inexistente se
        descarta y se deja un aviso, en lugar de ignorarlo en silencio o
        romper con un 404 genérico.
        """
        if caracteristica_id is None:
            return None
        caracteristica = Caracteristica.objects.filter(
            pk=caracteristica_id
        ).first()
        if caracteristica is None:
            avisos.append(
                'La característica indicada no existe: se muestra el '
                'catálogo completo.'
            )
        return caracteristica

    def _modelo(self, modelo_id, avisos):
        """Devuelve el modelo pedido o ``None`` si no es válido.

        Igual que con la característica, un id inexistente o mal formado no
        rompe la pantalla: se avisa y el filtro de conformidad no se aplica.
        """
        if modelo_id is None:
            return None
        modelo = ModeloCalidad.objects.filter(pk=modelo_id).first()
        if modelo is None:
            avisos.append(
                'El modelo indicado no existe: el filtro de conformidad no '
                'se aplicó.'
            )
        return modelo

    @staticmethod
    def _entero(valor):
        """Convierte un id de query string a ``int`` o ``None``."""
        if valor and valor.isdigit():
            return int(valor)
        return None

    @staticmethod
    def _flotante(valor):
        """Convierte un valor medido a ``float``; admite coma decimal."""
        if not valor:
            return None
        try:
            return float(valor.replace(',', '.'))
        except ValueError:
            return None

    @staticmethod
    def _booleano(valor):
        """Convierte el filtro ``cumple`` (``1``/``0``) a ``bool``."""
        if valor in ('1', 'true', 'True'):
            return True
        if valor in ('0', 'false', 'False'):
            return False
        return None
