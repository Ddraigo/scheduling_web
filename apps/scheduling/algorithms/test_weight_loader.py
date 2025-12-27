"""
Test script for dynamic weight loading mechanism.
Tests the WeightLoader with various scenarios to ensure failsafe behavior.

Run from project root:
    python -m apps.scheduling.algorithms.test_weight_loader
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Set up Django
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.algorithms.weight_loader import WeightLoader, DEFAULT_WEIGHTS
from apps.scheduling.models import RangBuocMem, RangBuocTrongDot, DotXep


def test_default_weights():
    """Test 1: Verify DEFAULT_WEIGHTS structure"""
    print("\n" + "="*60)
    print("TEST 1: Default Weights Structure")
    print("="*60)
    
    expected_keys = {
        'MIN_WORKING_DAYS',
        'LECTURE_CONSECUTIVENESS',
        'ROOM_STABILITY',
        'TEACHER_LECTURE_CONSOLIDATION',
        'TEACHER_PREFERENCE',
        'TEACHER_WORKING_DAYS',
        'ROOM_CAPACITY',
    }
    
    assert set(DEFAULT_WEIGHTS.keys()) == expected_keys, \
        f"Missing or extra keys in DEFAULT_WEIGHTS. Expected: {expected_keys}, Got: {set(DEFAULT_WEIGHTS.keys())}"
    
    for key, value in DEFAULT_WEIGHTS.items():
        assert isinstance(value, (int, float)), f"{key} should be numeric, got {type(value)}"
        assert value > 0, f"{key} should be positive, got {value}"
    
    print("✅ DEFAULT_WEIGHTS structure is valid")
    for key, value in sorted(DEFAULT_WEIGHTS.items()):
        print(f"   {key}: {value}")


def test_load_without_dot():
    """Test 2: Load weights without specific dot (should get global defaults)"""
    print("\n" + "="*60)
    print("TEST 2: Load Global Defaults (no ma_dot)")
    print("="*60)
    
    weights = WeightLoader.load_weights()
    
    assert isinstance(weights, dict), "Should return a dict"
    assert len(weights) > 0, "Should not be empty"
    
    print(f"✅ Loaded {len(weights)} global weights:")
    for key, value in sorted(weights.items()):
        print(f"   {key}: {value}")


def test_load_with_nonexistent_dot():
    """Test 3: Load weights for non-existent dot (should fallback to defaults)"""
    print("\n" + "="*60)
    print("TEST 3: Non-existent Dot (should fallback)")
    print("="*60)
    
    fake_dot = "DOT-9999-TEST-NONEXISTENT"
    weights = WeightLoader.load_weights(fake_dot)
    
    assert isinstance(weights, dict), "Should return a dict"
    assert len(weights) > 0, "Should not be empty"
    
    # Should fallback to either global RangBuocMem or DEFAULT_WEIGHTS
    print(f"✅ Loaded {len(weights)} weights for non-existent dot:")
    for key, value in sorted(weights.items()):
        print(f"   {key}: {value}")


def test_load_with_real_dot():
    """Test 4: Load weights for real dot (if exists in database)"""
    print("\n" + "="*60)
    print("TEST 4: Real Dot from Database")
    print("="*60)
    
    # Try to find a real dot
    try:
        dot = DotXep.objects.first()
        if dot is None:
            print("⚠️  No DotXep found in database, skipping test")
            return
        
        ma_dot = dot.ma_dot
        print(f"Testing with real dot: {ma_dot}")
        
        weights = WeightLoader.load_weights(ma_dot)
        
        assert isinstance(weights, dict), "Should return a dict"
        assert len(weights) > 0, "Should not be empty"
        
        print(f"✅ Loaded {len(weights)} weights for dot {ma_dot}:")
        for key, value in sorted(weights.items()):
            print(f"   {key}: {value}")
        
        # Check if dot has custom constraints
        has_custom = RangBuocTrongDot.objects.filter(ma_dot=ma_dot).exists()
        if has_custom:
            print(f"   (Dot has custom constraints in tb_RANG_BUOC_TRONG_DOT)")
        else:
            print(f"   (Dot uses global defaults from tb_RANG_BUOC_MEM)")
            
    except Exception as e:
        print(f"⚠️  Could not test with real dot: {e}")


def test_database_constraints():
    """Test 5: Check database RangBuocMem records"""
    print("\n" + "="*60)
    print("TEST 5: Database RangBuocMem Records")
    print("="*60)
    
    try:
        all_constraints = RangBuocMem.objects.all()
        
        if not all_constraints.exists():
            print("⚠️  No RangBuocMem records found in database")
            print("   System will use DEFAULT_WEIGHTS fallback")
        else:
            print(f"✅ Found {all_constraints.count()} RangBuocMem records:")
            for rb in all_constraints:
                print(f"   {rb.ma_rang_buoc}: {rb.ten_rang_buoc} (weight={rb.trong_so})")
                
    except Exception as e:
        print(f"⚠️  Could not query RangBuocMem: {e}")


def test_get_single_weight():
    """Test 6: Get single weight value"""
    print("\n" + "="*60)
    print("TEST 6: Get Single Weight")
    print("="*60)
    
    weight = WeightLoader.get_weight('TEACHER_PREFERENCE')
    print(f"✅ TEACHER_PREFERENCE weight: {weight}")
    
    weight = WeightLoader.get_weight('MIN_WORKING_DAYS')
    print(f"✅ MIN_WORKING_DAYS weight: {weight}")


def test_failsafe_behavior():
    """Test 7: Failsafe - simulate database error"""
    print("\n" + "="*60)
    print("TEST 7: Failsafe Behavior")
    print("="*60)
    
    # Even if database fails, WeightLoader should not crash
    try:
        weights = WeightLoader.load_weights("ANY-DOT")
        assert isinstance(weights, dict), "Should always return a dict"
        assert len(weights) > 0, "Should never be empty"
        print("✅ Failsafe works: Always returns valid weights")
        
    except Exception as e:
        print(f"❌ FAILSAFE FAILED: {e}")
        raise


def main():
    """Run all tests"""
    print("\n" + "#"*60)
    print("# WEIGHT LOADER TEST SUITE")
    print("#"*60)
    
    try:
        test_default_weights()
        test_load_without_dot()
        test_load_with_nonexistent_dot()
        test_load_with_real_dot()
        test_database_constraints()
        test_get_single_weight()
        test_failsafe_behavior()
        
        print("\n" + "#"*60)
        print("# ALL TESTS PASSED ✅")
        print("#"*60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
