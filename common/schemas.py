from typing import Literal, Optional, Any
from pydantic import BaseModel, Field
import time

class AgentRegistration(BaseModel):
    agent_id: str
    agent_type: Literal["buyer", "vendor", "escrow"]
    capabilities: list[str]
    public_key: Optional[str] = None
    registered_at: float = Field(default_factory=time.time)
    status: Literal["active", "suspended"] = "active"

class TransactionRequest(BaseModel):
    transaction_id: str
    buyer_id: str
    vendor_id: str
    amount: float
    delivery_conditions: list[str]
    signature: str

class DeliveryClaim(BaseModel):
    transaction_id: str
    vendor_id: str
    evidence: dict[str, Any]
    signature: str

class EscrowDecision(BaseModel):
    transaction_id: str
    action: Literal["hold", "release", "refund", "reject"]
    reason: str
    reputation_delta: int = 0
    security_flag_raised: bool = False

class ReputationRecord(BaseModel):
    agent_id: str
    quality_score: float = 1.0  # successful_deliveries / total_transactions
    total_transactions: int = 0
    successful_deliveries: int = 0
    disputed_deliveries: int = 0
    security_flags: int = 0
    last_updated: float = Field(default_factory=time.time)

class LedgerEntry(BaseModel):
    entry_id: str
    transaction_id: str
    agent_id: str
    event_type: Literal["successful_delivery", "disputed_delivery", "security_violation", "registration"]
    quality_score_after: float
    security_flags_after: int
    details: str
    timestamp: float = Field(default_factory=time.time)

class MessageEnvelope(BaseModel):
    message_id: str
    sender_id: str
    target_topic: str
    payload_type: str
    payload: dict[str, Any]
    signature: str
    timestamp: float = Field(default_factory=time.time)
