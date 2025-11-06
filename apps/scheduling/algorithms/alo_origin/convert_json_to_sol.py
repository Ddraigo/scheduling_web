#!/usr/bin/env python3
"""
Convert schedule_algorithm_DOT1_2025-2026_HK1.json to .sol format

JSON format:
{
  "schedule": [
    {"class": "LOP-00000157", "room": "F509", "slot": "Thu2-Ca4", ...},
    ...
  ]
}

SOL format:
<course_id> <room> <day> <period>
"""

import json
import sys
from pathlib import Path


# Map Vietnamese day names to numbers in .ctt format (0-5)
# Mapping: DB day (2-7: Thứ2-Thứ7) → .ctt day (0-5)
# Note: "Thu2" in JSON = "Thứ 2" (Monday), not Thursday!
DAY_MAP = {
    'Thu2': 0,  # Thứ 2 (Monday)
    'Thu3': 1,  # Thứ 3 (Tuesday)
    'Thu4': 2,  # Thứ 4 (Wednesday)
    'Thu5': 3,  # Thứ 5 (Thursday)
    'Thu6': 4,  # Thứ 6 (Friday)
    'Thu7': 5,  # Thứ 7 (Saturday)
    'T2': 0,    # Alternative: T2 = Thứ 2
    'T3': 1,    # Alternative: T3 = Thứ 3
    'T4': 2,    # Alternative: T4 = Thứ 4
    'T5': 3,    # Alternative: T5 = Thứ 5
    'T6': 4,    # Alternative: T6 = Thứ 6
    'T7': 5,    # Alternative: T7 = Thứ 7
    'Mon': 0,   # English: Monday
    'Tue': 1,   # English: Tuesday
    'Wed': 2,   # English: Wednesday
    'Thu': 3,   # English: Thursday
    'Fri': 4,   # English: Friday
    'Sat': 5,   # English: Saturday
}


def parse_slot(slot_str):
    """
    Parse slot string to get day and period.
    
    JSON formats:
    - "Thu2-Ca4" → .ctt format (day 0-5, period 0-4)
    - "T2-Ca1" → .ctt format
    
    Mapping:
    - Day: T2/T3/T4/T5/T6/T7 → 0-5 (corresponds to DB days 2-7 - 2)
    - Period: Ca1-Ca5 → 0-4 (corresponds to DB ca 1-5 - 1)
    
    Returns: (day, period) as integers or (None, None) on error
    """
    if not slot_str:
        return None, None
    
    slot_str = slot_str.strip()
    
    # Try format: "Thu2-Ca4" or "T2-Ca1"
    if '-' in slot_str:
        parts = slot_str.split('-')
        if len(parts) == 2:
            day_part = parts[0].strip()
            period_part = parts[1].strip()
            
            # Extract day number
            day = extract_day(day_part)
            
            # Extract period from "Ca4", "Ca1", etc.
            period = extract_period(period_part)
            
            if day is not None and period is not None:
                return day, period
    
    return None, None


def extract_day(day_str):
    """
    Extract day number from string like 'T2', 'Thu2', 'Mon', etc.
    
    Mapping to .ctt format (0-5):
    - T2, Mon → 0 (Thứ 2)
    - T3, Tue → 1 (Thứ 3)
    - T4, Wed → 2 (Thứ 4)
    - T5, Thu → 3 (Thứ 5)
    - T6, Fri → 4 (Thứ 6)
    - T7 → 5 (Thứ 7)
    """
    day_str = day_str.strip()
    
    # Direct mapping from DAY_MAP
    if day_str in DAY_MAP:
        return DAY_MAP[day_str]
    
    return None


def extract_period(period_str):
    """
    Extract period number from string like 'Ca4', 'Ca1', etc.
    
    Mapping to .ctt format (0-4):
    - Ca1 → 0
    - Ca2 → 1
    - Ca3 → 2
    - Ca4 → 3
    - Ca5 → 4
    
    JSON uses Ca (khung giờ): 1-5
    .ctt uses period: 0-4 (= Ca - 1)
    """
    period_str = period_str.strip()
    
    # Extract digits
    digits = ''.join(c for c in period_str if c.isdigit())
    
    if digits:
        ca_num = int(digits)
        # Convert Ca (1-5) to period (0-4)
        period = ca_num - 1
        if 0 <= period <= 4:
            return period
    
    return None


def convert_json_to_sol(json_file, sol_file=None):
    """
    Convert JSON schedule to SOL format.
    
    Args:
        json_file: Path to input JSON file
        sol_file: Path to output SOL file (optional, defaults to input name with .sol)
    
    Returns:
        list: Converted records or None on error
    """
    if sol_file is None:
        sol_file = Path(json_file).with_suffix('.sol')
    
    try:
        # Read JSON
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, dict) or 'schedule' not in data:
            print(f"ERROR: Invalid JSON format. Expected {{'schedule': [...]}}")
            return None
        
        schedule = data['schedule']
        
        if not isinstance(schedule, list):
            print(f"ERROR: 'schedule' must be a list")
            return None
        
        # Convert records
        records = []
        errors = []
        
        for idx, item in enumerate(schedule):
            if not isinstance(item, dict):
                errors.append(f"Line {idx}: Not a dict")
                continue
            
            course_id = item.get('class')
            room = item.get('room')
            slot = item.get('slot')
            
            if not course_id or not room or not slot:
                errors.append(
                    f"Line {idx}: Missing fields. Got class={course_id}, room={room}, slot={slot}"
                )
                continue
            
            day, period = parse_slot(slot)
            
            if day is None or period is None:
                errors.append(f"Line {idx}: Cannot parse slot '{slot}' for course {course_id}")
                continue
            
            records.append((course_id, room, day, period))
        
        # Print errors if any
        if errors:
            print(f"Warnings/Errors during conversion ({len(errors)} items):")
            for err in errors[:10]:  # Show first 10
                print(f"  {err}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")
        
        # Write SOL file
        with open(sol_file, 'w', encoding='utf-8') as f:
            for course_id, room, day, period in records:
                f.write(f"{course_id} {room} {day} {period}\n")
        
        print(f"\n✓ Conversion successful!")
        print(f"  Input:  {json_file}")
        print(f"  Output: {sol_file}")
        print(f"  Total records: {len(records)}")
        print(f"  Errors: {len(errors)}")
        
        return records
    
    except FileNotFoundError:
        print(f"ERROR: File not found: {json_file}")
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


if __name__ == '__main__':
    if len(sys.argv) < 2:
        # Default usage
        # Path: project_root/output/schedule_algorithm_DOT1_2025-2026_HK1.json
        default_json = Path(__file__).parent.parent.parent.parent.parent / 'output' / 'schedule_algorithm_DOT1_2025-2026_HK1.json'
        default_sol = Path(__file__).parent / 'schedule_algorithm_DOT1_2025-2026_HK1.sol'
        
        print(f"Usage: python convert_json_to_sol.py <input.json> [output.sol]\n")
        print(f"Converting default files:")
        print(f"  Input:  {default_json}")
        print(f"  Output: {default_sol}\n")
        
        convert_json_to_sol(str(default_json), str(default_sol))
    else:
        json_file = sys.argv[1]
        sol_file = sys.argv[2] if len(sys.argv) > 2 else None
        convert_json_to_sol(json_file, sol_file)
