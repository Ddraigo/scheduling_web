"""
Views for Sap Lich (Scheduling) app
Provides admin interface for LLM and algorithm-based scheduling
"""

from django.contrib import admin
from django.shortcuts import render
from apps.scheduling.models import DotXep


def llm_scheduler_view(request):
    """Admin view for LLM-based scheduler"""
    try:
        periods = list(DotXep.objects.all().values('ma_dot', 'ten_dot', 'trang_thai'))
    except Exception:
        periods = []
    
    # Get admin site context with proper breadcrumb info
    context = {
        **admin.site.each_context(request),
        'periods': periods,
        'title': 'Sắp lịch bằng LLM',
        'site_title': admin.site.site_title,
        'site_header': admin.site.site_header,
        'has_permission': True,
        'is_nav_sidebar_enabled': True,
        'app_label': 'sap_lich',
        'opts': {
            'app_label': 'sap_lich',
            'model_name': 'scheduler',
            'verbose_name_plural': 'Sắp lịch',
        },
    }
    return render(request, 'admin/llm_scheduler.html', context)


def algo_scheduler_view(request):
    """Admin view for algorithm-based scheduler"""
    try:
        periods = list(DotXep.objects.all().values('ma_dot', 'ten_dot', 'trang_thai'))
    except Exception:
        periods = []
    
    # Get admin site context with proper breadcrumb info
    context = {
        **admin.site.each_context(request),
        'periods': periods,
        'title': 'Sắp lịch bằng thuật toán',
        'site_title': admin.site.site_title,
        'site_header': admin.site.site_header,
        'has_permission': True,
        'is_nav_sidebar_enabled': True,
        'app_label': 'sap_lich',
        'opts': {
            'app_label': 'sap_lich',
            'model_name': 'scheduler',
            'verbose_name_plural': 'Sắp lịch',
        },
    }
    return render(request, 'admin/algo_scheduler.html', context)
