"""
Views for Sap Lich (Scheduling) app
Provides admin interface for LLM and algorithm-based scheduling
"""

import json
import logging
import random
import time
from datetime import datetime, timedelta
from django.contrib import admin
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Prefetch
from apps.scheduling.models import (
    DotXep, ThoiKhoaBieu, GiangVien, PhongHoc, 
    TimeSlot, KhungTG, PhanCong, LopMonHoc, MonHoc
)

logger = logging.getLogger(__name__)


def llm_scheduler_view(request):
    """Admin view for LLM Chatbot Assistant"""
    try:
        periods = list(DotXep.objects.all().values('ma_dot', 'ten_dot', 'trang_thai'))
    except Exception:
        periods = []
    
    # Get admin site context with proper breadcrumb info
    context = {
        **admin.site.each_context(request),
        'periods': periods,
        'title': 'Trợ lý AI - Hỏi đáp Lịch học',
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
        'current_time': datetime.now().strftime('%H:%M'),
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


@require_http_methods(["GET"])
def algo_scheduler_view_result_api(request):
    """
    API endpoint để xem kết quả thời khóa biểu đã được lưu vào database
    
    Expected GET parameters:
    - ma_dot: Mã đợt xếp lịch
    
    Returns:
    {
        "status": "success",
        "ma_dot": "2025-2026_HK1",
        "ten_dot": "Học kỳ 1 năm 2025-2026",
        "total_schedules": 150,
        "schedules": [
            {
                "ma_lop": "CTTT01",
                "ten_lop": "Cấu trúc dữ liệu",
                "ma_gv": "GV001",
                "ten_gv": "Nguyễn Văn A",
                "ma_phong": "A101",
                "thu": 2,
                "ca": 1,
                "tuan_hoc": 1
            },
            ...
        ]
    }
    """
    try:
        ma_dot = request.GET.get('ma_dot')
        
        if not ma_dot:
            return JsonResponse({
                'status': 'error',
                'message': 'Vui lòng cung cấp ma_dot'
            }, status=400)
        
        # Kiểm tra đợt xếp có tồn tại không
        try:
            dot_xep = DotXep.objects.get(ma_dot=ma_dot)
        except DotXep.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Không tìm thấy đợt xếp {ma_dot}'
            }, status=404)
        
        # Lấy tất cả thời khóa biểu của đợt
        from apps.scheduling.models import ThoiKhoaBieu, PhanCong
        
        tkb_list = ThoiKhoaBieu.objects.filter(
            ma_dot=dot_xep
        ).select_related(
            'ma_lop',
            'ma_lop__ma_mon_hoc',
            'ma_phong',
            'time_slot_id__ca'
        ).order_by('time_slot_id__thu', 'time_slot_id__ca__ma_khung_gio')
        
        # Lấy mapping từ ma_lop sang giảng viên qua PhanCong
        lop_to_gv = {}
        for pc in PhanCong.objects.filter(ma_dot=dot_xep).select_related('ma_lop', 'ma_gv'):
            lop_to_gv[pc.ma_lop.ma_lop] = pc.ma_gv
        
        # Format kết quả
        schedules = []
        for tkb in tkb_list:
            # Lấy thông tin giảng viên từ mapping
            gv = lop_to_gv.get(tkb.ma_lop.ma_lop)
            
            schedules.append({
                'id': tkb.ma_tkb,
                'ma_lop': tkb.ma_lop.ma_lop,
                'ten_lop': f"{tkb.ma_lop.ma_mon_hoc.ten_mon_hoc} (Nhóm {tkb.ma_lop.nhom_mh})",
                'ma_mon': tkb.ma_lop.ma_mon_hoc.ma_mon_hoc,
                'ten_mon': tkb.ma_lop.ma_mon_hoc.ten_mon_hoc,
                'ma_gv': gv.ma_gv if gv else 'N/A',
                'ten_gv': gv.ten_gv if gv else 'Chưa phân công',
                'ma_phong': tkb.ma_phong.ma_phong if tkb.ma_phong else 'N/A',
                'suc_chua': tkb.ma_phong.suc_chua if tkb.ma_phong and tkb.ma_phong.suc_chua else 0,
                'loai_phong': tkb.ma_phong.loai_phong if tkb.ma_phong else 'N/A',
                'thu': tkb.time_slot_id.thu,
                'ca': tkb.time_slot_id.ca.ma_khung_gio,
                'gio_bat_dau': str(tkb.time_slot_id.ca.gio_bat_dau),
                'gio_ket_thuc': str(tkb.time_slot_id.ca.gio_ket_thuc),
                'tuan_hoc': tkb.tuan_hoc if tkb.tuan_hoc else '1',
            })
        
        logger.info(f"Retrieved {len(schedules)} schedules for {ma_dot}")
        
        # Chạy validator để lấy breakdown costs từ file .sol đã lưu
        breakdown = None
        initial_cost = None
        final_cost = None
        
        try:
            from pathlib import Path
            import subprocess
            import re
            from django.conf import settings
            
            # Path to .ctt and .sol files
            ctt_file = Path(settings.BASE_DIR) / 'output' / 'test_web_algo' / 'ctt_files' / f'{ma_dot}.ctt'
            sol_file = Path(settings.BASE_DIR) / 'output' / 'test_web_algo' / f'solution_{ma_dot}.sol'
            
            if ctt_file.exists() and sol_file.exists():
                # Run validator
                result = subprocess.run(
                    ['python', 'apps/scheduling/utils/validator.py', str(ctt_file), str(sol_file)],
                    capture_output=True,
                    text=True,
                    cwd=settings.BASE_DIR
                )
                
                if result.returncode == 0:
                    output = result.stdout
                    
                    # Parse costs from validator output
                    breakdown = {}
                    cost_patterns = {
                        'min_working_days': r'Cost of MinWorkingDays \(soft\)\s*:\s*(\d+)',
                        'curriculum_compactness': r'Cost of CurriculumCompactness \(soft\)\s*:\s*(\d+)',
                        'lecture_consecutiveness': r'Cost of LectureConsecutiveness \(soft\)\s*:\s*(\d+)',
                        'room_stability': r'Cost of RoomStability \(soft\)\s*:\s*(\d+)',
                        'teacher_lecture_consolidation': r'Cost of TeacherLectureConsolidation \(soft - extended\)\s*:\s*(\d+)',
                        'teacher_working_days': r'Cost of TeacherWorkingDays \(soft - extended\)\s*:\s*(\d+)',
                        'teacher_preferences': r'Cost of TeacherPreferences \(soft - extended\)\s*:\s*(\d+)',
                        'room_capacity': r'Cost of RoomCapacity \(soft\)\s*:\s*(\d+)',
                    }
                    
                    for key, pattern in cost_patterns.items():
                        match = re.search(pattern, output)
                        if match:
                            breakdown[key] = int(match.group(1))
                    
                    # Parse total cost
                    total_match = re.search(r'Total Cost = (\d+)', output)
                    if total_match:
                        final_cost = int(total_match.group(1))
                        initial_cost = final_cost  # Không có initial cost khi load từ DB
                    
                    logger.info(f"Validator breakdown: {breakdown}")
                else:
                    logger.warning(f"Validator failed with code {result.returncode}: {result.stderr}")
        except Exception as e:
            logger.warning(f"Could not run validator: {e}")
        
        response = {
            'status': 'success',
            'ma_dot': ma_dot,
            'ten_dot': dot_xep.ten_dot,
            'total_schedules': len(schedules),
            'schedules': schedules
        }
        
        # Add breakdown if available
        if breakdown:
            response['breakdown'] = breakdown
            response['final_cost'] = final_cost
            response['initial_cost'] = initial_cost
        
        return JsonResponse(response)
    
    except Exception as e:
        logger.exception(f"Lỗi khi xem kết quả: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Lỗi: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def algo_scheduler_get_weights_api(request):
    """
    API endpoint để lấy trọng số của các ràng buộc cho đợt xếp lịch
    
    Expected GET parameters:
    - ma_dot: Mã đợt xếp lịch (optional)
    
    Returns:
    {
        "status": "success",
        "weights": {
            "RBM-001": {"name": "...", "weight": 2.5, "source": "dot"},
            "RBM-002": {"name": "...", "weight": 1.0, "source": "global"},
            ...
        }
    }
    """
    try:
        from apps.scheduling.algorithms.weight_loader import WeightLoader
        from apps.scheduling.models import RangBuocMem, RangBuocTrongDot
        
        ma_dot = request.GET.get('ma_dot')
        
        # Load weights using WeightLoader (3-tier priority)
        weights = WeightLoader.load_weights(ma_dot)
        
        # Get mapping from RBM codes to friendly names
        rang_buoc_map = {}
        for rb in RangBuocMem.objects.all():
            rang_buoc_map[rb.ma_rang_buoc] = rb.ten_rang_buoc
        
        # Get dot-specific overrides if ma_dot provided
        dot_overrides = set()
        if ma_dot:
            dot_overrides = set(
                RangBuocTrongDot.objects.filter(ma_dot=ma_dot)
                .values_list('ma_rang_buoc__ma_rang_buoc', flat=True)
            )
        
        # Map internal keys back to RBM codes with weight values
        # Reverse lookup from CONSTRAINT_MAPPING
        from apps.scheduling.algorithms.weight_loader import CONSTRAINT_MAPPING
        rbm_weights = {}
        
        for rbm_code, internal_key in CONSTRAINT_MAPPING.items():
            if internal_key in weights:
                source = 'dot' if rbm_code in dot_overrides else 'global'
                rbm_weights[rbm_code] = {
                    'name': rang_buoc_map.get(rbm_code, internal_key),
                    'weight': weights[internal_key],
                    'source': source
                }
        
        return JsonResponse({
            'status': 'success',
            'weights': rbm_weights
        })
    
    except Exception as e:
        logger.exception(f"Lỗi khi lấy weights: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Lỗi: {str(e)}'
        }, status=500)


