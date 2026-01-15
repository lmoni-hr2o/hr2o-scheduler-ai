from google.cloud import datastore
import json

def debug_datastore():
    client = datastore.Client(project='hrtimeplace')
    
    print("--- LearningLog ---")
    query = client.query(kind='LearningLog')
    logs = list(query.fetch(limit=5))
    print(f"Count: {len(logs)}")
    for log in logs:
        print(dict(log))
        
    print("\n--- Period ---")
    query = client.query(kind='Period')
    periods = list(query.fetch(limit=5))
    print(f"Count: {len(periods)}")
    for p in periods:
        data = dict(p)
        # Just show a bit of data
        print(f"ID: {p.key.name or p.key.id}, Employment: {data.get('employment', {}).get('person', {}).get('fullName')}")

if __name__ == "__main__":
    debug_datastore()
