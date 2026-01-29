from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Set
import requests
from datetime import datetime, timedelta
from google.cloud import datastore
from models import Employment, Activity, Period, LaborProfile, TimePlace
from utils.datastore_helper import get_db

router = APIRouter(prefix="/sync", tags=["Sync"])

BASE_URL = "https://europe-west3-hrtimeplace.cloudfunctions.net"

def fetch_external(endpoint: str, namespace: str, params: dict = None) -> List[dict]:
    """Helper to fetch from external Cloud Functions."""
    url = f"{BASE_URL}/{endpoint}"
    if not params: params = {}
    params["namespace"] = namespace
    
    try:
        print(f"DEBUG: Fetching {url} with {params}")
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"ERROR fetching {endpoint}: {e}")
        return []

@router.post("/full")
def full_sync(namespace: str = "OVERCLEAN", lookback_days: int = 90):
    """
    Performs the Full Sync Strategy:
    1. Fetch Employments -> Whitelist Companies & Active Employees.
    2. Fetch Periods (History) -> Learn Habits & Skills.
    3. Save everything to Datastore.
    """
    client = get_db().client
    
    # 1. Fetch Raw Data
    print(f"Step 1: Fetching Employments for {namespace}...")
    raw_employments = fetch_external("employment", namespace)
    
    print(f"Step 2: Fetching Periods (Last {lookback_days} days)...")
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=lookback_days)
    
    # Period endpoint format: start=ddMMyyyy
    p_params = {
        "isplan": "true",
        "iscalc": "false",
        "start": start_dt.strftime("%d%m%Y"),
        "end": end_dt.strftime("%d%m%Y")
    }
    raw_periods = fetch_external("period", namespace, p_params)
    
    # --- PROCESSING ---
    
    # A. Company Whitelist & Employee Filtering
    valid_company_ids = set()
    valid_employees: Dict[str, Employment] = {}
    
    # Filter active employments
    for emp in raw_employments:
        # Check dismissal
        dt_dismissed = emp.get("dtDismissed")
        if dt_dismissed:
            # Parse date if needed, assumed YYYY-MM-DD or ISO
            # For simplicity, if present and "past", skip. 
            pass # TODO: Add strict parsing if format known

        # Extract Company
        comp = emp.get("company", {})
        comp_id = str(comp.get("id"))
        if comp_id:
            valid_company_ids.add(comp_id)
            
            # Common Company Data
            comp_data = {
                "name": comp.get("name"), 
                "code": comp.get("code"),
                "address": comp.get("address"),
                "vat": comp.get("VATNumber"),
                "last_sync": datetime.now()
            }

            # 1. Store in Source Namespace (e.g. OVERCLEAN) - for Discovery
            key_source = client.key("Company", comp_id, namespace=namespace)
            bg_source = datastore.Entity(key=key_source)
            bg_source.update(comp_data)
            client.put(bg_source)

            # 2. Store in Company ID Namespace - for Agent
            key_self = client.key("Company", comp_id, namespace=comp_id)
            bg_self = datastore.Entity(key=key_self)
            bg_self.update(comp_data)
            client.put(bg_self)

        # Extract Person
        person = emp.get("person", {})
        p_id = str(person.get("ID") or person.get("id")) # Numeric ID preferred
        
        if p_id:
            # IMPORTANT: Set 'environment' to company_id so it gets partitioned!
            valid_employees[p_id] = Employment(
                id=p_id,
                name=comp.get("name", "Unknown"),
                fullName=person.get("fullName", "Unknown"),
                role="worker",
                environment=comp_id if comp_id else namespace,
                address=person.get("address"),
                city=person.get("city"),
                bornDate=str(person.get("borndate")),
                dtHired=str(emp.get("dtHired")),
                has_history=False,
                labor_profile_id=None
            )

    # B. Learning from History (Periods) & Activities
    emp_skills: Dict[str, Set[str]] = {} 
    unique_activities: Dict[str, Activity] = {}
    
    # Store Company ID mapping for Employees to route Activities correctly
    emp_comp_map = {e_id: e.environment for e_id, e in valid_employees.items()}

    for p in raw_periods:
        # Validate Status
        if p.get("status") != 100000 or p.get("cancelled") is True:
            continue
            
        # Identify Employee
        p_emp = p.get("employment", {})
        p_id = str(p_emp.get("person", {}).get("ID") or p_emp.get("person", {}).get("id"))
        
        if p_id not in valid_employees:
            continue
            
        emp_ns = emp_comp_map.get(p_id) # This is the Company ID now
        
        # Learn Activity
        act = p.get("activities", {})
        act_id = str(act.get("code") or act.get("id")) # Use code as ID if available, else generic ID
        
        if act_id and emp_ns:
            # Key activity by ID + Namespace to handle multi-tenant overlap if codes are same
            act_key_unique = f"{act_id}::{emp_ns}"
            
            if act_key_unique not in unique_activities:
                # Extract details
                proj = act.get("project", {})
                cust = proj.get("customer", {})
                unique_activities[act_key_unique] = Activity(
                    id=act_id,
                    name=act.get("name", "Unknown"),
                    code=act.get("code"),
                    environment=emp_ns,     # IMPORTANT: Set to Company ID
                    customer_address=cust.get("address") or cust.get("city"),
                    project_id=str(proj.get("id")),
                    typeActivity=act.get("typeActivity"),
                    operations=act.get("operations")
                )
 
        # Learn Skills
        act_code = act.get("code")
        if p_id not in emp_skills: emp_skills[p_id] = set()
        
        # Simple keyword extraction (Naive NLP)
        if act_code:
            keywords = ["VETRI", "MERCH", "PULIZIA", "ORDINARIO", "SANIFICAZIONE", "GIARDINAGGIO"]
            for k in keywords:
                if k in act_code.upper():
                    emp_skills[p_id].add(k)
        
        valid_employees[p_id].has_history = True
        
    # C. Updates & Storage
    batch = client.batch()
    batch.begin()
    count = 0
    
    # 1. Save Companies (Self-Replication)
    # We already saved them in 'namespace' (OVERCLEAN) in Step A.
    # NOW we also save them in their OWN namespace so agent.py can find them.
    for cid in valid_company_ids:
        # Find the original entity data (optimally we would have stored it in a dict in Step A, fetching again relies on memory)
        # Hack: We construct a minimal valid entity or query what we just saved. 
        # Better: let's modifying Step A to store comp objects for this step.
        pass # See modifying Step A below for cleaner approach.

    # 2. Save Employees (Partitioned by Company ID)
    for emp_id, emp_obj in valid_employees.items():
        # Assign Skills/Tags
        skills = list(emp_skills.get(emp_id, []))
        if skills:
            emp_obj.role = ", ".join(skills) # Store basic skills as role text for now
            
        # Convert to Entity
        # target_ns is the Company ID (stored in emp_obj.environment)
        target_ns = emp_obj.environment
        
        key = client.key("Employment", emp_id, namespace=target_ns)
        entity = datastore.Entity(key=key)
        
        # Exclude None fields to keep Datastore clean
        data = emp_obj.dict(exclude_none=True)
        
        entity.update(data)
        entity.update({"last_sync": datetime.now()})
        
        batch.put(entity)
        count += 1
        
        if count % 400 == 0:
            batch.commit()
            batch = client.batch()
            batch.begin()
            
    # 3. Save Activities (Partitioned by Company ID)
    for act_unique_key, act_obj in unique_activities.items():
        # target_ns is the Company ID
        target_ns = act_obj.environment
        
        key = client.key("Activity", act_obj.id, namespace=target_ns)
        entity = datastore.Entity(key=key)
        entity.update(act_obj.dict(exclude_none=True))
        entity.update({"last_sync": datetime.now()})
        batch.put(entity)
        count += 1
        if count % 400 == 0:
            batch.commit()
            batch = client.batch()
            batch.begin()

    # 4. Save Periods (History for AI) - Partitioned by Company ID
    for p in raw_periods:
        # Validate Status again just in case
        if p.get("status") != 100000 or p.get("cancelled") is True:
            continue
            
        p_emp = p.get("employment", {})
        p_id = str(p_emp.get("person", {}).get("ID") or p_emp.get("person", {}).get("id"))
        
        # Get Company ID (Namespace) from our map
        emp_ns = emp_comp_map.get(p_id)
        if not emp_ns: continue
        
        # Period ID
        pid = str(p.get("id"))
        if not pid: continue

        # Extract minimal data needed for AI/History
        # We store it as a 'Period' entity
        key = client.key("Period", pid, namespace=emp_ns)
        entity = datastore.Entity(key=key)
        
        # Flatten structure slightly for Datastore querying
        # Store essential fields
        period_data = {
            "id": pid,
            "employmentId": p_id,
            "tmregister": p.get("tmregister") or p.get("beginTimePlace", {}).get("tmregister"),
            "tmexit": p.get("tmexit") or p.get("endTimePlace", {}).get("tmregister"),
            "activities": p.get("activities"), # Keep nested for richness
            "last_sync": datetime.now()
        }
        
        entity.update(period_data)
        batch.put(entity)
        count += 1
        
        if count % 400 == 0:
            batch.commit()
            batch = client.batch()
            batch.begin()

    batch.commit()


    
    return {
        "status": "success",
        "companies_synced": len(valid_company_ids),
        "employees_synced": len(valid_employees),
        "activities_synced": len(unique_activities),
        "namespace": namespace
    }
