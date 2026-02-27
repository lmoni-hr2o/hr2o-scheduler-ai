try:
    from google.cloud import datastore
    import json
    import sys
    client = datastore.Client()
    key = client.key("DemandProfile", "5629499534213120")
    ent = client.get(key)
    if ent:
        data = json.loads(ent.get("data_json", "{}"))
        print(f"Total keys: {len(data)}")
        keys = sorted(list(data.keys()))
        print("Sample keys:")
        for k in keys[:50]:
            print(f"  - '{k}'")
    else:
        print("Profile not found")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
