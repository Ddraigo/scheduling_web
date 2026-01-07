from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib import messages

# Create your views here.

def index(request):
    # Page from the theme 
    return render(request, 'pages/dashboard.html')


def user_login_view(request):
    """
    Trang đăng nhập cho users (không phải admin)
    - Nếu user là superuser, yêu cầu dùng trang admin login
    - Nếu user là role khác, cho phép đăng nhập bình thường
    """
    # Nếu đã đăng nhập rồi, redirect về trang chủ
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('/admin/')
        return redirect('/')
    
    error = None
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Chỉ yêu cầu superuser dùng trang admin login
            if user.is_superuser:
                error = "Vui lòng sử dụng trang đăng nhập Admin."
            else:
                # Auto-fix is_staff nếu user có role nhưng chưa là staff
                if not user.is_staff:
                    groups = user.groups.values_list('name', flat=True)
                    allowed_groups = ['Truong_Khoa', 'Truong_Bo_Mon', 'Giang_Vien']
                    if any(group in allowed_groups for group in groups):
                        user.is_staff = True
                        user.save(update_fields=['is_staff'])
                
                # Đăng nhập thành công cho non-superuser
                login(request, user)
                next_url = request.GET.get('next', '/')
                return redirect(next_url)
        else:
            error = "Tên đăng nhập hoặc mật khẩu không đúng."
    
    return render(request, 'user/login.html', {'error': error})
