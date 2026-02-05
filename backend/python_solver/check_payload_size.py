from google.cloud import datastore
import json
import os

client = datastore.Client(namespace="PROFER")
# 1. Check Employees
query_emp = client.query(kind="Employment")
emps = list(query_emp.fetch())
emp_json = json.dumps([dict(e) for e in emps], default=str)
print(f"Employees: {len(emps)}, Total JSON size: {len(emp_json) / 1024:.2f} KB")

# 2. Check Activities
query_act = client.query(kind="Activity")
acts = list(query_act.fetch())
act_json = json.dumps([dict(a) for a in acts], default=str)
print(f"Activities: {len(acts)}, Total JSON size: {len(act_json) / 1024 / 1024:.2f} MB")