def thoikhoabieu_view(request):
    """
    View hiển thị thời khóa biểu với nhiều góc nhìn và dạng hiển thị
    - Góc nhìn: theo giáo viên, theo phòng
    - Dạng hiển thị: tổng quát (tất cả tuần), chi tiết (theo tuần)
    """
    # Lấy các tham số từ request
    view_type = request.GET.get('view', 'teacher')  # 'teacher' hoặc 'room'
    display_mode = request.GET.get('mode', 'general')  # 'general' hoặc 'weekly'
    week_number = int(request.GET.get('week', 1))  # Tuần hiện tại (1-15)
    ma_dot = request.GET.get('ma_dot', '')  # Đợt xếp lịch
    selected_id = request.GET.get('id', '')  # Mã GV hoặc mã phòng
    
    # Lấy danh sách đợt xếp lịch
    dot_list = DotXep.objects.all().order_by('-ma_dot')
    
    # Nếu không có ma_dot, lấy đợt mới nhất
    if not ma_dot and dot_list.exists():
        ma_dot = dot_list.first().ma_dot
    
    # Khởi tạo context
    context = {
        **admin.site.each_context(request),
        'title': 'Thời Khóa Biểu',
        'view_type': view_type,
        'display_mode': display_mode,
        'week_number': week_number,
        'ma_dot': ma_dot,
        'selected_id': selected_id,
        'dot_list': dot_list,
        'weeks': range(1, 16),  # 15 tuần
        'app_label': 'sap_lich',
        'opts': {
            'app_label': 'sap_lich',
            'model_name': 'thoikhoabieu',
            'verbose_name_plural': 'Thời khóa biểu',
        },
    }
    
    if not ma_dot:
        return render(request, 'admin/thoikhoabieu.html', context)
    
    try:
        dot_xep = DotXep.objects.get(ma_dot=ma_dot)
        context['dot_xep'] = dot_xep
        
        if view_type == 'teacher':
            # Lấy danh sách giáo viên CÓ LỊCH DẠY THỰC TẾ trong đợt này
            # Lấy từ TKB thông qua PhanCong
            gv_co_lich = PhanCong.objects.filter(
                ma_dot=dot_xep,
                ma_gv__isnull=False,
                ma_lop__tkb_list__ma_dot=dot_xep  # Lớp phải có TKB
            ).select_related('ma_gv').values(
                'ma_gv__ma_gv', 'ma_gv__ten_gv'
            ).distinct().order_by('ma_gv__ma_gv')
            
            teachers = [{'ma_gv': gv['ma_gv__ma_gv'], 'ten_gv': gv['ma_gv__ten_gv']} 
                       for gv in gv_co_lich]
            context['teachers'] = teachers
            
            # Nếu chưa chọn GV, chọn GV đầu tiên
            if not selected_id and teachers:
                selected_id = teachers[0]['ma_gv']
                context['selected_id'] = selected_id
            
            if selected_id:
                try:
                    gv = GiangVien.objects.get(ma_gv=selected_id)
                    context['selected_teacher'] = gv
                    
                    # Lấy các lớp mà GV dạy trong đợt này
                    lop_gv = PhanCong.objects.filter(
                        ma_dot=dot_xep, ma_gv=gv
                    ).values_list('ma_lop__ma_lop', flat=True)
                    
                    # Lấy TKB của các lớp đó
                    tkb_list = ThoiKhoaBieu.objects.filter(
                        ma_dot=dot_xep,
                        ma_lop__ma_lop__in=lop_gv
                    ).select_related(
                        'ma_lop', 'ma_lop__ma_mon_hoc', 'ma_phong', 
                        'time_slot_id', 'time_slot_id__ca'
                    ).order_by('time_slot_id__thu', 'time_slot_id__ca')
                    
                    schedule_data = build_schedule_data(
                        tkb_list, display_mode, week_number, dot_xep
                    )
                    context['schedule_data'] = schedule_data
                    
                    # Thêm ngày tháng cho từng thứ nếu ở chế độ weekly
                    if display_mode == 'weekly':
                        context['week_dates'] = get_week_dates(dot_xep, week_number)
                except GiangVien.DoesNotExist:
                    context['error'] = f'Không tìm thấy giáo viên {selected_id}'
                
        else:  # view_type == 'room'
            # Lấy danh sách phòng CÓ LỊCH SỬ DỤNG trong đợt này
            rooms = PhongHoc.objects.filter(
                tkb_list__ma_dot=dot_xep
            ).distinct().order_by('ma_phong')
            context['rooms'] = rooms
            
            # Nếu chưa chọn phòng, chọn phòng đầu tiên
            if not selected_id and rooms.exists():
                selected_id = rooms.first().ma_phong
                context['selected_id'] = selected_id
            
            if selected_id:
                try:
                    phong = PhongHoc.objects.get(ma_phong=selected_id)
                    context['selected_room'] = phong
                    
                    # Lấy TKB của phòng
                    tkb_list = ThoiKhoaBieu.objects.filter(
                        ma_dot=dot_xep,
                        ma_phong=phong
                    ).select_related(
                        'ma_lop', 'ma_lop__ma_mon_hoc', 'ma_phong',
                        'time_slot_id', 'time_slot_id__ca'
                    ).order_by('time_slot_id__thu', 'time_slot_id__ca')
                    
                    schedule_data = build_schedule_data(
                        tkb_list, display_mode, week_number, dot_xep
                    )
                    context['schedule_data'] = schedule_data
                    
                    # Thêm ngày tháng cho từng thứ nếu ở chế độ weekly
                    if display_mode == 'weekly':
                        context['week_dates'] = get_week_dates(dot_xep, week_number)
                except PhongHoc.DoesNotExist:
                    context['error'] = f'Không tìm thấy phòng {selected_id}'
                except PhongHoc.DoesNotExist:
                    context['error'] = f'Không tìm thấy phòng {selected_id}'
        
    except DotXep.DoesNotExist:
        context['error'] = f'Không tìm thấy đợt xếp lịch {ma_dot}'
    except Exception as e:
        logger.exception(f"Lỗi khi hiển thị TKB: {e}")
        context['error'] = f'Lỗi: {str(e)}'
    
    return render(request, 'admin/thoikhoabieu.html', context)


