from google.cloud import datastore
from datetime import datetime
client = datastore.Client(namespace='6196145969692672')
query = client.query(kind='Period')
query.add_filter('tmregister', '>=', datetime(2026, 1, 1))
res = list(query.fetch(limit=5))
print(f"Namespaced Count: {len(res)}")
if res: print(f"Sample: {res[0].get('tmregister')}")

client_default = datastore.Client()
query2 = client_default.query(kind='Period')
query2.add_filter('environment', '=', '6196145969692672')
query2.add_filter('tmregister', '>=', datetime(2026, 1, 1))
# This might fail due to index, but if we remove one of them it works
query3 = client_default.query(kind='Period')
query3.add_filter('environment', '=', '6196145969692672')
res3 = list(query3.fetch(limit=5))
print(f"Default NS Count (Env filter): {len(res3)}")
