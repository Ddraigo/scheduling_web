import json
from collections import defaultdict, Counter
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from apps.scheduling.models import GiangVien, LopMonHoc, PhongHoc, TimeSlot

# Load validation report
f = open('output/validation_report_detailed.json', 'r', encoding='utf-8')
data = json.load(f)

print("="*80)
print("PHAN TICH CHI TIET LOI LICH HOC")
print("="*80)

# 1. Summary
summary = data.get('summary', {})
print("\nTONG QUAN:")
print(f"  Total classes: {summary.get('total_classes', 0)}")
print(f"  OK classes: {summary.get('ok_classes', 0)} ({summary.get('ok_percentage', 0):.1f}%)")
print(f"  Hard violations: {summary.get('hard_violated_classes', 0)} ({summary.get('hard_violated_percentage', 0):.1f}%)")
print(f"  Soft violations: {summary.get('soft_violated_classes', 0)} ({summary.get('soft_violated_percentage', 0):.1f}%)")

# 2. Hard violations breakdown
print("\nHARD VIOLATIONS BREAKDOWN:")
hard_stats = data.get('hard_violation_stats', {})
for constraint, count in sorted(hard_stats.items()):
    print(f"  {constraint}: {count} violations")

# 3. Analyze violations by teacher
print("\nVIOLATIONS BY TEACHER:")
teacher_violations = defaultdict(lambda: {'HC-01': 0, 'HC-04': 0, 'HC-05': 0, 'HC-06': 0})
for cls in data.get('hard_violated_classes', []):
    teacher_id = cls.get('teacher_id', 'Unknown')
    teacher_name = cls.get('teacher', 'Unknown')
    for v in cls.get('hard_violations', []):
        constraint = v.get('constraint', 'Unknown')
        teacher_violations[teacher_id]['name'] = teacher_name
        teacher_violations[teacher_id][constraint] += 1

# Sort by total violations
sorted_teachers = sorted(
    teacher_violations.items(),
    key=lambda x: sum(x[1][c] for c in ['HC-01', 'HC-04', 'HC-05', 'HC-06']),
    reverse=True
)

for teacher_id, violations in sorted_teachers[:15]:
    total = sum(violations[c] for c in ['HC-01', 'HC-04', 'HC-05', 'HC-06'])
    print(f"  {teacher_id} ({violations['name']}): {total} violations")
    if violations['HC-01'] > 0:
        print(f"    - HC-01 (Teacher conflict): {violations['HC-01']}")
    if violations['HC-04'] > 0:
        print(f"    - HC-04 (Equipment): {violations['HC-04']}")
    if violations['HC-05'] > 0:
        print(f"    - HC-05 (Class TH → Room LT): {violations['HC-05']}")
    if violations['HC-06'] > 0:
        print(f"    - HC-06 (Class LT → Room TH): {violations['HC-06']}")

# 4. Analyze time slots with most conflicts
print(f"\n⏰ TIME SLOTS WITH MOST CONFLICTS:")
slot_conflicts = Counter()
for cls in data.get('hard_violated_classes', []):
    for v in cls.get('hard_violations', []):
        if v.get('constraint') == 'HC-01':
            slot = v.get('slot', 'Unknown')
            slot_conflicts[slot] += 1

for slot, count in slot_conflicts.most_common(15):
    print(f"  {slot}: {count} teacher conflicts")

# 5. Analyze equipment issues
print(f"\n🔧 EQUIPMENT ISSUES (HC-04):")
equipment_missing = Counter()
for cls in data.get('hard_violated_classes', []):
    for v in cls.get('hard_violations', []):
        if v.get('constraint') == 'HC-04':
            reason = v.get('reason', '')
            # Extract missing equipment
            if 'thiếu:' in reason:
                missing_part = reason.split('thiếu:')[1].split('(')[0].strip()
                equipment_missing[missing_part] += 1

print(f"  Most common missing equipment:")
for equip, count in equipment_missing.most_common(10):
    print(f"    - {equip}: {count} classes")

# 6. Analyze room type mismatches
print(f"\n🏫 ROOM TYPE MISMATCHES (HC-05 & HC-06):")
room_mismatches = defaultdict(list)
for cls in data.get('hard_violated_classes', []):
    for v in cls.get('hard_violations', []):
        if v.get('constraint') in ['HC-05', 'HC-06']:
            constraint = v.get('constraint')
            reason = v.get('reason', '')
            room_mismatches[constraint].append(reason)

print(f"  HC-05 (Class TH → Room LT): {len(room_mismatches['HC-05'])} violations")
print(f"  HC-06 (Class LT → Room TH): {len(room_mismatches['HC-06'])} violations")

