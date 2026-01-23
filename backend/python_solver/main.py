import os
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Request
from routers import schedule, training, ingestion, agent, reports, learning
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

# Enable CORS for Flutter Web - Explicit headers for stability
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-HMAC-Signature", "Environment", "Authorization"],
    expose_headers=["*"],
)

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
        return JSONResponse(status_code=500, content={"detail": str(e)})

app.include_router(schedule.router)
app.include_router(training.router)
app.include_router(ingestion.router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(agent.router)
app.include_router(reports.router)
app.include_router(learning.router)

@app.get("/")
def read_root():
    return {"status": "AI Agent Engine v1.2 is running"}

@app.get("/debug-routes")
def debug_routes():
    return [{"path": route.path, "name": route.name} for route in app.routes]
