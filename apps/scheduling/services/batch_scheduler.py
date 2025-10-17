"""
Batch Scheduler - Xử lý xếp lịch theo batch sử dụng LLM
Migrated from src/scheduling/batch_scheduler.py
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

from .ai_service import SchedulingAIService

logger = logging.getLogger(__name__)


class BatchScheduler:
    """
    Xếp lịch theo batch cho số lượng lớn classes
    Chia nhỏ classes thành các batch và xử lý từng batch với AI
    """
    
    def __init__(self, batch_size: int = 25):
        """
        Args:
            batch_size: Số lượng classes trong mỗi batch
        """
        self.batch_size = batch_size
        self.ai_service = SchedulingAIService()
        self.used_slots = defaultdict(set)  # Track used slots per room
        self.teacher_slots = defaultdict(set)  # Track used slots per teacher
    
    def reset(self):
        """Reset tracking data"""
        self.used_slots.clear()
        self.teacher_slots.clear()
    
    def generate_schedule_with_batching(
        self,
        classes_data: List[Dict],
        rooms_data: Dict[str, List[str]],
        assignments_data: List[Dict],
        preferences_data: Optional[List[Dict]] = None,
        ma_dot: Optional[str] = None,
        max_retries: int = 2
    ) -> Dict:
        """
        Generate schedule using batch processing with AI
        
        Args:
            classes_data: Danh sách lớp học
            rooms_data: {"LT": [...], "TH": [...]}
            assignments_data: Phân công giảng viên
            preferences_data: Nguyện vọng giảng viên
            ma_dot: Mã đợt xếp lịch
            max_retries: Số lần retry khi batch fail
            
        Returns:
            Dict chứa schedule và metadata
        """
        self.reset()
        
        # Build assignments map
        assignments_map = {
            a['MaLop']: a['MaGV']
            for a in assignments_data
            if a.get('MaLop') and a.get('MaGV')
        }
        
        # Build preferences map
        preferences_map = defaultdict(set)
        if preferences_data:
            for pref in preferences_data:
                ma_gv = pref.get('MaGV')
                slot = pref.get('TimeSlotID')
                if ma_gv and slot:
                    preferences_map[ma_gv].add(slot)
        
        # Split into batches
        batches = self._split_into_batches(classes_data)
        logger.info(f"Split {len(classes_data)} classes into {len(batches)} batches")
        
        # Process each batch
        all_schedules = []
        batch_results = []
        
        for batch_idx, batch_classes in enumerate(batches):
            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} ({len(batch_classes)} classes)")
            
            # Schedule this batch
            batch_result = self._schedule_batch(
                batch_classes=batch_classes,
                rooms_data=rooms_data,
                assignments_map=assignments_map,
                preferences_map=preferences_map,
                batch_idx=batch_idx,
                max_retries=max_retries
            )
            
            if batch_result['success']:
                batch_schedules = batch_result['schedules']
                all_schedules.extend(batch_schedules)
                
                # Update used slots
                for sched in batch_schedules:
                    room = sched['room']
                    slot = sched['slot']
                    self.used_slots[room].add(slot)
                    
                    # Update teacher slots
                    class_id = sched['class']
                    if class_id in assignments_map:
                        teacher = assignments_map[class_id]
                        self.teacher_slots[teacher].add(slot)
                
                batch_results.append({
                    'batch': batch_idx + 1,
                    'classes': len(batch_classes),
                    'scheduled': len(batch_schedules),
                    'success': True
                })
            else:
                logger.warning(f"Batch {batch_idx + 1} failed: {batch_result.get('error')}")
                batch_results.append({
                    'batch': batch_idx + 1,
                    'classes': len(batch_classes),
                    'scheduled': 0,
                    'success': False,
                    'error': batch_result.get('error')
                })
        
        # Summary
        total_scheduled = len(all_schedules)
        success_rate = (total_scheduled / len(classes_data) * 100) if classes_data else 0
        
        return {
            'schedule': all_schedules,
            'total_classes': len(classes_data),
            'total_scheduled': total_scheduled,
            'success_rate': round(success_rate, 2),
            'batches': len(batches),
            'batch_results': batch_results,
            'ma_dot': ma_dot
        }
    
    def _split_into_batches(self, classes_data: List[Dict]) -> List[List[Dict]]:
        """
        Chia classes thành các batch
        Ưu tiên nhóm classes cùng loại (LT/TH) trong một batch
        """
        # Separate by type
        lt_classes = [c for c in classes_data if c.get('type') == 'LT']
        th_classes = [c for c in classes_data if c.get('type') == 'TH']
        
        batches = []
        
        # Batch LT classes
        for i in range(0, len(lt_classes), self.batch_size):
            batches.append(lt_classes[i:i + self.batch_size])
        
        # Batch TH classes
        for i in range(0, len(th_classes), self.batch_size):
            batches.append(th_classes[i:i + self.batch_size])
        
        return batches
    
    def _schedule_batch(
        self,
        batch_classes: List[Dict],
        rooms_data: Dict[str, List[str]],
        assignments_map: Dict[str, str],
        preferences_map: Dict[str, Set[str]],
        batch_idx: int,
        max_retries: int = 2
    ) -> Dict:
        """
        Schedule một batch với AI retry logic
        
        Returns:
            Dict với 'success', 'schedules', optional 'error'
        """
        # Build constraint context for this batch
        constraints = self._build_batch_constraints(
            batch_classes,
            assignments_map,
            preferences_map
        )
        
        # Try scheduling with AI
        for attempt in range(max_retries + 1):
            try:
                result = self.ai_service.generate_schedule_with_ai(
                    classes_data=batch_classes,
                    rooms_data=rooms_data,
                    assignments_data=[
                        {'MaLop': c['id'], 'MaGV': assignments_map.get(c['id'])}
                        for c in batch_classes
                        if c['id'] in assignments_map
                    ],
                    preferences_data=None,  # Handled in constraints
                    additional_context=constraints
                )
                
                schedules = result.get('schedule', [])
                
                if schedules:
                    # Filter out slots that conflict with previous batches
                    valid_schedules = self._filter_conflicts(
                        schedules,
                        assignments_map
                    )
                    
                    if len(valid_schedules) >= len(batch_classes) * 0.8:  # Accept if 80%+ scheduled
                        return {
                            'success': True,
                            'schedules': valid_schedules,
                            'attempt': attempt + 1
                        }
                    else:
                        logger.warning(f"Batch {batch_idx + 1} attempt {attempt + 1}: "
                                     f"Only {len(valid_schedules)}/{len(batch_classes)} valid")
            
            except Exception as e:
                logger.error(f"Batch {batch_idx + 1} attempt {attempt + 1} error: {e}")
        
        # All retries failed
        return {
            'success': False,
            'schedules': [],
            'error': 'Max retries exceeded'
        }
    
    def _build_batch_constraints(
        self,
        batch_classes: List[Dict],
        assignments_map: Dict[str, str],
        preferences_map: Dict[str, Set[str]]
    ) -> str:
        """Build constraint description for AI context"""
        constraints = []
        
        # Used slots constraint
        if self.used_slots:
            constraints.append("Các slot đã được sử dụng (TRÁNH):")
            for room, slots in list(self.used_slots.items())[:5]:  # Show sample
                constraints.append(f"  - Phòng {room}: {sorted(list(slots))[:10]}")
        
        # Teacher conflicts
        if self.teacher_slots:
            constraints.append("\nGiảng viên đã có lịch (TRÁNH):")
            for teacher, slots in list(self.teacher_slots.items())[:5]:
                constraints.append(f"  - GV {teacher}: {sorted(list(slots))[:10]}")
        
        # Preferences for this batch
        batch_teachers = {assignments_map.get(c['id']) for c in batch_classes}
        batch_preferences = {
            teacher: slots
            for teacher, slots in preferences_map.items()
            if teacher in batch_teachers
        }
        
        if batch_preferences:
            constraints.append("\nNguyện vọng giảng viên (ƯU TIÊN):")
            for teacher, slots in list(batch_preferences.items())[:5]:
                constraints.append(f"  - GV {teacher}: {sorted(list(slots))[:10]}")
        
        return "\n".join(constraints) if constraints else ""
    
    def _filter_conflicts(
        self,
        schedules: List[Dict],
        assignments_map: Dict[str, str]
    ) -> List[Dict]:
        """Lọc bỏ schedules có conflict với previous batches"""
        valid = []
        
        for sched in schedules:
            room = sched['room']
            slot = sched['slot']
            class_id = sched['class']
            
            # Check room conflict
            if slot in self.used_slots[room]:
                logger.debug(f"Room conflict: {room} - {slot}")
                continue
            
            # Check teacher conflict
            teacher = assignments_map.get(class_id)
            if teacher and slot in self.teacher_slots[teacher]:
                logger.debug(f"Teacher conflict: {teacher} - {slot}")
                continue
            
            valid.append(sched)
        
        return valid
    
    def generate_schedule_django(
        self,
        ma_dot: str,
        batch_size: Optional[int] = None
    ) -> Dict:
        """
        Generate schedule using Django ORM
        
        Args:
            ma_dot: Mã đợt xếp lịch
            batch_size: Override default batch size
            
        Returns:
            Schedule generation result
        """
        from ..models import LopMonHoc, PhongHoc, PhanCong
        
        if batch_size:
            self.batch_size = batch_size
        
        try:
            # Get classes
            classes = LopMonHoc.objects.filter(
                dot_xep__ma_dot=ma_dot
            ).select_related('mon_hoc')
            
            classes_data = [
                {
                    'id': c.ma_lop,
                    'type': c.loai_lop or 'LT',
                    'size': c.si_so,
                    'name': c.mon_hoc.ten_mon if c.mon_hoc else c.ma_lop
                }
                for c in classes
            ]
            
            # Get rooms
            rooms_data = {
                'LT': list(PhongHoc.objects.filter(loai_phong='LT').values_list('ma_phong', flat=True)),
                'TH': list(PhongHoc.objects.filter(loai_phong='TH').values_list('ma_phong', flat=True)),
            }
            
            # Get assignments
            assignments = PhanCong.objects.filter(dot_xep__ma_dot=ma_dot)
            assignments_data = [
                {
                    'MaLop': pc.lop_mon_hoc.ma_lop,
                    'MaGV': pc.giang_vien.ma_gv
                }
                for pc in assignments
            ]
            
            # Generate
            return self.generate_schedule_with_batching(
                classes_data=classes_data,
                rooms_data=rooms_data,
                assignments_data=assignments_data,
                ma_dot=ma_dot
            )
        
        except Exception as e:
            logger.error(f"Error in batch scheduling: {e}")
            return {
                'schedule': [],
                'total_classes': 0,
                'total_scheduled': 0,
                'success_rate': 0,
                'error': str(e)
            }
