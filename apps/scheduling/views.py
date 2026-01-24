"""
Views and ViewSets for Scheduling API
SỬA: Tích hợp RBAC scope enforcement
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
from django.contrib import admin

# RBAC imports
from apps.sap_lich.rbac import get_user_role_info
from apps.sap_lich.permissions import (
    SchedulingRolePermission,
    SchedulingManagePermission,
    filter_queryset_by_role
)

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
    """ViewSet for Khoa (Faculty) - với scope filter"""
    queryset = Khoa.objects.all()
    serializer_class = KhoaSerializer
    permission_classes = [SchedulingManagePermission]
    
    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_role(self.request.user, qs, 'Khoa')

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
    """ViewSet for BoMon (Department) - với scope filter"""
    queryset = BoMon.objects.select_related('ma_khoa').all()
    serializer_class = BoMonSerializer
    permission_classes = [SchedulingManagePermission]
    filterset_fields = ['ma_khoa']
    
    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_role(self.request.user, qs, 'BoMon')


class GiangVienViewSet(viewsets.ModelViewSet):
    """ViewSet for GiangVien (Teacher) - với scope filter"""
    queryset = GiangVien.objects.select_related('ma_bo_mon').all()
    serializer_class = GiangVienSerializer
    permission_classes = [SchedulingManagePermission]
    filterset_fields = ['ma_bo_mon']
    search_fields = ['ma_gv', 'ten_gv', 'email']
    
    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_role(self.request.user, qs, 'GiangVien')


class MonHocViewSet(viewsets.ModelViewSet):
    """ViewSet for MonHoc (Subject) - Admin + Trưởng Khoa"""
    queryset = MonHoc.objects.all()
    serializer_class = MonHocSerializer
    permission_classes = [SchedulingManagePermission]
    search_fields = ['ma_mon_hoc', 'ten_mon_hoc']


class PhongHocViewSet(viewsets.ModelViewSet):
    """ViewSet for PhongHoc (Classroom) - Admin + Trưởng Khoa"""
    queryset = PhongHoc.objects.all()
    serializer_class = PhongHocSerializer
    permission_classes = [SchedulingManagePermission]
    filterset_fields = ['loai_phong']
    search_fields = ['ma_phong']


class LopMonHocViewSet(viewsets.ModelViewSet):
    """ViewSet for LopMonHoc (Class) - với scope filter"""
    queryset = LopMonHoc.objects.select_related('ma_mon_hoc').all()
    serializer_class = LopMonHocSerializer
    permission_classes = [SchedulingManagePermission]
    filterset_fields = ['ma_mon_hoc', 'nhom_mh', 'to_mh', 'he_dao_tao']
    search_fields = ['ma_lop']
    
    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_role(self.request.user, qs, 'LopMonHoc')


class DotXepViewSet(viewsets.ModelViewSet):
    """ViewSet for DotXep (Scheduling Period) - Admin + Trưởng Khoa"""
    queryset = DotXep.objects.all()
    serializer_class = DotXepSerializer
    permission_classes = [SchedulingManagePermission]
    filterset_fields = ['trang_thai', 'ma_du_kien_dt']


class PhanCongViewSet(viewsets.ModelViewSet):
    """ViewSet for PhanCong (Teaching Assignment) - với scope filter"""
    queryset = PhanCong.objects.select_related(
        'ma_dot', 'ma_lop', 'ma_gv', 'ma_lop__ma_mon_hoc'
    ).all()
    serializer_class = PhanCongSerializer
    permission_classes = [SchedulingManagePermission]
    filterset_fields = ['ma_dot', 'ma_gv', 'ma_lop']
    
    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_role(self.request.user, qs, 'PhanCong')


class TimeSlotViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for TimeSlot (read-only)"""
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['thu']


class ThoiKhoaBieuViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ThoiKhoaBieu (Schedule) - với RBAC scope enforcement
    SỬA: Fix ORM filter queries và enforce scope theo role
    """
    queryset = ThoiKhoaBieu.objects.select_related(
        'ma_dot', 'ma_lop', 'ma_phong', 'time_slot_id', 'ma_lop__ma_mon_hoc'
    ).all()
    serializer_class = ThoiKhoaBieuSerializer
    permission_classes = [SchedulingRolePermission]
    filterset_fields = ['ma_dot', 'ma_lop', 'ma_phong', 'tuan_hoc']
    
    def get_queryset(self):
        """Override để enforce scope theo role"""
        qs = super().get_queryset()
        # Filter theo role - scope enforcement
        return filter_queryset_by_role(self.request.user, qs, 'ThoiKhoaBieu')
    
    @action(detail=False, methods=['get'])
    def by_period(self, request):
        """
        Get schedule by period
        SỬA: Dùng đúng field FK (ma_dot) thay vì dot_xep__ma_dot
        """
        ma_dot = request.query_params.get('ma_dot')
        if not ma_dot:
            return Response(
                {'error': 'ma_dot parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # SỬA: Dùng ma_dot__ma_dot (FK trỏ đến DotXep.ma_dot)
        schedules = self.get_queryset().filter(ma_dot__ma_dot=ma_dot)
        serializer = self.get_serializer(schedules, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """
        Get schedule by teacher
        SỬA: Join đúng qua PhanCong (TKB.ma_lop -> PhanCong.ma_lop -> PhanCong.ma_gv)
        ENFORCE: Giảng viên chỉ thấy TKB của chính mình
        """
        ma_gv_param = request.query_params.get('ma_gv')
        ma_dot = request.query_params.get('ma_dot')
        
        # Get role info
        role_info = get_user_role_info(request.user)
        
        # ENFORCE: Giảng viên chỉ thấy TKB của chính mình
        if role_info['role'] == 'giang_vien':
            ma_gv = role_info['ma_gv']
            if not ma_gv:
                return Response(
                    {'error': 'Không tìm thấy thông tin giảng viên'},
                    status=status.HTTP_403_FORBIDDEN
                )
            # Bỏ qua ma_gv_param từ query nếu user là giảng viên
        else:
            # Admin/Trưởng Khoa/Trưởng Bộ Môn: dùng ma_gv từ query
            if not ma_gv_param:
                return Response(
                    {'error': 'ma_gv parameter required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            ma_gv = ma_gv_param
        
        # SỬA: Join qua PhanCong đúng cách
        # ThoiKhoaBieu.ma_lop -> LopMonHoc
        # LopMonHoc.phan_cong_list (reverse FK) -> PhanCong
        # PhanCong.ma_gv -> GiangVien
        schedules = self.get_queryset().filter(
            ma_lop__phan_cong_list__ma_gv__ma_gv=ma_gv
        ).distinct()
        
        if ma_dot:
            schedules = schedules.filter(ma_dot__ma_dot=ma_dot)
        
        serializer = self.get_serializer(schedules, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_room(self, request):
        """
        Get schedule by room
        SỬA: Dùng đúng field FK (ma_phong) thay vì phong_hoc__ma_phong
        """
        ma_phong = request.query_params.get('ma_phong')
        ma_dot = request.query_params.get('ma_dot')
        
        if not ma_phong:
            return Response(
                {'error': 'ma_phong parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # SỬA: Dùng ma_phong__ma_phong (FK trỏ đến PhongHoc.ma_phong)
        schedules = self.get_queryset().filter(ma_phong__ma_phong=ma_phong)
        if ma_dot:
            schedules = schedules.filter(ma_dot__ma_dot=ma_dot)
        
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


def assign_roles_view(request):
    """View để gán role hàng loạt cho users"""
    from django.contrib.auth.models import User, Group
    from django.shortcuts import render, redirect
    from django.contrib import messages
    
    if request.method == 'POST':
        usernames = request.POST.getlist('users')
        role = request.POST.get('role')
        
        if not usernames or not role:
            messages.error(request, 'Vui lòng chọn users và role!')
            return redirect('admin:auth_user_changelist')
        
        try:
            group = Group.objects.get(name=role)
            users = User.objects.filter(username__in=usernames)
            
            count = 0
            for user in users:
                user.groups.clear()
                user.groups.add(group)
                count += 1
            
            role_display = {
                'Truong_Khoa': ' Trưởng Khoa',
                'Truong_Bo_Mon': ' Trưởng Bộ Môn',
                'Giang_Vien': ' Giảng Viên'
            }.get(role, role)
            
            messages.success(request, f'✅ Đã gán role {role_display} cho {count} users!')
        except Group.DoesNotExist:
            messages.error(request, f'Không tìm thấy role: {role}')
        except Exception as e:
            messages.error(request, f'Lỗi: {str(e)}')
        
        return redirect('admin:auth_user_changelist')
    
    # GET request - show form
    users = User.objects.all().order_by('username')
    groups = Group.objects.all()
    giang_vien_map = {gv.ma_gv: gv for gv in GiangVien.objects.all()}
    
    # Set current_app for proper admin context (sidebar, breadcrumbs, etc.)
    request.current_app = admin.site.name
    
    # Merge admin.site.each_context to get proper Django Admin layout
    base_ctx = admin.site.each_context(request)
    context = {
        **base_ctx,
        'users': users,
        'groups': groups,
        'giang_vien_map': giang_vien_map,
        'title': 'Gán vai trò hàng loạt',
    }
    
    return render(request, 'admin/scheduling/assign_roles.html', context)