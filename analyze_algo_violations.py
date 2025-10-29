#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze why Algorithm schedule has so many violations"""

import json
from pathlib import Path
from collections import defaultdict

print("\n" + "="*100)
print("ANALYZING ALGORITHM VIOLATIONS")
print("="*100)

algo_file = 'output/validation_algorithm_unified.json'

with open(algo_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

hard_violations = data.get('hard_violations', [])

print(f"\nTotal Hard Violations: {len(hard_violations)}")

# Group by type
violations_by_type = defaultdict(int)
for v in hard_violations:
    v_type = v.get('type', 'UNKNOWN')
    violations_by_type[v_type] += 1

print("\n📊 Violations Breakdown by Type:")
for v_type, count in sorted(violations_by_type.items(), key=lambda x: x[1], reverse=True):
    print(f"   {v_type}: {count}")

# Show sample violations
print("\n📋 Sample Violations (first 10):")
for i, v in enumerate(hard_violations[:10], 1):
    v_type = v.get('type', 'UNKNOWN')
    msg = v.get('message', 'No message')
    print(f"   {i}. [{v_type}] {msg}")

# Group by class
violations_by_class = defaultdict(list)
for v in hard_violations:
    class_id = v.get('class', 'UNKNOWN')
    violations_by_class[class_id].append(v.get('type'))

print(f"\n📚 Classes with violations: {len(violations_by_class)}")

# Show top problem classes
print("\n🔴 Top 10 Problem Classes (most violations):")
top_classes = sorted(violations_by_class.items(), key=lambda x: len(x[1]), reverse=True)[:10]
for class_id, v_types in top_classes:
    print(f"   {class_id}: {len(v_types)} violations")
    from collections import Counter
    type_counts = Counter(v_types)
    for v_type, count in type_counts.most_common():
        print(f"      - {v_type}: {count}")

# Compare with LLM
llm_file = 'output/validation_detailed_unified.json'
with open(llm_file, 'r', encoding='utf-8') as f:
    llm_data = json.load(f)

llm_hard_viols = llm_data.get('hard_violations', [])
llm_violations_by_type = defaultdict(int)
for v in llm_hard_viols:
    v_type = v.get('type', 'UNKNOWN')
    llm_violations_by_type[v_type] += 1

print("\n" + "="*100)
print("ALGORITHM vs LLM - VIOLATION COMPARISON")
print("="*100)

all_types = set(violations_by_type.keys()) | set(llm_violations_by_type.keys())

print(f"\n{'Type':<20} {'Algorithm':<15} {'LLM':<15} {'Difference'}")
print("-" * 65)
for v_type in sorted(all_types):
    algo_count = violations_by_type.get(v_type, 0)
    llm_count = llm_violations_by_type.get(v_type, 0)
    diff = algo_count - llm_count
    print(f"{v_type:<20} {algo_count:<15} {llm_count:<15} {diff:+}")

print("\n💡 KEY FINDINGS:")
print(f"   Algorithm: {len(hard_violations)} violations | LLM: {len(llm_hard_viols)} violations")
print(f"   Algorithm is WORSE by: {len(hard_violations) - len(llm_hard_viols)} violations")