def build_schedule_data(tkb_list, display_mode, week_number, dot_xep):
    """
    Xây dựng dữ liệu lịch học theo tuần
    Args:
        tkb_list: QuerySet các TKB
        display_mode: 'general' hoặc 'weekly'
        week_number: Số tuần hiện tại
        dot_xep: DotXep object
    Returns: {
        'schedule': {
            'thu_2': [{'ca': 1, 'ca_info': {...}, 'classes': [...]}, ...],
            'thu_3': [...],
            ...
        },
        'ca_list': [...]
    }
    """
    # Khởi tạo cấu trúc dữ liệu
    schedule = {f'thu_{i}': {} for i in range(2, 9)}  # Thứ 2-8 (8=CN)
    
    # Lấy danh sách ca học
    ca_list = KhungTG.objects.all().order_by('ma_khung_gio')
    
    # Khởi tạo tất cả các slot trống
    for thu in range(2, 9):
        thu_key = f'thu_{thu}'
        for ca in ca_list:
            schedule[thu_key][ca.ma_khung_gio] = {
                'ca': ca.ma_khung_gio,
                'ca_info': {
                    'ten_ca': ca.ten_ca,
                    'gio_bd': ca.gio_bat_dau.strftime('%H:%M'),
                    'gio_kt': ca.gio_ket_thuc.strftime('%H:%M'),
                },
                'classes': []
            }
    
    # Tạo cache cho PhanCong để tránh query nhiều lần
    phan_cong_cache = {}
    phan_cong_data = PhanCong.objects.filter(
        ma_dot=dot_xep
    ).select_related('ma_gv', 'ma_lop')
    
    for pc in phan_cong_data:
        phan_cong_cache[pc.ma_lop.ma_lop] = {
            'gv_name': pc.ma_gv.ten_gv if pc.ma_gv else 'Chưa phân',
            'gv_code': pc.ma_gv.ma_gv if pc.ma_gv else '',
        }
    
    # Điền dữ liệu từ TKB
    for tkb in tkb_list:
        thu = tkb.time_slot_id.thu
        ca = tkb.time_slot_id.ca.ma_khung_gio
        thu_key = f'thu_{thu}'
        
        # Parse tuần học
        weeks = parse_tuan_hoc(tkb.tuan_hoc, week_number, display_mode)
        
        # Nếu ở chế độ chi tiết theo tuần và không có buổi nào trong tuần này thì bỏ qua
        if display_mode == 'weekly' and week_number not in weeks:
            continue
        
        # Lấy thông tin giáo viên từ cache
        gv_info = phan_cong_cache.get(tkb.ma_lop.ma_lop, {
            'gv_name': 'N/A',
            'gv_code': ''
        })
        
        class_info = {
            'ma_lop': tkb.ma_lop.ma_lop,
            'mon_hoc': tkb.ma_lop.ma_mon_hoc.ten_mon_hoc,
            'ma_mon': tkb.ma_lop.ma_mon_hoc.ma_mon_hoc,
            'phong': tkb.ma_phong.ma_phong if tkb.ma_phong else 'TBA',
            'gv_name': gv_info['gv_name'],
            'gv_code': gv_info['gv_code'],
            'weeks': weeks,
            'week_display': format_weeks(weeks) if display_mode == 'general' else f'Tuần {week_number}',
        }
        
        schedule[thu_key][ca]['classes'].append(class_info)
    
    # Chuyển dict thành list để dễ iterate trong template
    result_schedule = {}
    for thu_key, ca_dict in schedule.items():
        result_schedule[thu_key] = [slot_data for ca_id, slot_data in sorted(ca_dict.items())]
    
    return {
        'schedule': result_schedule,
        'ca_list': list(ca_list.values('ma_khung_gio', 'ten_ca', 'gio_bat_dau', 'gio_ket_thuc'))
    }


