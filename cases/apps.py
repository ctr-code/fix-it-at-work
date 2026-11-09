from django.apps import AppConfig


class CasesConfig(AppConfig):
    name = 'cases'
    verbose_name = 'Request to Resolution'

    def ready(self):
        from . import signals  # noqa: F401
