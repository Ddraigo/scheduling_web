"""
Simple LLM Interactive Test
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from apps.scheduling.services import ScheduleGeneratorLLM
from apps.scheduling.models import DotXep
import json

print("\n" + "="*80)
print("🚀 TEST: LLM SCHEDULE GENERATION")
print("="*80 + "\n")

# Get first period
print("Step 1: Finding scheduling period...")
try:
    period = DotXep.objects.first()
    if period:
        ma_dot = period.ma_dot
        print(f"✓ Using: {ma_dot} - {period.ten_dot}")
    else:
        print("❌ No periods found")
        exit()
except Exception as e:
    print(f"❌ Error: {e}")
    exit()

# Initialize generator
print("\nStep 2: Initialize ScheduleGeneratorLLM...")
try:
    gen = ScheduleGeneratorLLM()
    print("✓ Generator initialized")
except Exception as e:
    print(f"❌ Error: {e}")
    exit()

# Fetch data
print("\nStep 3: Fetch schedule data...")
try:
    data = gen._fetch_schedule_data(ma_dot)
    if data:
        print(f"✓ Data fetched:")
        print(f"  - Classes: {len(data.get('classes', []))}")
        print(f"  - Rooms: {sum(len(v) for v in data.get('rooms', {}).values())}")
        print(f"  - Teachers: {len(data.get('teachers', []))}")
        print(f"  - Constraints: {len(data.get('constraints', []))}")
        print(f"  - Preferences: {len(data.get('preferences', []))}")
    else:
        print("❌ No data")
        exit()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit()

# Prepare compact format
print("\nStep 4: Prepare compact data format...")
try:
    compact = gen._prepare_data_for_llm(data)
    
    # Calculate savings
    full = len(json.dumps(data, ensure_ascii=False))
    compact_size = len(json.dumps(compact, ensure_ascii=False))
    reduction = (1 - compact_size / full) * 100
    
    print(f"✓ Compact format created:")
    print(f"  - Full: {full:,} bytes")
    print(f"  - Compact: {compact_size:,} bytes")
    print(f"  - Reduction: {reduction:.1f}%")
    print(f"  - Slot mapping: {len(compact.get('slot_mapping', {}))} entries")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit()

# Build prompt
print("\nStep 5: Build LLM prompt...")
try:
    prompt = gen._build_llm_prompt(compact)
    print(f"✓ Prompt built: {len(prompt)} chars (~{len(prompt)//4} tokens)")
    print("\nPrompt preview:")
    print("-" * 80)
    for line in prompt[:500].split('\n')[:10]:
        print(line[:80])
    print("...")
    print("-" * 80)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit()

# Call LLM
print("\nStep 6: Call LLM (this takes 10-30 seconds)...")
try:
    print("⏳ Calling Gemini...")
    result = gen._call_llm_for_schedule(compact)
    
    if result:
        print(f"✓ LLM responded!")
        print(f"  - Type: {type(result).__name__}")
        if isinstance(result, dict):
            print(f"  - Schedule entries: {len(result.get('schedule', []))}")
            if result.get('schedule'):
                print(f"\n  Sample assignments (first 3):")
                for i, item in enumerate(result['schedule'][:3], 1):
                    print(f"    {i}. {item}")
    else:
        print("❌ No result")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("✅ Test complete!")
print("="*80 + "\n")
