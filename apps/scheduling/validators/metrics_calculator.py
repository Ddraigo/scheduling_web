"""
Metrics Calculator for Scheduling System
Chuyên tính toán Fitness Score cho ràng buộc mềm (Soft Constraints)

CÔNG THỨC TÍNH FITNESS:
======================
Fitness = 1.0 - (Violation_Penalty / Max_Possible_Penalty)

Trong đó:
- Violation_Penalty = Σ(trọng_số_i × vi_phạm_i) với i = 1..n ràng buộc
- Max_Possible_Penalty = Σ(trọng_số_i) với i = 1..n ràng buộc
- vi_phạm_i = số lần vi phạm ràng buộc i

Khoảng giá trị:
- 1.0 = không vi phạm (Perfect schedule)
- 0.5 = vi phạm 50% mức độ tối đa
- 0.0 = vi phạm 100% (Worst schedule)
- Có thể âm nếu vi phạm quá nặng

LOGIC XỬ LÝ RÀNG BUỘC:
=====================
1. Nếu tb_RANG_BUOC_TRONG_DOT trống → Lấy mặc định từ tb_RANG_BUOC_MEM với trọng số gốc
2. Nếu ràng buộc được liệt kê trong tb_RANG_BUOC_TRONG_DOT → Dùng trọng số từ tb_RANG_BUOC_MEM
3. Nếu muốn disable ràng buộc → Đặt trọng số = 0 trong tb_RANG_BUOC_MEM (hoặc xóa khỏi tb_RANG_BUOC_TRONG_DOT)

DANH SÁCH RÀNG BUỘC MỀM:
=======================
RBM-001: Giới hạn số ca/ngày cho giảng viên (trọng số: 0.9)
         - Vi phạm: Giảng viên dạy > 2 ca trong 1 ngày
         - Penalty: số lần vượt quá 2 ca/ngày

RBM-002: Giảm số ngày lên trường của giảng viên (trọng số: 0.7)
         - Vi phạm: Giảng viên dạy trên > 4 ngày/tuần
         - Penalty: (số ngày - 4) nếu > 4

RBM-003: Tối ưu tính liên tục - Gom ca trong ngày (trọng số: 0.8)
         - Vi phạm: Ca không liên tiếp (VD: Ca1 và Ca3 không có Ca2)
         - Penalty: số cặp ca không liên tiếp

RBM-004: Phạt khi xếp lịch ngoài nguyện vọng (trọng số: 0.9)
         - Vi phạm: Giảng viên được xếp ở slot ngoài nguyện vọng
         - Penalty: số lần xếp ngoài nguyện vọng

RBM-005: Tôn trọng ngày nghỉ/không dạy của giảng viên (trọng số: 0.9)
         - Vi phạm: Xếp lịch vào ngày GV không thể dạy
         - Penalty: số lần vi phạm

RBM-006: Ưu tiên xếp môn > 3 tín chỉ vào buổi sáng (trọng số: 0.8)
         - Vi phạm: Môn > 3 TC xếp ngoài buổi sáng (Ca1-Ca2)
         - Penalty: số lần vi phạm

RBM-007: Ưu tiên xếp môn ≤ 2 tín chỉ vào buổi chiều/tối (trọng số: 0.6)
         - Vi phạm: Môn ≤ 2 TC xếp ở buổi sáng
         - Penalty: số lần vi phạm
"""

import logging
from typing import Dict, List, Tuple, Optional
from django.db.models import Q, Count, F
from ..models import (
    RangBuocMem, RangBuocTrongDot, DotXep, GiangVien, 
    LopMonHoc, ThoiKhoaBieu, NguyenVong, NgayNghiCoDinh, NgayNghiDot
)

logger = logging.getLogger(__name__)


class SoftConstraintViolation:
    """Lưu trữ thông tin vi phạm ràng buộc"""
    def __init__(self, constraint_id: str, constraint_name: str, violation_count: int, weight: float):
        self.constraint_id = constraint_id
        self.constraint_name = constraint_name
        self.violation_count = violation_count
        self.weight = weight
        self.penalty = violation_count * weight
    
    def __repr__(self):
        return f"Violation({self.constraint_id}: {self.violation_count} × {self.weight} = {self.penalty:.2f})"


