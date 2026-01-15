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
    Analyzes historical schedules (last 30 days) to infer optimal staffing levels.
    Returns: { "weekdayTarget": int, "weekendTarget": int }
    """
    db = get_db()
    
    # Range: Last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Query 'schedules' collection (assuming this is where approved schedules are stored)
    # Note: In a real system, we'd filter by 'status' == 'approved'
    # For this prototype, we assume all saved schedules in Firestore are valid training data.
    docs = db.collection('schedules') \
             .where('companyId', '==', environment) \
             .limit(50) \
             .stream()
             
    weekday_counts = []
    weekend_counts = []
    
    for doc in docs:
        data = doc.to_dict()
        schedule = data.get('schedule', [])
        
        # Analyze daily headcount
        daily_map = {}
        for shift in schedule:
            d_str = shift.get('date')
            if not d_str: continue
            
            # Count only if it's within our window (optional optimization)
            daily_map[d_str] = daily_map.get(d_str, 0) + 1
            
        for date_str, count in daily_map.items():
            try:
                dt = datetime.fromisoformat(date_str)
                # 0-4 = Weekday, 5-6 = Weekend
                if dt.weekday() < 5:
                    weekday_counts.append(count)
                else:
                    weekend_counts.append(count)
            except:
                pass
                
    # Calculate Averages (Default to current manual defaults if no data)
    weekday_target = int(mean(weekday_counts)) if weekday_counts else 3
    weekend_target = int(mean(weekend_counts)) if weekend_counts else 2
    
    return {
        "weekdayTarget": weekday_target,
        "weekendTarget": weekend_target,
        "aiEnabled": True 
    }