def parse_tuan_hoc(tuan_hoc_pattern, week_number, display_mode):
    """
    Parse chuỗi pattern tuần học (VD: "1111111000000000") thành list các tuần
    Returns: [1, 2, 3, 4, 5, 6, 7] cho pattern trên
    """
    if not tuan_hoc_pattern:
        # Mặc định: tất cả 15 tuần
        return list(range(1, 16))
    
    weeks = []
    for i, char in enumerate(tuan_hoc_pattern):
        if char == '1':
            weeks.append(i + 1)
    
    return weeks if weeks else list(range(1, 16))


def format_weeks(weeks):
    """
    Format danh sách tuần thành chuỗi ngắn gọn
    VD: [1,2,3,4,5,7,8] -> "T1-5, 7-8"
    """
    if not weeks:
        return ""
    
    weeks = sorted(weeks)
    ranges = []
    start = weeks[0]
    end = weeks[0]
    
    for i in range(1, len(weeks)):
        if weeks[i] == end + 1:
            end = weeks[i]
        else:
            if start == end:
                ranges.append(f"T{start}")
            else:
                ranges.append(f"T{start}-{end}")
            start = weeks[i]
            end = weeks[i]
    
    # Thêm range cuối cùng
    if start == end:
        ranges.append(f"T{start}")
    else:
        ranges.append(f"T{start}-{end}")
    
    return ", ".join(ranges)


