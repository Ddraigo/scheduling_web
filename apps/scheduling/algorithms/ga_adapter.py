"""
GA Adapter - Chuyển đổi dữ liệu SQL sang cấu trúc thuật toán GA
Sử dụng greedy_heuristic_ga_algorithm_sql.py (SQL-compatible version)
"""
import pandas as pd
import sys
import os
from typing import List, Set, Tuple, Dict

# ✅ Import từ SQL version (không có random data, không auto-run)
sys.path.insert(0, os.path.dirname(__file__))
from greedy_heuristic_ga_algorithm_sql import Teacher, Room, Course, GlobalConfig, idx, bitset_from_pairs


def parse_timeslot_id(timeslot_id: str) -> Tuple[int, int]:
    """
    Chuyển TimeSlotID từ SQL sang (day, slot)
    
    Examples:
        'Thu2-Ca1' → (0, 0)  # Thứ 2, Ca 1
        'Thu3-Ca2' → (1, 1)  # Thứ 3, Ca 2
        'Thu8-Ca1' → None    # Chủ nhật, bỏ qua
    
    Returns:
        (day, slot) hoặc None nếu là CN (Thu8)
    """
    try:
        parts = timeslot_id.split('-')
        thu_str = parts[0].replace('Thu', '')
        ca_str = parts[1].replace('Ca', '')
        
        thu = int(thu_str)
        ca = int(ca_str)
        
        # GA algorithm: DAYS=5 (Mon-Fri), SLOTS=4 (Ca1-4)
        # SQL: Thu2-8 (Mon-Sun), Ca1-5
        
        # Chủ nhật (Thu8) → Bỏ qua
        if thu == 8:
            return None
        
        # Thu2 → day=0, Thu3 → day=1, ..., Thu6 → day=4
        day = thu - 2
        
        # Ca1 → slot=0, Ca2 → slot=1, ..., Ca5 → slot=4
        slot = ca - 1
        
        # Validate
        if day < 0 or day >= GlobalConfig.DAYS:
            return None
        if slot < 0 or slot >= GlobalConfig.SLOTS:
            return None
        
        return (day, slot)
    except:
        return None


