"""
Views for Sap Lich (Scheduling) app
Provides admin interface for LLM and algorithm-based scheduling
"""

import json
import logging
from django.contrib import admin
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from apps.scheduling.models import DotXep
from apps.scheduling.algorithms.algorithms_runner import AlgorithmsRunner

logger = logging.getLogger(__name__)


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


@csrf_exempt
@require_http_methods(["POST"])
def algo_scheduler_run_api(request):
    """
    API endpoint để chạy thuật toán xếp lịch
    Expected POST data: { "ma_dot": "2025-2026_HK1", "time_limit": 30, "seed": 42 }
    """
    try:
        data = json.loads(request.body)
        ma_dot = data.get('ma_dot')
        time_limit = float(data.get('time_limit', 30.0))
        seed = int(data.get('seed', 42))

        if not ma_dot:
            return JsonResponse({
                'status': 'error',
                'message': 'Vui lòng cung cấp ma_dot'
            }, status=400)

        # Chạy runner
        logger.info(f"Bắt đầu xếp lịch cho {ma_dot}")
        runner = AlgorithmsRunner(ma_dot=ma_dot, seed=seed, time_limit=time_limit)
        result = runner.run()

        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'JSON không hợp lệ'
        }, status=400)
    except Exception as e:
        logger.exception(f"Lỗi API: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

