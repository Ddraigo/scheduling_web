"""
Service để chạy thuật toán scheduling algorithm từ Django
"""

import logging
import time
import random
from pathlib import Path
from typing import Dict, Tuple, Optional
from django.conf import settings

from ..algorithms.algorithms_core import (
    parse_instance,
    build_initial_solution,
    run_metaheuristic,
    write_solution,
    CBCTTInstance,
    TimetableState,
    ScoreBreakdown,
    ProgressLogger
)
from ..algorithms.algorithms_data_adapter import export_to_ctt
from ..models import DotXep, PhanCong, ThoiKhoaBieu, TimeSlot

logger = logging.getLogger(__name__)


class AlgorithmRunner:
    """Runner để thực thi thuật toán scheduling"""
    
    def __init__(self, ma_dot: str, seed: int = 42):
        """
        Khởi tạo runner
        
        Args:
            ma_dot: Mã đợt xếp lịch
            seed: Random seed cho reproducibility
        """
        self.ma_dot = ma_dot
        self.seed = seed
        self.dot_xep = None
        self.instance = None
        self.ctt_file_path = None
        
    def prepare_data(self) -> bool:
        """
        Chuẩn bị dữ liệu: export DB sang .ctt file
        
        Returns:
            True nếu thành công, False nếu thất bại
        """
        try:
            # Lấy đợt xếp
            self.dot_xep = DotXep.objects.get(ma_dot=self.ma_dot)
            logger.info(f"Found DotXep: {self.dot_xep.ma_dot} - {self.dot_xep.ten_dot}")
            
            # Export sang .ctt file vào thư mục output/
            output_dir = Path(settings.BASE_DIR) / 'output' / 'test_web_algo' / 'ctt_files'
            output_dir.mkdir(parents=True, exist_ok=True)
            
            self.ctt_file_path = str(export_to_ctt(
                dot_xep=self.dot_xep,
                output_dir=str(output_dir)
            ))
            
            logger.info(f"Exported to CTT file: {self.ctt_file_path}")
            return True
            
        except DotXep.DoesNotExist:
            logger.error(f"DotXep not found: {self.ma_dot}")
            return False
        except Exception as e:
            logger.error(f"Error preparing data: {e}", exc_info=True)
            return False
    
    def run_optimization(
        self,
        strategy: str = "TS",
        init_method: str = "greedy-cprop",
        time_limit: float = 180.0
    ) -> Optional[Dict]:
        """
        Chạy thuật toán optimization
        
        Args:
            strategy: "TS" (Tabu Search) hoặc "SA" (Simulated Annealing)
            init_method: "greedy-cprop" hoặc "random-repair"
            time_limit: Thời gian tối đa (giây)
            
        Returns:
            Dictionary chứa kết quả, hoặc None nếu thất bại
        """
        if not self.ctt_file_path:
            logger.error("CTT file not prepared. Call prepare_data() first.")
            return None
        
        try:
            # Parse instance
            logger.info(f"Parsing CTT instance: {self.ctt_file_path}")
            self.instance = parse_instance(self.ctt_file_path, enforce_room_per_course=True)
            
            logger.info(f"Instance loaded: {len(self.instance.courses)} courses, "
                       f"{len(self.instance.rooms)} rooms, "
                       f"{self.instance.days} days × {self.instance.periods_per_day} periods")
            
            # Initialize
            rng = random.Random(self.seed)
            start_time = time.time()
            
            # Build initial solution
            logger.info(f"Building initial solution with {init_method}...")
            state = build_initial_solution(
                self.instance,
                rng,
                init_method,
                start_time,
                time_limit
            )
            
            initial_cost = state.current_cost
            initial_breakdown = state.score_breakdown()
            elapsed_init = time.time() - start_time
            
            logger.info(f"Initial solution built in {elapsed_init:.2f}s, cost: {initial_cost}")
            logger.info(f"  - Teacher Preferences: {initial_breakdown.teacher_preference_violations}")
            logger.info(f"  - Curriculum Compactness: {initial_breakdown.curriculum_compactness}")
            logger.info(f"  - Lecture Consecutiveness: {initial_breakdown.lecture_consecutiveness}")
            
            # Run metaheuristic - enable optimization phase for Teacher Lecture Consolidation
            remaining_time = time_limit - elapsed_init
            if remaining_time > 0:
                logger.info(f"Running {strategy} optimization for {remaining_time:.2f}s...")
                
                # Enable optimization phase: activate Teacher Lecture Consolidation penalty
                state._optimization_phase = True
                
                log_file = Path(settings.BASE_DIR) / 'output' / 'test_web_algo' / f'progress_{self.ma_dot}.csv'
                progress_logger = ProgressLogger(log_file)
                
                best_assignments, best_breakdown = run_metaheuristic(
                    state,
                    strategy,
                    rng,
                    progress_logger,
                    remaining_time
                )
                
                final_cost = best_breakdown.total
                logger.info(f"Optimization completed. Final cost: {final_cost}")
                logger.info(f"  - Teacher Preferences: {best_breakdown.teacher_preference_violations}")
                logger.info(f"  - Curriculum Compactness: {best_breakdown.curriculum_compactness}")
                logger.info(f"  - Lecture Consecutiveness: {best_breakdown.lecture_consecutiveness}")
            else:
                best_assignments = state.clone_assignments()
                best_breakdown = initial_breakdown
                final_cost = initial_cost
            
            # Save solution to .sol file
            sol_dir = Path(settings.BASE_DIR) / 'output' / 'test_web_algo'
            sol_dir.mkdir(parents=True, exist_ok=True)
            sol_file = sol_dir / f'solution_{self.ma_dot}.sol'
            write_solution(self.instance, best_assignments, sol_file)
            logger.info(f"Solution saved to: {sol_file}")
            
            # Return results
            return {
                'success': True,
                'ma_dot': self.ma_dot,
                'initial_cost': initial_cost,
                'final_cost': final_cost,
                'improvement': initial_cost - final_cost,
                'improvement_percent': (initial_cost - final_cost) / initial_cost * 100 if initial_cost > 0 else 0,
                'time_elapsed': time.time() - start_time,
                'breakdown': {
                    'room_capacity': best_breakdown.room_capacity,
                    'min_working_days': best_breakdown.min_working_days,
                    'curriculum_compactness': best_breakdown.curriculum_compactness,
                    'lecture_consecutiveness': best_breakdown.lecture_consecutiveness,
                    'room_stability': best_breakdown.room_stability,
                    'teacher_preferences': best_breakdown.teacher_preference_violations,
                },
                'sol_file': str(sol_file),
                'assignments': self._format_assignments(best_assignments)
            }
            
        except Exception as e:
            logger.error(f"Error during optimization: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_assignments(self, assignments: Dict[int, Tuple[int, int]]) -> Dict:
        """
        Format assignments để dễ đọc
        
        Args:
            assignments: {lecture_id: (period, room_idx)}
            
        Returns:
            Dictionary với format dễ đọc
        """
        formatted = {}
        for lecture_id, (period, room_idx) in assignments.items():
            course_idx = self.instance.lectures[lecture_id].course
            course_id = self.instance.courses[course_idx].id
            room_id = self.instance.rooms[room_idx].id
            
            day = period // self.instance.periods_per_day
            slot = period % self.instance.periods_per_day
            
            formatted[str(lecture_id)] = {
                'course_id': course_id,
                'room_id': room_id,
                'day': day,
                'period': slot,
                'period_absolute': period
            }
        
        return formatted
    
    def save_to_database(self, assignments: Dict[int, Tuple[int, int]]) -> bool:
        """
        Lưu kết quả vào database (ThoiKhoaBieu)
        
        Args:
            assignments: {lecture_id: (period, room_idx)}
            
        Returns:
            True nếu thành công
        """
        try:
            # Xóa thời khóa biểu cũ của đợt này
            ThoiKhoaBieu.objects.filter(ma_dot=self.dot_xep).delete()
            logger.info(f"Deleted old schedules for {self.ma_dot}")
            
            # Tạo mapping từ course_id (string) sang PhanCong
            course_id_to_phancong = {}
            for pc in PhanCong.objects.filter(ma_dot=self.dot_xep).select_related('ma_lop', 'ma_phong'):
                course_id_to_phancong[pc.ma_lop.ma_lop] = pc
            
            # Tạo mapping từ room_id (string) sang PhongHoc
            from ..models import PhongHoc
            room_id_to_phong = {p.ma_phong: p for p in PhongHoc.objects.all()}
            
            # Tạo ThoiKhoaBieu mới
            created_count = 0
            for lecture_id, (period, room_idx) in assignments.items():
                course_idx = self.instance.lectures[lecture_id].course
                course_id = self.instance.courses[course_idx].id
                room_id = self.instance.rooms[room_idx].id
                
                # Tính day và period
                day = period // self.instance.periods_per_day
                slot = period % self.instance.periods_per_day
                
                # Chuyển từ 0-based sang DB format (Thứ 2-7 = 2-7, Ca 1-5 = 1-5)
                db_day = day + 2  # 0→2, 1→3, ..., 5→7
                db_period = slot + 1  # 0→1, 1→2, ..., 4→5
                
                # Tìm TimeSlot tương ứng
                try:
                    time_slot = TimeSlot.objects.get(thu=db_day, ca__ma_khung_gio=db_period)
                except TimeSlot.DoesNotExist:
                    logger.warning(f"TimeSlot not found for day={db_day}, period={db_period}")
                    continue
                
                # Tìm PhanCong
                if course_id not in course_id_to_phancong:
                    logger.warning(f"PhanCong not found for course_id={course_id}")
                    continue
                
                phan_cong = course_id_to_phancong[course_id]
                
                # Tìm PhongHoc
                if room_id not in room_id_to_phong:
                    logger.warning(f"PhongHoc not found for room_id={room_id}")
                    continue
                
                phong = room_id_to_phong[room_id]
                
                # Tạo ThoiKhoaBieu
                ThoiKhoaBieu.objects.create(
                    ma_dot=self.dot_xep,
                    ma_phan_cong=phan_cong,
                    time_slot_id=time_slot,
                    ma_phong=phong
                )
                created_count += 1
            
            logger.info(f"Created {created_count} ThoiKhoaBieu records")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to database: {e}", exc_info=True)
            return False
