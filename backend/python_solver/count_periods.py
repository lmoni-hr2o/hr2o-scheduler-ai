from google.cloud import datastore
import os
client = datastore.Client()
environment = "PROFER"
query = client.query(kind="Period")
query.add_filter("environment", "=", environment)
# Count without fetching all
count = 0
for _ in query.fetch(keys_only=True):
    count += 1
print(f"Total Periods for {environment}: {count}")
