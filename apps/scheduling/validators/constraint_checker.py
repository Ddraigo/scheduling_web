"""
Shared constraint checking logic
Dùng chung cho GA algorithm, schedule validator, và validation scripts

Data Format Support:
1. Generic format: {'class': 'LOP-xxx', 'room': 'P101', 'slot': 'Thu2-Ca1'}
2. LLM format: {'ma_lop': 'LOP-xxx', 'ma_phong': 'P101', 'time_slot_id': 'T2-C1'}

Tự động detect format và xử lý cả hai
"""

from typing import Dict, List, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConstraintViolation:
    """Cấu trúc chuẩn cho constraint violation"""
    constraint_code: str  # 'HC-01', 'HC-02', 'HC-05', etc.
    message: str
    class_id: str
    severity: str = 'error'  # 'error' hoặc 'warning'
    details: Dict = field(default_factory=dict)


class ConstraintChecker:
    """
    Kiểm tra hard constraints cho schedules
    ⭐ LOGIC DÙNG CHUNG cho tất cả validation
    Hỗ trợ cả format generic và LLM
    """
    
    @staticmethod
    def _normalize_schedule(sched: Dict) -> Dict:
        """
        Normalize schedule sang format chung
        {'class': ..., 'room': ..., 'slot': ...}
        
        Hỗ trợ:
        - {'class': 'LOP-xxx', 'room': 'P101', 'slot': 'Thu2-Ca1'} → as-is
        - {'ma_lop': 'LOP-xxx', 'ma_phong': 'P101', 'time_slot_id': 'T2-C1'} → convert
        """
        normalized = {}
        
        # Class ID
        normalized['class'] = sched.get('class') or sched.get('ma_lop')
        
        # Room ID  
        normalized['room'] = sched.get('room') or sched.get('ma_phong')
        
        # Slot (standardize format)
        slot = sched.get('slot') or sched.get('time_slot_id')
        if slot:
            # Convert T2-C1 → Thu2-Ca1 if needed
            if slot.startswith('T') and '-C' in slot:
                parts = slot.split('-')
                day_str = 'Thu' + parts[0][1:]  # T2 → Thu2
                slot_str = 'Ca' + parts[1][1:]  # C1 → Ca1
                normalized['slot'] = f"{day_str}-{slot_str}"
            else:
                normalized['slot'] = slot
        
        # Da Dot (for LLM format)
        normalized['ma_dot'] = sched.get('ma_dot')
        
        return normalized
    
    @staticmethod
    def _normalize_assignment(assignment_data: Dict) -> Tuple[str, str]:
        """
        Normalize assignment data sang (class_id, teacher_id)
        
        Hỗ trợ:
        - {'MaLop': 'LOP-xxx', 'MaGV': 'GV001'} → ('LOP-xxx', 'GV001')
        - {'ma_lop': 'LOP-xxx', 'ma_gv': 'GV001'} → ('LOP-xxx', 'GV001')
        """
        class_id = assignment_data.get('MaLop') or assignment_data.get('ma_lop')
        teacher_id = assignment_data.get('MaGV') or assignment_data.get('ma_gv')
        return (class_id, teacher_id)
    
    @staticmethod
    def _calculate_class_type(class_data: Dict) -> str:
        """
        Xác định class type theo SQL logic:
        - WHEN so_tiet_th = 0 → 'LT'
        - WHEN so_tiet_lt = 0 AND so_tiet_th > 0 → 'TH'
        - WHEN so_tiet_lt > 0 AND so_tiet_th > 0 AND to_mh = 0 → 'LT'
        - ELSE → 'TH'
        
        Args:
            class_data: Dict có thể chứa: 
                - 'type': nếu đã có, dùng nó
                - 'SoTietTH', 'SoTietLT', 'To_MH': dùng để tính
                - 'so_tiet_th', 'so_tiet_lt', 'to_mh': dùng để tính
        """
        # Nếu đã có type, dùng luôn
        if 'type' in class_data and class_data['type']:
            return class_data['type']
        
        # Lấy giá trị (support cả snake_case và PascalCase)
        so_tiet_th = class_data.get('SoTietTH') or class_data.get('so_tiet_th') or 0
        so_tiet_lt = class_data.get('SoTietLT') or class_data.get('so_tiet_lt') or 0
        to_mh = class_data.get('To_MH') or class_data.get('to_mh')
        
        # Apply SQL logic
        if so_tiet_th == 0:
            return 'LT'
        elif so_tiet_lt == 0 and so_tiet_th > 0:
            return 'TH'
        elif so_tiet_lt > 0 and so_tiet_th > 0 and to_mh == 0:
            return 'LT'
        else:
            return 'TH'
    
    @staticmethod
    def check_teacher_conflicts(
        schedules: List[Dict],
        assignments_map: Dict[str, str]
    ) -> List[ConstraintViolation]:
        """
        HC-01: Kiểm tra GV dạy trùng giờ
        
        Args:
            schedules: [{'class': 'LOP-xxx', 'slot': 'Thu2-Ca1', 'room': 'P101'}, ...]
                       hoặc [{'ma_lop': 'LOP-xxx', 'time_slot_id': 'T2-C1', 'ma_phong': 'P101'}, ...]
            assignments_map: {'LOP-xxx': 'GV001', ...}
            
        Returns:
            List[ConstraintViolation]
        """
        violations = []
        by_teacher_time = defaultdict(list)
        
        # Group schedules by (teacher, timeslot)
        for sched in schedules:
            normalized = ConstraintChecker._normalize_schedule(sched)
            class_id = normalized.get('class')
            slot = normalized.get('slot')
            teacher = assignments_map.get(class_id)
            
            if teacher and slot:
                key = f"{teacher}_{slot}"
                by_teacher_time[key].append(class_id)
        
        # Detect conflicts
        for key, class_ids in by_teacher_time.items():
            if len(class_ids) > 1:
                parts = key.rsplit('_', 1)
                if len(parts) != 2:
                    continue
                teacher, slot = parts
                
                # Tạo 1 violation cho MỖI class bị ảnh hưởng bởi conflict
                for class_id in class_ids:
                    other_classes = [c for c in class_ids if c != class_id]
                    violations.append(ConstraintViolation(
                        constraint_code='HC-01',
                        message=f"GV {teacher} dạy trùng {slot} với lớp {', '.join(other_classes[:3])}{'...' if len(other_classes) > 3 else ''}",
                        class_id=class_id,
                        details={'teacher': teacher, 'slot': slot, 'conflicts': other_classes}
                    ))
        
        return violations
    
    @staticmethod
    def check_room_conflicts(schedules: List[Dict]) -> List[ConstraintViolation]:
        """
        HC-02: Kiểm tra phòng bị trùng giờ
        """
        violations = []
        by_room_time = defaultdict(list)
        
        for sched in schedules:
            normalized = ConstraintChecker._normalize_schedule(sched)
            room = normalized.get('room')
            slot = normalized.get('slot')
            class_id = normalized.get('class')
            if room and slot:
                key = f"{room}_{slot}"
                by_room_time[key].append(class_id)
        
        for key, class_ids in by_room_time.items():
            if len(class_ids) > 1:
                parts = key.rsplit('_', 1)
                if len(parts) != 2:
                    continue
                room, slot = parts
                
                # Tạo 1 violation cho MỖI class bị ảnh hưởng bởi conflict
                for class_id in class_ids:
                    other_classes = [c for c in class_ids if c != class_id]
                    violations.append(ConstraintViolation(
                        constraint_code='HC-02',
                        message=f"Phòng {room} bị trùng {slot} với lớp {', '.join(other_classes[:3])}{'...' if len(other_classes) > 3 else ''}",
                        class_id=class_id,
                        details={'room': room, 'slot': slot, 'conflicts': other_classes}
                    ))
        
        return violations
    
    @staticmethod
    def check_room_type_mismatch(
        schedules: List[Dict],
        class_types: Dict[str, str],  # {class_id: 'LT' or 'TH'}
        room_types: Dict[str, str]     # {room_id: 'LT' or 'TH'}
    ) -> List[ConstraintViolation]:
        """
        HC-05: Lớp TH xếp vào phòng LT
        HC-06: Lớp LT xếp vào phòng TH
        """
        violations = []
        
        for sched in schedules:
            normalized = ConstraintChecker._normalize_schedule(sched)
            class_id = normalized.get('class')
            room = normalized.get('room')
            
            if not class_id or not room:
                continue
            
            class_type = class_types.get(class_id, '')
            room_type = room_types.get(room, '')
            
            # HC-05: TH class → LT room
            if class_type == 'TH' and room_type == 'LT':
                violations.append(ConstraintViolation(
                    constraint_code='HC-05',
                    message=f"Phòng {room} là Lý thuyết, nhưng lớp cần TH",
                    class_id=class_id,
                    details={'room': room, 'class_type': 'TH', 'room_type': 'LT'}
                ))
            
            # HC-06: LT class → TH room
            elif class_type == 'LT' and room_type == 'TH':
                violations.append(ConstraintViolation(
                    constraint_code='HC-06',
                    message=f"Phòng {room} là Thực hành, nhưng lớp cần LT",
                    class_id=class_id,
                    details={'room': room, 'class_type': 'LT', 'room_type': 'TH'}
                ))
        
        return violations
    
    @staticmethod
    def check_room_capacity(
        schedules: List[Dict],
        class_sizes: Dict[str, int],      # {class_id: SoLuongSV}
        room_capacities: Dict[str, int]   # {room_id: SucChua}
    ) -> List[ConstraintViolation]:
        """
        HC-03: Phòng phải đủ chỗ ngồi cho lớp học
        """
        violations = []
        
        for sched in schedules:
            normalized = ConstraintChecker._normalize_schedule(sched)
            class_id = normalized.get('class')
            room = normalized.get('room')
            
            if not class_id or not room:
                continue
            
            class_size = class_sizes.get(class_id, 0)
            room_capacity = room_capacities.get(room, 0)
            
            # Phòng không đủ chỗ
            if class_size > room_capacity:
                violations.append(ConstraintViolation(
                    constraint_code='HC-03',
                    message=f"Phòng {room} chỉ chứa {room_capacity} SV, nhưng lớp có {class_size} SV (thiếu {class_size - room_capacity} chỗ)",
                    class_id=class_id,
                    details={
                        'room': room,
                        'class_size': class_size,
                        'room_capacity': room_capacity,
                        'shortage': class_size - room_capacity
                    }
                ))
        
        return violations
    
    @staticmethod
    def check_room_equipment(
        schedules: List[Dict],
        class_equipment: Dict[str, str],    # {class_id: ThietBiYeuCau}
        room_equipment: Dict[str, str]      # {room_id: ThietBi}
    ) -> List[ConstraintViolation]:
        """
        HC-04: Phòng phải có đủ thiết bị yêu cầu của lớp học
        """
        violations = []
        
        for sched in schedules:
            normalized = ConstraintChecker._normalize_schedule(sched)
            class_id = normalized.get('class')
            room = normalized.get('room')
            
            if not class_id or not room:
                continue
            
            required = class_equipment.get(class_id, '')
            if not required:
                continue
            
            # Parse required equipment (comma or semicolon separated)
            required_items = [item.strip().lower() for item in required.replace(';', ',').split(',') if item.strip()]
            
            # Get available equipment
            available = room_equipment.get(room, '').lower()
            
            # Check missing equipment
            missing = [req for req in required_items if req not in available]
            if missing:
                violations.append(ConstraintViolation(
                    constraint_code='HC-04',
                    message=f"Phòng {room} thiếu thiết bị: {', '.join(missing)}",
                    class_id=class_id,
                    details={
                        'room': room,
                        'required': required,
                        'available': room_equipment.get(room, ''),
                        'missing': missing
                    }
                ))
        
        return violations
    
    @staticmethod
    def check_sunday_classes(schedules: List[Dict]) -> List[ConstraintViolation]:
        """
        HC-08: Lớp học vào Chủ nhật
        """
        violations = []
        
        for sched in schedules:
            normalized = ConstraintChecker._normalize_schedule(sched)
            slot = normalized.get('slot', '')
            class_id = normalized.get('class')
            if 'Thu8' in slot or 'T8' in slot:  # Chủ nhật
                violations.append(ConstraintViolation(
                    constraint_code='HC-08',
                    message=f"Xếp lịch vào Chủ nhật",
                    class_id=class_id,
                    details={'slot': slot}
                ))
        
        return violations
    
    @staticmethod
    def check_session_requirements(
        schedules: List[Dict],
        class_sessions: Dict[str, int]  # {class_id: SoCaTuan}
    ) -> List[ConstraintViolation]:
        """
        HC-13: Kiểm tra yêu cầu SoCaTuan=2 (2 ca liên tiếp cùng ngày)
        """
        violations = []
        
        # Group schedules by class
        by_class = defaultdict(list)
        for sched in schedules:
            normalized = ConstraintChecker._normalize_schedule(sched)
            class_id = normalized.get('class')
            if class_id:
                by_class[class_id].append(normalized)
        
        for class_id, sessions_required in class_sessions.items():
            if sessions_required != 2:
                continue  # Chỉ check SoCaTuan=2
            
            class_schedules = by_class.get(class_id, [])
            
            # Phải có đúng 2 buổi
            if len(class_schedules) != 2:
                violations.append(ConstraintViolation(
                    constraint_code='HC-13',
                    message=f"SoCaTuan=2 nhưng có {len(class_schedules)} buổi",
                    class_id=class_id,
                    details={'required': 2, 'actual': len(class_schedules)}
                ))
                continue
            
            # Parse days và slots
            days = []
            slots = []
            for sched in class_schedules:
                slot_str = sched.get('slot', '')
                if '-' not in slot_str:
                    continue
                    
                parts = slot_str.split('-')
                if len(parts) != 2:
                    continue
                    
                day_part = parts[0]  # "Thu2" hoặc "T2"
                slot_part = parts[1]  # "Ca1" hoặc "C1"
                
                # Extract numbers
                day_num_str = ''.join(filter(str.isdigit, day_part))
                slot_num_str = ''.join(filter(str.isdigit, slot_part))
                
                if day_num_str and slot_num_str:
                    day_num = int(day_num_str)
                    slot_num = int(slot_num_str)
                    days.append(day_num)
                    slots.append(slot_num)
            
            if len(days) != 2 or len(slots) != 2:
                continue
            
            # Phải cùng ngày
            if days[0] != days[1]:
                violations.append(ConstraintViolation(
                    constraint_code='HC-13',
                    message=f"2 ca không cùng ngày",
                    class_id=class_id,
                    details={'days': days}
                ))
            # Phải liên tiếp
            elif abs(slots[0] - slots[1]) != 1:
                violations.append(ConstraintViolation(
                    constraint_code='HC-13',
                    message=f"2 ca không liên tiếp: Ca{slots[0]} và Ca{slots[1]}",
                    class_id=class_id,
                    details={'slots': slots}
                ))
        
        return violations
    
    @staticmethod
    def check_missing_classes(
        schedules: List[Dict],
        all_classes: List[str]
    ) -> List[ConstraintViolation]:
        """
        MISSING: Lớp chưa được xếp lịch
        """
        violations = []
        scheduled_classes = {s['class'] for s in schedules}
        
        for class_id in all_classes:
            if class_id not in scheduled_classes:
                violations.append(ConstraintViolation(
                    constraint_code='MISSING',
                    message='Lớp chưa được xếp lịch',
                    class_id=class_id
                ))
        
        return violations


