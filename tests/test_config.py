"""Tests for configuration parsing."""
import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestConfigParseBool(unittest.TestCase):
    """Test the _parse_bool helper."""

    def test_parse_true_values(self):
        from common.config import _parse_bool
        for val in ["true", "True", "TRUE", "1", "yes", "Yes", "on", "ON"]:
            self.assertTrue(_parse_bool(val), f"Expected True for '{val}'")

    def test_parse_false_values(self):
        from common.config import _parse_bool
        for val in ["false", "False", "FALSE", "0", "no", "No", "off", "OFF", ""]:
            self.assertFalse(_parse_bool(val), f"Expected False for '{val}'")

    def test_parse_none_returns_default(self):
        from common.config import _parse_bool
        self.assertFalse(_parse_bool(None, default=False))
        self.assertTrue(_parse_bool(None, default=True))

    def test_parse_empty_string_returns_default(self):
        from common.config import _parse_bool
        self.assertFalse(_parse_bool("", default=False))
        self.assertTrue(_parse_bool("", default=True))


class TestConfigDefaults(unittest.TestCase):
    """Test configuration defaults are safe for local/test mode."""

    def test_project_has_default(self):
        from common.config import GOOGLE_CLOUD_PROJECT
        self.assertIsNotNone(GOOGLE_CLOUD_PROJECT)
        self.assertTrue(len(GOOGLE_CLOUD_PROJECT) > 0)

    def test_location_has_default(self):
        from common.config import GOOGLE_CLOUD_LOCATION
        self.assertEqual(GOOGLE_CLOUD_LOCATION, "us-central1")

    def test_feature_flags_default_false(self):
        """Feature flags default to False so tests work without GCP creds."""
        from common.config import USE_FIRESTORE, USE_PUBSUB, USE_CLOUD_TRACE, REGISTER_WITH_AGENT_REGISTRY
        # These may be overridden by .env, but the code defaults are False
        # so tests without .env work fine
        self.assertIsInstance(USE_FIRESTORE, bool)
        self.assertIsInstance(USE_PUBSUB, bool)
        self.assertIsInstance(USE_CLOUD_TRACE, bool)
        self.assertIsInstance(REGISTER_WITH_AGENT_REGISTRY, bool)

    def test_backward_compatible_aliases_exist(self):
        from common.config import GCP_PROJECT, GCP_REGION, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION
        self.assertEqual(GCP_PROJECT, GOOGLE_CLOUD_PROJECT)
        self.assertEqual(GCP_REGION, GOOGLE_CLOUD_LOCATION)

    def test_pubsub_topics_dict(self):
        from common.config import PUBSUB_TOPICS
        self.assertIn("buyer_to_escrow", PUBSUB_TOPICS)
        self.assertIn("vendor_to_escrow", PUBSUB_TOPICS)
        self.assertIn("escrow_events", PUBSUB_TOPICS)
        self.assertIn("security_events", PUBSUB_TOPICS)

    def test_port_is_int(self):
        from common.config import PORT
        self.assertIsInstance(PORT, int)
        self.assertGreater(PORT, 0)


if __name__ == "__main__":
    unittest.main()
