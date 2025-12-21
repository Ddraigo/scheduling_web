from django.contrib import admin
from .models import SapLich

# Register model to make app appear in sidebar (but hide the model itself)
@admin.register(SapLich)
class SapLichAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return True  # Show app in sidebar
    
    def has_view_permission(self, request, obj=None):
        return False  # Hide model link
