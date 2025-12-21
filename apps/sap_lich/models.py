from django.db import models

# Dummy model to make app appear in admin sidebar
class SapLich(models.Model):
    class Meta:
        managed = False  # Don't create database table
        verbose_name = "Sắp lịch"
        verbose_name_plural = "Sắp lịch"
        app_label = 'sap_lich'
