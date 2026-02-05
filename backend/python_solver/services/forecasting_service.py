
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from google.cloud import datastore
from utils.datastore_helper import get_db

class ForecastingService:
    def __init__(self, environment: str):
        self.environment = environment
        self.db = get_db(namespace=environment)
        self.client = self.db.client
        self._df_cache = None
        self._risk_model_cache = None
        
        import os, psutil, gc
        self._proc = psutil.Process(os.getpid())
        self._gc = gc
        self._mem_limit_mb = 7000 # Safety cap

    def _log_mem(self, label):
        import sys
        mem = self._proc.memory_info().rss / (1024 * 1024)
        print(f"DEBUG: [ForecastingService] {label} | Memory: {mem:.1f} MB")
        sys.stdout.flush()
        if mem > self._mem_limit_mb:
             print(f"CRITICAL: Memory limit reached ({mem:.1f} MB). Aborting to prevent OOM.")
             raise MemoryError(f"Engine Memory Overload ({mem:.1f} MB)")

    def _get_periods_from_datastore(self) -> List[Dict[str, Any]]:
        """
        Fetches Period entities from Datastore for the current environment.
        """
        query = self.client.query(kind="Period")
        query.add_filter("environment", "=", self.environment)
        # Sort by tmregister is good practice for time-series, but we sort in DF anyway
        return list(query.fetch())

    def _parse_period_to_df(self, periods: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Converts raw Datastore Period entities into a clean DataFrame for ML.
        Mimics the 'master' dataframe construction in forecast_hr.py.
        """
        rows = []
        for p in periods:
            try:
                # Basic fields
                qt = p.get("tmregister") or p.get("beginTimePlace", {}).get("time")
                if not qt:
                    continue
                if isinstance(qt, datetime):
                    data = qt
                elif isinstance(qt, str):
                    # Attempt parse if string
                    try:
                        data = datetime.fromisoformat(qt.replace("Z", "+00:00"))
                    except:
                        continue 
                else:
                    continue 

                # Extract IDs
                # We need safe access as structure might vary
                act = p.get("activities", {}) or {}
                if isinstance(act, dict):
                    commessa = str(act.get("id") or act.get("code") or "")
                else:
                    commessa = ""
                
                emp = p.get("employment", {}) or {}
                if isinstance(emp, dict):
                    dipendente = str(emp.get("id") or emp.get("fullName") or "") # ID is better for consistency
                else:
                    dipendente = ""

                # Hours calculation
                start = p.get("tmentry") or p.get("beginTimePlace", {}).get("time")
                end = p.get("tmexit") or p.get("endTimePlace", {}).get("time")
                
                # Parse strings if necessary
                if start and isinstance(start, str):
                    try: start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    except: start = None
                if end and isinstance(end, str):
                    try: end = datetime.fromisoformat(end.replace("Z", "+00:00"))
                    except: end = None
                
                ore_lavorate = 0.0
                if start and end and isinstance(start, datetime) and isinstance(end, datetime):
                    diff = (end - start).total_seconds()
                    ore_lavorate = diff / 3600.0
                
                # Absence flag (heuristic based on typeActivity or specific flags in Period if available)
                # For now, we assume if Hours > 0 it's WORK.
                # If we had explicit absence records they would be separate.
                # Previsionale had "is_assenza" from Excel. Here we might need logic.
                # Placeholder: If 'typeActivity' == 'ASSENZA' or similar.
                is_assenza = 0
                type_act = str(act.get("typeActivity") or "").upper()
                if "ASSENZA" in type_act or "MALATTIA" in type_act or "FERIE" in type_act:
                    is_assenza = 1
                    ore_lavorate = 0 # Absence doesn't count as workload demand usually, but counts for risk

                # Start Hour for "Real Time" learning
                start_hour = 8.0 # Default
                if start and isinstance(start, datetime):
                     start_hour = start.hour + (start.minute / 60.0)

                rows.append({
                    "data": pd.Timestamp(data.date()),
                    "societa": self.environment, # Using environment as Proxy for Società
                    "commessa": commessa,
                    "dipendente": dipendente,
                    "ore_lavorate": float(ore_lavorate),
                    "start_hour": float(start_hour),
                    "accessi": 1,
                    "is_assenza": is_assenza
                })
            except Exception as e:
                print(f"DEBUG: Error parsing period {p.key.id if p.key else '?'}: {e}")
                continue
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        # Sorting
        df = df.sort_values("data")
        return df

    # --- Feature Engineering (Ported from forecast_hr.py) ---
    def _add_calendar_features(self, df: pd.DataFrame, date_col="data") -> pd.DataFrame:
        # Avoid full copy if possible, but Pandas warns on modifications to slices
        # We'll stick to a shallow operation where possible
        df["dow"] = df[date_col].dt.dayofweek.astype(np.int8)
        iso = df[date_col].dt.isocalendar()
        df["week"] = iso.week.astype(np.int16)
        df["woy"] = iso.week.astype(np.int16)
        df["month"] = df[date_col].dt.month.astype(np.int8)
        df["day"] = df[date_col].dt.day.astype(np.int8)
        return df

    def _add_time_index(self, df: pd.DataFrame, date_col="data") -> pd.DataFrame:
        if len(df) == 0: return df
        base = df[date_col].min()
        df["t_index"] = (df[date_col] - base).dt.days.astype(np.int32)
        return df

    def _add_rolling_features(self, df: pd.DataFrame, group_cols, target_col: str, windows=(7, 14, 28)) -> pd.DataFrame:
        if len(df) == 0: return df
        df = df.sort_values(group_cols + ["data"])
        for w in windows:
            # CRITICAL: observed=True prevents memory explosion on categorical groupby
            df[f"{target_col}_rollmean_{w}"] = (
                df.groupby(group_cols, observed=True)[target_col]
                  .transform(lambda s: s.rolling(w, min_periods=1).mean().astype(np.float32))
            )
        return df

    def _train_regressor(self, df: pd.DataFrame, target: str, cat_cols, num_cols):
        # Handle empty
        if len(df) < 10: return None
        self._log_mem(f"Start training regressor on {len(df)} rows")
        
        # Use OrdinalEncoder to keep memory low (No Cartesian expansion)
        pre = ColumnTransformer(
            [("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cat_cols),
             ("num", "passthrough", num_cols)],
            remainder="drop"
        )
        
        # Tell HGBC which features are categorical (first N columns from Transformer)
        cat_mask = [True] * len(cat_cols) + [False] * len(num_cols)
        model = HistGradientBoostingRegressor(
            max_depth=5, 
            learning_rate=0.05, 
            max_iter=100, # Faster training for response time
            random_state=42,
            categorical_features=cat_mask
        )
        
        pipe = Pipeline([("pre", pre), ("model", model)])
        pipe.fit(df[cat_cols + num_cols], df[target])
        self._log_mem("Regressor training complete")
        return pipe

    def _train_classifier(self, df: pd.DataFrame, target: str, cat_cols, num_cols):
        if len(df) < 10: return None
        self._log_mem(f"Start training classifier on {len(df)} rows")
        # Check if we have at least 2 classes
        if df[target].nunique() < 2: return None

        pre = ColumnTransformer(
            [("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cat_cols),
             ("num", "passthrough", num_cols)],
            remainder="drop"
        )
        
        cat_mask = [True] * len(cat_cols) + [False] * len(num_cols)
        # Using HistGradientBoostingClassifier instead of LogisticRegression 
        # because it handles ordinal categorical features perfectly (No dense OneHot needed)
        clf = HistGradientBoostingClassifier(
            max_depth=5, 
            max_iter=50, 
            class_weight="balanced", 
            categorical_features=cat_mask,
            random_state=42
        )
        
        pipe = Pipeline([("pre", pre), ("model", clf)])
        pipe.fit(df[cat_cols + num_cols], df[target])
        self._log_mem("Classifier training complete")
        return pipe

    # --- Public Methods ---

    def get_base_dataframe(self) -> pd.DataFrame:
        """
        Ultra-efficient fetch using projections and minimal object creation.
        Uses Categorical dtypes to drastically reduce memory footprint.
        """
        if self._df_cache is not None:
            return self._df_cache
        
        self._log_mem("Start get_base_dataframe (Namespaced Query)")
        lookback_days = 45 
        
        # 1. NAMESPACED QUERY (No filters to avoid index 400 errors)
        # Using environment namespace isolation (setup in __init__) 
        query = self.client.query(kind="Period")
        
        # 2. STRICT PROJECTION (Crucial: Reduces RAM by ~90% per record)
        # By NOT using a date filter on the server, we don't need a composite index for projection.
        # We fetch all (within limit) but very "skinny" records.
        try:
            query.projection = [
                "tmregister", "tmentry", "tmexit", 
                "activities.id", "activities.code", "activities.typeActivity",
                "employment.id", "employment.fullName"
            ]
            print("DEBUG: Using Projected Fetch (No-Filter Strategy)...")
            fetch_limit = 50000 
        except Exception as e:
            # Should not happen for Kind-only projection, but safe fallback
            print(f"WARNING: Projection failed ({e}). Using Full Fetch with LOW Limit.")
            fetch_limit = 3000 
            
        print(f"DEBUG: Streaming NAMESPACED periods for {self.environment} (Fetch Limit: {fetch_limit})...")
        
        # 45 days is enough for trends while saving ~25% RAM compared to 60 days
        cutoff_date = (datetime.now() - timedelta(days=lookback_days)).date()
        
        dates_raw = []
        commesse = []
        dipendenti = []
        ore = []
        start_hours = []
        assenza = []
        
        count = 0
        total_scanned = 0
        use_projection = True # Default to Try Projection
        
        
        # --- KEYS-ONLY FETCH (Revision 240) ---
        # Strategy: Fetch LIGHTWEIGHT keys first (limit 50,000 keys ~ 5MB RAM).
        # Then fetch ACTUAL entities in tiny micro-batches of 50 using get_multi.
        # This completely bypasses Query Iterator buffering issues.
        
        try:
            print(f"DEBUG: Starting KEYS-ONLY query (Limit: {fetch_limit})...")
            query = self.client.query(kind="Period")
            query.keys_only() # Crucial!
            
            # Fetch all keys (safe, keys are tiny)
            all_keys = list(query.fetch(limit=fetch_limit))
            total_keys = len(all_keys)
            print(f"DEBUG: Found {total_keys} keys. Starting MICRO-BATCH retrieval...")
            
            # Process in Micro-Batches of 100
            # 100 records * 1.5MB = ~150MB max RAM spike per batch.
            micro_batch_size = 100
            
            for i in range(0, total_keys, micro_batch_size):
                chunk_keys = all_keys[i : i + micro_batch_size]
                
                try:
                    # Fetch Full Entities by Key
                    entities = self.client.get_multi(chunk_keys)
                    
                    # Process
                    for p in entities:
                         try:
                            # 0. Safety
                            if not p: continue

                            # 1. Date 
                            qt = p.get("tmregister")
                            if not qt: continue
                            if isinstance(qt, str):
                                dt = datetime.fromisoformat(qt.replace("Z", "+00:00"))
                            else: dt = qt
                            
                            # PYTHON DATE FILTER
                            if dt.date() < cutoff_date:
                                continue
                            
                            count += 1
                            
                            # 2. Activity / Employee
                            act = p.get("activities") or {} 
                            if not isinstance(act, dict): act = {}
                            comm = str(act.get("id") or act.get("code") or "")
                            
                            emp = p.get("employment") or {}
                            if not isinstance(emp, dict): emp = {}
                            dip = str(emp.get("id") or emp.get("fullName") or "")
                            
                            # 3. Hours
                            st = p.get("tmentry")
                            en = p.get("tmexit")
                            if st and isinstance(st, str): st = datetime.fromisoformat(st.replace("Z", "+00:00"))
                            if en and isinstance(en, str): en = datetime.fromisoformat(en.replace("Z", "+00:00"))
                            
                            h = 0.0
                            sh = 8.0
                            if st:
                                sh = st.hour + (st.minute / 60.0)
                                if en: h = (en - st).total_seconds() / 3600.0
                            
                            # 4. Absence
                            type_a = str(act.get("typeActivity") or "").upper()
                            is_abs = 1 if any(x in type_a for x in ["ASSENZA", "MALATTIA", "FERIE"]) else 0
                            if is_abs: h = 0.0
                            
                            # Collect
                            dates_raw.append(dt.date())
                            commesse.append(comm)
                            dipendenti.append(dip)
                            ore.append(h)
                            start_hours.append(sh)
                            assenza.append(is_abs)
                            
                         except Exception:
                             continue
                    
                    # Memory Check
                    if (i + len(chunk_keys)) % 1000 == 0:
                        mem = self._proc.memory_info().rss / (1024 * 1024)
                        print(f"DEBUG: Processed {i} keys | Memory: {mem:.1f} MB")
                        if mem > 6000:
                             print("CRITICAL: Memory Limit. Stopping.")
                             break
                             
                    # Cleanup
                    del entities
                    del chunk_keys
                    
                except Exception as e_batch:
                    print(f"ERROR processing micro-batch {i}: {e_batch}")
                    continue
                    
            # Cleanup Keys
            del all_keys
            import gc
            gc.collect()
            
        except Exception as e_query:
            print(f"CRITICAL: Keys fetch failed: {e_query}")
        
        print(f"DEBUG: [ForecastingService] Data fetch complete. Total: {count} records.")

        print(f"DEBUG: Data collected. Count: {count}, Valid: {len(dates_raw)}")
        
        if not dates_raw:
            self._df_cache = pd.DataFrame()
            return self._df_cache
            
        # Build DataFrame with MEMORY EFFICIENT DTYPES
        # 'category' is used for strings with many repetitions (Activities, Employees)
        df = pd.DataFrame({
            "data": pd.to_datetime(dates_raw),
            "societa": pd.Series([self.environment] * len(dates_raw), dtype="category"),
            "commessa": pd.Series(commesse, dtype="category"),
            "dipendente": pd.Series(dipendenti, dtype="category"),
            "ore_lavorate": np.array(ore, dtype=np.float32),
            "start_hour": np.array(start_hours, dtype=np.float32),
            "accessi": np.ones(len(dates_raw), dtype=np.int8),
            "is_assenza": np.array(assenza, dtype=np.int16)
        })
        
        # Immediate cleanup
        del dates_raw, commesse, dipendenti, ore, start_hours, assenza
        self._gc.collect()
        
        df = df.sort_values("data")
        self._df_cache = df
        self._log_mem("DataFrame finalized (Categorical)")
        return df

    def _parse_single_period(self, p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extracted logic from old _parse_period_to_df to process a single record.
        """
        try:
            # Basic fields
            qt = p.get("tmregister") or p.get("beginTimePlace", {}).get("time")
            if not qt: return None
            
            if isinstance(qt, datetime): data = qt
            elif isinstance(qt, str):
                try: data = datetime.fromisoformat(qt.replace("Z", "+00:00"))
                except: return None
            else: return None

            act = p.get("activities", {}) or {}
            commessa = str(act.get("id") or act.get("code") or "") if isinstance(act, dict) else ""
            
            emp = p.get("employment", {}) or {}
            dipendente = str(emp.get("id") or emp.get("fullName") or "") if isinstance(emp, dict) else ""

            start = p.get("tmentry") or p.get("beginTimePlace", {}).get("time")
            end = p.get("tmexit") or p.get("endTimePlace", {}).get("time")
            
            if start and isinstance(start, str):
                try: start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                except: start = None
            if end and isinstance(end, str):
                try: end = datetime.fromisoformat(end.replace("Z", "+00:00"))
                except: end = None
            
            ore_lavorate = 0.0
            if start and end and isinstance(start, datetime) and isinstance(end, datetime):
                ore_lavorate = (end - start).total_seconds() / 3600.0
            
            is_assenza = 0
            type_act = str(act.get("typeActivity") or "").upper()
            if any(x in type_act for x in ["ASSENZA", "MALATTIA", "FERIE"]):
                is_assenza = 1
                ore_lavorate = 0.0

            start_hour = 8.0
            if start and isinstance(start, datetime):
                 start_hour = start.hour + (start.minute / 60.0)

            return {
                "data": pd.Timestamp(data.date()),
                "societa": self.environment,
                "commessa": commessa,
                "dipendente": dipendente,
                "ore_lavorate": float(ore_lavorate),
                "start_hour": float(start_hour),
                "accessi": 1,
                "is_assenza": is_assenza
            }
        except: return None

    def predict_demand(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Trains model on history and predicts daily demand (ore_tot) for each active Activity.
        Returns list of daily demand objects.
        """
        df = self.get_base_dataframe()
        
        if df.empty:
            print("WARNING: No data for forecasting.")
            return []

        # Aggregate Daily Demand per Activity
        # CRITICAL: observed=True prevents Cartesian OOM with large category lists (PROFER scale)
        comm_daily = df.groupby(["societa", "commessa", "data"], as_index=False, observed=True).agg(
            ore_tot=("ore_lavorate", "sum")
        )
        
        comm_daily = self._add_calendar_features(comm_daily)
        comm_daily = self._add_time_index(comm_daily)
        comm_daily = self._add_rolling_features(comm_daily, ["societa", "commessa"], "ore_tot", windows=(7, 28))
        
        # Fill NA caused by rolling
        for c in comm_daily.columns:
            if "rollmean" in c:
                comm_daily[c] = comm_daily[c].fillna(0)

        cat_cols = ["societa", "commessa", "dow", "month", "woy"]
        num_cols = [c for c in comm_daily.columns if "rollmean" in c] + ["day", "week", "t_index"]
        
        from utils.status_manager import update_status
        update_status(message="Analisi storica della domanda...", progress=0.25, phase="OPTIMIZATION")
        
        # Train
        model = self._train_regressor(comm_daily, "ore_tot", cat_cols, num_cols)
        if not model:
            print("WARNING: Not enough data to train demand model.")
            update_status(log="Dati insufficienti per il modello ML, uso fallback statico.")
            return []
        
        update_status(message="Previsione fabbisogno neurale...", progress=0.3, phase="OPTIMIZATION")

        # Loop di previsione (Date target)
        horizon = pd.date_range(start_date, end_date, freq="D")
        
        # We need to construct the future dataframe.
        # We take all known commesse
        active_commesse = comm_daily["commessa"].unique()
        
        predictions = []
        
        # Stats generation: Duration and Start Hour
        base_date = comm_daily["data"].min()
        
        # Duration: filter out potential zero-hour artifacts
        duration_stats = df[df["ore_lavorate"] > 0].groupby("commessa", observed=True)["ore_lavorate"].median().to_dict()
        
        # Start stats: simple median per activity
        start_stats = df.groupby("commessa", observed=True)["start_hour"].median().to_dict()
        
        # Rilevamento Giorni Attivi (Active DOW): quali giorni hanno effettivamente lavoro?
        # Un giorno è attivo se ha una somma di ore storica > 0
        active_dows = comm_daily.groupby("dow")["ore_lavorate"].sum()
        active_dows = active_dows[active_dows > 0].index.tolist()
        print(f"DEBUG: Giorni della settimana storicamente attivi: {active_dows}")
        
        # EXPERIMENTAL: Median per activity AND DOW if enough data exists (>5 records per group)
        # This allows for "Saturday starts later" patterns.
        dow_start_stats = df.groupby(["commessa", "dow"], observed=True)["start_hour"].agg(["median", "count"])
        dow_start_map = {}
        for (comm, dow), row in dow_start_stats.iterrows():
            if row["count"] >= 5:
                dow_start_map[(comm, dow)] = float(row["median"])

        # Vectorized Future State Generation
        prediction_rows = []
        for comm in active_commesse:
            if comm not in last_states.index: continue
            last_state = last_states.loc[comm]
            # Fallback to general median if DOW-specific isn't stable
            base_typical_start = start_stats.get(comm, 8.0)
            typical_duration = max(2.0, min(10.0, duration_stats.get(comm, 4.0))) # Clip to reasonable range
            
            for date_curr in horizon:
                iso = date_curr.isocalendar()
                dow = date_curr.dayofweek
                
                # Weekend Fix: Salta se il giorno (DOW) non è storicamente attivo per questa azienda
                if dow not in active_dows: continue
                
                # Try to get DOW specific start, else use activity median
                typical_start = dow_start_map.get((comm, dow), base_typical_start)

                row = {
                    "societa": self.environment,
                    "commessa": comm,
                    "data": date_curr,
                    "dow": dow,
                    "month": date_curr.month,
                    "day": date_curr.day,
                    "week": int(iso.week),
                    "woy": int(iso.week),
                    "t_index": (date_curr - base_date).days,
                    "typical_start": typical_start,
                    "typical_duration": typical_duration
                }
                for col in num_cols:
                    if "rollmean" in col: row[col] = last_state[col]
                prediction_rows.append(row)

        if not prediction_rows: return []

        X_future = pd.DataFrame(prediction_rows)
        # Typecasting same as training for OneHot consistency
        X_future["societa"] = X_future["societa"].astype("category")
        X_future["commessa"] = X_future["commessa"].astype("category")
        
        update_status(message="Calcolo previsioni batch...", progress=0.35, phase="OPTIMIZATION")
        preds = model.predict(X_future[cat_cols + num_cols])
        
        predictions = []
        for i, pred_ore in enumerate(preds):
            pred_ore = max(0.0, float(pred_ore))
            if pred_ore >= 2.0:
                row = prediction_rows[i]
                predictions.append({
                    "date": row["data"].strftime("%Y-%m-%d"),
                    "activity_id": row["commessa"],
                    "predicted_hours": float(round(pred_ore, 2)),
                    "typical_start_hour": float(round(row["typical_start"], 2)),
                    "typical_duration": float(round(row["typical_duration"], 2))
                })
        
        # Cleanup
        del X_future, prediction_rows
        self._gc.collect()
        return predictions


    def predict_absence_risk(self, target_date: datetime) -> Dict[str, float]:
        """
        Returns a dictionary { employee_id: probability_of_absence (0.0-1.0) } for the target date.
        """
        df = self.get_base_dataframe()
        if df.empty: return {}

        # Cache the model to avoid re-training for every date in a week
        if self._risk_model_cache is None:
            print("DEBUG: Training Absence Risk model once...")
            # 1. Aggregate Daily Absence per Employee
            # CRITICAL: observed=True prevents memory explosion on PROFER scale
            abs_daily = df.groupby(["societa", "dipendente", "data"], as_index=False, observed=True).agg(
                is_assenza=("is_assenza", "max")
            )
            abs_daily = self._add_calendar_features(abs_daily)
            abs_daily = self._add_time_index(abs_daily)
            abs_daily = self._add_rolling_features(abs_daily, ["societa", "dipendente"], "is_assenza", windows=(14, 60))
            
            # Fill NA
            for c in abs_daily.columns:
                if "rollmean" in c: abs_daily[c] = abs_daily[c].fillna(0)

            self._abs_daily = abs_daily
            self._risk_model_cache = self._train_classifier(
                abs_daily, "is_assenza", 
                ["societa", "dipendente", "dow", "month", "woy"],
                [c for c in abs_daily.columns if "rollmean" in c] + ["day", "week", "t_index"]
            )

        from utils.status_manager import update_status
        update_status(message="Calcolo rischio assenze...", progress=0.6, phase="OPTIMIZATION")
        
        model = self._risk_model_cache
        if not model: return {}
        
        abs_daily = self._abs_daily
            
        # Prediction loop
        active_emps = abs_daily["dipendente"].unique()
        # CRITICAL: observed=True for tail(1)
        last_states = abs_daily.sort_values("data").groupby("dipendente", observed=True).tail(1).set_index("dipendente")
        base_date = abs_daily["data"].min()
        
        # Row for prediction
        iso = target_date.isocalendar()
        
        for emp in active_emps:
            if emp not in last_states.index: continue
            last_state = last_states.loc[emp]
            
            row = {
                "societa": self.environment,
                "dipendente": emp,
                "data": target_date,
                "dow": target_date.weekday(),
                "month": target_date.month,
                "day": target_date.day,
                "week": int(iso.week),
                "woy": int(iso.week),
                "t_index": (target_date - base_date).days
            }
             # Copy rolling feats
            for col in num_cols:
                if "rollmean" in col:
                    row[col] = last_state[col]
            
            X = pd.DataFrame([row])
            try:
                # predict_proba returns [ [p0, p1], ... ]
                # We want p1 (probability of class 1 = absence)
                prob = model.predict_proba(X[cat_cols + num_cols])[0][1]
                risks[emp] = float(prob)
            except:
                risks[emp] = 0.0
                
        return risks
