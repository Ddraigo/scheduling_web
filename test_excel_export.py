"""
Test Excel Export Functionality
Run: python test_excel_export.py
"""

import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import Khoa, GiangVien, MonHoc, PhongHoc
from apps.scheduling.utils.excel_export import ExcelExporter

def test_export():
    print("=" * 70)
    print("TESTING EXCEL EXPORT FUNCTIONALITY")
    print("=" * 70)
    
    # Test 1: Export Khoa
    print("\n[1] Testing Khoa export...")
    khoa_qs = Khoa.objects.all()[:5]
    if khoa_qs.exists():
        response = ExcelExporter.export_khoa(khoa_qs)
        print(f"✓ Khoa export successful: {response['Content-Disposition']}")
        print(f"  - Total records: {khoa_qs.count()}")
    else:
        print("✗ No Khoa data found")
    
    # Test 2: Export GiangVien
    print("\n[2] Testing GiangVien export...")
    gv_qs = GiangVien.objects.all()[:10]
    if gv_qs.exists():
        response = ExcelExporter.export_giang_vien(gv_qs)
        print(f"✓ GiangVien export successful: {response['Content-Disposition']}")
        print(f"  - Total records: {gv_qs.count()}")
        
        # Show sample data
        print("  - Sample data:")
        for gv in gv_qs[:3]:
            print(f"    • {gv.ma_gv} - {gv.ten_gv} ({gv.ma_bo_mon.ten_bo_mon})")
    else:
        print("✗ No GiangVien data found")
    
    # Test 3: Export MonHoc
    print("\n[3] Testing MonHoc export...")
    mh_qs = MonHoc.objects.all()[:10]
    if mh_qs.exists():
        response = ExcelExporter.export_mon_hoc(mh_qs)
        print(f"✓ MonHoc export successful: {response['Content-Disposition']}")
        print(f"  - Total records: {mh_qs.count()}")
    else:
        print("✗ No MonHoc data found")
    
    # Test 4: Export PhongHoc
    print("\n[4] Testing PhongHoc export...")
    ph_qs = PhongHoc.objects.all()[:10]
    if ph_qs.exists():
        response = ExcelExporter.export_phong_hoc(ph_qs)
        print(f"✓ PhongHoc export successful: {response['Content-Disposition']}")
        print(f"  - Total records: {ph_qs.count()}")
    else:
        print("✗ No PhongHoc data found")
    
    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED!")
    print("=" * 70)
    print("\nℹ️  To use in Admin:")
    print("1. Go to http://localhost:8000/admin/")
    print("2. Navigate to any model (e.g., Scheduling > Giảng viên)")
    print("3. Select records to export")
    print("4. Choose 'Xuất Excel (.xlsx)' from Actions dropdown")
    print("5. Click 'Go' - file will download automatically")
    print()

if __name__ == '__main__':
    try:
        test_export()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