def get_week_dates(dot_xep, week_number):
    """
    Tính ngày cụ thể cho từng thứ trong tuần
    Returns: {
        2: {'date': datetime, 'display': '01/01'},
        3: {'date': datetime, 'display': '02/01'},
        ...
        8: {'date': datetime, 'display': '07/01'}
    }
    """
    # Lấy ngày bắt đầu từ DuKienDT
    if not dot_xep.ma_du_kien_dt or not dot_xep.ma_du_kien_dt.ngay_bd:
        return {}
    
    # Tính ngày bắt đầu của tuần (Thứ 2)
    # week_number = 1 => tuần đầu tiên
    start_date = dot_xep.ma_du_kien_dt.ngay_bd
    days_to_add = (week_number - 1) * 7
    week_start = start_date + timedelta(days=days_to_add)
    
    # Điều chỉnh để week_start là thứ 2
    # weekday(): 0=Monday, 6=Sunday
    weekday = week_start.weekday()
    if weekday != 0:  # Nếu không phải thứ 2
        week_start = week_start - timedelta(days=weekday)
    
    week_dates = {}
    for thu in range(2, 9):  # Thứ 2-8 (8=CN)
        if thu == 8:
            # Chủ nhật
            day_offset = 6
        else:
            # Thứ 2-7
            day_offset = thu - 2
        
        day_date = week_start + timedelta(days=day_offset)
        week_dates[thu] = {
            'date': day_date,
            'display': day_date.strftime('%d/%m')
        }
    
    return week_dates
