"""
Wrapper cho greedy_heuristic_ga_algorithm.py
Tránh auto-run khi import
"""
import sys
import os

# Thêm path
sys.path.insert(0, os.path.dirname(__file__))

# Ngăn chặn auto-run bằng cách redirect stdout tạm thời
import io
import contextlib

# Capture output để tránh in ra console khi import
with contextlib.redirect_stdout(io.StringIO()), \
     contextlib.redirect_stderr(io.StringIO()):
    try:
        # Import module - sẽ chạy run_demo() nhưng không in ra
        from greedy_heuristic_ga_algorithm import *
    except Exception as e:
        # Bỏ qua lỗi khi run_demo() thất bại (do chưa có data)
        pass

# Export các hàm/class cần dùng
__all__ = [
    'Teacher', 'Room', 'Course', 'GlobalConfig',
    'teachers', 'rooms', 'courses',
    'candidate_rooms_for_course', 'feasible_slots',
    'run_demo', 'build_option_lists',
    'DAYS', 'SLOTS', 'idx', 'bitset_from_pairs', 'window_available'
]