def sql_to_teachers(giang_vien_df: pd.DataFrame, nguyen_vong_df: pd.DataFrame, 
                   timeslots_df: pd.DataFrame, phan_cong_df: pd.DataFrame = None) -> List[Teacher]:
    """
    Chuyển đổi tb_GIANG_VIEN + tb_NGUYEN_VONG → List[Teacher]
    
    ⚠️ CHIẾN LƯỢC: HYBRID (HARD + SOFT)
    - Nếu GV có ĐỦ nguyện vọng (wishes >= số lớp được giao):
      → HARD: availability_bits = bitset của wishes (chỉ dạy vào slot đã đăng ký)
    - Nếu GV THIẾU nguyện vọng (wishes < số lớp được giao):
      → SOFT: availability_bits = tất cả slots, wishes làm gợi ý ưu tiên
    - Nếu GV không có nguyện vọng:
      → FULL: có sẵn tất cả slots, wishes rỗng
    
    Args:
        giang_vien_df: Bảng giảng viên (MaGV, TenGV, MaKhoa)
        nguyen_vong_df: Bảng nguyện vọng (MaGV, TimeSlotID, MaDot)
        timeslots_df: Bảng time slots (TimeSlotID, Thu, Ca)
        phan_cong_df: Bảng phân công (để đếm số lớp mỗi GV) - optional
    
    Returns:
        List[Teacher] cho GA algorithm
    """
    teachers = []
    
    # Tạo mapping MaGV → index
    gv_id_to_index = {row['MaGV']: idx for idx, row in giang_vien_df.iterrows()}
    
    # Đếm số lớp mỗi GV được phân công
    gv_class_count = {}
    if phan_cong_df is not None and not phan_cong_df.empty:
        # Strip whitespace để tránh mismatch
        phan_cong_df['MaGV'] = phan_cong_df['MaGV'].astype(str).str.strip()
        for ma_gv in giang_vien_df['MaGV']:
            ma_gv_clean = str(ma_gv).strip()
            count = len(phan_cong_df[phan_cong_df['MaGV'] == ma_gv_clean])
            gv_class_count[ma_gv] = count
    
    # Stats
    gv_hard = 0      # Đủ nguyện vọng → Hard
    gv_soft = 0      # Thiếu nguyện vọng → Soft
    gv_full = 0      # Không có nguyện vọng → Full
    
    # Tạo all_slots để dùng cho fallback
    all_slots = set()
    for _, ts in timeslots_df.iterrows():
        parsed = parse_timeslot_id(ts['TimeSlotID'])
        if parsed:
            all_slots.add(parsed)
    
    for idx, (_, gv) in enumerate(giang_vien_df.iterrows()):
        ma_gv = gv['MaGV']
        
        # 1. Wishes: Lấy từ tb_NGUYEN_VONG
        wishes = set()
        gv_wishes = nguyen_vong_df[nguyen_vong_df['MaGV'] == ma_gv]
        
        # Debug: Đếm số nguyện vọng trước khi parse
        total_nv_records = len(gv_wishes)
        parsed_count = 0
        rejected_count = 0
        
        for _, nv in gv_wishes.iterrows():
            parsed = parse_timeslot_id(nv['TimeSlotID'])
            if parsed:
                wishes.add(parsed)
                parsed_count += 1
            else:
                rejected_count += 1
                # Debug: In ra nguyện vọng bị reject
                if rejected_count <= 3:  # Chỉ in 3 cái đầu
                    print(f"      🔍 DEBUG: {ma_gv} - NV bị reject: {nv['TimeSlotID']}")
        
        # 2. Đếm số lớp được giao
        num_classes = gv_class_count.get(ma_gv, 0)
        
        # 3. Quyết định chiến lược: HARD vs SOFT vs FULL
        if len(wishes) == 0:
            # FULL: Không có nguyện vọng → Có sẵn tất cả slots
            availability_bits = bitset_from_pairs(all_slots)
            gv_full += 1
            strategy = "FULL"
        elif len(wishes) >= num_classes:
            # HARD: Đủ nguyện vọng → CHỈ dạy vào slot đã đăng ký
            availability_bits = bitset_from_pairs(wishes)
            gv_hard += 1
            strategy = "HARD"
        else:
            # SOFT: Thiếu nguyện vọng → Có sẵn tất cả slots, wishes làm gợi ý
            availability_bits = bitset_from_pairs(all_slots)
            gv_soft += 1
            strategy = "SOFT"
            # Debug: In ra GV thiếu nguyện vọng
            print(f"   ⚠️  GV SOFT: {ma_gv} - {num_classes} lớp, {total_nv_records} NV trong SQL nhưng chỉ parse được {len(wishes)} (reject {rejected_count})")
        
        # 4. Department
        dept = str(gv.get('MaKhoa', f'DEPT_{idx % 3}'))
        
        teachers.append(Teacher(
            id=idx,
            name=str(ma_gv),  # Lưu MaGV để trace back
            dept=dept,
            availability_bits=availability_bits,
            wishes=wishes
        ))
    
    # Print stats
    print(f"📊 Teachers Strategy:")
    print(f"   ✅ {gv_hard} GV HARD (đủ nguyện vọng, chỉ dạy slot đã đăng ký)")
    print(f"   ⚠️  {gv_soft} GV SOFT (thiếu nguyện vọng, full slots + wishes gợi ý)")
    print(f"   📌 {gv_full} GV FULL (không có nguyện vọng, full slots)")
    
    return teachers


def sql_to_rooms(phong_hoc_df: pd.DataFrame) -> List[Room]:
    """
    Chuyển đổi tb_PHONG_HOC → List[Room]
    
    Args:
        phong_hoc_df: Bảng phòng học (MaPhong, TenPhong, SucChua, LoaiPhong, ThietBi)
    
    Returns:
        List[Room] cho GA algorithm
    """
    rooms = []
    
    for idx, (_, ph) in enumerate(phong_hoc_df.iterrows()):
        ma_phong = ph['MaPhong']
        
        # Lấy trực tiếp từ SQL - KHÔNG parse!
        loai_phong = str(ph.get('LoaiPhong', 'Lý thuyết'))  # Default = LT
        thiet_bi = str(ph.get('ThietBi', ''))  # Lưu nguyên string từ SQL
        
        rooms.append(Room(
            id=idx,
            name=str(ma_phong),
            capacity=int(ph['SucChua']),
            room_type=loai_phong,
            equipment=thiet_bi  # ✅ Lưu trực tiếp, không parse
        ))
    
    return rooms


