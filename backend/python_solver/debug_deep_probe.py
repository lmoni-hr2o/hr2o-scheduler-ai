
from google.cloud import datastore

client = datastore.Client(project="hrtimeplace")

def probe():
    print("--- DEEP PROBE: OVERCLEAN & Company Data ---")
    
    # 1. Check Employees in OVERCLEAN (or similar)
    # The solver likely gets them from here or company NS
    nss = ["OVERCLEAN", "4779563276042240", "6196145969692672"]
    
    for ns in nss:
        print(f"\nNamespace: {ns}")
        q = client.query(kind="Employment", namespace=ns)
        emps = list(q.fetch(limit=10))
        print(f"  > Found {len(emps)} sample employees.")
        for e in emps:
            print(f"    - {e.get('fullName') or e.get('name')}: Profile={e.get('labor_profile_id')}, Role={e.get('role')}")
            
        # Check profiles in this NS
        q_lp = client.query(kind="LaborProfile", namespace=ns)
        lps = list(q_lp.fetch())
        print(f"  > Found {len(lps)} profiles in this NS: {[p.key.name for p in lps]}")

if __name__ == "__main__":
    probe()