class MetricsCalculator:
    """
    Tính toán Fitness Score cho lịch xếp dựa trên ràng buộc mềm
    
    Cách sử dụng:
    >>> calculator = MetricsCalculator(ma_dot='DOT1_2025-2026_HK1')
    >>> fitness = calculator.calculate_fitness()
    >>> violations = calculator.get_violations_report()
    """
    
    # Danh sách ràng buộc mặc định (nếu tb_RANG_BUOC_TRONG_DOT trống)
    DEFAULT_CONSTRAINTS = {
        'RBM-001': 'Giới hạn số ca/ngày cho giảng viên',
        'RBM-002': 'Giảm số ngày lên trường của giảng viên',
        'RBM-003': 'Tối ưu tính liên tục (Gom ca trong ngày)',
        'RBM-004': 'Phạt khi xếp lịch ngoài nguyện vọng',
        'RBM-005': 'Tôn trọng ngày nghỉ/không dạy của giảng viên',
        'RBM-006': 'Ưu tiên xếp môn > 3 tín chỉ vào buổi sáng',
        'RBM-007': 'Ưu tiên xếp môn ≤ 2 tín chỉ vào buổi chiều/tối',
    }
    
    def __init__(self, ma_dot: str):
        """
        Khởi tạo calculator
        
        Args:
            ma_dot: Mã đợt xếp (VD: 'DOT1_2025-2026_HK1')
        """
        self.ma_dot = ma_dot
        self.dot_xep = None
        self.active_constraints = {}  # {RBM_ID: weight}
        self.violations = []  # List[SoftConstraintViolation]
        self.tkb_assignments = []  # Cache lịch xếp
        
        # Load dữ liệu
        self._load_dot_xep()
        self._load_active_constraints()
        self._load_tkb_assignments()
    
    def _load_dot_xep(self):
        """Load đợt xếp từ database"""
        try:
            self.dot_xep = DotXep.objects.get(ma_dot=self.ma_dot)
            logger.info(f"✅ Loaded DotXep: {self.ma_dot}")
        except DotXep.DoesNotExist:
            logger.error(f"❌ DotXep not found: {self.ma_dot}")
            raise ValueError(f"Đợt xếp '{self.ma_dot}' không tồn tại")
    
    def _load_active_constraints(self):
        """
        Load ràng buộc áp dụng cho đợt này
        
        Logic:
        1. Nếu tb_RANG_BUOC_TRONG_DOT có dữ liệu → Dùng những ràng buộc đó
        2. Nếu trống → Dùng toàn bộ ràng buộc từ tb_RANG_BUOC_MEM
        """
        # Kiểm tra xem tb_RANG_BUOC_TRONG_DOT có ràng buộc cho đợt này không
        constraints_in_dot = RangBuocTrongDot.objects.filter(
            ma_dot=self.dot_xep
        ).select_related('ma_rang_buoc')
        
        if constraints_in_dot.exists():
            # Có danh sách ràng buộc cụ thể cho đợt này
            for rbtd in constraints_in_dot:
                rb = rbtd.ma_rang_buoc
                # Nếu trọng số = 0, skip (disabled)
                if rb.trong_so > 0:
                    self.active_constraints[rb.ma_rang_buoc] = rb.trong_so
            logger.info(f"✅ Loaded {len(self.active_constraints)} active constraints from tb_RANG_BUOC_TRONG_DOT")
        else:
            # Trống → Dùng mặc định từ tb_RANG_BUOC_MEM
            all_constraints = RangBuocMem.objects.all()
            for rb in all_constraints:
                # Chỉ lấy ràng buộc có trọng số > 0
                if rb.trong_so > 0:
                    self.active_constraints[rb.ma_rang_buoc] = rb.trong_so
            logger.info(f"✅ Loaded {len(self.active_constraints)} default constraints from tb_RANG_BUOC_MEM")
    
    def _load_tkb_assignments(self):
        """Load lịch xếp (ThoiKhoaBieu) cho đợt này"""
        self.tkb_assignments = list(
            ThoiKhoaBieu.objects.filter(ma_dot=self.dot_xep).select_related(
                'ma_lop', 'ma_phong', 'time_slot_id', 'ma_dot'
            )
        )
        logger.info(f"✅ Loaded {len(self.tkb_assignments)} TKB assignments for {self.ma_dot}")
    
    def calculate_fitness(self) -> float:
        """
        Tính Fitness Score
        
        Công thức:
        Fitness = 1.0 - (Total_Penalty / Max_Possible_Penalty)
        
        Returns:
            float: Fitness score trong khoảng [-∞, 1.0]
                - 1.0 = Perfect (không vi phạm)
                - 0.5 = Trung bình
                - 0.0 = Rất tệ (vi phạm toàn bộ)
                - < 0 = Quá tệ
        """
        self.violations = []  # Reset violations
        
        # Tính vi phạm cho từng ràng buộc
        for constraint_id, weight in self.active_constraints.items():
            violation_count = self._check_constraint(constraint_id)
            if violation_count > 0:
                rb = RangBuocMem.objects.get(ma_rang_buoc=constraint_id)
                violation = SoftConstraintViolation(
                    constraint_id=constraint_id,
                    constraint_name=rb.ten_rang_buoc,
                    violation_count=violation_count,
                    weight=weight
                )
                self.violations.append(violation)
        
        # Tính tổng penalty
        total_penalty = sum(v.penalty for v in self.violations)
        
        # Tính max possible penalty
        max_penalty = sum(self.active_constraints.values()) * len(self.tkb_assignments)
        
        # Tính fitness
        if max_penalty == 0:
            fitness = 1.0  # Không có ràng buộc → perfect
        else:
            fitness = 1.0 - (total_penalty / max_penalty)
        
        logger.info(f"📊 Fitness Calculation:")
        logger.info(f"   Total Violations: {len(self.violations)}")
        logger.info(f"   Total Penalty: {total_penalty:.2f}")
        logger.info(f"   Max Possible Penalty: {max_penalty:.2f}")
        logger.info(f"   Fitness Score: {fitness:.4f}")
        
        return fitness
    
    def _check_constraint(self, constraint_id: str) -> int:
        """
        Kiểm tra ràng buộc và đếm số lần vi phạm
        
        Args:
            constraint_id: ID ràng buộc (VD: 'RBM-001')
            
        Returns:
            int: Số lần vi phạm (0 = tuân thủ)
        """
        method_name = f'_check_{constraint_id.lower().replace("-", "_")}'
        
        # Gọi method tương ứng với constraint
        if hasattr(self, method_name):
            return getattr(self, method_name)()
        else:
            logger.warning(f"Constraint checker not implemented: {constraint_id}")
            return 0
    
    # ============ CONSTRAINT CHECKERS ============
    
    def _check_rbm_001(self) -> int:
        """
        RBM-001: Giới hạn số ca/ngày cho giảng viên
        Vi phạm: Giảng viên dạy > 4 ca trong 1 ngày
        """
        violations = 0
        
        # Group TKB by (GiangVien, Ngày)
        gv_day_slots = {}  # {(ma_gv, ngay_bd): [time_slot_list]}
        
        for tkb in self.tkb_assignments:
            if not tkb.ma_lop or not tkb.ma_lop.phan_cong_list.exists():
                continue
            
            pc = tkb.ma_lop.phan_cong_list.first()  # Giảng viên dạy
            if not pc or not pc.ma_gv:
                continue
            
            ma_gv = pc.ma_gv.ma_gv
            ngay_bd = tkb.ngay_bd
            key = (ma_gv, ngay_bd)
            
            if key not in gv_day_slots:
                gv_day_slots[key] = []
            gv_day_slots[key].append(tkb.time_slot_id)
        
        # Kiểm tra: nếu > 4 ca/ngày → vi phạm
        for (ma_gv, ngay), slots in gv_day_slots.items():
            if len(slots) > 4:
                violations += len(slots) - 4  # Mỗi ca vượt quá 2 là 1 vi phạm
                logger.debug(f"RBM-001 violation: {ma_gv} has {len(slots)} slots on {ngay}")
        
        return violations
    
    def _check_rbm_002(self) -> int:
        """
        RBM-002: Giảm số ngày lên trường của giảng viên
        Vi phạm: Giảng viên dạy trên > 4 ngày/tuần
        """
        violations = 0
        
        # Group TKB by (GiangVien, Tuần)
        gv_week_days = {}  # {(ma_gv, week_num): set(ngay_dow)}
        
        for tkb in self.tkb_assignments:
            if not tkb.ma_lop or not tkb.ma_lop.phan_cong_list.exists():
                continue
            
            pc = tkb.ma_lop.phan_cong_list.first()
            if not pc or not pc.ma_gv:
                continue
            
            ma_gv = pc.ma_gv.ma_gv
            ngay_dow = tkb.time_slot_id.thu  # Thứ trong tuần (2-8)
            
            # Giả sử tuần 1 từ ngay_bd
            from datetime import timedelta
            days_diff = (tkb.ngay_bd - self.dot_xep.ma_du_kien_dt.ngay_bd).days
            week_num = days_diff // 7 + 1
            
            key = (ma_gv, week_num)
            if key not in gv_week_days:
                gv_week_days[key] = set()
            gv_week_days[key].add(ngay_dow)
        
        # Kiểm tra: nếu > 4 ngày/tuần → vi phạm
        for (ma_gv, week), days in gv_week_days.items():
            if len(days) > 4:
                violations += len(days) - 4
                logger.debug(f"RBM-002 violation: {ma_gv} teaches {len(days)} days on week {week}")
        
        return violations
    
    def _check_rbm_003(self) -> int:
        """
        RBM-003: Tối ưu tính liên tục - Gom ca trong ngày
        Vi phạm: Ca không liên tiếp (VD: Ca1 và Ca3 không có Ca2)
        """
        violations = 0
        
        # Group TKB by (GiangVien, Ngày)
        gv_day_sessions = {}  # {(ma_gv, ngay_bd): [ca_numbers]}
        
        for tkb in self.tkb_assignments:
            if not tkb.ma_lop or not tkb.ma_lop.phan_cong_list.exists():
                continue
            
            pc = tkb.ma_lop.phan_cong_list.first()
            if not pc or not pc.ma_gv:
                continue
            
            ma_gv = pc.ma_gv.ma_gv
            ngay_bd = tkb.ngay_bd
            ca_num = tkb.time_slot_id.ca.ma_khung_gio
            key = (ma_gv, ngay_bd)
            
            if key not in gv_day_sessions:
                gv_day_sessions[key] = []
            gv_day_sessions[key].append(ca_num)
        
        # Kiểm tra: các ca có liên tiếp không
        for (ma_gv, ngay), sessions in gv_day_sessions.items():
            sessions_sorted = sorted(set(sessions))
            
            # Kiểm tra các cặp: nếu (a, a+1) không đầy đủ → vi phạm
            for i in range(len(sessions_sorted) - 1):
                if sessions_sorted[i+1] - sessions_sorted[i] > 1:
                    violations += sessions_sorted[i+1] - sessions_sorted[i] - 1
                    logger.debug(f"RBM-003 violation: {ma_gv} on {ngay} missing sessions between {sessions_sorted[i]} and {sessions_sorted[i+1]}")
        
        return violations
    
    def _check_rbm_004(self) -> int:
        """
        RBM-004: Phạt khi xếp lịch ngoài nguyện vọng
        Vi phạm: Giảng viên được xếp ở slot ngoài nguyện vọng
        """
        violations = 0
        
        # Lấy danh sách nguyện vọng
        nguyen_vong_set = set()
        for nv in NguyenVong.objects.filter(ma_dot=self.dot_xep):
            nguyen_vong_set.add((nv.ma_gv.ma_gv, nv.time_slot_id.time_slot_id))
        
        # Kiểm tra: nếu GV được xếp ở slot không trong nguyện vọng → vi phạm
        for tkb in self.tkb_assignments:
            if not tkb.ma_lop or not tkb.ma_lop.phan_cong_list.exists():
                continue
            
            pc = tkb.ma_lop.phan_cong_list.first()
            if not pc or not pc.ma_gv:
                continue
            
            ma_gv = pc.ma_gv.ma_gv
            slot_id = tkb.time_slot_id.time_slot_id
            
            # Nếu có nguyện vọng cho GV này
            if any(gv == ma_gv for gv, _ in nguyen_vong_set):
                # Và slot này không trong nguyện vọng
                if (ma_gv, slot_id) not in nguyen_vong_set:
                    violations += 1
                    logger.debug(f"RBM-004 violation: {ma_gv} assigned outside preferences at {slot_id}")
        
        return violations
    
    def _check_rbm_005(self) -> int:
        """
        RBM-005: Tôn trọng ngày nghỉ/không dạy của giảng viên
        Vi phạm: Xếp lịch vào ngày GV không thể dạy
        """
        violations = 0
        
        # TODO: Cần thêm bảng "Ngày GV không dạy" trong database
        # Hiện tại, chỉ kiểm tra các ngày nghỉ từ NgayNghiDot
        
        ngay_nghi = set()
        for nn in NgayNghiDot.objects.filter(ma_dot=self.dot_xep):
            for i in range(nn.so_ngay_nghi):
                from datetime import timedelta
                ngay = nn.ngay_bd + timedelta(days=i)
                ngay_nghi.add(ngay)
        
        # Kiểm tra: nếu TKB xếp vào ngày nghỉ → vi phạm
        for tkb in self.tkb_assignments:
            if tkb.ngay_bd in ngay_nghi:
                violations += 1
                logger.debug(f"RBM-005 violation: {tkb.ma_lop} assigned on holiday {tkb.ngay_bd}")
        
        return violations
    
    def _check_rbm_006(self) -> int:
        """
        RBM-006: Ưu tiên xếp môn > 3 tín chỉ vào buổi sáng
        Vi phạm: Môn > 3 TC xếp ngoài buổi sáng (Ca1-Ca2)
        """
        violations = 0
        MORNING_SESSIONS = {1, 2}  # Ca1, Ca2 = buổi sáng
        
        for tkb in self.tkb_assignments:
            if not tkb.ma_lop:
                continue
            
            mon_hoc = tkb.ma_lop.ma_mon_hoc
            so_tin_chi = mon_hoc.so_tin_chi or 0
            
            # Nếu môn > 3 TC và không ở buổi sáng → vi phạm
            if so_tin_chi > 3:
                ca_num = tkb.time_slot_id.ca.ma_khung_gio
                if ca_num not in MORNING_SESSIONS:
                    violations += 1
                    logger.debug(f"RBM-006 violation: {tkb.ma_lop} ({so_tin_chi}TC) not in morning session {ca_num}")
        
        return violations
    
    def _check_rbm_007(self) -> int:
        """
        RBM-007: Ưu tiên xếp môn ≤ 2 tín chỉ vào buổi chiều/tối
        Vi phạm: Môn ≤ 2 TC xếp ở buổi sáng
        """
        violations = 0
        MORNING_SESSIONS = {1, 2}
        
        for tkb in self.tkb_assignments:
            if not tkb.ma_lop:
                continue
            
            mon_hoc = tkb.ma_lop.ma_mon_hoc
            so_tin_chi = mon_hoc.so_tin_chi or 0
            
            # Nếu môn ≤ 2 TC và ở buổi sáng → vi phạm
            if so_tin_chi <= 2:
                ca_num = tkb.time_slot_id.ca.ma_khung_gio
                if ca_num in MORNING_SESSIONS:
                    violations += 1
                    logger.debug(f"RBM-007 violation: {tkb.ma_lop} ({so_tin_chi}TC) in morning session {ca_num}")
        
        return violations
    
    # ============ REPORTING ============
    
    def get_violations_report(self) -> Dict:
        """
        Trả về báo cáo chi tiết về vi phạm
        
        Returns:
            Dict chứa:
            - total_violations: Tổng số vi phạm
            - violations: List chi tiết từng vi phạm
            - summary_by_constraint: Tóm tắt theo ràng buộc
        """
        return {
            'total_violations': len(self.violations),
            'violations': [
                {
                    'constraint_id': v.constraint_id,
                    'constraint_name': v.constraint_name,
                    'violation_count': v.violation_count,
                    'weight': v.weight,
                    'penalty': v.penalty
                }
                for v in self.violations
            ],
            'summary_by_constraint': {
                v.constraint_id: {
                    'name': v.constraint_name,
                    'count': v.violation_count,
                    'weight': v.weight,
                    'penalty': v.penalty
                }
                for v in self.violations
            }
        }
    
    def print_report(self):
        """In báo cáo chi tiết"""
        print("\n" + "="*80)
        print(f"METRICS REPORT - {self.ma_dot}")
        print("="*80)
        
        fitness = self.calculate_fitness()
        print(f"\n📊 Fitness Score: {fitness:.4f}")
        print(f"   Status: {'✅ EXCELLENT' if fitness > 0.9 else '✅ GOOD' if fitness > 0.7 else '⚠️ FAIR' if fitness > 0.5 else '❌ POOR'}")
        
        print(f"\n📋 Active Constraints: {len(self.active_constraints)}")
        for c_id, weight in self.active_constraints.items():
            rb = RangBuocMem.objects.get(ma_rang_buoc=c_id)
            print(f"   - {c_id}: {rb.ten_rang_buoc} (weight: {weight})")
        
        print(f"\n⚠️ Violations: {len(self.violations)}")
        if self.violations:
            for v in self.violations:
                print(f"   - {v.constraint_id}: {v.violation_count} violations × {v.weight} = {v.penalty:.2f} penalty")
        else:
            print("   ✅ No violations!")
        
        print("\n" + "="*80 + "\n")
