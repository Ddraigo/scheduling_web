#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script kiem tra CHI TIET lich xep - UNIFIED VALIDATION VERSION
Su dung UnifiedValidator + MetricsCalculator

Tinh nang:
- Kiem tra HARD CONSTRAINTS (rang buoc cung)
- Tinh SOFT CONSTRAINTS fitness score
- Xuat bao cao chi tiet JSON + terminal
"""

import json
import sys
import os
import django
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import logging

# Setup Django
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import (
    LopMonHoc, GiangVien, PhongHoc, TimeSlot, PhanCong, DotXep, ThoiKhoaBieu, NguyenVong
)
from apps.scheduling.validators.validation_framework_v2 import (
    UnifiedValidator, load_schedule_from_json
)
from apps.scheduling.validators import MetricsCalculator
from apps.scheduling.validators.unified_output_format import UnifiedValidationOutput

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Các vị trí có thể có LLM schedule file
LLM_SCHEDULE_PATHS = [
    'output/schedule_llm_2025-2026-HK1.json',
]

# Lấy file đầu tiên tồn tại
SCHEDULE_FILE = None
for path in LLM_SCHEDULE_PATHS:
    if Path(path).exists():
        SCHEDULE_FILE = path
        break
MA_DOT = 'DOT1_2025-2026_HK1'
OUTPUT_REPORT = 'output/validation_detailed_unified.json'

# ============================================================================
# MAIN VALIDATION PIPELINE
# ============================================================================

def main():
    print("\n" + "="*100)
    print("VALIDATION FRAMEWORK - KIEM TRA LICH XEP CHI TIET")
    print("="*100)
    
    # 1. Load schedule data
    print(f"\nLoading schedule from {SCHEDULE_FILE}...")
    try:
        schedule_data = load_schedule_from_json(SCHEDULE_FILE)
        print(f"   OK: Loaded {len(schedule_data.get_all_assignments())} assignments")
    except Exception as e:
        print(f"   ERROR loading schedule: {e}")
        return
    
    # 2. Initialize UnifiedValidator
    print(f"\nInitializing validator (ma_dot={MA_DOT})...")
    try:
        validator = UnifiedValidator(ma_dot=MA_DOT, schedule_data=schedule_data)
        print(f"   OK: Validator initialized")
    except Exception as e:
        print(f"   ERROR initializing validator: {e}")
        return
    
    # 3. Validate schedule
    print(f"\nValidating schedule...")
    result = validator.validate_schedule()
    
    # 4. Print report (skip due to encoding issues, JSON is saved)
    # print_validation_report(result, schedule_data, validator)
    
    # 5. Save JSON report
    print(f"\nSaving detailed report to {OUTPUT_REPORT}...")
    save_detailed_report(result, schedule_data, validator, OUTPUT_REPORT)
    
    print("\n" + "="*100)
    print("OK: VALIDATION COMPLETE")
    print("="*100 + "\n")


def print_validation_report(result: dict, schedule_data, validator):
    """In bao cao validation"""
    
    status = result.get('status', 'UNKNOWN')
    total = result.get('total_assignments', 0)
    violations = result.get('violations', [])
    
    print(f"\n{'='*100}")
    print("VALIDATION SUMMARY")
    print(f"{'='*100}")
    
    # Status
    status_symbol = 'FAIL' if status == 'FAIL' else 'WARNING' if status == 'WARNING' else 'OK'
    print(f"\nStatus: {status_symbol}")
    print(f"Total Assignments: {total}")
    print(f"Hard Constraint Violations: {len(violations)}")
    
    # Fitness score
    if 'fitness_score' in result:
        fitness = result['fitness_score']
        fitness_symbol = 'GREEN' if fitness > 0.9 else 'YELLOW' if fitness > 0.7 else 'RED'
        print(f"Fitness Score: {fitness:.4f} ({fitness_symbol}) - 1.0=perfect, 0.0=worst, <0=severe")
    
    # Detailed metrics
    if 'metrics' in result:
        metrics = result['metrics']
        violations_list = metrics.get('violations', [])
        
        if violations_list:
            print(f"\nSOFT CONSTRAINT VIOLATIONS:")
            for v in violations_list:
                name = v.get('name', 'Unknown')
                count = v.get('violation_count', 0)
                weight = v.get('weight', 0)
                penalty = v.get('penalty', 0)
                print(f"   - {name}: {count} violations, penalty={penalty:.2f}")
    
    # Hard constraint violations summary
    if violations:
        print(f"\nHARD CONSTRAINT VIOLATIONS SUMMARY:")
        violation_types = defaultdict(int)
        for v in violations:
            v_type = v.get('type', 'UNKNOWN')
            violation_types[v_type] += 1
        
        for v_type in sorted(violation_types.keys()):
            count = violation_types[v_type]
            print(f"   - {v_type}: {count} violations")
    
    # First 10 violations details
    if violations:
        print(f"\nFIRST 10 HARD CONSTRAINT VIOLATIONS:")
        for i, v in enumerate(violations[:10]):
            print(f"\n   {i+1}. {v.get('type', 'UNKNOWN')}")
            if 'class' in v:
                print(f"      Class: {v['class']}")
            if 'message' in v:
                print(f"      Message: {v['message']}")
    
    if len(violations) > 10:
        print(f"\n   ... and {len(violations)-10} more violations")


def save_detailed_report(result: dict, schedule_data, validator, output_file: str):
    """Save comprehensive JSON report in UNIFIED FORMAT"""
    
    # Create UnifiedValidationOutput
    total_assignments = result.get('total_assignments', 0)
    unified_output_obj = UnifiedValidationOutput(
        source="LLM",
        ma_dot=MA_DOT,
        total_classes=total_assignments
    )
    
    # Add hard violations
    for violation in result.get('violations', []):
        unified_output_obj.add_hard_violation(violation)
    
    # Add soft violations
    for soft_violation in result.get('soft_violations', []):
        unified_output_obj.add_soft_violation(soft_violation)
    
    # Get violated classes
    violated_classes = set(v.get('class') for v in result.get('violations', []) if v.get('class'))
    
    # Add OK classes
    try:
        from apps.scheduling.models import PhanCong
        
        all_classes = LopMonHoc.objects.all()
        for lop in all_classes:
            if lop.ma_lop not in violated_classes:
                ok_class_info = UnifiedValidationOutput.format_ok_class_info(lop, schedule_data)
                unified_output_obj.add_ok_class(ok_class_info)
    except Exception as e:
        logger.warning(f"Error adding ok_class_info: {e}")
    
    # Generate and save
    output_dict = unified_output_obj.generate()
    
    # Add fitness score if available
    if 'fitness_score' in result:
        output_dict['fitness']['combined_fitness'] = result['fitness_score']
    
    # Create output directory if not exists
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_dict, f, ensure_ascii=False, indent=2)
    
    print(f"   OK: Report saved (UNIFIED FORMAT): {output_file}")
    
    # Print summary
    unified_output_obj.print_summary()


if __name__ == '__main__':
    main()
