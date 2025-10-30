#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UNIFIED VALIDATION OUTPUT FORMAT SPECIFICATION
Định nghĩa format output chuẩn cho cả LLM và Algorithm validation
"""

import json
from typing import Dict, List, Any
from datetime import datetime

# ============================================================================
# UNIFIED OUTPUT FORMAT SPECIFICATION
# ============================================================================

UNIFIED_OUTPUT_SCHEMA = {
    "timestamp": "ISO 8601 datetime",
    "source": "LLM | Algorithm",
    "ma_dot": "DOT1_2025-2026_HK1",
    
    "summary": {
        "total_classes": "int - Total number of classes",
        "ok_classes": "int - Classes with no violations",
        "violated_classes": "int - Classes with any violations",
        "hard_violated_classes": "int - Classes with hard constraint violations",
        "soft_violated_classes": "int - Classes with soft constraint violations",
        "ok_percentage": "float - % of OK classes",
        "violated_percentage": "float - % of violated classes",
        "hard_violated_percentage": "float - % of hard violated classes",
        "soft_violated_percentage": "float - % of soft violated classes",
    },
    
    "constraint_stats": {
        "hard_constraints": {
            "HC-01": "int - count",
            "HC-02": "int - count",
            "HC-03": "int - count",
            "HC-04": "int - count",
            "HC-05": "int - count",
            "HC-06": "int - count",
            "HC-08": "int - count",
            "HC-13": "int - count",
        },
        "soft_constraints": {
            "RBM-001": "int - count",
            "RBM-002": "int - count",
            "RBM-003": "int - count",
            "RBM-004": "int - count",
            "RBM-005": "int - count",
            "RBM-006": "int - count",
            "RBM-007": "int - count",
        },
    },
    
    "fitness": {
        "hard_fitness": "float - 1.0 - (hard_violations / total_classes)",
        "soft_fitness": "float - fitness from soft constraints",
        "combined_fitness": "float - (hard_fitness + soft_fitness) / 2",
        "status": "PASS | WARNING | FAIL",
    },
    
    "hard_violations": [
        {
            "type": "HC-XX_NAME",
            "class": "LOP-XXXXX",
            "room": "Phòng (nếu có)",
            "slot": "Slot (nếu có)",
            "required": "Yêu cầu (nếu có)",
            "available": "Có sẵn (nếu có)",
            "message": "Chi tiết lỗi",
        }
    ],
    
    "violations_by_class": {
        "LOP-XXXXX": [
            {
                "type": "HC-XX_NAME",
                "room": "...",
                "message": "...",
            }
        ],
    },
    
    "violations_by_type": {
        "HC-02": [
            {
                "class": "LOP-XXXXX",
                "message": "...",
            }
        ],
    },
    
    "ok_classes": [
        {
            "MaLop": "LOP-XXXXX",
            "info": {
                "TenMonHoc": "Tên môn học",
                "SoCaTuan": 1,
                "Nhom": 1,
                "SoSV": 40,
                "ThietBiYeuCau": "PC",
                "SoTinChi": 3,
            }
        }
    ],
}

# ============================================================================
# UNIFIED OUTPUT FORMAT GENERATOR
# ============================================================================

class UnifiedValidationOutput:
    """Generate unified validation output"""
    
    def __init__(self, source: str, ma_dot: str, total_classes: int, fitness_data: Dict = None):
        self.source = source  # "LLM" or "Algorithm"
        self.ma_dot = ma_dot
        self.total_classes = total_classes
        self.timestamp = datetime.now().isoformat()
        
        # 🔥 NEW: Store fitness data từ validator (hard_fitness, soft_fitness, combined_fitness)
        self.fitness_data = fitness_data or {}
        
        self.hard_violations = []
        self.soft_violations = []  # NEW: Store soft violations separately
        self.violations_by_class = {}
        self.violations_by_type = {}
        self.ok_classes = []
        
        self.hard_constraint_counts = {}
        self.soft_constraint_counts = {}
    
    @staticmethod
    def format_ok_class_info(lop_mon_hoc, schedule_data=None) -> Dict[str, Any]:
        """
        Static method: Format thông tin class thành unified format cho ok_class_info
        
        Args:
            lop_mon_hoc: LopMonHoc model instance
            schedule_data: Schedule data object để lấy room/slot assignments (optional)
        
        Returns:
            Dict với cấu trúc:
            {
                'MaLop': str,
                'MaGV': str (hoặc None),
                'MaPhong': str (hoặc None),
                'MaSlot': str (hoặc None),
                'info': {
                    'TenMonHoc': str,
                    'SoCaTuan': int,
                    'Nhom': str,
                    'SoSV': int,
                    'ThietBiYeuCau': str,
                    'SoTinChi': int,
                }
            }
        """
        from apps.scheduling.models import PhanCong
        
        # Get teacher assignment
        ma_gv = None
        phan_cong = PhanCong.objects.filter(ma_lop=lop_mon_hoc).first()
        if phan_cong and phan_cong.ma_gv:
            ma_gv = phan_cong.ma_gv.ma_gv
        
        # Get room assigned to this class (all sessions use same room)
        ma_phong = None
        ma_slot = None
        if schedule_data:
            class_assignments = schedule_data.get_assignments_for_class(lop_mon_hoc.ma_lop)
            if class_assignments:
                ma_phong = class_assignments[0].get('room')  # All sessions have same room
                ma_slot = class_assignments[0].get('slot')   # TimeSlotID (e.g., "Thu2-Ca4")
        
        return {
            'MaLop': lop_mon_hoc.ma_lop,
            'MaGV': ma_gv,
            'MaPhong': ma_phong,
            'MaSlot': ma_slot,
            'info': {
                'TenMonHoc': lop_mon_hoc.ma_mon_hoc.ten_mon_hoc if lop_mon_hoc.ma_mon_hoc else 'N/A',
                'SoCaTuan': lop_mon_hoc.so_ca_tuan or 1,
                'Nhom': lop_mon_hoc.nhom_mh or '?',
                'SoSV': lop_mon_hoc.so_luong_sv or 0,
                'ThietBiYeuCau': lop_mon_hoc.thiet_bi_yeu_cau or '',
                'SoTinChi': lop_mon_hoc.ma_mon_hoc.so_tin_chi if lop_mon_hoc.ma_mon_hoc else 0,
            }
        }
    
    def add_hard_violation(self, violation: Dict[str, Any]):
        """Thêm hard constraint violation"""
        self.hard_violations.append(violation)
        
        # Group by class
        ma_lop = violation.get('class')
        if ma_lop:
            if ma_lop not in self.violations_by_class:
                self.violations_by_class[ma_lop] = []
            self.violations_by_class[ma_lop].append(violation)
        
        # Group by type
        v_type = violation.get('type')
        if v_type:
            if v_type not in self.violations_by_type:
                self.violations_by_type[v_type] = []
            self.violations_by_type[v_type].append(violation)
            
            # Count by type
            self.hard_constraint_counts[v_type] = self.hard_constraint_counts.get(v_type, 0) + 1
    
    def add_soft_violation(self, violation: Dict[str, Any]):
        """Thêm soft constraint violation"""
        self.soft_violations.append(violation)
        
        # Count soft violations
        v_type = violation.get('type')
        if v_type:
            if v_type not in self.violations_by_type:
                self.violations_by_type[v_type] = []
            self.violations_by_type[v_type].append(violation)
            
            # Count by type
            self.soft_constraint_counts[v_type] = self.soft_constraint_counts.get(v_type, 0) + 1
    
    def add_ok_class(self, class_info: Dict[str, Any]):
        """Thêm class không có violations"""
        self.ok_classes.append(class_info)
    
    def generate(self) -> Dict[str, Any]:
        """Generate unified output
        
        Logic tính fitness:
        - Nếu có HARD CONSTRAINTS violations → Lịch KHÔNG khả thi → Fitness = 0.0
        - Nếu KHÔNG có hard violations → Tính từ soft constraints
          - hard_fitness = 1.0 - (soft_violations / total_classes)
          - soft_fitness = 1.0 (không vi phạm hard)
          - combined_fitness = (hard_fitness + soft_fitness) / 2
        """
        
        violated_classes = len(self.violations_by_class)
        ok_classes_count = self.total_classes - violated_classes
        hard_violations_count = len(self.hard_violations)
        soft_violations_count = len(self.soft_violations)
        
        ok_percentage = (ok_classes_count / self.total_classes * 100) if self.total_classes > 0 else 0
        violated_percentage = (violated_classes / self.total_classes * 100) if self.total_classes > 0 else 0
        hard_violated_percentage = (len(set(v.get('class') for v in self.hard_violations)) / self.total_classes * 100) if self.total_classes > 0 else 0
        soft_violated_percentage = (len(set(v.get('class') for v in self.soft_violations)) / self.total_classes * 100) if self.total_classes > 0 else 0
        
        # 🔥 Calculate fitness scores từ fitness_data (nếu có từ validator)
        # Nếu validator pass fitness_data → Dùng đó (chính xác hơn)
        # Nếu không → Tính lại (backward compatibility)
        if self.fitness_data:
            hard_fitness = self.fitness_data.get('hard_fitness', 0.0)
            soft_fitness = self.fitness_data.get('soft_fitness', 0.0)
            combined_fitness = self.fitness_data.get('combined_fitness', 0.0)
        else:
            # Fallback: Tính lại (cũ cách tính)
            if hard_violations_count > 0:
                hard_fitness = 0.0
                soft_fitness = 0.0
                combined_fitness = 0.0
            else:
                # Không có hard violations → Tính từ soft constraints
                hard_fitness = 1.0 - (soft_violations_count / self.total_classes) if self.total_classes > 0 else 1.0
                soft_fitness = 1.0  # Không vi phạm hard constraints
                combined_fitness = (hard_fitness + soft_fitness) / 2.0
        
        # Determine status
        if combined_fitness <= 0.0:
            status = "INFEASIBLE"  # Lịch không khả thi
        elif combined_fitness < 0.7:
            status = "FAIL"
        elif combined_fitness < 0.9:
            status = "WARNING"
        else:
            status = "PASS"
        
        output = {
            "timestamp": self.timestamp,
            "source": self.source,
            "ma_dot": self.ma_dot,
            
            "summary": {
                "total_classes": self.total_classes,
                "ok_classes": ok_classes_count,
                "violated_classes": violated_classes,
                "hard_violated_classes": len(set(v.get('class') for v in self.hard_violations)),
                "soft_violated_classes": len(set(v.get('class') for v in self.soft_violations)),
                "ok_percentage": round(ok_percentage, 2),
                "violated_percentage": round(violated_percentage, 2),
                "hard_violated_percentage": round(hard_violated_percentage, 2),
                "soft_violated_percentage": round(soft_violated_percentage, 2),
            },
            
            "constraint_stats": {
                "hard_constraints": dict(sorted(self.hard_constraint_counts.items())),
                "soft_constraints": dict(sorted(self.soft_constraint_counts.items())),
            },
            
            "fitness": {
                "hard_fitness": round(hard_fitness, 4),
                "soft_fitness": round(soft_fitness, 4),
                "combined_fitness": round(combined_fitness, 4),
                "status": status,
            },
            
            "hard_violations": self.hard_violations,
            "soft_violations": self.soft_violations,
            "violations_by_class": dict(sorted(self.violations_by_class.items())),
            "violations_by_type": dict(sorted(self.violations_by_type.items())),
            "ok_classes": self.ok_classes,
        }
        
        return output
    
    def save(self, output_file: str):
        """Save unified output to file"""
        output = self.generate()
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    
    def print_summary(self):
        """Print summary"""
        output = self.generate()
        summary = output['summary']
        fitness = output['fitness']
        constraints = output['constraint_stats']
        
        print("\n" + "="*100)
        print(f"UNIFIED VALIDATION OUTPUT - {self.source}")
        print("="*100)
        
        print(f"\n[Summary]")
        print(f"  Total Classes: {summary['total_classes']}")
        print(f"  OK Classes: {summary['ok_classes']} ({summary['ok_percentage']}%)")
        print(f"  Violated Classes: {summary['violated_classes']} ({summary['violated_percentage']}%)")
        print(f"  - Hard Violated: {summary['hard_violated_classes']} ({summary['hard_violated_percentage']}%)")
        print(f"  - Soft Violated: {summary['soft_violated_classes']} ({summary['soft_violated_percentage']}%)")
        
        print(f"\n[Fitness]")
        print(f"  Hard Fitness: {fitness['hard_fitness']}")
        print(f"  Soft Fitness: {fitness['soft_fitness']}")
        print(f"  Combined Fitness: {fitness['combined_fitness']}")
        print(f"  Status: {fitness['status']}")
        
        print(f"\n[Hard Constraints]")
        for constraint, count in sorted(constraints['hard_constraints'].items()):
            print(f"  {constraint}: {count}")
        
        if constraints['soft_constraints']:
            print(f"\n[Soft Constraints]")
            for constraint, count in sorted(constraints['soft_constraints'].items()):
                print(f"  {constraint}: {count}")
        
        print("\n" + "="*100 + "\n")
