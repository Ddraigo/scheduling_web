#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick check of unified output files"""

import json
from pathlib import Path

files_to_check = [
    'output/validation_algorithm_unified.json',
    'output/validation_detailed_unified.json',
]

for file in files_to_check:
    fpath = Path(file)
    if fpath.exists():
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        hard_viols = len(data.get('hard_violations', []))
        soft_viols = len(data.get('soft_violations', []))
        source = data.get('source', 'unknown')
        fitness = data.get('fitness', {}).get('combined_fitness')
        
        print(f"\n📄 {file}")
        print(f"   Source: {source}")
        print(f"   Hard violations: {hard_viols}")
        print(f"   Soft violations: {soft_viols}")
        print(f"   Fitness: {fitness}")
    else:
        print(f"❌ {file} NOT FOUND")

print("\n✅ Check complete")
