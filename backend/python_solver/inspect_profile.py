from google.cloud import datastore
import json
client = datastore.Client()
key = client.key("DemandProfile", "5629499534213120")
ent = client.get(key)
if ent:
    data = json.loads(ent.get("data_json", "{}"))
    print(f"Total Activities: {len(data)}")
    keys = list(data.keys())
    print(f"Sample IDs: {keys[:10]}")
    for k in keys[:5]:
        print(f"Act {k} DOWs: {list(data[k].keys())}")
else:
    print("Profile not found")
