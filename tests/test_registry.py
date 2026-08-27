import unittest
from common.firestore_client import FirestoreClient
from registry.registry import AgentRegistry, AgentNotFoundError, AgentSuspendedError

class TestAgentRegistry(unittest.TestCase):
    def setUp(self):
        self.db = FirestoreClient(use_mock=True)
        self.registry = AgentRegistry(db_client=self.db)

    def test_register_and_get_agent(self):
        agent = self.registry.register_agent(
            agent_id="vendor-alpha",
            agent_type="vendor",
            capabilities=["widget_supplier", "fast_shipping"]
        )
        self.assertEqual(agent.agent_id, "vendor-alpha")
        
        fetched = self.registry.get_agent("vendor-alpha")
        self.assertEqual(fetched.agent_id, "vendor-alpha")
        self.assertEqual(fetched.capabilities, ["widget_supplier", "fast_shipping"])

    def test_verify_unregistered_agent_raises_error(self):
        with self.assertRaises(AgentNotFoundError):
            self.registry.verify_agent_authorized("unknown-agent")

    def test_verify_agent_type(self):
        self.registry.register_agent("buyer-1", "buyer", ["procurement"])
        self.assertTrue(self.registry.verify_agent_authorized("buyer-1", expected_type="buyer"))
        with self.assertRaises(ValueError):
            self.registry.verify_agent_authorized("buyer-1", expected_type="vendor")

if __name__ == "__main__":
    unittest.main()
