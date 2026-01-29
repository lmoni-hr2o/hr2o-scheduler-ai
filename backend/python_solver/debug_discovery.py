from google.cloud import datastore
import json
import os

def debug_discovery():
    print("--- DEBUG DISCOVERY STARTED ---")
    
    TARGET = "5398177821753344"
    
    # Check all namespaces
    for ns in [None, "OVERCLEAN", "OVERFLOW"]:
        print(f"\nScanning Namespace: '{ns}'")
        try:
            client = datastore.Client(namespace=ns)
            
            # 1. Scan COMPANY entities
            print("  > Checking 'Company' entities...")
            query_c = client.query(kind="Company")
            companies = list(query_c.fetch(limit=50))
            for c in companies:
                cid = str(c.key.id_or_name)
                data = dict(c)
                name = data.get("name")
                code = data.get("code")
                if cid == TARGET or code == TARGET:
                    print(f"    *** FOUND TARGET COMPANY! ID={cid}, Name={name}, Code={code} ***")
                elif name and ("OVERCLEAN" in name.upper() or "PROFER" in name.upper()):
                     print(f"    Found Potential Match: ID={cid}, Name={name}, Code={code}")
            
            # 2. Scan PERIOD entities
            query = client.query(kind="Period")
            results = list(query.fetch(limit=100))
            
            print(f"  > Found {len(results)} Period entities (sample 100).")
            
            if not results:
                continue

            print("  > Analyzing first 5 entities...")
            for i, entity in enumerate(results[:5]):
                data = dict(entity)
                eid = str(entity.key.id_or_name)
                
                # Check for Company ID fields
                found_keys = {}
                
                # Flat keys
                for key in ["environment", "companyId", "aziendaId", "idAzienda", "company_id"]:
                    if key in data: found_keys[f"FLAT:{key}"] = data[key]
                
                # Nested Employment
                emp = data.get("employment")
                if isinstance(emp, dict):
                     comp = emp.get("company", {})
                     if isinstance(comp, dict):
                         for k in ["id", "code", "name"]:
                             if k in comp: found_keys[f"EMP:company.{k}"] = comp[k]
                     for k in ["environment", "namespace", "aziendaId"]:
                         if k in emp: found_keys[f"EMP:{k}"] = emp[k]
                
                # Check match
                is_match = False
                for v in found_keys.values():
                    if str(v) == TARGET:
                        is_match = True
                        break
                
                print(f"    [Entity {i+1}] ID: {eid}")
                print(f"      Identifiers: {json.dumps(found_keys, default=str)}")
                if is_match: print(f"      *** MATCHES TARGET {TARGET} ***")

        except Exception as e:
            print(f"Error scanning namespace {ns}: {e}")

if __name__ == "__main__":
    debug_discovery()
