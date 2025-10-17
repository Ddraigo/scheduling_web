"""
Views and ViewSets for Scheduling API
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
import logging

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
from .services.schedule_service import ScheduleService
from .services.schedule_validator import ScheduleValidator
from .services.batch_scheduler import BatchScheduler
from .services.query_handler import QueryHandler

logger = logging.getLogger(__name__)


class KhoaViewSet(viewsets.ModelViewSet):
    """ViewSet for Khoa (Faculty)"""
    queryset = Khoa.objects.all()
    serializer_class = KhoaSerializer
    permission_classes = [IsAuthenticated]


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
            schedule_service = ScheduleService()
            result = schedule_service.generate_schedule(ma_dot, use_ai=use_ai)
            
            if result['success']:
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
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

