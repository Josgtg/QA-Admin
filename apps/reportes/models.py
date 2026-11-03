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
        """Promedio provisional del avance de las técnicas activas (0-100).

        La fórmula definitiva corresponde a HU-14 (sin diseño). Ver D8.
        """
        avances = list(
            self.seguimientos_tecnicas.filter(activa=True).values_list(
                'porcentaje_avance', flat=True
            )
        )
        if not avances:
            return None
        return round(sum(avances) / len(avances), 1)

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
        from apps.modelos.models import RevisionMetrica

        return RevisionMetrica.objects.filter(
            metrica_aplicada__modelo_aplicado__proyecto=self
        ).select_related(
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
    return registro


def tendencia_salud(proyecto, limite=6):
    """Devuelve los últimos registros de salud, del más antiguo al más nuevo."""
    registros = list(
        proyecto.registros_salud.order_by('-fecha')[:limite]
    )
    return list(reversed(registros))
