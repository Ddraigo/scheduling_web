"""
Test script để kiểm tra AI tự sinh câu truy vấn
Flow: Câu hỏi tự nhiên → AI sinh query spec → Hệ thống thực thi → Kết quả
"""

import os
import sys
import time
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.services.chatbot_service import ScheduleChatbot


def test_ai_query_generation():
    """Test AI sinh query specification"""
    print("=" * 70)
    print("TEST: AI TỰ SINH CÂU TRUY VẤN")
    print("=" * 70)
    
    chatbot = ScheduleChatbot()
    
    # Test cases - giảm số lượng để tránh rate limit
    test_questions = [
        "Khoa CNTT có bao nhiêu giảng viên?",
        "Có bao nhiêu môn học trong hệ thống?",
        "Danh sách phòng thực hành",
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}: {question}")
        print("-" * 70)
        
        # Test AI query generation
        result = chatbot._generate_query_with_ai(question)
        
        if result.get('success'):
            spec = result['query_spec']
            print(f"✅ AI SINH QUERY THÀNH CÔNG (model: {result.get('model_used', 'unknown')}):")
            print(f"   Intent: {spec.get('intent_type')}")
            print(f"   Query type: {spec.get('query_type')}")
            print(f"   Tables: {spec.get('tables')}")
            print(f"   Filters: {spec.get('filters')}")
            print(f"   Needs đợt xếp: {spec.get('needs_dot_xep')}")
            print(f"   Explanation: {spec.get('explanation')}")
            
            # Thực thi query
            print("\n    THỰC THI QUERY:")
            query_result = chatbot._execute_ai_generated_query(spec, ma_dot=None)
            print(f"   Success: {query_result['success']}")
            print(f"   Summary: {query_result['summary']}")
            if query_result['data']:
                print(f"   Data (first 3): {query_result['data'][:3]}")
        else:
            print(f"❌ AI QUERY GENERATION FAILED: {result.get('error')}")
            print("   → Sẽ dùng rule-based fallback")
        
        # Delay giữa các test để tránh rate limit
        if i < len(test_questions):
            print("\n   ⏳ Waiting 3s to avoid rate limit...")
            time.sleep(3)


def test_full_chat_flow():
    """Test full chat flow với AI query"""
    print("\n" + "=" * 70)
    print("TEST: FULL CHAT FLOW VỚI AI QUERY")
    print("=" * 70)
    
    chatbot = ScheduleChatbot()
    
    questions = [
        "Khoa Công nghệ thông tin có bao nhiêu giảng viên?",
        "Liệt kê các môn học có số tín chỉ lớn hơn 3",
    ]
    
    for q in questions:
        print(f"\n{'='*70}")
        print(f"QUESTION: {q}")
        print("-" * 70)
        
        result = chatbot.chat(q)
        
        if result.get('success'):
            print(f"✅ Response:\n{result['response'][:500]}...")
            metadata = result.get('metadata', {})
            print(f"\n📌 Model used: {metadata.get('model', 'N/A')}")
        else:
            print(f"❌ Error: {result.get('error')}")


if __name__ == '__main__':
    print("🚀 Testing AI Query Generation System")
    print("Flow: Câu hỏi → AI sinh query → Hệ thống thực thi → AI trả lời")
    print()
    
    # Test 1: AI sinh query spec
    test_ai_query_generation()
    
    # Test 2: Full chat flow
    # test_full_chat_flow()
    
    print("\n" + "=" * 70)
    print("✨ Test completed!")
