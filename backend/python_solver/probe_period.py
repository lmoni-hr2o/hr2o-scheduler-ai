from google.cloud import datastore
client = datastore.Client(namespace='6196145969692672')
query = client.query(kind='Period')
res = list(query.fetch(limit=1))
if res:
    print("--- PERIOD ENTITY KEYS ---")
    print(list(res[0].keys()))
    print("\n--- SAMPLE VALUES ---")
    print(f"tmregister: {res[0].get('tmregister')}")
    print(f"beginTimePlace: {res[0].get('beginTimePlace')}")
    # Print size estimate
    import sys
    print(f"\nEntity Size (approx): {sys.getsizeof(str(res[0])) / 1024:.1f} KB")
else:
    print("No Period found in namespace 6196145969692672")
