from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Set
import requests
from datetime import datetime, timedelta
from google.cloud import datastore
from models import Employment, Activity, Period, LaborProfile, TimePlace
from utils.datastore_helper import get_db
from utils.demand_profiler import DemandProfiler

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
    print(f"Step 1: Fetching Master Data (Companies, Activities) for {namespace}...")
    raw_companies = fetch_external("company", namespace)
    raw_activities = fetch_external("activity", namespace)

    print(f"Step 2: Fetching Employments for {namespace}...")
    raw_employments = fetch_external("employment", namespace)
    
    print(f"Step 3: Fetching Periods (Last {lookback_days} days)...")
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
    
    # --- DEBUG LOGGING ---
    if raw_periods and len(raw_periods) > 0:
        print(f"DEBUG: Sample Raw Period (Keys): {list(raw_periods[0].keys())}")
        print(f"DEBUG: Sample Raw Period (Activity): {raw_periods[0].get('activities')}")
    else:
        print(f"DEBUG: No raw periods received for {namespace}.")
    
    # --- PROCESSING ---
    
    # --- PROCESSING ---
    
    # A. Company Master Data
    valid_company_ids = set()
    
    # --- CUMULATIVE DISCOVERY: Load Known Companies ---
    try:
        q_comp = client.query(kind="Company") # Query across namespaces or default?
        # Companies are in 'namespace' and 'company_id' namespaces.
        # Just getting from 'namespace' (OVERCLEAN) is enough.
        q_source = client.query(kind="Company", namespace=namespace)
        for c_ent in q_source.fetch():
            cid = str(c_ent.key.name)
            valid_company_ids.add(cid)
        print(f"Pre-loaded {len(valid_company_ids)} known companies from Datastore.")
    except Exception as e:
        print(f"Company pre-load failed: {e}")

    # Process explicit Company list
    for comp in raw_companies:
        comp_id = str(comp.get("id"))
        if comp_id:
            valid_company_ids.add(comp_id)
            
            comp_data = {
                "name": comp.get("name"), 
                "code": comp.get("code"),
                "address": comp.get("address"),
                "vat": comp.get("VATNumber"),
                "last_sync": datetime.now()
            }
            
            # Store in Source Namespace (for discovery)
            key_source = client.key("Company", comp_id, namespace=namespace)
            bg_source = datastore.Entity(key=key_source)
            bg_source.update(comp_data)
            client.put(bg_source)

            # Store in Self Namespace (for agent)
            key_self = client.key("Company", comp_id, namespace=comp_id)
            bg_self = datastore.Entity(key=key_self)
            bg_self.update(comp_data)
            client.put(bg_self)
            
    # B. Employments
    valid_employees: Dict[str, Employment] = {}
    
    # --- BRUTE FORCE DISCOVERY: Scan ALL project namespaces ---
    print("Step 2: Performing project-wide Discovery Recovery...")
    try:
        # First, find all namespaces
        q_ns = client.query(kind="__namespace__")
        q_ns.keys_only()
        all_nss = [str(e.key.id or e.key.name) for e in q_ns.fetch()]
        
        for ns_id in all_nss:
            # Skip architectural namespaces
            if ns_id.startswith("__"): continue
            
            q_emp = client.query(kind="Employment", namespace=ns_id)
            for e_ent in q_emp.fetch():
                e_id = str(e_ent.key.name)
                # Only add if not already present (prefer existing or custom)
                if e_id not in valid_employees:
                    # Robust extraction with type safety for Pydantic 2
                    def safe_str(v): return str(v) if v is not None else ""
                    
                    valid_employees[e_id] = Employment(
                        id=e_id,
                        name=safe_str(e_ent.get("name") or e_ent.get("fullName")),
                        fullName=safe_str(e_ent.get("fullName") or e_ent.get("name")),
                        role=safe_str(e_ent.get("role") or "worker"),
                        environment=safe_str(e_ent.get("environment") or ns_id),
                        address=safe_str(e_ent.get("address")),
                        city=safe_str(e_ent.get("city")),
                        bornDate=safe_str(e_ent.get("bornDate")),
                        dtHired=safe_str(e_ent.get("dtHired")),
                        contract_type=safe_str(e_ent.get("contract_type") or "Standard"),
                        contract_hours=float(e_ent.get("contract_hours") or 40.0),
                        qualification=safe_str(e_ent.get("qualification") or ""),
                        labor_profile_id=safe_str(e_ent.get("labor_profile_id")),
                        has_history=bool(e_ent.get("has_history") or False)
                    )
        print(f"  > Brute Force Discovery found {len(valid_employees)} unique individuals.")
    except Exception as e:
        print(f"Brute Force Discovery failed: {e}")

    # Merge/Update with current API list (for new discoveries)
    print(f"Step 2b: Merging with {len(raw_employments)} records from API /employment list...")
    for emp in raw_employments:
        if emp.get("dtDismissed"): pass # Skip logic same as before or enhance
        
        comp = emp.get("company", {})
        comp_id = str(comp.get("id"))
        
        # If company not in fetched list, maybe add it? 
        # For now, trust the employment's company link if valid
        if comp_id: valid_company_ids.add(comp_id) 

        person = emp.get("person", {})
        p_id = str(person.get("ID") or person.get("id"))
        e_id = str(emp.get("id"))
        
        if e_id:
            # --- Extract Contract Details & Labor Profile ---
            contract = emp.get("contract", {})
            c_type = contract.get("typeDescription") or contract.get("type", "Standard")
            c_hours = contract.get("hoursWeekly") or contract.get("hours", 40.0)
            c_qual = contract.get("levelDescription") or contract.get("qualification", "")
            
            try:
                c_hours_float = float(c_hours)
                if c_hours_float <= 0: c_hours_float = 40.0
            except:
                c_hours_float = 40.0
                
            safe_qual = "".join([c for c in c_qual if c.isalnum()])
            safe_type = "".join([c for c in c_type if c.isalnum()])
            
            if not comp_id:
                continue 

            # Create initial Employment with BEST GUESS from list
            valid_employees[e_id] = Employment(
                id=e_id,
                name=comp.get("name", "Unknown"),
                fullName=person.get("fullName", "Unknown"),
                role="worker",
                environment=comp_id,
                address=person.get("address"),
                city=person.get("city"),
                bornDate=str(person.get("borndate")),
                dtHired=str(emp.get("dtHired")),
                contract_type=c_type, # Use real type from list if available
                contract_hours=c_hours_float, # Use real hours from list if available
                qualification=c_qual,
                labor_profile_id=f"AUTO_{safe_type}_{safe_qual}_{int(c_hours_float)}",
                has_history=False
            )

    # B2. ENHANCED SYNC: Fetch Detailed Hours (emphour=true)
    all_eids = list(valid_employees.keys())
    chunk_size = 20
    
    print(f"Step 2b: Found {len(all_eids)} valid employees. Enhancing with Real Hours...")
    
    updated_count = 0
    for i in range(0, len(all_eids), chunk_size):
        chunk = all_eids[i:i+chunk_size]
        ids_str = ",".join(chunk)
        
        try:
             h_data = fetch_external("employment", namespace, params={
                 "emphour": "true",
                 "employments": ids_str
             })
             
             print(f"  > Batch {i//chunk_size}: Received {len(h_data)} hour records.")
             
             for h_rec in h_data:
                 eid = str(h_rec.get("idEmployment") or h_rec.get("id")) # idEmployment usually checks out
                 
                 # Calculate Weekly Hours
                 weekly_h = (h_rec.get("hhMonday") or 0.0) + \
                            (h_rec.get("hhTuesday") or 0.0) + \
                            (h_rec.get("hhWednesday") or 0.0) + \
                            (h_rec.get("hhThursday") or 0.0) + \
                            (h_rec.get("hhFriday") or 0.0) + \
                            (h_rec.get("hhSaturday") or 0.0) + \
                            (h_rec.get("hhSunday") or 0.0)
                 
                 if eid in valid_employees:
                     emp_obj = valid_employees[eid]
                     
                     # Infer Contract Type based on ACTUAL historical hours if present
                     # Skip if h_rec is None or not a dict
                     if not isinstance(h_rec, dict): continue

                     new_hours = 0.0
                     if weekly_h > 0:
                         new_type = "FullTime" if weekly_h >= 30 else "PartTime"
                         new_hours = weekly_h
                     else:
                         # Keep what we had from master list
                         # If hours == 40, it's 'Standard', otherwise it's likely a custom 'Contract'
                         new_type = "Standard" if (emp_obj.contract_hours or 0) >= 40 else "Contract"
                         new_hours = emp_obj.contract_hours or 40.0
                     
                     # Update Object
                     emp_obj.contract_hours = new_hours
                     emp_obj.contract_type = new_type
                     
                     # Re-generate Profile ID
                     s_qual = "".join([c for c in (emp_obj.qualification or "") if c.isalnum()])
                     emp_obj.labor_profile_id = f"AUTO_{new_type}_{s_qual}_{int(new_hours)}"
                     updated_count += 1
                 else:
                     if i == 0: print(f"    ! ID {eid} not in valid_employees")
                     
        except Exception as e:
            print(f"Error fetching hours for chunk {i}: {e}")

    print(f"Step 2b: Successfully updated {updated_count} employees with real hours.")

    # C. Activities Master Data
    unique_activities: Dict[str, Activity] = {}
    
    for act in raw_activities:
        act_id = str(act.get("id") or act.get("code"))
        # We need to know which Company this activity belongs to.
        # The API usually returns all for the namespace.
        # We might need 'company' field in activity or assume it belongs to 'namespace' if not specified.
        # Or look at project -> customer.
        # Assuming the activity structure has 'company' or we assign to all companies in namespace?
        # Safe bet: Check if 'company' is in act object.
        act_comp = act.get("company", {})
        act_ns = str(act_comp.get("id")) if act_comp else namespace
        
        if act_id:
            act_key_unique = f"{act_id}::{act_ns}"
            proj = act.get("project", {})
            cust = proj.get("customer", {})
            
            unique_activities[act_key_unique] = Activity(
                id=act_id,
                name=str(act.get("name") or act.get("code") or "Unknown"),
                code=str(act.get("code") or act_id),
                environment=act_ns,
                customer_address=str(cust.get("address") or cust.get("city") or ""),
                project_id=str(proj.get("id") or ""),
                typeActivity=str(act.get("typeActivity") or ""),
                operations=act.get("operations") or [],
                dailySchedule=act.get("dailySchedule"),
                weeklySchedule=act.get("weeklySchedule"),
                hhSchedule=act.get("hhSchedule"),
                typeSchedule=act.get("typeSchedule")
            )

    # D. Periods (History Learning)
    batch = client.batch()
    batch.begin()
    
    emp_skills: Dict[str, Set[str]] = {} 
    emp_comp_map = {e_id: e.environment for e_id, e in valid_employees.items()}
    companies_with_history = set()

    for p in raw_periods:
        # Validate Status again just in case
        if p.get("status") != 100000 or p.get("cancelled") is True:
            continue
            
        p_emp = p.get("employment", {})
        e_id = str(p_emp.get("id")) # Use Employment ID
        
        # Get Company ID (Namespace) from our map
        emp_ns = emp_comp_map.get(e_id)
        if not emp_ns: continue
        
        # Mark company as having history (Active)
        companies_with_history.add(emp_ns)

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
            "employmentId": e_id,
            "personId": str(p_emp.get("person", {}).get("id")),
            "tmregister": p.get("tmregister") or p.get("beginTimePlace", {}).get("tmregister"),
            "tmentry": p.get("tmentry") or p.get("beginTimePlace", {}).get("time"),
            "tmexit": p.get("tmexit") or p.get("endTimePlace", {}).get("time"),
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
        
        if e_id in valid_employees:
            valid_employees[e_id].has_history = True
            
            # Additional Activity Discovery (if sync missed some)
            act = p.get("activities", {})
            act_id = str(act.get("code") or act.get("id"))
            
            if act_id:
                act_key_unique = f"{act_id}::{emp_ns}"
                if act_key_unique not in unique_activities:
                    # Inferred fallback
                    proj = act.get("project", {})
                    cust = proj.get("customer", {})
                    unique_activities[act_key_unique] = Activity(
                        id=act_id,
                        name=act.get("name", "Unknown"),
                        code=act.get("code"),
                        environment=emp_ns,
                        customer_address=cust.get("address") or cust.get("city"),
                        project_id=str(proj.get("id")),
                        typeActivity=act.get("typeActivity"),
                        operations=act.get("operations")
                    )

            # Skill Learning
            act_code = act.get("code")
            if p_id not in emp_skills: emp_skills[p_id] = set()
            if act_code:
                 keywords = ["VETRI", "MERCH", "PULIZIA", "ORDINARIO", "SANIFICAZIONE", "GIARDINAGGIO"]
                 for k in keywords:
                     if k in act_code.upper():
                         emp_skills[p_id].add(k)
                         
    batch.commit()
        
    # C. Updates & Storage
    batch = client.batch()
    batch.begin()
    count = 0
    
    # Calculate Employee Counts per Company
    emp_counts = {}
    for e in valid_employees.values():
        cid = e.environment
        emp_counts[cid] = emp_counts.get(cid, 0) + 1

    # 1. Save Companies (Self-Replication)
    for cid in valid_company_ids:
        has_hist = (cid in companies_with_history)
        emp_count = emp_counts.get(cid, 0)
        
        # Update in Source Namespace
        key_source = client.key("Company", cid, namespace=namespace)
        ent_source = client.get(key_source)
        if ent_source:
            ent_source["has_history"] = has_hist
            ent_source["active_employees_count"] = emp_count
            batch.put(ent_source)
            
        # Update in Self Namespace
        key_self = client.key("Company", cid, namespace=cid)
        ent_self = client.get(key_self)
        if ent_self:
            ent_self["has_history"] = has_hist
            ent_self["active_employees_count"] = emp_count
            batch.put(ent_self)
            
        count += 2
        if count % 400 == 0:
            batch.commit()
            batch = client.batch()
            batch.begin()

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

    # 2b. Save Inferred Labor Profiles
    # First: Clean up OLD automated profiles to avoid duplicates (e.g. from previous ID logic)
    print("Step 2b: Cleaning up old AUTO profiles...")
    cleanup_batch = client.batch()
    cleanup_batch.begin()
    c_count = 0
    
    for cid in valid_company_ids:
        # Use namespace for the company
        try:
            q_old = client.query(kind="LaborProfile", namespace=cid)
            # Fetch keys only for speed if possible, but we need ID check
            for old_p in q_old.fetch():
                if old_p.key.name and old_p.key.name.startswith("AUTO_"):
                    # We only delete if it exists to keep DB clean
                    cleanup_batch.delete(old_p.key)
                    c_count += 1
                    if c_count % 400 == 0:
                        cleanup_batch.commit()
                        cleanup_batch = client.batch()
                        cleanup_batch.begin()
        except Exception as e:
            print(f"Warning: Cleanup failed for {cid}: {e}")

    cleanup_batch.commit()
    print(f"Deleted {c_count} old auto-profiles.")

    saved_profiles = set()
    for emp_id, emp_obj in valid_employees.items():
        pid = emp_obj.labor_profile_id
        target_ns = emp_obj.environment
        sig = f"{pid}::{target_ns}"
        
        if pid and sig not in saved_profiles and pid.startswith("AUTO_"):
            saved_profiles.add(sig)
            
            target_ns = emp_obj.environment
            key_p = client.key("LaborProfile", pid, namespace=target_ns)
            
            ent_p = datastore.Entity(key=key_p)
            ent_p.update({
                "id": pid,
                "name": f"{emp_obj.contract_type} ({int(emp_obj.contract_hours or 40)}h)",
                "company_id": target_ns,
                "max_weekly_hours": emp_obj.contract_hours or 40.0,
                "max_daily_hours": 8.0, 
                "max_consecutive_days": 6,
                "min_rest_hours": 11.0,
                "is_default": False,
                "last_updated": datetime.now()
            })
            batch.put(ent_p)
            count += 1
            if count % 400 == 0:
                batch.commit()
                batch = client.batch()
                batch.begin()

    # 3. Save Activities 
    for act_unique_key, act_obj in unique_activities.items():
        # Optimization: If activity is at root of namespace, save it to ALL discovered companies
        # so they can all select it in the UI.
        target_namespaces = [act_obj.environment]
        if act_obj.environment == namespace:
            target_namespaces.extend(list(valid_company_ids))
            # Deduplicate just in case
            target_namespaces = list(set(target_namespaces))

        for target_ns in target_namespaces:
            if not target_ns: continue
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

    batch.commit()
    
    # 4. Trigger Demand Learning for each active company
    print(f"Step 4: Learning Demand Profiles for {len(companies_with_history)} active companies...")
    for cid in companies_with_history:
        try:
            q_p = client.query(kind="Period", namespace=cid)
            periods_for_learn = list(q_p.fetch())
            if periods_for_learn:
                profiler = DemandProfiler(cid)
                profiler.learn_from_periods(periods_for_learn)
                profiler.save_to_datastore()
                print(f"  > Learned profile for {cid} from {len(periods_for_learn)} periods.")
        except Exception as e_learn:
            print(f"  ! Error learning profile for {cid}: {e_learn}")

    return {
        "status": "success",
        "companies_synced": len(valid_company_ids),
        "companies_active": len(companies_with_history),
        "employees_synced": len(valid_employees),
        "activities_synced": len(unique_activities),
        "namespace": namespace
    }
