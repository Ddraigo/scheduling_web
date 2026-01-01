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
    path('api/algo-scheduler/stats/', views.algo_scheduler_get_stats_api, name='algo_scheduler_get_stats_api'),
    path('api/algo-scheduler/view-result/', views.algo_scheduler_view_result_api, name='algo_scheduler_view_result_api'),
    path('api/algo-scheduler/weights/', views.algo_scheduler_get_weights_api, name='algo_scheduler_get_weights_api'),
    path('api/algo-scheduler/export-excel/', views.algo_scheduler_export_excel_api, name='algo_scheduler_export_excel_api'),
    path('thoikhoabieu/', views.thoikhoabieu_view, name='thoikhoabieu'),
]
