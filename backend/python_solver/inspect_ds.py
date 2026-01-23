from google.cloud import datastore
import os

def inspect():
    client = datastore.Client(namespace="OVERCLEAN")
    print("Inspecting OVERCLEAN namespace...")
    
    kinds = ['Period', 'period', 'Activity', 'activity', 'Employment', 'employment']
    for kind in kinds:
        entities = list(client.query(kind=kind).fetch(limit=1))
        if entities:
            print(f"\nSample of {kind}:")
            print(dict(entities[0]))
        else:
            print(f"\nNo entities found for {kind}")

if __name__ == "__main__":
    inspect()
