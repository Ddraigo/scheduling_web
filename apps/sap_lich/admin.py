from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import SapLichProxy

# Register a proxy model to make the app appear in sidebar
@admin.register(SapLichProxy)
class SapLichProxyAdmin(admin.ModelAdmin):
    # Override changelist view to show custom links
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'Công cụ sắp lịch'
        extra_context['custom_links'] = [
            {
                'name': 'Sắp lịch bằng LLM',
                'url': reverse('admin:llm_scheduler'),
                'icon': 'fas fa-robot',
                'description': 'Sử dụng AI để tạo thời khóa biểu tự động'
            },
            {
                'name': 'Sắp lịch bằng thuật toán',
                'url': reverse('admin:algo_scheduler'),
                'icon': 'fas fa-cogs',
                'description': 'Sử dụng thuật toán di truyền để tối ưu lịch học'
            }
        ]
        return super().changelist_view(request, extra_context)
    
    # Don't show add button
    def has_add_permission(self, request):
        return False
    
    # Don't allow delete
    def has_delete_permission(self, request, obj=None):
        return False
    
    # Make list view cleaner
    list_display = []
    
    class Media:
        css = {
            'all': ('admin/css/custom_sap_lich.css',)
        }


