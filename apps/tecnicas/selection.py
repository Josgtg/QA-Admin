SESSION_KEY = 'ultimo_proyecto_id'


def seleccionar_proyecto(request, proyecto):
    if proyecto is None:
        request.session.pop(SESSION_KEY, None)
        return
    request.session[SESSION_KEY] = proyecto.pk


def obtener_proyecto_seleccionado(request):
    from .models import Proyecto

    proyecto_id = request.session.get(SESSION_KEY)
    if proyecto_id:
        proyecto = Proyecto.objects.filter(pk=proyecto_id).first()
        if proyecto is not None:
            return proyecto
    return Proyecto.objects.order_by('pk').first()
