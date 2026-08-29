import os
import sys
import time
import traceback
from flask import Flask, render_template, jsonify, request

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.config import (
    GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GEMINI_MODEL,
    HMAC_SECRET_KEY, CLOUD_RUN_SERVICE_URL, USE_FIRESTORE, USE_PUBSUB,
    USE_CLOUD_TRACE, DEMO_MODE, PORT,
)
from common.schemas import AutonomySettings, AgentPolicy
from common.firestore_client import FirestoreClient
from common.pubsub import PubSubManager
from common.identity import sign_payload
from common.agent_cards import build_escrow_card, build_buyer_card, build_vendor_card
from registry.registry import AgentRegistry
from agents.escrow.agent import EscrowMediatorAgent
from agents.buyer.agent import BuyerAgent
from agents.vendor.agent import VendorAgent

app = Flask(__name__)

# --- Service Initialization ---
# Determine mock vs real based on config flags
_use_mock_db = not USE_FIRESTORE
_use_mock_pubsub = not USE_PUBSUB

db = FirestoreClient(use_mock=_use_mock_db)
pubsub = PubSubManager(use_mock=_use_mock_pubsub)
registry = AgentRegistry(db_client=db)
escrow = EscrowMediatorAgent(db_client=db, registry=registry)

# Initialize tracing if configured
if USE_CLOUD_TRACE:
    from common.tracing import init_tracing
    init_tracing()

# Seed default demo agents with policies
registry.register_agent(
    "buyer-enterprise-01",
    "buyer",
    ["global_procurement", "automated_escrow"],
    policy=AgentPolicy(max_transaction_amount=25000.0, require_human_approval_above=10000.0)
)
registry.register_agent(
    "vendor-prime-logistics",
    "vendor",
    ["hardware_supply", "express_shipping"],
    policy=AgentPolicy(max_transaction_amount=15000.0)
)
registry.register_agent(
    "vendor-rogue-actor",
    "vendor",
    ["unverified_supplier"],
    policy=AgentPolicy(max_transaction_amount=5000.0)
)

# Seed initial demo transaction
initial_txn_id = "txn-escrow-8801"
buyer_agent = BuyerAgent(agent_id="buyer-enterprise-01", pubsub_mgr=pubsub)
req = buyer_agent.initiate_transaction(
    transaction_id=initial_txn_id,
    vendor_id="vendor-prime-logistics",
    amount=5000.0,
    delivery_conditions=["hardware_received", "quality_passed"]
)
escrow.initiate_escrow(req)


# ====== HELPER: Get base URL ======
def _get_base_url() -> str:
    """Return the base URL for agent cards — uses Cloud Run URL if set, else request context."""
    if CLOUD_RUN_SERVICE_URL:
        return CLOUD_RUN_SERVICE_URL.rstrip("/")
    return request.url_root.rstrip("/")


# ====== A2A AGENT CARD DISCOVERY ENDPOINTS ======

@app.route("/.well-known/agent-card.json")
def agent_card_escrow():
    """A2A discovery endpoint for the Escrow Mediator agent."""
    card = build_escrow_card(_get_base_url())
    return jsonify(card), 200, {"Content-Type": "application/json"}


@app.route("/agents/buyer/.well-known/agent-card.json")
def agent_card_buyer():
    """A2A discovery endpoint for the Buyer agent."""
    card = build_buyer_card(_get_base_url())
    return jsonify(card), 200, {"Content-Type": "application/json"}


@app.route("/agents/vendor/.well-known/agent-card.json")
def agent_card_vendor():
    """A2A discovery endpoint for the Vendor agent."""
    card = build_vendor_card(_get_base_url())
    return jsonify(card), 200, {"Content-Type": "application/json"}


# ====== HEALTH & DIAGNOSTICS ======

@app.route("/api/health")
def api_health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "agent-trust-ledger",
        "project": GOOGLE_CLOUD_PROJECT,
        "region": GOOGLE_CLOUD_LOCATION,
        "timestamp": time.time(),
    })


