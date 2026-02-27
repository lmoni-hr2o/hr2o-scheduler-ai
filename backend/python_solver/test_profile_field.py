import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/lucamoni/.config/gcloud/application_default_credentials.json"
from google.cloud import datastore

client = datastore.Client()
query = client.query(kind="DemandProfile")
res = list(query.fetch(limit=10))
for p in res:
    print(f"Key: {p.key.name}, Env: {p.get('environment')}")
