#!/usr/bin/env python
"""
Debug script để kiểm tra chatbot query generation
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from apps.scheduling.services.chatbot_service import ScheduleChatbot


def test_entity_extraction():
    """Test entity extraction từ câu hỏi"""
    chatbot = ScheduleChatbot()
    
    test_questions = [
        "Có bao nhiêu giảng viên?",
        "Khoa CNTT có bao nhiêu giảng viên?",
        "Khoa Công nghệ thông tin có bao nhiêu giảng viên?",
        "Phòng trống thứ 2 ca 1",
        "Lịch dạy của giảng viên Nguyễn Văn A",
        "Thầy Minh dạy môn gì?",
        "Môn Lập trình Python có mấy tín chỉ?",
    ]
    
    print("=" * 80)
    print("🔍 TEST ENTITY EXTRACTION (Rule-based)")
    print("=" * 80)
    
    for q in test_questions:
        intent = chatbot._extract_query_intent(q)
        print(f"\n❓ Question: {q}")
        print(f"   Intent Type: {intent['type']}")
        print(f"   Query Type: {intent.get('query_type')}")
        print(f"   Entities: {intent['entities']}")


def test_database_query():
    """Test trực tiếp database query"""
    from apps.scheduling.models import Khoa, BoMon, GiangVien
    from django.db.models import Q
    
    print("\n" + "=" * 80)
    print("📊 TEST DATABASE QUERIES")
    print("=" * 80)
    
    # 1. Kiểm tra có khoa nào không
    print("\n1️⃣ Danh sách Khoa:")
    for khoa in Khoa.objects.all():
        print(f"   - {khoa.ma_khoa}: {khoa.ten_khoa}")
    
    # 2. Kiểm tra bộ môn
    print("\n2️⃣ Danh sách Bộ môn:")
    for bm in BoMon.objects.select_related('ma_khoa').all()[:10]:
        khoa_name = bm.ma_khoa.ten_khoa if bm.ma_khoa else "N/A"
        print(f"   - {bm.ma_bo_mon}: {bm.ten_bo_mon} (Khoa: {khoa_name})")
    
    # 3. Đếm giảng viên theo khoa
    print("\n3️⃣ Số giảng viên theo Khoa:")
    total = 0
    for khoa in Khoa.objects.all():
        count = GiangVien.objects.filter(ma_bo_mon__ma_khoa=khoa).count()
        print(f"   - {khoa.ten_khoa}: {count} GV")
        total += count
    print(f"   TỔNG: {total} GV")
    
    # 4. Test query với từ khóa "CNTT"
    print("\n4️⃣ Test query filter 'CNTT':")
    
    # Cách 1: Filter trực tiếp
    qs1 = GiangVien.objects.filter(
        Q(ma_bo_mon__ma_khoa__ten_khoa__icontains='CNTT') |
        Q(ma_bo_mon__ma_khoa__ma_khoa__icontains='CNTT')
    )
    print(f"   Query filter 'CNTT': {qs1.count()} GV")
    
    # Cách 2: Filter "Công nghệ"
    qs2 = GiangVien.objects.filter(
        Q(ma_bo_mon__ma_khoa__ten_khoa__icontains='Công nghệ') |
        Q(ma_bo_mon__ma_khoa__ma_khoa__icontains='Công nghệ')
    )
    print(f"   Query filter 'Công nghệ': {qs2.count()} GV")
    
    # In ra các khoa có chứa "công nghệ" hoặc "cntt"
    print("\n5️⃣ Tìm khoa có tên chứa 'công nghệ' hoặc 'cntt':")
    khoa_list = Khoa.objects.filter(
        Q(ten_khoa__icontains='công nghệ') |
        Q(ten_khoa__icontains='cntt') |
        Q(ma_khoa__icontains='cntt')
    )
    for k in khoa_list:
        print(f"   - {k.ma_khoa}: {k.ten_khoa}")
    if not khoa_list:
        print("   ⚠️ Không tìm thấy khoa nào!")


def test_execute_query():
    """Test _execute_dynamic_query"""
    chatbot = ScheduleChatbot()
    
    print("\n" + "=" * 80)
    print("🚀 TEST EXECUTE DYNAMIC QUERY")
    print("=" * 80)
    
    # Test 1: Đếm tất cả giảng viên
    intent1 = {
        'type': 'giang_vien_info',
        'query_type': 'COUNT',
        'entities': {'giang_vien': None, 'khoa': None, 'mon_hoc': None, 'phong': None, 'thu': None, 'ca': None, 'loai_phong': None, 'bo_mon': None, 'lop': None, 'dot_xep': None}
    }
    result1 = chatbot._execute_dynamic_query(intent1, None)
    print(f"\n❓ Test 1: Đếm tất cả giảng viên")
    print(f"   Result: {result1}")
    
    # Test 2: Đếm giảng viên khoa CNTT (đã map thành "Công nghệ thông tin")
    intent2 = {
        'type': 'giang_vien_info',
        'query_type': 'COUNT',
        'entities': {'giang_vien': None, 'khoa': 'Công nghệ thông tin', 'mon_hoc': None, 'phong': None, 'thu': None, 'ca': None, 'loai_phong': None, 'bo_mon': None, 'lop': None, 'dot_xep': None}
    }
    result2 = chatbot._execute_dynamic_query(intent2, None)
    print(f"\n❓ Test 2: Đếm giảng viên khoa 'Công nghệ thông tin' (từ CNTT)")
    print(f"   Result: {result2}")
    
    # Test 3: Đếm với từ khóa khác
    intent3 = {
        'type': 'giang_vien_info',
        'query_type': 'COUNT',
        'entities': {'giang_vien': None, 'khoa': 'Công nghệ', 'mon_hoc': None, 'phong': None, 'thu': None, 'ca': None, 'loai_phong': None, 'bo_mon': None, 'lop': None, 'dot_xep': None}
    }
    result3 = chatbot._execute_dynamic_query(intent3, None)
    print(f"\n❓ Test 3: Đếm giảng viên khoa 'Công nghệ'")
    print(f"   Result: {result3}")


if __name__ == "__main__":
    test_entity_extraction()
    test_database_query()
    test_execute_query()
    
    print("\n" + "=" * 80)
    print("✅ DEBUG COMPLETE")
    print("=" * 80)
