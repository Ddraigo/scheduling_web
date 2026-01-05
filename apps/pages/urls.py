from django.urls import path
from django.contrib.auth.views import LogoutView

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.user_login_view, name='user_login'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
]
