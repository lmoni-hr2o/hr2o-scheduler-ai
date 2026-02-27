import hmac, hashlib, json, sys, time, requests
secret = 'development-secret-key-12345'
base_url = 'https://timeplanner-466805262752.europe-west3.run.app'

def make_headers(payload, env):
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return {'Content-Type': 'application/json', 'X-HMAC-Signature': signature, 'Environment': env}

env = "lmoni-hr2o/hr2o-scheduler-ai"
# fetch employment
emp_headers = make_headers('', env)
emp_resp = requests.get(f'{base_url}/agent/employment', headers=emp_headers)
print('Employment status', emp_resp.status_code)
if emp_resp.status_code != 200:
    print('Body', emp_resp.text)
    sys.exit(1)
employees = emp_resp.json()
print('Fetched', len(employees), 'employees')
# fetch activities
act_resp = requests.get(f'{base_url}/agent/activities', headers=emp_headers)
print('Activities status', act_resp.status_code)
if act_resp.status_code != 200:
    print('Body', act_resp.text)
    sys.exit(1)
activities = act_resp.json()
print('Fetched', len(activities), 'activities')
# generate schedule
payload = {
    'start_date': '2026-03-01',
    'end_date': '2026-03-07',
    'employees': employees,
    'activities': activities,
    'required_shifts': [],
    'unavailabilities': [],
    'constraints': {'min_rest_hours': 11}
}
payload_str = json.dumps(payload)
# trigger generation
gen_headers = make_headers(payload_str, env)
gen_resp = requests.post(f'{base_url}/schedule/generate', data=payload_str, headers=gen_headers)
print('Generate status', gen_resp.status_code)
if gen_resp.status_code != 200:
    print('Error', gen_resp.text)
    sys.exit(1)
job_id = gen_resp.json().get('job_id')
print('Job ID', job_id)
# poll for result
for i in range(30):
    time.sleep(2)
    status_resp = requests.get(f'{base_url}/schedule/job/{job_id}', headers=make_headers('', env))
    if status_resp.status_code != 200:
        continue
    data = status_resp.json()
    status = data.get('status')
    print('Poll', i, 'status', status)
    if status == 'completed':
        schedule = data.get('schedule')
        print('Completed. Shift count:', len(schedule))
        print(json.dumps(schedule[:3], indent=2))
        break
    elif status == 'failed':
        print('Job failed', data.get('error'))
        break
