#!/usr/bin/env python
"""
Script để fix format slot trong file JSON schedule
Chuyển tất cả compact format (T2-C1) thành format gốc (Thu2-Ca1)
"""

import json
import os
import re

def compact_to_original_slot(compact_slot):
    """Chuyển format compact (T2-C1) sang format gốc (Thu2-Ca1)"""
    # Map day numbers to Vietnamese days
    day_map = {
        '2': 'Thu2',    # Thứ 2
        '3': 'Thu3',    # Thứ 3
        '4': 'Thu4',    # Thứ 4
        '5': 'Thu5',    # Thứ 5
        '6': 'Thu6',    # Thứ 6
        '7': 'Thu7',    # Thứ 7
        '8': 'CN',      # Chủ nhật
    }
    
    # Map session numbers to Ca
    session_map = {
        '1': 'Ca1',
        '2': 'Ca2',
        '3': 'Ca3',
        '4': 'Ca4',
        '5': 'Ca5',
    }
    
    # Try to parse compact format: T2-C1
    pattern = r'^T([2-8])-C([1-5])$'
    match = re.match(pattern, compact_slot)
    
    if match:
        day_num = match.group(1)
        session_num = match.group(2)
        
        # Get day name
        day_name = day_map.get(day_num, f'Thu{day_num}')
        
        # Get session name
        session_name = session_map.get(session_num, f'Ca{session_num}')
        
        return f'{day_name}-{session_name}'
    
    # If doesn't match, return as is
    return compact_slot


def fix_json_file(filepath):
    """Fix JSON file by converting all compact slots to original format"""
    
    print(f"📂 Opening {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    schedule = data.get('schedule', [])
    mixed_format_count = 0
    failed_count = 0
    
    print(f"📊 Processing {len(schedule)} entries...")
    
    for i, entry in enumerate(schedule):
        slot = entry.get('slot', '')
        
        # If slot is in compact format (T2-C1), convert to original (Thu2-Ca1)
        if slot and slot.startswith('T') and '-C' in slot:
            try:
                new_slot = compact_to_original_slot(slot)
                if new_slot != slot:
                    print(f"  ✓ {i+1:3d}. {entry['class']:<15} {slot:<10} → {new_slot}")
                    entry['slot'] = new_slot
                    mixed_format_count += 1
            except Exception as e:
                print(f"  ❌ {i+1:3d}. Failed to convert {slot}: {e}")
                failed_count += 1
    
    print(f"\n📊 Results:")
    print(f"  ✓ Fixed: {mixed_format_count}")
    print(f"  ❌ Failed: {failed_count}")
    
    # Save back
    print(f"\n💾 Saving fixed JSON...")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Done! File saved to {filepath}")


if __name__ == '__main__':
    # Fix the generated schedule file
    filepath = 'output/schedule_llm_2025-2026-HK1.json'
    
    if os.path.exists(filepath):
        fix_json_file(filepath)
    else:
        print(f"❌ File not found: {filepath}")
