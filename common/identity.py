import hmac
import hashlib
import json
from typing import Any

def canonicalize_payload(payload: dict[str, Any]) -> bytes:
    """Sort keys and serialize payload to deterministic JSON bytes for signing."""
    return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')

def sign_payload(payload: dict[str, Any], secret_key: str) -> str:
    """Generate HMAC-SHA256 signature for a dictionary payload."""
    data = canonicalize_payload(payload)
    key = secret_key.encode('utf-8')
    return hmac.new(key, data, hashlib.sha256).hexdigest()

def verify_signature(payload: dict[str, Any], signature: str, secret_key: str) -> bool:
    """Verify payload HMAC-SHA256 signature against expected value."""
    expected = sign_payload(payload, secret_key)
    return hmac.compare_digest(expected, signature)
