import unittest
from common.schemas import TransactionRequest, DeliveryClaim, AutonomySettings, AgentPolicy
from common.firestore_client import FirestoreClient
from registry.registry import AgentRegistry, AgentSuspendedError, AgentPausedError
from agents.escrow.agent import EscrowMediatorAgent
from common.identity import sign_payload
from common.config import HMAC_SECRET_KEY

class TestGovernanceAndAutonomy(unittest.TestCase):
    def setUp(self):
        self.db = FirestoreClient(use_mock=True)
        self.registry = AgentRegistry(db_client=self.db)
        self.escrow = EscrowMediatorAgent(db_client=self.db, registry=self.registry)

        self.registry.register_agent("buyer-gov", "buyer", ["procurement"])
        self.registry.register_agent("vendor-gov", "vendor", ["supply"])
        self.registry.register_agent("vendor-rogue", "vendor", ["untrusted"])

    def test_agent_suspension_blocks_transaction(self):
        # Suspend agent
        self.registry.set_agent_status("vendor-rogue", "suspended")
        
        req = TransactionRequest(
            transaction_id="txn-suspend-01",
            buyer_id="buyer-gov",
            vendor_id="vendor-rogue",
            amount=1000.0,
            delivery_conditions=["received"],
            signature="mock-sig"
        )
        with self.assertRaises(AgentSuspendedError):
            self.escrow.initiate_escrow(req)

    def test_agent_paused_blocks_transaction(self):
        self.registry.set_agent_status("vendor-gov", "paused")
        req = TransactionRequest(
            transaction_id="txn-paused-01",
            buyer_id="buyer-gov",
            vendor_id="vendor-gov",
            amount=500.0,
            delivery_conditions=["received"],
            signature="mock-sig"
        )
        with self.assertRaises(AgentPausedError):
            self.escrow.initiate_escrow(req)

    def test_autonomy_manual_mode_requires_approval(self):
        self.db.save_autonomy_settings(AutonomySettings(mode="manual"))
        
        txn_id = "txn-manual-01"
        req = TransactionRequest(
            transaction_id=txn_id,
            buyer_id="buyer-gov",
            vendor_id="vendor-gov",
            amount=500.0,
            delivery_conditions=["received"],
            signature="mock-sig"
        )
        self.escrow.initiate_escrow(req)

        evidence = {"received": True}
        sig = sign_payload({"transaction_id": txn_id, "vendor_id": "vendor-gov", "evidence": evidence}, HMAC_SECRET_KEY)
        claim = DeliveryClaim(transaction_id=txn_id, vendor_id="vendor-gov", evidence=evidence, signature=sig)

        decision = self.escrow.process_claim(claim)
        self.assertEqual(decision.action, "awaiting_human_approval")
        
        # Human operator approves
        approve_dec = self.escrow.operator_approve_release(txn_id, operator_id="admin_user")
        self.assertEqual(approve_dec.action, "release")
        
        txn = self.db.get_transaction(txn_id)
        self.assertEqual(txn["status"], "released")

    def test_operator_refund_and_pause_actions(self):
        txn_id = "txn-operator-02"
        req = TransactionRequest(
            transaction_id=txn_id,
            buyer_id="buyer-gov",
            vendor_id="vendor-gov",
            amount=1200.0,
            delivery_conditions=["received"],
            signature="mock-sig"
        )
        self.escrow.initiate_escrow(req)

        # Operator pauses
        pause_dec = self.escrow.operator_pause_transaction(txn_id)
        self.assertEqual(pause_dec.action, "paused")
        self.assertEqual(self.db.get_transaction(txn_id)["status"], "paused")

        # Operator resumes
        resume_dec = self.escrow.operator_resume_transaction(txn_id)
        self.assertEqual(resume_dec.action, "hold")
        self.assertEqual(self.db.get_transaction(txn_id)["status"], "escrowed")

        # Operator refunds
        refund_dec = self.escrow.operator_refund_buyer(txn_id, reason="Buyer requested cancellation")
        self.assertEqual(refund_dec.action, "refund")
        self.assertEqual(self.db.get_transaction(txn_id)["status"], "refunded")

if __name__ == "__main__":
    unittest.main()
