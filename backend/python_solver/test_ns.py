from google.cloud import datastore
from datetime import datetime
import os

try:
    print("Testing Namespaced Query...")
    client = datastore.Client(namespace='6196145969692672')
    query = client.query(kind='Period')
    # Use a safe property that is likely indexed
    res = list(query.fetch(limit=10))
    print(f"Namespaced Count (limit 10): {len(res)}")
    if res: 
        print(f"Sample Kind: {res[0].kind}")
        print(f"Sample Env: {res[0].get('environment')}")
except Exception as e:
    print(f"Namespaced Error: {e}")

try:
    print("\nTesting Default NS Query...")
    client_default = datastore.Client()
    query2 = client_default.query(kind='Period')
    query2.add_filter('environment', '=', '6196145969692672')
    res2 = list(query2.fetch(limit=10))
    print(f"Default NS Count (Env filter, limit 10): {len(res2)}")
except Exception as e:
    print(f"Default NS Error: {e}")
