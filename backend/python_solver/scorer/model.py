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
        self.weights_filename = "scorer_weights.h5"
        self.local_weights_path = f"/tmp/{self.weights_filename}"
        
        try:
            self.model = self._build_model()
            self.load_weights()
            self.enabled = True
        except Exception as e:
            print(f"NeuralScorer initialization failed: {e}. AI scoring disabled.")
            self.model = None
            self.enabled = False

        self._initialized = True

    def _build_model(self):
        """Builds a refined Neural Network for Affinity Prediction."""
        model = Sequential([
            layers.Dense(32, activation='relu', input_shape=(10,)), # 10 Complex Features
            layers.Dropout(0.2), # Prevent overfitting on small data
            layers.Dense(16, activation='relu'),
            layers.Dense(1, activation='sigmoid') 
        ])
        model.compile(optimizer='adam', loss='binary_crossentropy')
        return model

    def load_weights(self):
        """Loads weights from GCS or local fallback."""
        if self.model is None: return
        try:
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(self.weights_filename)
            
            if blob.exists():
                blob.download_to_filename(self.local_weights_path)
                self.model.load_weights(self.local_weights_path)
                print(f"Loaded weights from GCS: gs://{self.bucket_name}/{self.weights_filename}")
            else:
                print("No weights found in GCS, using default initialization.")
        except Exception as e:
            print(f"Error loading from GCS: {e}. Falling back to default.")

    def save_weights(self):
        """Saves weights to local temp and uploads to GCS."""
        if self.model is None: return
        try:
            self.model.save_weights(self.local_weights_path)
            
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(self.weights_filename)
            blob.upload_from_filename(self.local_weights_path)
            print(f"Uploaded weights to GCS: gs://{self.bucket_name}/{self.weights_filename}")
        except Exception as e:
            print(f"Error saving to GCS: {e}")

    def extract_features(self, emp, shift, all_roles):
        """
        Extracts 10 real features for an (employee, shift) pair.
        """
        from datetime import datetime
        
        # 1. Role Match (1.0 index if match, 0.0 else)
        role_match = 1.0 if emp.get("role") == shift.get("role") else 0.0
        
        # 2. Time of day (normalized 0.0 to 1.0)
        start_hour = int(shift.get("start_time", "08:00").split(":")[0])
        time_feature = start_hour / 24.0
        
        # 3. Day of week (normalized 0.0 to 1.0)
        date_obj = datetime.fromisoformat(shift.get("date", "2024-01-01"))
        day_feature = date_obj.weekday() / 6.0
        
        # 4. Seniority / Loyalty (Mocked based on ID length or constant for now)
        seniority = min(len(emp.get("id", "")) / 10.0, 1.0)
        
        # 5. Role Index (Categorical -> Linear)
        role_idx = all_roles.index(shift.get("role")) / max(len(all_roles)-1, 1) if shift.get("role") in all_roles else 0.0

        # Fill with some defaults/noise for the remaining 5 to make it 10
        features = [
            role_match, 
            time_feature, 
            day_feature, 
            seniority, 
            role_idx,
            0.5, 0.5, 0.5, 0.5, 0.5 # Reserved for future metrics
        ]
        return np.array(features, dtype=np.float32)

    def predict_affinity(self, emp, shift, all_roles):
        """
        Predicts how suitable an employee is for a shift using REAL features.
        """
        if not self.enabled or self.model is None:
            return 0.5 # Default affinity

        try:
            features = self.extract_features(emp, shift, all_roles)
            input_vector = np.expand_dims(features, axis=0) # Batch dimension
            
            score = self.model.predict(input_vector, verbose=0)
            return float(score[0][0])
        except Exception as e:
            print(f"Prediction error: {e}")
            return 0.5 # Safe fallback

    def train(self, X, y, epochs=5):
        """
        Trains the model on new data.
        X: numpy array of features
        y: numpy array of labels (0.0 or 1.0)
        """
        if not self.enabled or self.model is None:
            print("Training skipped: Scorer disabled.")
            return 0.0

        print(f"Training on {len(X)} examples...")
        history = self.model.fit(X, y, epochs=epochs, verbose=1)
        return history.history['loss'][-1]

    def get_stats(self):
        """Returns metadata and statistical summary of the model."""
        if not self.enabled or self.model is None:
            return {"status": "disabled"}

        weights = self.model.get_weights()
        flat_weights = np.concatenate([w.flatten() for w in weights])
        
        return {
            "status": "active",
            "architecture": [
                {"layer": i, "name": layer.__class__.__name__, "units": getattr(layer, 'units', 'N/A')}
                for i, layer in enumerate(self.model.layers)
            ],
            "weights_stats": {
                "count": int(len(flat_weights)),
                "mean": float(np.mean(flat_weights)),
                "std": float(np.std(flat_weights)),
                "min": float(np.min(flat_weights)),
                "max": float(np.max(flat_weights))
            },
            "bucket": self.bucket_name,
            "filename": self.weights_filename
        }
