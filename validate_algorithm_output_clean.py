#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Validate Algorithm Output - UNIFIED VALIDATION VERSION (No Emoji)
Kiem tra toan dien lich tu schedule_algorithm_*.json

Su dung UnifiedValidator + MetricsCalculator de dam bao nhat quan
voi validate_detailed.py (LLM output)

Tinh nang:
- Kiem tra HARD CONSTRAINTS (rang buoc cung)
- Tinh SOFT CONSTRAINTS fitness score
- So sanh voi LLM output neu co
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
    LopMonHoc, GiangVien, PhongHoc, TimeSlot, PhanCong, NguyenVong
)
from apps.scheduling.validators.validation_framework_v2 import (
    UnifiedValidator, load_schedule_from_json, ScheduleData
)
from apps.scheduling.validators import MetricsCalculator
from apps.scheduling.validators.unified_output_format import UnifiedValidationOutput

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

ALGORITHM_SCHEDULES = [
    'output/schedule_algorithm.json',
    'output/schedule_algorithm_DOT1_2025-2026_HK1.json',
]

LLM_SCHEDULE = 'output/schedule_llm_2025-2026-HK1.json'

MA_DOT = 'DOT1_2025-2026_HK1'

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def find_latest_algorithm_schedule():
    """Find latest algorithm schedule file"""
    output_dir = Path('output')
    
    for pattern in ALGORITHM_SCHEDULES:
        fpath = Path(pattern)
        if fpath.exists():
            return str(fpath)
    
    candidates = list(output_dir.glob('schedule_algorithm_*.json'))
    if candidates:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return str(candidates[0])
    
    return None


def compare_schedules(llm_result: dict, algo_result: dict) -> dict:
    """Compare validation results between LLM and Algorithm"""
    
    comparison = {
        'llm_status': llm_result.get('status'),
        'algo_status': algo_result.get('status'),
        'llm_violations': len(llm_result.get('violations', [])),
        'algo_violations': len(algo_result.get('violations', [])),
        'llm_fitness': llm_result.get('fitness_score'),
        'algo_fitness': algo_result.get('fitness_score'),
        'better': None,
        'difference': None,
    }
    
    llm_fitness = llm_result.get('fitness_score', -float('inf'))
    algo_fitness = algo_result.get('fitness_score', -float('inf'))
    
    if llm_fitness > algo_fitness + 0.01:
        comparison['better'] = 'LLM'
        comparison['difference'] = llm_fitness - algo_fitness
    elif algo_fitness > llm_fitness + 0.01:
        comparison['better'] = 'Algorithm'
        comparison['difference'] = algo_fitness - llm_fitness
    else:
        comparison['better'] = 'EQUAL'
        comparison['difference'] = abs(llm_fitness - algo_fitness)
    
    return comparison


# ============================================================================
# MAIN VALIDATION PIPELINE
# ============================================================================

def main():
    print("\n" + "="*100)
    print("ALGORITHM OUTPUT VALIDATION - UNIFIED FRAMEWORK")
    print("="*100)
    
    # 1. Find algorithm schedule
    print(f"\nSearching for algorithm schedule...")
    algo_schedule_file = find_latest_algorithm_schedule()
    
    if not algo_schedule_file:
        print(f"   ERROR: No algorithm schedule found in output/")
        print(f"   Tried patterns: {ALGORITHM_SCHEDULES}")
        return
    
    print(f"   OK: Found {algo_schedule_file}")
    
    # 2. Validate algorithm schedule
    print(f"\n{'='*100}")
    print("ALGORITHM VALIDATION")
    print(f"{'='*100}")
    
    algo_result, algo_schedule_data, algo_validator = validate_schedule_file(algo_schedule_file, MA_DOT, "Algorithm")
    
    # 3. Optionally validate LLM schedule and compare
    if Path(LLM_SCHEDULE).exists():
        print(f"\n{'='*100}")
        print("LLM VALIDATION (for comparison)")
        print(f"{'='*100}")
        
        llm_result, llm_schedule_data, llm_validator = validate_schedule_file(LLM_SCHEDULE, MA_DOT, "LLM")
        
        # Compare results
        print(f"\n{'='*100}")
        print("COMPARISON: ALGORITHM vs LLM")
        print(f"{'='*100}")
        
        comparison = compare_schedules(llm_result, algo_result)
        print_comparison(comparison, algo_result, llm_result)
        
        # Save both algorithm and LLM reports in UNIFIED FORMAT
        save_algorithm_report(algo_result, algo_schedule_data, algo_validator)
        
        # Save comparison report
        save_comparison_report(algo_result, llm_result, comparison)
    else:
        print(f"\nWARNING: LLM schedule not found: {LLM_SCHEDULE}")
        print(f"   Skipping comparison. Only validating algorithm output.")
        
        # Save algorithm report only
        save_algorithm_report(algo_result, algo_schedule_data, algo_validator)
    
    print("\n" + "="*100)
    print("OK: VALIDATION COMPLETE")
    print("="*100 + "\n")


