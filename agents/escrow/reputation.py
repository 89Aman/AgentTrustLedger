import time
import uuid
from typing import Optional
from common.schemas import ReputationRecord, LedgerEntry
from common.firestore_client import FirestoreClient

class ReputationManager:
    """
    Manages public reputation records and append-only audit ledgers in Firestore (Memory Bank capability).
    Separates delivery quality score from security flags.
    """
    def __init__(self, db_client: Optional[FirestoreClient] = None):
        self.db = db_client or FirestoreClient()

    def get_or_create_reputation(self, agent_id: str) -> ReputationRecord:
        data = self.db.get_reputation(agent_id)
        if data:
            return ReputationRecord(**data)
        record = ReputationRecord(
            agent_id=agent_id,
            quality_score=1.0,
            total_transactions=0,
            successful_deliveries=0,
            disputed_deliveries=0,
            security_flags=0,
            last_updated=time.time()
        )
        self.db.save_reputation(record)
        return record

    def record_successful_delivery(self, agent_id: str, transaction_id: str, details: str = "Successful delivery verified") -> ReputationRecord:
        rep = self.get_or_create_reputation(agent_id)
        rep.total_transactions += 1
        rep.successful_deliveries += 1
        rep.quality_score = round(rep.successful_deliveries / rep.total_transactions, 3)
        rep.last_updated = time.time()
        self.db.save_reputation(rep)

        entry = LedgerEntry(
            entry_id=f"leg-{uuid.uuid4().hex[:8]}",
            transaction_id=transaction_id,
            agent_id=agent_id,
            event_type="successful_delivery",
            quality_score_after=rep.quality_score,
            security_flags_after=rep.security_flags,
            details=details,
            timestamp=time.time()
        )
        self.db.add_ledger_entry(entry)
        print(f"[ReputationManager] Agent '{agent_id}' successful delivery logged. New Quality Score: {rep.quality_score}")
        return rep

    def record_disputed_delivery(self, agent_id: str, transaction_id: str, details: str = "Delivery conditions not met") -> ReputationRecord:
        rep = self.get_or_create_reputation(agent_id)
        rep.total_transactions += 1
        rep.disputed_deliveries += 1
        rep.quality_score = round(rep.successful_deliveries / rep.total_transactions, 3)
        rep.last_updated = time.time()
        self.db.save_reputation(rep)

        entry = LedgerEntry(
            entry_id=f"leg-{uuid.uuid4().hex[:8]}",
            transaction_id=transaction_id,
            agent_id=agent_id,
            event_type="disputed_delivery",
            quality_score_after=rep.quality_score,
            security_flags_after=rep.security_flags,
            details=details,
            timestamp=time.time()
        )
        self.db.add_ledger_entry(entry)
        print(f"[ReputationManager] Agent '{agent_id}' disputed delivery logged. New Quality Score: {rep.quality_score}")
        return rep

    def record_security_violation(self, agent_id: str, transaction_id: str, violation_reason: str) -> ReputationRecord:
        rep = self.get_or_create_reputation(agent_id)
        rep.security_flags += 1
        rep.last_updated = time.time()
        self.db.save_reputation(rep)

        entry = LedgerEntry(
            entry_id=f"leg-{uuid.uuid4().hex[:8]}",
            transaction_id=transaction_id,
            agent_id=agent_id,
            event_type="security_violation",
            quality_score_after=rep.quality_score,
            security_flags_after=rep.security_flags,
            details=violation_reason,
            timestamp=time.time()
        )
        self.db.add_ledger_entry(entry)
        print(f"[ReputationManager] SECURITY VIOLATION logged for agent '{agent_id}'. Total Security Flags: {rep.security_flags}")
        return rep
