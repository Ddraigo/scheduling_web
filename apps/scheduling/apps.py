from django.apps import AppConfig


class SchedulingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scheduling'
    verbose_name = 'Xem và Quản lý TKB'  # Menu for viewing and managing schedules
    
    def ready(self):
        """Import signals and perform startup tasks"""
        pass
