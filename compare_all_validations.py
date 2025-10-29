#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
COMPARISON: Tat ca validation results
So sanh tat ca ket qua validation: LLM, Algorithm moi, Algorithm cu
"""

import json
from pathlib import Path
from collections import defaultdict

def load_json(filepath):
    """Load JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: Cannot load {filepath}: {e}")
        return None

def extract_violations(data, source):
    """Extract violations from different formats"""
    
    violations = {
        'hard': [],
        'soft': [],
        'total_assignments': 0,
    }
    
    if source == 'llm_new':
        # From validate_detailed_new.py
        violations['hard'] = data.get('hard_violations', [])
        summary = data.get('summary', {})
        violations['total_assignments'] = summary.get('total_assignments', 0)
        
    elif source == 'algo_new':
        # From validate_algorithm_output_new.py
        violations['hard'] = data.get('hard_violations', [])
        summary = data.get('summary', {})
        violations['total_assignments'] = summary.get('total_assignments', 0)
        
    elif source == 'algo_old':
        # From validation_report_DOT1_2025-2026_HK1_validated.json
        hard_constraints = data.get('hard_constraints', {})
        violations_by_class = hard_constraints.get('violations_by_class', {})
        
        # Convert to flat list
        for class_id, viols in violations_by_class.items():
            for v in viols:
                violations['hard'].append({
                    'type': v.get('type', 'UNKNOWN'),
                    'class': class_id,
                    'name': v.get('name', ''),
                    'detail': v.get('detail', ''),
                })
        
        violations['total_assignments'] = data.get('summary', {}).get('total_assignments', 0)
    
    return violations

def main():
    print("\n" + "="*100)
    print("COMPARISON: ALL VALIDATION RESULTS")
    print("="*100)
    
    # Load all files
    llm_new_file = 'output/validation_detailed_unified.json'
    algo_new_file = 'output/validation_algorithm_unified.json'
    algo_old_file = 'output/validation_report_DOT1_2025-2026_HK1_validated.json'
    
    llm_new_data = load_json(llm_new_file)
    algo_new_data = load_json(algo_new_file)
    algo_old_data = load_json(algo_old_file)
    
    if not all([llm_new_data, algo_new_data, algo_old_data]):
        print("ERROR: Cannot load all files")
        return
    
    # Extract violations
    llm_new = extract_violations(llm_new_data, 'llm_new')
    algo_new = extract_violations(algo_new_data, 'algo_new')
    algo_old = extract_violations(algo_old_data, 'algo_old')
    
    # Analyze hard violations
    def count_by_type(violations):
        by_type = defaultdict(int)
        for v in violations:
            v_type = v.get('type', 'UNKNOWN')
            by_type[v_type] += 1
        return dict(by_type)
    
    print("\n[1] LLM NEW (validate_detailed_new.py)")
    print(f"    Total Assignments: {llm_new['total_assignments']}")
    print(f"    Hard Violations: {len(llm_new['hard'])}")
    print(f"    By Type: {count_by_type(llm_new['hard'])}")
    
    print("\n[2] ALGORITHM NEW (validate_algorithm_output_new.py)")
    print(f"    Total Assignments: {algo_new['total_assignments']}")
    print(f"    Hard Violations: {len(algo_new['hard'])}")
    print(f"    By Type: {count_by_type(algo_new['hard'])}")
    
    print("\n[3] ALGORITHM OLD (validation_report_DOT1_2025-2026_HK1_validated.json)")
    print(f"    Total Assignments: {algo_old['total_assignments']}")
    print(f"    Hard Violations: {len(algo_old['hard'])}")
    print(f"    By Type: {count_by_type(algo_old['hard'])}")
    
    # Compare
    print("\n" + "="*100)
    print("ANALYSIS")
    print("="*100)
    
    llm_count = len(llm_new['hard'])
    algo_new_count = len(algo_new['hard'])
    algo_old_count = len(algo_old['hard'])
    
    print(f"\nHard Violations Count:")
    print(f"  LLM New:      {llm_count:3d}")
    print(f"  Algo New:     {algo_new_count:3d}")
    print(f"  Algo Old:     {algo_old_count:3d}")
    
    if algo_new_count == 0 and algo_old_count > 0:
        print(f"\n  WARNING: Algo New has ZERO violations but Algo Old has {algo_old_count}!")
        print(f"  This suggests validate_algorithm_output_new.py has a BUG")
        print(f"  or it's checking a DIFFERENT schedule file")
    
    # Compare LLM vs Algo Old
    print(f"\nLLM vs Algorithm (using old validated file):")
    print(f"  LLM:  {llm_count} violations")
    print(f"  Algo: {algo_old_count} violations")
    
    if llm_count < algo_old_count:
        ratio = algo_old_count / llm_count if llm_count > 0 else float('inf')
        print(f"  => LLM is {ratio:.1f}x BETTER")
    else:
        print(f"  => LLM is WORSE or EQUAL")
    
    # Recommendation
    print(f"\n" + "="*100)
    print("ISSUES & RECOMMENDATIONS")
    print("="*100)
    
    issues = []
    
    if algo_new_count == 0 and algo_old_count > 0:
        issues.append(
            "ERROR: validate_algorithm_output_new.py produces ZERO violations\n"
            "       but old validation had 205 violations.\n"
            "       ACTION: Fix the import in validate_algorithm_output_new.py\n"
            "               Ensure it uses validation_framework_v2"
        )
    
    if llm_count > 0 and algo_old_count > 0:
        issues.append(
            f"INFO: LLM output ({llm_count} violations) is better than Algorithm ({algo_old_count} violations)\n"
            f"      Use LLM output as reference for quality comparison"
        )
    
    if not issues:
        issues.append("No major issues detected")
    
    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. {issue}")
    
    print(f"\n" + "="*100 + "\n")

if __name__ == '__main__':
    main()
