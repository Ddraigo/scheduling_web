"""
Ví dụ sử dụng Data Access Layer + LLM Service
Cách áp dụng vào API và views
"""

from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .data_access_layer import DataAccessLayer
from .llm_service import LLMDataProcessor, LLMPromptBuilder, get_dataset_json, get_conflict_report_json


# ======================== EXAMPLE 1: API LẤY DATASET CHO LLM ========================

@api_view(['GET'])
def api_get_dataset_for_llm(request, ma_dot):
    """
    API endpoint lấy toàn bộ dataset cho LLM
    Sử dụng DataAccessLayer để lấy dữ liệu tối ưu
    
    URL: /api/scheduling/dataset-for-llm/<ma_dot>/
    """
    try:
        processor = LLMDataProcessor()
        dataset = processor.prepare_dataset_for_llm_prompt(ma_dot)
        
        return Response({
            'success': True,
            'data': dataset
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# ======================== EXAMPLE 2: API PHÁT HIỆN XUNG ĐỘT ========================

@api_view(['GET'])
def api_detect_scheduling_conflicts(request, ma_dot):
    """
    API endpoint phát hiện xung đột trong lịch học
    Dùng cho LLM để tìm vấn đề cần sửa
    
    URL: /api/scheduling/conflicts/<ma_dot>/
    """
    try:
        processor = LLMDataProcessor()
        conflicts = processor.detect_scheduling_conflicts(ma_dot)
        
        return Response({
            'success': True,
            'conflicts': conflicts,
            'total_conflicts': sum(len(v) for v in conflicts.values())
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# ======================== EXAMPLE 3: LẤY LỊCH GIẢNG VIÊN ========================

@api_view(['GET'])
def api_get_giang_vien_schedule(request, ma_gv):
    """
    API endpoint lấy lịch dạy của giảng viên
    Tối ưu hóa query để tránh N+1 problem
    
    URL: /api/scheduling/giang-vien/<ma_gv>/schedule/
    """
    try:
        processor = LLMDataProcessor()
        gv_data = processor.prepare_giang_vien_schedule_for_llm(ma_gv)
        
        return Response({
            'success': True,
            'data': gv_data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# ======================== EXAMPLE 4: TÌM PHÒNG PHÙ HỢP ========================

@api_view(['POST'])
def api_find_suitable_rooms(request):
    """
    API endpoint tìm phòng học phù hợp cho lớp
    
    POST data:
    {
        "so_luong_sv": 40,
        "yeu_cau_thiet_bi": "PC"
    }
    
    URL: /api/scheduling/find-rooms/
    """
    try:
        so_luong_sv = request.data.get('so_luong_sv')
        yeu_cau_thiet_bi = request.data.get('yeu_cau_thiet_bi')
        
        processor = LLMDataProcessor()
        phong_list = processor.get_phong_hoc_truong_hop_dat_yeu_cau(
            so_luong_sv, yeu_cau_thiet_bi
        )
        
        return Response({
            'success': True,
            'so_phong_phu_hop': len(phong_list),
            'phong_list': phong_list
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# ======================== EXAMPLE 5: LẤY GIẢNG VIÊN TRỐNG ========================

@api_view(['GET'])
def api_get_available_giang_vien(request, ma_time_slot):
    """
    API endpoint lấy danh sách giảng viên trống trong time slot
    
    URL: /api/scheduling/available-giang-vien/<ma_time_slot>/
    """
    try:
        processor = LLMDataProcessor()
        gv_list = processor.get_giang_vien_trong_time_slot(ma_time_slot)
        
        return Response({
            'success': True,
            'time_slot': ma_time_slot,
            'so_giang_vien_trong': len(gv_list),
            'giang_vien_list': gv_list
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# ======================== EXAMPLE 6: LẤY THỐNG KÊ ĐỢT XẾP ========================

@api_view(['GET'])
def api_get_dot_xep_statistics(request, ma_dot):
    """
    API endpoint lấy thống kê đợt xếp
    
    URL: /api/scheduling/dot-statistics/<ma_dot>/
    """
    try:
        thong_ke = DataAccessLayer.get_thong_ke_dot_xep(ma_dot)
        
        return Response({
            'success': True,
            'statistics': thong_ke
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# ======================== EXAMPLE 7: BUILD PROMPT CHO LLM ========================

@api_view(['GET'])
def api_build_llm_prompt(request, ma_dot):
    """
    API endpoint xây dựng prompt cho LLM
    
    URL: /api/scheduling/build-llm-prompt/<ma_dot>/
    """
    try:
        prompt = LLMPromptBuilder.build_scheduling_context_prompt(ma_dot)
        
        return Response({
            'success': True,
            'prompt': prompt
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# ======================== EXAMPLE 8: FUNCTION DÙNG TRONG VIEWS/SERVICES ========================

def process_scheduling_with_llm_support(ma_dot):
    """
    Hàm xử lý xếp lịch có hỗ trợ LLM
    Dùng DataAccessLayer để lấy dữ liệu một cách hiệu quả
    """
    # Bước 1: Lấy dataset
    dataset = DataAccessLayer.get_dataset_for_llm(ma_dot)
    
    # Bước 2: Phát hiện xung đột
    processor = LLMDataProcessor()
    conflicts = processor.detect_scheduling_conflicts(ma_dot)
    
    # Bước 3: Nếu có xung đột, xây dựng prompt cho LLM
    if sum(len(v) for v in conflicts.values()) > 0:
        prompt = LLMPromptBuilder.build_scheduling_context_prompt(ma_dot)
        # Gửi prompt cho LLM và xử lý kết quả...
        return {
            'has_conflicts': True,
            'conflicts': conflicts,
            'llm_prompt': prompt
        }
    
    return {
        'has_conflicts': False,
        'message': 'Lịch học không có xung đột'
    }


def get_complete_schedule_info(ma_dot):
    """
    Lấy toàn bộ thông tin lịch học của đợt xếp
    Dùng cho dashboard hoặc report
    """
    dot_info = DataAccessLayer.get_dot_xep_with_lop_mon_hoc(ma_dot)
    
    # Lấy tất cả lớp cần xếp
    lop_list = [
        {
            'lop': item['lop'].ma_lop,
            'mon': item['lop'].mon_hoc.ten_mon_hoc,
            'giang_vien': item['giang_vien'].ten_gv if item['giang_vien'] else 'Chưa phân công',
            'so_sv': item['lop'].so_luong_sv,
        }
        for item in dot_info['lop_list']
    ]
    
    # Lấy thống kê
    thong_ke = DataAccessLayer.get_thong_ke_dot_xep(ma_dot)
    
    return {
        'dot_xep': dot_info['dot_xep'],
        'lop_hoc': lop_list,
        'statistics': thong_ke
    }


# ======================== EXAMPLE 9: SERIALIZER DÙNG DAL ========================

"""
Trong serializers.py, bạn có thể sử dụng DAL như thế này:

from .services import DataAccessLayer

class GiangVienScheduleSerializer(serializers.Serializer):
    giang_vien_id = serializers.CharField()
    
    def to_representation(self, instance):
        processor = LLMDataProcessor()
        return processor.prepare_giang_vien_schedule_for_llm(instance.ma_gv)
"""


# ======================== EXAMPLE 10: QUERY TỪNG PHẦN ========================

def batch_lấy_dữ_liệu_multiple_dot():
    """
    Lấy dữ liệu từ nhiều đợt xếp mà không bị N+1
    """
    all_dot = DataAccessLayer.get_all_dot_xep()
    
    results = {}
    for dot in all_dot:
        dataset = DataAccessLayer.get_dataset_for_llm(dot.ma_dot)
        results[dot.ma_dot] = dataset
    
    return results
