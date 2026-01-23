from fastapi import APIRouter, Depends
# from firebase_admin import firestore  # Replaced with Datastore
from utils.datastore_helper import get_db
from datetime import datetime, timedelta
from statistics import mean
from utils.security import verify_hmac

router = APIRouter(prefix="/learning", tags=["Learning"])

@router.get("/demand")
def learn_demand(environment: str = Depends(verify_hmac)):
    """
    Exposes the high-fidelity Demand Profile learned by the Neural Engine.
    """
    from utils.demand_profiler import get_demand_profile
    profile = get_demand_profile(environment)
    return {
        "profile": profile,
        "last_updated": datetime.now().isoformat(),
        "aiEnabled": True 
    }
