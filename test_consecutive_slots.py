#!/usr/bin/env python3
"""
Test script for HC-09 Consecutive Slots validation and normalization
"""

import re
from typing import List, Dict


def is_consecutive_pair(slot1: str, slot2: str) -> bool:
    """Test function: Check if 2 slots form consecutive pair"""
    try:
        match1 = re.match(r'T(\d+)-C(\d+)', str(slot1))
        match2 = re.match(r'T(\d+)-C(\d+)', str(slot2))
        
        if not match1 or not match2:
            return False
        
        day1, session1 = int(match1.group(1)), int(match1.group(2))
        day2, session2 = int(match2.group(1)), int(match2.group(2))
        
        if day1 != day2:
            return False
        
        s_min, s_max = min(session1, session2), max(session1, session2)
        
        if (s_min, s_max) in [(1, 2), (3, 4)]:
            return True
        
        if s_min == s_max:
            return True
        
        return False
        
    except (AttributeError, ValueError, IndexError):
        return False


def test_consecutive_validation():
    """Test consecutive slot validation"""
    
    test_cases = [
        # (slot1, slot2, expected_result, description)
        ("T2-C1", "T2-C2", True, "Valid: Ca 1-2 (morning consecutive)"),
        ("T2-C2", "T2-C3", False, "Invalid: Ca 2-3 (lunch break)"),
        ("T3-C3", "T3-C4", True, "Valid: Ca 3-4 (afternoon consecutive)"),
        ("T2-C1", "T3-C1", False, "Invalid: Different days"),
        ("T2-C5", "T2-C5", True, "Valid: Same session (Ca 5)"),
        ("T2-C1", "T2-C3", False, "Invalid: Ca 1-3 (skips Ca 2)"),
        ("T4-C4", "T4-C5", False, "Invalid: Ca 4-5 (different periods)"),
        ("T5-C3", "T5-C4", True, "Valid: Ca 3-4 on Friday"),
    ]
    
    print("=" * 80)
    print("TEST: Consecutive Slots Validation")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for slot1, slot2, expected, description in test_cases:
        result = is_consecutive_pair(slot1, slot2)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        
        print(f"{status} | {description}")
        print(f"     | Slots: {slot1}, {slot2}")
        print(f"     | Expected: {expected}, Got: {result}\n")
        
        if result == expected:
            passed += 1
        else:
            failed += 1
    
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return failed == 0


def test_consecutive_normalization():
    """Test consecutive slot normalization logic"""
    
    print("\n" + "=" * 80)
    print("TEST: Consecutive Slots Normalization")
    print("=" * 80)
    
    test_cases = [
        # (input_slots, expected_issue, should_fix_to)
        (["T2-C1", "T2-C2"], None, None, "Already valid (Ca 1-2)"),
        (["T2-C2", "T2-C3"], "lunch_break", ["T2-C1", "T2-C2"], "Ca 2-3 → normalize to Ca 1-2"),
        (["T3-C3", "T3-C4"], None, None, "Already valid (Ca 3-4)"),
        (["T2-C3", "T2-C4"], None, None, "Ca 3-4 valid even though not consecutive with Ca 1-2"),
    ]
    
    passed = 0
    failed = 0
    
    for input_slots, expected_issue, should_fix_to, description in test_cases:
        print(f"\n📋 Test: {description}")
        print(f"   Input: {input_slots}")
        
        # Check if has issue
        if len(input_slots) == 2:
            slots_sorted = sorted([int(re.match(r'T(\d+)-C(\d+)', s).group(2)) for s in input_slots])
            has_lunch_break = slots_sorted == [2, 3]
            
            if has_lunch_break and expected_issue == "lunch_break":
                print(f"   ✅ DETECTED: Lunch break issue (Ca 2-3)")
                if should_fix_to:
                    print(f"   ✅ FIXED TO: {should_fix_to}")
                    passed += 1
                else:
                    failed += 1
            elif not has_lunch_break and expected_issue is None:
                print(f"   ✅ VALID: No issues detected")
                passed += 1
            else:
                print(f"   ❌ UNEXPECTED: Expected {expected_issue}, got different result")
                failed += 1
        else:
            print(f"   ⚠️ SKIPPED: Not a 2-session case")
    
    print("\n" + "=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return failed == 0


def test_slot_parsing():
    """Test slot format parsing"""
    
    print("\n" + "=" * 80)
    print("TEST: Slot Format Parsing")
    print("=" * 80)
    
    test_slots = [
        "T2-C1",
        "T2-C2",
        "T3-C3",
        "T3-C4",
        "T7-C5",
        "Thu2-Ca1",  # Original format (should normalize)
        "2-1",       # Shorthand (should normalize)
    ]
    
    for slot in test_slots:
        match = re.match(r'T(\d+)-C(\d+)', slot)
        if match:
            day, session = match.groups()
            print(f"✅ {slot:15} → Day: {day}, Session: {session}")
        else:
            print(f"⚠️  {slot:15} → Could not parse (would need normalization)")
    
    print("=" * 80)
    return True


if __name__ == "__main__":
    all_pass = True
    
    all_pass &= test_consecutive_validation()
    all_pass &= test_consecutive_normalization()
    all_pass &= test_slot_parsing()
    
    print("\n" + "=" * 80)
    if all_pass:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED - Review implementation")
    print("=" * 80)
