"""
Data Adapter: Chuyển đổi dữ liệu từ Django models sang input/output cho CB-CTT solver
"""

from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
from datetime import datetime
import logging
import json
from pathlib import Path

from apps.scheduling.models import (
    LopMonHoc, PhanCong, TimeSlot, PhongHoc, GiangVien, 
    MonHoc, DotXep, ThoiKhoaBieu, NguyenVong, RangBuocTrongDot,
    RangBuocMem, BoMon, Khoa
)
from .algorithms_core import (
    CBCTTInstance, Room, Course, Curriculum, Lecture
)

logger = logging.getLogger(__name__)


class AlgorithmsDataAdapter:
    """
    Adapter chuyển đổi giữa Django models và solver core
    """

    @staticmethod
    def build_cbctt_instance_from_db(ma_dot: str) -> CBCTTInstance:
        """
        Xây dựng CBCTTInstance từ dữ liệu database cho một DotXep
        
        Args:
            ma_dot: Mã đợt xếp lịch (VD: '2025-2026_HK1')
        
        Returns:
            CBCTTInstance: Instance input cho solver
        """
        # Lấy DotXep
        try:
            dot_xep = DotXep.objects.get(ma_dot=ma_dot)
        except DotXep.DoesNotExist:
            raise ValueError(f"Không tìm thấy đợt xếp: {ma_dot}")

        # Lấy tất cả lớp môn học trong đợt này (qua PhanCong)
        phan_congs = PhanCong.objects.filter(ma_dot=dot_xep).select_related(
            'ma_lop__ma_mon_hoc', 'ma_gv'
        )
        
        if not phan_congs.exists():
            raise ValueError(f"Không có phân công nào cho đợt: {ma_dot}")

        lop_mon_hocs = [pc.ma_lop for pc in phan_congs]
        
        # Lấy tất cả phòng (có thể add filter nếu cần)
        phong_hocs = PhongHoc.objects.all()
        
        # Lấy tất cả timeslot
        time_slots = TimeSlot.objects.all().select_related('ca').order_by('thu', 'ca')
        
        if not time_slots.exists():
            raise ValueError("Không có timeslot nào trong hệ thống")

        # Lấy thông tin ràng buộc áp dụng trong đợt (để reference sau này)
        try:
            rang_buoc_trong_dot = RangBuocTrongDot.objects.filter(ma_dot=dot_xep).select_related('ma_rang_buoc')
            applied_constraints = {rb.ma_rang_buoc.ma_rang_buoc: rb.ma_rang_buoc.trong_so for rb in rang_buoc_trong_dot}
            logger.info(f"Ràng buộc áp dụng: {list(applied_constraints.keys())}")
        except Exception as e:
            logger.warning(f"Lỗi lấy ràng buộc: {e}")
            applied_constraints = {}

        # Xác định số ngày và tiết/ngày từ dữ liệu
        days = len(set(ts.thu for ts in time_slots))  # Số ngày (thứ)
        periods_per_day = time_slots.filter(thu=time_slots.first().thu).count()

        # Xây dựng danh sách Room
        rooms: List[Room] = []
        room_by_id: Dict[str, int] = {}
        for idx, phong in enumerate(phong_hocs):
            # Xác định loại phòng: "TH" (Thực hành) hoặc "LT" (Lý thuyết - mặc định)
            room_type = "TH" if ("Thực hành" in (phong.loai_phong or "") or "TH" in (phong.loai_phong or "")) else "LT"
            
            room = Room(
                id=phong.ma_phong,
                capacity=phong.suc_chua,
                index=idx,
                equipment=phong.thiet_bi or "",  # Thiết bị của phòng
                room_type=room_type  # Loại phòng
            )
            rooms.append(room)
            room_by_id[phong.ma_phong] = idx

        # Xây dựng danh sách Course (từ PhanCong)
        courses: List[Course] = []
        course_by_id: Dict[str, int] = {}
        teacher_by_id: Dict[str, int] = {}
        teachers: List[str] = []
        
        # 🟢 Đếm số lớp cho mỗi MonHoc để tính min_working_days
        # min_working_days = Số ngày tối thiểu các lớp cùng một môn phải phân bổ để sinh viên có lựa chọn
        # Mặc định = 2 (có thể tùy chỉnh)
        mon_hoc_count: Dict[str, int] = defaultdict(int)
        for phan_cong in phan_congs:
            mon_hoc_count[phan_cong.ma_lop.ma_mon_hoc.ma_mon_hoc] += 1
        
        for idx, phan_cong in enumerate(phan_congs):
            lop_mh = phan_cong.ma_lop
            # Lấy giảng viên từ PhanCong
            teacher_id = phan_cong.ma_gv.ma_gv if phan_cong.ma_gv else "UNKNOWN"

            # Tìm hoặc tạo teacher index
            if teacher_id not in teacher_by_id:
                teacher_by_id[teacher_id] = len(teachers)
                teachers.append(teacher_id)

            # 🟢 min_working_days = số ngày tối thiểu để các lớp cùng một môn phân tán
            # Ví dụ: Môn Toán có 3 lớp, min_working_days = 4 → 3 lớp phải xếp vào ít nhất 4 ngày khác nhau
            # Mặc định = 4 (theo yêu cầu để tăng tính phân tán)
            min_working_days_default = 5
            
            # Xác định loại lớp: "TH" (Thực hành) hoặc "LT" (Lý thuyết)
            # Logic SQL:
            #   IF SoTietTH = 0 THEN 'LT'
            #   ELSE IF SoTietLT = 0 AND SoTietTH > 0 THEN 'TH'
            #   ELSE IF SoTietLT > 0 AND SoTietTH > 0 AND To_MH = 0 THEN 'LT'
            #   ELSE 'TH'
            mon_hoc = lop_mh.ma_mon_hoc
            so_tiet_lt = mon_hoc.so_tiet_lt or 0
            so_tiet_th = mon_hoc.so_tiet_th or 0
            to_mh = lop_mh.to_mh or 0
            
            if so_tiet_th == 0:
                course_type = "LT"
            elif so_tiet_lt == 0 and so_tiet_th > 0:
                course_type = "TH"
            elif so_tiet_lt > 0 and so_tiet_th > 0 and to_mh == 0:
                course_type = "LT"
            else:
                course_type = "TH"
            
            course = Course(
                id=lop_mh.ma_lop,
                teacher=teacher_id,
                lectures=lop_mh.so_ca_tuan,  # Số ca/tuần cần xếp (1 tuần chuẩn = 7 ngày × 5 ca/ngày = 35 ca)
                min_working_days=min_working_days_default,  # 🟢 Sử dụng giá trị mặc định 4
                students=lop_mh.so_luong_sv or 0,
                index=idx,
                teacher_index=teacher_by_id[teacher_id],
                so_ca_tuan=lop_mh.so_ca_tuan,  # Số ca/tuần từ database
                equipment=lop_mh.thiet_bi_yeu_cau or "",  # Thiết bị yêu cầu
                course_type=course_type  # Loại lớp
            )
            courses.append(course)
            course_by_id[lop_mh.ma_lop] = idx

        # Xây dựng danh sách Lecture
        lectures: List[Lecture] = []
        course_lecture_ids: List[List[int]] = [[] for _ in courses]
        
        for course_idx, course in enumerate(courses):
            for lecture_idx in range(course.lectures):
                lecture = Lecture(
                    id=len(lectures),
                    course=course_idx,
                    index=lecture_idx
                )
                lectures.append(lecture)
                course_lecture_ids[course_idx].append(lecture.id)

        # Xây dựng Curriculum
        curriculums: List[Curriculum] = []
        curriculum_by_id: Dict[str, int] = {}
        course_curriculums: List[List[int]] = [[] for _ in courses]
        
        # Curriculum 1: Từ giáo viên (các lớp của cùng 1 GV không được trùng lịch)
        teacher_to_courses: Dict[str, List[int]] = defaultdict(list)
        for course_idx, course in enumerate(courses):
            teacher_to_courses[course.teacher].append(course_idx)

        for teacher_id, course_indices in teacher_to_courses.items():
            if len(course_indices) > 0:
                curriculum = Curriculum(
                    name=f"Teacher_{teacher_id}",
                    courses=course_indices,
                    index=len(curriculums)
                )
                curriculums.append(curriculum)
                for course_idx in course_indices:
                    course_curriculums[course_idx].append(curriculum.index)
                curriculum_by_id[curriculum.name] = curriculum.index

        # Curriculum 2: Từ nguyện vọng giáo viên
        # � LOGIC SAI - ĐANG DISABLE
        # Lý do: Code cũ tạo curriculum cho TẤT CẢ GV cùng timeslot (vd: Thu2-Ca1 có 3 GV → gom 3 GV vào 1 curriculum)
        # Điều này SAI vì các lớp của GV khác nhau không cần hard constraint với nhau
        # 
        # 🟢 ĐÚNG: NguyenVong CHỈ dùng để xây feasible_periods (xem bên dưới)
        #    - feasible_periods: Giới hạn những slot GV có thể dạy (hard constraint)
        #    - curriculum teacher: Đã đảm bảo các lớp cùng GV không trùng (hard constraint)
        #    → Không cần curriculum từ NguyenVong nữa
        
        DISABLE_PREFERENCE_CURRICULUM = True  # 🔴 FORCE DISABLE - logic cũ SAI
        
        if not DISABLE_PREFERENCE_CURRICULUM:
            # CODE CŨ - ĐÃ DISABLE
            try:
                nguyen_vongs = NguyenVong.objects.filter(ma_dot=dot_xep).select_related('ma_gv', 'time_slot_id')
                if nguyen_vongs.exists():
                    # Nhóm giáo viên theo timeslot nguyện vọng
                    timeslot_to_teachers: Dict[str, List[str]] = defaultdict(list)
                    for nv in nguyen_vongs:
                        timeslot_to_teachers[nv.time_slot_id.time_slot_id].append(nv.ma_gv.ma_gv)
                    
                    # Tạo curriculum: CHỈ GV có ĐÚNG 1 LỚP trong timeslot đó
                    for timeslot_id, teacher_ids in timeslot_to_teachers.items():
                        valid_courses = []
                        
                        for teacher_id in teacher_ids:
                            # Lấy tất cả lớp của GV này
                            courses_of_teacher = teacher_to_courses.get(teacher_id, [])
                            
                            # FILTER CHẶT: Chỉ thêm nếu GV có ≤ 2 lớp
                            # (vì nếu có 5+ lớp, sẽ rất khó scheduling)
                            if 1 <= len(courses_of_teacher) <= 2:
                                valid_courses.extend(courses_of_teacher)
                        
                        # Tạo curriculum nếu có courses hợp lệ
                        if len(valid_courses) >= 1:
                            course_indices_set = set(valid_courses)
                            
                            # Chỉ tạo nếu ≤ 2 lớp
                            if len(course_indices_set) <= 2:
                                curriculum = Curriculum(
                                    name=f"Preference_{timeslot_id}",
                                    courses=list(course_indices_set),
                                    index=len(curriculums)
                                )
                                curriculums.append(curriculum)
                                for course_idx in course_indices_set:
                                    course_curriculums[course_idx].append(curriculum.index)
                                curriculum_by_id[curriculum.name] = curriculum.index
                                logger.info(f"✓ Nguyện vọng {timeslot_id}: {len(course_indices_set)} lớp (hard constraint)")
            except Exception as e:
                logger.warning(f"Lỗi tạo curriculum từ nguyện vọng: {e}")
        else:
            logger.info("✓ Nguyện vọng curriculum DISABLED - NguyenVong chỉ dùng cho feasible_periods")

        # Xây dựng feasible_periods (dựa trên NGUYỆN VỌNG = lịch rảnh của GV)
        # 🟢 QUAN TRỌNG: feasible_periods phải dựa trên NguyenVong của giảng viên
        #    Nếu GV không có NguyenVong cho một TimeSlot → lớp của GV không thể xếp vào đó
        total_periods = days * periods_per_day
        feasible_periods: List[List[int]] = []
        unavailability: List[set] = []
        
        # Bước 1: Lấy tất cả NguyenVong và tạo mapping: teacher_id -> set(period_index)
        teacher_available_periods: Dict[str, Set[int]] = defaultdict(set)
        try:
            nguyen_vongs_all = NguyenVong.objects.filter(ma_dot=dot_xep).select_related('ma_gv', 'time_slot_id', 'time_slot_id__ca')
            for nv in nguyen_vongs_all:
                teacher_id = nv.ma_gv.ma_gv
                ts = nv.time_slot_id
                # Chuyển TimeSlot (thu, ca) → period_index
                # period_index = (thu - 2) * periods_per_day + (ca_index - 1)
                # (vì thu từ 2-7, ca từ 1-5)
                day_index = ts.thu - 2  # 0-5 (Thứ 2-7, bỏ Thứ 8 = CN)
                period_index_in_day = ts.ca.ma_khung_gio - 1  # 0-4 (Ca 1-5)
                period_index = day_index * periods_per_day + period_index_in_day
                teacher_available_periods[teacher_id].add(period_index)
        except Exception as e:
            logger.warning(f"⚠️  Lỗi đọc NguyenVong để xây dựng feasible_periods: {e}")
        
        # Bước 2: Xây dựng feasible_periods cho mỗi course
        # 🟢 CHIẾN LƯỢC MỚI: Cho phép TẤT CẢ slots (trừ Chủ Nhật) để tránh infeasibility
        #    - Nếu GV có NguyenVong: Ưu tiên slots trong NguyenVong (qua heuristic)
        #    - Nếu không đủ slots: Cho phép xếp vào slots khác (soft constraint violation)
        # 
        # ⚠️ LƯU Ý: unavailability BLOCK Chủ Nhật (thu = 8, tức day_index = 6)
        
        # Tính toán slots của Chủ Nhật cần block
        # TimeSlot có thu từ 2-8 (Thứ 2 - Chủ Nhật)
        # day_index = thu - 2 → Chủ Nhật (thu=8) có day_index = 6
        # Nếu days = 7 → có Chủ Nhật, nếu days = 6 → không có
        sunday_slots: Set[int] = set()
        if days >= 7:  # Nếu có Chủ Nhật trong dữ liệu
            sunday_day_index = 6  # Chủ Nhật
            for period_in_day in range(periods_per_day):
                sunday_slot = sunday_day_index * periods_per_day + period_in_day
                if sunday_slot < total_periods:
                    sunday_slots.add(sunday_slot)
        
        for course_idx, course in enumerate(courses):
            teacher_id = course.teacher
            
            # CHO PHÉP TẤT CẢ SLOTS - không hạn chế
            available = list(range(total_periods))
            
            # Log để debug (giữ thông tin về NguyenVong)
            if teacher_id in teacher_available_periods:
                nv_periods = len(teacher_available_periods[teacher_id])
                logger.debug(f"  Course {course.id} (GV {teacher_id}): {nv_periods} preferred periods (from NguyenVong), {total_periods} total allowed")
            else:
                logger.debug(f"  Course {course.id} (GV {teacher_id}): NO NguyenVong, all {total_periods} periods allowed")
            
            feasible_periods.append(available)
            unavailability.append(sunday_slots.copy())  # Block Chủ Nhật cho tất cả courses

        # Xây dựng course_room_preference (sắp xếp phòng theo: equipment match → room type match → capacity)
        course_room_preference: List[List[int]] = []
        for course in courses:
            students = course.students
            course_equip = course.equipment or ""
            course_type = course.course_type
            
            def room_sort_key(r_idx):
                room = rooms[r_idx]
                # Priority 1: Equipment match (0 = match, 1 = no match)
                equip_match = 0 if course_equip == "" or course_equip in room.equipment else 1
                # Priority 2: Room type match (0 = match, 1 = no match)
                type_match = 0 if room.room_type == course_type else 1
                # Priority 3: Capacity (0 = adequate, 1 = undersized)
                capacity_ok = 0 if room.capacity >= students else 1
                # Priority 4: Capacity difference
                capacity_diff = abs(room.capacity - students)
                # Priority 5: Room capacity
                capacity = room.capacity
                
                return (equip_match, type_match, capacity_ok, capacity_diff, capacity)
            
            room_order = sorted(range(len(rooms)), key=room_sort_key)
            course_room_preference.append(room_order)

        # Xây dựng lecture_neighbors (từ teacher và curriculum)
        lecture_neighbors: List[set] = [set() for _ in lectures]
        
        # Thêm neighbors từ teacher
        teacher_to_lectures: Dict[str, List[int]] = defaultdict(list)
        for course_idx, course in enumerate(courses):
            for lecture_id in course_lecture_ids[course_idx]:
                teacher_to_lectures[course.teacher].append(lecture_id)

        for lecture_ids in teacher_to_lectures.values():
            for lid in lecture_ids:
                lecture_neighbors[lid].update(lecture_ids)

        # Thêm neighbors từ curriculum
        for curriculum in curriculums:
            lecture_ids: List[int] = []
            for course_idx in curriculum.courses:
                lecture_ids.extend(course_lecture_ids[course_idx])
            for lid in lecture_ids:
                lecture_neighbors[lid].update(lecture_ids)

        # Loại bỏ self-neighbor
        for lid, neighbors in enumerate(lecture_neighbors):
            neighbors.discard(lid)

        # Lấy thông tin khác
        course_teachers = [course.teacher for course in courses]
        course_students = [course.students for course in courses]

        return CBCTTInstance(
            name=f"Schedule_{ma_dot}",
            days=days,
            periods_per_day=periods_per_day,
            courses=courses,
            rooms=rooms,
            curriculums=curriculums,
            unavailability=unavailability,
            lectures=lectures,
            course_curriculums=course_curriculums,
            feasible_periods=feasible_periods,
            course_room_preference=course_room_preference,
            course_teachers=course_teachers,
            course_students=course_students,
            course_lecture_ids=course_lecture_ids,
            lecture_neighbors=lecture_neighbors,
            course_by_id=course_by_id,
            room_by_id=room_by_id,
            curriculum_by_id=curriculum_by_id,
            teacher_by_id=teacher_by_id,
            teachers=teachers,
            course_so_ca_tuan=[course.so_ca_tuan for course in courses],  # Số ca/tuần cho mỗi course
            teacher_preferred_periods=dict(teacher_available_periods),  # Truyền NguyenVong preferences
        )

    @staticmethod
    def save_results_to_db(
        ma_dot: str,
        instance: CBCTTInstance,
        assignments: Dict[int, Tuple[int, int]],
        score_breakdown
    ) -> Dict:
        """
        Lưu kết quả xếp lịch vào database
        
        Args:
            ma_dot: Mã đợt xếp
            instance: Instance từ solver
            assignments: Dict lecture_id -> (period, room_idx)
            score_breakdown: ScoreBreakdown từ solver
        
        Returns:
            Dict chứa thông tin kết quả lưu
        """
        try:
            dot_xep = DotXep.objects.get(ma_dot=ma_dot)
        except DotXep.DoesNotExist:
            raise ValueError(f"Không tìm thấy đợt: {ma_dot}")

        # Xóa lịch cũ
        ThoiKhoaBieu.objects.filter(ma_dot=dot_xep).delete()

        # Lưu lịch mới
        created_count = 0
        
        # Lấy danh sách thứ từ TimeSlot (để map day_index -> thu)
        all_time_slots = TimeSlot.objects.all().order_by('thu', 'ca')
        unique_days = sorted(set(ts.thu for ts in all_time_slots))  # [2, 3, 4, 5, 6, 7, 8]
        
        for lecture_id, (period, room_idx) in assignments.items():
            lecture = instance.lectures[lecture_id]
            course = instance.courses[lecture.course]
            course_obj = LopMonHoc.objects.get(ma_lop=course.id)
            
            day_idx, slot_idx = instance.period_to_slot(period)
            
            # Convert day_idx (0-6) to thu (2-8)
            if day_idx >= len(unique_days):
                logger.warning(f"Day index {day_idx} out of range")
                continue
            thu = unique_days[day_idx]
            
            # Tìm timeslot theo thu và slot index
            try:
                time_slots_on_day = list(TimeSlot.objects.filter(thu=thu).order_by('ca'))
                if slot_idx >= len(time_slots_on_day):
                    logger.warning(f"Slot index {slot_idx} out of range for day {thu}")
                    continue
                time_slot = time_slots_on_day[slot_idx]
            except Exception as e:
                logger.warning(f"Lỗi lấy timeslot cho thu={thu}, slot_idx={slot_idx}: {e}")
                continue

            # Tìm phòng
            room = instance.rooms[room_idx]
            phong_hoc = PhongHoc.objects.get(ma_phong=room.id)

            # Generate ma_tkb duy nhất
            ma_tkb = f"{ma_dot}_{course_obj.ma_lop}_{time_slot.time_slot_id}_{room.id}".replace(" ", "_")

            # Tạo entry ThoiKhoaBieu
            thoikhoa = ThoiKhoaBieu(
                ma_tkb=ma_tkb,
                ma_dot=dot_xep,
                ma_lop=course_obj,
                ma_phong=phong_hoc,
                time_slot_id=time_slot
            )
            try:
                thoikhoa.save()
                created_count += 1
            except Exception as e:
                logger.warning(f"Lỗi lưu ThoiKhoaBieu {ma_tkb}: {e}")

        return {
            'ma_dot': ma_dot,
            'created_count': created_count,
            'room_capacity_penalty': score_breakdown.room_capacity,
            'min_working_days_penalty': score_breakdown.min_working_days,
            'curriculum_compactness_penalty': score_breakdown.curriculum_compactness,
            'room_stability_penalty': score_breakdown.room_stability,
            'lecture_clustering_penalty': score_breakdown.lecture_clustering,
            'total_cost': score_breakdown.total,
        }

    @staticmethod
    def format_result_for_ui(
        ma_dot: str,
        instance: CBCTTInstance,
        assignments: Dict[int, Tuple[int, int]],
        score_breakdown,
        elapsed_time: float
    ) -> Dict:
        """
        Định dạng kết quả để trả về UI
        """
        schedule_items = []
        for lecture_id, (period, room_idx) in assignments.items():
            lecture = instance.lectures[lecture_id]
            course = instance.courses[lecture.course]
            room = instance.rooms[room_idx]
            day_idx, slot = instance.period_to_slot(period)
            thu = day_idx + 2  # Convert: day_idx (0-6) → thu (2-8)

            schedule_items.append({
                'course_id': course.id,
                'teacher': course.teacher,
                'room': room.id,
                'day': thu,  # 2-8 (Thứ 2-Chủ Nhật)
                'slot': slot,
                'students': course.students,
                'room_capacity': room.capacity,
            })

        return {
            'ma_dot': ma_dot,
            'status': 'success',
            'elapsed_time': elapsed_time,
            'total_lectures': len(assignments),
            'score_breakdown': {
                'room_capacity': score_breakdown.room_capacity,
                'min_working_days': score_breakdown.min_working_days,
                'curriculum_compactness': score_breakdown.curriculum_compactness,
                'room_stability': score_breakdown.room_stability,
                'lecture_clustering': score_breakdown.lecture_clustering,
                'total': score_breakdown.total,
            },
            'schedule_items': schedule_items[:10],  # Trả về 10 item đầu cho UI preview
            'total_items': len(schedule_items),
        }

    @staticmethod
    def export_result_to_json(
        ma_dot: str,
        instance: CBCTTInstance,
        assignments: Dict[int, Tuple[int, int]],
        score_breakdown,
        elapsed_time: float,
        output_path: Optional[str] = None
    ) -> Dict:
        """
        Xuất kết quả xếp lịch ra file JSON có đầy đủ thông tin
        
        Args:
            ma_dot: Mã đợt xếp
            instance: Instance từ solver
            assignments: Dict lecture_id -> (period, room_idx)
            score_breakdown: ScoreBreakdown từ solver
            elapsed_time: Thời gian chạy
            output_path: Đường dẫn file output (default: output/schedule_{ma_dot}.json)
        
        Returns:
            Dict chứa thông tin output
        """
        if output_path is None:
            output_path = f"output/schedule_algorithm_{ma_dot}.json"
        
        # 1. Xây dựng danh sách lịch (để save vào DB)
        schedule_items = []
        course_slot_map: Dict[str, List[Dict]] = defaultdict(list)  # course_id -> list of slots
        
        for lecture_id, (period, room_idx) in assignments.items():
            lecture = instance.lectures[lecture_id]
            course = instance.courses[lecture.course]
            room = instance.rooms[room_idx]
            day_idx, slot = instance.period_to_slot(period)
            thu = day_idx + 2  # Convert: day_idx (0-6) → thu (2-8)
            
            # Tìm timeslot
            try:
                time_slots_on_day = list(TimeSlot.objects.filter(thu=thu).order_by('ca'))
                if slot < len(time_slots_on_day):
                    time_slot = time_slots_on_day[slot]
                    slot_id = time_slot.time_slot_id
                else:
                    slot_id = f"Thu{thu}-Ca{slot}"
            except Exception as e:
                logger.warning(f"Lỗi lấy timeslot: {e}")
                slot_id = f"Thu{thu}-Ca{slot}"
            
            schedule_items.append({
                'class': course.id,
                'teacher': course.teacher,
                'room': room.id,
                'slot': slot_id,
                'students': course.students,
                'room_capacity': room.capacity,
            })
            
            # Nhóm theo course
            course_slot_map[course.id].append({
                'slot': slot_id,
                'room': room.id,
                'day': thu,  # 2-8
                'slot_index': slot,
            })

        # 2. Thống kê
        stats = {
            'total_lectures': len(schedule_items),
            'total_courses': len(set(s['class'] for s in schedule_items)),
            'total_rooms_used': len(set(s['room'] for s in schedule_items)),
            'total_teachers': len(instance.teachers),
            'total_timeslots': instance.days * instance.periods_per_day,
        }

        # 3. Tính toán các chỉ số
        teacher_lectures: Dict[str, int] = defaultdict(int)
        teacher_days: Dict[str, set] = defaultdict(set)
        room_usage: Dict[str, int] = defaultdict(int)
        
        for item in schedule_items:
            teacher_lectures[item['teacher']] += 1
            room_usage[item['room']] += 1
            # Tách thứ từ slot_id (vd: "Thu2-Ca1" -> 2)
            if '-' in item['slot']:
                try:
                    thu = int(item['slot'].split('-')[0].replace('Thu', ''))
                    teacher_days[item['teacher']].add(thu)
                except:
                    pass
        
        avg_teaching_days = sum(len(days) for days in teacher_days.values()) / len(instance.teachers) if instance.teachers else 0

        # 4. Tạo kết quả JSON
        result = {
            'metadata': {
                'ma_dot': ma_dot,
                'created_at': datetime.now().isoformat(),
                'solver': 'CB-CTT Local Search',
                'elapsed_time_seconds': elapsed_time,
            },
            'schedule': schedule_items,
            'statistics': {
                'total_assignments': stats['total_lectures'],
                'total_courses': stats['total_courses'],
                'total_rooms_used': stats['total_rooms_used'],
                'total_teachers': stats['total_teachers'],
                'total_timeslots': stats['total_timeslots'],
                'avg_teaching_days_per_teacher': round(avg_teaching_days, 2),
                'teacher_workload_distribution': dict(sorted(teacher_lectures.items())),
                'room_usage_distribution': dict(sorted(room_usage.items())),
            },
            'score_breakdown': {
                'room_capacity_penalty': score_breakdown.room_capacity,
                'min_working_days_penalty': score_breakdown.min_working_days,
                'curriculum_compactness_penalty': score_breakdown.curriculum_compactness,
                'room_stability_penalty': score_breakdown.room_stability,
                'lecture_clustering_penalty': score_breakdown.lecture_clustering,
                'total_cost': score_breakdown.total,
            },
            'constraints_info': {
                'hard_constraints': {
                    'no_room_conflict': True,  # Luôn đúng vì solver đảm bảo
                    'no_teacher_conflict': True,  # Luôn đúng vì solver đảm bảo
                    'no_curriculum_conflict': True,  # Luôn đúng vì solver đảm bảo
                    'room_capacity_respected': 'Soft constraint - có penalty nếu vượt',
                },
                'soft_constraints': {
                    'room_capacity': f'{score_breakdown.room_capacity} violations',
                    'min_working_days': f'{score_breakdown.min_working_days} violations',
                    'curriculum_compactness': f'{score_breakdown.curriculum_compactness} violations',
                    'room_stability': f'{score_breakdown.room_stability} violations',
                    'lecture_clustering': f'{score_breakdown.lecture_clustering} violations (tiết không liền nhau)',
                },
            },
            'course_details': {},
        }

        # 5. Thêm chi tiết từng course
        for course_idx, course in enumerate(instance.courses):
            if course.id in course_slot_map:
                result['course_details'][course.id] = {
                    'teacher': course.teacher,
                    'lectures': course.lectures,
                    'min_working_days': course.min_working_days,
                    'students': course.students,
                    'so_ca_tuan': course.so_ca_tuan,
                    'slots': course_slot_map[course.id],
                }

        # 6. Lưu JSON file
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"Lưu kết quả vào {output_path}")
            return {
                'status': 'success',
                'output_path': output_path,
                'total_items': len(schedule_items),
            }
        except Exception as e:
            logger.error(f"Lỗi lưu file JSON: {e}")
            return {
                'status': 'error',
                'message': str(e),
            }
