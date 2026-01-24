# To run this code you need to install the following dependencies:
# pip install google-genai

import base64
import os
from dotenv import load_dotenv

load_dotenv('.env')

from google import genai
from google.genai import types


def generate():
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-2.5-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""Xin chào! Trả lời ngắn gọn: 1 + 1 = ?"""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_budget=-1,
        ),
    )

    print("Testing Gemini 2.5 Flash API...")
    print("=" * 50)
    
    try:
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            print(chunk.text, end="")
        print("\n" + "=" * 50)
        print("✓ API hoạt động!")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")

if __name__ == "__main__":
    generate()
