from utils.mapping_helper import mapper
import json

def debug():
    print("Running discover_all...")
    mapper.discover_all()
    print(f"Total mappings: {len(mapper._mappings)}")
    print(json.dumps(mapper._mappings, indent=2))
    
    # Test lookups
    test_ids = ["OVERCLEAN", "123", "VBC"]
    for tid in test_ids:
        ns = mapper.get_namespace(tid)
        print(f"ID: {tid} -> NS: {ns}")

if __name__ == "__main__":
    debug()
