from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pages"
    verbose_name = "Tài khoản"
    
    def ready(self):
        """
        Import auth_admin để custom User và Group admin
        """
        import apps.pages.auth_admin
