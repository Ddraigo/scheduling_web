"""
Post-processing schedule repair
- Fix HC-01 (teacher conflicts) by swapping slots
- Fix HC-05 (room type mismatch) by reassigning rooms
"""

import logging
from typing import List, Dict, Set, Tuple
import json

logger = logging.getLogger(__name__)


class ScheduleRepair:
    """Repair schedule violations"""
    
    def __init__(self):
        self.teacher_slots: Dict[str, Set[str]] = {}  # teacher -> set of slots
        self.room_slots: Dict[str, Set[str]] = {}      # room -> set of slots
    
    def repair_schedule(
        self,
        schedule: List[Dict],
        phan_cong_df,
        rooms_df,
        timeslots: List[str]
    ) -> Tuple[List[Dict], Dict]:
        """
        Repair schedule to fix HC violations
        
        Returns: (repaired_schedule, repair_stats)
        """
        
        logger.info("🔧 Starting schedule repair...")
        
        # Build maps
        class_teacher = dict(zip(phan_cong_df['MaLop'], phan_cong_df['MaGV']))
        class_type = dict(zip(phan_cong_df['MaLop'], phan_cong_df['LoaiPhong']))
        class_students = dict(zip(phan_cong_df['MaLop'], phan_cong_df['SoLuongSV']))
        
        room_capacity = dict(zip(rooms_df['MaPhong'], rooms_df['SucChua']))
        lt_rooms = set(rooms_df[rooms_df['LoaiPhong'].str.contains('thuyết|LT', case=False, na=False)]['MaPhong'])
        th_rooms = set(rooms_df[rooms_df['LoaiPhong'].str.contains('hành|TH', case=False, na=False)]['MaPhong'])
        
        repaired = []
        repairs_made = {'hc01_fixed': 0, 'hc05_fixed': 0, 'failed': 0}
        
        # Pass 1: Fix HC-05 (room type mismatch)
        logger.info("📌 Pass 1: Fix HC-05 (room type mismatch)...")
        for entry in schedule:
            class_id = entry['class']
            room = entry['room']
            slot = entry['slot']
            
            if class_id not in class_type:
                logger.warning(f"⚠️ Class {class_id} not in phan_cong!")
                repaired.append(entry)
                continue
            
            class_req_type = class_type[class_id]
            room_is_lt = room in lt_rooms
            room_is_th = room in th_rooms
            
            # HC-05 check: TH class in LT room
            if class_req_type == 'TH' and room_is_lt:
                logger.info(f"🔴 HC-05: {class_id} (TH) in LT room {room} → fixing...")
                
                # Find available TH room
                new_room = self._find_available_room(
                    class_id, slot, th_rooms, room_capacity, class_students
                )
                
                if new_room:
                    logger.info(f"✅ Fixed: {class_id} → {new_room}")
                    entry['room'] = new_room
                    repairs_made['hc05_fixed'] += 1
                    self._register_assignment(class_id, new_room, slot, class_teacher)
                else:
                    logger.warning(f"❌ Cannot fix HC-05 for {class_id} - no available TH room")
                    repairs_made['failed'] += 1
            
            repaired.append(entry)
        
        # Pass 2: Fix HC-01 (teacher conflicts)
        logger.info("📌 Pass 2: Fix HC-01 (teacher conflicts)...")
        
        # Build teacher->slots map
        teacher_slots = {}
        for entry in repaired:
            class_id = entry['class']
            slot = entry['slot']
            
            if class_id in class_teacher:
                teacher = class_teacher[class_id]
                if teacher not in teacher_slots:
                    teacher_slots[teacher] = []
                teacher_slots[teacher].append((class_id, slot, entry['room']))
        
        # Find conflicts
        repaired_pass2 = []
        for entry in repaired:
            class_id = entry['class']
            slot = entry['slot']
            room = entry['room']
            
            if class_id not in class_teacher:
                repaired_pass2.append(entry)
                continue
            
            teacher = class_teacher[class_id]
            
            # Check if teacher has multiple classes in same slot
            same_slot_count = sum(1 for cls, s, r in teacher_slots[teacher] if s == slot)
            
            if same_slot_count > 1:
                logger.info(f"🔴 HC-01: {teacher} teaches {same_slot_count} classes in {slot} → fixing...")
                
                # Find alternative slot
                new_slot = self._find_available_slot(
                    class_id, teacher, slot, timeslots, class_teacher, teacher_slots
                )
                
                if new_slot:
                    logger.info(f"✅ Fixed: {class_id} → {new_slot}")
                    entry['slot'] = new_slot
                    repairs_made['hc01_fixed'] += 1
                    teacher_slots[teacher] = [(c, s if c != class_id else new_slot, r) 
                                             for c, s, r in teacher_slots[teacher]]
                else:
                    logger.warning(f"❌ Cannot fix HC-01 for {class_id} - no available slot")
                    repairs_made['failed'] += 1
            
            repaired_pass2.append(entry)
        
        logger.info(f"🔧 Repair stats: {repairs_made}")
        return repaired_pass2, repairs_made
    
    def _find_available_room(
        self,
        class_id: str,
        slot: str,
        candidate_rooms: Set[str],
        room_capacity: Dict[str, int],
        class_students: Dict[str, int]
    ) -> str:
        """Find available room for class"""
        
        class_size = class_students.get(class_id, 40)
        
        for room in sorted(candidate_rooms):
            if room_capacity.get(room, 0) < class_size:
                continue
            
            # Check if room not already used in this slot
            if (room, slot) not in self.room_slots:
                return room
        
        return None
    
    def _find_available_slot(
        self,
        class_id: str,
        teacher: str,
        current_slot: str,
        all_timeslots: List[str],
        class_teacher: Dict[str, str],
        teacher_slots: Dict[str, List[Tuple]]
    ) -> str:
        """Find alternative slot for class to avoid teacher conflict"""
        
        used_slots = {s for c, s, r in teacher_slots.get(teacher, []) if c != class_id}
        
        for slot in all_timeslots:
            if slot not in used_slots and slot != current_slot:
                return slot
        
        return None
    
    def _register_assignment(
        self,
        class_id: str,
        room: str,
        slot: str,
        class_teacher: Dict[str, str]
    ):
        """Register assignment in tracking dicts"""
        
        if room not in self.room_slots:
            self.room_slots[room] = set()
        self.room_slots[room].add(slot)
        
        if class_id in class_teacher:
            teacher = class_teacher[class_id]
            if teacher not in self.teacher_slots:
                self.teacher_slots[teacher] = set()
            self.teacher_slots[teacher].add(slot)
