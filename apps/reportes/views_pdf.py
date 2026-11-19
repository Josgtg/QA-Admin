"""Vistas para exportación de reportes PDF."""

from django.http import FileResponse, Http404, HttpRequest
from django.shortcuts import get_object_or_404
from django.views import View

from apps.reportes.models import Proyecto
from apps.reportes.services.pdf import ReportePDFService


class ExportarPDFView(View):
    """Vista para descargar el reporte PDF del proyecto."""

    def get(self, request: HttpRequest, proyecto_id: int) -> FileResponse:
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)

        service = ReportePDFService(proyecto)
        buffer = service.generar()

        # Nombre del archivo: reporte-{nombre_proyecto}-{fecha}.pdf
        from datetime import date

        fecha_str = date.today().strftime("%Y%m%d")
        nombre_archivo = f"reporte-{proyecto.nombre}-{fecha_str}.pdf".replace(" ", "_")

        response = FileResponse(
            buffer,
            content_type="application/pdf",
            as_attachment=True,
            filename=nombre_archivo,
        )
        return response