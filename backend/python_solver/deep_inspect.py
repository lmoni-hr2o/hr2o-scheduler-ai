from google.cloud import datastore
import json

def inspect():
    for ns in [None, "OVERCLEAN", "OVERFLOW"]:
        client = datastore.Client(namespace=ns)
        for kind in ['Period', 'period']:
            query = client.query(kind=kind)
            results = list(query.fetch(limit=1))
            if results:
                print(f"\n--- Namespace: {ns}, Kind: {kind} ---")
                print(json.dumps(dict(results[0]), indent=2, default=str))

if __name__ == "__main__":
    inspect()
