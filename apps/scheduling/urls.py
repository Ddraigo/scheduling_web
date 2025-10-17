"""
URL routing for Scheduling app
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'khoa', views.KhoaViewSet, basename='khoa')
router.register(r'bo-mon', views.BoMonViewSet, basename='bomon')
router.register(r'giang-vien', views.GiangVienViewSet, basename='giangvien')
router.register(r'mon-hoc', views.MonHocViewSet, basename='monhoc')
router.register(r'phong-hoc', views.PhongHocViewSet, basename='phonghoc')
router.register(r'lop-mon-hoc', views.LopMonHocViewSet, basename='lopmonhoc')
router.register(r'dot-xep', views.DotXepViewSet, basename='dotxep')
router.register(r'phan-cong', views.PhanCongViewSet, basename='phancong')
router.register(r'time-slot', views.TimeSlotViewSet, basename='timeslot')
router.register(r'thoi-khoa-bieu', views.ThoiKhoaBieuViewSet, basename='thoikhoabieu')
router.register(r'schedule-generation', views.ScheduleGenerationViewSet, basename='schedule-generation')

app_name = 'scheduling'

urlpatterns = [
    path('', include(router.urls)),
]
