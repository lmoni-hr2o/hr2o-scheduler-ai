import os
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Request
from routers import schedule, training, ingestion, agent, reports, learning, labor_profiles, sync
from fastapi.middleware.cors import CORSMiddleware

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
    print(f"DEBUG: Incoming {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        print(f"DEBUG: Response status: {response.status_code}")
        return response
    except Exception as e:
        print(f"CRITICAL: Middleware caught exception: {e}")
        from fastapi.responses import JSONResponse
        response = JSONResponse(status_code=500, content={"detail": str(e)})
        # Manually add CORS headers to error response to prevent 'Failed to fetch' in browser
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

# Enable CORS - outermost layer
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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

@app.get("/")
def read_root():
    return {"status": "AI Agent Engine v1.2 is running"}

@app.get("/debug-routes")
def debug_routes():
    return [{"path": route.path, "name": route.name} for route in app.routes]
