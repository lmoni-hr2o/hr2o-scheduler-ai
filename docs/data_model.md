# Data Model & Flow (Pure Python / Stateless Mode)

Due to Firestore "Datastore Mode" limitations in the current project, the AI Engine has been transitioned to a **Stateless API Architecture**.

## 1. Primary Flow (Stateless)
Data is not fetched from Firestore by the AI Engine. Instead, the Flutter App provides the full context in each request.

| Component | Responsibility | Data Storage |
| --- | --- | --- |
| **Flutter App** | UI & Orchestration | Local Provider State (Mock for MVP) |
| **Python Solver** | Scheduling Logic | None (Stateless) |
| **Python Scorer** | Affinity Prediction | Local `.h5` Weights |

## 2. API Schema

### `POST /schedule/generate`
**Input:** Full JSON with `employees` list, `start_date`, `end_date`, and `constraints`.
**Output:** Optimized JSON with a list of `shifts`.

### `POST /training/log-feedback`
**Input:** User override details (Employee swapped, Shift ID).
**Storage:** **SQLite** (`/tmp/learning_data.db`).
> [!NOTE]
> Database in `/tmp` is ephemeral and reset on each new deployment or server restart.

## 3. Training Loop
1. User drags a shift in Flutter.
2. Flutter calls `/training/log-feedback`.
3. Backend saves the correction in SQLite.
4. User clicks "Retrain" in the AI Monitor.
5. Backend reads SQLite, updates `model_weights.h5`, and saves them to the container disk.