def sql_to_courses(phan_cong_df: pd.DataFrame, lop_monhoc_df: pd.DataFrame, 
                  mon_hoc_df: pd.DataFrame, giang_vien_df: pd.DataFrame) -> Tuple[List[Course], Dict]:
    """
    Chuyển đổi tb_PHAN_CONG + tb_LOP_MONHOC + tb_MON_HOC → List[Course]
    
    Args:
        phan_cong_df: Bảng phân công (MaDot, MaLop, MaGV)
        lop_monhoc_df: Bảng lớp môn học (MaLop, MaMonHoc, SoLuongSV, SoCaTuan, ThietBiYeuCau)
        mon_hoc_df: Bảng môn học (MaMonHoc, TenMonHoc, SoTinChi, SoTietLT, SoTietTH)
        giang_vien_df: Bảng giảng viên (để mapping MaGV → index)
    
    Returns:
        (List[Course], mapping_dict) - mapping để trace back kết quả
    """
    courses = []
    mapping = {
        'course_id_to_info': {},  # {course_id: {'MaLop', 'MaGV', 'ca_idx', ...}}
        'gv_id_map': {},  # {MaGV: index}
    }
    
    # Tạo mapping MaGV → index
    for idx, (_, gv) in enumerate(giang_vien_df.iterrows()):
        mapping['gv_id_map'][gv['MaGV']] = idx
    
    course_id = 0
    
    for _, pc in phan_cong_df.iterrows():
        ma_lop = pc['MaLop']
        ma_gv = pc['MaGV']
        
        # Lấy thông tin lớp môn học
        lm_rows = lop_monhoc_df[lop_monhoc_df['MaLop'] == ma_lop]
        if lm_rows.empty:
            continue
        lm = lm_rows.iloc[0]
        
        # Lấy thông tin môn học
        mh_rows = mon_hoc_df[mon_hoc_df['MaMonHoc'] == lm['MaMonHoc']]
        if mh_rows.empty:
            continue
        mh = mh_rows.iloc[0]
        
        # 1. Duration: Tính số slot liên tiếp
        # GA: 1 slot = 1 tiết (thay vì 3 tiết như thực tế)
        # Nếu SoTietLT + SoTietTH <= 3 → duration=1 (1 ca)
        # Nếu > 3 → duration=2 (2 ca liên tiếp)
        total_tiet = mh['SoTietLT'] + mh['SoTietTH']
        duration = 1  # Mặc định 1 slot (1 ca)
        
        # 2. Equipment required: Lấy trực tiếp từ SQL - KHÔNG parse!
        thiet_bi_yeu_cau = str(lm.get('ThietBiYeuCau', ''))
        
        # 3. Room type required: ĐÚNG LOGIC
        # Lớp TH = Môn có SoTietTH > 0 VÀ To_MH > 0 (tổ thực hành)
        # Lớp LT = Tất cả trường hợp khác
        to_mh = lm.get('To_MH', 0)
        so_tiet_th = mh.get('SoTietTH', 0)
        
        if so_tiet_th > 0 and to_mh > 0:
            room_type_required = 'Thực hành'  # Tổ TH: CHỈ phòng TH
        else:
            room_type_required = 'Lý thuyết'  # Lớp LT chung: CHỈ phòng LT
        
        # 4. Candidate teachers: Chỉ GV được phân công
        gv_index = mapping['gv_id_map'].get(ma_gv)
        if gv_index is None:
            continue
        
        candidate_teachers = {gv_index}
        
        # 4. Department
        dept = str(lm.get('HeDaoTao', 'Unknown'))
        
        # 5. Mở rộng theo SoCaTuan (số ca/tuần)
        so_ca = int(lm.get('SoCaTuan', 1))
        
        for ca_idx in range(so_ca):
            # ✅ SỬA: Dùng format đặc biệt "MaLop::CaX" để parse dễ dàng
            course_name = f"{ma_lop}::Ca{ca_idx+1}"
            
            courses.append(Course(
                id=course_id,
                name=course_name,
                dept=dept,
                size=int(lm['SoLuongSV']),
                duration=duration,
                room_type_required=room_type_required,
                equipment_required=thiet_bi_yeu_cau,  # ✅ Lưu trực tiếp string
                candidate_teachers=candidate_teachers
            ))
            
            # Lưu mapping để trace back
            mapping['course_id_to_info'][course_id] = {
                'MaLop': ma_lop,
                'MaGV': ma_gv,
                'ca_idx': ca_idx,
                'TenMonHoc': mh.get('TenMonHoc', ''),
                'MaMonHoc': lm['MaMonHoc'],
                'SoTinChi': mh.get('SoTinChi', 0),
                'SoCaTuan': so_ca
            }
            
            course_id += 1
    
    return courses, mapping


