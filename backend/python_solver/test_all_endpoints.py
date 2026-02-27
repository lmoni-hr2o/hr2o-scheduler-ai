import hmac
import hashlib
import json
import urllib.request
import subprocess
import sys

def get_token():
    try:
        return subprocess.check_output(["gcloud", "auth", "print-identity-token"]).decode().strip()
    except Exception as e:
        print(f"Token Error: {e}")
        return None

token = get_token()
if not token: sys.exit(1)

secret_key = "development-secret-key-12345"

def make_req(endpoint, method="GET", payload=None):
    url = f"https://timeplanner-466805262752.europe-west3.run.app{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Environment": "OVERCLEAN"
    }
    
    data = None
    if payload is not None:
        json_payload = json.dumps(payload, separators=(',', ':'))
        signature = hmac.new(secret_key.encode(), json_payload.encode(), hashlib.sha256).hexdigest()
        headers["Content-Type"] = "application/json"
        headers["X-HMAC-Signature"] = signature
        data = json_payload.encode()
    else:
        signature = hmac.new(secret_key.encode(), "".encode(), hashlib.sha256).hexdigest()
        headers["X-HMAC-Signature"] = signature

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)

print("--- TESTING API ENDPOINTS ---")

# 1. Activities
status, body = make_req("/agent/activities")
print(f"[Activities] Status: {status}")
acts = []
if status == 200:
    acts = json.loads(body)
    print(f"  -> Found {len(acts)} activities. Sample: {acts[0].get('id') if acts else 'None'} ({acts[0].get('name') if acts else ''})")
else:
    print(f"  -> Error: {body}")

# 2. Employment
status, body = make_req("/agent/employment")
print(f"[Employment] Status: {status}")
emps = []
if status == 200:
    emps = json.loads(body)
    print(f"  -> Found {len(emps)} employments. Sample: {emps[0].get('id') if emps else 'None'} ({emps[0].get('firstName') if emps else ''})")
else:
    print(f"  -> Error: {body}")

# 3. Pre-check
if acts:
    # Use first 10 activities to get a good mix
    test_acts = acts[:10]
    test_emps = emps[:5] if emps else []
    
    payload = {
      "environment": "OVERCLEAN",
      "employees": test_emps,
      "activities": test_acts,
      "constraints": {"min_rest_hours": 11},
      "config": {},
      "start_date": "2026-02-23", # Monday
      "end_date": "2026-03-01"    # Sunday (1 week)
    }
    status, body = make_req("/reports/pre-check", "POST", payload)
    print(f"[Pre-Check] Status: {status}")
    if status == 200:
        res = json.loads(body)
        print(f"  -> Stats: {res.get('stats')}")
        print(f"  -> Summary: {res.get('summary')}")
    else:
        print(f"  -> Error: {body}")
else:
    print("[Pre-Check] Skipped due to no activities.")
