"""core URL Configuration"""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter
from apps.scheduling import views as views_scheduling
from apps.sap_lich import views as views_sap_lich

# Create router for scheduling ViewSets
scheduler_router = DefaultRouter()
scheduler_router.register(r'khoa', views_scheduling.KhoaViewSet, basename='khoa')
scheduler_router.register(r'bo-mon', views_scheduling.BoMonViewSet, basename='bomon')
scheduler_router.register(r'giang-vien', views_scheduling.GiangVienViewSet, basename='giangvien')
scheduler_router.register(r'mon-hoc', views_scheduling.MonHocViewSet, basename='monhoc')
scheduler_router.register(r'phong-hoc', views_scheduling.PhongHocViewSet, basename='phonghoc')
scheduler_router.register(r'lop-mon-hoc', views_scheduling.LopMonHocViewSet, basename='lopmonhoc')
scheduler_router.register(r'dot-xep', views_scheduling.DotXepViewSet, basename='dotxep')
scheduler_router.register(r'phan-cong', views_scheduling.PhanCongViewSet, basename='phancong')
scheduler_router.register(r'time-slot', views_scheduling.TimeSlotViewSet, basename='timeslot')
scheduler_router.register(r'thoi-khoa-bieu', views_scheduling.ThoiKhoaBieuViewSet, basename='thoikhoabieu')
scheduler_router.register(r'schedule-generation', views_scheduling.ScheduleGenerationViewSet, basename='schedule-generation')

urlpatterns = [
    # Redirect root to admin dashboard
    path('', lambda request: redirect('/admin/', permanent=False)),

    path('', include('apps.pages.urls')),
    path('', include('apps.data_table.urls')),
    path('charts/', include('apps.charts.urls')),
    
    # Scheduling API - Custom endpoints FIRST, then ViewSet routes
    # ⭐ MUST BE BEFORE dyn_api to prevent matching 'llm_scheduler' as model_name
    path('api/scheduling/llm_scheduler/', views_scheduling.llm_scheduler_api, name='llm-scheduler'),
    path('api/scheduling/chatbot/', views_scheduling.chatbot_api, name='chatbot-api'),
    path('api/scheduling/chatbot/history/', views_scheduling.chatbot_history_api, name='chatbot-history'),
    path('api/scheduling/chatbot/clear/', views_scheduling.chatbot_clear_api, name='chatbot-clear'),
    path('api/scheduling/token_stats/', views_scheduling.token_stats_api, name='token-stats'),
    path('api/scheduling/debug/dotxep/', views_scheduling.debug_dotxep_api, name='debug-dotxep'),
    path('api/scheduling/', include(scheduler_router.urls)),  # Then all ViewSets
    
    # Empty scheduling app include (all routes above)
    path('api/scheduling/', include('apps.scheduling.urls')),
    
    # Sap Lich app (timetabling views)
    path('', include('apps.sap_lich.urls')),
    
    # DynAPI MUST BE LAST to prevent greedy matching of api/<model_name>/
    path('', include('apps.dyn_api.urls')),
    
    # Sap Lich admin pages (must be before admin/ to work)
    path('admin/sap_lich/llm-scheduler/', admin.site.admin_view(views_sap_lich.llm_scheduler_view), name='sap_lich_llm_scheduler'),
    path('admin/sap_lich/algo-scheduler/', admin.site.admin_view(views_sap_lich.algo_scheduler_view), name='sap_lich_algo_scheduler'),
    path('admin/sap_lich/thoikhoabieu/', admin.site.admin_view(views_sap_lich.thoikhoabieu_view), name='sap_lich_thoikhoabieu'),
    path('admin/sap_lich/tkb-manage/', admin.site.admin_view(views_sap_lich.tkb_manage_view), name='sap_lich_tkb_manage'),
    
    path("admin/", admin.site.urls),
    path("", include('admin_black.urls')),
]

# Lazy-load on routing is needed
try:
    urlpatterns.append( path("api/", include("api.urls")) )
    urlpatterns.append( path("login/jwt/", view=obtain_auth_token) )
except:
    pass