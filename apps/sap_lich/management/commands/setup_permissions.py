"""
Management command: Setup permissions cho hệ thống TKB
Tự động tạo groups và gán permissions cho từng role

USAGE:
    python manage.py setup_permissions

CHỨC NĂNG:
1. Tạo 3 groups: Truong_Khoa, Truong_Bo_Mon, Giang_Vien (tương thích cả tên có dấu)
2. Gán permissions phù hợp cho mỗi group theo RBAC policy
3. Đảm bảo Jazzmin sidebar hiển thị đúng menu theo permissions

DEPLOY:
- Chạy command này sau mỗi lần migrate hoặc khi setup môi trường mới
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from apps.scheduling.models import (
    Khoa, BoMon, GiangVien, MonHoc, PhongHoc,
    LopMonHoc, DotXep, PhanCong, ThoiKhoaBieu,
    GVDayMon, KhungTG, RangBuocMem, RangBuocTrongDot,
    DuKienDT, NgayNghiCoDinh, NgayNghiDot, NguyenVong, TimeSlot
)


class Command(BaseCommand):
    help = 'Setup permissions cho hệ thống TKB (RBAC)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== SETUP PERMISSIONS - HỆ THỐNG TKB ===\n'))
        
        # 1. TẠO GROUPS (tương thích cả tên cũ có dấu)
        self.stdout.write('1. Tạo Groups...')
        
        groups_config = [
            {
                'name': 'Truong_Khoa',
                'alias': 'Trưởng Khoa',
                'description': 'Trưởng Khoa - Quản lý TKB trong khoa'
            },
            {
                'name': 'Truong_Bo_Mon',
                'alias': 'Trưởng Bộ Môn',
                'description': 'Trưởng Bộ Môn - Xem TKB trong bộ môn'
            },
            {
                'name': 'Giang_Vien',
                'alias': 'Giảng Viên',
                'description': 'Giảng Viên - Xem TKB của mình'
            },
        ]
        
        groups = {}
        for config in groups_config:
            # Tạo group với tên không dấu (chuẩn)
            group, created = Group.objects.get_or_create(name=config['name'])
            groups[config['name']] = group
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Tạo group: {config['name']} ({config['alias']})"))
            else:
                self.stdout.write(f"  - Group đã tồn tại: {config['name']}")
            
            # Tạo group với tên có dấu (tương thích cũ) nếu chưa có
            group_alias, created_alias = Group.objects.get_or_create(name=config['alias'])
            if created_alias:
                self.stdout.write(self.style.WARNING(f"  ⚠ Tạo alias group: {config['alias']} (tương thích cũ)"))
        
        # 2. GÁN PERMISSIONS
        self.stdout.write('\n2. Gán Permissions cho Groups...')
        
        # === TRƯỞNG KHOA: Quản lý TKB trong khoa ===
        self.stdout.write('\n  [TRƯỞNG KHOA]')
        truong_khoa = groups['Truong_Khoa']
        truong_khoa_perms = [
            # TKB: view + change
            ('scheduling', 'thoikhoabieu', 'view'),
            ('scheduling', 'thoikhoabieu', 'change'),
            
            # Quản lý dữ liệu khoa
            ('scheduling', 'khoa', 'view'),
            ('scheduling', 'bomon', 'view'),
            ('scheduling', 'giangvien', 'view'),
            ('scheduling', 'monhoc', 'view'),
            ('scheduling', 'gvdaymon', 'view'),
            ('scheduling', 'phonghoc', 'view'),
            ('scheduling', 'lopmonhoc', 'view'),
            ('scheduling', 'dotxep', 'view'),
            ('scheduling', 'phancong', 'view'),
            ('scheduling', 'phancong', 'change'),  # Có thể sửa phân công
            ('scheduling', 'nguyenvong', 'view'),
        ]
        self._assign_permissions(truong_khoa, truong_khoa_perms)
        
        # Gán cho alias group (tương thích cũ)
        truong_khoa_alias = Group.objects.get(name='Trưởng Khoa')
        self._assign_permissions(truong_khoa_alias, truong_khoa_perms)
        
        # === TRƯỞNG BỘ MÔN: Xem TKB trong bộ môn ===
        self.stdout.write('\n  [TRƯỞNG BỘ MÔN]')
        truong_bo_mon = groups['Truong_Bo_Mon']
        truong_bo_mon_perms = [
            # TKB: chỉ view
            ('scheduling', 'thoikhoabieu', 'view'),
            
            # Xem dữ liệu bộ môn
            ('scheduling', 'bomon', 'view'),
            ('scheduling', 'giangvien', 'view'),
            ('scheduling', 'phancong', 'view'),
            ('scheduling', 'nguyenvong', 'view'),
        ]
        self._assign_permissions(truong_bo_mon, truong_bo_mon_perms)
        
        # Gán cho alias
        truong_bo_mon_alias = Group.objects.get(name='Trưởng Bộ Môn')
        self._assign_permissions(truong_bo_mon_alias, truong_bo_mon_perms)
        
        # === GIẢNG VIÊN: Xem TKB của mình + Nguyện vọng ===
        self.stdout.write('\n  [GIẢNG VIÊN]')
        giang_vien = groups['Giang_Vien']
        giang_vien_perms = [
            # TKB: chỉ view (scope filter sẽ hạn chế chỉ thấy của mình)
            ('scheduling', 'thoikhoabieu', 'view'),
            
            # Nguyện vọng: view + add + change
            ('scheduling', 'nguyenvong', 'view'),
            ('scheduling', 'nguyenvong', 'add'),
            ('scheduling', 'nguyenvong', 'change'),
        ]
        self._assign_permissions(giang_vien, giang_vien_perms)
        
        # Gán cho alias
        giang_vien_alias = Group.objects.get(name='Giảng Viên')
        self._assign_permissions(giang_vien_alias, giang_vien_perms)
        
        self.stdout.write(self.style.SUCCESS('\n✅ HOÀN TẤT SETUP PERMISSIONS!'))
        self.stdout.write(self.style.WARNING('\n📝 LƯU Ý:'))
        self.stdout.write('  - Superuser luôn có toàn quyền (không cần group)')
        self.stdout.write('  - Jazzmin sidebar hiển thị menu dựa trên permissions')
        self.stdout.write('  - API ViewSets enforce scope filter theo role')
        self.stdout.write('  - User cần được add vào group để có quyền truy cập\n')
    
    def _assign_permissions(self, group, perms_config):
        """
        Gán permissions cho group
        
        Args:
            group: Group object
            perms_config: List of tuples (app_label, model_name, codename)
        """
        count = 0
        for app_label, model_name, action in perms_config:
            try:
                # Get ContentType
                model_class = self._get_model_class(model_name)
                content_type = ContentType.objects.get_for_model(model_class)
                
                # Get permission
                codename = f'{action}_{model_name}'
                permission = Permission.objects.get(
                    content_type=content_type,
                    codename=codename
                )
                
                # Add to group
                group.permissions.add(permission)
                count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"    ✗ Lỗi: {app_label}.{model_name}.{action} - {e}")
                )
        
        self.stdout.write(self.style.SUCCESS(f"    ✓ Gán {count} permissions cho {group.name}"))
    
    def _get_model_class(self, model_name):
        """Map model name to model class"""
        model_map = {
            'khoa': Khoa,
            'bomon': BoMon,
            'giangvien': GiangVien,
            'monhoc': MonHoc,
            'phonghoc': PhongHoc,
            'lopmonhoc': LopMonHoc,
            'dotxep': DotXep,
            'phancong': PhanCong,
            'thoikhoabieu': ThoiKhoaBieu,
            'gvdaymon': GVDayMon,
            'khungtg': KhungTG,
            'rangbuocmem': RangBuocMem,
            'rangbuoctrongdot': RangBuocTrongDot,
            'dukiendt': DuKienDT,
            'ngaynghicodinh': NgayNghiCoDinh,
            'ngaynghidot': NgayNghiDot,
            'nguyenvong': NguyenVong,
            'timeslot': TimeSlot,
        }
        return model_map[model_name]
