from typing import Optional, Dict, Any
from common.config import GEMINI_MODEL, HMAC_SECRET_KEY, PUBSUB_TOPIC_VENDOR_TO_ESCROW
from common.schemas import DeliveryClaim
from common.identity import sign_payload
from common.pubsub import PubSubManager
from common.tracing import traced_step

try:
    from google.adk.agents import LlmAgent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

class VendorAgent:
    """
    Vendor Fulfillment Agent.
    Fulfills contract terms, constructs delivery proof, signs delivery claims,
    and publishes claims to the Escrow Mediator over Pub/Sub.
    """
    def __init__(self, agent_id: str = "vendor-agent-01", pubsub_mgr: Optional[PubSubManager] = None):
        self.agent_id = agent_id
        self.pubsub_mgr = pubsub_mgr or PubSubManager()
        self.model = GEMINI_MODEL

        if ADK_AVAILABLE:
            try:
                self.adk_agent = LlmAgent(
                    name=self.agent_id,
                    model=self.model,
                    instruction="""You are a vendor supplier agent. You:
                    1. Accept procurement orders
                    2. Assemble verifiable delivery evidence
                    3. Submit signed delivery claims to escrow""",
                    tools=[]
                )
            except Exception as e:
                print(f"[VendorAgent] LlmAgent init fallback: {e}")
                self.adk_agent = None
        else:
            self.adk_agent = None

    @traced_step("vendor.submit_delivery_claim")
    def submit_delivery_claim(
        self,
        transaction_id: str,
        evidence: Dict[str, Any],
        override_signature: Optional[str] = None
    ) -> DeliveryClaim:
        if override_signature:
            sig = override_signature
        else:
            payload_to_sign = {
                "transaction_id": transaction_id,
                "vendor_id": self.agent_id,
                "evidence": evidence
            }
            sig = sign_payload(payload_to_sign, HMAC_SECRET_KEY)

        claim = DeliveryClaim(
            transaction_id=transaction_id,
            vendor_id=self.agent_id,
            evidence=evidence,
            signature=sig
        )

        self.pubsub_mgr.publish_message(
            topic_name=PUBSUB_TOPIC_VENDOR_TO_ESCROW,
            sender_id=self.agent_id,
            payload_type="DeliveryClaim",
            payload=claim.model_dump()
        )
        print(f"[VendorAgent:{self.agent_id}] Submitted delivery claim for transaction '{transaction_id}'.")
        return claim
