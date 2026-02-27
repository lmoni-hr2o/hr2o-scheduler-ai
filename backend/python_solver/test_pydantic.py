import datetime
from models import Employment

data = {
    "id": "123",
    "name": "Test Co",
    "dtHired": datetime.datetime.now()
}
print(f"Data before: {data}")
try:
    emp = Employment(**data)
    print(f"Success! dtHired: {type(emp.dtHired)} = {emp.dtHired}")
except Exception as e:
    print(f"Failed: {e}")
