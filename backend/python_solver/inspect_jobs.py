from google.cloud import datastore
import datetime

def inspect_jobs():
    client = datastore.Client()
    query = client.query(kind="AsyncJob")
    query.order = ["-created_at"]
    
    print(f"{'Job ID':<40} | {'Status':<15} | {'Created At':<30} | {'Updated At':<30}")
    print("-" * 120)
    
    for entity in query.fetch(limit=10):
        print(f"{entity.get('job_id', 'N/A'):<40} | {entity.get('status', 'N/A'):<15} | {str(entity.get('created_at')):<30} | {str(entity.get('updated_at')):<30}")

if __name__ == "__main__":
    inspect_jobs()
