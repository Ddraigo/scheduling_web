# Generated migration for setting up group permissions
from django.db import migrations


def setup_group_permissions(apps, schema_editor):
    """Gán permissions cho các groups"""
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    
    # Lấy content types
    try:
        sap_lich_ct = ContentType.objects.get(app_label='sap_lich', model='saplich')
    except ContentType.DoesNotExist:
        print("ContentType sap_lich.saplich không tồn tại, bỏ qua...")
        sap_lich_ct = None
    
    # ThoiKhoaBieu thuộc app scheduling
    try:
        tkb_ct = ContentType.objects.get(app_label='scheduling', model='thoikhoabieu')
    except ContentType.DoesNotExist:
        print("ContentType scheduling.thoikhoabieu không tồn tại, bỏ qua...")
        tkb_ct = None
    
    # Lấy permissions
    view_saplich = None
    if sap_lich_ct:
        view_saplich = Permission.objects.filter(codename='view_saplich', content_type=sap_lich_ct).first()
    
    view_tkb = change_tkb = add_tkb = delete_tkb = None
    if tkb_ct:
        view_tkb = Permission.objects.filter(codename='view_thoikhoabieu', content_type=tkb_ct).first()
        change_tkb = Permission.objects.filter(codename='change_thoikhoabieu', content_type=tkb_ct).first()
        add_tkb = Permission.objects.filter(codename='add_thoikhoabieu', content_type=tkb_ct).first()
        delete_tkb = Permission.objects.filter(codename='delete_thoikhoabieu', content_type=tkb_ct).first()
    
    # auth.view_user permission
    try:
        user_ct = ContentType.objects.get(app_label='auth', model='user')
        view_user = Permission.objects.filter(codename='view_user', content_type=user_ct).first()
    except:
        view_user = None
    
    # Định nghĩa permissions cho từng group
    # Tên group có thể là tiếng Việt có dấu hoặc không dấu
    group_permissions = {
        # Trưởng Khoa - có quyền view và change TKB (trong phạm vi khoa)
        'Trưởng Khoa': [view_saplich, view_tkb, change_tkb, view_user],
        'Truong_Khoa': [view_saplich, view_tkb, change_tkb, view_user],
        
        # Trưởng Bộ Môn - có quyền view và change TKB (trong phạm vi bộ môn)
        'Trưởng Bộ Môn': [view_saplich, view_tkb, change_tkb, view_user],
        'Truong_Bo_Mon': [view_saplich, view_tkb, change_tkb, view_user],
        
        # Giảng Viên - chỉ có quyền view
        'Giảng Viên': [view_saplich, view_tkb, view_user],
        'Giang_Vien': [view_saplich, view_tkb, view_user],
    }
    
    for group_name, perms in group_permissions.items():
        try:
            group = Group.objects.get(name=group_name)
            for perm in perms:
                if perm:
                    group.permissions.add(perm)
            print(f"✅ Đã gán permissions cho group: {group_name}")
        except Group.DoesNotExist:
            # Group không tồn tại, bỏ qua
            pass


def reverse_permissions(apps, schema_editor):
    """Gỡ bỏ permissions (rollback)"""
    # Không làm gì để giữ nguyên permissions khi rollback
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sap_lich', '0002_saplich_delete_saplichproxy'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(setup_group_permissions, reverse_permissions),
    ]
