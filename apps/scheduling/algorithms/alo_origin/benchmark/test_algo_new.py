#!/usr/bin/env python3
"""
Script để test algo_new.py với dữ liệu từ database

Quy trình:
1. Chuyển đổi DB → .ctt
2. Chạy algo_new.py
3. So sánh kết quả
"""

import os
import sys
import time
import subprocess
import json
from pathlib import Path

# Thêm workspace vào path
WORKSPACE = Path(__file__).parent
sys.path.insert(0, str(WORKSPACE))
os.chdir(WORKSPACE)


def run_converter():
    """Chạy converter để tạo .ctt file"""
    print("\n" + "=" * 60)
    print("📌 BƯỚC 1: Chuyển đổi DB → .ctt format")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [sys.executable, "convert_db_to_ctt.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        print(result.stdout)
        if result.stderr:
            print("⚠️  Warnings:", result.stderr)
        if result.returncode != 0:
            print(f"❌ Converter failed with code {result.returncode}")
            return None
        
        # Tìm file .ctt đã tạo
        ctt_files = list(WORKSPACE.glob("output_*.ctt"))
        if ctt_files:
            return str(ctt_files[-1])  # Lấy file mới nhất
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def run_algo_new(ctt_file, time_limit=30, seed=42):
    """Chạy algo_new.py với file .ctt"""
    print("\n" + "=" * 60)
    print("📌 BƯỚC 2: Chạy algo_new.py")
    print("=" * 60)
    print(f"📂 Input file: {ctt_file}")
    print(f"⏱️  Time limit: {time_limit}s")
    print(f"🎲 Seed: {seed}")
    
    algo_script = WORKSPACE / "apps/scheduling/algorithms/algorithms_core.py"
    if not algo_script.exists():
        print(f"❌ Script not found: {algo_script}")
        return None
    
    output_file = ctt_file.replace(".ctt", ".sol")
    log_file = ctt_file.replace(".ctt", ".log")
    
    cmd = [
        sys.executable,
        str(algo_script),
        "--instance", str(ctt_file),
        "--out", output_file,
        "--seed", str(seed),
        "--time_limit", str(time_limit),
        "--meta", "SA",  # Simulated Annealing
        "--log", log_file
    ]
    
    print(f"\n🚀 Running command:")
    print(f"   {' '.join(cmd)}\n")
    
    try:
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=time_limit + 10)
        elapsed = time.time() - start_time
        
        print(result.stdout)
        if result.stderr:
            print("⚠️  Errors:", result.stderr)
        
        if result.returncode == 0:
            print(f"\n✅ Success in {elapsed:.2f}s")
            return {
                'output_file': output_file,
                'log_file': log_file,
                'elapsed': elapsed
            }
        else:
            print(f"❌ Failed with code {result.returncode}")
            return None
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout after {time_limit + 10}s")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def analyze_solution(sol_file, ctt_file):
    """Phân tích kết quả lịch"""
    print("\n" + "=" * 60)
    print("📌 BƯỚC 3: Phân tích kết quả")
    print("=" * 60)
    
    if not Path(sol_file).exists():
        print(f"❌ Solution file not found: {sol_file}")
        return
    
    # Đọc .ctt để lấy thông tin
    with open(ctt_file, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.strip().split('\n')
        
        # Lấy header
        courses_count = 0
        rooms_count = 0
        curricula_count = 0
        
        for line in lines:
            if line.startswith('Courses:'):
                courses_count = int(line.split(':')[1].strip())
            elif line.startswith('Rooms:'):
                rooms_count = int(line.split(':')[1].strip())
            elif line.startswith('Curricula:'):
                curricula_count = int(line.split(':')[1].strip())
    
    # Đọc solution
    with open(sol_file, 'r', encoding='utf-8') as f:
        assignments = f.readlines()
    
    print(f"\n Instance Statistics:")
    print(f"  - Courses: {courses_count}")
    print(f"  - Rooms: {rooms_count}")
    print(f"  - Curricula: {curricula_count}")
    print(f"  - Total periods: 5 days × 6 periods/day = 30")
    
    print(f"\n Solution Statistics:")
    print(f"  - Assignments: {len(assignments)}")
    print(f"  - Expected: {courses_count} (1 per course)")
    
    # Phân tích phân bố
    room_usage = {}
    day_usage = [0] * 5
    period_usage = [0] * 6
    
    for line in assignments:
        parts = line.strip().split()
        if len(parts) >= 4:
            course_id, room_id, day, period = parts[0], parts[1], int(parts[2]), int(parts[3])
            
            if room_id not in room_usage:
                room_usage[room_id] = 0
            room_usage[room_id] += 1
            day_usage[day] += 1
            period_usage[period] += 1
    
    print(f"\n  Room Usage:")
    for room, count in sorted(room_usage.items()):
        print(f"  - {room}: {count} lectures")
    
    print(f"\n Day Distribution (lectures per day):")
    for day, count in enumerate(day_usage):
        print(f"  - Day {day}: {count}")
    
    print(f"\n⏰ Period Distribution (lectures per period):")
    for period, count in enumerate(period_usage):
        print(f"  - Period {period}: {count}")
    
    print(f"\n✅ Analysis complete!")


def main():
    """Main workflow"""
    print("\n" + "=" * 70)
    print(" 🎯 TEST WORKFLOW: Database → algo_new.py")
    print("=" * 70)
    
    # Step 1: Convert
    ctt_file = run_converter()
    if not ctt_file:
        print("❌ Converter failed!")
        sys.exit(1)
    
    # Step 2: Run algo_new.py
    result = run_algo_new(ctt_file, time_limit=30, seed=42)
    if not result:
        print("❌ Algo failed!")
        sys.exit(1)
    
    # Step 3: Analyze
    analyze_solution(result['output_file'], ctt_file)
    
    print("\n" + "=" * 70)
    print(" ✨ TEST COMPLETE!")
    print("=" * 70)
    print(f"\n📁 Files generated:")
    print(f"  - Input: {ctt_file}")
    print(f"  - Output: {result['output_file']}")
    print(f"  - Log: {result['log_file']}")
    print(f"  - Elapsed: {result['elapsed']:.2f}s")


if __name__ == "__main__":
    main()
