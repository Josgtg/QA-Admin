from datetime import date

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Periodo:
    """Periodo derivado de las fechas del proyecto (``hu7_clases.puml``).

    Es un **helper de presentación**: no se persiste, no hace consultas y no
    representa una entidad de dominio. ``Proyecto.periodo()`` calcula el estado
    y ``ListaProyectosView`` agrupa y ordena.
    """

    FUTURO = 'Futuro'
    ACTIVO = 'Activo'
    TERMINADO = 'Terminado'
    ESTADOS = (FUTURO, ACTIVO, TERMINADO)

    DESCRIPCIONES = {
        FUTURO: 'Proyectos que todavía no han iniciado.',
        ACTIVO: 'Proyectos que están en curso.',
        TERMINADO: 'Proyectos que ya finalizaron.',
    }

    ALIASES = {
        'futuro': FUTURO,
        'planificacion': FUTURO,
        'activo': ACTIVO,
        'activos': ACTIVO,
        'terminado': TERMINADO,
        'cerrado': TERMINADO,
        'cerrados': TERMINADO,
    }

    def __init__(self, nombre):
        if nombre not in self.ESTADOS:
            raise ValueError('Periodo no válido.')
        self.nombre = nombre
        self.id = nombre.lower()
        self.descripcion = self.DESCRIPCIONES[nombre]

    def __str__(self):
        return self.nombre

    def __eq__(self, other):
        return isinstance(other, Periodo) and self.nombre == other.nombre

    def __hash__(self):
        return hash(self.nombre)

    @classmethod
    def desde_parametro(cls, valor):
        if not valor:
            return None
        clave = valor.strip().lower()
        nombre = cls.ALIASES.get(clave)
        if nombre is None:
            raise ValueError('Periodo no válido.')
        return cls(nombre)


