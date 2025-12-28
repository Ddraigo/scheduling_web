"""
Middleware để filter menu admin dựa theo role của user
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
                # Lấy thông tin role từ context processor
                is_admin = request.user.is_superuser
                groups = request.user.groups.values_list('name', flat=True)
                is_truong_khoa = 'Truong_Khoa' in groups
                is_truong_bo_mon = 'Truong_Bo_Mon' in groups
                is_giang_vien = 'Giang_Vien' in groups
                
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
                        
                        # Filter theo role
                        if app_label == 'sap_lich':
                            # Truong_Khoa và Truong_Bo_Mon thấy sap_lich
                            if is_truong_khoa or is_truong_bo_mon:
                                filtered_apps.append(app)
                        
                        elif app_label == 'scheduling':
                            # Filter models trong scheduling app
                            if is_truong_khoa:
                                # Truong_Khoa thấy tất cả models
                                filtered_apps.append(app)
                            elif is_truong_bo_mon:
                                # Truong_Bo_Mon chỉ thấy một số models
                                allowed_models = [
                                    'monhoc', 'giangvien', 'nguyenvong',
                                    'gvdaymon', 'phancong'
                                ]
                                filtered_models = []
                                for model in app.get('models', []):
                                    model_name = model.get('object_name', '').lower()
                                    if model_name in allowed_models:
                                        filtered_models.append(model)
                                
                                if filtered_models:
                                    app_copy = app.copy()
                                    app_copy['models'] = filtered_models
                                    filtered_apps.append(app_copy)
                            # Giang_Vien không thấy scheduling app
                        
                        elif app_label == 'auth':
                            # Chỉ admin thấy auth app
                            if is_admin:
                                filtered_apps.append(app)
                        
                        elif app_label == 'data_table':
                            # Admin và Truong_Khoa thấy data_table
                            if is_admin or is_truong_khoa:
                                filtered_apps.append(app)
                        
                        else:
                            # Các app khác - mặc định chỉ admin thấy
                            if is_admin:
                                filtered_apps.append(app)
                    
                    response.context_data['available_apps'] = filtered_apps
        
        return response
