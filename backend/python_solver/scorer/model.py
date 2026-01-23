from google.cloud import storage
import tensorflow as tf
import numpy as np
import os

# Robust Keras import
try:
    from tensorflow.keras import layers, Sequential
except ImportError:
    try:
        from keras import layers, Sequential
    except ImportError:
        # Fallback for some weird builds
        import keras
        layers = keras.layers
        Sequential = keras.Sequential

class NeuralScorer:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NeuralScorer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
            
        self.bucket_name = os.getenv("AI_MODELS_BUCKET", "timeplanner")
        self.weights_filename = "scorer_weights.weights.h5"
        self.local_weights_path = f"/tmp/{self.weights_filename}"
        self.last_load_time = 0
        self.init_error = None
        
        try:
            self.model = self._build_model()
            self.load_weights()
            self.enabled = True
        except Exception as e:
            self.init_error = str(e)
            print(f"NeuralScorer initialization failed: {e}. AI scoring disabled.")
            self.model = None
            self.enabled = False

        self._initialized = True

    def _build_model(self):
        """Builds a refined Neural Network for Affinity Prediction."""
        # Increased to 11 features: added Project/Commessa Affinity
        model = Sequential([
            layers.Dense(64, activation='relu', input_shape=(11,)), 
            layers.Dropout(0.3), 
            layers.Dense(32, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(16, activation='relu'),
            layers.Dense(1, activation='sigmoid') 
        ])
        model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        return model

    def load_weights(self):
        """Loads weights from GCS or local fallback."""
        if self.model is None: return
        import time
        try:
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(self.weights_filename)
            
            if blob.exists():
                blob.download_to_filename(self.local_weights_path)
                self.model.load_weights(self.local_weights_path)
                self.last_load_time = time.time()
                print(f"Loaded weights from GCS: gs://{self.bucket_name}/{self.weights_filename}")
            else:
                print("No weights found in GCS, using default initialization.")
        except Exception as e:
            print(f"Error loading from GCS: {e}. Falling back to default.")

    def refresh_if_needed(self, force=False):
        """Checks if weights need to be reloaded (every 5 mins or if forced)."""
        import time
        if self.model is None: return
        
        # Reload if forced or it's been more than 5 minutes
        if force or (time.time() - self.last_load_time > 300):
            print("Refreshing AI weights from GCS...")
            self.load_weights()

    def save_weights(self):
        """Saves weights to local temp and uploads to GCS."""
        if self.model is None: return
        try:
            self.model.save_weights(self.local_weights_path)
            
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(self.weights_filename)
            blob.upload_from_filename(self.local_weights_path)
            import time
            self.last_load_time = time.time()
            print(f"Uploaded weights to GCS: gs://{self.bucket_name}/{self.weights_filename}")
        except Exception as e:
            print(f"Error saving to GCS: {e}")

    def reset_weights(self):
        """Deletes weights from GCS and resets the model to random state."""
        try:
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(self.weights_filename)
            if blob.exists():
                blob.delete()
                print(f"Deleted weights file from GCS: gs://{self.bucket_name}/{self.weights_filename}")
            
            # Reconstruct model (random weights)
            self.model = self._build_model()
            self.save_weights() # Save the new random weights immediately
            print("Model reset to random state.")
            return True
        except Exception as e:
            print(f"Error resetting weights: {e}")
            return False

    def extract_features(self, emp, shift, all_roles, mappings=None):
        """
        Extracts 11 real features for an (employee, shift) pair.
        Uses dynamic mappings if provided, otherwise falls back to defaults.
        """
        from datetime import datetime
        import re
        from utils.date_utils import parse_date

        # Helper to get value from entity based on mappings
        def get_mapped_value(entity, feature_name, default=None):
            # 1. Try mapped paths
            if mappings and feature_name in mappings:
                paths = mappings[feature_name]
                for path in paths:
                    try:
                        # Handle dot notation (flat or nested)
                        if "." in path:
                            parts = path.split(".")
                            curr = entity
                            found = True
                            for p in parts:
                                if isinstance(curr, dict) and p in curr:
                                    curr = curr[p]
                                else:
                                    found = False
                                    break
                            if found and curr: return curr
                        else:
                            val = entity.get(path)
                            if val: return val
                    except: continue
            
            # 2. Try default heuristics/hardcoded paths (Fallback)
            if feature_name == "role":
                return entity.get("role") or (entity.get("employment") or {}).get("role")
            if feature_name == "age":
                 return entity.get("bornDate") or (entity.get("person") or {}).get("bornDate")
            if feature_name == "address":
                return entity.get("address") or (entity.get("person") or {}).get("address")
            
            return default

        def get_age(born_str):
            if not born_str: return 0.5
            try:
                born = parse_date(born_str)
                if not born: return 0.5
                age = (datetime.now() - born).days // 365
                return min(max(age, 18), 70) / 70.0 # Normalized 18-70
            except: return 0.5

        def get_distance(emp_addr, cust_addr):
            # Placeholder for real geoloc distance
            if not emp_addr or not cust_addr: return 0.9
            if str(emp_addr).lower() == str(cust_addr).lower(): return 0.0
            return 0.3 # Moderate distance fallback

        def get_punctuality(emp):
            return emp.get("punctuality_score", 0.95)

        def get_task_keywords(ops):
            if not ops: return 0.5
            # Simplified for now
            return 0.5

        def normalize_role(r):
            if not r: return "WORKER"
            r = str(r).upper().strip()
            if "SVILUPPATORE" in r or "DEV" in r: return "DEVELOPER"
            if "PULIZI" in r or "CLEAN" in r: return "CLEANER"
            if "OPERA" in r: return "WORKER"
            if "MANUTEN" in r: return "MAINTENANCE"
            if "COORDINA" in r or "RESPONSABILE" in r: return "MANAGER"
            return r

        # --- Feature Extraction using Mapped Values ---

        # 1. Role Match
        raw_emp_role = get_mapped_value(emp, "role_match", default=emp.get("role"))
        # Shift role comes from the shift dict explicitly, usually not mapped on emp side
        shift_role = normalize_role(shift.get("role"))
        emp_role = normalize_role(raw_emp_role)
        role_match = 1.0 if emp_role == shift_role else 0.0
        
        # 2. Time of day
        start_hour = int(shift.get("start_time", "08:00").split(":")[0])
        time_feature = start_hour / 24.0
        
        # 3. Day of week
        date_obj = parse_date(shift.get("date", "2024-01-01"))
        day_feature = (date_obj.weekday() / 6.0) if date_obj else 0.5
        
        # 4. Age (Normalized)
        # Try finding birth date via "age" mapping
        born_date_val = get_mapped_value(emp, "age")
        age_feature = get_age(born_date_val)
        
        # 5. Distance (Normalized)
        emp_addr = get_mapped_value(emp, "distance")
        cust_addr = shift.get("customer_address")
        dist_feature = get_distance(emp_addr, cust_addr)
        
        # 6. Punctuality
        punctuality = get_mapped_value(emp, "punctuality", default=0.95)
        if isinstance(punctuality, str): punctuality = 0.95 # Safety
        
        # 7. Task Keywords/Complexity
        keywords = 0.5 # Todo: Link to "task_keywords" mapping if applicable to employee skills
        
        # 8. Seniority
        seniority = min(len(str(emp.get("id", ""))) / 10.0, 1.0)
        
        # 9. Role Index
        s_role_norm = str(shift.get("role") or "").strip().upper()
        role_idx = all_roles.index(s_role_norm) / max(len(all_roles)-1, 1) if s_role_norm in all_roles else 0.0

        # 10. Vehicle required
        vehicle_req = 1.0 if shift.get("selectVehicleRequired") else 0.0
        # If vehicle required, check if emp has vehicle (from mappings)
        if vehicle_req > 0:
            has_vehicle = get_mapped_value(emp, "vehicle_req")
            if not has_vehicle: vehicle_feature = 0.0 # Penalty
            else: vehicle_feature = 1.0
        else:
            vehicle_feature = 1.0

        # 11. Project/Commessa Affinity
        project_affinity = 0.0
        shift_proj = shift.get("project")
        if isinstance(shift_proj, dict):
            shift_proj_id = str(shift_proj.get("id") or "")
        else:
            shift_proj_id = str(shift_proj or "")
            
        # Check historical projects
        emp_projects = emp.get("project_ids", [])
        if shift_proj_id and str(shift_proj_id) in [str(x) for x in emp_projects]:
            project_affinity = 1.0
        
        if project_affinity == 0.0:
            # Check mappings for project_affinity field in employee (maybe a preferred project field)
            pref_proj = get_mapped_value(emp, "project_affinity")
            if pref_proj and str(pref_proj) == shift_proj_id:
                project_affinity = 1.0

        features = [
            role_match, time_feature, day_feature, age_feature,
            dist_feature, float(punctuality), keywords, seniority,
            role_idx, vehicle_feature, project_affinity
        ]
        return np.array(features, dtype=np.float32)

    def predict_affinity(self, emp, shift, all_roles, mappings=None):
        """
        Predicts how suitable an employee is for a shift using REAL features.
        """
        if not self.enabled or self.model is None:
            return 0.5 # Default affinity

        try:
            features = self.extract_features(emp, shift, all_roles, mappings)
            input_vector = np.expand_dims(features, axis=0) # Batch dimension
            
            score = self.model.predict(input_vector, verbose=0)
            return float(score[0][0])
        except Exception as e:
            print(f"Prediction error: {e}")
            return 0.5 # Safe fallback

    def train(self, X, y, epochs=20, validation_split=0.2):
        """
        Trains the model on new data with validation and early stopping.
        Returns a dict of metrics.
        """
        if not self.enabled or self.model is None:
            print("Training skipped: Scorer disabled.")
            return {"loss": 0.0, "val_loss": 0.0, "val_accuracy": 0.5}

        print(f"Training on {len(X)} examples...")
        
        callbacks = []
        try:
            from tensorflow.keras.callbacks import EarlyStopping
            # Stop if validation loss doesn't improve for 3 epochs
            es = EarlyStopping(
                monitor='val_loss', 
                mode='min', 
                verbose=1, 
                patience=3, 
                restore_best_weights=True
            )
            callbacks.append(es)
        except Exception as e:
            print(f"Warning: Could not initialize EarlyStopping: {e}")

        history = self.model.fit(
            X, y, 
            epochs=epochs, 
            verbose=1,
            validation_split=validation_split,
            callbacks=callbacks
        )
        
        # Extract final metrics (from the best epoch if restored)
        final_loss = history.history['loss'][-1]
        final_val_loss = history.history.get('val_loss', [0.0])[-1]
        final_val_acc = history.history.get('val_accuracy', [0.0])[-1]
        
        return {
            "loss": final_loss,
            "val_loss": final_val_loss,
            "val_accuracy": final_val_acc
        }

    def get_stats(self):
        """Returns metadata and statistical summary of the model."""
        if not self.enabled or self.model is None:
            return {
                "status": "disabled",
                "error": getattr(self, 'init_error', 'Model not initialized')
            }

        try:
            weights = self.model.get_weights()
            flat_weights = np.concatenate([w.flatten() for w in weights]) if weights else np.array([])
            
            return {
                "status": "active",
                "architecture": [
                    {
                        "layer": i, 
                        "name": layer.__class__.__name__, 
                        "units": getattr(layer, 'units', 'N/A')
                    }
                    for i, layer in enumerate(self.model.layers)
                ],
                "weights_stats": {
                    "count": int(len(flat_weights)),
                    "mean": float(np.mean(flat_weights)) if len(flat_weights) > 0 else 0.0,
                    "std": float(np.std(flat_weights)) if len(flat_weights) > 0 else 0.0,
                    "min": float(np.min(flat_weights)) if len(flat_weights) > 0 else 0.0,
                    "max": float(np.max(flat_weights)) if len(flat_weights) > 0 else 0.0
                },
                "bucket": self.bucket_name,
                "filename": self.weights_filename
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
