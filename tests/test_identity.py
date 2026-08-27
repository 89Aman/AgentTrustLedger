import unittest
from common.identity import sign_payload, verify_signature

class TestIdentity(unittest.TestCase):
    def test_sign_and_verify_payload(self):
        payload = {
            "transaction_id": "txn-001",
            "buyer_id": "buyer-alpha",
            "amount": 500.0,
            "conditions": ["item_delivered", "quality_verified"]
        }
        secret = "test-secret-key-123"

        sig = sign_payload(payload, secret)
        self.assertIsNotNone(sig)
        self.assertEqual(len(sig), 64)  # SHA-256 hex string

        # Verification should succeed
        self.assertTrue(verify_signature(payload, sig, secret))

    def test_verify_fails_on_tampered_payload(self):
        payload = {"transaction_id": "txn-001", "amount": 500.0}
        secret = "test-secret-key-123"
        sig = sign_payload(payload, secret)

        # Tamper payload
        tampered_payload = {"transaction_id": "txn-001", "amount": 999.0}
        self.assertFalse(verify_signature(tampered_payload, sig, secret))

    def test_verify_fails_on_wrong_secret(self):
        payload = {"transaction_id": "txn-001", "amount": 500.0}
        secret = "correct-secret"
        sig = sign_payload(payload, secret)

        self.assertFalse(verify_signature(payload, sig, "wrong-secret"))

if __name__ == "__main__":
    unittest.main()
