"""
Agent Card builders for A2A-compatible discovery endpoints.

Pure functions — no network calls, no side effects.
Each returns a dict representing a truthful A2A agent card.
"""
from typing import Optional


def _build_card(
    name: str,
    description: str,
    base_url: str,
    card_path: str,
    skills: list[dict],
    version: str = "1.0.0",
) -> dict:
    """Build a single A2A-compatible agent card."""
    base_url = base_url.rstrip("/")
    if not card_path.startswith("/"):
        card_path = "/" + card_path
    return {
        "protocolVersion": "0.3.0",
        "name": name,
        "description": description,
        "url": f"{base_url}{card_path}",
        "version": version,
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": skills,
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "provider": {
            "organization": "Agent Trust Ledger",
            "url": base_url,
        },
        "documentationUrl": f"{base_url}/",
        "tags": ["escrow", "trust", "reputation", "a2a", "fortified-enterprise-fleet"],
    }


def build_escrow_card(base_url: str) -> dict:
    """Build the Escrow Mediator agent card."""
    return _build_card(
        name="Agent Trust Ledger — Escrow Mediator",
        description=(
            "A neutral agent-to-agent transaction mediator that holds simulated escrow "
            "balances, verifies signed delivery claims, blocks unsafe requests before "
            "model processing, releases demo credits after verified delivery, and writes "
            "auditable reputation events."
        ),
        base_url=base_url,
        card_path="/.well-known/agent-card.json",
        skills=[
            {
                "id": "create_simulated_escrow",
                "name": "Create Simulated Escrow",
                "description": "Hold simulated demo credits in escrow pending delivery verification.",
                "tags": ["escrow", "funds", "simulated"]
            },
            {
                "id": "verify_signed_delivery_claim",
                "name": "Verify Signed Delivery Claim",
                "description": "Validate HMAC-signed delivery claims against escrow contract conditions.",
                "tags": ["hmac", "verification", "claim"]
            },
            {
                "id": "block_unsafe_claim",
                "name": "Block Unsafe Claim",
                "description": "Security & Trust Guard — custom pre-model security validation inspired by Model Armor principles.",
                "tags": ["security", "guard", "model-armor"]
            },
            {
                "id": "release_demo_credits",
                "name": "Release Demo Credits",
                "description": "Release simulated escrow balance to vendor after verified delivery.",
                "tags": ["release", "settlement", "demo-credits"]
            },
            {
                "id": "update_reputation_ledger",
                "name": "Update Reputation Ledger",
                "description": "Write auditable reputation events to the agent credit bureau.",
                "tags": ["reputation", "credit-bureau", "ledger"]
            },
            {
                "id": "retrieve_audit_events",
                "name": "Retrieve Audit Events",
                "description": "Query immutable audit trail of all escrow lifecycle events.",
                "tags": ["audit", "opentelemetry", "traces"]
            },
        ],
    )


def build_buyer_card(base_url: str) -> dict:
    """Build the Buyer Agent card."""
    return _build_card(
        name="Agent Trust Ledger — Buyer Agent",
        description=(
            "An enterprise buyer agent that creates signed transaction requests, "
            "selects registered vendors, and initiates simulated escrow."
        ),
        base_url=base_url,
        card_path="/agents/buyer/.well-known/agent-card.json",
        skills=[
            {
                "id": "create_signed_transaction_request",
                "name": "Create Signed Transaction Request",
                "description": "Build and HMAC-sign a transaction request with delivery conditions.",
                "tags": ["buyer", "procurement", "signed-request"]
            },
            {
                "id": "select_registered_vendor",
                "name": "Select Registered Vendor",
                "description": "Choose a vendor based on public reputation scores from the credit bureau.",
                "tags": ["vendor-selection", "reputation", "discovery"]
            },
            {
                "id": "initiate_simulated_escrow",
                "name": "Initiate Simulated Escrow",
                "description": "Submit a signed transaction request to the Escrow Mediator for demo credit hold.",
                "tags": ["escrow-initiation", "demo-credits", "contract"]
            },
        ],
    )


def build_vendor_card(base_url: str) -> dict:
    """Build the Vendor Agent card."""
    return _build_card(
        name="Agent Trust Ledger — Vendor Agent",
        description=(
            "A vendor agent that receives work requests and submits signed delivery "
            "claims with evidence for simulated escrow settlement."
        ),
        base_url=base_url,
        card_path="/agents/vendor/.well-known/agent-card.json",
        skills=[
            {
                "id": "receive_work_request",
                "name": "Receive Work Request",
                "description": "Accept a procurement work request from the escrow contract.",
                "tags": ["work-request", "procurement", "fulfillment"]
            },
            {
                "id": "submit_signed_delivery_claim",
                "name": "Submit Signed Delivery Claim",
                "description": "Construct and HMAC-sign a delivery claim with evidence payload.",
                "tags": ["delivery-claim", "hmac", "evidence"]
            },
            {
                "id": "provide_delivery_evidence",
                "name": "Provide Delivery Evidence",
                "description": "Attach verifiable delivery evidence (shipping, quality checks) to the claim.",
                "tags": ["evidence", "proof-of-delivery", "quality"]
            },
        ],
    )


def get_all_cards(base_url: str) -> dict[str, dict]:
    """Return all 3 agent cards keyed by role."""
    return {
        "escrow": build_escrow_card(base_url),
        "buyer": build_buyer_card(base_url),
        "vendor": build_vendor_card(base_url),
    }


def get_card_endpoints() -> list[str]:
    """Return the 3 agent-card discovery paths."""
    return [
        "/.well-known/agent-card.json",
        "/agents/buyer/.well-known/agent-card.json",
        "/agents/vendor/.well-known/agent-card.json",
    ]
