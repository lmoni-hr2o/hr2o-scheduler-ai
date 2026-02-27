import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Request
from routers import schedule, training, ingestion, agent, reports, learning, labor_profiles, sync, insights, worker
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import psutil
import time

def log_memory(msg=""):
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / (1024 * 1024)
    print(f"DIAGNOSTIC: {msg} | Memory: {mem:.2f} MB")

# Initialize Firebase
try:
    if os.getenv("FIREBASE_CREDENTIALS"):
        cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS"))
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()
except ValueError:
    pass 

app = FastAPI(title="TimePlanner AI Agent API")

# CORSMiddleware will be added later to be the outermost

@app.middleware("http")
async def log_requests(request: Request, call_next):
    log_memory(f"Incoming {request.method} {request.url.path}")
    start_time = time.time()
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        print(f"DEBUG: Response status: {response.status_code} | Duration: {duration:.2f}s")
        return response
    except Exception as e:
        import traceback
        print(f"CRITICAL: Middleware caught exception: {e}")
        traceback.print_exc()
        from fastapi.responses import JSONResponse
        # We return a response here. CORSMiddleware (added later/outer) will wrap this.
        return JSONResponse(status_code=500, content={"detail": f"Internal Error: {str(e)}"})

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Enable CORS - mandatory outermost layer for browser security
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hrtimeplace.web.app", 
        "https://hrtimeplace.firebaseapp.com",
        "http://localhost:8080", 
        "http://localhost"
    ],
    allow_credentials=True, # Improved with explicit origins
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(schedule.router)
app.include_router(training.router)
app.include_router(ingestion.router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(agent.router)
app.include_router(reports.router)
app.include_router(learning.router)
app.include_router(labor_profiles.router)
app.include_router(sync.router)
app.include_router(insights.router)
app.include_router(worker.router)

@app.on_event("startup")
async def startup_event():
    print("STARTUP: Running version V2-FIX-PROFILER-VERIFICATION")
    # RESET LOCK on startup: In case of previous crash, ensure we aren't blocked
    print("Startup: Clearing any stale locks...")
    try:
        from utils.status_manager import set_running
        set_running(False)
        print("Startup: Lock cleared.")
    except Exception as e:
        print(f"Startup: Warning - could not clear lock: {e}")


@app.get("/")
def read_root():
    return {"status": "AI Agent Engine v1.2 is running"}

@app.get("/debug-routes")
def debug_routes():
    return [{"path": route.path, "name": route.name} for route in app.routes]
