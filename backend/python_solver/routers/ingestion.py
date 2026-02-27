from fastapi import APIRouter, HTTPException, Request, Header, Depends
from utils.datastore_helper import get_db, SERVER_TIMESTAMP
import hmac
import hashlib
import json
import os
import secrets

router = APIRouter()
router = APIRouter()
# db = firestore.client() # Moved inside function to avoid init issues

# Hardcoded for development, matching the Node.js version
# In production, this should come from environment variables
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "development-secret-key-12345")

async def verify_hmac(request: Request, x_signature: str = Header(None)):
    """
    Middleware-like dependency to verify HMAC signature.
    """
    if not x_signature:
        raise HTTPException(status_code=401, detail="Missing X-Signature header")

    try:
        # In FastAPI, we need the raw bytes to verify HMAC accurately.
        # We read the body, then reset the stream so the endpoint can read it again.
        body_bytes = await request.body()
        
        # For compatibility with the Node.js simplifiction:
        # The Node version stringified the parsed JSON. To match that EXACTLY 
        # is tricky without knowing exact JSON serialization rules (spaces etc).
        # HOWEVER, the Python test script created the signature from the raw payload string.
        # So using raw bytes here is actually more correct and robust.
        
        # NOTE: If the test script sends JSON with specific spacing, 
        # and we verify raw bytes, it should match perfectly.
        
        computed_hmac = hmac.new(
            key=API_SECRET_KEY.encode('utf-8'),
            msg=body_bytes,
            digestmod=hashlib.sha256
        ).hexdigest()

        # Constant-time comparison
        if not hmac.compare_digest(computed_hmac, x_signature):
             raise HTTPException(status_code=403, detail="Invalid Signature")
             
    except HTTPException:
        raise
    except Exception as e:
        print(f"HMAC Error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@router.post("/import-data", dependencies=[Depends(verify_hmac)])
async def import_data(payload: dict):
    """
    Imports employee data to Firestore.
    Replaces the Node.js Cloud Function.
    """
    company_id = payload.get("company_id")
    employees = payload.get("employees")

    if not company_id or not isinstance(employees, list):
        raise HTTPException(status_code=400, detail="Invalid payload. 'company_id' and 'employees' list required.")

    try:
        db = get_db()
        batch = db.batch()
        company_ref = db.collection("companies").document(company_id)
        
        # Upsert company
        batch.set(company_ref, {"updated_at": SERVER_TIMESTAMP}, merge=True)

        for emp in employees:
            # Use provided ID or auto-generate
            emp_id = emp.get("id")
            if not emp_id:
                new_ref = company_ref.collection("employees").document()
                emp_id = new_ref.id
            
            emp_ref = company_ref.collection("employees").document(emp_id)
            
            data = {
                "first_name": emp.get("first_name"),
                "last_name": emp.get("last_name"),
                "role": emp.get("role"),
                "contract": emp.get("contract", {}),
                "updated_at": SERVER_TIMESTAMP()
            }
            
            batch.set(emp_ref, data, merge=True)

        # batch.commit()
        return {
            "message": "READ-ONLY: Import disabled",
            "count": len(employees)
        }

    except Exception as e:
        print(f"Import Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