def extract_soft_constraints_weights(constraints_df: pd.DataFrame) -> Dict[str, float]:
    """
    Đọc ràng buộc mềm từ SQL và tạo weights cho GA - FULLY DYNAMIC
    
    Mapping SQL RBM → GA weights:
        RBM-001: Giới hạn ca/ngày (w_daily_limit)
        RBM-002: Giảm số ngày lên trường (w_compact_days)
        RBM-003: Cân bằng tải giảng dạy (w_fair)
        RBM-004: Thưởng nguyện vọng (w_wish)
        RBM-005: Tối ưu liên tục (w_compact)
        RBM-006: Phạt ngoài nguyện vọng (w_unsat)
    
    Args:
        constraints_df: tb_RANG_BUOC_MEM hoặc tb_RANG_BUOC_TRONG_DOT
                       (MaRangBuoc, TenRangBuoc, TrongSo)
    
    Returns:
        Dict[str, float] - Dynamic weights dictionary
        {
            'w_daily_limit': 0.90,
            'w_compact_days': 0.85,
            'w_fair': 1.0,
            'w_wish': 1.2,
            'w_compact': 0.5,
            'w_unsat': 0.8
        }
    """
    # Default weights (fallback nếu SQL empty hoặc thiếu RBM)
    weights = {
        'w_daily_limit': 0.90,      # RBM-001
        'w_compact_days': 0.85,     # RBM-002
        'w_fair': 1.0,              # RBM-005
        'w_wish': 1.2,              # RBM-006
        'w_compact': 0.5,           # RBM-007
        'w_unsat': 0.8              # RBM-008
    }
    
    if constraints_df.empty:
        print("⚠️  Không có ràng buộc mềm trong SQL, dùng defaults")
        return weights
    
    # ✅ DYNAMIC: Đọc từ SQL và map theo MaRangBuoc
    rbm_map = {
        'RBM-001': 'w_daily_limit',
        'RBM-002': 'w_compact_days',
        'RBM-003': 'w_fair',
        'RBM-004': 'w_wish',
        'RBM-005': 'w_compact',
        'RBM-006': 'w_unsat'
    }
    
    print(f"\n⚖️  Đọc {len(constraints_df)} ràng buộc mềm từ SQL:")
    for _, rb in constraints_df.iterrows():
        ma_rb = rb['MaRangBuoc']
        trong_so = float(rb['TrongSo'])
        ten_rb = rb.get('TenRangBuoc', 'Unknown')
        
        # Map MaRangBuoc → weight key
        if ma_rb in rbm_map:
            weight_key = rbm_map[ma_rb]
            weights[weight_key] = trong_so
            print(f"   ✅ {ma_rb} → {weight_key} = {trong_so:.2f} ({ten_rb})")
        else:
            print(f"   ⚠️  {ma_rb} không có mapping, bỏ qua ({ten_rb})")
    
    print(f"\n📊 Final GA Weights (from SQL):")
    print(f"   Fitness = REWARDS - PENALTIES")
    print(f"")
    print(f"   REWARDS:")
    print(f"     + w_fair × fairness_score      (Cân bằng tải)")
    print(f"     + w_wish × wish_hit            (Thưởng nguyện vọng)")
    print(f"     + w_daily × daily_ok           (Tuân thủ giới hạn ca/ngày)")
    print(f"     + w_compact_days × days_ok     (Gom ngày hiệu quả)")
    print(f"")
    print(f"   PENALTIES:")
    print(f"     - w_compact × gaps             (Phạt khoảng trống)")
    print(f"     - w_unsat × wish_miss          (Phạt ngoài nguyện vọng)")
    print(f"")
    print(f"   Weight Values:")
    print(f"     w_fair (RBM-003):         {weights.get('w_fair', 'N/A')}")
    print(f"     w_wish (RBM-004):         {weights.get('w_wish', 'N/A')}")
    print(f"     w_compact (RBM-005):      {weights.get('w_compact', 'N/A')}")
    print(f"     w_unsat (RBM-006):        {weights.get('w_unsat', 'N/A')}")
    print(f"     w_daily_limit (RBM-001):  {weights.get('w_daily_limit', 'N/A')}")
    print(f"     w_compact_days (RBM-002): {weights.get('w_compact_days', 'N/A')}")
    
    return weights


