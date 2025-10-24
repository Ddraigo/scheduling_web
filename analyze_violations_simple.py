import json
from collections import defaultdict, Counter

# Load validation report
f = open('output/validation_report_detailed.json', 'r', encoding='utf-8')
data = json.load(f)

# Summary
summary = data.get('summary', {})
print("="*80)
print("ANALYSIS: Schedule Quality & LLM Improvement Opportunities")
print("="*80)
print("\n1. OVERALL STATISTICS:")
print(f"   Total classes: {summary.get('total_classes', 0)}")
print(f"   OK (no violations): {summary.get('ok_classes', 0)} ({summary.get('ok_percentage', 0):.1f}%)")
print(f"   Hard violations: {summary.get('hard_violated_classes', 0)} ({summary.get('hard_violated_percentage', 0):.1f}%)")
print(f"   Soft violations (preferences): {summary.get('soft_violated_classes', 0)} ({summary.get('soft_violated_percentage', 0):.1f}%)")

# Hard violations breakdown
print("\n2. HARD VIOLATIONS BREAKDOWN:")
hard_stats = data.get('hard_violation_stats', {})
hc01_count = hard_stats.get('HC-01', 0)
hc04_count = hard_stats.get('HC-04', 0)
print(f"   HC-01 (Teacher conflicts): {hc01_count} violations")
print(f"   HC-04 (Equipment mismatch): {hc04_count} violations")

# Teacher analysis
print("\n3. TEACHER CONFLICT ANALYSIS (HC-01):")
teacher_violations = defaultdict(list)
for cls in data.get('hard_violated_classes', []):
    teacher_id = cls.get('teacher_id', 'Unknown')
    teacher_name = cls.get('teacher', 'Unknown')
    for v in cls.get('hard_violations', []):
        if v.get('constraint') == 'HC-01':
            teacher_violations[teacher_id].append({
                'name': teacher_name,
                'slot': v.get('slot'),
                'class': cls.get('MaLop')
            })

# Top conflicted teachers
sorted_teachers = sorted(teacher_violations.items(), key=lambda x: len(x[1]), reverse=True)
print("   Top teachers with conflicts:")
for teacher_id, conflicts in sorted_teachers[:10]:
    print(f"     {teacher_id}: {len(conflicts)} conflicts")

# Time slots with most conflicts
print("\n4. BUSIEST TIME SLOTS:")
slot_conflicts = Counter()
for cls in data.get('hard_violated_classes', []):
    for v in cls.get('hard_violations', []):
        if v.get('constraint') == 'HC-01':
            slot = v.get('slot', 'Unknown')
            slot_conflicts[slot] += 1

print("   Time slots with most teacher conflicts:")
for slot, count in slot_conflicts.most_common(10):
    print(f"     {slot}: {count} conflicts")

# Equipment analysis
print("\n5. EQUIPMENT MISMATCH ANALYSIS (HC-04):")
equipment_issues = defaultdict(int)
for cls in data.get('hard_violated_classes', []):
    for v in cls.get('hard_violations', []):
        if v.get('constraint') == 'HC-04':
            reason = v.get('reason', '')
            if 'thiếu:' in reason:
                missing = reason.split('thiếu:')[1].split('(')[0].strip()
                equipment_issues[missing] += 1

print("   Most commonly missing equipment:")
for equip, count in sorted(equipment_issues.items(), key=lambda x: x[1], reverse=True)[:8]:
    print(f"     {equip}: {count} violations")

# Room type check
print("\n6. ROOM TYPE MISMATCHES:")
hc05_violations = []
hc06_violations = []
for cls in data.get('hard_violated_classes', []):
    for v in cls.get('hard_violations', []):
        if v.get('constraint') == 'HC-05':
            hc05_violations.append(v)
        elif v.get('constraint') == 'HC-06':
            hc06_violations.append(v)

print(f"   HC-05 (Class TH in LT room): {len(hc05_violations)} violations")
print(f"   HC-06 (Class LT in TH room): {len(hc06_violations)} violations")

