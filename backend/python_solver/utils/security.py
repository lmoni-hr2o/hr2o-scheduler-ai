import hmac
import hashlib
import json
import time
from fastapi import Request, HTTPException, Header
from typing import Optional

# Security Configuration
# In production, these should be in Secret Manager
ENV_SECRETS = {
    "production": "prod-secret-key-xyz",
    "development": "development-secret-key-12345",
    "staging": "staging-secret-key-abc"
}

DEFAULT_SECRET = "development-secret-key-12345"

async def verify_hmac(request: Request, x_hmac_signature: Optional[str] = Header(None), environment: Optional[str] = Header(None)):
    """
    FastAPI dependency to verify HMAC signature.
    Requires 'X-HMAC-Signature' and 'Environment' headers.
    """
    if not environment:
        raise HTTPException(status_code=400, detail="Missing 'Environment' header.")
    
    if not x_hmac_signature:
        raise HTTPException(status_code=401, detail="Missing 'X-HMAC-Signature' header.")

    # Get secret for this environment
    secret = ENV_SECRETS.get(environment, DEFAULT_SECRET)
    
    # Get request body
    body = await request.body()
    body_str = body.decode('utf-8')

    # Re-calculate signature
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        body_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, x_hmac_signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature.")

    return environment

def validate_environment(environment: str):
    """
    Simple check if environment is supported.
    """
    if environment not in ENV_SECRETS:
        raise HTTPException(status_code=400, detail=f"Unsupported environment: {environment}")
    return environment
