"""
DRF Permission Classes - Scope Enforcement cho API
Tích hợp RBAC để enforce phạm vi dữ liệu theo role

USAGE:
    class MyViewSet(viewsets.ModelViewSet):
        permission_classes = [SchedulingRolePermission]
        
        def get_queryset(self):
            return filter_queryset_by_role(
                self.request.user, 
                MyModel.objects.all()
            )
"""

import logging
from rest_framework.permissions import BasePermission, IsAuthenticated
from django.db.models import Q
from apps.sap_lich.rbac import (
    get_user_role_info,
    has_admin_access,
    can_manage_schedule,
    can_run_scheduler
)

logger = logging.getLogger(__name__)


class SchedulingRolePermission(BasePermission):
    """
    Permission class kiểm tra user có quyền truy cập hệ thống scheduling không
    - Admin: toàn quyền
    - Trưởng Khoa/Trưởng Bộ Môn/Giảng Viên: có quyền xem (scope filter tại queryset)
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        role_info = get_user_role_info(request.user)
        
        # Nếu không có role => từ chối
        if role_info['role'] is None:
            logger.warning(
                f"User '{request.user.username}' không có role hợp lệ. "
                f"Truy cập API bị từ chối."
            )
            return False
        
        return True


class SchedulingManagePermission(BasePermission):
    """
    Permission class cho các action quản lý (create, update, delete)
    Chỉ Admin và Trưởng Khoa mới có quyền
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Safe methods (GET, HEAD, OPTIONS) => cho phép nếu có role
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            role_info = get_user_role_info(request.user)
            return role_info['role'] is not None
        
        # Unsafe methods => chỉ admin và trưởng khoa
        return can_manage_schedule(request.user)


class SchedulerPermission(BasePermission):
    """
    Permission class cho các action chạy thuật toán xếp lịch
    Chỉ Admin mới có quyền
    """
    
    def has_permission(self, request, view):
        return can_run_scheduler(request.user)


