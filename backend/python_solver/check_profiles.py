import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/lucamoni/.config/gcloud/application_default_credentials.json"
from google.cloud import datastore

client = datastore.Client()
query = client.query(kind="DemandProfile")
for p in query.fetch():
    print(p.key.namespace, p.key.name, dict(p).keys())
