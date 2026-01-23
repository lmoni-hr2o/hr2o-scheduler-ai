from utils.datastore_helper import get_db
from utils.mapping_helper import EnvironmentMapper
import json

def analyze_data():
    db = get_db()
    mapper = EnvironmentMapper()
    
    print("Discovering all companies...")
    companies = mapper.discover_all()
    
    results = []
    
    for company_id, meta in companies.items():
        # Get employees
        raw_list = mapper.get_employment(company_id)
        # Get activities
        raw_activities = mapper.get_activities(company_id)
        # Get periods (history)
        raw_periods = mapper.get_periods(company_id)
        
        results.append({
            "id": company_id,
            "employees": len(raw_list),
            "activities": len(raw_activities),
            "periods": len(raw_periods),
            "diagnostic": meta
        })
    
    # Sort by companies with most historical periods
    results.sort(key=lambda x: x['periods'], reverse=True)
    
    print("\nTop companies by data availability:")
    for r in results[:10]:
        print(f"Company: {r['id']}")
        print(f"  - Employees: {r['employees']}")
        print(f"  - Activities: {r['activities']}")
        print(f"  - Historical Periods: {r['periods']}")
        print(f"  - Health Score: {r['diagnostic'].get('quality_score', 0)}%")
        print("-" * 20)

if __name__ == "__main__":
    analyze_data()
