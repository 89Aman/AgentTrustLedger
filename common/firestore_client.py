import os
import time
from typing import Optional, Any, List, Dict
from common.config import GOOGLE_CLOUD_PROJECT, USE_FIRESTORE
from common.schemas import AgentRegistration, ReputationRecord, LedgerEntry, AutonomySettings, SecurityEvent

class FirestoreClient:
    """
    Wrapper around Google Cloud Firestore client.
    Supports in-memory mock fallback when running in pure offline testing mode.
    """
    def __init__(self, use_mock: Optional[bool] = None):
        if use_mock is not None:
            self.use_mock = use_mock
        else:
            self.use_mock = not USE_FIRESTORE

        self.db = None
        self.backend_mode = "in-memory fallback"

        # Always initialize mock containers to prevent attribute errors
        self._mock_agents = {}
        self._mock_transactions = {}
        self._mock_reputation = {}
        self._mock_ledgers = {}
        self._mock_settings = {"autonomy": AutonomySettings().model_dump()}
        self._mock_security_events = {}
        self._mock_audit_events = []

        if not self.use_mock:
            try:
                from google.cloud import firestore
                self.db = firestore.Client(project=GOOGLE_CLOUD_PROJECT)
                if os.getenv("FIRESTORE_EMULATOR_HOST"):
                    self.backend_mode = "Firestore emulator"
                else:
                    self.backend_mode = "Firestore (production)"
                print(f"[FirestoreClient] Initialized: {self.backend_mode} (project={GOOGLE_CLOUD_PROJECT})")
            except Exception as e:
                print(f"[FirestoreClient] Cloud client initialization skipped/failed ({e}), using in-memory store.")
                self.use_mock = True
                self.backend_mode = "in-memory fallback"
        else:
            print("[FirestoreClient] Initialized: in-memory fallback mode")

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

    def list_agents(self) -> List[dict]:
        if self.use_mock:
            return list(self._mock_agents.values())
        docs = self.db.collection("agents").stream()
        return [d.to_dict() for d in docs]

    # --- Settings Operations (Autonomy Mode & Policies) ---
    def get_autonomy_settings(self) -> AutonomySettings:
        if self.use_mock:
            data = self._mock_settings.get("autonomy", {})
            return AutonomySettings(**data)
        doc = self.db.collection("settings").document("autonomy").get()
        if doc.exists:
            return AutonomySettings(**doc.to_dict())
        default = AutonomySettings()
        self.save_autonomy_settings(default)
        return default

    def save_autonomy_settings(self, settings: AutonomySettings):
        if self.use_mock:
            self._mock_settings["autonomy"] = settings.model_dump()
            return
        self.db.collection("settings").document("autonomy").set(settings.model_dump())

    # --- Security Events Operations ---
    def save_security_event(self, event: SecurityEvent):
        if self.use_mock:
            self._mock_security_events[event.event_id] = event.model_dump()
            return
        self.db.collection("security_events").document(event.event_id).set(event.model_dump())

    def list_security_events(self) -> List[dict]:
        if self.use_mock:
            events = list(self._mock_security_events.values())
            events.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return events
        docs = self.db.collection("security_events").order_by("created_at", direction="DESCENDING").stream()
        return [d.to_dict() for d in docs]

    def update_security_event_status(self, event_id: str, status: str):
        if self.use_mock:
            if event_id in self._mock_security_events:
                self._mock_security_events[event_id]["status"] = status
            return
        self.db.collection("security_events").document(event_id).update({"status": status})

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

    def list_transactions(self) -> List[dict]:
        if self.use_mock:
            txns = list(self._mock_transactions.values())
            txns.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return txns
        try:
            docs = self.db.collection("transactions").order_by("created_at", direction="DESCENDING").stream()
            return [d.to_dict() for d in docs]
        except Exception:
            docs = self.db.collection("transactions").stream()
            txns = [d.to_dict() for d in docs]
            txns.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return txns

    def add_audit_log(self, transaction_id: str, log_entry: dict):
        log_entry["timestamp"] = log_entry.get("timestamp", time.time())
        log_entry["transaction_id"] = transaction_id
        if self.use_mock:
            txn = self._mock_transactions.get(transaction_id, {})
            audit = txn.get("audit_log", [])
            audit.append(log_entry)
            txn["audit_log"] = audit
            self._mock_transactions[transaction_id] = txn
            self._mock_audit_events.append(log_entry)
            return
        doc_ref = self.db.collection("transactions").document(transaction_id)
        doc_ref.collection("audit_log").add(log_entry)
        self.db.collection("audit_events").add(log_entry)

    def list_audit_events(self) -> List[dict]:
        if self.use_mock:
            return sorted(self._mock_audit_events, key=lambda x: x.get("timestamp", 0), reverse=True)
        try:
            docs = self.db.collection("audit_events").order_by("timestamp", direction="DESCENDING").limit(100).stream()
            return [d.to_dict() for d in docs]
        except Exception:
            docs = self.db.collection("audit_events").limit(100).stream()
            events = [d.to_dict() for d in docs]
            events.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            return events

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

    def list_reputation(self) -> List[dict]:
        if self.use_mock:
            return list(self._mock_reputation.values())
        docs = self.db.collection("reputation").stream()
        return [d.to_dict() for d in docs]

    def add_ledger_entry(self, entry: LedgerEntry):
        if self.use_mock:
            entries = self._mock_ledgers.get(entry.agent_id, [])
            entries.append(entry.model_dump())
            self._mock_ledgers[entry.agent_id] = entries
            return
        doc_ref = self.db.collection("reputation").document(entry.agent_id)
        doc_ref.collection("ledger").document(entry.entry_id).set(entry.model_dump())
