import os
import sys
import time
from flask import Flask, render_template, jsonify, request

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.config import GCP_PROJECT, GEMINI_MODEL, HMAC_SECRET_KEY
from common.schemas import AutonomySettings, AgentPolicy
from common.firestore_client import FirestoreClient
from common.pubsub import PubSubManager
from common.identity import sign_payload
from registry.registry import AgentRegistry
from agents.escrow.agent import EscrowMediatorAgent
from agents.buyer.agent import BuyerAgent
from agents.vendor.agent import VendorAgent

app = Flask(__name__)

# Single shared instance for web service demo
db = FirestoreClient(use_mock=True)
pubsub = PubSubManager(use_mock=True)
registry = AgentRegistry(db_client=db)
escrow = EscrowMediatorAgent(db_client=db, registry=registry)

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

@app.route("/")
def index():
    return render_template("index.html", gcp_project=GCP_PROJECT, model=GEMINI_MODEL)

@app.route("/api/state")
def get_state():
    agents = db.list_agents()
    transactions = db.list_transactions()
    reputation = list(db._mock_reputation.values()) if db.use_mock else []
    security_events = db.list_security_events()
    autonomy = db.get_autonomy_settings().model_dump()
    
    audit_logs = []
    if db.use_mock:
        for txn_id, txn in db._mock_transactions.items():
            for log in txn.get("audit_log", []):
                log_copy = dict(log)
                log_copy["transaction_id"] = txn_id
                audit_logs.append(log_copy)
        audit_logs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

    # Compute KPIs
    funds_in_escrow = sum(t.get("amount", 0) for t in transactions if t.get("status") in ["escrowed", "awaiting_human_approval"])
    active_txns = sum(1 for t in transactions if t.get("status") in ["escrowed", "awaiting_human_approval", "paused"])
    needs_review = sum(1 for t in transactions if t.get("status") in ["awaiting_human_approval", "disputed"])
    security_blocks = len(security_events)
    trusted_count = sum(1 for a in agents if a.get("status") == "active" and "rogue" not in a.get("agent_id", ""))
    flagged_count = sum(1 for a in agents if a.get("status") in ["suspended", "paused"] or "rogue" in a.get("agent_id", ""))

    return jsonify({
        "gcp_project": GCP_PROJECT,
        "model": GEMINI_MODEL,
        "agents": agents,
        "transactions": transactions,
        "reputation": reputation,
        "security_events": security_events,
        "autonomy": autonomy,
        "audit_logs": audit_logs,
        "kpis": {
            "funds_in_escrow": funds_in_escrow,
            "active_transactions": active_txns,
            "needs_review": needs_review,
            "security_blocks": security_blocks,
            "network_health": f"{trusted_count} trusted / {flagged_count} flagged"
        }
    })

# --- Autonomy Settings Endpoints ---
@app.route("/api/settings/autonomy", methods=["GET", "POST"])
def settings_autonomy():
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

# --- Transaction Operator Actions ---
@app.route("/api/transactions/<txn_id>/details", methods=["GET"])
def transaction_details(txn_id):
    txn = db.get_transaction(txn_id)
    if not txn:
        return jsonify({"error": "Transaction not found"}), 404
    return jsonify(txn)

@app.route("/api/transactions/<txn_id>/approve", methods=["POST"])
def transaction_approve(txn_id):
    try:
        decision = escrow.operator_approve_release(txn_id)
        return jsonify({"success": True, "action": decision.action, "reason": decision.reason})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/transactions/<txn_id>/refund", methods=["POST"])
def transaction_refund(txn_id):
    try:
        data = request.get_json(silent=True) or {}
        reason = data.get("reason", "Operator manual refund")
        decision = escrow.operator_refund_buyer(txn_id, reason=reason)
        return jsonify({"success": True, "action": decision.action, "reason": decision.reason})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/transactions/<txn_id>/pause", methods=["POST"])
def transaction_pause(txn_id):
    try:
        decision = escrow.operator_pause_transaction(txn_id)
        return jsonify({"success": True, "action": decision.action, "reason": decision.reason})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/transactions/<txn_id>/resume", methods=["POST"])
def transaction_resume(txn_id):
    try:
        decision = escrow.operator_resume_transaction(txn_id)
        return jsonify({"success": True, "action": decision.action, "reason": decision.reason})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --- Agent Governance Endpoints ---
@app.route("/api/agents/<agent_id>/status", methods=["POST"])
def agent_set_status(agent_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status", "active")
    if status not in ["active", "paused", "suspended"]:
        return jsonify({"error": "Invalid status"}), 400
    try:
        agent = registry.set_agent_status(agent_id, status)
        return jsonify({"success": True, "agent": agent.model_dump()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/agents/<agent_id>/policy", methods=["POST"])
def agent_set_policy(agent_id):
    data = request.get_json(silent=True) or {}
    try:
        policy = AgentPolicy(**data)
        agent = registry.update_agent_policy(agent_id, policy)
        return jsonify({"success": True, "agent": agent.model_dump()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --- Security Center Endpoints ---
@app.route("/api/security/events", methods=["GET"])
def security_events_list():
    return jsonify(db.list_security_events())

@app.route("/api/security/events/<event_id>/resolve", methods=["POST"])
def security_event_resolve(event_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status", "resolved")
    db.update_security_event_status(event_id, status)
    return jsonify({"success": True, "event_id": event_id, "status": status})

# --- Demo Action Endpoints ---
@app.route("/api/action/initiate", methods=["POST"])
def action_initiate():
    data = request.get_json(silent=True) or {}
    buyer_id = data.get("buyer_id", "buyer-enterprise-01")
    vendor_id = data.get("vendor_id", "vendor-prime-logistics")
    amount = float(data.get("amount", 5000.0))
    txn_id = f"txn-{int(time.time())}"

    buyer = BuyerAgent(agent_id=buyer_id, pubsub_mgr=pubsub)
    req = buyer.initiate_transaction(
        transaction_id=txn_id,
        vendor_id=vendor_id,
        amount=amount,
        delivery_conditions=["hardware_received", "quality_passed"]
    )
    decision = escrow.initiate_escrow(req)
    return jsonify({"transaction_id": txn_id, "action": decision.action, "reason": decision.reason})

@app.route("/api/action/claim_spoofed", methods=["POST"])
def action_claim_spoofed():
    data = request.get_json(silent=True) or {}
    txn_id = data.get("transaction_id")
    if not txn_id and db._mock_transactions:
        # Pick latest non-released transaction or latest transaction
        txns = list(db._mock_transactions.keys())
        txn_id = txns[-1]
    
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

@app.route("/api/action/claim_legit", methods=["POST"])
def action_claim_legit():
    data = request.get_json(silent=True) or {}
    txn_id = data.get("transaction_id")
    if not txn_id and db._mock_transactions:
        txns = list(db._mock_transactions.keys())
        txn_id = txns[-1]

    if not txn_id:
        return jsonify({"error": "No transaction found"}), 400

    vendor_id = db._mock_transactions[txn_id].get("vendor_id", "vendor-prime-logistics")
    vendor = VendorAgent(agent_id=vendor_id, pubsub_mgr=pubsub)

    evidence = {"hardware_received": True, "quality_passed": True}
    claim = vendor.submit_delivery_claim(
        transaction_id=txn_id,
        evidence=evidence
    )
    decision = escrow.process_claim(claim)
    return jsonify({"action": decision.action, "reason": decision.reason})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
