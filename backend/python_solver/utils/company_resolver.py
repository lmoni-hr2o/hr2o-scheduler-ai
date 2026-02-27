from google.cloud import datastore
from typing import Optional
from cachetools import cached, TTLCache

# Cache resolutions for 10 minutes to avoid Datastore hits on every request
resolver_cache = TTLCache(maxsize=1000, ttl=600)

@cached(cache=resolver_cache)
def resolve_environment_to_id(environment: Optional[str]) -> Optional[str]:
    """
    Takes an environment string (might be a Datastore ID or a Company Code like '1362')
    and resolves it to the correct Datastore numeric ID.
    """
    if not environment:
        return environment
        
    # Sanitize: Datastore namespaces cannot contain slashes
    env_str = str(environment).strip().replace("/", "_")
    
    if env_str.upper() == "OVERCLEAN":
        return env_str
        
    client = datastore.Client()
    
    # 1. See if the ID works directly (Company entity usually copied to its own namespace)
    # actually, querying the namespace metadata directly is safer.
    # but querying a single key is very fast.
    key1 = client.key("Company", env_str, namespace=env_str)
    comp1 = client.get(key1)
    if comp1:
        return env_str # Valid ID already
        
    # 2. Try looking up in OVERCLEAN as a code
    q_comp = client.query(kind="Company", namespace="OVERCLEAN")
    q_comp.add_filter("code", "=", env_str)
    comp_res = list(q_comp.fetch(limit=1))
    
    if comp_res:
        real_env = comp_res[0].key.name or comp_res[0].key.id
        print(f"DEBUG: Resolved environment/code '{env_str}' to ID '{real_env}'")
        return str(real_env)
        
    # 3. If everything fails, assume it's an ID that hasn't been synced properly
    # but still return it as is.
    return env_str
