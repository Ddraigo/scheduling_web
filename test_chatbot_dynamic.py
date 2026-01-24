"""
Test Chatbot với Dynamic Query Generation
Chạy: python manage.py shell < test_chatbot_dynamic.py
"""

from apps.scheduling.services.chatbot_service import get_chatbot

def test_chatbot_dynamic():
    """Test các tính năng mới của chatbot"""
    
    chatbot = get_chatbot()
    
    print("="*80)
    print("🤖 TEST CHATBOT VỚI DYNAMIC QUERY GENERATION")
    print("="*80)
    
    # Test cases - không cần chỉ định đợt xếp
    test_cases = [
        # 1. Thống kê cơ bản
        {
            'title': 'Đếm Giảng Viên',
            'message': 'Có bao nhiêu giảng viên trong hệ thống?'
        },
        {
            'title': 'Đếm Môn Học',
            'message': 'Số lượng môn học'
        },
        
        # 2. Tìm kiếm giảng viên
        {
            'title': 'Thông Tin Giảng Viên',
            'message': 'Giảng viên khoa CNTT'
        },
        {
            'title': 'Môn Dạy Của GV',
            'message': 'Thầy Nguyễn dạy môn gì?'
        },
        
        # 3. Thông tin môn học
        {
            'title': 'Tìm Môn Học',
            'message': 'Môn Lập trình Python'
        },
        {
            'title': 'Chi Tiết Môn Học',
            'message': 'Môn Cấu trúc dữ liệu có bao nhiêu tín chỉ?'
        },
        
        # 4. Lịch dạy / TKB
        {
            'title': 'Lịch Dạy GV',
            'message': 'Lịch dạy của giảng viên Nguyễn'
        },
        {
            'title': 'TKB Theo Thứ',
            'message': 'Thời khóa biểu thứ 2'
        },
        {
            'title': 'TKB Theo Ca',
            'message': 'Lịch học thứ 3 ca 1'
        },
        
        # 5. Nguyện vọng
        {
            'title': 'Nguyện Vọng GV',
            'message': 'Nguyện vọng của giảng viên'
        },
        {
            'title': 'Nguyện Vọng Cụ Thể',
            'message': 'Thầy A có nguyện vọng gì?'
        },
        
        # 6. Phòng học
        {
            'title': 'Phòng Trống',
            'message': 'Phòng trống thứ 2 ca 1'
        },
        {
            'title': 'Phòng Thực Hành',
            'message': 'Gợi ý phòng thực hành thứ 3 ca 2'
        },
        
        # 7. Thống kê khoa
        {
            'title': 'Thống Kê Khoa',
            'message': 'Khoa CNTT có bao nhiêu giảng viên?'
        },
        {
            'title': 'Danh Sách Khoa',
            'message': 'Có mấy khoa?'
        },
    ]
    
    for idx, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"📝 TEST {idx}: {test['title']}")
        print(f"{'='*80}")
        print(f"❓ Câu hỏi: {test['message']}")
        print(f"\n{'─'*80}")
        
        # Gọi chatbot - KHÔNG CẦN truyền ma_dot
        result = chatbot.chat(test['message'])
        
        if result['success']:
            print(f"✅ Kết quả:")
            print(f"\n{result['response']}")
            
            # Hiển thị metadata
            print(f"\n{'─'*80}")
            print(f" Metadata:")
            print(f"  - Intent Type: {result['intent']['type']}")
            print(f"  - Query Type: {result['intent'].get('query_type', 'N/A')}")
            print(f"  - Entities: {result['intent']['entities']}")
            print(f"  - Model: {result['metadata']['model']}")
        else:
            print(f"❌ Lỗi: {result.get('error', 'Unknown error')}")
            print(f"Response: {result['response']}")
        
        print(f"\n{'='*80}\n")
    
    print("\n✨ Hoàn thành test!\n")

if __name__ == '__main__':
    test_chatbot_dynamic()
