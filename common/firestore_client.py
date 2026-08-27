import os
import time
from typing import Optional, Any
from common.config import GCP_PROJECT
from common.schemas import AgentRegistration, ReputationRecord, LedgerEntry

class FirestoreClient:
    """
    Wrapper around Google Cloud Firestore client.
    Supports in-memory mock fallback when running in pure offline testing mode.
    """
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.db = None
        if not use_mock:
            try:
                from google.cloud import firestore
                self.db = firestore.Client(project=GCP_PROJECT)
            except Exception as e:
                print(f"[FirestoreClient] Cloud client initialization skipped/failed ({e}), using in-memory store.")
                self.use_mock = True

        if self.use_mock:
            self._mock_agents = {}
            self._mock_transactions = {}
            self._mock_reputation = {}
            self._mock_ledgers = {}

    # --- Agent Registry Operations ---
    def save_agent(self, agent: AgentRegistration):
        if self.use_mock:
            self._mock_agents[agent.agent_id] = agent.model_dump()
            return
        doc_ref = self.db.collection("agents").document(agent.agent_id)
        doc_ref.set(agent.model_dump())

    def get_agent(self, agent_id: str) -> Optional[dict]:
        if self.use_mock:
            return self._mock_agents.get(agent_id)
        doc = self.db.collection("agents").document(agent_id).get()
        return doc.to_dict() if doc.exists else None

    # --- Transaction Operations (Escrow State & Memory Bank) ---
    def save_transaction(self, transaction_id: str, data: dict):
        if self.use_mock:
            if transaction_id not in self._mock_transactions:
                self._mock_transactions[transaction_id] = data
            else:
                self._mock_transactions[transaction_id].update(data)
            return
        doc_ref = self.db.collection("transactions").document(transaction_id)
        doc_ref.set(data, merge=True)

    def get_transaction(self, transaction_id: str) -> Optional[dict]:
        if self.use_mock:
            return self._mock_transactions.get(transaction_id)
        doc = self.db.collection("transactions").document(transaction_id).get()
        return doc.to_dict() if doc.exists else None

    def add_audit_log(self, transaction_id: str, log_entry: dict):
        log_entry["timestamp"] = log_entry.get("timestamp", time.time())
        if self.use_mock:
            txn = self._mock_transactions.get(transaction_id, {})
            audit = txn.get("audit_log", [])
            audit.append(log_entry)
            txn["audit_log"] = audit
            self._mock_transactions[transaction_id] = txn
            return
        doc_ref = self.db.collection("transactions").document(transaction_id)
        doc_ref.collection("audit_log").add(log_entry)

    # --- Reputation & Audit Ledger Operations ---
    def save_reputation(self, record: ReputationRecord):
        if self.use_mock:
            self._mock_reputation[record.agent_id] = record.model_dump()
            return
        doc_ref = self.db.collection("reputation").document(record.agent_id)
        doc_ref.set(record.model_dump())

    def get_reputation(self, agent_id: str) -> Optional[dict]:
        if self.use_mock:
            return self._mock_reputation.get(agent_id)
        doc = self.db.collection("reputation").document(agent_id).get()
        return doc.to_dict() if doc.exists else None

    def add_ledger_entry(self, entry: LedgerEntry):
        if self.use_mock:
            entries = self._mock_ledgers.get(entry.agent_id, [])
            entries.append(entry.model_dump())
            self._mock_ledgers[entry.agent_id] = entries
            return
        doc_ref = self.db.collection("reputation").document(entry.agent_id)
        doc_ref.collection("ledger").document(entry.entry_id).set(entry.model_dump())
