"""
Serializers for Scheduling API
"""

from rest_framework import serializers
from .models import (
    Khoa, BoMon, GiangVien, MonHoc, PhongHoc,
    LopMonHoc, DotXep, PhanCong, TimeSlot, ThoiKhoaBieu
)


class KhoaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Khoa
        fields = '__all__'


class BoMonSerializer(serializers.ModelSerializer):
    khoa_ten = serializers.CharField(source='khoa.ten_khoa', read_only=True)
    
    class Meta:
        model = BoMon
        fields = '__all__'


class GiangVienSerializer(serializers.ModelSerializer):
    bo_mon_ten = serializers.CharField(source='bo_mon.ten_bo_mon', read_only=True)
    
    class Meta:
        model = GiangVien
        fields = '__all__'


class MonHocSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonHoc
        fields = '__all__'


class PhongHocSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhongHoc
        fields = '__all__'


class LopMonHocSerializer(serializers.ModelSerializer):
    mon_hoc_ten = serializers.CharField(source='mon_hoc.ten_mon_hoc', read_only=True)
    
    class Meta:
        model = LopMonHoc
        fields = '__all__'


class DotXepSerializer(serializers.ModelSerializer):
    class Meta:
        model = DotXep
        fields = '__all__'


class PhanCongSerializer(serializers.ModelSerializer):
    giang_vien_ten = serializers.CharField(source='giang_vien.ten_gv', read_only=True)
    lop_ten = serializers.CharField(source='lop_mon_hoc.ten_lop', read_only=True)
    mon_hoc_ten = serializers.CharField(source='lop_mon_hoc.mon_hoc.ten_mon_hoc', read_only=True)
    
    class Meta:
        model = PhanCong
        fields = '__all__'


class TimeSlotSerializer(serializers.ModelSerializer):
    thu_text = serializers.SerializerMethodField()
    
    class Meta:
        model = TimeSlot
        fields = '__all__'
    
    def get_thu_text(self, obj):
        thu_map = {2: 'Thứ 2', 3: 'Thứ 3', 4: 'Thứ 4', 
                   5: 'Thứ 5', 6: 'Thứ 6', 7: 'Thứ 7'}
        return thu_map.get(obj.thu, f'Thứ {obj.thu}')


class ThoiKhoaBieuSerializer(serializers.ModelSerializer):
    lop_ten = serializers.CharField(source='lop_mon_hoc.ten_lop', read_only=True)
    mon_hoc_ten = serializers.CharField(source='lop_mon_hoc.mon_hoc.ten_mon_hoc', read_only=True)
    phong_ten = serializers.CharField(source='phong_hoc.ten_phong', read_only=True)
    giang_vien_ten = serializers.SerializerMethodField()
    time_info = serializers.SerializerMethodField()
    
    class Meta:
        model = ThoiKhoaBieu
        fields = '__all__'
    
    def get_giang_vien_ten(self, obj):
        if obj.phan_cong:
            return obj.phan_cong.giang_vien.ten_gv
        return None
    
    def get_time_info(self, obj):
        return {
            'thu': obj.time_slot.thu,
            'tiet_bat_dau': obj.time_slot.tiet_bat_dau,
            'so_tiet': obj.time_slot.so_tiet,
            'gio_bat_dau': obj.time_slot.gio_bat_dau.strftime('%H:%M'),
            'gio_ket_thuc': obj.time_slot.gio_ket_thuc.strftime('%H:%M'),
        }


class ScheduleGenerationSerializer(serializers.Serializer):
    """Serializer for schedule generation request"""
    ma_dot = serializers.CharField(max_length=20)
    use_ai = serializers.BooleanField(default=True)
    force_regenerate = serializers.BooleanField(default=False)