def validate_schedule_file(filepath: str, ma_dot: str, source: str) -> dict:
    """Validate a schedule file using UnifiedValidator"""
    
    print(f"\nLoading schedule from {Path(filepath).name}...")
    try:
        schedule_data = load_schedule_from_json(filepath)
        print(f"   OK: Loaded {len(schedule_data.get_all_assignments())} assignments")
    except Exception as e:
        print(f"   ERROR loading schedule: {e}")
        return None, None, None
    
    print(f"\nInitializing validator (source={source}, ma_dot={ma_dot})...")
    try:
        validator = UnifiedValidator(ma_dot=ma_dot, schedule_data=schedule_data)
        print(f"   OK: Validator initialized")
    except Exception as e:
        print(f"   WARNING initializing validator: {e}")
        validator = None
    
    print(f"\nValidating schedule...")
    result = validator.validate_schedule()
    
    # Print summary
    print_validation_summary(result, source)
    
    return result, schedule_data, validator


def print_validation_summary(result: dict, source: str):
    """Print validation summary for a schedule"""
    
    status = result.get('status', 'UNKNOWN')
    total = result.get('total_assignments', 0)
    violations = len(result.get('violations', []))
    fitness = result.get('fitness_score')
    
    print(f"\n[{source} Validation Results]")
    print(f"   Status: {status}")
    print(f"   Total Assignments: {total}")
    print(f"   Hard Violations: {violations}")
    
    if fitness is not None:
        fitness_level = "GREEN" if fitness > 0.9 else "YELLOW" if fitness > 0.7 else "RED"
        print(f"   Fitness Score: {fitness:.4f} ({fitness_level})")
    
    if 'metrics' in result:
        metrics = result.get('metrics', {})
        violations_list = metrics.get('violations', [])
        if violations_list:
            print(f"   Soft Constraint Violations: {len(violations_list)}")


def print_comparison(comparison: dict, algo_result: dict, llm_result: dict):
    """Print comparison between algorithm and LLM"""
    
    print(f"\n[COMPARISON METRICS]")
    print(f"   Algorithm Status: {comparison['algo_status']} | LLM Status: {comparison['llm_status']}")
    print(f"   Algorithm Violations: {comparison['algo_violations']} | LLM Violations: {comparison['llm_violations']}")
    
    algo_fitness = comparison['algo_fitness']
    llm_fitness = comparison['llm_fitness']
    
    if algo_fitness is not None and llm_fitness is not None:
        print(f"   Algorithm Fitness: {algo_fitness:.4f} | LLM Fitness: {llm_fitness:.4f}")
        
        if comparison['better'] == 'Algorithm':
            print(f"\n   RESULT: Algorithm is BETTER by {comparison['difference']:.4f} points")
        elif comparison['better'] == 'LLM':
            print(f"\n   RESULT: LLM is BETTER by {comparison['difference']:.4f} points")
        else:
            print(f"\n   RESULT: Results are EQUAL (diff={comparison['difference']:.4f})")
    else:
        print(f"   WARNING: Cannot compare fitness scores (one or both missing)")


def save_algorithm_report(result: dict, schedule_data, validator):
    """Save algorithm validation report in UNIFIED FORMAT"""
    
    # Create UnifiedValidationOutput
    total_assignments = result.get('total_assignments', 0)
    unified_output_obj = UnifiedValidationOutput(
        source="Algorithm",
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
        all_classes = LopMonHoc.objects.all()
        for lop in all_classes:
            if lop.ma_lop not in violated_classes:
                ok_class_info = {
                    'MaLop': lop.ma_lop,
                    'info': {
                        'TenMonHoc': lop.ma_mon_hoc.ten_mon_hoc if lop.ma_mon_hoc else 'N/A',
                        'SoCaTuan': lop.so_ca_tuan or 1,
                        'Nhom': lop.nhom_mh or '?',
                        'SoSV': lop.so_luong_sv or 0,
                        'ThietBiYeuCau': lop.thiet_bi_yeu_cau or '',
                        'SoTinChi': lop.ma_mon_hoc.so_tin_chi if lop.ma_mon_hoc else 0,
                    }
                }
                unified_output_obj.add_ok_class(ok_class_info)
    except:
        pass
    
    # Generate and save
    output_dict = unified_output_obj.generate()
    
    # Add fitness score if available
    if 'fitness_score' in result:
        output_dict['fitness']['combined_fitness'] = result['fitness_score']
    
    output_file = 'output/validation_algorithm_unified.json'
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_dict, f, ensure_ascii=False, indent=2)
    
    print(f"\nOK: Algorithm report saved (UNIFIED FORMAT): {output_file}")
    
    # Print summary
    unified_output_obj.print_summary()


def save_comparison_report(algo_result: dict, llm_result: dict, comparison: dict):
    """Save comparison report between algorithm and LLM"""
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'ma_dot': MA_DOT,
        'comparison': comparison,
        'algorithm': algo_result,
        'llm': llm_result,
    }
    
    output_file = 'output/validation_comparison_algorithm_vs_llm.json'
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\nOK: Comparison report saved: {output_file}")


if __name__ == '__main__':
    main()
