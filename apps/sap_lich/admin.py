from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from .models import SapLichProxy
from .views import llm_scheduler_view, algo_scheduler_view

# Register a proxy model to make the app appear in sidebar
@admin.register(SapLichProxy)
class SapLichProxyAdmin(admin.ModelAdmin):
    
    def get_urls(self):
        """Add custom URLs for LLM and Algorithm schedulers"""
        urls = super().get_urls()
        custom_urls = [
            path('llm-scheduler/', self.admin_site.admin_view(llm_scheduler_view), name='sap_lich_llm_scheduler'),
            path('algo-scheduler/', self.admin_site.admin_view(algo_scheduler_view), name='sap_lich_algo_scheduler'),
        ]
        return custom_urls + urls
    
    # Override changelist view to show custom links
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'Công cụ sắp lịch'
        extra_context['custom_links'] = [
            {
                'name': 'Sắp lịch bằng LLM',
                'url': reverse('admin:sap_lich_llm_scheduler'),
                'icon': 'fas fa-robot',
                'description': 'Sử dụng AI để tạo thời khóa biểu tự động'
            },
            {
                'name': 'Sắp lịch bằng thuật toán',
                'url': reverse('admin:sap_lich_algo_scheduler'),
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


