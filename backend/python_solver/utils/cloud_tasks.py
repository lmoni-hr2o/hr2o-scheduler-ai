import os
import json
from google.cloud import tasks_v2

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "hrtimeplace")
REGION = os.getenv("GOOGLE_CLOUD_REGION", "europe-west3")
QUEUE_NAME = "schedule-workers"

def enqueue_task(url: str, payload: dict, in_seconds: int = 0):
    """
    Enqueues a task to the Cloud Tasks queue.
    :param url: The relative URL (path) of the worker endpoint (e.g., '/worker/solve').
    :param payload: The JSON payload to send to the worker.
    :param in_seconds: Delay execution by N seconds.
    """
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(PROJECT_ID, REGION, QUEUE_NAME)

    # Construct the request body
    task = {
        "http_request": {  # Specify the type of request.
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"https://timeplanner-466805262752.europe-west3.run.app{url}", # Self-call
            "headers": {"Content-Type": "application/json"},
        },
        "dispatch_deadline": {"seconds": 1800} # Allow up to 30 mins
    }

    if payload:
        # The API expects a payload of type bytes.
        converted_payload = json.dumps(payload).encode()
        task["http_request"]["body"] = converted_payload

    if in_seconds > 0:
        # Convert "in_seconds" to a timestamp
        from google.protobuf import timestamp_pb2
        import datetime
        d = datetime.datetime.utcnow() + datetime.timedelta(seconds=in_seconds)
        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(d)
        task["schedule_time"] = timestamp

    # Use the client to build and send the task.
    try:
        response = client.create_task(request={"parent": parent, "task": task})
        print(f"DEBUG: Task created: {response.name}")
        return response.name
    except Exception as e:
        print(f"CRITICAL: Failed to enqueue task: {e}")
        raise e
