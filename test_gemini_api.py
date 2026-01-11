"""Test Gemini API key trực tiếp"""
import os
from dotenv import load_dotenv

# Load từ .env (file Django đang dùng)
load_dotenv('.env')

api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')

print("=" * 70)
print("KIỂM TRA GEMINI API KEY")
print("=" * 70)
print(f"API Key: {api_key[:10]}...{api_key[-5:] if api_key else 'NOT SET'}")
print(f"Length: {len(api_key) if api_key else 0}")

if not api_key:
    print("❌ API Key không được cấu hình!")
    exit(1)

# Test API call
print("\n📡 Testing API call...")

try:
    from google import genai
    
    client = genai.Client(api_key=api_key)
    
    # Thử một request đơn giản
    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents="Trả lời ngắn gọn: 1 + 1 = ?"
    )
    
    print(f"✓ API hoạt động bình thường!")
    print(f"Response: {response.text}")
    
except Exception as e:
    error_str = str(e)
    print(f"❌ Lỗi API: {error_str}")
    
    if "429" in error_str or "rate" in error_str.lower():
        print("\n⚠️  Bị RATE LIMITED - API key đã vượt quota!")
        print("Giải pháp:")
        print("1. Đợi 1-2 phút rồi thử lại")
        print("2. Kiểm tra quota tại: https://aistudio.google.com/apikey")
        print("3. Tạo API key mới nếu cần")
    elif "invalid" in error_str.lower() or "api key" in error_str.lower():
        print("\n⚠️  API KEY KHÔNG HỢP LỆ!")
        print("Hãy kiểm tra lại key trong file .env")
    else:
        print(f"\n⚠️  Lỗi khác: {type(e).__name__}")
