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
]
