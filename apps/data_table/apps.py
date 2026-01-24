from django.apps import AppConfig

class DataTableConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.data_table'
    verbose_name = 'Dữ liệu'
    
    def ready(self):
        """Register proxy models for admin after all apps are loaded."""
        from django.contrib import admin
        from .models import (
            KhoaProxy, BoMonProxy, GiangVienProxy, MonHocProxy, GVDayMonProxy,
            PhongHocProxy, LopMonHocProxy, KhungTGProxy, TimeSlotProxy,
            RangBuocMemProxy, DuKienDTProxy, ThoiKhoaBieuProxy,
            DotXepProxy, PhanCongProxy, RangBuocTrongDotProxy, 
            NgayNghiCoDinhProxy, NgayNghiDotProxy, NguyenVongProxy,
            PageItems, HideShowFilter, ModelFilter
        )
        from apps.scheduling.admin import (
            KhoaAdmin, BoMonAdmin, GiangVienAdmin, MonHocAdmin, GVDayMonAdmin,
            PhongHocAdmin, LopMonHocAdmin, KhungTGAdmin, TimeSlotAdmin,
            RangBuocMemAdmin, DuKienDTAdmin, ThoiKhoaBieuAdmin,
            DotXepAdmin, PhanCongAdmin, RangBuocTrongDotAdmin, 
            NgayNghiCoDinhAdmin, NgayNghiDotAdmin, NguyenVongAdmin
        )
        from apps.sap_lich.rbac import get_user_role_info
        from apps.scheduling.models import GiangVien
        
        def get_user_scope(user):
            """Lấy thông tin scope của user (ma_khoa, ma_bo_mon)"""
            role_info = get_user_role_info(user)
            return {
                'role': role_info.get('role'),
                'ma_khoa': role_info.get('ma_khoa'),
                'ma_bo_mon': role_info.get('ma_bo_mon'),
                'ma_gv': role_info.get('ma_gv'),
            }
        
        # Wrapper to override has_module_permission and filter queryset by role
        def create_proxy_admin(base_class, model_name):
            class ProxyAdmin(base_class):
                def has_module_permission(self, request):
                    return True
                
                def changelist_view(self, request, extra_context=None):
                    """Giữ nguyên changelist mặc định của Django admin."""
                    return super().changelist_view(request, extra_context)
                
                def has_view_permission(self, request, obj=None):
                    if request.user.is_superuser:
                        return True
                    scope = get_user_scope(request.user)
                    role = scope['role']
                    
                    # Admin: toàn quyền
                    if role == 'admin':
                        return True
                    
                    # Trưởng khoa: xem tất cả trong khoa
                    if role == 'truong_khoa':
                        return True
                    
                    # Trưởng bộ môn: chỉ xem một số model liên quan
                    if role == 'truong_bo_mon':
                        allowed = ['giangvien', 'monhoc', 'gvdaymon', 'nguyenvong', 'phancong', 'lopmonhoc']
                        return model_name.lower().replace('proxy', '') in allowed
                    
                    # Giảng viên: chỉ xem nguyện vọng của mình
                    if role == 'giang_vien':
                        return model_name.lower().replace('proxy', '') == 'nguyenvong'
                    
                    return False
                
                def has_change_permission(self, request, obj=None):
                    if request.user.is_superuser:
                        return True
                    scope = get_user_scope(request.user)
                    role = scope['role']
                    
                    if role == 'admin':
                        return True
                    if role == 'truong_khoa':
                        # Trưởng khoa có thể sửa hầu hết models NGOẠI TRỪ Khoa
                        actual_model = model_name.lower().replace('proxy', '')
                        blocked = ['khoa']  # Không cho sửa Khoa
                        return actual_model not in blocked
                    if role == 'truong_bo_mon':
                        # Trưởng bộ môn chỉ sửa một số model
                        allowed = ['giangvien', 'nguyenvong']
                        return model_name.lower().replace('proxy', '') in allowed
                    # Giảng viên: chỉ sửa nguyện vọng của mình
                    if role == 'giang_vien':
                        if model_name.lower().replace('proxy', '') == 'nguyenvong':
                            # Kiểm tra obj thuộc về GV này không
                            if obj is not None:
                                return str(obj.ma_gv_id) == scope['ma_gv']
                            return True
                    return False
                
                def has_add_permission(self, request):
                    if request.user.is_superuser:
                        return True
                    scope = get_user_scope(request.user)
                    role = scope['role']
                    
                    if role == 'admin':
                        return True
                    if role == 'truong_khoa':
                        # Trưởng khoa có thể thêm hầu hết models NGOẠI TRỪ Khoa
                        actual_model = model_name.lower().replace('proxy', '')
                        blocked = ['khoa']  # Không cho thêm Khoa
                        return actual_model not in blocked
                    if role == 'truong_bo_mon':
                        # Trưởng bộ môn chỉ thêm một số model
                        allowed = ['nguyenvong']
                        return model_name.lower().replace('proxy', '') in allowed
                    # Giảng viên: chỉ thêm nguyện vọng của mình
                    if role == 'giang_vien':
                        return model_name.lower().replace('proxy', '') == 'nguyenvong'
                    return False
                
                def has_delete_permission(self, request, obj=None):
                    if request.user.is_superuser:
                        return True
                    scope = get_user_scope(request.user)
                    role = scope['role']
                    
                    if role == 'admin':
                        return True
                    if role == 'truong_khoa':
                        # Trưởng khoa có thể xóa hầu hết models NGOẠI TRỪ Khoa
                        actual_model = model_name.lower().replace('proxy', '')
                        blocked = ['khoa']  # Không cho xóa Khoa
                        return actual_model not in blocked
                    # Giảng viên: chỉ xóa nguyện vọng của mình
                    if role == 'giang_vien':
                        if model_name.lower().replace('proxy', '') == 'nguyenvong':
                            if obj is not None:
                                return str(obj.ma_gv_id) == scope['ma_gv']
                            return True
                    return False
                
                def get_queryset(self, request):
                    """Filter queryset theo role và scope của user"""
                    qs = super().get_queryset(request)
                    
                    if request.user.is_superuser:
                        return qs
                    
                    scope = get_user_scope(request.user)
                    role = scope['role']
                    ma_khoa = scope['ma_khoa']
                    ma_bo_mon = scope['ma_bo_mon']
                    
                    if role == 'admin':
                        return qs
                    
                    # Lấy tên model thực (bỏ 'proxy')
                    actual_model = model_name.lower().replace('proxy', '')
                    
                    # === TRƯỞNG KHOA: Filter theo khoa ===
                    if role == 'truong_khoa' and ma_khoa:
                        if actual_model == 'khoa':
                            return qs.filter(ma_khoa=ma_khoa)
                        elif actual_model == 'bomon':
                            return qs.filter(ma_khoa__ma_khoa=ma_khoa)
                        elif actual_model == 'giangvien':
                            return qs.filter(ma_bo_mon__ma_khoa__ma_khoa=ma_khoa)
                        elif actual_model == 'gvdaymon':
                            return qs.filter(ma_gv__ma_bo_mon__ma_khoa__ma_khoa=ma_khoa)
                        elif actual_model == 'nguyenvong':
                            return qs.filter(ma_gv__ma_bo_mon__ma_khoa__ma_khoa=ma_khoa)
                        elif actual_model == 'phancong':
                            return qs.filter(ma_gv__ma_bo_mon__ma_khoa__ma_khoa=ma_khoa)
                        elif actual_model == 'lopmonhoc':
                            # Lớp môn học của GV trong khoa
                            return qs.filter(phan_cong_list__ma_gv__ma_bo_mon__ma_khoa__ma_khoa=ma_khoa).distinct()
                        elif actual_model == 'thoikhoabieu':
                            return qs.filter(ma_lop__phan_cong_list__ma_gv__ma_bo_mon__ma_khoa__ma_khoa=ma_khoa).distinct()
                        # Các model khác (không filter theo khoa): MonHoc, PhongHoc, TimeSlot, KhungTG, DotXep, DuKienDT, RangBuocMem, NgayNghi
                        return qs
                    
                    # === TRƯỞNG BỘ MÔN: Filter theo bộ môn ===
                    if role == 'truong_bo_mon' and ma_bo_mon:
                        if actual_model == 'giangvien':
                            return qs.filter(ma_bo_mon__ma_bo_mon=ma_bo_mon)
                        elif actual_model == 'gvdaymon':
                            return qs.filter(ma_gv__ma_bo_mon__ma_bo_mon=ma_bo_mon)
                        elif actual_model == 'nguyenvong':
                            return qs.filter(ma_gv__ma_bo_mon__ma_bo_mon=ma_bo_mon)
                        elif actual_model == 'phancong':
                            return qs.filter(ma_gv__ma_bo_mon__ma_bo_mon=ma_bo_mon)
                        elif actual_model == 'lopmonhoc':
                            return qs.filter(phan_cong_list__ma_gv__ma_bo_mon__ma_bo_mon=ma_bo_mon).distinct()
                        # MonHoc: trưởng bộ môn xem tất cả môn học (không filter)
                        return qs
                    
                    # === GIẢNG VIÊN: Chỉ xem nguyện vọng của mình ===
                    if role == 'giang_vien' and scope['ma_gv']:
                        if actual_model == 'nguyenvong':
                            return qs.filter(ma_gv__ma_gv=scope['ma_gv'])
                        return qs.none()  # Không cho xem model khác
                    
                    # Mặc định: không filter
                    return qs
                
            return ProxyAdmin
        
        # Register proxy models (skip if already registered)
        proxy_mappings = [
            (KhoaProxy, KhoaAdmin, 'KhoaProxy'),
            (BoMonProxy, BoMonAdmin, 'BoMonProxy'),
            (GiangVienProxy, GiangVienAdmin, 'GiangVienProxy'),
            (MonHocProxy, MonHocAdmin, 'MonHocProxy'),
            (GVDayMonProxy, GVDayMonAdmin, 'GVDayMonProxy'),
            (PhongHocProxy, PhongHocAdmin, 'PhongHocProxy'),
            (LopMonHocProxy, LopMonHocAdmin, 'LopMonHocProxy'),
            (KhungTGProxy, KhungTGAdmin, 'KhungTGProxy'),
            (TimeSlotProxy, TimeSlotAdmin, 'TimeSlotProxy'),
            (RangBuocMemProxy, RangBuocMemAdmin, 'RangBuocMemProxy'),
            (DuKienDTProxy, DuKienDTAdmin, 'DuKienDTProxy'),
            (ThoiKhoaBieuProxy, ThoiKhoaBieuAdmin, 'ThoiKhoaBieuProxy'),
            (DotXepProxy, DotXepAdmin, 'DotXepProxy'),
            (PhanCongProxy, PhanCongAdmin, 'PhanCongProxy'),
            (RangBuocTrongDotProxy, RangBuocTrongDotAdmin, 'RangBuocTrongDotProxy'),
            (NgayNghiCoDinhProxy, NgayNghiCoDinhAdmin, 'NgayNghiCoDinhProxy'),
            (NgayNghiDotProxy, NgayNghiDotAdmin, 'NgayNghiDotProxy'),
            (NguyenVongProxy, NguyenVongAdmin, 'NguyenVongProxy'),
        ]
        
        for proxy_model, admin_class, model_name in proxy_mappings:
            if proxy_model not in admin.site._registry:
                admin.site.register(proxy_model, create_proxy_admin(admin_class, model_name))
        
        # Register helper models
        for model in [PageItems, HideShowFilter, ModelFilter]:
            if model not in admin.site._registry:
                admin.site.register(model)
