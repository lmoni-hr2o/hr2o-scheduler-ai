from google.cloud import datastore

def discover_datastore():
    # We will try to find all namespaces first
    client = datastore.Client(project='hrtimeplace')
    
    print("--- Namespaces ---")
    query = client.query(kind='__namespace__')
    namespaces = [entity.key.id_or_name for entity in query.fetch()]
    if not namespaces:
        # Default namespace is None/empty string in some contexts, but let's add it
        namespaces = [None]
    print(f"Detected namespaces: {namespaces}")
    
    for ns in namespaces:
        print(f"\nScanning Namespace: [{ns}]")
        ns_client = datastore.Client(project='hrtimeplace', namespace=ns)
        
        # List all kinds in this namespace
        kind_query = ns_client.query(kind='__kind__')
        kinds = [entity.key.id_or_name for entity in kind_query.fetch()]
        print(f"  Kinds in {ns}: {kinds}")
        
        for kind in kinds:
            if kind.startswith('__'): continue
            count_query = ns_client.query(kind=kind)
            entities = list(count_query.fetch(limit=1))
            if entities:
                print(f"    Sample from {kind}: {dict(entities[0])}")

if __name__ == "__main__":
    discover_datastore()
