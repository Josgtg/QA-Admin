from django.urls import path

from .views import CatalogoModelosView

app_name = 'modelos'

urlpatterns = [
    path('', CatalogoModelosView.as_view(), name='catalogo'),
]
