import sys
from utils.datastore_helper import get_db
import json

def inspect_profile(env):
    try:
        client = get_db().client
        key = client.key("DemandProfile", env)
        entity = client.get(key)
        
        if not entity:
            print(f"❌ No DemandProfile found for environment: {env}")
            return
            
        print(f"✅ DemandProfile found for {env}")
        print(f"Last Updated: {entity.get('last_updated')}")
        
        data = entity.get("data_json")
        if data:
            profile = json.loads(data)
            print(f"Profile Keys (Activity IDs): {list(profile.keys())}")
            # print sample
            if profile:
                first_key = list(profile.keys())[0]
                print(f"Sample Entry [{first_key}]: {profile[first_key]}")
        else:
            print("⚠️ 'data_json' field is empty!")
            
    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    env = sys.argv[1] if len(sys.argv) > 1 else "lmoni-hr2o"
    inspect_profile(env)
