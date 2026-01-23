from google.cloud import datastore
import os

def check_ids():
    for ns in [None, "OVERCLEAN", "OVERFLOW"]:
        print(f"\n--- Namespace: {ns} ---")
        client = datastore.Client(namespace=ns)
        for kind in ['Period', 'period']:
            print(f"Kind: {kind}")
            try:
                query = client.query(kind=kind)
                for entity in query.fetch(limit=20):
                    data = dict(entity)
                    env = data.get("environment")
                    emp = data.get("employment", {})
                    comp = emp.get("company", {}) if isinstance(emp, dict) else {}
                    
                    c_id = comp.get("id")
                    c_code = comp.get("code")
                    c_name = comp.get("name")
                    
                    proj = data.get("activities", {}).get("project", {})
                    p_code = proj.get("code")
                    p_cust = proj.get("customer", {})
                    
                    print(f"  Env: {env} | CompID: {c_id} | CompCode: {c_code} | CompName: {c_name} | ProjCode: {p_code}")
            except Exception as e:
                print(f"  Error: {e}")

if __name__ == "__main__":
    check_ids()
