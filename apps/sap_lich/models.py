from django.db import models
from apps.scheduling.models import DotXep

# Proxy model to make the app appear in admin sidebar
class SapLichProxy(DotXep):
    class Meta:
        proxy = True
        verbose_name = "Công cụ sắp lịch"
        verbose_name_plural = "Công cụ sắp lịch"

