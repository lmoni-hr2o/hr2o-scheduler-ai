from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime
import requests
from models import Activity, Employment, Period
from utils.security import verify_hmac
import firebase_admin
# from firebase_admin import firestore  # Replaced with Datastore
from utils.datastore_helper import get_db

router = APIRouter(prefix="/agent", tags=["Agent"])

# Host API Configuration - 
EXTERNAL_ACTIVITY_URL = "https://europe-west3-hrtimeplace.cloudfunctions.net/activity?namespace=OVERCLEAN"
EXTERNAL_EMPLOYMENT_URL = "https://europe-west3-hrtimeplace.cloudfunctions.net/employment?namespace=OVERCLEAN"
EXTERNAL_PERIOD_URL = "https://europe-west3-hrtimeplace.cloudfunctions.net/period?namespace=OVERCLEAN&isplan=true&iscalc=false&start=01022023&end=02022023"

@router.get("/activities", response_model=List[Activity])
def get_activities(environment: str = Depends(verify_hmac)):
    """
    Fetches activity data from Datastore Period entities.
    Extracts unique activities from the 'activities' field in Period.
    """
    print(f"DEBUG: Fetching activities for environment: {environment}")
    
    try:
        from utils.datastore_helper import get_db
        db = get_db()
        
        # Query all Period entities
        # POSSIBLE FIX: Try default namespace followed by 'OVERCLEAN' namespace
        periods = []
        for ns in [None, "OVERCLEAN"]:
            print(f"DEBUG: Fetching activities from namespace: {ns}")
            ns_db = get_db(namespace=ns)
            batch_periods = list(ns_db.collection("Period").stream())
            if not batch_periods:
                batch_periods = list(ns_db.collection("period").stream())
            
            if batch_periods:
                print(f"DEBUG: Found {len(batch_periods)} Period entities in namespace {ns}")
                periods.extend(batch_periods)
        
        if not periods:
            from google.cloud import datastore
            client = datastore.Client() # default
            query = client.query(kind='__kind__')
            query.keys_only()
            kinds = [entity.key.id_or_name for entity in query.fetch()]
            print(f"DEBUG: NO PERIOD DATA FOUND FOR ACTIVITIES. Available kinds in default Datastore: {kinds}")
        
        # Extract unique activities
        activities_dict = {}
        for period_doc in periods:
            period_data = period_doc.to_dict()
            activity_data = period_data.get("activities")
            
            if activity_data and isinstance(activity_data, dict):
                act_id = str(activity_data.get("id", ""))
                if act_id and act_id not in activities_dict:
                    activities_dict[act_id] = Activity(
                        id=act_id,
                        name=activity_data.get("name", "Unknown Activity"),
                        role_required="worker",
                        environment=environment,
                        project=activity_data.get("project"),
                        code=activity_data.get("code"),
                        note=activity_data.get("note"),
                        typeActivity=activity_data.get("typeActivity"),
                        dtEnd=activity_data.get("dtEnd"),
                        type=activity_data.get("type"),
                        productivityType=activity_data.get("productivityType"),
                        operations=activity_data.get("operations")
                    )
        
        result = list(activities_dict.values())
        print(f"DEBUG: Found {len(result)} unique activities from Period data")
        return result
        
    except Exception as e:
        print(f"ERROR fetching activities from Datastore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch activities: {str(e)}")

