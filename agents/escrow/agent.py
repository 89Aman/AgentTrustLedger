import time
from typing import Optional
from common.config import GEMINI_MODEL
from common.schemas import TransactionRequest, DeliveryClaim, EscrowDecision
from common.firestore_client import FirestoreClient
from common.tracing import traced_step
from registry.registry import AgentRegistry
from agents.escrow.security_guard import inspect_claim_for_security_violations
from agents.escrow.reputation import ReputationManager

class EscrowMediatorAgent:
    """
    Escrow Mediator Agent (Fortified Enterprise Fleet core).
    Holds funds in escrow, verifies agent identities & registration, evaluates delivery evidence,
    enforces Security & Trust Guard, and updates public reputation records.
    """
    def __init__(
        self,
        db_client: Optional[FirestoreClient] = None,
        registry: Optional[AgentRegistry] = None,
        reputation_mgr: Optional[ReputationManager] = None
    ):
        self.db = db_client or FirestoreClient()
        self.registry = registry or AgentRegistry(db_client=self.db)
        self.reputation_mgr = reputation_mgr or ReputationManager(db_client=self.db)
        self.name = "escrow_mediator_agent"
        self.model = GEMINI_MODEL

    @traced_step("escrow.initiate")
    def initiate_escrow(self, request: TransactionRequest) -> EscrowDecision:
        # 1. Check Agent Registry for Buyer & Vendor
        self.registry.verify_agent_authorized(request.buyer_id, expected_type="buyer")
        self.registry.verify_agent_authorized(request.vendor_id, expected_type="vendor")

        # 2. Store Escrow State in Firestore (Memory Bank)
        txn_data = {
            "transaction_id": request.transaction_id,
            "buyer_id": request.buyer_id,
            "vendor_id": request.vendor_id,
            "amount": request.amount,
            "delivery_conditions": request.delivery_conditions,
            "status": "escrowed",
            "timeline": ["ESCROWED"],
            "created_at": time.time(),
            "updated_at": time.time()
        }
        self.db.save_transaction(request.transaction_id, txn_data)
        self.db.add_audit_log(request.transaction_id, {
            "step": "escrow_hold",
            "actor": self.name,
            "tag": "ESCROW",
            "details": f"[ESCROW] Funds held — {request.transaction_id} — ${request.amount:,.2f} simulated ({request.buyer_id} → {request.vendor_id})"
        })

        print(f"[EscrowMediator] Transaction '{request.transaction_id}' ESCROWED (${request.amount:,.2f} simulated)")
        return EscrowDecision(
            transaction_id=request.transaction_id,
            action="hold",
            reason=f"Escrow Amount: ${request.amount:,.2f} simulated locked in escrow pending delivery verification."
        )

    @traced_step("escrow.process_claim")
    def process_claim(self, claim: DeliveryClaim) -> EscrowDecision:
        # 1. Run Security and Trust Guard checks (Signature + Prompt Injection)
        is_valid, violation_reason, violation_type = inspect_claim_for_security_violations(claim)
        
        if not is_valid:
            # Log security incident into Credit Bureau & audit ledger
            self.reputation_mgr.record_security_violation(claim.vendor_id, claim.transaction_id, violation_reason)
            self.db.add_audit_log(claim.transaction_id, {
                "step": "claim_rejected_security_guard",
                "actor": self.name,
                "tag": "SECURITY GUARD",
                "violation_type": violation_type,
                "details": f"[SECURITY GUARD] Claim blocked — {violation_reason}"
            })
            # Keep transaction in escrowed status so legitimate delivery can still proceed
            txn = self.db.get_transaction(claim.transaction_id) or {}
            timeline = txn.get("timeline", ["ESCROWED"])
            if "SPOOFED CLAIM BLOCKED" not in timeline:
                timeline.append("SPOOFED CLAIM BLOCKED")
            self.db.save_transaction(claim.transaction_id, {
                "timeline": timeline,
                "last_security_incident": violation_reason,
                "updated_at": time.time()
            })
            print(f"[EscrowMediator] SECURITY GUARD INTERVENTION on txn '{claim.transaction_id}': {violation_reason}")
            return EscrowDecision(
                transaction_id=claim.transaction_id,
                action="reject",
                reason=violation_reason,
                security_flag_raised=True
            )

        # 2. Check transaction status
        txn = self.db.get_transaction(claim.transaction_id)
        if not txn:
            reason = f"Transaction '{claim.transaction_id}' not found."
            return EscrowDecision(transaction_id=claim.transaction_id, action="reject", reason=reason)

        if txn.get("status") not in ["escrowed", "disputed"]:
            reason = f"Transaction '{claim.transaction_id}' is already '{txn.get('status')}', cannot process claim."
            return EscrowDecision(transaction_id=claim.transaction_id, action="reject", reason=reason)

        # 3. Verify vendor identity matches contract
        if claim.vendor_id != txn.get("vendor_id"):
            reason = f"SECURITY GUARD: Vendor identity '{claim.vendor_id}' does not match contract vendor '{txn.get('vendor_id')}'."
            self.reputation_mgr.record_security_violation(claim.vendor_id, claim.transaction_id, reason)
            return EscrowDecision(transaction_id=claim.transaction_id, action="reject", reason=reason, security_flag_raised=True)

        # 4. Verify delivery evidence conditions
        evidence = claim.evidence
        conditions = txn.get("delivery_conditions", [])
        verified = True
        missing_conditions = []

        for condition in conditions:
            if condition not in evidence or not evidence[condition]:
                verified = False
                missing_conditions.append(condition)

        timeline = txn.get("timeline", ["ESCROWED"])

        if verified:
            if "LEGITIMATE CLAIM VERIFIED" not in timeline:
                timeline.append("LEGITIMATE CLAIM VERIFIED")
            timeline.append("RELEASED")
            
            # Release funds & update reputation
            self.db.save_transaction(claim.transaction_id, {
                "status": "released",
                "timeline": timeline,
                "updated_at": time.time()
            })
            self.db.add_audit_log(claim.transaction_id, {
                "step": "funds_released",
                "actor": self.name,
                "tag": "ESCROW",
                "details": f"[ESCROW] Valid delivery verified — ${txn['amount']:,.2f} simulated released to vendor '{claim.vendor_id}'."
            })
            rep = self.reputation_mgr.record_successful_delivery(
                agent_id=claim.vendor_id,
                transaction_id=claim.transaction_id,
                details=f"Successful delivery for txn {claim.transaction_id}"
            )
            self.db.add_audit_log(claim.transaction_id, {
                "step": "reputation_updated",
                "actor": self.name,
                "tag": "REPUTATION",
                "details": f"[REPUTATION] {claim.vendor_id} quality score updated to {int(rep.quality_score * 100)}% (completed {rep.total_transactions} txns)"
            })
            print(f"[EscrowMediator] Transaction '{claim.transaction_id}' RELEASED to vendor '{claim.vendor_id}'.")
            return EscrowDecision(
                transaction_id=claim.transaction_id,
                action="release",
                reason=f"Delivery evidence verified. Escrow funds (${txn['amount']:,.2f} simulated) released to vendor '{claim.vendor_id}'."
            )
        else:
            timeline.append("REFUNDED")
            # Refund buyer & log disputed delivery
            self.db.save_transaction(claim.transaction_id, {
                "status": "refunded",
                "timeline": timeline,
                "updated_at": time.time()
            })
            self.db.add_audit_log(claim.transaction_id, {
                "step": "funds_refunded",
                "actor": self.name,
                "tag": "ESCROW",
                "details": f"[ESCROW] Conditions missing ({missing_conditions}) — Funds (${txn['amount']:,.2f} simulated) refunded to buyer '{txn['buyer_id']}'."
            })
            self.reputation_mgr.record_disputed_delivery(
                agent_id=claim.vendor_id,
                transaction_id=claim.transaction_id,
                details=f"Failed delivery verification on txn {claim.transaction_id}"
            )
            print(f"[EscrowMediator] Transaction '{claim.transaction_id}' REFUNDED to buyer.")
            return EscrowDecision(
                transaction_id=claim.transaction_id,
                action="refund",
                reason=f"Delivery conditions not met: missing {missing_conditions}. Funds refunded."
            )
