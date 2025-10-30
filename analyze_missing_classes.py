#!/usr/bin/env python
"""
Compare HC-04 unfixable classes with MISSING_CLASS from validation
"""

# HC-04 couldn't fix (from logs)
hc04_unfixable = [
    'LOP-00000163',
    'LOP-00000157', 
    'LOP-00000160',
    'LOP-00000166',
    'LOP-00000187',
    'LOP-00000190',
]

# MISSING_CLASS from validation report (we saw earlier)
missing_classes = [
    'LOP-00000145', 'LOP-00000148', 'LOP-00000157', 'LOP-00000160',
    'LOP-00000161', 'LOP-00000162', 'LOP-00000163', 'LOP-00000164', 'LOP-00000166'
]

print("HC-04 UNFIXABLE (from logs):")
for cls in hc04_unfixable:
    print(f"  {cls}")

print(f"\nTotal HC-04 unfixable: {len(hc04_unfixable)}")

print("\nMISSING_CLASS (from validation):")
for cls in missing_classes:
    print(f"  {cls}")

print(f"\nTotal MISSING: {len(missing_classes)}")

# Check overlap
overlap = set(hc04_unfixable) & set(missing_classes)
print(f"\nOverlap (both in HC-04 unfixable AND MISSING): {len(overlap)}")
for cls in sorted(overlap):
    print(f"  {cls}")

# Check what's in MISSING but NOT in HC-04 logs
missing_only = set(missing_classes) - set(hc04_unfixable)
print(f"\nIn MISSING but NOT in HC-04 logs: {len(missing_only)}")
for cls in sorted(missing_only):
    print(f"  {cls}")

print(f"\n⚠️ HYPOTHESIS:")
print(f"  - LLM generated 216 assignments (all classes)")
print(f"  - 6 classes had HC-04 violations that couldn't be fixed")
print(f"  - 3 other classes also weren't scheduled somehow")
print(f"  - Total 9 MISSING_CLASS in final output")