@router.get("/employment", response_model=List[Employment])
def get_employment(environment: str = Depends(verify_hmac)):
    """
    Fetches employment data from Datastore Period entities.
    Extracts unique employees from the 'employment' field in Period.
    """
    print(f"DEBUG: Fetching employment for environment: {environment}")
    
    try:
        from utils.datastore_helper import get_db
        db = get_db()
        
        # Query all Period entities
        # POSSIBLE FIX: Try default namespace followed by 'OVERCLEAN' namespace
        periods = []
        for ns in [None, "OVERCLEAN"]:
            print(f"DEBUG: Fetching employment from namespace: {ns}")
            ns_db = get_db(namespace=ns)
            batch_periods = list(ns_db.collection("Period").stream())
            if not batch_periods:
                batch_periods = list(ns_db.collection("period").stream())
                
            if batch_periods:
                print(f"DEBUG: Found {len(batch_periods)} Period entities in namespace {ns}")
                periods.extend(batch_periods)
        
        if not periods:
            from google.cloud import datastore
            client = datastore.Client() # default
            query = client.query(kind='__kind__')
            query.keys_only()
            kinds = [entity.key.id_or_name for entity in query.fetch()]
            print(f"DEBUG: NO PERIOD DATA FOUND. Available kinds in default Datastore: {kinds}")
        
        # Extract unique employees
        employees_dict = {}
        for period_doc in periods:
            period_data = period_doc.to_dict()
            employment_data = period_data.get("employment")
            
            if employment_data and isinstance(employment_data, dict):
                emp_id = str(employment_data.get("id", ""))
                if emp_id and emp_id not in employees_dict:
                    # Extract person name
                    person = employment_data.get("person", {})
                    name = person.get("fullName", "Unknown Employee")
                    
                    employees_dict[emp_id] = Employment(
                        id=emp_id,
                        name=name,
                        role="worker",  # Default role
                        environment=environment,
                        company=employment_data.get("company"),
                        person=person,
                        dtHired=employment_data.get("dtHired"),
                        dtDismissed=employment_data.get("dtDismissed"),
                        badge=employment_data.get("badge")
                    )
        
        result = list(employees_dict.values())
        print(f"DEBUG: Found {len(result)} unique employees from Period data")
        return result
        
    except Exception as e:
        print(f"ERROR fetching employment from Datastore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch employment: {str(e)}")

@router.get("/periods", response_model=List[Period])
def get_periods(
    start_date: datetime, 
    end_date: datetime, 
    environment: str = Depends(verify_hmac)
):
    """
    Legge i Periodi dall'API esterna dell'host.
    """
    if "URL_PERIOD" in EXTERNAL_PERIOD_URL or "INSERISCI_QUI" in EXTERNAL_PERIOD_URL:
        try:
            from utils.datastore_helper import get_db
            db = get_db()
            # Match Firestore structure to Datastore logic
            docs = db.collection("environments").document(environment).collection("periods") \
                    .where("tmregister", ">=", start_date) \
                    .where("tmregister", "<=", end_date) \
                    .stream()
            return [Period(**doc.to_dict()) for doc in docs]
        except Exception as e:
            print(f"DEBUG: Internal periods fetch failed: {e}")
            return []

    try:
        params = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
        response = requests.get(EXTERNAL_PERIOD_URL, params=params, headers={"Environment": environment})
        response.raise_for_status()
        data = response.json()
        return [Period(**item) for item in data] if isinstance(data, list) else []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Host Period (Read) API Error: {str(e)}")

@router.post("/periods", response_model=Period)
def create_period(period: Period, environment: str = Depends(verify_hmac)):
    """
    Scrive un Periodo nell'API esterna dell'host.
    """
    if period.environment != environment:
        raise HTTPException(status_code=400, detail="Environment mismatch between body and header.")
    
    if "URL_PERIOD" in EXTERNAL_PERIOD_URL or "INSERISCI_QUI" in EXTERNAL_PERIOD_URL:
        try:
            from utils.datastore_helper import get_db
            db = get_db()
            doc_ref = db.collection("environments").document(environment).collection("periods").document()
            period_dict = period.dict()
            period_dict["id"] = doc_ref.id
            doc_ref.set(period_dict)
            return Period(**period_dict)
        except Exception as e:
            print(f"DEBUG: Internal period creation failed: {e}")
            return period

    try:
        response = requests.post(EXTERNAL_PERIOD_URL, json=period.dict(), headers={"Environment": environment})
        response.raise_for_status()
        return Period(**response.json())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Host Period (Write) API Error: {str(e)}")
