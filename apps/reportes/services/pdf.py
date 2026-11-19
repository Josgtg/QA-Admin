"""Servicio de generación de reportes PDF para proyectos de calidad.

Usa WeasyPrint (HTML → PDF) con templates Django para facilitar el estilo.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from typing import Any

from django.template.loader import render_to_string
from django.templatetags.static import static
from weasyprint import HTML

from apps.modelos.models import Metrica, MetricaAplicada, RevisionMetrica
from apps.reportes.models import (
    DetalleSalud,
    MiembroProyecto,
    Proyecto,
    RegistroSalud,
)
from apps.tecnicas.models import Evidencia, SeguimientoPaso, SeguimientoTecnica


@dataclass(frozen=True)
class MetricaReporte:
    """Métrica con sus datos para el reporte."""

    nombre: str
    caracteristica: str
    meta: str
    ultimo_valor: float | None
    unidad: str
    estado: str  # 'Cumple', 'No cumple', 'Sin medición'
    cumple: bool
    tiene_evidencia: bool
    fecha_ultima_revision: date | None


@dataclass(frozen=True)
class PasoReporte:
    """Paso de técnica para el reporte."""

    orden: int
    instruccion: str
    completado: bool
    tiene_evidencia: bool
    fecha_completado: datetime | None
    comentario: str


@dataclass(frozen=True)
class TecnicaReporte:
    """Técnica con sus pasos para el reporte."""

    nombre: str
    dimension: str
    tipo_control: str
    porcentaje_avance: float
    esta_completada: bool
    pasos: tuple[PasoReporte, ...]


@dataclass(frozen=True)
class ItemAtencion:
    """Elemento que necesita atención (métrica no cumplida o técnica pendiente)."""

    tipo: str  # 'METRICA' o 'TECNICA'
    nombre: str
    detalle: str
    severidad: float  # 0-100, mayor = más urgente


@dataclass(frozen=True)
class DatosReportePDF:
    """Todos los datos necesarios para el PDF, recopilados en una sola pasada."""

    proyecto: Proyecto
    fecha_generacion: date
    indice_salud: float | None
    tono_salud: str
    riesgo_salud: str
    metricas: tuple[MetricaReporte, ...]
    tecnicas: tuple[TecnicaReporte, ...]
    items_atencion: tuple[ItemAtencion, ...]
    ultima_actualizacion: datetime | None
    equipo: tuple[MiembroProyecto, ...]

    @classmethod
    def recopilar(cls, proyecto: Proyecto) -> "DatosReportePDF":
        """Recopila todos los datos del proyecto en una sola pasada consistente."""
        # Índice de salud y tonos
        indice_salud = proyecto.indice_salud()
        tono_salud, riesgo_salud = cls._calcular_tono_riesgo(indice_salud)

        # Equipo activo
        equipo = tuple(proyecto.equipo_activo())

        # Métricas
        metricas = cls._recopilar_metricas(proyecto)

        # Técnicas
        tecnicas = cls._recopilar_tecnicas(proyecto)

        # Items de atención (combinados: métricas no cumplen primero, luego técnicas pendientes)
        items_atencion = cls._construir_items_atencion(metricas, tecnicas)

        # Última actualización (del último registro de salud)
        ultimo_registro = proyecto.registros_salud.order_by("-fecha").first()
        ultima_actualizacion = ultimo_registro.actualizado if ultimo_registro else None

        return cls(
            proyecto=proyecto,
            fecha_generacion=date.today(),
            indice_salud=indice_salud,
            tono_salud=tono_salud,
            riesgo_salud=riesgo_salud,
            metricas=metricas,
            tecnicas=tecnicas,
            items_atencion=items_atencion,
            ultima_actualizacion=ultima_actualizacion,
            equipo=equipo,
        )

    @staticmethod
    def _calcular_tono_riesgo(indice: float | None) -> tuple[str, str]:
        """Calcula el tono de color y nivel de riesgo según el índice."""
        if indice is None:
            return "gray", "Sin datos"
        if indice >= 80:
            return "green", "Bajo"
        if indice >= 60:
            return "amber", "Medio"
        if indice >= 40:
            return "orange", "Alto"
        return "red", "Crítico"

    @classmethod
    def _recopilar_metricas(cls, proyecto: Proyecto) -> tuple[MetricaReporte, ...]:
        """Recopila todas las métricas aplicadas con su estado actual."""
        aplicado = proyecto.modelo_aplicado_vigente()
        if aplicado is None:
            return ()

        metricas_aplicadas = aplicado.metricas_aplicadas().filter(activa=True).select_related(
            "metrica__caracteristica"
        )

        resultado = []
        for aplicada in metricas_aplicadas:
            metrica = aplicada.metrica
            ultima_revision = metrica.ultima_revision(proyecto)
            ultimo_valor = ultima_revision.valor if ultima_revision else None
            cumple = metrica.esta_aceptada(proyecto)
            tiene_evidencia = ultima_revision.tiene_evidencia() if ultima_revision else False

            # Meta legible desde la instantánea
            if aplicada.tipo_umbral == "MINIMO":
                meta_texto = f"≥ {aplicada.umbral} {metrica.unidad}"
            else:
                meta_texto = f"≤ {aplicada.umbral} {metrica.unidad}"

            if ultima_revision is None:
                estado = "Sin medición"
            elif cumple:
                estado = "Cumple"
            else:
                estado = "No cumple"

            resultado.append(
                MetricaReporte(
                    nombre=metrica.nombre,
                    caracteristica=metrica.caracteristica.nombre,
                    meta=meta_texto,
                    ultimo_valor=ultimo_valor,
                    unidad=metrica.unidad,
                    estado=estado,
                    cumple=cumple,
                    tiene_evidencia=tiene_evidencia,
                    fecha_ultima_revision=ultima_revision.fecha if ultima_revision else None,
                )
            )

        return tuple(resultado)

    @classmethod
    def _recopilar_tecnicas(cls, proyecto: Proyecto) -> tuple[TecnicaReporte, ...]:
        """Recopila todas las técnicas activas con sus pasos."""
        seguimientos = proyecto.seguimientos_activos().select_related("tecnica")

        resultado = []
        for seguimiento in seguimientos:
            tecnica = seguimiento.tecnica
            pasos_seguimiento = seguimiento.pasos.select_related("paso", "evidencia").order_by(
                "paso__orden"
            )

            pasos = []
            for sp in pasos_seguimiento:
                evidencia = sp.evidencia_segura()
                pasos.append(
                    PasoReporte(
                        orden=sp.paso.orden,
                        instruccion=sp.paso.instruccion,
                        completado=sp.completado,
                        tiene_evidencia=evidencia is not None,
                        fecha_completado=sp.fecha_completado,
                        comentario=sp.comentario,
                    )
                )

            resultado.append(
                TecnicaReporte(
                    nombre=tecnica.nombre,
                    dimension=tecnica.get_dimension_display(),
                    tipo_control=tecnica.get_tipo_control_display(),
                    porcentaje_avance=seguimiento.calcular_porcentaje_avance(),
                    esta_completada=seguimiento.esta_completada(),
                    pasos=tuple(pasos),
                )
            )

        return tuple(resultado)

    @classmethod
    def _construir_items_atencion(
        cls, metricas: tuple[MetricaReporte, ...], tecnicas: tuple[TecnicaReporte, ...]
    ) -> tuple[ItemAtencion, ...]:
        """Construye lista combinada de items que necesitan atención.

        Métricas no cumplidas primero (ordenadas por desviación), luego técnicas pendientes.
        """
        items = []

        # Métricas que no cumplen
        for m in metricas:
            if m.estado == "No cumple" and m.ultimo_valor is not None:
                # Calcular desviación aproximada para severidad
                # Como no tenemos el umbral exacto aquí, usamos una heurística
                severidad = 80  # Base alta para métricas no cumplidas
                items.append(
                    ItemAtencion(
                        tipo="METRICA",
                        nombre=m.nombre,
                        detalle=f"Valor actual: {m.ultimo_valor} {m.unidad} (meta: {m.meta})",
                        severidad=severidad,
                    )
                )
            elif m.estado == "Sin medición":
                items.append(
                    ItemAtencion(
                        tipo="METRICA",
                        nombre=m.nombre,
                        detalle="No hay mediciones registradas",
                        severidad=60,
                    )
                )

        # Técnicas con pasos pendientes
        for t in tecnicas:
            if not t.esta_completada:
                pasos_pendientes = sum(1 for p in t.pasos if not p.completado)
                total = len(t.pasos)
                # Severidad inversa al avance: menos avance = más severo
                severidad = max(20, 100 - t.porcentaje_avance)
                items.append(
                    ItemAtencion(
                        tipo="TECNICA",
                        nombre=t.nombre,
                        detalle=f"{pasos_pendientes} de {total} pasos pendientes ({t.porcentaje_avance:.0f}% completado)",
                        severidad=severidad,
                    )
                )

        # Ordenar: métricas primero (por severidad desc), luego técnicas (por severidad desc)
        items.sort(key=lambda x: (x.tipo != "METRICA", -x.severidad))

        return tuple(items)


class ReportePDFService:
    """Genera el reporte PDF del proyecto usando WeasyPrint."""

    def __init__(self, proyecto: Proyecto):
        self.proyecto = proyecto
        self.datos: DatosReportePDF | None = None

    def generar(self) -> BytesIO:
        """Genera el PDF y devuelve un BytesIO con el contenido."""
        self.datos = DatosReportePDF.recopilar(self.proyecto)
        html = self._renderizar_html(self.datos)
        return self._html_a_pdf(html)

    def _renderizar_html(self, datos: DatosReportePDF) -> str:
        """Renderiza el template HTML con los datos."""
        context = {
            "datos": datos,
            "proyecto": datos.proyecto,
            "fecha_generacion": datos.fecha_generacion,
            "indice_salud": datos.indice_salud,
            "tono_salud": datos.tono_salud,
            "riesgo_salud": datos.riesgo_salud,
            "metricas": datos.metricas,
            "tecnicas": datos.tecnicas,
            "items_atencion": datos.items_atencion,
            "ultima_actualizacion": datos.ultima_actualizacion,
            "equipo": datos.equipo,
        }
        return render_to_string("reportes/pdf/reporte.html", context)

    def _html_a_pdf(self, html: str) -> BytesIO:
        """Convierte HTML a PDF usando WeasyPrint."""
        buffer = BytesIO()
        # base_url permite resolver rutas relativas (static, media)
        HTML(string=html, base_url="/").write_pdf(buffer)
        buffer.seek(0)
        return buffer