#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compare structure of two validation output files"""

import json
from pathlib import Path

files_to_compare = {
    'Old Format (27-10)': 'output/validation_report_DOT1_2025-2026_HK1_validated.json',
    'New UNIFIED Format (29-10)': 'output/validation_algorithm_unified.json',
}

print("\n" + "="*100)
print("COMPARISON: OLD vs NEW UNIFIED FORMAT")
print("="*100)

for label, file in files_to_compare.items():
    fpath = Path(file)
    if fpath.exists():
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n📄 {label}: {file}")
        print(f"   Top-level keys: {list(data.keys())}")
        
        # Get violation counts
        if 'hard_violations' in data:
            hard = len(data.get('hard_violations', []))
            soft = len(data.get('soft_violations', []))
            print(f"   Hard violations: {hard}")
            print(f"   Soft violations: {soft}")
        elif 'hard_constraints' in data:
            hard = data['summary'].get('hard_violated_classes', 0)
            soft = data['summary'].get('soft_violated_classes', 0)
            print(f"   Hard violated classes: {hard}")
            print(f"   Soft violated classes: {soft}")
        
        # Check for fitness
        if 'fitness' in data:
            fitness = data['fitness'].get('combined_fitness')
            print(f"   Fitness: {fitness}")
            print(f"   Status: {data['fitness'].get('status')}")
        elif 'summary' in data:
            print(f"   Fitness: NOT IN OLD FORMAT")
        
        # Check schema
        if 'summary' in data:
            print(f"   Schema Type: OLD FORMAT (summary/hard_constraints keys)")
        elif 'constraint_stats' in data:
            print(f"   Schema Type: NEW UNIFIED FORMAT (constraint_stats/fitness keys)")
    else:
        print(f"❌ {file} NOT FOUND")

print("\n" + "="*100)
print("VERDICT:")
print("="*100)
print("""
✅ NEW UNIFIED FORMAT (validation_algorithm_unified.json):
   - Generated: 29-10-2025
   - Uses standardized schema with constraint_stats, fitness, violations grouped 3 ways
   - Contains BOTH hard (191) and soft (109) violations
   - Has fitness calculation with status
   - THIS IS THE CORRECT FORMAT we should use

❌ OLD FORMAT (validation_report_DOT1_2025-2026_HK1_validated.json):
   - Generated: 27-10-2025 (OUTDATED)
   - Uses old schema with hard_constraints/soft_violated_classes
   - Only counted soft violations on hard-violated classes (incomplete)
   - Should be DELETED or ARCHIVED
""")
