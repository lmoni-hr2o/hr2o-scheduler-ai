
import hmac, hashlib, json, requests
secret = 'development-secret-key-12345'
base_url = 'https://timeplanner-466805262752.europe-west3.run.app'

def make_headers(payload, env):
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return {'Content-Type': 'application/json', 'X-HMAC-Signature': signature, 'Environment': env}

env = "OVERCLEAN"

# 1. Fetch some real data from production
emp_headers = make_headers('', env)
emp_resp = requests.get(f'{base_url}/agent/employment', headers=emp_headers)
if emp_resp.status_code != 200:
    print('Failed to fetch employment:', emp_resp.text)
    exit(1)
employees = emp_resp.json()[:5] # Just take 5

act_resp = requests.get(f'{base_url}/agent/activities', headers=emp_headers)
activities = act_resp.json()[:5]

# 2. Test Synchronous Generation
payload = {
    'start_date': '2026-03-09', # Next Monday
    'end_date': '2026-03-09',
    'employees': employees,
    'activities': activities,
    'required_shifts': [],
    'unavailabilities': [],
    'constraints': {'min_rest_hours': 11}
}
payload_str = json.dumps(payload, separators=(',', ':'))
gen_headers = make_headers(payload_str, env)
print('Triggering synchronous generation on production...')
gen_resp = requests.post(f'{base_url}/schedule/generate', data=payload_str, headers=gen_headers)

print('Status:', gen_resp.status_code)
if gen_resp.status_code == 200:
    res = gen_resp.json()
    print('Response Status:', res.get('status'))
    print('Shift Count:', len(res.get('schedule', [])))
    print('Message:', res.get('message'))
    if len(res.get('schedule', [])) > 0:
        print('SUCCESS: Production is working in synchronous mode.')
else:
    print('ERROR:', gen_resp.text)
