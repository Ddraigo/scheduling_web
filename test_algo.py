#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test chạy thuật toán trực tiếp
"""
import os
import sys
import django
import time
import random

# Force UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.algorithms.algorithms_runner import AlgorithmsRunner
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

print("=" * 80)
print("🚀 TEST CHẠY THUẬT TOÁN")
print("=" * 80)

ma_dot = "DOT1_2025-2026_HK1"
print(f"\n🎯 Chạy cho đợt: {ma_dot}")
print(f"⏳ Thời gian: 300 giây (5 phút)")

# Dùng seed ngẫu nhiên để mỗi lần chạy có kết quả khác nhau
random_seed = random.randint(1, 1_000_000)
print(f"🎲 Seed: {random_seed} (ngẫu nhiên)")

runner = AlgorithmsRunner(ma_dot=ma_dot, seed=random_seed, time_limit=300.0)

start = time.time()
result = runner.run()
elapsed = time.time() - start

print(f"\n{'=' * 80}")
print(f"⏱️  Tổng thời gian: {elapsed:.2f}s")
print(f"📊 Status: {result['status']}")

if result['status'] == 'success':
    print(f"\n✅ THÀNH CÔNG!")
    print(f"   - Đợt: {result['ma_dot']}")
    print(f"   - Lưu vào DB: {result['save_result']['created_count']} entries")
    print(f"   - JSON export: {result['json_export'].get('output_path', 'N/A')}")
    
    scores = result['ui_data']['score_breakdown']
    print(f"\n📈 Chi tiết điểm số:")
    print(f"   - Room capacity: {scores['room_capacity']}")
    print(f"   - Min working days: {scores['min_working_days']}")
    print(f"   - Curriculum compactness: {scores['curriculum_compactness']}")
    print(f"   - Room stability: {scores['room_stability']}")
    print(f"   - Lecture clustering: {scores['lecture_clustering']}")
    print(f"   - TỔNG: {scores['total']}")
else:
    print(f"\n❌ LỖI: {result.get('message', 'Unknown error')}")
    if 'debug_info' in result:
        print(f"\n🔍 Debug info:")
        for k, v in result['debug_info'].items():
            print(f"   - {k}: {v}")

print(f"\n{'=' * 80}")
