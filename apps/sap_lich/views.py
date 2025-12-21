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
            'model_name': 'saplich',
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
            'model_name': 'saplich',
            'verbose_name_plural': 'Sắp lịch',
        },
    }
    return render(request, 'admin/algo_scheduler.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def algo_scheduler_run_api(request):
    """
    API endpoint để chạy thuật toán xếp lịch với improved algorithm (fixed teacher preference bug)
    
    Expected POST data:
    {
        "ma_dot": "2025-2026_HK1",
        "strategy": "TS",  // "TS" (Tabu Search) hoặc "SA" (Simulated Annealing)
        "init_method": "greedy-cprop",  // "greedy-cprop" hoặc "random-repair"
        "time_limit": 180,  // seconds (default 180s = 3 phút)
        "seed": 42,  // optional, random seed
        "save_to_db": true  // optional, lưu vào ThoiKhoaBieu hay không
    }
    
    Returns:
    {
        "status": "success",
        "ma_dot": "2025-2026_HK1",
        "initial_cost": 145,
        "final_cost": 89,
        "improvement": 56,
        "improvement_percent": 38.6,
        "time_elapsed": 180.5,
        "breakdown": {
            "room_capacity": 0,
            "min_working_days": 0,
            "curriculum_compactness": 45,
            "lecture_consecutiveness": 0,
            "room_stability": 0,
            "teacher_preferences": 44
        },
        "sol_file": "/path/to/solution.sol",
        "saved_to_db": true,
        "message": "Xếp lịch thành công!"
    }
    """
    try:
        from apps.scheduling.algorithms.algorithms_runner import AlgorithmRunner
        
        data = json.loads(request.body)
        ma_dot = data.get('ma_dot')
        strategy = data.get('strategy', 'TS').upper()
        init_method = data.get('init_method', 'greedy-cprop')
        time_limit = float(data.get('time_limit', 180))
        seed = data.get('seed', 42)
        save_to_db = data.get('save_to_db', True)

        # Validation
        if not ma_dot:
            return JsonResponse({
                'status': 'error',
                'message': 'Vui lòng cung cấp ma_dot'
            }, status=400)

        if strategy not in ['TS', 'SA']:
            return JsonResponse({
                'status': 'error',
                'message': 'Strategy không hợp lệ. Phải là "TS" hoặc "SA"'
            }, status=400)

        if init_method not in ['greedy-cprop', 'random-repair']:
            return JsonResponse({
                'status': 'error',
                'message': 'Init method không hợp lệ. Phải là "greedy-cprop" hoặc "random-repair"'
            }, status=400)

        logger.info(f"🚀 Bắt đầu xếp lịch cho {ma_dot}")
        logger.info(f"   Strategy: {strategy}, Init: {init_method}, Time: {time_limit}s, Seed: {seed}")

        # Step 1: Initialize runner
        runner = AlgorithmRunner(ma_dot=ma_dot, seed=seed)

        # Step 2: Prepare data (export DB to CTT)
        logger.info("📊 Step 1: Chuẩn bị dữ liệu (export DB sang CTT)")
        if not runner.prepare_data():
            return JsonResponse({
                'status': 'error',
                'message': 'Không thể chuẩn bị dữ liệu. Kiểm tra xem DotXep có tồn tại và có dữ liệu hợp lệ không.'
            }, status=400)

        # Step 3: Run optimization
        logger.info("🔧 Step 2: Chạy thuật toán optimization")
        result = runner.run_optimization(
            strategy=strategy,
            init_method=init_method,
            time_limit=time_limit
        )

        if not result or not result.get('success'):
            error_msg = result.get('error', 'Thuật toán thất bại') if result else 'Lỗi không xác định'
            logger.error(f"❌ Optimization failed: {error_msg}")
            return JsonResponse({
                'status': 'error',
                'message': error_msg
            }, status=500)

        # Step 4: Save to database (nếu requested)
        if save_to_db:
            logger.info("💾 Step 3: Lưu kết quả vào database")
            
            # Reconstruct assignments from formatted result
            assignments = {}
            for lecture_id_str, assignment_data in result.get('assignments', {}).items():
                lecture_id = int(lecture_id_str)
                period = assignment_data['period_absolute']
                
                # Find room_idx from room_id
                room_id = assignment_data['room_id']
                room_idx = None
                for idx, room in enumerate(runner.instance.rooms):
                    if room.id == room_id:
                        room_idx = idx
                        break
                
                if room_idx is not None:
                    assignments[lecture_id] = (period, room_idx)
            
            saved = runner.save_to_database(assignments)
            result['saved_to_db'] = saved
            
            if not saved:
                logger.warning("⚠️  Lưu vào database thất bại, nhưng optimization thành công")
                result['warning'] = 'Lưu vào database thất bại'
        else:
            result['saved_to_db'] = False

        # Format response
        logger.info(f"✅ Xếp lịch hoàn tất!")
        logger.info(f"   Initial cost: {result['initial_cost']}")
        logger.info(f"   Final cost: {result['final_cost']}")
        logger.info(f"   Improvement: {result['improvement']} ({result['improvement_percent']:.1f}%)")
        logger.info(f"   Teacher preferences: {result['breakdown']['teacher_preferences']} violations")

        # Convert to JsonResponse format
        response = {
            'status': 'success',
            'ma_dot': result['ma_dot'],
            'initial_cost': result['initial_cost'],
            'final_cost': result['final_cost'],
            'improvement': result['improvement'],
            'improvement_percent': round(result['improvement_percent'], 2),
            'time_elapsed': round(result['time_elapsed'], 2),
            'breakdown': result['breakdown'],
            'sol_file': result['sol_file'],
            'saved_to_db': result['saved_to_db'],
            'message': f'Xếp lịch thành công! Cost giảm từ {result["initial_cost"]} xuống {result["final_cost"]} ({result["improvement_percent"]:.1f}%)',
            'details': {
                'strategy': strategy,
                'init_method': init_method,
                'seed': seed,
                'lectures_scheduled': len(result.get('assignments', {}))
            }
        }

        if 'warning' in result:
            response['warning'] = result['warning']

        return JsonResponse(response)

    except json.JSONDecodeError:
        logger.error("JSON không hợp lệ")
        return JsonResponse({
            'status': 'error',
            'message': 'JSON không hợp lệ'
        }, status=400)
    except Exception as e:
        logger.exception(f"Lỗi API: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Lỗi: {str(e)}'
        }, status=500)

