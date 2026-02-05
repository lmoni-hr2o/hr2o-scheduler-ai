from google.cloud import datastore

def find_company():
    client = datastore.Client()
    # List all namespaces
    query = client.query(kind='__namespace__')
    namespaces = [entity.key.name for entity in query.fetch() if entity.key.name]
    namespaces.append(None) # Default namespace
    
    print(f"Searching for 'atempo' in {len(namespaces)} namespaces...")
    
    for ns in namespaces:
        ns_client = datastore.Client(namespace=ns)
        query = ns_client.query(kind='Company')
        for entity in query.fetch():
            name = entity.get('name', '').upper()
            if 'ATEMPO' in name:
                print(f"FOUND: Name='{entity.get('name')}', Namespace='{ns}', ID='{entity.key.name}'")

if __name__ == "__main__":
    find_company()
