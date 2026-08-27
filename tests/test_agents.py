import unittest
from common.firestore_client import FirestoreClient
from common.pubsub import PubSubManager
from registry.registry import AgentRegistry
from agents.escrow.agent import EscrowMediatorAgent
from agents.buyer.agent import BuyerAgent
from agents.vendor.agent import VendorAgent

class TestAgentInteraction(unittest.TestCase):
    def setUp(self):
        self.db = FirestoreClient(use_mock=True)
        self.pubsub = PubSubManager(use_mock=True)
        self.registry = AgentRegistry(db_client=self.db)

        # Register agents
        self.registry.register_agent("buyer-01", "buyer", ["procurement"])
        self.registry.register_agent("vendor-01", "vendor", ["supply"])

        self.buyer = BuyerAgent(agent_id="buyer-01", pubsub_mgr=self.pubsub)
        self.vendor = VendorAgent(agent_id="vendor-01", pubsub_mgr=self.pubsub)
        self.escrow = EscrowMediatorAgent(db_client=self.db, registry=self.registry)

    def test_full_agent_flow(self):
        txn_id = "txn-flow-100"
        
        # 1. Buyer initiates transaction
        req = self.buyer.initiate_transaction(
            transaction_id=txn_id,
            vendor_id="vendor-01",
            amount=750.0,
            delivery_conditions=["item_shipped", "quality_verified"]
        )

        # 2. Escrow processes transaction request
        hold_decision = self.escrow.initiate_escrow(req)
        self.assertEqual(hold_decision.action, "hold")

        # 3. Vendor submits valid claim
        claim = self.vendor.submit_delivery_claim(
            transaction_id=txn_id,
            evidence={"item_shipped": True, "quality_verified": True}
        )

        # 4. Escrow processes claim and releases funds
        release_decision = self.escrow.process_claim(claim)
        self.assertEqual(release_decision.action, "release")

        # 5. Check reputation score updated
        rep = self.escrow.reputation_mgr.get_or_create_reputation("vendor-01")
        self.assertEqual(rep.quality_score, 1.0)
        self.assertEqual(rep.total_transactions, 1)

if __name__ == "__main__":
    unittest.main()
