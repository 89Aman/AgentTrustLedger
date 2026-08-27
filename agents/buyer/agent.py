import time
from typing import Optional
from common.config import GEMINI_MODEL, HMAC_SECRET_KEY, PUBSUB_TOPIC_BUYER_TO_ESCROW
from common.schemas import TransactionRequest
from common.identity import sign_payload
from common.pubsub import PubSubManager
from common.tracing import traced_step

try:
    from google.adk.agents import LlmAgent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

class BuyerAgent:
    """
    Buyer Procurement Agent.
    Selects vendors based on public reputation scores, formats transaction contracts,
    signs payloads with HMAC keys, and publishes to Pub/Sub (Agent Gateway).
    """
    def __init__(self, agent_id: str = "buyer-agent-01", pubsub_mgr: Optional[PubSubManager] = None):
        self.agent_id = agent_id
        self.pubsub_mgr = pubsub_mgr or PubSubManager()
        self.model = GEMINI_MODEL

        if ADK_AVAILABLE:
            try:
                self.adk_agent = LlmAgent(
                    name=self.agent_id,
                    model=self.model,
                    instruction="""You are a procurement buyer agent. You:
                    1. Inspect vendor reputation scores before transacting
                    2. Formulate explicit transaction agreements with delivery conditions
                    3. Transact securely via Escrow Mediator""",
                    tools=[]
                )
            except Exception as e:
                print(f"[BuyerAgent] LlmAgent init fallback: {e}")
                self.adk_agent = None
        else:
            self.adk_agent = None

    @traced_step("buyer.initiate_transaction")
    def initiate_transaction(
        self,
        transaction_id: str,
        vendor_id: str,
        amount: float,
        delivery_conditions: list[str]
    ) -> TransactionRequest:
        payload_to_sign = {
            "transaction_id": transaction_id,
            "buyer_id": self.agent_id,
            "vendor_id": vendor_id,
            "amount": amount,
            "delivery_conditions": delivery_conditions
        }
        sig = sign_payload(payload_to_sign, HMAC_SECRET_KEY)
        
        req = TransactionRequest(
            transaction_id=transaction_id,
            buyer_id=self.agent_id,
            vendor_id=vendor_id,
            amount=amount,
            delivery_conditions=delivery_conditions,
            signature=sig
        )

        self.pubsub_mgr.publish_message(
            topic_name=PUBSUB_TOPIC_BUYER_TO_ESCROW,
            sender_id=self.agent_id,
            payload_type="TransactionRequest",
            payload=req.model_dump()
        )
        print(f"[BuyerAgent:{self.agent_id}] Initiated transaction '{transaction_id}' with vendor '{vendor_id}' for ${amount}.")
        return req
