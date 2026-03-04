import requests
import os
from typing import List, Optional, Dict
from config import settings

class ApiClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ApiClient, cls).__new__(cls)
            cls._instance.session = requests.Session()
            cls._instance.base_url = "https://europe-west3-hrtimeplace.cloudfunctions.net"
            # In production, this should be configurable
            # cls._instance.base_url = os.getenv("EXTERNAL_API_BASE_URL", cls._instance.base_url)
        return cls._instance

    def fetch_external(self, endpoint: str, namespace: str, params: dict = None) -> List[dict]:
        """
        Helper to fetch from external Cloud Functions using a persistent session.
        Implements Point 3: Connection Reuse / Keep-Alive.
        """
        url = f"{self.base_url}/{endpoint}"
        if not params: params = {}
        params["namespace"] = namespace
        
        try:
            # Using self.session instead of one-off requests calls
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"ERROR fetching {endpoint}: {e}")
            return []

# Singleton instance
api_client = ApiClient()
