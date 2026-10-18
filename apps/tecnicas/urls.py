from django.urls import path

from .views import SeguirTecnicaView

app_name = 'tecnicas'

urlpatterns = [
    path('seguimiento/', SeguirTecnicaView.as_view(), name='seguimiento'),
]
