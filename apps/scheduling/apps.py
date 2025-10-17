from django.apps import AppConfig


class SchedulingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scheduling'
    verbose_name = 'Scheduling System'
    
    def ready(self):
        """Import signals and perform startup tasks"""
        pass
