from google.cloud import datastore
from datetime import datetime

def get_id_or_name(key):
    if key is None: return None
    return key.id or key.name

def migrate_periods_to_company_namespaces(root_namespace: str = "OVERCLEAN"):
    """
    Moves Period entities from a root namespace to their specific company ID namespaces.
    Extracts target namespace from nested employment.company links.
    """
    client = datastore.Client()
    messages = []
    messages.append(f"Starting hyper-defensive migration for namespace: {root_namespace}")
    
    # 1. Stream Periods in the root namespace
    query_period = client.query(kind="Period", namespace=root_namespace)
    
    migrated_count = 0
    error_count = 0
    batch = client.batch()
    batch.begin()
    
    for p in query_period.fetch():
        target_ns = None
        
        # Strategy A: Extract from nested employment entity
        emp_ent = p.get("employment")
        if isinstance(emp_ent, datastore.Entity):
            comp_ent = emp_ent.get("company")
            if isinstance(comp_ent, datastore.Entity) and hasattr(comp_ent, 'key') and comp_ent.key:
                target_ns = str(get_id_or_name(comp_ent.key))
            elif isinstance(comp_ent, dict) and "id" in comp_ent:
                target_ns = str(comp_ent["id"])
        
        # Strategy B: Fallback to top-level fields
        if not target_ns:
            target_ns = p.get("companyId") or p.get("company_id")
        
        if not target_ns or target_ns == "None":
            error_count += 1
            continue
            
        # Create new key in target namespace
        p_id = get_id_or_name(p.key)
        if not p_id: 
            error_count += 1
            continue
            
        new_key = client.key("Period", p_id, namespace=target_ns)
        new_entity = datastore.Entity(key=new_key)
        new_entity.update(dict(p))
        
        # Ensure employmentId is set for future lookups
        if not new_entity.get("employmentId") and isinstance(emp_ent, datastore.Entity) and emp_ent.key:
            new_entity["employmentId"] = str(get_id_or_name(emp_ent.key))
            
        new_entity["migrated_from_root"] = True
        new_entity["migrated_at"] = datetime.now()
        
        batch.put(new_entity)
        migrated_count += 1
        
        if migrated_count % 300 == 0:
            batch.commit()
            print(f"Migrated {migrated_count} periods so far...")
            batch = client.batch()
            batch.begin()
            
    batch.commit()
    messages.append(f"Successfully migrated {migrated_count} periods. Missed {error_count} (no company link).")
    
    return messages