@app.route("/api/diagnostics")
def api_diagnostics():
    """Diagnostics endpoint — reports service connection status."""
    firestore_status = "in-memory fallback"
    if not db.use_mock:
        firestore_status = "connected (production)"
    elif USE_FIRESTORE:
        firestore_status = "configured but fallback active"

    pubsub_status = "in-memory fallback"
    if not pubsub.use_mock:
        pubsub_status = "connected (production)"
    elif USE_PUBSUB:
        pubsub_status = "configured but fallback active"

    trace_status = "disabled"
    if USE_CLOUD_TRACE:
        from common.tracing import _tracing_initialized
        trace_status = "connected (Cloud Trace)" if _tracing_initialized else "configured but export failed"

    vertex_status = "configured"
    vertex_model = GEMINI_MODEL

    return jsonify({
        "project": GOOGLE_CLOUD_PROJECT,
        "region": GOOGLE_CLOUD_LOCATION,
        "model": vertex_model,
        "cloud_run_url": CLOUD_RUN_SERVICE_URL or "not set",
        "demo_mode": DEMO_MODE,
        "services": {
            "firestore": firestore_status,
            "pubsub": pubsub_status,
            "cloud_trace": trace_status,
            "vertex_ai": vertex_status,
        },
        "agent_cards": {
            "escrow": f"{_get_base_url()}/.well-known/agent-card.json",
            "buyer": f"{_get_base_url()}/agents/buyer/.well-known/agent-card.json",
            "vendor": f"{_get_base_url()}/agents/vendor/.well-known/agent-card.json",
        },
    })


@app.route("/api/registry/verify")
def api_registry_verify():
    """Verify official Google Cloud Agent Registry registration status."""
    try:
        from registry.google_agent_registry import verify_official_registration
        result = verify_official_registration(GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION)
        return jsonify(result)
    except ImportError:
        return jsonify({"status": "not_available", "message": "Agent Registry module not loaded."})
    except Exception as e:
        return jsonify({"status": "verification_failed", "error": str(e)})


# ====== API ENDPOINTS ======

@app.route("/api/agents", methods=["GET"])
def api_agents_list():
    """List all registered agents."""
    try:
        agents = db.list_agents()
        return jsonify(agents)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<agent_id>", methods=["GET"])
def api_agent_detail(agent_id):
    """Get a single agent's details."""
    try:
        agent = db.get_agent(agent_id)
        if not agent:
            return jsonify({"error": f"Agent '{agent_id}' not found"}), 404
        return jsonify(agent)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/transactions", methods=["GET", "POST"])
def api_transactions():
    """List or create transactions."""
    if request.method == "GET":
        try:
            return jsonify(db.list_transactions())
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # POST — create new transaction
    try:
        data = request.get_json(silent=True) or {}
        buyer_id = data.get("buyer_id", "buyer-enterprise-01")
        vendor_id = data.get("vendor_id", "vendor-prime-logistics")
        amount = float(data.get("amount", 5000.0))
        txn_id = f"txn-{int(time.time())}"

        buyer = BuyerAgent(agent_id=buyer_id, pubsub_mgr=pubsub)
        txn_req = buyer.initiate_transaction(
            transaction_id=txn_id,
            vendor_id=vendor_id,
            amount=amount,
            delivery_conditions=data.get("delivery_conditions", ["hardware_received", "quality_passed"])
        )
        decision = escrow.initiate_escrow(txn_req)
        return jsonify({"transaction_id": txn_id, "action": decision.action, "reason": decision.reason})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/transactions/<transaction_id>", methods=["GET"])
def api_transaction_detail(transaction_id):
    """Get transaction details."""
    try:
        txn = db.get_transaction(transaction_id)
        if not txn:
            return jsonify({"error": "Transaction not found"}), 404
        return jsonify(txn)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/transactions/<transaction_id>/delivery-claims", methods=["POST"])
def api_delivery_claim(transaction_id):
    """Submit a delivery claim for a transaction."""
    try:
        data = request.get_json(silent=True) or {}
        vendor_id = data.get("vendor_id")
        evidence = data.get("evidence", {})
        signature = data.get("signature", "")

        if not vendor_id:
            return jsonify({"error": "vendor_id is required"}), 400

        from common.schemas import DeliveryClaim
        claim = DeliveryClaim(
            transaction_id=transaction_id,
            vendor_id=vendor_id,
            evidence=evidence,
            signature=signature,
        )
        decision = escrow.process_claim(claim)
        return jsonify({"action": decision.action, "reason": decision.reason, "security_flag_raised": decision.security_flag_raised})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit-events", methods=["GET"])
