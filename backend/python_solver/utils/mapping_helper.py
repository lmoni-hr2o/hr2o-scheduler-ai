import time
from typing import Dict, List, Optional
from utils.datastore_helper import get_db

class EnvironmentMapper:
    """
    Singleton to manage company-to-namespace mappings.
    Speeds up lookups by avoiding multi-namespace scans.
    """
    _instance = None
    _mappings: Dict[str, Dict] = {} # id -> {ns, name}
    _entities: Dict[str, Dict] = {} # id -> {Activity: [], Employment: [], Period: []}
    _diagnostics: Dict[str, Dict] = {} # id -> diagnostic metrics
    _last_refresh = 0
    _refresh_interval = 600 # 10 minutes

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EnvironmentMapper, cls).__new__(cls)
        return cls._instance

    def refresh_if_needed(self, force=False):
        if force or (time.time() - self._last_refresh > self._refresh_interval):
            self.discover_all()

    def discover_all(self):
        name_to_ids = {} # name -> set(ids)
        id_to_ns = {} # id -> ns
        raw_entities = [] # list of (ns, kind, data)
        
        for ns in [None, "OVERCLEAN", "OVERFLOW"]:
            client = get_db(namespace=ns).client
            # 1. Scan Periods and direct kinds
            for kind in ['Period', 'period', 'Activity', 'activity', 'Employment', 'employment']:
                try:
                    # Increase limit to capture more data
                    for entity in client.query(kind=kind).fetch(limit=5000):
                        data = dict(entity)
                        data["_ns"] = ns
                        data["_kind"] = kind
                        if entity.key.id:
                            data["_entity_id"] = str(entity.key.id)
                        elif entity.key.name:
                            data["_entity_id"] = str(entity.key.name)
                        raw_entities.append(data)
                        
                        emp = data.get("employment", data if kind.lower() == 'employment' else {})
                        comp = ((emp or {}).get("company", {}) if isinstance(emp, (dict, type(None))) else {})
                        comp_name = (comp or {}).get("name")
                        
                        if comp_name:
                            comp_name_clean = str(comp_name).strip().upper()
                            if comp_name_clean not in name_to_ids: name_to_ids[comp_name_clean] = set()
                            
                            field_srcs = [
                                (comp or {}).get("id"), (comp or {}).get("code"), 
                                (comp or {}).get("idAzienda"), (comp or {}).get("aziendaId"),
                                data.get("environment"), data.get("companyId"), 
                                data.get("aziendaId"), data.get("idAzienda"),
                                data.get("codiceAzienda"), data.get("azienda"),
                                data.get("codAzienda"), data.get("idazienda")
                            ]
                            current_ids = set()
                            for key in field_srcs:
                                if key and str(key).lower() not in ["development", "test", "none", "unknown", ""]:
                                    current_ids.add(str(key))
                                    id_to_ns[str(key)] = ns
                            
                            name_to_ids[comp_name_clean].update(current_ids)
                            id_to_ns[comp_name_clean] = ns
                except Exception as e:
                    print(f"Mapper scan error (kind={kind}, ns={ns}): {e}")

        # 2. External API Discovery
        final_entries = {}
        entities_by_company = {}
        import requests
        all_companies = []
        for ns in ["OVERCLEAN", "OVERFLOW"]:
            try:
                url = f"https://europe-west3-hrtimeplace.cloudfunctions.net/company?namespace={ns}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    companies = response.json()
                    print(f"DEBUG: API found {len(companies)} companies for {ns}")
                    for company in companies:
                        company['_namespace'] = ns
                        all_companies.append(company)
                else:
                    print(f"ERROR: External company API returned {response.status_code} for {ns}: {response.text}")
            except Exception as e:
                print(f"CRITICAL: Failed to fetch companies for {ns}: {e}")

        # Fallback: Create entries from name_to_ids if API missed them
        for cname, ids in name_to_ids.items():
            for cid in ids:
                if not any(str(c.get('id')) == cid for c in all_companies):
                    all_companies.append({
                        "id": cid,
                        "name": cname,
                        "code": cid,
                        "_namespace": id_to_ns.get(cid)
                    })

        for company in all_companies:
            cid = str(company['id'])
            cname = str(company.get('name', cid)).strip().upper()
            final_entries[cid] = {
                "ns": company.get('_namespace'),
                "name": company.get('name', cid),
                "aliases": [cid, company.get('code', ''), cname]
            }
            entities_by_company[cid] = {"Activity": [], "Employment": [], "Period": []}

        # 3. Match entities (Fuzzy)
        for data in raw_entities:
            kind = data["_kind"].lower()
            matched_id = None
            
            # Extract possible identifiers to match
            names_to_try = set()
            ids_to_try = set()
            
            # 1. Collect IDs from various fields (Flat and common)
            for key in ["environment", "companyId", "aziendaId", "azienda", "idAzienda", "id_azienda", "codiceAzienda", "cod_azienda", "idazienda", "company_id"]:
                val = data.get(key)
                if val: ids_to_try.add(str(val).strip())
            
            # 2. Collect names and IDs from Employment/Period (Nested)
            if kind in ['employment', 'period']:
                emp_d = data.get("employment") if kind == 'period' else data
                if isinstance(emp_d, dict):
                    # Company Name
                    n = (emp_d.get("company") or {}).get("name")
                    if n: names_to_try.add(str(n).strip().upper())
                    # Company IDs
                    for k in ["id", "code", "idAzienda", "aziendaId"]:
                        cid = (emp_d.get("company") or {}).get(k)
                        if cid: ids_to_try.add(str(cid).strip())
                    # Flat IDs within nested employment
                    for k in ["aziendaId", "idAzienda", "id_azienda", "environment", "namespace", "_ns"]:
                        cid = emp_d.get(k)
                        if cid: ids_to_try.add(str(cid).strip())
            
            # 3. Collect names from Activity
            if kind in ['activity', 'activities', 'period']:
                act_d = data.get("activities") if kind == 'period' else data
                if isinstance(act_d, dict):
                    # Customer Name
                    cust = (act_d.get("project") or {}).get("customer", {})
                    if isinstance(cust, dict):
                        n = cust.get("name")
                        if n: names_to_try.add(str(n).strip().upper())
                        cid = cust.get("id")
                        if cid: ids_to_try.add(str(cid).strip())
                    
                    # Project Name (sometimes same as customer)
                    n2 = (act_d.get("project") or {}).get("name")
                    if n2: names_to_try.add(str(n2).strip().upper())

            # 4. Perform Matching
            # Try ID first (Strict)
            for tid in ids_to_try:
                if tid in final_entries:
                    matched_id = tid
                    break
                # Check aliases
                for cid, info in final_entries.items():
                    if tid in info["aliases"]:
                        matched_id = cid
                        break
                if matched_id: break
            
            # Try Name (Fuzzy)
            if not matched_id:
                for name in names_to_try:
                    for cid, info in final_entries.items():
                        cname = str(info["name"]).strip().upper()
                        if name == cname or name in cname or cname in name:
                            matched_id = cid
                            break
                    if matched_id: break
            
            # 5. LAST RESORT: Very loose match for Periods
            if not matched_id and kind == 'period':
                # Log a few unmatched periods to understand their structure
                if len(entities_by_company.get("_unmatched_debug", [])) < 5:
                    if "_unmatched_debug" not in entities_by_company: entities_by_company["_unmatched_debug"] = []
                    entities_by_company["_unmatched_debug"].append({
                        "keys": list(data.keys()),
                        "ids": list(ids_to_try),
                        "names": list(names_to_try)
                    })
                    print(f"DEBUG: Unmatched Period Keys: {list(data.keys())}")
                    print(f"DEBUG: Unmatched Period IDs found: {list(ids_to_try)}")
                    print(f"DEBUG: Unmatched Period Names found: {list(names_to_try)}")

            if matched_id:
                # Direct Entity or Nested (from Period)
                is_act = kind in ['activity', 'activities'] or (kind == 'period' and ("activities" in data or "project" in data))
                is_emp = kind in ['employment', 'employment'] or (kind == 'period' and ("employment" in data or "person" in data))
                
                if is_act:
                    entities_by_company[matched_id]["Activity"].append(data)
                if is_emp:
                    entities_by_company[matched_id]["Employment"].append(data)
                if kind == 'period':
                    entities_by_company[matched_id]["Period"].append(data)
            else:
                # Log unmatched for debugging
                if kind == 'period':
                    if len(entities_by_company.get("_unmatched_debug", [])) < 5:
                        if "_unmatched_debug" not in entities_by_company: entities_by_company["_unmatched_debug"] = []
                        entities_by_company["_unmatched_debug"].append(data)
        
        self._mappings = final_entries
        self._entities = entities_by_company
        self._id_to_ns = id_to_ns
        
        # 4. Calculate Diagnostics
        new_diagnostics = {}
        for cid, data in entities_by_company.items():
            if not isinstance(data, dict): continue
            
            emps = data.get("Employment", [])
            acts = data.get("Activity", [])
            pers = data.get("Period", [])
            
            # Employee stats
            emp_with_addr = 0
            emp_with_born = 0
            for e in emps:
                person = e.get("person", {}) or e.get("employment", {}).get("person", {}) or {}
                if person.get("address") or person.get("city"): emp_with_addr += 1
                if person.get("bornDate"): emp_with_born += 1
            
            # Activity stats
            act_with_addr = 0
            for a in acts:
                # Check deep in the structure for customer address
                proj = a.get("project", {}) or a.get("activities", {}).get("project", {}) or {}
                cust = proj.get("customer", {})
                if isinstance(cust, dict) and (cust.get("address") or cust.get("city")):
                    act_with_addr += 1

            new_diagnostics[cid] = {
                "total_employees": len(emps),
                "employees_with_address": emp_with_addr,
                "employees_with_born_date": emp_with_born,
                "total_activities": len(acts),
                "activities_with_address": act_with_addr,
                "total_periods": len(pers),
                "quality_score": (
                    (emp_with_addr / len(emps) if emps else 0) * 0.4 +
                    (act_with_addr / len(acts) if acts else 0) * 0.4 +
                    (1.0 if pers else 0.0) * 0.2
                ) * 100
            }

        self._diagnostics = new_diagnostics
        self._last_refresh = time.time()
        
        # Debug output
        summary = []
        for cid, lists in entities_by_company.items():
            if not isinstance(lists, dict): continue
            ac = len(lists.get("Activity", []))
            em = len(lists.get("Employment", []))
            pe = len(lists.get("Period", []))
            diag = new_diagnostics.get(cid, {})
            if ac > 0 or em > 0 or pe > 0:
                summary.append(f"{final_entries.get(cid, {'name': cid})['name']} ({cid}): A={ac}, E={em}, P={pe}, Quality={diag.get('quality_score', 0):.1f}%")
        
        print("--- Environment Mapping Summary ---")
        for s in summary[:20]: print(f"  {s}")
        if len(summary) > 20: print(f"  ... and {len(summary)-20} more matched companies")
        
        total_activities = sum(len(v["Activity"]) for v in entities_by_company.values() if isinstance(v, dict))
        total_employment = sum(len(v["Employment"]) for v in entities_by_company.values() if isinstance(v, dict))
        total_periods = sum(len(v["Period"]) for v in entities_by_company.values() if isinstance(v, dict))
        print(f"EnvironmentMapper: Matched {len(summary)} active companies. Total: {total_employment} employments, {total_activities} activities, {total_periods} periods.")

    def get_namespace(self, company_id: str) -> Optional[str]:
        self.refresh_if_needed()
        # Check direct mapping
        if hasattr(self, '_id_to_ns') and company_id in self._id_to_ns:
            return self._id_to_ns[company_id]
        
        # Search in aliases
        for entry in self._mappings.values():
            if company_id in entry.get("aliases", []):
                return entry["ns"]
                
        return None

    def get_all_companies(self) -> List[Dict]:
        self.refresh_if_needed()
        res = []
        for company_id, info in self._mappings.items():
            entities = self._entities.get(company_id, {})
            # Relaxed visibility: Must have at least SOME data
            has_activities = len(entities.get("Activity", [])) > 0
            has_periods = len(entities.get("Period", [])) > 0
            has_employees = len(entities.get("Employment", [])) > 0
            
            if has_activities or has_periods or has_employees:
                res.append({"id": company_id, "name": info["name"]})
        
        res.sort(key=lambda x: x["name"])
        return res

    def get_activities(self, company_id: str) -> List[Dict]:
        self.refresh_if_needed()
        # company_id is now the company NAME (e.g., "OVERCLEAN")
        # Check direct match first
        if company_id in self._entities:
            return self._entities[company_id].get("Activity", [])
        
        # Fallback: search by alias (in case an ID/code was passed)
        for company_name, info in self._mappings.items():
            if company_id in info.get("aliases", []) or company_id == company_name:
                return self._entities.get(company_name, {}).get("Activity", [])
        
        return []

    def get_employment(self, company_id: str) -> List[Dict]:
        self.refresh_if_needed()
        # company_id is now the company NAME (e.g., "OVERCLEAN")
        # Check direct match first
        if company_id in self._entities:
            return self._entities[company_id].get("Employment", [])
        
        # Fallback: search by alias (in case an ID/code was passed)
        for company_name, info in self._mappings.items():
            if company_id in info.get("aliases", []) or company_id == company_name:
                return self._entities.get(company_name, {}).get("Employment", [])
        
        return []

    def get_periods(self, company_id: str) -> List[Dict]:
        self.refresh_if_needed()
        # company_id is the namespace (e.g., "OVERCLEAN")
        if company_id in self._entities:
            return self._entities[company_id].get("Period", [])
        
        # Fallback: search by alias
        for company_name, info in self._mappings.items():
            if company_id in info.get("aliases", []) or company_id == company_name:
                return self._entities.get(company_name, {}).get("Period", [])
        
        return []

    def get_diagnostics(self, company_id: str) -> Dict:
        self.refresh_if_needed()
        if company_id in self._diagnostics:
            return self._diagnostics[company_id]
        
        # Try finding by name/alias
        for cid, info in self._mappings.items():
            if company_id in info.get("aliases", []) or company_id == info["name"]:
                return self._diagnostics.get(cid, {})
        
        return {}

mapper = EnvironmentMapper()
