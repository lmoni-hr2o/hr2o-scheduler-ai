from models import Employment, Activity
print("Models imported successfully")
try:
    e = Employment(id="123", name="Comp", fullName="John", role="worker")
    print("Employment instantiated")
except Exception as e:
    print(f"Employment error: {e}")

try:
    a = Activity(id="123", name="Act", environment="test")
    print("Activity instantiated")
except Exception as e:
    print(f"Activity error: {e}")
