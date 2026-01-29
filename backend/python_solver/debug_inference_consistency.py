import sys
import os
import numpy as np
import zlib

# Add current directory to path
sys.path.append(os.getcwd())

from scorer.model import NeuralScorer

def verify_consistency():
    print("--- CONSISTENCY VERIFICATION: Role Hashing ---")
    scorer = NeuralScorer()
    
    emp = {"role": "DEVELOPER", "id": "EMP1"}
    shift = {"role": "DEVELOPER", "date": "2024-01-01", "start_time": "09:00"}
    
    # Test 1: Extraction with NO roles provided
    feat1 = scorer.extract_features(emp, shift)
    
    # Test 2: Extraction with random roles list provided (should be ignored)
    feat2 = scorer.extract_features(emp, shift, all_roles=["MANAGER", "CLEANER"])
    
    # Test 3: Extraction with different role but same normalized name
    shift2 = {"role": "developer ", "date": "2024-01-01", "start_time": "09:00"}
    feat3 = scorer.extract_features(emp, shift2)
    
    print(f"Feature Vector 1 (Role Index): {feat1[8]}")
    print(f"Feature Vector 2 (Role Index): {feat2[8]}")
    print(f"Feature Vector 3 (Role Index): {feat3[8]}")
    
    # Check if they match
    if np.array_equal(feat1, feat2) and np.array_equal(feat1, feat3):
        print("✅ SUCCESS: Feature vectors are identical across different contexts.")
    else:
        print("❌ FAILURE: Feature vectors differ. Stable indexing is NOT working.")

    # Manual verification of hash
    clean_role = "DEVELOPER"
    expected_hash = zlib.adler32(clean_role.encode()) % 1000 / 1000.0
    print(f"Expected Hash for '{clean_role}': {expected_hash}")
    
    if abs(feat1[8] - expected_hash) < 1e-6:
        print("✅ SUCCESS: Hash value matches expected zlib output.")
    else:
        print(f"❌ FAILURE: Hash value {feat1[8]} != {expected_hash}.")

if __name__ == "__main__":
    verify_consistency()
