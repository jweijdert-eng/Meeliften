"""App Configuration"""

from django.apps import AppConfig

from meeliften import __version__


class MeeliftenConfig(AppConfig):
    name = "meeliften"
    label = "meeliften"
    verbose_name = f"Meeliften v{__version__}"
