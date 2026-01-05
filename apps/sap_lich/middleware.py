"""
Middleware để filter menu admin dựa theo role của user

PHÂN QUYỀN:
- Admin (superuser): Tất cả (sắp lịch, chat bot, xem TKB, quản lý TKB, scheduling models)
- Trưởng Khoa: Xem TKB, tất cả scheduling models
- Trưởng Bộ Môn: Xem TKB, một số scheduling models
- Giảng Viên: Chỉ xem TKB (của mình)
"""


class AdminMenuFilterMiddleware:
    """
    Middleware để custom admin sidebar menu dựa trên groups của user
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_template_response(self, request, response):
        """
        Modify template context để filter admin menu
        """
        if hasattr(response, 'context_data') and request.path.startswith('/admin/'):
            if request.user.is_authenticated:
                is_admin = request.user.is_superuser
                groups = request.user.groups.values_list('name', flat=True)
                is_truong_khoa = 'Trưởng Khoa' in groups
                is_truong_bo_mon = 'Trưởng Bộ Môn' in groups
                is_giang_vien = 'Giảng Viên' in groups
                
                # Filter available_apps trong context
                if 'available_apps' in response.context_data:
                    available_apps = response.context_data['available_apps']
                    filtered_apps = []
                    
                    for app in available_apps:
                        app_label = app.get('app_label', '')
                        
                        # Admin thấy tất cả
                        if is_admin:
                            filtered_apps.append(app)
                            continue
                        
                        # Filter theo role cho non-admin
                        if app_label == 'sap_lich':
                            # Tất cả roles (TK, TBM, GV) thấy app sap_lich nhưng menu sẽ bị filter
                            if is_truong_khoa or is_truong_bo_mon or is_giang_vien:
                                # Filter custom_links - chỉ giữ lại "Xem thời khóa biểu"
                                app_copy = dict(app)
                                if 'models' in app_copy:
                                    # Giữ nguyên models nhưng filter custom links sẽ xử lý ở jazzmin
                                    pass
                                filtered_apps.append(app_copy)
                        
                        elif app_label == 'scheduling':
                            # Trưởng Khoa thấy tất cả models
                            if is_truong_khoa:
                                filtered_apps.append(app)
                            elif is_truong_bo_mon:
                                # Trưởng Bộ Môn chỉ thấy một số models
                                allowed_models = ['monhoc', 'giangvien', 'nguyenvong', 'gvdaymon', 'phancong']
                                filtered_models = []
                                for model in app.get('models', []):
                                    model_name = model.get('object_name', '').lower()
                                    if model_name in allowed_models:
                                        filtered_models.append(model)
                                if filtered_models:
                                    app_copy = dict(app)
                                    app_copy['models'] = filtered_models
                                    filtered_apps.append(app_copy)
                            # Giảng Viên không thấy scheduling app
                        
                        elif app_label == 'auth':
                            # Chỉ admin thấy auth app
                            pass  # Không thêm vào filtered_apps
                        
                        elif app_label == 'data_table':
                            # Admin và Truong_Khoa thấy data_table
                            if is_truong_khoa:
                                filtered_apps.append(app)
                        
                        # Các app khác - chỉ admin thấy (đã xử lý ở trên)
                    
                    response.context_data['available_apps'] = filtered_apps
        
        return response