def filter_queryset_by_role(user, queryset, model_name=None):
    """
    Filter queryset dựa trên role và scope của user
    
    Args:
        user: Django User object
        queryset: QuerySet cần filter
        model_name: str - tên model để xác định cách filter
            Hỗ trợ: 'ThoiKhoaBieu', 'PhanCong', 'LopMonHoc', 'GiangVien', 'BoMon', 'Khoa'
    
    Returns:
        QuerySet đã được filter theo scope
    """
    role_info = get_user_role_info(user)
    role = role_info['role']
    
    # Admin: không filter
    if role == 'admin':
        return queryset
    
    # Không có role => empty queryset
    if role is None:
        logger.warning(f"User '{user.username}' không có role. Trả về empty queryset.")
        return queryset.none()
    
    # Auto-detect model name từ queryset nếu không truyền
    if model_name is None:
        model_name = queryset.model.__name__
    
    # === FILTER THEO TỪNG MODEL ===
    
    if model_name == 'ThoiKhoaBieu':
        # TKB: filter qua PhanCong -> GiangVien -> BoMon -> Khoa
        if role == 'truong_khoa':
            ma_khoa = role_info['ma_khoa']
            if not ma_khoa:
                logger.error(f"Truong Khoa '{user.username}' không có ma_khoa. Trả về empty.")
                return queryset.none()
            # Filter: TKB.ma_lop -> PhanCong.ma_lop -> PhanCong.ma_gv -> GiangVien -> BoMon -> Khoa
            return queryset.filter(
                ma_lop__phan_cong_list__ma_gv__ma_bo_mon__ma_khoa__ma_khoa=ma_khoa
            ).distinct()
        
        elif role == 'truong_bo_mon':
            ma_bo_mon = role_info['ma_bo_mon']
            if not ma_bo_mon:
                logger.error(f"Truong Bo Mon '{user.username}' không có ma_bo_mon. Trả về empty.")
                return queryset.none()
            return queryset.filter(
                ma_lop__phan_cong_list__ma_gv__ma_bo_mon__ma_bo_mon=ma_bo_mon
            ).distinct()
        
        elif role == 'giang_vien':
            ma_gv = role_info['ma_gv']
            if not ma_gv:
                logger.error(f"Giang Vien '{user.username}' không có ma_gv. Trả về empty.")
                return queryset.none()
            # TKB của giảng viên: qua PhanCong
            return queryset.filter(
                ma_lop__phan_cong_list__ma_gv__ma_gv=ma_gv
            ).distinct()
    
    elif model_name == 'PhanCong':
        if role == 'truong_khoa':
            ma_khoa = role_info['ma_khoa']
            if not ma_khoa:
                return queryset.none()
            return queryset.filter(
                ma_gv__ma_bo_mon__ma_khoa__ma_khoa=ma_khoa
            )
        
        elif role == 'truong_bo_mon':
            ma_bo_mon = role_info['ma_bo_mon']
            if not ma_bo_mon:
                return queryset.none()
            return queryset.filter(
                ma_gv__ma_bo_mon__ma_bo_mon=ma_bo_mon
            )
        
        elif role == 'giang_vien':
            ma_gv = role_info['ma_gv']
            if not ma_gv:
                return queryset.none()
            return queryset.filter(ma_gv__ma_gv=ma_gv)
    
    elif model_name == 'GiangVien':
        if role == 'truong_khoa':
            ma_khoa = role_info['ma_khoa']
            if not ma_khoa:
                return queryset.none()
            return queryset.filter(ma_bo_mon__ma_khoa__ma_khoa=ma_khoa)
        
        elif role == 'truong_bo_mon':
            ma_bo_mon = role_info['ma_bo_mon']
            if not ma_bo_mon:
                return queryset.none()
            return queryset.filter(ma_bo_mon__ma_bo_mon=ma_bo_mon)
        
        elif role == 'giang_vien':
            ma_gv = role_info['ma_gv']
            if not ma_gv:
                return queryset.none()
            return queryset.filter(ma_gv=ma_gv)
    
    elif model_name == 'BoMon':
        if role == 'truong_khoa':
            ma_khoa = role_info['ma_khoa']
            if not ma_khoa:
                return queryset.none()
            return queryset.filter(ma_khoa__ma_khoa=ma_khoa)
        
        elif role in ['truong_bo_mon', 'giang_vien']:
            ma_bo_mon = role_info['ma_bo_mon']
            if not ma_bo_mon:
                return queryset.none()
            return queryset.filter(ma_bo_mon=ma_bo_mon)
    
    elif model_name == 'Khoa':
        if role == 'truong_khoa':
            ma_khoa = role_info['ma_khoa']
            if not ma_khoa:
                return queryset.none()
            return queryset.filter(ma_khoa=ma_khoa)
        
        elif role in ['truong_bo_mon', 'giang_vien']:
            # Trưởng bộ môn/GV chỉ thấy khoa của mình
            ma_khoa = role_info['ma_khoa']
            if not ma_khoa:
                return queryset.none()
            return queryset.filter(ma_khoa=ma_khoa)
    
    elif model_name == 'LopMonHoc':
        # Lớp môn học: filter qua PhanCong
        if role == 'truong_khoa':
            ma_khoa = role_info['ma_khoa']
            if not ma_khoa:
                return queryset.none()
            return queryset.filter(
                phan_cong_list__ma_gv__ma_bo_mon__ma_khoa__ma_khoa=ma_khoa
            ).distinct()
        
        elif role == 'truong_bo_mon':
            ma_bo_mon = role_info['ma_bo_mon']
            if not ma_bo_mon:
                return queryset.none()
            return queryset.filter(
                phan_cong_list__ma_gv__ma_bo_mon__ma_bo_mon=ma_bo_mon
            ).distinct()
        
        elif role == 'giang_vien':
            ma_gv = role_info['ma_gv']
            if not ma_gv:
                return queryset.none()
            return queryset.filter(
                phan_cong_list__ma_gv__ma_gv=ma_gv
            ).distinct()
    
    # Model khác: mặc định trả về empty cho non-admin
    logger.warning(
        f"Model '{model_name}' không được xử lý scope filter. "
        f"Role '{role}' sẽ thấy empty queryset."
    )
    return queryset.none()
