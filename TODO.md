# HR2O Scheduler AI - TODO List

## 1. Backend: `main.py` (Entry Point)
- [x] **Global Exception Handling**: Replace the try-except block in the middleware with a cleaner FastAPI `@app.exception_handler`.
- [x] **Environment-based CORS**: Replace hardcoded CORS origins with environment variables (`os.getenv("ALLOWED_ORIGINS")`).
- [x] **Scalable Locks**: Improve the startup lock mechanism by tying it to a worker ID or implementing a TTL to handle multiple Cloud Run instances correctly.

## 2. Backend: `solver/engine.py` (Optimization Engine)
- [x] **Employee Deduplication**: Prioritize unique IDs over names during normalization to avoid merging real homonyms.
- [x] **Dynamic Memory Management**: Replace the hardcoded limit of 5000 turns with a dynamic memory check using `psutil` before starting ML turn generation.
- [x] **Constraint Optimization**: Optimize rest period constraints ($O(n^2) \to O(n)$) by grouping shifts into 24-hour windows and comparing only adjacent shifts.
- [x] **Jitter Sensitivity Analysis**: Verify that the `SCALE` (10) vs `random.randint(0, 30)` jitter doesn't negatively impact the optimal solution.
- [x] **Enhanced Infeasibility Reporting**: Use `solver.ResponseStats()` to provide specific feedback (e.g., "Missing employees for role X") when the model is infeasible, instead of forcing a feasible state.

## 3. Backend: `models.py` (Pydantic Models)
- [x] **Performance Optimization**: For `Activity` and `Employment` models used in intensive loops, use `ConfigDict(populate_by_name=True)` and consider disabling extra validation for pre-cleaned database data.

## 4. Backend: `routers/schedule.py` (API Layer)
- [x] **Configurable Shift Filter**: Move the 60-minute hardcoded filter to a query parameter or company-specific configuration.
- [x] **Job Status Error Handling**: Return a `404 Not Found` error when a job is missing, instead of the potentially confusing "Read-Only Mode" message.
