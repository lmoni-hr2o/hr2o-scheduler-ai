import gzip
import json
import base64
from typing import Any, Union

def compress_payload(data: Union[str, dict]) -> Union[bytes, str]:
    """
    Compresses a string or dict using Gzip if it's large.
    Returns bytes (compressed) or the original string (if small).
    """
    if isinstance(data, (dict, list)):
        data_str = json.dumps(data)
    else:
        data_str = str(data)
        
    encoded = data_str.encode('utf-8')
    
    # Only compress if larger than 50KB to avoid overhead
    if len(encoded) < 50 * 1024:
        return data_str
        
    compressed = gzip.compress(encoded)
    print(f"DEBUG Compression: Reduced {len(encoded)} bytes to {len(compressed)} bytes.")
    return compressed

def decompress_payload(payload: Union[bytes, str]) -> str:
    """
    Decompresses a payload if it's in bytes (compressed).
    Otherwise returns as is.
    """
    if isinstance(payload, bytes):
        try:
            decompressed = gzip.decompress(payload)
            return decompressed.decode('utf-8')
        except Exception as e:
            print(f"ERROR Decompression failed: {e}")
            return str(payload)
            
    return str(payload)
