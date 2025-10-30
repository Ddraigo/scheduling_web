import json
import sys
sys.path.insert(0, '/d:/HOCTAP/DU_AN_CNTT/scheduling_web')

# Import the function to build the LLM prompt
from apps.scheduling.schedule_generator_llm import get_all_scheduling_data, _format_phan_cong_compact

# Get data
phan_cong_info, rooms, slots, teacher_prefs = get_all_scheduling_data()

print(f"Total classes in database: {len(phan_cong_info)}")
print(f"Sample classes (first 10):")
for i, pc in enumerate(list(phan_cong_info.items())[:10]):
    print(f"  {pc[0]}")

missing_classes = ['LOP-00000145', 'LOP-00000148', 'LOP-00000157', 'LOP-00000160', 
                   'LOP-00000161', 'LOP-00000162', 'LOP-00000163', 'LOP-00000164']

print(f"\nChecking for missing classes in data:")
for mc in missing_classes:
    if mc in phan_cong_info:
        print(f"  ✓ {mc} - found")
    else:
        print(f"  ✗ {mc} - NOT FOUND in database!")

# Check suitable rooms
print(f"\nChecking suitable rooms for missing classes:")
from apps.scheduling.schedule_generator_llm import _get_suitable_rooms_for_class

for mc in missing_classes[:3]:  # Check first 3
    if mc in phan_cong_info:
        pc = phan_cong_info[mc]
        suitable = _get_suitable_rooms_for_class(pc, rooms)
        print(f"  {mc}: {len(suitable)} suitable rooms")
        if suitable:
            print(f"    {suitable[:3]}")
        else:
            print(f"    NO SUITABLE ROOMS!")
