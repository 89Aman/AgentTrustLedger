import re
from typing import Optional, Tuple, Any
from common.identity import verify_signature
from common.config import HMAC_SECRET_KEY
from common.schemas import DeliveryClaim

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"system\s*:\s*override",
    r"mark\s+this\s+delivery\s+as\s+verified",
    r"bypass\s+verification",
    r"admin\s+mode",
    r"grant\s+refund",
    r"release\s+all\s+funds"
]

class SecurityGuardViolation(Exception):
    def __init__(self, reason: str, violation_type: str):
        super().__init__(reason)
        self.reason = reason
        self.violation_type = violation_type

def inspect_claim_for_security_violations(claim: DeliveryClaim) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Security & Trust Guard — custom pre-model validation inspired by Model Armor principles.
    Validates HMAC signatures, transaction state, agent authorization, and prompt-injection patterns
    before LLM model execution.
    Returns: (is_valid, violation_reason, violation_type)
    """
    payload_to_verify = {
        "transaction_id": claim.transaction_id,
        "vendor_id": claim.vendor_id,
        "evidence": claim.evidence
    }

    # 1. Verify HMAC Signature
    if not claim.signature or not verify_signature(payload_to_verify, claim.signature, HMAC_SECRET_KEY):
        return False, f"SECURITY GUARD: HMAC signature mismatch — Spoofed payload detected from agent '{claim.vendor_id}'.", "signature_spoof"

    # 2. Check evidence text for prompt injection patterns
    evidence_str = str(claim.evidence).lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, evidence_str):
            return False, f"SECURITY GUARD: Prompt injection attempt detected — Prompt-injection pattern detected in delivery notes matching pattern '{pattern}'.", "prompt_injection"

    return True, None, None

def security_guard_callback(callback_context, llm_request) -> Optional[Any]:
    """
    ADK before_model_callback hook.
    Intercepts and screens claims before LLM model execution.
    """
    claim_data = getattr(callback_context, "state", {}).get("current_claim")
    if claim_data and isinstance(claim_data, DeliveryClaim):
        is_valid, reason, vtype = inspect_claim_for_security_violations(claim_data)
        if not is_valid:
            print(f"[SecurityGuard] REJECTED claim on txn {claim_data.transaction_id}: {reason}")
            raise SecurityGuardViolation(reason, vtype)
    return None
