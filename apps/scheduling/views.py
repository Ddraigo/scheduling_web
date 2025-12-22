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
        
        # LLM-based schedule generation is deprecated
        # Use algorithm-based scheduling instead (algo_scheduler)
        return Response({
            'error': 'LLM schedule generation is deprecated. Please use algorithm-based scheduling or chatbot for queries.',
            'suggestion': 'Go to /admin/sap_lich/algo-scheduler/ for algorithm-based scheduling'
        }, status=status.HTTP_400_BAD_REQUEST)
    
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
        """Validate schedule for a period - using DataAccessLayer"""
        ma_dot = request.data.get('ma_dot')
        
        if not ma_dot:
            return Response(
                {'error': 'ma_dot parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .services.data_access_layer import DataAccessLayer
            
            # Lấy thống kê từ DataAccessLayer
            thong_ke = DataAccessLayer.get_thong_ke_dot_xep(ma_dot)
            xung_dot = DataAccessLayer.get_dataset_xung_dot(ma_dot)
            
            result = {
                'success': True,
                'ma_dot': ma_dot,
                'thong_ke': thong_ke,
                'xung_dot_phong': len(xung_dot.get('xung_dot_phong', {})),
                'lop_chua_phan_cong': xung_dot.get('lop_chua_phan_cong', []).count(),
            }
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error validating schedule: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def conflicts(self, request):
        """Check schedule conflicts for a period using LLM Service"""
        ma_dot = request.query_params.get('ma_dot')
        
        if not ma_dot:
            return Response(
                {'error': 'ma_dot parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .services.llm_service import LLMDataProcessor
            processor = LLMDataProcessor()
            conflicts = processor.detect_scheduling_conflicts(ma_dot)
            return Response({
                'success': True,
                'conflicts': conflicts,
                'total': sum(len(v) for v in conflicts.values())
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error checking conflicts: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def teacher_schedule(self, request):
        """Get teacher schedule and availability using Data Access Layer"""
        ma_gv = request.query_params.get('ma_gv')
        ma_dot = request.query_params.get('ma_dot')
        
        if not ma_gv:
            return Response(
                {'error': 'ma_gv parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .services.data_access_layer import DataAccessLayer, get_giang_vien_info_dict
            gv_info = get_giang_vien_info_dict(ma_gv)
            tkb_list = DataAccessLayer.get_tkb_by_giang_vien(ma_gv, ma_dot)
            
            schedule = []
            for t in tkb_list:
                schedule.append({
                    'lop': t.ma_lop.ma_lop,
                    'mon': t.ma_lop.ma_mon_hoc.ten_mon_hoc,
                    'phong': t.ma_phong.ma_phong,
                    'thu': t.time_slot_id.thu,
                    'ca': t.time_slot_id.ca.ma_khung_gio
                })
            
            return Response({
                'success': True,
                'giang_vien': gv_info,
                'schedule': schedule
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error getting teacher schedule: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


from rest_framework.decorators import api_view
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import DotXep
import traceback


@require_http_methods(["GET"])
def llm_scheduler_api(request):
    """
    API endpoint - Deprecated, use chatbot_api instead
    """
    return JsonResponse({
        'success': False,
        'error': 'This endpoint is deprecated. Use /api/scheduling/chatbot/ for chatbot interactions.'
    }, status=400)


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


@api_view(['GET', 'POST'])
def token_stats_api(request):
    """
    API endpoint để xem thống kê token usage - Deprecated
    """
    return Response({
        'success': False,
        'error': 'Token stats API is deprecated. LLM now only supports chatbot mode.'
    }, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# CHATBOT API - Hỏi đáp về lịch học và dữ liệu
# ============================================================

@api_view(['POST'])
def chatbot_api(request):
    """
    API endpoint for chatbot - trả lời câu hỏi về lịch học và database
    
    Request body:
        - message: Câu hỏi của người dùng
        - ma_dot: Mã đợt xếp (optional)
    
    Response:
        - success: True/False
        - response: Câu trả lời từ chatbot
        - intent: Ý định phát hiện được
    """
    try:
        import json
        
        # Parse request body
        if request.content_type == 'application/json':
            data = request.data
        else:
            data = json.loads(request.body.decode('utf-8'))
        
        message = data.get('message', '').strip()
        ma_dot = data.get('ma_dot')
        
        if not message:
            return Response({
                'success': False,
                'error': 'Vui lòng nhập câu hỏi'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"🤖 Chatbot request: {message[:100]}...")
        
        # Import và gọi chatbot
        from .services.chatbot_service import get_chatbot
        chatbot = get_chatbot()
        
        result = chatbot.chat(message, ma_dot)
        
        return Response(result, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.exception(f"❌ Chatbot API error: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def chatbot_history_api(request):
    """
    API lấy lịch sử chat
    """
    try:
        from .services.chatbot_service import get_chatbot
        chatbot = get_chatbot()
        
        return Response({
            'success': True,
            'history': chatbot.get_conversation_history()
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.exception(f"❌ Chatbot history API error: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def chatbot_clear_api(request):
    """
    API xóa lịch sử chat
    """
    try:
        from .services.chatbot_service import get_chatbot
        chatbot = get_chatbot()
        chatbot.clear_history()
        
        return Response({
            'success': True,
            'message': 'Đã xóa lịch sử chat'
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.exception(f"❌ Chatbot clear API error: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)