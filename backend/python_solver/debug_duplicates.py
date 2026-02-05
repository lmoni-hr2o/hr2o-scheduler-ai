from google.cloud import datastore
from collections import defaultdict

def check_duplicates(namespace):
    client = datastore.Client(namespace=namespace)
    query = client.query(kind='Employment')
    
    employees = list(query.fetch())
    print(f"Total Employment entities in {namespace}: {len(employees)}")
    
    by_name = defaultdict(list)
    for ent in employees:
        full_name = ent.get('fullName', 'Unknown').upper().strip()
        by_name[full_name].append({
            'id': ent.key.name,
            'role': ent.get('role'),
            'type': ent.get('type')
        })
        
    print("\nDUPLICATES FOUND:")
    print("-" * 60)
    found = False
    for name, list_ents in by_name.items():
        if len(list_ents) > 1:
            found = True
            print(f"Name: {name}")
            for e in list_ents:
                print(f"  - ID: {e['id']}, Role: {e['role']}, Type: {e['type']}")
                
    if not found:
        print("No duplicates found by name.")

if __name__ == "__main__":
    check_duplicates("6196145969692672")
