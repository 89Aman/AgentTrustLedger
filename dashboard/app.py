import os
import sys
import time
from flask import Flask, render_template, jsonify, request

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.config import GCP_PROJECT, GEMINI_MODEL, HMAC_SECRET_KEY
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

# Seed default demo agents
registry.register_agent("buyer-enterprise-01", "buyer", ["global_procurement", "automated_escrow"])
registry.register_agent("vendor-prime-logistics", "vendor", ["hardware_supply", "express_shipping"])
registry.register_agent("vendor-rogue-actor", "vendor", ["unverified_supplier"])

@app.route("/")
def index():
    return render_template("index.html", gcp_project=GCP_PROJECT, model=GEMINI_MODEL)

@app.route("/api/state")
def get_state():
    agents = list(db._mock_agents.values()) if db.use_mock else []
    transactions = list(db._mock_transactions.values()) if db.use_mock else []
    reputation = list(db._mock_reputation.values()) if db.use_mock else []
    
    audit_logs = []
    if db.use_mock:
        for txn_id, txn in db._mock_transactions.items():
            for log in txn.get("audit_log", []):
                log_copy = dict(log)
                log_copy["transaction_id"] = txn_id
                audit_logs.append(log_copy)
        audit_logs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

    return jsonify({
        "gcp_project": GCP_PROJECT,
        "model": GEMINI_MODEL,
        "agents": agents,
        "transactions": transactions,
        "reputation": reputation,
        "audit_logs": audit_logs
    })

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
        txn_id = list(db._mock_transactions.keys())[-1]
    
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
        txn_id = list(db._mock_transactions.keys())[-1]

    if not txn_id:
        return jsonify({"error": "No transaction found"}), 400

    vendor_id = db._mock_transactions[txn_id].get("vendor_id", "vendor-prime-logistics")
    vendor = VendorAgent(agent_id=vendor_id, pubsub_mgr=pubsub)

    # Ensure status is escrowed for claim retry
    db.save_transaction(txn_id, {"status": "escrowed"})

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
