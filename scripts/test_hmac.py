import hmac
import hashlib
import json
import requests
import sys

# Configuration
# Pointing to the new unified Python service on Cloud Run
API_URL = "https://timeplanner-466805262752.europe-west3.run.app/api/v1/import-data" 
SECRET_KEY = "development-secret-key-12345"

def generate_signature(payload_str, secret):
    return hmac.new(
        secret.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def test_generation():
    print("\n--- Testing Stateless Solver ---")
    URL = "https://timeplanner-466805262752.europe-west3.run.app/schedule/generate"
    payload = {
        "start_date": "2023-01-01",
        "end_date": "2023-01-07",
        "employees": [
            {"id": "e1", "name": "Mario Rossi", "role": "Cashier"},
            {"id": "e2", "name": "Luigi Verdi", "role": "Manager"}
        ],
        "constraints": {"min_rest_hours": 11}
    }
    
    try:
        response = requests.post(URL, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Solution: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

def test_feedback():
    print("\n--- Testing Phase 5: Feedback Logging ---")
    URL = "https://timeplanner-466805262752.europe-west3.run.app/training/log-feedback"
    payload = {
        "action": "manual_override",
        "selected_id": "e2",  # User chose Luigi
        "rejected_id": "e1",  # User rejected Mario
        "shift_data": {"shift_id": "Mon_shift", "role": "Manager"}
    }
    response = requests.post(URL, json=payload)
    print(f"Feedback Status: {response.status_code}, Response: {response.json()}")

def test_retrain():
    print("\n--- Testing Phase 5: Retraining Loop ---")
    URL = "https://timeplanner-466805262752.europe-west3.run.app/training/retrain"
    payload = {} # Local DB retraining doesn't need params
    response = requests.post(URL, json=payload)
    print(f"Retrain Status: {response.status_code}, Response: {response.json()}")

def test_variable_shifts():
    print("\n--- Testing Phase 7.1: Variable Shift Durations (LOCAL) ---")
    URL = "http://127.0.0.1:8000/schedule/generate"
    payload = {
        "start_date": "2024-01-01",
        "end_date": "2024-01-07",
        "employees": [
            {"id": "e1", "name": "Mario Rossi", "role": "Cashier"},
            {"id": "e2", "name": "Luigi Verdi", "role": "Cashier"},
            {"id": "e3", "name": "Yoshi", "role": "Cashier"}
        ],
        "unavailabilities": [
          {"employee_id": "e1", "date": "2024-01-01"}
        ],
        "required_shifts": [
            {
                "id": "shift_1",
                "date": "2024-01-01",
                "start_time": "09:00",
                "end_time": "13:00",
                "role": "Cashier"
            },
            {
                "id": "shift_2",
                "date": "2024-01-01",
                "start_time": "10:00",
                "end_time": "12:00",
                "role": "Cashier"
            }
        ]
    }
    
    try:
        response = requests.post(URL, json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"Schedule: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"Error Body: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # To test locally, start the server with:
    # cd backend/python_solver && uvicorn main:app --reload
    # test_generation()
    # test_feedback()
    # test_retrain()
    test_variable_shifts()

