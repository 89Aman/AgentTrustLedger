from typing import Literal, Optional, Any, Dict, List
from pydantic import BaseModel, Field
import time

class AgentPolicy(BaseModel):
    max_transaction_amount: float = 10000.0
    max_daily_transactions: int = 20
    require_human_approval_above: float = 5000.0
    allowed_capabilities: list[str] = Field(default_factory=list)

class AgentRegistration(BaseModel):
    agent_id: str
    agent_type: Literal["buyer", "vendor", "escrow"]
    capabilities: list[str]
    public_key: Optional[str] = None
    registered_at: float = Field(default_factory=time.time)
    status: Literal["active", "paused", "suspended"] = "active"
    policy: AgentPolicy = Field(default_factory=AgentPolicy)

class AutonomySettings(BaseModel):
    mode: Literal["manual", "guarded_auto", "full_auto"] = "guarded_auto"
    minimum_release_confidence: float = 0.85
    approval_amount_threshold: float = 5000.0
    require_approval_for_security_events: bool = True

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
    action: Literal["hold", "release", "refund", "reject", "awaiting_human_approval", "paused"]
    reason: str
    reputation_delta: int = 0
    security_flag_raised: bool = False
    confidence: float = 0.96

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
    event_type: Literal["successful_delivery", "disputed_delivery", "security_violation", "registration", "human_operator_action", "policy_update"]
    quality_score_after: float
    security_flags_after: int
    details: str
    actor: str = "system"
    timestamp: float = Field(default_factory=time.time)

class SecurityEvent(BaseModel):
    event_id: str
    transaction_id: str
    agent_id: str
    severity: Literal["critical", "high", "medium", "low"] = "high"
    event_type: str
    reason: str
    status: Literal["open", "resolved", "false_positive"] = "open"
    created_at: float = Field(default_factory=time.time)
    trace_id: Optional[str] = None

class MessageEnvelope(BaseModel):
    message_id: str
    sender_id: str
    target_topic: str
    payload_type: str
    payload: dict[str, Any]
    signature: str
    timestamp: float = Field(default_factory=time.time)
