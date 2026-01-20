"""
Custom Admin Login View - Chỉ cho phép superuser đăng nhập
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import admin
from django.contrib import messages


def admin_login_view(request):
    """
    Trang đăng nhập Admin - chỉ cho phép superuser
    """
    # Nếu đã đăng nhập
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('/admin/')
        else:
            # Non-superuser đã đăng nhập, logout và hiện lỗi
            return redirect('/login/')
    
    error = None
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Chỉ cho phép superuser
            if user.is_superuser:
                login(request, user)
                next_url = request.POST.get('next', '/admin/')
                return redirect(next_url)
            else:
                error = "Tài khoản này không có quyền truy cập Admin. Vui lòng sử dụng trang đăng nhập dành cho người dùng."
        else:
            error = "Tên đăng nhập hoặc mật khẩu không đúng."
    
    # Lấy next parameter từ GET
    next_url = request.GET.get('next', '/admin/')
    
    # Set current_app for proper admin context if user is authenticated
    if request.user.is_authenticated and request.user.is_superuser:
        request.current_app = admin.site.name
        base_ctx = admin.site.each_context(request)
    else:
        base_ctx = {}
    
    context = {
        **base_ctx,
        'error': error,
        'next': next_url,
        'title': 'Đăng nhập Admin',
    }
    
    return render(request, 'admin/custom_login.html', context)
