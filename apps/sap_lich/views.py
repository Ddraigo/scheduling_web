"""
Views for Sap Lich (Scheduling) app
Provides admin interface for LLM and algorithm-based scheduling
"""

import json
import logging
import random
import time
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
    API endpoint để chạy thuật toán xếp lịch với retry logic
    Expected POST data: { "ma_dot": "2025-2026_HK1", "time_limit": 300, "seed": null }
    
    Key changes:
    - Sử dụng random seed (không seed=42 cố định)
    - Tăng time_limit mặc định lên 300s (5 phút)
    - Thêm retry logic (tối đa 3 lần nếu fail)
    """
    try:
        data = json.loads(request.body)
        ma_dot = data.get('ma_dot')
        time_limit = float(data.get('time_limit', 300.0))  # Default 5 minutes
        seed = data.get('seed')  # None by default → random seed

        if not ma_dot:
            return JsonResponse({
                'status': 'error',
                'message': 'Vui lòng cung cấp ma_dot'
            }, status=400)

        # Nếu seed không cung cấp, dùng random seed
        if seed is None:
            seed = random.randint(1, 1_000_000)
        else:
            seed = int(seed)

        logger.info(f"Bắt đầu xếp lịch cho {ma_dot} (seed={seed}, time_limit={time_limit}s)")

        # Retry logic: nếu fail (depth < 216), thử lại với seed khác
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            if attempt > 0:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} - Thử lại với seed mới")
                seed = random.randint(1, 1_000_000)

            try:
                # Chạy runner
                runner = AlgorithmsRunner(ma_dot=ma_dot, seed=seed, time_limit=time_limit)
                result = runner.run()

                # Kiểm tra xem có thành công không
                if result['status'] == 'success':
                    logger.info(f"✅ Xếp lịch thành công ở attempt {attempt + 1}")
                    return JsonResponse(result)
                else:
                    # Fail nhưng không phải lỗi exception - có thể retry
                    depth = result.get('debug_info', {}).get('max_depth', 0)
                    if depth < 200:  # Nếu depth rất thấp, retry
                        logger.warning(f"Depth thấp ({depth}/216), retry với seed mới")
                        last_error = result
                        continue
                    else:
                        # Depth khá cao, không retry
                        logger.error(f"Xếp lịch fail với depth {depth}")
                        return JsonResponse(result)

            except Exception as e:
                logger.exception(f"Attempt {attempt + 1} failed: {e}")
                last_error = str(e)
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                    continue
                else:
                    # Lần cuối fail
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Xếp lịch thất bại sau {max_retries} lần: {str(e)}',
                        'attempts': max_retries
                    }, status=500)

        # Nếu tất cả attempts đều fail
        logger.error(f"Tất cả {max_retries} attempts đều thất bại")
        if isinstance(last_error, dict):
            return JsonResponse(last_error)
        else:
            return JsonResponse({
                'status': 'error',
                'message': f'Xếp lịch thất bại sau {max_retries} lần',
                'last_error': str(last_error),
                'attempts': max_retries
            }, status=500)

    except json.JSONDecodeError:
        logger.error("JSON không hợp lệ")
        return JsonResponse({
            'status': 'error',
            'message': 'JSON không hợp lệ'
        }, status=400)
    except Exception as e:
        logger.exception(f"Lỗi API không dự báo: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Lỗi: {str(e)}'
        }, status=500)

