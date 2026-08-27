import os
from dotenv import load_dotenv

load_dotenv()

raw_project = os.getenv("GCP_PROJECT", "massive-house-506806-t6")
# Handle potential PowerShell space-concatenated string
if " " in raw_project:
    for part in raw_project.split():
        if "=" in part:
            k, v = part.split("=", 1)
            os.environ[k] = v.strip()
    GCP_PROJECT = os.environ.get("GCP_PROJECT", raw_project.split()[0])
else:
    GCP_PROJECT = raw_project

GCP_REGION = os.getenv("GCP_REGION", "us-central1").split()[0]
HMAC_SECRET_KEY = os.getenv("HMAC_SECRET_KEY", "agent-trust-ledger-secret-key-2026").split()[0]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").split()[0]

# Vertex AI via ADK: set env vars ADK reads automatically
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = os.getenv("USE_VERTEX_AI", "true").split()[0]
os.environ["GOOGLE_CLOUD_PROJECT"] = GCP_PROJECT
os.environ["GOOGLE_CLOUD_LOCATION"] = GCP_REGION

# Pub/Sub topic and subscription names
PUBSUB_TOPICS = {
    "buyer_to_escrow": os.getenv("PUBSUB_TOPIC_BUYER_TO_ESCROW", "buyer-to-escrow"),
    "vendor_to_escrow": os.getenv("PUBSUB_TOPIC_VENDOR_TO_ESCROW", "vendor-to-escrow"),
    "escrow_to_buyer": os.getenv("PUBSUB_TOPIC_ESCROW_TO_BUYER", "escrow-to-buyer"),
    "escrow_to_vendor": os.getenv("PUBSUB_TOPIC_ESCROW_TO_VENDOR", "escrow-to-vendor"),
}

# Backwards-compatible flat aliases (used by buyer/vendor agents)
PUBSUB_TOPIC_BUYER_TO_ESCROW = PUBSUB_TOPICS["buyer_to_escrow"]
PUBSUB_TOPIC_VENDOR_TO_ESCROW = PUBSUB_TOPICS["vendor_to_escrow"]
PUBSUB_TOPIC_ESCROW_TO_BUYER = PUBSUB_TOPICS["escrow_to_buyer"]
PUBSUB_TOPIC_ESCROW_TO_VENDOR = PUBSUB_TOPICS["escrow_to_vendor"]
