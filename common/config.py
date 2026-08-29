import os
from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str, default: bool = False) -> bool:
    """Robust string-to-boolean parsing."""
    if not value:
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT", ""))
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", os.getenv("GCP_REGION", ""))
AGENT_REGISTRY_LOCATION = os.getenv("AGENT_REGISTRY_LOCATION", "")

GCP_PROJECT = GOOGLE_CLOUD_PROJECT
GCP_REGION = GOOGLE_CLOUD_LOCATION

CLOUD_RUN_SERVICE_URL = os.getenv("CLOUD_RUN_SERVICE_URL", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "")
HMAC_SECRET_KEY = os.getenv("HMAC_SECRET_KEY", "")
PORT = int(os.getenv("PORT", "8080"))
FLASK_ENV = os.getenv("FLASK_ENV", "development")
DEMO_MODE = _parse_bool(os.getenv("DEMO_MODE", "true"), default=True)


USE_FIRESTORE = _parse_bool(os.getenv("USE_FIRESTORE", "false"), default=False)
USE_PUBSUB = _parse_bool(os.getenv("USE_PUBSUB", "false"), default=False)
USE_CLOUD_TRACE = _parse_bool(os.getenv("USE_CLOUD_TRACE", "false"), default=False)
REGISTER_WITH_AGENT_REGISTRY = _parse_bool(os.getenv("REGISTER_WITH_AGENT_REGISTRY", "false"), default=False)


if "GOOGLE_GENAI_USE_VERTEXAI" not in os.environ:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = os.getenv("USE_VERTEX_AI", "true")
if "GOOGLE_CLOUD_PROJECT" not in os.environ and GOOGLE_CLOUD_PROJECT:
    os.environ["GOOGLE_CLOUD_PROJECT"] = GOOGLE_CLOUD_PROJECT
if "GOOGLE_CLOUD_LOCATION" not in os.environ and GOOGLE_CLOUD_LOCATION:
    os.environ["GOOGLE_CLOUD_LOCATION"] = GOOGLE_CLOUD_LOCATION


PUBSUB_TOPICS = {
    "buyer_to_escrow": os.getenv("PUBSUB_TOPIC_BUYER_TO_ESCROW", "buyer-to-escrow"),
    "vendor_to_escrow": os.getenv("PUBSUB_TOPIC_VENDOR_TO_ESCROW", "vendor-to-escrow"),
    "escrow_events": os.getenv("PUBSUB_TOPIC_ESCROW_EVENTS", "escrow-events"),
    "security_events": os.getenv("PUBSUB_TOPIC_SECURITY_EVENTS", "security-events"),
}

PUBSUB_TOPIC_BUYER_TO_ESCROW = PUBSUB_TOPICS["buyer_to_escrow"]
PUBSUB_TOPIC_VENDOR_TO_ESCROW = PUBSUB_TOPICS["vendor_to_escrow"]
PUBSUB_TOPIC_ESCROW_EVENTS = PUBSUB_TOPICS["escrow_events"]
PUBSUB_TOPIC_SECURITY_EVENTS = PUBSUB_TOPICS["security_events"]


PUBSUB_TOPIC_ESCROW_TO_BUYER = os.getenv("PUBSUB_TOPIC_ESCROW_TO_BUYER", "escrow-to-buyer")
PUBSUB_TOPIC_ESCROW_TO_VENDOR = os.getenv("PUBSUB_TOPIC_ESCROW_TO_VENDOR", "escrow-to-vendor")
