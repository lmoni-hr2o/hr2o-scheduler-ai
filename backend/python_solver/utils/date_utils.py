from datetime import datetime
import re

def parse_date(date_str):
    """
    Robustly parses a date string into a datetime object.
    Supports:
    - YYYY-MM-DD (ISO)
    - YYYY-MM-DDTHH:MM:SS
    - DD/MM/YYYY
    - DD-MM-YYYY
    """
    # If it's a list (common in some exports), take first element
    if isinstance(date_str, list) and date_str:
        date_str = date_str[0]
        
    if not date_str: return None
    
    # Check if it's already a datetime or has date properties
    if hasattr(date_str, 'year') and hasattr(date_str, 'month'):
        return date_str
    
    if isinstance(date_str, datetime):
        return date_str
    
    date_str = str(date_str).strip()
    
    # Try ISO formats first
    try:
        # Handles 2024-01-19 and 2024-01-19T...
        return datetime.fromisoformat(date_str.replace('Z', ''))
    except ValueError:
        pass
    
    # Try DD/MM/YYYY or DD-MM-YYYY
    match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', date_str)
    if match:
        d, m, y = match.groups()
        try:
            return datetime(int(y), int(m), int(d))
        except ValueError:
            pass
            
    # Try some other variations if needed
    return None

def format_date_iso(dt):
    """Returns YYYY-MM-DD"""
    if not dt: return None
    if isinstance(dt, str):
        parsed = parse_date(dt)
        return parsed.strftime("%Y-%m-%d") if parsed else None
    return dt.strftime("%Y-%m-%d")