# 7. Teacher conflict patterns
print(f"\n🚨 TEACHER CONFLICT PATTERNS (HC-01):")
teacher_conflict_slots = defaultdict(list)
for cls in data.get('hard_violated_classes', []):
    teacher_id = cls.get('teacher_id', 'Unknown')
    for v in cls.get('hard_violations', []):
        if v.get('constraint') == 'HC-01':
            slot = v.get('slot', 'Unknown')
            teacher_conflict_slots[teacher_id].append(slot)

print(f"  Teachers with multiple conflicts:")
for teacher_id, slots in sorted(teacher_conflict_slots.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
    if len(slots) > 1:
        slot_counts = Counter(slots)
        print(f"    {teacher_id}: {len(slots)} conflicts at {len(slot_counts)} different slots")
        print(f"      Hottest slots: {', '.join([f'{s}({c}x)' for s, c in slot_counts.most_common(3)])}")

# 8. Soft violations (teacher preferences)
print(f"\n⚠️  SOFT VIOLATIONS (Teacher Preferences):")
soft_stats = data.get('soft_violation_stats', {})
for constraint, count in sorted(soft_stats.items()):
    print(f"  {constraint}: {count} violations")

print("\n" + "="*80)
print("💡 RECOMMENDATIONS FOR LLM IMPROVEMENT:")
print("="*80)

recommendations = []

# Check HC-01 severity
hc01_count = hard_stats.get('HC-01', 0)
if hc01_count > 20:
    recommendations.append(f"""
1. ⚠️ TEACHER CONFLICTS (HC-01): {hc01_count} conflicts - CRITICAL
   Problem: LLM is not properly respecting teacher time slot constraints
   Solution:
   - Add stricter teacher conflict checking in LLM prompt
   - Implement hard constraint: "One teacher can only teach ONE class per time slot"
   - Consider: Group teachers by their constraint classes and schedule them separately
   - Use conflict detection in post-processing to detect and fix violations
""")

# Check HC-04 severity
hc04_count = hard_stats.get('HC-04', 0)
if hc04_count > 10:
    recommendations.append(f"""
2. 🔧 EQUIPMENT MISMATCH (HC-04): {hc04_count} conflicts
   Problem: Classes requiring specific equipment placed in rooms lacking them
   Solution:
   - Pre-filter available rooms by class requirements in LLM context
   - Group classes by equipment needs: PC-requiring, Projector-requiring, etc.
   - Add validation rule: "Always check equipment before assigning room"
   - Create room availability matrix based on equipment
""")

# Check HC-05/06 severity
hc05_count = len(room_mismatches['HC-05'])
hc06_count = len(room_mismatches['HC-06'])
if hc05_count > 5 or hc06_count > 5:
    recommendations.append(f"""
3. 🏫 ROOM TYPE MISMATCH (HC-05/HC-06): {hc05_count} + {hc06_count} conflicts
   Problem: Practice classes scheduled in theory rooms (or vice versa)
   Likely cause: Class type detection logic may still have edge cases
   Solution:
   - Validate class type detection with real data sample
   - Double-check: Mixed classes (both LT & TH hours) are correctly classified
   - Add explicit room type validation before assignment
""")

# Check soft violations
soft_count = data.get('summary', {}).get('soft_violated_classes', 0)
if soft_count > 50:
    recommendations.append(f"""
4. 💚 TEACHER PREFERENCES: {soft_count} violations
   Problem: LLM not prioritizing teacher preferences enough
   Solution:
   - Weight teacher preferences higher in scoring function
   - Add constraint: "Try to honor at least 80% of teacher preferences"
   - Use preference satisfaction as tie-breaker when multiple solutions exist
""")

# Time slot analysis
busiest_slots = slot_conflicts.most_common(3)
if busiest_slots:
    slots_str = ", ".join([f"{s[0]}({s[1]}x)" for s in busiest_slots])
    recommendations.append(f"""
5. ⏰ BUSY TIME SLOTS: {slots_str}
   Problem: Some time slots are heavily overloaded
   Solution:
   - Implement better load balancing across time slots
   - Add constraint: "Distribute classes evenly across time slots"
   - Consider: Progressive slot filling algorithm
""")

for rec in recommendations:
    print(rec)

print("\n" + "="*80)
print("IMPLEMENTATION PRIORITY:")
print("="*80)
print("""
1. 🔴 FIX CRITICAL: HC-01 (Teacher conflicts) - This breaks basic feasibility
2. 🟠 FIX HIGH: HC-04 (Equipment) - This requires pre-processing
3. 🟡 IMPROVE: HC-05/06 (Room types) - Likely edge cases
4. 🟢 OPTIMIZE: Teacher preferences - Nice to have but non-critical
""")
