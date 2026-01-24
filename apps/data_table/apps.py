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
        
        # Wrapper to override has_module_permission
        def create_proxy_admin(base_class):
            class ProxyAdmin(base_class):
                def has_module_permission(self, request):
                    return True
            return ProxyAdmin
        
        # Register proxy models (skip if already registered)
        proxy_mappings = [
            (KhoaProxy, KhoaAdmin),
            (BoMonProxy, BoMonAdmin),
            (GiangVienProxy, GiangVienAdmin),
            (MonHocProxy, MonHocAdmin),
            (GVDayMonProxy, GVDayMonAdmin),
            (PhongHocProxy, PhongHocAdmin),
            (LopMonHocProxy, LopMonHocAdmin),
            (KhungTGProxy, KhungTGAdmin),
            (TimeSlotProxy, TimeSlotAdmin),
            (RangBuocMemProxy, RangBuocMemAdmin),
            (DuKienDTProxy, DuKienDTAdmin),
            (ThoiKhoaBieuProxy, ThoiKhoaBieuAdmin),
            (DotXepProxy, DotXepAdmin),
            (PhanCongProxy, PhanCongAdmin),
            (RangBuocTrongDotProxy, RangBuocTrongDotAdmin),
            (NgayNghiCoDinhProxy, NgayNghiCoDinhAdmin),
            (NgayNghiDotProxy, NgayNghiDotAdmin),
            (NguyenVongProxy, NguyenVongAdmin),
        ]
        
        for proxy_model, admin_class in proxy_mappings:
            if proxy_model not in admin.site._registry:
                admin.site.register(proxy_model, create_proxy_admin(admin_class))
        
        # Register helper models
        for model in [PageItems, HideShowFilter, ModelFilter]:
            if model not in admin.site._registry:
                admin.site.register(model)
