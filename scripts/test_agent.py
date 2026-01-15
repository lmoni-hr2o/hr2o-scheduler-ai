import hmac
import hashlib
import json
import requests
import time

SECRET_KEY = "development-secret-key-12345"
BASE_URL = "http://127.0.0.1:8000"
ENVIRONMENT = "development"

def generate_signature(payload_str, secret):
    return hmac.new(
        secret.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def sign_and_post(endpoint, payload):
    url = f"{BASE_URL}{endpoint}"
    payload_str = json.dumps(payload)
    signature = generate_signature(payload_str, SECRET_KEY)
    
    headers = {
        "Content-Type": "application/json",
        "X-HMAC-Signature": signature,
        "Environment": ENVIRONMENT
    }
    
    print(f"\n--- POST Request to {endpoint} ---")
    response = requests.post(url, headers=headers, data=payload_str)
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response Body: {response.text}")
    return response

def sign_and_get(endpoint, params=None):
    url = f"{BASE_URL}{endpoint}"
    signature = generate_signature("", SECRET_KEY) # Empty body for GET
    
    headers = {
        "X-HMAC-Signature": signature,
        "Environment": ENVIRONMENT
    }
    
    print(f"\n--- GET Request to {endpoint} ---")
    response = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response Body: {response.text}")
    return response

def test_agent_api():
    # 1. Test Period Creation (POST)
    print("\n[Testing Period Creation]")
    period_payload = {
        "environment": ENVIRONMENT,
        "allDay": True,
        "partialDay": "G",
        "beginTimePlan": "2024-01-01T09:00:00",
        "endTimePlan": "2024-01-01T17:00:00",
        "latitude": 45.4642,
        "longitude": 9.1900,
        "positionDetectionSystem": "gps",
        "timeDetectionSystem": "ntp"
    }
    sign_and_post("/agent/periods", period_payload)

    # 2. Test Schedule Generation (POST)
    print("\n[Testing Schedule Generation]")
    gen_payload = {
        "start_date": "2024-01-01",
        "end_date": "2024-01-07",
        "employees": [
            {"id": "e1", "name": "Mario Rossi", "role": "Cashier"},
            {"id": "e2", "name": "Luigi Verdi", "role": "Manager"}
        ],
        "required_shifts": [
            {
                "id": "shift_1",
                "date": "2024-01-01",
                "start_time": "09:00",
                "end_time": "13:00",
                "role": "Cashier"
            }
        ]
    }
    sign_and_post("/schedule/generate", gen_payload)

    # 3. Test Learning Environment Lockdown (POST)
    print("\n[Testing Training (Allowed in Development)]")
    train_payload = {
        "action": "manual_override",
        "selected_id": "e1",
        "shift_data": {"shift_id": "123"}
    }
    sign_and_post("/training/log-feedback", train_payload)

    # 4. Test Reading Activities (GET)
    print("\n[Testing Reading Activities (GET)]")
    sign_and_get("/agent/activities")

    # 5. Test Error: Missing Environment Header (GET)
    print("\n[Testing Error: Missing Environment Header]")
    url = f"{BASE_URL}/agent/activities"
    signature = generate_signature("", SECRET_KEY)
    resp = requests.get(url, headers={"X-HMAC-Signature": signature})
    print(f"Status Code: {resp.status_code}, Body: {resp.text}")

if __name__ == "__main__":
    test_agent_api()
