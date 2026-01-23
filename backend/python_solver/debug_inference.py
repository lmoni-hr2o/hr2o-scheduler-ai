import sys
import os
import numpy as np

# Add current directory to path
sys.path.append(os.getcwd())

# Mocks to allow importing NeuralScorer locally without GC dependencies if needed,
# BUT we want to try to load real weights if we can, or just check the feature extraction logic.
# Since we know verify_mappings worked for extraction, the issue might be the MODEL itself predicting 0.

try:
    from scorer.model import NeuralScorer
except ImportError:
    # If standard import fails due to dependencies, we resort to the mocked version
    # But usually we want to see the REAL model behavior.
    pass

def debug_inference():
    print("--- DEBUG INFERENCE ---")
    
    # 1. Instantiate Scorer
    try:
        scorer = NeuralScorer()
    except Exception as e:
        print(f"Failed to init scorer: {e}")
        return

    # 2. Check if Model is loaded
    if scorer.model is None:
        print("Model is NONE. Trying to load default/mock...")
        scorer.model = scorer._build_model()
        # We assume weights might be missing locally, so it's an untrained model.
        # An untrained model (sigmoid output) should output ~0.5.
    
    print("Model ready.")
    
    # 3. Create a perfect match scenario
    emp = {"role": "WORKER", "bornDate": "1990-01-01", "id": "TEST_EMP"}
    shift = {"role": "WORKER", "date": "2024-01-01", "start_time": "08:00"}
    all_roles = ["WORKER"]
    
    # 4. Extract Features
    features = scorer.extract_features(emp, shift, all_roles)
    print(f"Features: {features}")
    
    # 5. Predict
    batch = np.array([features])
    pred = scorer.model.predict(batch, verbose=0)
    print(f"Prediction: {pred[0][0]}")
    
    if pred[0][0] < 0.01:
        print("⚠️  Prediction is near ZERO. This confirms the model output is low.")
    else:
        print(f"Prediction is {pred[0][0]:.4f}. If this is high, then Cloud Run environment has different weights.")

if __name__ == "__main__":
    debug_inference()