def ga_result_to_json(timetable: List[Dict], metrics: Dict, mapping: Dict, 
                     teachers: List[Teacher], rooms: List[Room]) -> Dict:
    """
    Chuyển kết quả GA về format JSON tương thích với SQL
    
    Args:
        timetable: Kết quả từ GA (list of dict)
        metrics: Metrics từ GA
        mapping: Mapping từ sql_to_courses
        teachers: List[Teacher] đã convert
        rooms: List[Room] đã convert
    
    Returns:
        Dict JSON format cho SQL insertion
    """
    from datetime import datetime
    
    schedule = []
    
    for entry in timetable:
        # Entry từ GA: {'Course', 'Dept', 'Teacher', 'Day', 'Slot', 'Room', ...}
        course_name = entry['Course']
        
        # ✅ SỬA: Parse course name theo format "MaLop::CaX"
        if '::' not in course_name:
            print(f"⚠️ Warning: Course name '{course_name}' không đúng format (expect: MaLop::CaX), skipping...")
            continue
        
        # Tìm course_id từ name
        course_id = None
        for cid, info in mapping['course_id_to_info'].items():
            expected_name = f"{info['MaLop']}::Ca{info['ca_idx']+1}"
            if expected_name == course_name:
                course_id = cid
                break
        
        if course_id is None:
            print(f"⚠️ Warning: Course '{course_name}' not found in mapping, skipping...")
            continue
        
        info = mapping['course_id_to_info'][course_id]
        
        # Parse day, slot
        day = entry['Day']
        slot = entry['Slot']
        
        # Convert back to TimeSlotID (day=0 → Thu2, slot=0 → Ca1)
        thu = day + 2  # day=0 → Thu2
        ca = slot + 1  # slot=0 → Ca1
        timeslot_id = f"Thu{thu}-Ca{ca}"
        
        # Get Teacher name (MaGV)
        teacher_name = entry['Teacher']
        teacher_obj = next((t for t in teachers if t.name == teacher_name), None)
        ma_gv = info['MaGV']
        
        # Get Room name (MaPhong)
        room_name = entry['Room']
        room_obj = next((r for r in rooms if r.name == room_name), None)
        ma_phong = room_name
        
        schedule.append({
            'MaLop': info['MaLop'],
            'MaPhong': ma_phong,
            'TimeSlotID': timeslot_id,
            'MaGV': ma_gv,
            'MaMonHoc': info['MaMonHoc'],
            'SoTinChi': info['SoTinChi'],
            'IsPreferred': entry.get('WishHit', 0) == 1
        })
    
    return {
        'metadata': {
            'algorithm': 'Genetic_Algorithm_Memetic',
            'created_at': datetime.now().isoformat(),
            'total_assignments': len(mapping['course_id_to_info']),
            'scheduled': len(schedule),
            'success_rate': f"{(len(schedule) / max(1, len(mapping['course_id_to_info']))) * 100:.1f}%"
        },
        'metrics': {
            'fitness_before': metrics.get('fitness_before', 0),
            'fitness_after': metrics.get('fitness_after', 0),
            'improvements': metrics.get('improvements', 0),
            'fairness_std': metrics.get('fairness_std', 0),
            'wish_satisfaction': metrics.get('wish_satisfaction', 0),
            'wish_unsatisfied': metrics.get('wish_unsatisfied', 0),
            'wish_coverage_rate': metrics.get('wish_coverage_rate', 0),
            'compactness_penalty': metrics.get('compactness_penalty', 0),
            'all_assigned': metrics.get('all_assigned', False),
            'feasible': metrics.get('feasible', False)
        },
        'schedule': schedule
    }