class Proyecto(models.Model):
    """Proyecto del encargado de calidad (``hu6_clases.puml``).

    Vive en ``reportes`` según el diseño vigente. ``seguimientos()`` es la
    única referencia permitida de esta app hacia ``tecnicas`` y se resuelve con
    el accessor inverso, sin importar el módulo.
    """

    nombre = models.CharField(max_length=200)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    class Meta:
        verbose_name = 'proyecto'
        verbose_name_plural = 'proyectos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def clean(self):
        errores = {}
        if not self.fecha_inicio:
            errores['fecha_inicio'] = 'Indica la fecha de inicio.'
        if not self.fecha_fin:
            errores['fecha_fin'] = 'Indica la fecha de fin.'
        if (
            self.fecha_inicio
            and self.fecha_fin
            and self.fecha_fin < self.fecha_inicio
        ):
            errores['fecha_fin'] = (
                'La fecha de fin no puede ser anterior a la de inicio.'
            )
        if errores:
            raise ValidationError(errores)

    @property
    def fecha_fin_estimada(self):
        return self.fecha_fin

    def periodo(self):
        """Estado derivado de las fechas: Futuro, Activo o Terminado."""
        hoy = timezone.localdate()
        if hoy < self.fecha_inicio:
            return Periodo.FUTURO
        if hoy > self.fecha_fin:
            return Periodo.TERMINADO
        return Periodo.ACTIVO

    def esta_en_periodo(self, periodo):
        return self.periodo() == periodo

    def indice_salud(self):
        """Índice de 0 a 100: promedia técnicas y métricas (HU-14).

        Cada parte vale lo mismo. Si el proyecto solo tiene una, el índice es
        esa parte; si no tiene ninguna, no hay índice.
        """
        partes = [
            parte
            for parte in (self.avance_tecnicas(), self.cumplimiento_metricas())
            if parte is not None
        ]
        if not partes:
            return None
        return round(sum(partes) / len(partes), 1)

    def avance_tecnicas(self):
        """Promedio del avance de las técnicas activas, o None si no hay."""
        avances = list(
            self.seguimientos_tecnicas.filter(activa=True).values_list(
                'porcentaje_avance', flat=True
            )
        )
        if not avances:
            return None
        return sum(avances) / len(avances)

    def cumplimiento_metricas(self):
        """Porcentaje de métricas activas que cumplen, o None si no hay."""
        valores = [valor for _, valor in self.estado_metricas()]
        if not valores:
            return None
        return sum(valores) / len(valores)

    def estado_metricas(self):
        """Cada métrica activa con su nombre y 100 si cumple o 0 si no."""
        from apps.modelos.models import Metrica

        aplicado = self.modelo_aplicado_vigente()
        if aplicado is None:
            return []
        ultimos = Metrica.ultimos_valores_por_metrica(self)
        return [
            (
                instantanea.metrica.nombre,
                100.0
                if instantanea.evaluar_cumplimiento(
                    ultimos.get(instantanea.metrica_id)
                )
                else 0.0,
            )
            for instantanea in aplicado.metricas_aplicadas().filter(activa=True)
        ]

    # --- Equipo ---------------------------------------------------------

    def equipo_activo(self):
        return self.equipo.filter(activo=True).select_related('persona')

    def miembros_todos(self):
        return self.equipo.select_related('persona').order_by(
            '-activo', 'persona__nombre'
        )

    def agregar_miembro(self, persona, rol):
        miembro, creado = self.equipo.get_or_create(
            persona=persona,
            defaults={'rol': rol},
        )
        if not creado:
            miembro.rol = rol
            miembro.activo = True
            miembro.full_clean()
            miembro.save(update_fields=['rol', 'activo'])
        return miembro

    # --- Técnicas -------------------------------------------------------

    def seguimientos(self):
        """Seguimientos de técnicas del proyecto (``hu6_clases.puml``)."""
        return self.seguimientos_tecnicas.all()

    def seguimientos_activos(self):
        return self.seguimientos_tecnicas.filter(activa=True).select_related(
            'tecnica'
        )

    # --- Métricas -------------------------------------------------------

    def historial_modelos(self):
        return self.modelos_aplicados.select_related(
            'modelo_calidad'
        ).order_by('-fecha_aplicacion', '-pk')

    def modelo_aplicado_vigente(self):
        return (
            self.modelos_aplicados.filter(vigente=True)
            .select_related('modelo_calidad')
            .first()
        )

    def revisiones(self):
        """Revisiones del proyecto vía ModeloAplicado -> MetricaAplicada."""
        from apps.modelos.models import Metrica

        return Metrica.revisiones_de_proyecto(self).select_related(
            'metrica_aplicada__metrica',
            'miembro_proyecto__persona',
        )

    def tiene_mediciones(self):
        return self.revisiones().exists()

    @transaction.atomic
    def aplicar_modelo(self, modelo_calidad):
        """Aplica un modelo predefinido y crea su instantánea (HU-02)."""
        from apps.modelos.models import ModeloAplicado

        if not modelo_calidad.modelo_metricas.exists():
            raise ValidationError(
                {
                    'modelo_calidad': (
                        'Este modelo no tiene métricas configuradas.'
                    )
                }
            )

        vigente = self.modelo_aplicado_vigente()
        if vigente is not None and vigente.modelo_calidad_id == modelo_calidad.pk:
            return vigente
        if vigente is not None:
            vigente.cerrar()

        aplicado = ModeloAplicado.objects.create(
            proyecto=self,
            modelo_calidad=modelo_calidad,
        )
        aplicado.crear_instantanea()
        return aplicado

    def cambiar_modelo(self, modelo_calidad):
        return self.aplicar_modelo(modelo_calidad)


class Persona(models.Model):
    nombre = models.CharField(max_length=150, unique=True)

    class Meta:
        verbose_name = 'persona'
        verbose_name_plural = 'personas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class MiembroProyecto(models.Model):
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='equipo',
    )
    persona = models.ForeignKey(
        Persona,
        on_delete=models.PROTECT,
        related_name='membresias',
    )
    rol = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'miembro de proyecto'
        verbose_name_plural = 'miembros de proyecto'
        ordering = ['persona__nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['proyecto', 'persona'],
                name='miembro_unico_por_proyecto_y_persona',
            ),
        ]

    def __str__(self):
        return f'{self.persona} · {self.proyecto} · {self.rol}'

    def clean(self):
        if not self.rol or not self.rol.strip():
            raise ValidationError({'rol': 'El rol no puede estar vacío.'})

    def desactivar(self):
        self.activo = False
        self.save(update_fields=['activo'])

    def reactivar(self):
        self.activo = True
        self.save(update_fields=['activo'])

    def cambiar_rol(self, nuevo_rol):
        self.rol = nuevo_rol
        self.full_clean()
        self.save(update_fields=['rol'])


