"""Tests for agent card generation and Flask discovery endpoints."""
import unittest
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.agent_cards import (
    build_escrow_card,
    build_buyer_card,
    build_vendor_card,
    get_all_cards,
    get_card_endpoints,
)


class TestAgentCardBuilder(unittest.TestCase):
    """Test pure agent card builder functions."""

    def setUp(self):
        self.base_url = "https://test-service.run.app"

    def test_escrow_card_structure(self):
        card = build_escrow_card(self.base_url)
        self.assertEqual(card["name"], "Agent Trust Ledger — Escrow Mediator")
        self.assertIn("simulated escrow", card["description"].lower())
        self.assertEqual(card["url"], f"{self.base_url}/.well-known/agent-card.json")
        self.assertEqual(len(card["skills"]), 6)
        self.assertEqual(card["version"], "1.0.0")

    def test_buyer_card_structure(self):
        card = build_buyer_card(self.base_url)
        self.assertEqual(card["name"], "Agent Trust Ledger — Buyer Agent")
        self.assertIn("signed transaction", card["description"].lower())
        self.assertEqual(card["url"], f"{self.base_url}/agents/buyer/.well-known/agent-card.json")
        self.assertEqual(len(card["skills"]), 3)

    def test_vendor_card_structure(self):
        card = build_vendor_card(self.base_url)
        self.assertEqual(card["name"], "Agent Trust Ledger — Vendor Agent")
        self.assertIn("delivery claims", card["description"].lower())
        self.assertEqual(card["url"], f"{self.base_url}/agents/vendor/.well-known/agent-card.json")
        self.assertEqual(len(card["skills"]), 3)

    def test_escrow_card_skills(self):
        card = build_escrow_card(self.base_url)
        skill_ids = [s["id"] for s in card["skills"]]
        expected = [
            "create_simulated_escrow",
            "verify_signed_delivery_claim",
            "block_unsafe_claim",
            "release_demo_credits",
            "update_reputation_ledger",
            "retrieve_audit_events",
        ]
        self.assertEqual(skill_ids, expected)

    def test_buyer_card_skills(self):
        card = build_buyer_card(self.base_url)
        skill_ids = [s["id"] for s in card["skills"]]
        expected = [
            "create_signed_transaction_request",
            "select_registered_vendor",
            "initiate_simulated_escrow",
        ]
        self.assertEqual(skill_ids, expected)

    def test_vendor_card_skills(self):
        card = build_vendor_card(self.base_url)
        skill_ids = [s["id"] for s in card["skills"]]
        expected = [
            "receive_work_request",
            "submit_signed_delivery_claim",
            "provide_delivery_evidence",
        ]
        self.assertEqual(skill_ids, expected)

    def test_get_all_cards(self):
        cards = get_all_cards(self.base_url)
        self.assertIn("escrow", cards)
        self.assertIn("buyer", cards)
        self.assertIn("vendor", cards)
        self.assertEqual(len(cards), 3)

    def test_get_card_endpoints(self):
        endpoints = get_card_endpoints()
        self.assertEqual(len(endpoints), 3)
        self.assertIn("/.well-known/agent-card.json", endpoints)
        self.assertIn("/agents/buyer/.well-known/agent-card.json", endpoints)
        self.assertIn("/agents/vendor/.well-known/agent-card.json", endpoints)

    def test_card_url_uses_base_url(self):
        """Cards must use the provided base URL, never hardcode .run.app."""
        custom_url = "http://localhost:8080"
        card = build_escrow_card(custom_url)
        self.assertTrue(card["url"].startswith(custom_url))

    def test_cards_are_json_serializable(self):
        """All cards must serialize to valid JSON."""
        cards = get_all_cards(self.base_url)
        for role, card in cards.items():
            serialized = json.dumps(card)
            parsed = json.loads(serialized)
            self.assertEqual(parsed["name"], card["name"])

    def test_cards_do_not_expose_secrets(self):
        """Agent cards must not contain HMAC secrets or internal credentials."""
        cards = get_all_cards(self.base_url)
        for role, card in cards.items():
            card_str = json.dumps(card).lower()
            self.assertNotIn("hmac_secret", card_str)
            self.assertNotIn("secret_key", card_str)
            self.assertNotIn("agent-trust-ledger-secret", card_str)

    def test_security_guard_description_is_honest(self):
        """Security Guard skill must use the exact truthful label."""
        card = build_escrow_card(self.base_url)
        guard_skill = next(s for s in card["skills"] if s["id"] == "block_unsafe_claim")
        self.assertIn("custom pre-model security validation", guard_skill["description"])
        self.assertIn("Model Armor principles", guard_skill["description"])

    def test_base_url_trailing_slash_stripped(self):
        """Base URL with trailing slash should not produce double slashes."""
        card = build_escrow_card("https://example.com/")
        # The builder receives the URL as-is; the caller strips trailing slash.
        # But the card URL should still be valid.
        self.assertNotIn("//.", card["url"])


class TestAgentCardEndpoints(unittest.TestCase):
    """Test the Flask endpoints serve agent cards correctly."""

    def setUp(self):
        # Import app with test context
        from dashboard.app import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_escrow_card_endpoint_returns_200(self):
        resp = self.client.get("/.well-known/agent-card.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["name"], "Agent Trust Ledger — Escrow Mediator")

    def test_buyer_card_endpoint_returns_200(self):
        resp = self.client.get("/agents/buyer/.well-known/agent-card.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["name"], "Agent Trust Ledger — Buyer Agent")

    def test_vendor_card_endpoint_returns_200(self):
        resp = self.client.get("/agents/vendor/.well-known/agent-card.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["name"], "Agent Trust Ledger — Vendor Agent")

    def test_card_content_type_is_json(self):
        resp = self.client.get("/.well-known/agent-card.json")
        self.assertIn("application/json", resp.content_type)

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("project", data)

    def test_diagnostics_endpoint(self):
        resp = self.client.get("/api/diagnostics")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("services", data)
        self.assertIn("firestore", data["services"])
        self.assertIn("agent_cards", data)


if __name__ == "__main__":
    unittest.main()
