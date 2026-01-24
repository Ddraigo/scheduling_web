from django.db import models


class UserProfile(models.Model):
    """Dummy model để tạo app 'Tài khoản' trong admin sidebar"""
    class Meta:
        verbose_name = "Hồ sơ người dùng"
        verbose_name_plural = "Hồ sơ người dùng"
        app_label = 'pages'
    
    def __str__(self):
        return "Hồ sơ người dùng"
