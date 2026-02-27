from fastapi import APIRouter, HTTPException, Depends
from utils.datastore_helper import get_db
from utils.security import verify_hmac
from models import LaborProfile
from typing import List, Optional, Dict
from datetime import datetime
import uuid

router = APIRouter(prefix="/labor-profiles", tags=["Labor Profiles"])

@router.get("/{company_id}")
def list_profiles(company_id: str, environment: str = Depends(verify_hmac)):
    """List all Labor Profiles for a specific company."""
    client = get_db(namespace=company_id).client
    query = client.query(kind="LaborProfile")
    query.add_filter("company_id", "=", company_id)
    
    profiles = []
    for entity in query.fetch():
        profiles.append({
            "id": entity.key.name,
            "name": entity.get("name"),
            "company_id": entity.get("company_id"),
            "max_weekly_hours": entity.get("max_weekly_hours", 40.0),
            "max_daily_hours": entity.get("max_daily_hours", 8.0),
            "max_consecutive_days": entity.get("max_consecutive_days", 6),
            "min_rest_hours": entity.get("min_rest_hours", 11.0),
            "is_default": entity.get("is_default", False),
            "last_updated": entity.get("last_updated")
        })
    
    return profiles

@router.post("/")
def create_or_update_profile(profile: LaborProfile, environment: str = Depends(verify_hmac)):
    """Create or update a Labor Profile."""
    client = get_db().client
    
    # Generate ID if not provided
    if not profile.id:
        profile.id = str(uuid.uuid4())
    
    key = client.key("LaborProfile", profile.id)
    
    from google.cloud import datastore
    entity = datastore.Entity(key=key)
    entity.update({
        "name": profile.name,
        "company_id": profile.company_id,
        "max_weekly_hours": profile.max_weekly_hours,
        "max_daily_hours": profile.max_daily_hours,
        "max_consecutive_days": profile.max_consecutive_days,
        "min_rest_hours": profile.min_rest_hours,
        "is_default": profile.is_default,
        "last_updated": datetime.now()
    })
    
    # client.put(entity)
    return {"status": "success", "profile_id": profile.id, "message": "READ-ONLY: Write disabled"}

@router.delete("/{profile_id}")
def delete_profile(profile_id: str, environment: str = Depends(verify_hmac)):
    """Delete a Labor Profile."""
    client = get_db().client
    key = client.key("LaborProfile", profile_id)
    
    # Check if profile exists
    entity = client.get(key)
    if not entity:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # TODO: Check if any employees are using this profile
    # For now, we allow deletion
    
    # client.delete(key)
    return {"status": "success", "message": "READ-ONLY: Delete disabled"}

@router.post("/{profile_id}/clone")
def clone_profile(profile_id: str, target_company_id: str, new_name: str = None, environment: str = Depends(verify_hmac)):
    """Clone a profile to another company (or same company with new name)."""
    client = get_db().client
    
    # Fetch source profile
    source_key = client.key("LaborProfile", profile_id)
    source = client.get(source_key)
    
    if not source:
        raise HTTPException(status_code=404, detail="Source profile not found")
    
    # Create new profile
    new_id = str(uuid.uuid4())
    new_key = client.key("LaborProfile", new_id)
    
    from google.cloud import datastore
    entity = datastore.Entity(key=new_key)
    entity.update({
        "name": new_name or f"{source.get('name')} (Copy)",
        "company_id": target_company_id,
        "max_weekly_hours": source.get("max_weekly_hours", 40.0),
        "max_daily_hours": source.get("max_daily_hours", 8.0),
        "max_consecutive_days": source.get("max_consecutive_days", 6),
        "min_rest_hours": source.get("min_rest_hours", 11.0),
        "is_default": False,  # Never clone as default
        "last_updated": datetime.now()
    })
    
    client.put(entity)
    
    return {"status": "success", "new_profile_id": new_id}

@router.get("/assignments/{company_id}")
def list_assignments(company_id: str, environment: str = Depends(verify_hmac)):
    """List all employee-profile assignments for a specific company."""
    client = get_db().client
    query = client.query(kind="EmployeeLaborAssignment")
    query.add_filter("company_id", "=", company_id)
    
    assignments = {}
    for entity in query.fetch():
        assignments[entity.key.name] = entity.get("labor_profile_id")
    
    return assignments

@router.post("/assignments")
def assign_profile(employee_id: str, profile_id: Optional[str], company_id: str, environment: str = Depends(verify_hmac)):
    """Assign a Labor Profile to an employee."""
    client = get_db().client
    key = client.key("EmployeeLaborAssignment", employee_id)
    
    if not profile_id:
        # If profile_id is None/Empty, remove the assignment
        # client.delete(key)
        return {"status": "success", "message": "READ-ONLY: Remove disabled"}
    
    from google.cloud import datastore
    entity = datastore.Entity(key=key)
    entity.update({
        "employee_id": employee_id,
        "labor_profile_id": profile_id,
        "company_id": company_id,
        "last_updated": datetime.now()
    })
    
    # client.put(entity)
    return {"status": "success", "message": "READ-ONLY: Assign disabled"}

