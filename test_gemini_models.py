"""Test các model Gemini khác nhau"""
import os
from dotenv import load_dotenv

load_dotenv('.env')

from google import genai
from google.genai import types

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# Các model có quota riêng biệt
models_to_test = [
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash", 
    "gemini-1.5-flash-8b",
]

print("=" * 60)
print("TESTING DIFFERENT GEMINI MODELS")
print("=" * 60)

for model in models_to_test:
    print(f"\n📡 Testing {model}...")
    try:
        response = client.models.generate_content(
            model=model,
            contents="1 + 1 = ?",
            config=types.GenerateContentConfig(
                max_output_tokens=50,
            )
        )
        print(f"   ✓ SUCCESS! Response: {response.text.strip()}")
    except Exception as e:
        error_str = str(e)
        if '429' in error_str:
            print(f"   ✗ Rate limited")
        else:
            print(f"   ✗ Error: {error_str[:100]}")

print("\n" + "=" * 60)
