"""
Algorithms Runner: Điều phối chạy CB-CTT scheduler
"""

import time
import random
import logging
from typing import Dict, Tuple, Optional

from .algorithms_core import (
    build_initial_solution, rebuild_state, TimetableState, ScoreBreakdown,
    run_metaheuristic, ProgressLogger
)
from .algorithms_data_adapter import AlgorithmsDataAdapter

logger = logging.getLogger(__name__)


class AlgorithmsRunner:
    """
    Điều phối chạy thuật toán xếp lịch
    """

    def __init__(self, ma_dot: str, seed: int = None, time_limit: float = 30.0):
        """
        Khởi tạo runner
        
        Args:
            ma_dot: Mã đợt xếp (VD: '2025-2026_HK1')
            seed: Random seed (nếu None thì luôn ngẫu nhiên)
            time_limit: Thời gian tối đa (giây)
        """
        self.ma_dot = ma_dot
        self.seed = seed
        self.time_limit = time_limit
        if seed is not None:
            self.rng = random.Random(seed)
        else:
            self.rng = random.Random()
        self.start_time = None
        self.instance = None

    def run(self) -> Dict:
        """
        Chạy toàn bộ quy trình xếp lịch
        
        Returns:
            Dict chứa kết quả (status, schedule, score_breakdown, etc.)
        """
        self.start_time = time.time()
        
        try:
            # 1. Load dữ liệu từ DB
            logger.info(f"Đang load dữ liệu cho đợt: {self.ma_dot}")
            self.instance = AlgorithmsDataAdapter.build_cbctt_instance_from_db(self.ma_dot)
            logger.info(f"✅ Loaded {len(self.instance.lectures)} lectures, {len(self.instance.courses)} courses, {len(self.instance.rooms)} rooms")
            logger.info(f"   Days: {self.instance.days}, Periods/day: {self.instance.periods_per_day}, Total periods: {self.instance.total_periods}")
            logger.info(f"   Teachers: {len(self.instance.teachers)}, Curriculums: {len(self.instance.curriculums)}")

            # 2. Xây dựng lời giải khởi tạo
            logger.info("Đang xây dựng lời giải khởi tạo...")
            init_deadline = self.start_time + self.time_limit * 0.35
            time_budget = max(5.0, init_deadline - time.time())
            
            try:
                state = build_initial_solution(
                    self.instance,
                    self.rng,
                    time_limit=time_budget
                )
            except RuntimeError as e:
                logger.error(f"❌ Lỗi xây dựng lời giải khởi tạo: {e}")
                
                # Đếm số nguyện vọng để debug
                from apps.scheduling.models import NguyenVong, DotXep
                nguyen_vong_count = 0
                try:
                    dot_xep = DotXep.objects.get(ma_dot=self.ma_dot)
                    nguyen_vong_count = NguyenVong.objects.filter(ma_dot=dot_xep).count()
                except Exception:
                    pass
                
                return {
                    'status': 'error',
                    'ma_dot': self.ma_dot,
                    'message': f"Không thể xây dựng lời giải khởi tạo: {str(e)}",
                    'elapsed_time': time.time() - self.start_time,
                    'debug_info': {
                        'courses': len(self.instance.courses),
                        'rooms': len(self.instance.rooms),
                        'lectures': len(self.instance.lectures),
                        'total_periods': self.instance.total_periods,
                        'teachers': len(self.instance.teachers),
                        'curriculums': len(self.instance.curriculums),
                        'nguyen_vong_count': nguyen_vong_count,
                    }
                }

            elapsed = time.time() - self.start_time
            logger.info(f"✅ Lời giải khởi tạo xây dựng xong trong {elapsed:.2f}s, cost={state.current_cost}")
            logger.info(f"   Assigned: {len(state.assignments)}/{len(self.instance.lectures)} lectures")

            # 3. Kiểm tra ràng buộc cứng
            if not state.check_hard_constraints():
                logger.error("❌ Lời giải khởi tạo không thỏa ràng buộc cứng")
                return {
                    'status': 'error',
                    'ma_dot': self.ma_dot,
                    'message': "Lời giải khởi tạo không thỏa ràng buộc cứng",
                    'elapsed_time': time.time() - self.start_time,
                }

            # 4. Chạy metaheuristic optimization (Tabu Search hoặc Simulated Annealing)
            logger.info("Đang chạy metaheuristic optimization...")
            opt_start = time.time()
            opt_budget = max(5.0, self.time_limit - (opt_start - self.start_time))
            
            with ProgressLogger() as progress_logger:
                best_assignments, best_breakdown = run_metaheuristic(
                    state,
                    meta="SA",  # Simulated Annealing
                    rng=self.rng,
                    logger=progress_logger,
                    remaining_time=opt_budget
                )
            
            opt_elapsed = time.time() - opt_start
            logger.info(f"✅ Metaheuristic hoàn thành trong {opt_elapsed:.2f}s, cost={best_breakdown.total}")
            logger.info(f"   - Room capacity: {best_breakdown.room_capacity}")
            logger.info(f"   - Min working days: {best_breakdown.min_working_days}")
            logger.info(f"   - Curriculum compactness: {best_breakdown.curriculum_compactness}")
            logger.info(f"   - Room stability: {best_breakdown.room_stability}")
            logger.info(f"   - Lecture clustering: {best_breakdown.lecture_clustering}")

            # 5. Lưu kết quả vào DB (TẠM THỜI DISABLED - chưa cần)
            logger.info("⊘ Skip saving to database (disabled for testing)")
            save_result = {
                'ma_dot': self.ma_dot,
                'created_count': 0,  # Placeholder
                'room_capacity_penalty': best_breakdown.room_capacity,
                'min_working_days_penalty': best_breakdown.min_working_days,
                'curriculum_compactness_penalty': best_breakdown.curriculum_compactness,
                'room_stability_penalty': best_breakdown.room_stability,
                'lecture_clustering_penalty': best_breakdown.lecture_clustering,
                'total_cost': best_breakdown.total,
            }
            # save_result = AlgorithmsDataAdapter.save_results_to_db(
            #     self.ma_dot,
            #     self.instance,
            #     best_assignments,
            #     best_breakdown
            # )

            # 6. Format kết quả cho UI
            elapsed_total = time.time() - self.start_time
            ui_result = AlgorithmsDataAdapter.format_result_for_ui(
                self.ma_dot,
                self.instance,
                best_assignments,
                best_breakdown,
                elapsed_total
            )

            # 7. Export kết quả ra file JSON
            logger.info("Đang export kết quả ra file JSON...")
            json_export = AlgorithmsDataAdapter.export_result_to_json(
                self.ma_dot,
                self.instance,
                best_assignments,
                best_breakdown,
                elapsed_total
            )
            logger.info(f"JSON export status: {json_export.get('status')}")

            return {
                'status': 'success',
                'ma_dot': self.ma_dot,
                'elapsed_time': elapsed_total,
                'ui_data': ui_result,
                'save_result': save_result,
                'json_export': json_export,
            }

        except Exception as e:
            logger.exception(f"Lỗi không mong muốn: {e}")
            return {
                'status': 'error',
                'ma_dot': self.ma_dot,
                'message': f"Lỗi: {str(e)}",
                'elapsed_time': time.time() - self.start_time,
            }

    def run_with_metaheuristic(self, metaheuristic: str = "SA") -> Dict:
        """
        Chạy với metaheuristic optimization (nâng cao - dành cho sau)
        
        Args:
            metaheuristic: 'SA' (Simulated Annealing) hoặc 'TS' (Tabu Search)
        
        Returns:
            Dict kết quả
        """
        # TODO: Thêm code cho metaheuristic (Simulated Annealing, Tabu Search)
        # Tạm thời chỉ dùng lời giải khởi tạo
        return self.run()
