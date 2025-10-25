"""
Views and ViewSets for Scheduling API
"""

import os
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.http import JsonResponse
import traceback

logger = logging.getLogger(__name__)

from .models import (
    Khoa, BoMon, GiangVien, MonHoc, PhongHoc,
    LopMonHoc, DotXep, PhanCong, TimeSlot, ThoiKhoaBieu
)
from .serializers import (
    KhoaSerializer, BoMonSerializer, GiangVienSerializer,
    MonHocSerializer, PhongHocSerializer, LopMonHocSerializer,
    DotXepSerializer, PhanCongSerializer, TimeSlotSerializer,
    ThoiKhoaBieuSerializer, ScheduleGenerationSerializer
)
from .services.schedule_validator import ScheduleValidator
from .services.batch_scheduler import BatchScheduler
from .services.query_handler import QueryHandler

logger = logging.getLogger(__name__)


class KhoaViewSet(viewsets.ModelViewSet):
    """ViewSet for Khoa (Faculty)"""
    queryset = Khoa.objects.all()
    serializer_class = KhoaSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Sinh mã khoa tự động dạng KHOA-xxx
        existing = Khoa.objects.filter(ma_khoa__startswith='KHOA-')
        used_nums = set()
        for obj in existing:
            try:
                num = int(obj.ma_khoa.split('-')[1])
                used_nums.add(num)
            except Exception:
                continue
        next_num = 1
        while next_num in used_nums:
            next_num += 1
        serializer.save(ma_khoa=f"KHOA-{next_num:03d}")


class BoMonViewSet(viewsets.ModelViewSet):
    """ViewSet for BoMon (Department)"""
    queryset = BoMon.objects.select_related('khoa').all()
    serializer_class = BoMonSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['khoa']


class GiangVienViewSet(viewsets.ModelViewSet):
    """ViewSet for GiangVien (Teacher)"""
    queryset = GiangVien.objects.select_related('bo_mon').all()
    serializer_class = GiangVienSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['bo_mon']
    search_fields = ['ma_gv', 'ten_gv', 'email']


class MonHocViewSet(viewsets.ModelViewSet):
    """ViewSet for MonHoc (Subject)"""
    queryset = MonHoc.objects.all()
    serializer_class = MonHocSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['ma_mon_hoc', 'ten_mon_hoc']


class PhongHocViewSet(viewsets.ModelViewSet):
    """ViewSet for PhongHoc (Classroom)"""
    queryset = PhongHoc.objects.all()
    serializer_class = PhongHocSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['loai_phong', 'toa_nha']
    search_fields = ['ma_phong', 'ten_phong']


class LopMonHocViewSet(viewsets.ModelViewSet):
    """ViewSet for LopMonHoc (Class)"""
    queryset = LopMonHoc.objects.select_related('mon_hoc').all()
    serializer_class = LopMonHocSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['mon_hoc', 'loai_lop', 'hoc_ky', 'nam_hoc']
    search_fields = ['ma_lop', 'ten_lop']


class DotXepViewSet(viewsets.ModelViewSet):
    """ViewSet for DotXep (Scheduling Period)"""
    queryset = DotXep.objects.all()
    serializer_class = DotXepSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['trang_thai', 'nam_hoc', 'hoc_ky']


class PhanCongViewSet(viewsets.ModelViewSet):
    """ViewSet for PhanCong (Teaching Assignment)"""
    queryset = PhanCong.objects.select_related(
        'dot_xep', 'lop_mon_hoc', 'giang_vien', 'lop_mon_hoc__mon_hoc'
    ).all()
    serializer_class = PhanCongSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['dot_xep', 'giang_vien', 'lop_mon_hoc']


class TimeSlotViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for TimeSlot (read-only)"""
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['thu']


class ThoiKhoaBieuViewSet(viewsets.ModelViewSet):
    """ViewSet for ThoiKhoaBieu (Schedule)"""
    queryset = ThoiKhoaBieu.objects.select_related(
        'dot_xep', 'phan_cong', 'lop_mon_hoc', 
        'phong_hoc', 'time_slot', 'lop_mon_hoc__mon_hoc'
    ).all()
    serializer_class = ThoiKhoaBieuSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['dot_xep', 'lop_mon_hoc', 'phong_hoc', 'tuan_hoc']
    
    @action(detail=False, methods=['get'])
    def by_period(self, request):
        """Get schedule by period"""
        ma_dot = request.query_params.get('ma_dot')
        if not ma_dot:
            return Response(
                {'error': 'ma_dot parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        schedules = self.queryset.filter(dot_xep__ma_dot=ma_dot)
        serializer = self.get_serializer(schedules, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """Get schedule by teacher"""
        ma_gv = request.query_params.get('ma_gv')
        ma_dot = request.query_params.get('ma_dot')
        
        if not ma_gv:
            return Response(
                {'error': 'ma_gv parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        schedules = self.queryset.filter(phan_cong__giang_vien__ma_gv=ma_gv)
        if ma_dot:
            schedules = schedules.filter(dot_xep__ma_dot=ma_dot)
        
        serializer = self.get_serializer(schedules, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_room(self, request):
        """Get schedule by room"""
        ma_phong = request.query_params.get('ma_phong')
        ma_dot = request.query_params.get('ma_dot')
        
        if not ma_phong:
            return Response(
                {'error': 'ma_phong parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        schedules = self.queryset.filter(phong_hoc__ma_phong=ma_phong)
        if ma_dot:
            schedules = schedules.filter(dot_xep__ma_dot=ma_dot)
        
        serializer = self.get_serializer(schedules, many=True)
        return Response(serializer.data)


class ScheduleGenerationViewSet(viewsets.ViewSet):
    """ViewSet for schedule generation operations"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate schedule for a period"""
        serializer = ScheduleGenerationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ma_dot = serializer.validated_data['ma_dot']
        use_ai = serializer.validated_data.get('use_ai', True)
        
        logger.info(f"Generating schedule for period {ma_dot}, use_ai={use_ai}")
        
        try:
            # schedule_service = ScheduleService()  # ← ScheduleService no longer exists
            # result = schedule_service.generate_schedule(ma_dot, use_ai=use_ai)
            
            # Use LLM generator instead
            from .services.schedule_generator_llm import ScheduleGeneratorLLM
            generator = ScheduleGeneratorLLM()
            result = generator.create_schedule_llm(ma_dot)
            
            if result and isinstance(result, dict):
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to generate schedule'}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error in schedule generation: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get generation status for a period"""
        ma_dot = request.query_params.get('ma_dot')
        
        if not ma_dot:
            return Response(
                {'error': 'ma_dot parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            dot_xep = DotXep.objects.get(ma_dot=ma_dot)
            scheduled_count = ThoiKhoaBieu.objects.filter(dot_xep=dot_xep).count()
            assigned_count = PhanCong.objects.filter(dot_xep=dot_xep).count()
            
            return Response({
                'ma_dot': ma_dot,
                'ten_dot': dot_xep.ten_dot,
                'trang_thai': dot_xep.trang_thai,
                'total_assignments': assigned_count,
                'scheduled_count': scheduled_count,
                'completion_rate': (scheduled_count / assigned_count * 100) if assigned_count > 0 else 0,
            })
        
        except DotXep.DoesNotExist:
            return Response(
                {'error': f'Period {ma_dot} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def validate(self, request):
        """Validate schedule for a period"""
        ma_dot = request.data.get('ma_dot')
        
        if not ma_dot:
            return Response(
                {'error': 'ma_dot parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            validator = ScheduleValidator()
            result = validator.validate_schedule_django(ma_dot)
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error validating schedule: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def batch_generate(self, request):
        """Generate schedule using batch processing"""
        ma_dot = request.data.get('ma_dot')
        batch_size = request.data.get('batch_size', 25)
        
        if not ma_dot:
            return Response(
                {'error': 'ma_dot parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            batch_scheduler = BatchScheduler(batch_size=batch_size)
            result = batch_scheduler.generate_schedule_django(ma_dot)
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in batch generation: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def conflicts(self, request):
        """Check schedule conflicts for a period"""
        ma_dot = request.query_params.get('ma_dot')
        
        if not ma_dot:
            return Response(
                {'error': 'ma_dot parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            query_handler = QueryHandler()
            result = query_handler.get_schedule_conflicts(ma_dot)
            return Response({'report': result}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error checking conflicts: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def teacher_schedule(self, request):
        """Get teacher schedule and availability"""
        ma_gv = request.query_params.get('ma_gv')
        ma_dot = request.query_params.get('ma_dot')
        
        if not ma_gv or not ma_dot:
            return Response(
                {'error': 'ma_gv and ma_dot parameters required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            query_handler = QueryHandler()
            result = query_handler.get_teacher_availability(ma_gv, ma_dot)
            return Response({'report': result}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error getting teacher schedule: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def room_utilization(self, request):
        """Get room utilization report"""
        ma_dot = request.query_params.get('ma_dot')
        
        if not ma_dot:
            return Response(
                {'error': 'ma_dot parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            query_handler = QueryHandler()
            result = query_handler.get_room_utilization(ma_dot)
            return Response({'report': result}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error getting room utilization: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def class_distribution(self, request):
        """Get class distribution by teacher and department"""
        ma_dot = request.query_params.get('ma_dot')
        
        if not ma_dot:
            return Response(
                {'error': 'ma_dot parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            query_handler = QueryHandler()
            result = query_handler.get_class_distribution(ma_dot)
            return Response({'report': result}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error getting distribution: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


from rest_framework.decorators import api_view
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .services.schedule_generator_llm import ScheduleGeneratorLLM
from .models import DotXep
import traceback


@require_http_methods(["GET"])
def llm_scheduler_api(request):
    """
    API endpoint for LLM-based schedule generation steps
    Query params:
        - period_id: DotXep ma_dot (e.g., DOT1_2025-2026_HK1)
        - step: fetch_data, prepare_compact, generate_schedule, etc.
    """
    ma_dot = request.GET.get('period_id')
    step = request.GET.get('step', 'fetch_data')  # Default to fetch_data
    
    print(f"\n=== LLM API DEBUG ===")
    print(f"period_id: {ma_dot}")
    print(f"step: {step}")
    
    if not ma_dot:
        return JsonResponse({'error': 'Missing period_id parameter'}, status=400)
    
    try:
        # First check if DotXep exists
        print(f"Checking if DotXep {ma_dot} exists...")
        try:
            dot = DotXep.objects.get(ma_dot=ma_dot)
            print(f"✓ Found DotXep: {dot.ten_dot}")
        except DotXep.DoesNotExist:
            print(f"✗ DotXep {ma_dot} NOT FOUND")
            return JsonResponse({'error': f'Period {ma_dot} not found'}, status=404)
        
        logger.info(f"LLM API called: ma_dot={ma_dot}, step={step}")
        
        generator = ScheduleGeneratorLLM()
        
        if step == 'fetch_data':
            print(f"Executing fetch_data for {ma_dot}")
            result = handle_fetch_data_helper(generator, ma_dot)
            return JsonResponse(result, status=200 if result.get('success') else 400)
        
        elif step == 'prepare_compact':
            print(f"Executing prepare_compact for {ma_dot}")
            result = handle_prepare_compact_helper(generator, ma_dot)
            return JsonResponse(result, status=200 if result.get('success') else 400)
        
        elif step == 'build_prompt':
            print(f"Executing build_prompt for {ma_dot}")
            result = handle_build_prompt_helper(generator, ma_dot)
            return JsonResponse(result, status=200 if result.get('success') else 400)
        
        elif step == 'call_llm':
            print(f"Executing call_llm for {ma_dot}")
            result = handle_call_llm_helper(generator, ma_dot)
            return JsonResponse(result, status=200 if result.get('success') else 400)
        
        elif step == 'validate_and_save':
            print(f"Executing validate_and_save for {ma_dot}")
            result = handle_validate_and_save_helper(generator, ma_dot)
            return JsonResponse(result, status=200 if result.get('success') else 400)
        
        elif step == 'generate_schedule':
            # Chạy toàn bộ pipeline
            print(f"Executing full pipeline for {ma_dot}")
            result = generator.create_schedule_llm_by_ma_dot(ma_dot)
            return JsonResponse({'success': True, 'message': 'Schedule generated', 'result': str(result)})
        
        else:
            print(f"Unknown step: {step}")
            return JsonResponse({'error': f'Unknown step: {step}'}, status=400)
    
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"LLM Scheduler API error:\n{error_trace}")
        print(f"\n❌ EXCEPTION in API:\n{error_trace}\n")
        return JsonResponse({'error': str(e)}, status=400)


@api_view(['GET'])
def debug_dotxep_api(request):
    """Debug endpoint to check DotXep data"""
    ma_dot = request.GET.get('ma_dot', 'DOT1_2025-2026_HK1')
    
    print(f"\n=== DEBUG DotXep ===")
    
    # List all DotXep
    all_dots = DotXep.objects.all()
    print(f"Total DotXep: {all_dots.count()}")
    for dot in all_dots[:5]:
        print(f"  - {dot.ma_dot}: {dot.ten_dot}")
    
    # Try to get specific DotXep
    print(f"\nSearching for: {ma_dot}")
    try:
        dot = DotXep.objects.get(ma_dot=ma_dot)
        print(f"✓ Found: {dot.ten_dot} (semester: {dot.ma_du_kien_dt_id})")
        return JsonResponse({
            'success': True,
            'ma_dot': dot.ma_dot,
            'ten_dot': dot.ten_dot,
            'ma_du_kien_dt_id': dot.ma_du_kien_dt_id,
            'trang_thai': dot.trang_thai
        })
    except DotXep.DoesNotExist:
        print(f"✗ NOT FOUND")
        all_dots_list = list(DotXep.objects.all().values('ma_dot', 'ten_dot'))
        return JsonResponse({
            'success': False,
            'error': f'DotXep {ma_dot} not found',
            'available': all_dots_list
        }, status=404)


# ======================== HELPER FUNCTIONS FOR LLM TEST ========================

def json_serial(obj):
    """Convert non-serializable objects to serializable format"""
    if hasattr(obj, 'isoformat'):  # datetime
        return obj.isoformat()
    if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):  # QuerySet/list
        try:
            return list(obj)
        except:
            pass
    return str(obj)


def handle_fetch_data_helper(generator, ma_dot):
    """Fetch schedule data from database"""
    try:
        logger.info(f"🔍 Fetching data for ma_dot={ma_dot}")
        
        # Use the new step method
        result = generator.fetch_data_step(ma_dot)
        
        if result.get('success'):
            logger.info(f"📊 Data fetched successfully")
            return {
                'success': True,
                'message': 'Dữ liệu đã được tải thành công',
                'stats': result.get('stats', {})
            }
        else:
            logger.warning(f"⚠️ {result.get('error')}")
            return {
                'success': False,
                'error': result.get('error', 'Failed to fetch data')
            }
    
    except Exception as e:
        logger.exception(f"❌ Fetch data error: {e}")
        return {'success': False, 'error': str(e)}


def handle_prepare_compact_helper(generator, ma_dot):
    """Prepare compact data format"""
    try:
        logger.info(f"🔄 Preparing compact format for ma_dot={ma_dot}")
        
        result = generator.prepare_compact_step(ma_dot)
        
        if result.get('success'):
            logger.info(f"📊 Compact format prepared")
            return {
                'success': True,
                'message': 'Dữ liệu đã được chuẩn bị',
                'stats': result.get('stats', {})
            }
        else:
            logger.warning(f"⚠️ {result.get('error')}")
            return {
                'success': False,
                'error': result.get('error', 'Failed to prepare compact format')
            }
    
    except Exception as e:
        logger.exception(f"❌ Prepare compact error: {e}")
        return {'success': False, 'error': str(e)}


def handle_build_prompt_helper(generator, ma_dot):
    """Build LLM prompt"""
    try:
        logger.info(f"📝 Building prompt for ma_dot={ma_dot}")
        
        result = generator.build_prompt_step(ma_dot)
        
        if result.get('success'):
            logger.info(f"✅ Prompt built successfully")
            prompt_info = result.get('prompt', {})
            return {
                'success': True,
                'message': 'Prompt đã được tạo',
                'prompt': {
                    'length': prompt_info.get('prompt_length', 0),
                    'tokens': prompt_info.get('prompt_length', 0) // 4,
                    'preview': prompt_info.get('prompt_preview', '')
                }
            }
        else:
            logger.warning(f"⚠️ {result.get('error')}")
            return {
                'success': False,
                'error': result.get('error', 'Failed to build prompt')
            }
    
    except Exception as e:
        logger.exception(f"❌ Build prompt error: {e}")
        return {'success': False, 'error': str(e)}


def handle_call_llm_helper(generator, ma_dot):
    """Call LLM for schedule generation"""
    try:
        logger.info(f"🧠 Calling LLM for ma_dot={ma_dot}")
        
        result = generator.call_llm_step(ma_dot)
        
        if result.get('success'):
            logger.info(f"✅ LLM call successful")
            return {
                'success': True,
                'message': 'LLM đã tạo lịch thành công',
                'llm_result': {
                    'schedule_count': result.get('schedule_count', 0),
                    'has_errors': result.get('has_errors', False)
                }
            }
        else:
            logger.warning(f"⚠️ {result.get('error')}")
            return {
                'success': False,
                'error': result.get('error', 'LLM call failed')
            }
    
    except Exception as e:
        logger.exception(f"❌ LLM call error: {e}")
        return {'success': False, 'error': str(e)}


def handle_validate_and_save_helper(generator, ma_dot):
    """Validate and save schedule"""
    try:
        logger.info(f"✅ Validating and saving schedule for ma_dot={ma_dot}")
        
        result = generator.validate_and_save_step(ma_dot)
        
        if result.get('success'):
            logger.info(f"✅ Schedule validated and saved")
            return {
                'success': True,
                'message': 'Lịch đã được validate & lưu',
                'result': result.get('result', '')
            }
        else:
            logger.warning(f"⚠️ {result.get('error')}")
            return {
                'success': False,
                'error': result.get('error', 'Failed to validate and save')
            }
    
    except Exception as e:
        logger.exception(f"❌ Validate and save error: {e}")
        return {'success': False, 'error': str(e)}


@api_view(['GET', 'POST'])
def token_stats_api(request):
    """
    API endpoint để xem thống kê token usage
    
    Methods:
        GET: Lấy thống kê token tóm tắt
        POST: Export token report ra file markdown
    """
    try:
        from .services.schedule_ai import ScheduleAI
        
        ai = ScheduleAI()
        
        if request.method == 'GET':
            # Trả về JSON stats
            summary = ai.get_token_summary()
            return Response({
                'success': True,
                'message': 'Token usage statistics',
                'data': summary
            }, status=status.HTTP_200_OK)
        
        elif request.method == 'POST':
            # Export report ra file
            filepath = request.POST.get('filepath', None)
            report = ai.export_token_report(filepath)
            return Response({
                'success': True,
                'message': 'Token usage report exported',
                'filepath': filepath or os.path.join(os.path.dirname(__file__), '../../output/token_usage_report.md'),
                'report_preview': report[:500] + '...' if len(report) > 500 else report
            }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.exception(f"❌ Token stats API error: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)