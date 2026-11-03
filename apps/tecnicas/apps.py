from django.apps import AppConfig


class TecnicasConfig(AppConfig):
    name = 'apps.tecnicas'

    def ready(self):
        from . import signals  # noqa: F401