class RegistroSalud(models.Model):
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='registros_salud',
    )
    fecha = models.DateField(default=timezone.localdate)
    indice = models.FloatField()
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'registro de salud'
        verbose_name_plural = 'registros de salud'
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(
                fields=['proyecto', 'fecha'],
                name='salud_unica_por_proyecto_y_fecha',
            ),
        ]

    def __str__(self):
        return f'{self.proyecto} · {self.fecha} · {self.indice}'

    @transaction.atomic
    def guardar_detalles(self, proyecto):
        """Guarda cómo estaba cada técnica y métrica en este registro."""
        self.detalles.all().delete()
        detalles = [
            DetalleSalud(
                registro=self,
                tipo=TipoDetalleSalud.TECNICA,
                nombre=seguimiento.tecnica.nombre,
                valor=seguimiento.porcentaje_avance,
            )
            for seguimiento in proyecto.seguimientos_activos()
        ]
        detalles += [
            DetalleSalud(
                registro=self,
                tipo=TipoDetalleSalud.METRICA,
                nombre=nombre,
                valor=valor,
            )
            for nombre, valor in proyecto.estado_metricas()
        ]
        DetalleSalud.objects.bulk_create(detalles)

    def causas_de_caida(self, anterior):
        """Técnicas y métricas que bajaron respecto al registro anterior."""
        previos = {
            (detalle.tipo, detalle.nombre): detalle
            for detalle in anterior.detalles.all()
        }
        if not previos:
            return []
        causas = []
        for detalle in self.detalles.all():
            previo = previos.pop((detalle.tipo, detalle.nombre), None)
            if previo is None:
                bajo = detalle.valor < anterior.indice
            else:
                bajo = detalle.valor < previo.valor
            if bajo:
                causas.append(
                    detalle.describir_cambio(
                        previo.valor if previo else None, detalle.valor
                    )
                )
        for previo in previos.values():
            if previo.valor > self.indice:
                causas.append(previo.describir_cambio(previo.valor, None))
        return causas


class TipoDetalleSalud(models.TextChoices):
    """Indica si un detalle de salud es de una técnica o de una métrica."""

    TECNICA = 'TECNICA', 'Técnica'
    METRICA = 'METRICA', 'Métrica'


class DetalleSalud(models.Model):
    """Estado de una técnica o métrica al guardar un registro de salud."""

    registro = models.ForeignKey(
        RegistroSalud,
        on_delete=models.CASCADE,
        related_name='detalles',
    )
    tipo = models.CharField(max_length=10, choices=TipoDetalleSalud.choices)
    nombre = models.CharField(max_length=200)
    valor = models.FloatField()

    class Meta:
        verbose_name = 'detalle de salud'
        verbose_name_plural = 'detalles de salud'
        ordering = ['tipo', 'nombre']

    def __str__(self):
        return f'{self.registro} · {self.nombre} · {self.valor}'

    def describir_cambio(self, antes, despues):
        """Devuelve la causa de una caída con un texto fácil de leer."""
        if self.tipo == TipoDetalleSalud.METRICA:
            if antes is None:
                texto = 'se agregó sin cumplir su meta'
            elif despues is None:
                texto = 'se quitó cuando cumplía su meta'
            else:
                texto = 'dejó de cumplir su meta'
        elif antes is None:
            texto = f'se agregó con {despues:g} % de avance'
        elif despues is None:
            texto = f'se quitó cuando tenía {antes:g} % de avance'
        else:
            texto = f'bajó de {antes:g} % a {despues:g} % de avance'
        return {
            'tipo': self.get_tipo_display(),
            'nombre': self.nombre,
            'antes': antes,
            'despues': despues,
            'texto': texto,
        }


def registrar_salud(proyecto):
    """Guarda o refresca el índice de salud del proyecto para hoy."""
    indice = proyecto.indice_salud()
    if indice is None:
        return None
    registro, _ = RegistroSalud.objects.update_or_create(
        proyecto=proyecto,
        fecha=timezone.localdate(),
        defaults={'indice': indice},
    )
    registro.guardar_detalles(proyecto)
    return registro


def tendencia_salud(proyecto, limite=6, desde=None, hasta=None):
    """Devuelve los registros de salud, del más antiguo al más nuevo."""
    registros = proyecto.registros_salud.prefetch_related('detalles')
    if desde:
        registros = registros.filter(fecha__gte=desde)
    if hasta:
        registros = registros.filter(fecha__lte=hasta)
    return list(reversed(registros.order_by('-fecha')[:limite]))


def caidas_salud(registros):
    """Caídas entre registros consecutivos, de la más nueva a la más antigua."""
    caidas = [
        {
            'fecha': actual.fecha,
            'antes': anterior.indice,
            'despues': actual.indice,
            'causas': actual.causas_de_caida(anterior),
        }
        for anterior, actual in zip(registros, registros[1:])
        if actual.indice < anterior.indice
    ]
    return list(reversed(caidas))
