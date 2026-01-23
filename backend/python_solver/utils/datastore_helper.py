"""
Datastore Helper Module
Provides a Firestore-like interface for Google Cloud Datastore (Datastore Mode).
"""
from google.cloud import datastore
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

# Constant to replace firestore.SERVER_TIMESTAMP
SERVER_TIMESTAMP = datetime.utcnow

class DatastoreClient:
    """Wrapper around Datastore client to mimic Firestore API"""
    
    def __init__(self, namespace: Optional[str] = None):
        if namespace is not None:
            self.namespace = namespace
        else:
            self.namespace = os.getenv("DATASTORE_NAMESPACE")
        self.client = datastore.Client(namespace=self.namespace)
        print(f"DEBUG: Initialized DatastoreClient with namespace: {self.namespace}")
    
    def collection(self, collection_name: str):
        """Returns a CollectionReference-like object"""
        return CollectionReference(self.client, collection_name)
    
    def document(self, path: str):
        """
        Mimics Firestore db.document('path/to/doc')
        Useful for quick access.
        """
        parts = path.split('/')
        if len(parts) % 2 != 0:
            raise ValueError("Path must have an even number of parts (collection/doc/...)")
        
        # We start with a collection and then drill down
        current = self.collection(parts[0])
        doc = current.doc(parts[1])
        
        for i in range(2, len(parts), 2):
            current = doc.collection(parts[i])
            doc = current.doc(parts[i+1])
            
        return doc

    def key(self, *args, **kwargs):
        """Proxy to native datastore.Client.key"""
        return self.client.key(*args, **kwargs)

    def get(self, *args, **kwargs):
        """Proxy to native datastore.Client.get"""
        return self.client.get(*args, **kwargs)

    def batch(self):
        """Returns a batch object for batched writes"""
        return DatastoreBatch(self.client)


class DatastoreBatch:
    """Mimics Firestore WriteBatch for Datastore"""
    
    def __init__(self, client: datastore.Client):
        self.client = client
        self.operations = []
    
    def set(self, doc_ref, data: Dict[str, Any], merge: bool = False):
        """Adds a set operation to the batch"""
        # Replace SERVER_TIMESTAMP with actual datetime
        processed_data = {}
        for key, value in data.items():
            if callable(value):  # Check if it's SERVER_TIMESTAMP function
                processed_data[key] = datetime.utcnow()
            else:
                processed_data[key] = value
        
        self.operations.append(('set', doc_ref.key, processed_data, merge))
        return self
    
    def commit(self):
        """Commits all batched operations"""
        entities_to_put = []
        
        for op_type, key, data, merge in self.operations:
            if op_type == 'set':
                if merge:
                    # Fetch existing entity and merge
                    existing = self.client.get(key)
                    if existing:
                        existing.update(data)
                        entities_to_put.append(existing)
                    else:
                        entity = datastore.Entity(key=key)
                        entity.update(data)
                        entities_to_put.append(entity)
                else:
                    entity = datastore.Entity(key=key)
                    entity.update(data)
                    entities_to_put.append(entity)
        
        if entities_to_put:
            self.client.put_multi(entities_to_put)


class CollectionReference:
    """Mimics Firestore CollectionReference for Datastore"""
    
    def __init__(self, client: datastore.Client, kind: str, parent_key=None):
        self.client = client
        self.kind = kind
        self.parent_key = parent_key
    
    def doc(self, doc_id: str):
        """Returns a DocumentReference-like object"""
        if self.parent_key:
            key = self.client.key(self.kind, doc_id, parent=self.parent_key)
        else:
            key = self.client.key(self.kind, doc_id)
        return DocumentReference(self.client, key, self.kind)
    
    def document(self, doc_id: Optional[str] = None):
        """Alias for doc() to match Firestore API"""
        if doc_id is None:
            # Generate a new ID
            incomplete_key = self.client.key(self.kind, parent=self.parent_key)
            return DocumentReference(self.client, incomplete_key, self.kind)
        return self.doc(doc_id)
    
    def stream(self):
        """Returns all entities in this collection"""
        query = self.client.query(kind=self.kind, ancestor=self.parent_key)
        entities = list(query.fetch())
        return [DatastoreDocument(entity) for entity in entities]
    
    def where(self, field: str, op: str, value: Any):
        """Returns a Query object with filter"""
        return Query(self.client, self.kind, self.parent_key).where(field, op, value)


class DocumentReference:
    """Mimics Firestore DocumentReference for Datastore"""
    
    def __init__(self, client: datastore.Client, key, kind: str):
        self.client = client
        self.key = key
        self.kind = kind
        self.id = key.name or str(key.id) if key.id else None
    
    def collection(self, subcollection_name: str):
        """Returns a subcollection (nested kind in Datastore)"""
        return CollectionReference(self.client, subcollection_name, parent_key=self.key)
    
    def get(self):
        """Fetches the entity"""
        entity = self.client.get(self.key)
        if entity:
            return DatastoreDocument(entity)
        return None
    
    def set(self, data: Dict[str, Any]):
        """Creates or updates the entity"""
        entity = datastore.Entity(key=self.key)
        entity.update(data)
        self.client.put(entity)
    
    def to_dict(self):
        """Returns the entity data as dict"""
        entity = self.client.get(self.key)
        if entity:
            return dict(entity)
        return {}


class DatastoreDocument:
    """Mimics Firestore DocumentSnapshot for Datastore"""
    
    def __init__(self, entity: datastore.Entity):
        self.entity = entity
        self.id = entity.key.name or str(entity.key.id) if entity.key.id else None
    
    def to_dict(self):
        """Returns entity data as dict"""
        data = dict(self.entity)
        # Add the ID to the dict for compatibility
        data['id'] = self.id
        return data


class Query:
    """Mimics Firestore Query for Datastore"""
    
    def __init__(self, client: datastore.Client, kind: str, parent_key=None):
        self.client = client
        self.kind = kind
        self.parent_key = parent_key
        self.query = client.query(kind=kind, ancestor=parent_key)
    
    def where(self, field: str, op: str, value: Any):
        """Adds a filter to the query"""
        # Convert Firestore operators to Datastore operators
        op_map = {
            '==': '=',
            '>=': '>=',
            '<=': '<=',
            '>': '>',
            '<': '<'
        }
        datastore_op = op_map.get(op, '=')
        self.query.add_filter(field, datastore_op, value)
        return self
    
    def stream(self):
        """Executes the query and returns results"""
        entities = list(self.query.fetch())
        return [DatastoreDocument(entity) for entity in entities]


def get_db(namespace: Optional[str] = None):
    """Returns a Datastore client with Firestore-like interface"""
    return DatastoreClient(namespace=namespace)
