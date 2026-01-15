from google.cloud import datastore
from datetime import datetime
import json

def get_client():
    return datastore.Client()

def init_db():
    """Datastore doesn't need explicit initialization like SQL."""
    pass

def save_log(action: str, selected_id: str, rejected_id: str, shift_data: dict, environment: str):
    """Saves a training log to Cloud Datastore."""
    client = get_client()
    key = client.key('LearningLog')
    log_entry = datastore.Entity(key=key, exclude_from_indexes=['shift_data'])
    
    log_entry.update({
        'timestamp': datetime.utcnow(),
        'action': action,
        'selected_id': selected_id,
        'rejected_id': rejected_id,
        'shift_data': json.dumps(shift_data),
        'environment': environment
    })
    
    client.put(log_entry)

def get_all_logs(environment: str):
    """Retrieves all logs for a specific environment from Datastore."""
    client = get_client()
    query = client.query(kind='LearningLog')
    query.add_filter('environment', '=', environment)
    query.order = ['-timestamp']
    
    results = list(query.fetch())
    logs = []
    for entity in results:
        log_dict = dict(entity)
        # Parse JSON back to dict if needed
        if 'shift_data' in log_dict:
            log_dict['shift_data'] = json.loads(log_dict['shift_data'])
        logs.append(log_dict)
    
    return logs
