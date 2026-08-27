import time
import uuid
from typing import Optional
from common.config import GEMINI_MODEL
from common.schemas import TransactionRequest, DeliveryClaim, EscrowDecision, AutonomySettings, SecurityEvent
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
        # 1. Check Agent Registry for Buyer & Vendor Authorization & Status
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
            "verification_confidence": 0.96,
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
            
            # Save dedicated Security Incident for Security Center
            sec_event = SecurityEvent(
                event_id=f"sec-{uuid.uuid4().hex[:8]}",
                transaction_id=claim.transaction_id,
                agent_id=claim.vendor_id,
                severity="high" if violation_type == "signature_spoof" else "critical",
                event_type=violation_type or "security_violation",
                reason=violation_reason,
                status="open",
                created_at=time.time()
            )
            self.db.save_security_event(sec_event)

            self.db.add_audit_log(claim.transaction_id, {
                "step": "claim_rejected_security_guard",
                "actor": self.name,
                "tag": "SECURITY GUARD",
                "violation_type": violation_type,
                "details": f"[SECURITY GUARD] Claim blocked — {violation_reason}"
            })
            
            txn = self.db.get_transaction(claim.transaction_id) or {}
            timeline = txn.get("timeline", ["ESCROWED"])
            if "SPOOFED CLAIM BLOCKED" not in timeline:
                timeline.append("SPOOFED CLAIM BLOCKED")
            self.db.save_transaction(claim.transaction_id, {
                "timeline": timeline,
                "last_security_incident": violation_reason,
                "has_security_event": True,
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

        if txn.get("status") not in ["escrowed", "disputed", "awaiting_human_approval"]:
            reason = f"Transaction '{claim.transaction_id}' is already '{txn.get('status')}', cannot process claim."
            return EscrowDecision(transaction_id=claim.transaction_id, action="reject", reason=reason)

        # 3. Verify vendor authorization and identity matches contract
        try:
            self.registry.verify_agent_authorized(claim.vendor_id, expected_type="vendor")
        except Exception as e:
            reason = f"SECURITY GUARD: Vendor '{claim.vendor_id}' is not authorized ({e})."
            return EscrowDecision(transaction_id=claim.transaction_id, action="reject", reason=reason, security_flag_raised=True)

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
            
            # Check Autonomy Policy settings
            autonomy = self.db.get_autonomy_settings()
            require_human = False
            hold_reason = ""

            if autonomy.mode == "manual":
                require_human = True
                hold_reason = "Manual Approval policy requires human authorization to release escrow."
            elif autonomy.mode == "guarded_auto":
                if txn.get("has_security_event") and autonomy.require_approval_for_security_events:
                    require_human = True
                    hold_reason = "Guarded Auto: Transaction has previous security events; human approval required."
                elif txn.get("amount", 0) > autonomy.approval_amount_threshold:
                    require_human = True
                    hold_reason = f"Guarded Auto: Amount (${txn.get('amount'):,.2f}) exceeds threshold (${autonomy.approval_amount_threshold:,.2f}); human approval required."

            if require_human:
                timeline.append("AWAITING HUMAN APPROVAL")
                self.db.save_transaction(claim.transaction_id, {
                    "status": "awaiting_human_approval",
                    "timeline": timeline,
                    "hold_reason": hold_reason,
                    "updated_at": time.time()
                })
                self.db.add_audit_log(claim.transaction_id, {
                    "step": "awaiting_human_approval",
                    "actor": self.name,
                    "tag": "POLICY",
                    "details": f"[POLICY] Delivery verified — {hold_reason}"
                })
                return EscrowDecision(
                    transaction_id=claim.transaction_id,
                    action="awaiting_human_approval",
                    reason=hold_reason
                )

            # Otherwise, auto release funds
            return self._execute_release(claim.transaction_id, txn, claim.vendor_id, timeline)
        else:
            timeline.append("REFUNDED")
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

    def _execute_release(self, transaction_id: str, txn: dict, vendor_id: str, timeline: list, actor: str = "escrow_mediator_agent") -> EscrowDecision:
        if "RELEASED" not in timeline:
            timeline.append("RELEASED")
        
        self.db.save_transaction(transaction_id, {
            "status": "released",
            "timeline": timeline,
            "updated_at": time.time()
        })
        self.db.add_audit_log(transaction_id, {
            "step": "funds_released",
            "actor": actor,
            "tag": "ESCROW",
            "details": f"[ESCROW] Valid delivery verified — ${txn['amount']:,.2f} simulated released to vendor '{vendor_id}'."
        })
        rep = self.reputation_mgr.record_successful_delivery(
            agent_id=vendor_id,
            transaction_id=transaction_id,
            details=f"Successful delivery for txn {transaction_id}"
        )
        self.db.add_audit_log(transaction_id, {
            "step": "reputation_updated",
            "actor": actor,
            "tag": "REPUTATION",
            "details": f"[REPUTATION] {vendor_id} quality score updated to {int(rep.quality_score * 100)}% (completed {rep.total_transactions} txns)"
        })
        print(f"[EscrowMediator] Transaction '{transaction_id}' RELEASED to vendor '{vendor_id}'.")
        return EscrowDecision(
            transaction_id=transaction_id,
            action="release",
            reason=f"Delivery evidence verified. Escrow funds (${txn['amount']:,.2f} simulated) released to vendor '{vendor_id}'."
        )

    # --- Operator Human-in-the-Loop Actions ---
    @traced_step("operator.approve_release")
    def operator_approve_release(self, transaction_id: str, operator_id: str = "human_operator") -> EscrowDecision:
        txn = self.db.get_transaction(transaction_id)
        if not txn:
            raise ValueError(f"Transaction '{transaction_id}' not found.")
        timeline = txn.get("timeline", ["ESCROWED"])
        timeline.append("OPERATOR APPROVED")
        
        self.db.add_audit_log(transaction_id, {
            "step": "operator_approval",
            "actor": operator_id,
            "tag": "OPERATOR",
            "details": f"[OPERATOR] Human operator '{operator_id}' approved release of ${txn['amount']:,.2f} simulated."
        })
        return self._execute_release(transaction_id, txn, txn["vendor_id"], timeline, actor=operator_id)

    @traced_step("operator.refund_buyer")
    def operator_refund_buyer(self, transaction_id: str, operator_id: str = "human_operator", reason: str = "Operator manual refund") -> EscrowDecision:
        txn = self.db.get_transaction(transaction_id)
        if not txn:
            raise ValueError(f"Transaction '{transaction_id}' not found.")
        timeline = txn.get("timeline", ["ESCROWED"])
        timeline.append("OPERATOR REFUNDED")
        
        self.db.save_transaction(transaction_id, {
            "status": "refunded",
            "timeline": timeline,
            "updated_at": time.time()
        })
        self.db.add_audit_log(transaction_id, {
            "step": "operator_refund",
            "actor": operator_id,
            "tag": "OPERATOR",
            "details": f"[OPERATOR] Human operator refunded ${txn['amount']:,.2f} simulated to buyer '{txn['buyer_id']}'. Reason: {reason}"
        })
        return EscrowDecision(
            transaction_id=transaction_id,
            action="refund",
            reason=f"Operator manual refund issued: {reason}"
        )

    @traced_step("operator.pause_transaction")
    def operator_pause_transaction(self, transaction_id: str, operator_id: str = "human_operator") -> EscrowDecision:
        txn = self.db.get_transaction(transaction_id)
        if not txn:
            raise ValueError(f"Transaction '{transaction_id}' not found.")
        timeline = txn.get("timeline", ["ESCROWED"])
        timeline.append("PAUSED BY OPERATOR")
        
        self.db.save_transaction(transaction_id, {
            "status": "paused",
            "timeline": timeline,
            "updated_at": time.time()
        })
        self.db.add_audit_log(transaction_id, {
            "step": "operator_pause",
            "actor": operator_id,
            "tag": "OPERATOR",
            "details": f"[OPERATOR] Human operator paused transaction '{transaction_id}'."
        })
        return EscrowDecision(
            transaction_id=transaction_id,
            action="paused",
            reason=f"Transaction '{transaction_id}' paused by operator."
        )

    @traced_step("operator.resume_transaction")
    def operator_resume_transaction(self, transaction_id: str, operator_id: str = "human_operator") -> EscrowDecision:
        txn = self.db.get_transaction(transaction_id)
        if not txn:
            raise ValueError(f"Transaction '{transaction_id}' not found.")
        timeline = txn.get("timeline", ["ESCROWED"])
        timeline.append("RESUMED BY OPERATOR")
        
        self.db.save_transaction(transaction_id, {
            "status": "escrowed",
            "timeline": timeline,
            "updated_at": time.time()
        })
        self.db.add_audit_log(transaction_id, {
            "step": "operator_resume",
            "actor": operator_id,
            "tag": "OPERATOR",
            "details": f"[OPERATOR] Human operator resumed transaction '{transaction_id}'."
        })
        return EscrowDecision(
            transaction_id=transaction_id,
            action="hold",
            reason=f"Transaction '{transaction_id}' resumed by operator."
        )
