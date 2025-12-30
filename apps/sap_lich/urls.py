"""
URLs for Sap Lich app
"""

from django.urls import path
from . import views

app_name = 'sap_lich'

urlpatterns = [
    path('llm-scheduler/', views.llm_scheduler_view, name='llm_scheduler'),
    path('algo-scheduler/', views.algo_scheduler_view, name='algo_scheduler'),
    path('api/algo-scheduler/run/', views.algo_scheduler_run_api, name='algo_scheduler_run_api'),
    path('api/algo-scheduler/view-result/', views.algo_scheduler_view_result_api, name='algo_scheduler_view_result_api'),
    path('api/algo-scheduler/weights/', views.algo_scheduler_get_weights_api, name='algo_scheduler_get_weights_api'),
    path('thoikhoabieu/', views.thoikhoabieu_view, name='thoikhoabieu'),
    path('tkb-manage/', views.tkb_manage_view, name='tkb_manage'),
    
    # TKB CRUD APIs
    path('api/tkb/create/', views.tkb_create_api, name='tkb_create'),
    path('api/tkb/update/', views.tkb_update_api, name='tkb_update'),
    path('api/tkb/delete/', views.tkb_delete_api, name='tkb_delete'),
    path('api/tkb/restore/', views.tkb_restore_api, name='tkb_restore'),
    path('api/tkb/swap/', views.tkb_swap_api, name='tkb_swap'),
    path('api/tkb/mini-schedule/', views.tkb_mini_schedule_api, name='tkb_mini_schedule'),
    path('api/tkb/occupied-rooms/', views.tkb_occupied_rooms_api, name='tkb_occupied_rooms'),
    path('api/tkb/mon-hoc-info/', views.tkb_mon_hoc_info_api, name='tkb_mon_hoc_info'),
]