# Soft violations
print("\n7. SOFT VIOLATIONS (Teacher Preferences):")
soft_stats = data.get('soft_violation_stats', {})
for constraint, count in sorted(soft_stats.items()):
    print(f"   {constraint}: {count} classes not in preferred slots")

print("\n" + "="*80)
print("LLM IMPROVEMENT RECOMMENDATIONS:")
print("="*80)

print("""
PRIORITY 1 - CRITICAL (HC-01: Teacher Conflicts) - {hc01_count} violations
=============================================================================
PROBLEM:
  - {hc01_count} assignments have teacher teaching multiple classes at same time
  - This is the #1 blocker for schedule feasibility

ROOT CAUSES (likely):
  1. LLM not properly tracking teacher time slots during scheduling
  2. Teacher context not fully utilized in decision making
  3. No conflict resolution mechanism in post-processing

SOLUTIONS (in order of impact):
  1. Add explicit teacher availability tracking in LLM prompt
     - Create teacher-slot conflict matrix before LLM generates schedule
     - Pass conflict information to LLM as hard constraint
  
  2. Implement assignment-time validation layer
     - After LLM generates schedule, check each teacher-slot combination
     - Detect and fix conflicts by reassigning one class to different time slot
  
  3. Use graph-based conflict detection
     - Build conflict graph: nodes=classes, edges=shared teacher+slot
     - Use graph algorithms to find independent sets (no conflicts)

CODE CHANGES:
  - schedule_ai.py: Add teacher availability matrix to context
  - schedule_validator.py: Add HC-01 conflict detection in post-processing
  - schedule_generator_llm.py: Implement conflict resolution logic

PRIORITY 2 - HIGH (HC-04: Equipment) - {hc04_count} violations
=============================================================================
PROBLEM:
  - {hc04_count} classes assigned to rooms lacking required equipment
  - Some rooms missing PC, some missing projectors, etc.

ROOT CAUSES:
  1. Equipment not pre-filtered when passing room options to LLM
  2. LLM doesn't have visibility into room capabilities
  3. No pre-assignment validation

SOLUTIONS:
  1. Pre-filter available rooms by equipment requirements
     - Group classes by equipment: PC-only, Projector-only, None
     - Pass only compatible rooms for each class group
  
  2. Create equipment-to-rooms mapping
     - tb_PHONG_HOC.ThietBi preprocessing
     - For each class requirement, pre-filter compatible rooms
  
  3. Add equipment constraint to LLM prompt
     - Make equipment matching an explicit constraint
     - Use as tie-breaker when multiple rooms available

CODE CHANGES:
  - schedule_generator_llm.py: Pre-filter rooms by equipment
  - schedule_ai.py: Add equipment mapping to context

PRIORITY 3 - MEDIUM (HC-05/06: Room Types) - 0 violations
=============================================================================
STATUS: Currently working correctly!
  - Class type detection logic now matches SQL standard
  - No room type mismatches detected
  
MONITORING:
  - Continue monitoring for edge cases
  - Verify mixed classes (LT + TH hours) classification

PRIORITY 4 - NICE-TO-HAVE (Teacher Preferences) - soft violations
=============================================================================
PROBLEM:
  - 50%+ of assignments violate teacher preferences
  - Not a feasibility blocker but affects satisfaction

SOLUTIONS:
  1. Weight preferences higher in scoring
  2. Use preference satisfaction as tie-breaker
  3. Implement preference-aware scheduling phase
""".format(hc01_count=hc01_count, hc04_count=hc04_count))

print("\n" + "="*80)
print("QUICK WINS (30-minute fixes):")
print("="*80)
print("""
1. Add post-processing HC-01 conflict detector
   - After LLM schedule generation, check all (teacher, slot) combinations
   - If conflict found, move one class to alternate slot
   - Cost: ~50 lines of code

2. Improve equipment pre-filtering
   - Before passing classes to LLM, group by equipment requirements
   - Pass pre-filtered room list for each class
   - Cost: ~30 lines of code

3. Add equipment constraint to system prompt
   - Explicit instruction: "Room must have required equipment"
   - Show equipment details for each room
   - Cost: ~10 lines in prompt
""")
