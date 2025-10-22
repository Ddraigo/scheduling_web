"""
BATCH SCHEDULING với LLM
Chia 216 lớp thành 8-10 batches, AI xếp từng batch
"""

import logging
from typing import List, Dict, Set, Tuple
import json

logger = logging.getLogger(__name__)


class BatchScheduler:
    """Xếp lịch theo batches nhỏ sử dụng LLM"""
    
    def __init__(self, ai_instance, batch_size: int = 25):
        self.ai = ai_instance
        self.batch_size = batch_size
        self.used_slots: Set[Tuple[str, str, str]] = set()  # (TimeSlotID, MaPhong, MaGV)
        
        # 🔴 FIX: Global tracking for all batches (SHARED STATE)
        self.teacher_schedule: Dict[str, List[str]] = {}  # {'GV001': ['Thu2-Ca1', 'Thu3-Ca2'], ...}
        self.room_schedule: Dict[str, List[str]] = {}     # {'C201': ['Thu2-Ca1', 'Thu2-Ca2'], ...}
    
    def generate_schedule_with_batching(
        self, 
        classes: List[Dict],
        rooms: Dict[str, List[str]],  # {'LyThuyet': [...], 'ThucHanh': [...]}
        timeslots: List[str],
        max_retries: int = 2
    ) -> Dict:
        """
        Xếp lịch theo batches
        
        Args:
            classes: Danh sách 216 lớp
            rooms: Dict phòng học {'LyThuyet': [...], 'ThucHanh': [...]}
            timeslots: Danh sách TimeSlotID
            max_retries: Số lần thử lại nếu batch fail
            
        Returns:
            {'schedule': [...], 'metadata': {...}}
        """
        logger.info(f"🔄 Bắt đầu batch scheduling: {len(classes)} lớp, batch_size={self.batch_size}")
        
        all_schedules = []
        num_batches = (len(classes) + self.batch_size - 1) // self.batch_size
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(classes))
            batch_classes = classes[start_idx:end_idx]
            
            logger.info(f"📦 Batch {batch_idx + 1}/{num_batches}: Xếp {len(batch_classes)} lớp...")
            
            # Thử xếp batch này
            batch_success = False
            for retry in range(max_retries):
                try:
                    batch_schedules = self._schedule_batch(
                        batch_classes, rooms, timeslots, batch_idx + 1
                    )
                    
                    if batch_schedules and len(batch_schedules) >= len(batch_classes) * 0.5:
                        all_schedules.extend(batch_schedules)
                        batch_success = True
                        logger.info(f"✅ Batch {batch_idx + 1} thành công: {len(batch_schedules)} schedules")
                        break
                    else:
                        logger.warning(f"⚠️ Batch {batch_idx + 1} không đủ schedules, retry {retry + 1}/{max_retries}")
                        
                except Exception as e:
                    logger.error(f"❌ Batch {batch_idx + 1} lỗi: {e}, retry {retry + 1}/{max_retries}")
            
            if not batch_success:
                logger.error(f"❌ Batch {batch_idx + 1} FAILED sau {max_retries} lần thử!")
                return {
                    'schedule': [],
                    'error': f'Batch {batch_idx + 1} failed',
                    'partial_schedules': all_schedules
                }
        
        logger.info(f"🎉 Hoàn thành batch scheduling: {len(all_schedules)} schedules")
        
        return {
            'schedule': all_schedules,
            'metadata': {
                'method': 'batch_scheduling',
                'num_batches': num_batches,
                'batch_size': self.batch_size,
                'total_classes': len(classes),
                'total_schedules': len(all_schedules)
            }
        }
    
    def _schedule_batch(
        self,
        batch_classes: List[Dict],
        rooms: Dict[str, List[str]],
        all_timeslots: List[str],
        batch_number: int
    ) -> List[Dict]:
        """Xếp lịch cho 1 batch"""
        
        # Lọc ra slots CHƯA dùng
        available_timeslots = [
            slot for slot in all_timeslots
            if not self._is_slot_heavily_used(slot)
        ]
        
        # 🔴 FIX: Tạo prompt với SHARED TEACHER/ROOM CONTEXT
        prompt = self._create_batch_prompt(
            batch_classes, rooms, available_timeslots, batch_number
        )
        
        logger.info(f"🤖 Gửi batch {batch_number} ({len(prompt)} chars) tới AI...")
        logger.info(f"📊 Shared state: {len(self.teacher_schedule)} GVs already scheduled, {len(self.room_schedule)} rooms occupied")
        
        # Gọi AI
        result = self.ai.generate_schedule_json(prompt)
        
        if 'schedule' not in result:
            return []
        
        batch_schedules = result['schedule']
        
        # Validate & update BOTH local and global tracking
        valid_schedules = []
        for schedule in batch_schedules:
            if self._validate_schedule_entry(schedule, rooms, all_timeslots):
                # Đánh dấu slot đã dùng (format mới: class, room, slot)
                self.used_slots.add((
                    schedule['slot'],      # TimeSlotID
                    schedule['room'],      # MaPhong
                    schedule['class']      # MaLop
                ))
                
                # 🔴 FIX: Update GLOBAL TRACKING
                # Lấy teacher từ batch_classes (dựa trên class ID)
                teacher_id = None
                for cls in batch_classes:
                    if cls['id'] == schedule['class']:
                        teacher_id = cls['teacher']
                        break
                
                if teacher_id:
                    if teacher_id not in self.teacher_schedule:
                        self.teacher_schedule[teacher_id] = []
                    self.teacher_schedule[teacher_id].append(schedule['slot'])
                
                # Track room
                if schedule['room'] not in self.room_schedule:
                    self.room_schedule[schedule['room']] = []
                self.room_schedule[schedule['room']].append(schedule['slot'])
                
                valid_schedules.append(schedule)
            else:
                logger.warning(f"⚠️ Schedule không hợp lệ: {schedule}")
        
        return valid_schedules
    
    def _is_slot_heavily_used(self, timeslot: str) -> bool:
        """Kiểm tra slot đã dùng quá nhiều chưa"""
        # Đếm số lần slot này đã dùng
        count = sum(1 for (ts, _, _) in self.used_slots if ts == timeslot)
        # Nếu >80% phòng đã dùng → coi như heavily used
        return count > 120  # 146 phòng × 0.8
    
    def _create_batch_prompt(
        self,
        batch_classes: List[Dict],
        rooms: Dict[str, List[str]],
        timeslots: List[str],
        batch_number: int
    ) -> str:
        """Tạo prompt cho 1 batch - WITH SHARED CONTEXT"""
        
        # Lấy phòng chưa dùng nhiều (keys: 'LT' và 'TH' từ context)
        ly_thuyet_rooms = rooms.get('LT', rooms.get('LyThuyet', []))[:50]
        thuc_hanh_rooms = rooms.get('TH', rooms.get('ThucHanh', []))[:50]
        
        # 🔴 FIX: Add SHARED STATE to prompt
        already_scheduled_str = ""
        if self.teacher_schedule or self.room_schedule:
            already_scheduled_str = """

🔴 CRITICAL - ALREADY SCHEDULED IN PREVIOUS BATCHES:

TEACHERS ALREADY ASSIGNED (DO NOT ASSIGN SAME SLOT):
"""
            for gv_id, slots in sorted(self.teacher_schedule.items()):
                if len(slots) > 0:
                    already_scheduled_str += f"  {gv_id}: {slots}\n"
            
            already_scheduled_str += """
ROOMS ALREADY OCCUPIED (DO NOT USE SAME SLOT):
"""
            for room_id, slots in sorted(self.room_schedule.items()):
                if len(slots) > 0:
                    already_scheduled_str += f"  {room_id}: {slots}\n"
        
        prompt = f"""BATCH {batch_number} - SCHEDULE {len(batch_classes)} CLASSES

AVAILABLE RESOURCES:

LyThuyet Rooms ({len(ly_thuyet_rooms)}): {ly_thuyet_rooms}
ThucHanh Rooms ({len(thuc_hanh_rooms)}): {thuc_hanh_rooms}
TimeSlots ({len(timeslots)}): {timeslots}

CLASSES TO SCHEDULE ({len(batch_classes)} classes):
{json.dumps(batch_classes, ensure_ascii=False, indent=2)}{already_scheduled_str}

🔴 HARD CONSTRAINTS FOR THIS BATCH:
1. MUST NOT schedule a teacher in an already-used timeslot
2. MUST NOT use a room in an already-used timeslot
3. MUST NOT create duplicate assignments
4. Room type MUST match class type (LT/TH)
5. Room capacity MUST fit class size
6. Each class gets exactly 1 assignment

OUTPUT: JSON with {len(batch_classes)} schedules
{{
  "schedule": [
    {{"class": "LOP-xxx", "room": "Dxxx", "slot": "ThuX-CaY"}}
  ]
}}"""
        
        return prompt
    
    def _validate_schedule_entry(
        self,
        schedule: Dict,
        rooms: Dict[str, List[str]],
        timeslots: List[str]
    ) -> bool:
        """Validate 1 schedule entry - CHỈ 3 FIELDS: class, room, slot"""
        
        required_keys = ['class', 'room', 'slot']
        
        # Kiểm tra keys
        for key in required_keys:
            if key not in schedule:
                return False
        
        # Kiểm tra TimeSlotID hợp lệ
        if schedule['slot'] not in timeslots:
            return False
        
        # Kiểm tra MaPhong hợp lệ (support both 'LT'/'TH' and 'LyThuyet'/'ThucHanh')
        all_rooms = rooms.get('LT', rooms.get('LyThuyet', [])) + rooms.get('TH', rooms.get('ThucHanh', []))
        if schedule['room'] not in all_rooms:
            return False
        
        # Không cần check conflict vì AI đã handle
        return True

