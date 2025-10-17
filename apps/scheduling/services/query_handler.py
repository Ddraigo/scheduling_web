"""
Query Handler - Xử lý các query phân tích và kiểm tra xung đột
Migrated from src/scheduling/query_handler.py
"""

import logging
from typing import Dict, List, Optional
from collections import defaultdict
from tabulate import tabulate

logger = logging.getLogger(__name__)


class QueryHandler:
    """Xử lý query và phân tích dữ liệu thời khóa biểu"""
    
    def __init__(self):
        pass
    
    def get_specific_data(self, query: str, connection=None) -> str:
        """
        Execute custom SQL query và format output
        
        Args:
            query: SQL query string
            connection: Database connection (optional, uses Django if not provided)
            
        Returns:
            Formatted string output with table
        """
        try:
            if connection is None:
                # Use Django ORM raw query
                from django.db import connection as django_conn
                connection = django_conn
            
            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
            
            if not rows:
                return "Không có dữ liệu."
            
            # Format as table
            table = tabulate(rows, headers=columns, tablefmt='grid')
            return f"Kết quả truy vấn:\n{table}\n\nTổng: {len(rows)} dòng"
        
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return f"Lỗi khi thực thi query: {str(e)}"
    
    def get_schedule_conflicts(self, ma_dot: str) -> str:
        """
        Kiểm tra xung đột trong thời khóa biểu
        Tìm các trường hợp giảng viên hoặc phòng bị trùng slot
        
        Args:
            ma_dot: Mã đợt xếp lịch
            
        Returns:
            Formatted conflict report
        """
        from ..models import ThoiKhoaBieu
        
        try:
            schedules = ThoiKhoaBieu.objects.filter(
                dot_xep__ma_dot=ma_dot
            ).select_related(
                'lop_mon_hoc',
                'phong_hoc',
                'time_slot',
                'phan_cong__giang_vien'
            ).order_by('time_slot__ma_time_slot')
            
            if not schedules.exists():
                return f"Không tìm thấy thời khóa biểu cho đợt {ma_dot}"
            
            # Check teacher conflicts
            teacher_conflicts = self._find_teacher_conflicts(schedules)
            
            # Check room conflicts
            room_conflicts = self._find_room_conflicts(schedules)
            
            # Format output
            output = []
            output.append(f"=== KIỂM TRA XUNG ĐỘT - ĐỢT {ma_dot} ===\n")
            
            # Teacher conflicts
            if teacher_conflicts:
                output.append(f"🔴 XUNG ĐỘT GIẢNG VIÊN ({len(teacher_conflicts)} trường hợp):")
                for conflict in teacher_conflicts[:20]:  # Show top 20
                    output.append(
                        f"  - GV {conflict['teacher']}: "
                        f"Slot {conflict['slot']} - "
                        f"Lớp {', '.join(conflict['classes'])}"
                    )
                if len(teacher_conflicts) > 20:
                    output.append(f"  ... và {len(teacher_conflicts) - 20} xung đột khác")
            else:
                output.append("✅ Không có xung đột giảng viên")
            
            output.append("")
            
            # Room conflicts
            if room_conflicts:
                output.append(f"🔴 XUNG ĐỘT PHÒNG HỌC ({len(room_conflicts)} trường hợp):")
                for conflict in room_conflicts[:20]:
                    output.append(
                        f"  - Phòng {conflict['room']}: "
                        f"Slot {conflict['slot']} - "
                        f"Lớp {', '.join(conflict['classes'])}"
                    )
                if len(room_conflicts) > 20:
                    output.append(f"  ... và {len(room_conflicts) - 20} xung đột khác")
            else:
                output.append("✅ Không có xung đột phòng học")
            
            # Summary
            total_conflicts = len(teacher_conflicts) + len(room_conflicts)
            output.append(f"\n📊 TỔNG KẾT: {total_conflicts} xung đột")
            
            return "\n".join(output)
        
        except Exception as e:
            logger.error(f"Error checking conflicts: {e}")
            return f"Lỗi khi kiểm tra xung đột: {str(e)}"
    
    def _find_teacher_conflicts(self, schedules) -> List[Dict]:
        """Tìm xung đột giảng viên"""
        teacher_slots = defaultdict(lambda: defaultdict(list))
        
        for tkb in schedules:
            if not tkb.phan_cong:
                continue
            
            teacher = tkb.phan_cong.giang_vien.ma_gv
            slot = tkb.time_slot.ma_time_slot
            class_id = tkb.lop_mon_hoc.ma_lop
            
            teacher_slots[teacher][slot].append(class_id)
        
        conflicts = []
        for teacher, slots in teacher_slots.items():
            for slot, classes in slots.items():
                if len(classes) > 1:
                    conflicts.append({
                        'teacher': teacher,
                        'slot': slot,
                        'classes': classes,
                        'count': len(classes)
                    })
        
        return sorted(conflicts, key=lambda x: x['count'], reverse=True)
    
    def _find_room_conflicts(self, schedules) -> List[Dict]:
        """Tìm xung đột phòng học"""
        room_slots = defaultdict(lambda: defaultdict(list))
        
        for tkb in schedules:
            room = tkb.phong_hoc.ma_phong
            slot = tkb.time_slot.ma_time_slot
            class_id = tkb.lop_mon_hoc.ma_lop
            
            room_slots[room][slot].append(class_id)
        
        conflicts = []
        for room, slots in room_slots.items():
            for slot, classes in slots.items():
                if len(classes) > 1:
                    conflicts.append({
                        'room': room,
                        'slot': slot,
                        'classes': classes,
                        'count': len(classes)
                    })
        
        return sorted(conflicts, key=lambda x: x['count'], reverse=True)
    
    def get_teacher_availability(self, ma_gv: str, ma_dot: str) -> str:
        """
        Xem lịch dạy và nguyện vọng của giảng viên
        
        Args:
            ma_gv: Mã giảng viên
            ma_dot: Mã đợt xếp lịch
            
        Returns:
            Formatted teacher schedule
        """
        from ..models import ThoiKhoaBieu, GiangVien
        
        try:
            # Get teacher info
            try:
                teacher = GiangVien.objects.get(ma_gv=ma_gv)
            except GiangVien.DoesNotExist:
                return f"Không tìm thấy giảng viên {ma_gv}"
            
            # Get schedule
            schedules = ThoiKhoaBieu.objects.filter(
                phan_cong__giang_vien__ma_gv=ma_gv,
                dot_xep__ma_dot=ma_dot
            ).select_related(
                'lop_mon_hoc__mon_hoc',
                'phong_hoc',
                'time_slot'
            ).order_by('time_slot__ma_time_slot')
            
            output = []
            output.append(f"=== LỊCH GIẢNG VIÊN - {ma_dot} ===")
            output.append(f"Giảng viên: {teacher.ten_gv} ({ma_gv})")
            output.append(f"Email: {teacher.email or 'N/A'}")
            output.append("")
            
            if schedules.exists():
                # Build table
                table_data = []
                for tkb in schedules:
                    table_data.append([
                        tkb.time_slot.ma_time_slot,
                        tkb.lop_mon_hoc.ma_lop,
                        tkb.lop_mon_hoc.mon_hoc.ten_mon if tkb.lop_mon_hoc.mon_hoc else 'N/A',
                        tkb.phong_hoc.ma_phong,
                        tkb.lop_mon_hoc.si_so
                    ])
                
                table = tabulate(
                    table_data,
                    headers=['Slot', 'Lớp', 'Môn học', 'Phòng', 'Sĩ số'],
                    tablefmt='grid'
                )
                output.append(table)
                output.append(f"\nTổng: {len(table_data)} lớp")
            else:
                output.append("Chưa có lịch dạy trong đợt này.")
            
            return "\n".join(output)
        
        except Exception as e:
            logger.error(f"Error getting teacher availability: {e}")
            return f"Lỗi: {str(e)}"
    
    def get_room_utilization(self, ma_dot: str) -> str:
        """
        Phân tích mức độ sử dụng phòng học
        
        Args:
            ma_dot: Mã đợt xếp lịch
            
        Returns:
            Room utilization report
        """
        from ..models import ThoiKhoaBieu, PhongHoc, TimeSlot
        
        try:
            # Get total slots
            total_slots = TimeSlot.objects.count()
            if total_slots == 0:
                return "Chưa có time slots trong hệ thống"
            
            # Get all rooms
            rooms = PhongHoc.objects.all()
            
            # Get schedules
            schedules = ThoiKhoaBieu.objects.filter(
                dot_xep__ma_dot=ma_dot
            ).select_related('phong_hoc')
            
            # Calculate utilization
            room_usage = defaultdict(set)
            for tkb in schedules:
                room = tkb.phong_hoc.ma_phong
                slot = tkb.time_slot.ma_time_slot
                room_usage[room].add(slot)
            
            # Build table
            table_data = []
            for room in rooms:
                ma_phong = room.ma_phong
                used_slots = len(room_usage[ma_phong])
                util_rate = (used_slots / total_slots * 100) if total_slots > 0 else 0
                
                table_data.append([
                    ma_phong,
                    room.loai_phong or 'N/A',
                    room.suc_chua,
                    used_slots,
                    total_slots,
                    f"{util_rate:.1f}%"
                ])
            
            # Sort by utilization
            table_data.sort(key=lambda x: float(x[5].replace('%', '')), reverse=True)
            
            table = tabulate(
                table_data,
                headers=['Phòng', 'Loại', 'Sức chứa', 'Đã dùng', 'Tổng slots', 'Tỷ lệ'],
                tablefmt='grid'
            )
            
            # Summary
            total_rooms = len(rooms)
            total_used_slots = sum(len(slots) for slots in room_usage.values())
            total_available_slots = total_rooms * total_slots
            overall_util = (total_used_slots / total_available_slots * 100) if total_available_slots > 0 else 0
            
            output = []
            output.append(f"=== MỨC ĐỘ SỬ DỤNG PHÒNG HỌC - ĐỢT {ma_dot} ===\n")
            output.append(table)
            output.append(f"\n📊 TỔNG KẾT:")
            output.append(f"  - Tổng phòng: {total_rooms}")
            output.append(f"  - Tổng slots: {total_slots}")
            output.append(f"  - Slots đã dùng: {total_used_slots}/{total_available_slots}")
            output.append(f"  - Tỷ lệ sử dụng: {overall_util:.1f}%")
            
            return "\n".join(output)
        
        except Exception as e:
            logger.error(f"Error calculating room utilization: {e}")
            return f"Lỗi: {str(e)}"
    
    def get_class_distribution(self, ma_dot: str) -> str:
        """
        Phân tích phân bố lớp học theo giảng viên và bộ môn
        
        Args:
            ma_dot: Mã đợt xếp lịch
            
        Returns:
            Distribution report
        """
        from ..models import PhanCong
        from django.db.models import Count
        
        try:
            # By teacher
            teacher_dist = PhanCong.objects.filter(
                dot_xep__ma_dot=ma_dot
            ).values(
                'giang_vien__ma_gv',
                'giang_vien__ten_gv'
            ).annotate(
                so_lop=Count('lop_mon_hoc')
            ).order_by('-so_lop')
            
            output = []
            output.append(f"=== PHÂN BỐ LỚP HỌC - ĐỢT {ma_dot} ===\n")
            
            if teacher_dist:
                output.append("📚 THEO GIẢNG VIÊN:")
                table_data = [
                    [t['giang_vien__ma_gv'], t['giang_vien__ten_gv'], t['so_lop']]
                    for t in teacher_dist
                ]
                table = tabulate(
                    table_data,
                    headers=['Mã GV', 'Tên', 'Số lớp'],
                    tablefmt='grid'
                )
                output.append(table)
            
            # By department
            dept_dist = PhanCong.objects.filter(
                dot_xep__ma_dot=ma_dot
            ).values(
                'giang_vien__bo_mon__ma_bo_mon',
                'giang_vien__bo_mon__ten_bo_mon'
            ).annotate(
                so_lop=Count('lop_mon_hoc')
            ).order_by('-so_lop')
            
            if dept_dist:
                output.append("\n📊 THEO BỘ MÔN:")
                table_data = [
                    [d['giang_vien__bo_mon__ma_bo_mon'], d['giang_vien__bo_mon__ten_bo_mon'], d['so_lop']]
                    for d in dept_dist
                    if d['giang_vien__bo_mon__ma_bo_mon']  # Filter None
                ]
                table = tabulate(
                    table_data,
                    headers=['Mã BM', 'Tên', 'Số lớp'],
                    tablefmt='grid'
                )
                output.append(table)
            
            return "\n".join(output)
        
        except Exception as e:
            logger.error(f"Error getting distribution: {e}")
            return f"Lỗi: {str(e)}"
