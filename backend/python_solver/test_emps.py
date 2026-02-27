import subprocess
from google.cloud import datastore

def count_employments(ns):
    try:
        client = datastore.Client(namespace=ns)
        query = client.query(kind="Employment")
        return len(list(query.fetch()))
    except Exception as e:
        print(f"Error querying {ns}: {e}")
        return -1

ns_str = "OVERCLEAN"
ns_num = "5629499534213120"

print(f"Employments in {ns_str}: {count_employments(ns_str)}")
print(f"Employments in {ns_num}: {count_employments(ns_num)}")
