from google.cloud import datastore
import os

def debug_data():
    for ns in [None, "OVERCLEAN", "OVERFLOW"]:
        print(f"\n--- Namespace: {ns} ---")
        client = datastore.Client(namespace=ns)
        for kind in ["Period", "period", "LearningLog"]:
            query = client.query(kind=kind)
            entities = list(query.fetch(limit=5))
            if not entities:
                print(f"Kind '{kind}': No data")
                continue
            
            print(f"Kind '{kind}': Found {len(entities)} (example structure follow)")
            for e in entities:
                data = dict(e)
                # Check for environment
                env = data.get('environment')
                # Check for activity name
                act = data.get('activities', {})
                act_name = act.get('name') if isinstance(act, dict) else "N/A"
                # Check for employment company
                emp = data.get('employment', {})
                comp_name = emp.get('company', {}).get('name') if isinstance(emp, dict) else "N/A"
                pers_name = emp.get('person', {}).get('fullName') if isinstance(emp, dict) else "N/A"
                
                print(f"  - ID: {e.key.id_or_name}")
                print(f"    Env Field: {env}")
                print(f"    Activity Name: {act_name}")
                print(f"    Company Name: {comp_name}")
                print(f"    Person Name: {pers_name}")
                break # Only one example per kind/ns

if __name__ == "__main__":
    debug_data()
