from google.cloud import datastore
import json
import os

def check_ids():
    print("--- ID MISMATCH DEBUGGER ---")
    
    # Target reported by user (or use "OVERCLEAN" namespace directly)
    TARGET_NS = "OVERCLEAN" 
    
    try:
        client = datastore.Client(namespace=TARGET_NS)
        
        # 1. Fetch Employments (Reference)
        print(f"\nFetching Employments from '{TARGET_NS}'...")
        emps = list(client.query(kind="Employment").fetch(limit=50))
        print(f"Found {len(emps)} employments.")
        
        emp_map = {}
        print("Sample Employment IDs:")
        for e in emps[:5]:
            eid = str(e.key.id_or_name)
            data = dict(e)
            # Collect all possible IDs to help debugging
            details = {
                "key_id": eid,
                "id_field": data.get("id"),
                "code": (data.get("person") or {}).get("code"),
                "name": (data.get("person") or {}).get("name")
            }
            emp_map[eid] = data
            print(f"  - Key: {eid} | Data.id: {data.get('id')} | Name: {details['name']}")

        # 2. Fetch Periods (Assignment)
        print(f"\nFetching Periods from '{TARGET_NS}'...")
        periods = list(client.query(kind="Period").fetch(limit=50))
        print(f"Found {len(periods)} periods.")
        
        print("Analyzing Period -> Employment Links:")
        mismatch_count = 0
        for i, p in enumerate(periods[:10]):
            data = dict(p)
            emp_data = data.get("employment", {})
            
            # This is the logic used in training.py
            p_emp_id = str(emp_data.get("id", "")) or str(data.get("employmentId", ""))
            
            is_found = False
            # Check against Keys
            if p_emp_id in emp_map: is_found = True
            
            # Check against Data.id
            if not is_found:
                for eid, edata in emp_map.items():
                    if str(edata.get("id")) == p_emp_id:
                        is_found = True
                        break
            
            status = "MATCH" if is_found else "MISMATCH"
            if not is_found: mismatch_count += 1
            
            print(f"  [Period {i}] Used ID: '{p_emp_id}' -> {status}")
            if not is_found:
                print(f"     Details: employment object in Period: {json.dumps(emp_data, default=str)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_ids()
