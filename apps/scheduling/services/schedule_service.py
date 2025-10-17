"""
Schedule Service - Main business logic for scheduling
Migrated from src/scheduling/
"""

from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
import logging
import json

from ..models import (
    DotXep, PhanCong, LopMonHoc, GiangVien, PhongHoc,
    TimeSlot, ThoiKhoaBieu
)
from .ai_service import SchedulingAIService

logger = logging.getLogger(__name__)


class ScheduleService:
    """Main service for schedule generation and management"""
    
    def __init__(self):
        self.ai_service = SchedulingAIService()
    
    def get_classes_for_period(self, ma_dot: str) -> List[Dict]:
        """
        Get all classes that need to be scheduled for a period
        
        Args:
            ma_dot: Scheduling period code
            
        Returns:
            List of class dictionaries with assignment info
        """
        try:
            assignments = PhanCong.objects.filter(
                dot_xep__ma_dot=ma_dot
            ).select_related(
                'lop_mon_hoc',
                'lop_mon_hoc__mon_hoc',
                'giang_vien'
            )
            
            classes = []
            for pc in assignments:
                lop = pc.lop_mon_hoc
                mon_hoc = lop.mon_hoc
                
                classes.append({
                    'ma_phan_cong': pc.ma_phan_cong,
                    'ma_lop': lop.ma_lop,
                    'ten_lop': lop.ten_lop,
                    'ma_gv': pc.giang_vien.ma_gv,
                    'ten_gv': pc.giang_vien.ten_gv,
                    'ma_mon_hoc': mon_hoc.ma_mon_hoc,
                    'ten_mon_hoc': mon_hoc.ten_mon_hoc,
                    'si_so': lop.si_so,
                    'loai_lop': lop.loai_lop or 'LT',
                    'so_tiet': mon_hoc.so_tiet_tong,
                })
            
            return classes
        
        except Exception as e:
            logger.error(f"Error getting classes for period {ma_dot}: {e}")
            return []
    
    def get_available_rooms(self, loai_phong: Optional[str] = None) -> List[Dict]:
        """
        Get available rooms
        
        Args:
            loai_phong: Filter by room type (LT/TH)
            
        Returns:
            List of room dictionaries
        """
        try:
            query = PhongHoc.objects.all()
            
            if loai_phong:
                query = query.filter(loai_phong=loai_phong)
            
            return [
                {
                    'ma_phong': r.ma_phong,
                    'ten_phong': r.ten_phong,
                    'suc_chua': r.suc_chua,
                    'loai_phong': r.loai_phong,
                    'toa_nha': r.toa_nha,
                }
                for r in query
            ]
        
        except Exception as e:
            logger.error(f"Error getting rooms: {e}")
            return []
    
    def get_available_timeslots(self) -> List[Dict]:
        """
        Get all available time slots
        
        Returns:
            List of timeslot dictionaries
        """
        try:
            timeslots = TimeSlot.objects.all().order_by('thu', 'tiet_bat_dau')
            
            return [
                {
                    'ma_time_slot': ts.ma_time_slot,
                    'thu': ts.thu,
                    'tiet_bat_dau': ts.tiet_bat_dau,
                    'so_tiet': ts.so_tiet,
                    'gio_bat_dau': ts.gio_bat_dau.strftime('%H:%M'),
                    'gio_ket_thuc': ts.gio_ket_thuc.strftime('%H:%M'),
                }
                for ts in timeslots
            ]
        
        except Exception as e:
            logger.error(f"Error getting timeslots: {e}")
            return []
    
    @transaction.atomic
    def generate_schedule(self, ma_dot: str, use_ai: bool = True) -> Dict[str, Any]:
        """
        Generate schedule for a scheduling period
        
        Args:
            ma_dot: Scheduling period code
            use_ai: Whether to use AI for optimization
            
        Returns:
            Dictionary with generation results
        """
        try:
            # Validate period exists
            dot_xep = DotXep.objects.get(ma_dot=ma_dot)
            
            # Get data
            classes = self.get_classes_for_period(ma_dot)
            rooms = self.get_available_rooms()
            timeslots = self.get_available_timeslots()
            
            if not classes:
                return {
                    'success': False,
                    'error': 'No classes to schedule'
                }
            
            logger.info(f"Generating schedule for {len(classes)} classes")
            
            # Prepare data for AI/algorithm
            scheduling_data = {
                'period': ma_dot,
                'classes': classes,
                'rooms': rooms,
                'timeslots': timeslots,
            }
            
            if use_ai:
                # Use AI service
                result = self.ai_service.generate_schedule_with_ai(scheduling_data)
                
                if 'error' in result:
                    return {
                        'success': False,
                        'error': result['error']
                    }
                
                assignments = result.get('assignments', [])
            else:
                # Use greedy algorithm (fallback)
                assignments = self._greedy_schedule(scheduling_data)
            
            # Save to database
            saved_count = self._save_schedule_to_db(ma_dot, assignments)
            
            # Update period status
            dot_xep.trang_thai = 'SCHEDULED'
            dot_xep.save()
            
            return {
                'success': True,
                'period': ma_dot,
                'total_classes': len(classes),
                'scheduled_count': saved_count,
                'method': 'AI' if use_ai else 'Greedy',
            }
        
        except DotXep.DoesNotExist:
            return {
                'success': False,
                'error': f'Period {ma_dot} not found'
            }
        except Exception as e:
            logger.error(f"Error generating schedule: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _greedy_schedule(self, data: Dict) -> List[Dict]:
        """
        Simple greedy scheduling algorithm (fallback)
        
        Args:
            data: Scheduling data
            
        Returns:
            List of assignments
        """
        classes = data['classes']
        rooms = data['rooms']
        timeslots = data['timeslots']
        
        assignments = []
        used_slots = {}  # (room_id, timeslot_id) -> class_id
        
        for cls in classes:
            # Find suitable room
            suitable_rooms = [
                r for r in rooms
                if r['suc_chua'] >= cls['si_so'] and
                r['loai_phong'] == cls['loai_lop']
            ]
            
            if not suitable_rooms:
                suitable_rooms = rooms  # Fallback to any room
            
            # Try to assign to a slot
            assigned = False
            for room in suitable_rooms:
                for slot in timeslots:
                    key = (room['ma_phong'], slot['ma_time_slot'])
                    
                    if key not in used_slots:
                        # Found available slot
                        assignments.append({
                            'class_id': cls['ma_lop'],
                            'room_id': room['ma_phong'],
                            'timeslot_id': slot['ma_time_slot'],
                        })
                        used_slots[key] = cls['ma_lop']
                        assigned = True
                        break
                
                if assigned:
                    break
        
        return assignments
    
    def _save_schedule_to_db(self, ma_dot: str, assignments: List[Dict]) -> int:
        """
        Save schedule assignments to database
        
        Args:
            ma_dot: Period code
            assignments: List of assignments
            
        Returns:
            Number of saved records
        """
        try:
            # Clear existing schedule
            ThoiKhoaBieu.objects.filter(dot_xep__ma_dot=ma_dot).delete()
            
            dot_xep = DotXep.objects.get(ma_dot=ma_dot)
            saved_count = 0
            
            for assignment in assignments:
                try:
                    lop = LopMonHoc.objects.get(ma_lop=assignment['class_id'])
                    phong = PhongHoc.objects.get(ma_phong=assignment['room_id'])
                    timeslot = TimeSlot.objects.get(ma_time_slot=assignment['timeslot_id'])
                    
                    # Get corresponding assignment
                    phan_cong = PhanCong.objects.filter(
                        dot_xep=dot_xep,
                        lop_mon_hoc=lop
                    ).first()
                    
                    ThoiKhoaBieu.objects.create(
                        dot_xep=dot_xep,
                        phan_cong=phan_cong,
                        lop_mon_hoc=lop,
                        phong_hoc=phong,
                        time_slot=timeslot,
                        tuan_hoc=assignment.get('week', 1)
                    )
                    saved_count += 1
                
                except Exception as e:
                    logger.warning(f"Error saving assignment: {e}")
                    continue
            
            return saved_count
        
        except Exception as e:
            logger.error(f"Error saving schedule: {e}")
            return 0
