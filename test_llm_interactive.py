"""
Interactive LLM Schedule Generation Test Script
Usage: python manage.py shell < test_llm_interactive.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.services import ScheduleGeneratorLLM
from apps.scheduling.models import DotXep
import json

print("\n" + "="*80)
print("🚀 LLM SCHEDULE GENERATION - INTERACTIVE TEST")
print("="*80 + "\n")

# Step 1: List available periods
print("📋 Step 1: Available scheduling periods")
print("-" * 80)

try:
    periods = DotXep.objects.all().values('ma_dot', 'ten_dot', 'trang_thai')[:5]
    if periods:
        for period in periods:
            print(f"  • {period['ma_dot']}: {period['ten_dot']} (Status: {period['trang_thai']})")
        
        # Use first period
        ma_dot = periods[0]['ma_dot']
        print(f"\n✓ Using period: {ma_dot}")
    else:
        print("  ❌ No scheduling periods found")
        print("  💡 Tip: Create a DotXep (scheduling period) first")
        ma_dot = None
except Exception as e:
    print(f"  ❌ Error fetching periods: {e}")
    ma_dot = None

if ma_dot:
    # Step 2: Initialize LLM Generator
    print("\n📊 Step 2: Initialize ScheduleGeneratorLLM")
    print("-" * 80)
    try:
        generator = ScheduleGeneratorLLM()
        print("  ✓ Generator initialized")
        print(f"  • Using LLM: Gemini")
        print(f"  • Token optimization: 71% reduction")
        print(f"  • Data format: Compact (T2-C1 slots)")
    except Exception as e:
        print(f"  ❌ Error initializing: {e}")
        generator = None

    if generator:
        # Step 3: Fetch schedule data (test data preparation)
        print("\n📥 Step 3: Fetch Schedule Data")
        print("-" * 80)
        try:
            print("  ⏳ Fetching data from database...")
            data = generator._fetch_schedule_data(ma_dot)
            
            if data:
                print(f"  ✓ Data fetched successfully")
                print(f"    • Classes: {len(data.get('classes', []))} lớp")
                print(f"    • Rooms: {sum(len(v) for v in data.get('rooms', {}).values())} phòng")
                print(f"    • Teachers: {len(data.get('teachers', []))} giảng viên")
                print(f"    • Constraints: {len(data.get('constraints', []))} ràng buộc")
                print(f"    • Preferences: {len(data.get('preferences', []))} nguyện vọng")
            else:
                print("  ❌ No data fetched")
        except Exception as e:
            print(f"  ❌ Error fetching data: {e}")
            data = None

        if data:
            # Step 4: Prepare data for LLM (test compact format)
            print("\n🔧 Step 4: Prepare Compact Data Format")
            print("-" * 80)
            try:
                print("  ⏳ Converting to compact format...")
                compact_data = generator._prepare_data_for_llm(data)
                
                # Calculate token savings
                import json
                full_size = len(json.dumps(data, ensure_ascii=False))
                compact_size = len(json.dumps(compact_data, ensure_ascii=False))
                reduction = (1 - compact_size / full_size) * 100
                
                print(f"  ✓ Compact format created")
                print(f"    • Full format: {full_size:,} bytes")
                print(f"    • Compact format: {compact_size:,} bytes")
                print(f"    • Reduction: {reduction:.1f}%")
                print(f"    • Slot mapping: {len(compact_data.get('slot_mapping', {}))} slots")
                
                # Show sample
                if 'phan_cong' in compact_data and compact_data['phan_cong']:
                    print(f"\n  Sample phan_cong (compact):")
                    for item in compact_data['phan_cong'][:2]:
                        print(f"    {item}")
                        
            except Exception as e:
                print(f"  ❌ Error preparing data: {e}")
                compact_data = None

            if compact_data:
                # Step 5: Build LLM Prompt
                print("\n📝 Step 5: Build LLM Prompt")
                print("-" * 80)
                try:
                    print("  ⏳ Building prompt...")
                    prompt = generator._build_llm_prompt(compact_data)
                    
                    print(f"  ✓ Prompt built")
                    print(f"    • Prompt length: {len(prompt)} characters")
                    print(f"    • Estimated tokens: ~{len(prompt) // 4} tokens")
                    print(f"\n  Prompt preview (first 300 chars):")
                    print("  " + "-" * 76)
                    lines = prompt[:300].split('\n')
                    for line in lines[:10]:
                        if line:
                            print(f"  {line[:76]}")
                    if len(prompt) > 300:
                        print(f"  ... (truncated, total {len(prompt)} chars)")
                    print("  " + "-" * 76)
                    
                except Exception as e:
                    print(f"  ❌ Error building prompt: {e}")

                # Step 6: Generate Schedule with LLM
                print("\n🤖 Step 6: Call LLM for Schedule Generation")
                print("-" * 80)
                try:
                    print("  ⏳ Calling Gemini LLM...")
                    print("     (This may take 10-30 seconds)")
                    
                    result = generator._call_llm_for_schedule(compact_data)
                    
                    if result and isinstance(result, dict):
                        print(f"  ✓ LLM returned result")
                        print(f"    • Type: {type(result).__name__}")
                        print(f"    • Schedule entries: {len(result.get('schedule', []))} assignments")
                        
                        # Show sample
                        if result.get('schedule'):
                            print(f"\n  Sample assignments (first 3):")
                            for i, item in enumerate(result['schedule'][:3], 1):
                                print(f"    {i}. {item}")
                    else:
                        print(f"  ❌ Invalid result from LLM")
                        print(f"     Type: {type(result)}")
                        
                except Exception as e:
                    print(f"  ❌ Error calling LLM: {e}")
                    import traceback
                    traceback.print_exc()

print("\n" + "="*80)
print("✅ Interactive test complete")
print("="*80 + "\n")

print("💡 Next Steps:")
print("  1. Check that data is correctly fetched")
print("  2. Verify compact format reduces tokens by ~71%")
print("  3. Test LLM prompt generation")
print("  4. Review LLM response format")
print("")
print("📚 Documentation:")
print("  • Token optimization: SCHEDULE_GENERATOR_LLM_TOKEN_OPTIMIZATION.md")
print("  • Slot mapping: SLOT_MAPPING_GUIDE.md")
print("  • Architecture: AUDIT_SCHEDULE_FILES.md")
print("")
