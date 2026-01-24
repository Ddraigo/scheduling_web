"""
Quick Demo - Chatbot với Dynamic Query
Chạy: python quick_demo_chatbot.py
"""

import os
import sys
import time
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.services.chatbot_service import get_chatbot

def demo():
    """Demo nhanh các tính năng mới"""
    
    print("\n" + "="*80)
    print("🤖 CHATBOT DEMO - DYNAMIC QUERY GENERATION")
    print("="*80)
    print("\n💡 Tính năng mới:")
    print("  ✅ Tự động phát hiện đợt xếp")
    print("  ✅ Sinh truy vấn động dựa trên câu hỏi")
    print("  ✅ Trả lời tự nhiên dựa trên kết quả thực tế")
    print("  ✅ Không cần chọn đợt trước nữa!")
    
    chatbot = get_chatbot()
    
    # Demo questions - chỉ 2 câu để tiết kiệm quota
    questions = [
        "Có bao nhiêu giảng viên?",
        "Phòng trống thứ 2 ca 1",
    ]
    
    print(f"\n{'='*80}")
    print("📝 DEMO QUESTIONS (delay 5s giữa mỗi câu):")
    print(f"{'='*80}\n")
    
    for i, question in enumerate(questions, 1):
        print(f"\n{'─'*80}")
        print(f"❓ Question {i}: {question}")
        print(f"{'─'*80}")
        
        result = chatbot.chat(question)
        
        if result['success']:
            print(f"\n💬 Response:\n{result['response']}\n")
            print(f"🔍 Intent: {result['intent']['type']}")
            if result['intent'].get('query_type'):
                print(f"🔍 Query Type: {result['intent']['query_type']}")
        else:
            print(f"\n❌ Error: {result.get('error')}")
        
        # Delay giữa các câu hỏi như người bình thường
        if i < len(questions):
            print("\n⏳ Đợi 5s trước câu tiếp theo...")
            time.sleep(5)
    
    print(f"\n{'='*80}")
    print("\n✨ Interactive Mode - Nhập câu hỏi (hoặc 'quit' để thoát):")
    print("💡 Tip: Đợi vài giây giữa các câu hỏi để tránh rate limit")
    print(f"{'='*80}\n")
    
    while True:
        try:
            question = input("\n❓ Bạn: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q', 'thoát']:
                print("\n👋 Bye bye!")
                break
            
            if not question:
                continue
            
            print("\n🤔 Đang xử lý...")
            result = chatbot.chat(question)
            
            if result['success']:
                print(f"\n🤖 Bot: {result['response']}")
            else:
                print(f"\n❌ Lỗi: {result.get('error')}")
                
        except KeyboardInterrupt:
            print("\n\n👋 Bye bye!")
            break
        except Exception as e:
            print(f"\n❌ Lỗi: {e}")

if __name__ == '__main__':
    demo()