def api_audit_events():
    """List audit events."""
    try:
        audit_logs = db.list_audit_events()
        return jsonify(audit_logs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ====== DASHBOARD ======

@app.route("/")
def index():
    return render_template("index.html", gcp_project=GOOGLE_CLOUD_PROJECT, model=GEMINI_MODEL)


@app.route("/api/state")
def get_state():
    try:
        agents = db.list_agents()
        transactions = db.list_transactions()
        reputation = db.list_reputation()
        security_events = db.list_security_events()
        autonomy = db.get_autonomy_settings().model_dump()
        audit_logs = db.list_audit_events()

        # Compute KPIs
        funds_in_escrow = sum(t.get("amount", 0) for t in transactions if t.get("status") in ["escrowed", "awaiting_human_approval"])
        active_txns = sum(1 for t in transactions if t.get("status") in ["escrowed", "awaiting_human_approval", "paused"])
        needs_review = sum(1 for t in transactions if t.get("status") in ["awaiting_human_approval", "disputed"])
        security_blocks = len(security_events)
        trusted_count = sum(1 for a in agents if a.get("status") == "active" and "rogue" not in a.get("agent_id", ""))
        flagged_count = sum(1 for a in agents if a.get("status") in ["suspended", "paused"] or "rogue" in a.get("agent_id", ""))

        # Service status for diagnostics
        firestore_mode = "in-memory fallback"
        if not db.use_mock:
            firestore_mode = "Firestore (production)"
        pubsub_mode = "in-memory fallback"
        if not pubsub.use_mock:
            pubsub_mode = "Pub/Sub (production)"

        return jsonify({
            "gcp_project": GOOGLE_CLOUD_PROJECT,
            "model": GEMINI_MODEL,
            "agents": agents,
            "transactions": transactions,
            "reputation": reputation,
            "security_events": security_events,
            "autonomy": autonomy,
            "audit_logs": audit_logs,
            "services": {
                "firestore": firestore_mode,
                "pubsub": pubsub_mode,
            },
            "kpis": {
                "funds_in_escrow": funds_in_escrow,
                "active_transactions": active_txns,
                "needs_review": needs_review,
                "security_blocks": security_blocks,
                "network_health": f"{trusted_count} trusted / {flagged_count} flagged"
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# --- Autonomy Settings Endpoints ---
@app.route("/api/settings/autonomy", methods=["GET", "POST"])
def settings_autonomy():
    try:
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            current = db.get_autonomy_settings()
            if "mode" in data:
                current.mode = data["mode"]
            if "approval_amount_threshold" in data:
                current.approval_amount_threshold = float(data["approval_amount_threshold"])
            if "minimum_release_confidence" in data:
                current.minimum_release_confidence = float(data["minimum_release_confidence"])
            if "require_approval_for_security_events" in data:
                current.require_approval_for_security_events = bool(data["require_approval_for_security_events"])
            db.save_autonomy_settings(current)
            return jsonify({"success": True, "autonomy": current.model_dump()})
        return jsonify(db.get_autonomy_settings().model_dump())
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# --- Transaction Operator Actions ---
@app.route("/api/transactions/<txn_id>/details", methods=["GET"])
def transaction_details(txn_id):
    try:
        txn = db.get_transaction(txn_id)
        if not txn:
            return jsonify({"error": "Transaction not found"}), 404
        return jsonify(txn)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/transactions/<txn_id>/approve", methods=["POST"])
def transaction_approve(txn_id):
    try:
        decision = escrow.operator_approve_release(txn_id)
        return jsonify({"success": True, "action": decision.action, "reason": decision.reason})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


@app.route("/api/transactions/<txn_id>/refund", methods=["POST"])
def transaction_refund(txn_id):
    try:
        data = request.get_json(silent=True) or {}
        reason = data.get("reason", "Operator manual refund")
        decision = escrow.operator_refund_buyer(txn_id, reason=reason)
        return jsonify({"success": True, "action": decision.action, "reason": decision.reason})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


@app.route("/api/transactions/<txn_id>/pause", methods=["POST"])
def transaction_pause(txn_id):
    try:
        decision = escrow.operator_pause_transaction(txn_id)
        return jsonify({"success": True, "action": decision.action, "reason": decision.reason})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


@app.route("/api/transactions/<txn_id>/resume", methods=["POST"])
def transaction_resume(txn_id):
    try:
        decision = escrow.operator_resume_transaction(txn_id)
        return jsonify({"success": True, "action": decision.action, "reason": decision.reason})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


# --- Agent Governance Endpoints ---
@app.route("/api/agents/<agent_id>/status", methods=["POST"])
def agent_set_status(agent_id):
    try:
        data = request.get_json(silent=True) or {}
        status = data.get("status", "active")
        if status not in ["active", "paused", "suspended"]:
            return jsonify({"error": "Invalid status"}), 400
        agent = registry.set_agent_status(agent_id, status)
        return jsonify({"success": True, "agent": agent.model_dump()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


@app.route("/api/agents/<agent_id>/policy", methods=["POST"])
def agent_set_policy(agent_id):
    try:
        data = request.get_json(silent=True) or {}
        policy = AgentPolicy(**data)
        agent = registry.update_agent_policy(agent_id, policy)
        return jsonify({"success": True, "agent": agent.model_dump()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


# --- Security Center Endpoints ---
@app.route("/api/security/events", methods=["GET"])
def security_events_list():
    try:
        return jsonify(db.list_security_events())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/security/events/<event_id>/resolve", methods=["POST"])
def security_event_resolve(event_id):
    try:
        data = request.get_json(silent=True) or {}
        status = data.get("status", "resolved")
        db.update_security_event_status(event_id, status)
        return jsonify({"success": True, "event_id": event_id, "status": status})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# --- Demo Action Endpoints ---
@app.route("/api/action/initiate", methods=["POST"])
def action_initiate():
    try:
        data = request.get_json(silent=True) or {}
        buyer_id = data.get("buyer_id", "buyer-enterprise-01")
        vendor_id = data.get("vendor_id", "vendor-prime-logistics")
        amount = float(data.get("amount", 5000.0))
        txn_id = f"txn-{int(time.time())}"

        buyer = BuyerAgent(agent_id=buyer_id, pubsub_mgr=pubsub)
        txn_req = buyer.initiate_transaction(
            transaction_id=txn_id,
            vendor_id=vendor_id,
            amount=amount,
            delivery_conditions=["hardware_received", "quality_passed"]
        )
        decision = escrow.initiate_escrow(txn_req)
        return jsonify({"transaction_id": txn_id, "action": decision.action, "reason": decision.reason})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "reason": f"Initiation failed: {e}"}), 500


@app.route("/api/action/claim_spoofed", methods=["POST"])
def action_claim_spoofed():
    try:
        data = request.get_json(silent=True) or {}
        txn_id = data.get("transaction_id")
        if not txn_id:
            txns = db.list_transactions()
            if txns:
                txn_id = txns[0].get("transaction_id")

        if not txn_id:
            return jsonify({"error": "No transaction found"}), 400

        rogue = VendorAgent(agent_id="vendor-rogue-actor", pubsub_mgr=pubsub)
        claim = rogue.submit_delivery_claim(
            transaction_id=txn_id,
            evidence={"hardware_received": True, "quality_passed": True},
            override_signature="bad-spoofed-signature"
        )
        decision = escrow.process_claim(claim)
        return jsonify({"action": decision.action, "reason": decision.reason, "security_flag": decision.security_flag_raised})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "reason": f"Spoofed claim failed: {e}"}), 500


@app.route("/api/action/claim_legit", methods=["POST"])
def action_claim_legit():
    try:
        data = request.get_json(silent=True) or {}
        txn_id = data.get("transaction_id")
        if not txn_id:
            txns = db.list_transactions()
            if txns:
                txn_id = txns[0].get("transaction_id")

        if not txn_id:
            return jsonify({"error": "No transaction found"}), 400

        txn_data = db.get_transaction(txn_id) or {}
        vendor_id = txn_data.get("vendor_id", "vendor-prime-logistics")
        vendor = VendorAgent(agent_id=vendor_id, pubsub_mgr=pubsub)

        evidence = {"hardware_received": True, "quality_passed": True}
        claim = vendor.submit_delivery_claim(
            transaction_id=txn_id,
            evidence=evidence
        )
        decision = escrow.process_claim(claim)
        return jsonify({"action": decision.action, "reason": decision.reason})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "reason": f"Legit claim failed: {e}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", PORT))
    app.run(host="0.0.0.0", port=port, debug=True)