# ⭐ MAIN VALIDATION FUNCTION
def validate_all_constraints(
    schedules: List[Dict],
    classes_data: List[Dict],
    rooms_data: Dict[str, List[str]],
    assignments_data: List[Dict]
) -> Dict:
    """
    Kiểm tra TẤT CẢ hard constraints
    ⭐ Function dùng chung cho tất cả validation
    
    Returns:
        {
            'feasible': bool,
            'violations': List[ConstraintViolation],
            'violations_by_type': Dict[str, int],
            'violations_by_class': Dict[str, List[ConstraintViolation]]
        }
    """
    all_violations = []
    
    # Build helper maps
    class_map = {c['id']: c for c in classes_data}
    assignments_map = {}
    for a in assignments_data:
        malop = a.get('MaLop')
        magv = a.get('MaGV')
        if malop and magv:
            assignments_map[malop] = magv
    
    # Calculate class types using SQL logic
    class_types = {}
    for c in classes_data:
        class_id = c.get('id')
        if class_id:
            class_types[class_id] = ConstraintChecker._calculate_class_type(c)
    room_types = {}
    for room in rooms_data.get('LT', []):
        room_types[room] = 'LT'
    for room in rooms_data.get('TH', []):
        room_types[room] = 'TH'
    
    class_sessions = {c['id']: c.get('sessions', c.get('SoCaTuan', 1)) for c in classes_data}
    class_sizes = {c['id']: c.get('size', c.get('SoLuongSV', 0)) for c in classes_data}
    
    # Build room capacities map (need to pass from caller)
    room_capacities = {}
    if 'room_capacities' in rooms_data:
        room_capacities = rooms_data['room_capacities']
    
    # Run all checks
    all_violations.extend(
        ConstraintChecker.check_teacher_conflicts(schedules, assignments_map)
    )
    all_violations.extend(
        ConstraintChecker.check_room_conflicts(schedules)
    )
    all_violations.extend(
        ConstraintChecker.check_room_type_mismatch(schedules, class_types, room_types)
    )
    all_violations.extend(
        ConstraintChecker.check_room_capacity(schedules, class_sizes, room_capacities)
    )
    all_violations.extend(
        ConstraintChecker.check_sunday_classes(schedules)
    )
    all_violations.extend(
        ConstraintChecker.check_session_requirements(schedules, class_sessions)
    )
    all_violations.extend(
        ConstraintChecker.check_missing_classes(schedules, list(class_map.keys()))
    )
    
    # Aggregate results
    violations_by_type = defaultdict(int)
    violations_by_class = defaultdict(list)
    
    for v in all_violations:
        violations_by_type[v.constraint_code] += 1
        violations_by_class[v.class_id].append(v)
    
    return {
        'feasible': len(all_violations) == 0,
        'total_violations': len(all_violations),
        'violations': all_violations,
        'violations_by_type': dict(violations_by_type),
        'violations_by_class': dict(violations_by_class),
        'violated_classes_count': len(violations_by_class)
    }
