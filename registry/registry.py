import time
from typing import Optional, Literal
from common.schemas import AgentRegistration
from common.firestore_client import FirestoreClient

class AgentNotFoundError(Exception):
    pass

class AgentSuspendedError(Exception):
    pass

class AgentRegistry:
    """
    Agent Registry service for publishing, versioning, discovering, and verifying
    enterprise-approved transacting agents (Agent Registry capability).
    """
    def __init__(self, db_client: Optional[FirestoreClient] = None):
        self.db = db_client or FirestoreClient()

    def register_agent(
        self,
        agent_id: str,
        agent_type: Literal["buyer", "vendor", "escrow"],
        capabilities: list[str],
        public_key: Optional[str] = None
    ) -> AgentRegistration:
        registration = AgentRegistration(
            agent_id=agent_id,
            agent_type=agent_type,
            capabilities=capabilities,
            public_key=public_key,
            registered_at=time.time(),
            status="active"
        )
        self.db.save_agent(registration)
        print(f"[AgentRegistry] Registered agent '{agent_id}' ({agent_type}) with capabilities: {capabilities}")
        return registration

    def get_agent(self, agent_id: str) -> AgentRegistration:
        data = self.db.get_agent(agent_id)
        if not data:
            raise AgentNotFoundError(f"Agent '{agent_id}' is not registered in the Agent Registry.")
        return AgentRegistration(**data)

    def verify_agent_authorized(self, agent_id: str, expected_type: Optional[str] = None) -> bool:
        agent = self.get_agent(agent_id)
        if agent.status != "active":
            raise AgentSuspendedError(f"Agent '{agent_id}' is suspended.")
        if expected_type and agent.agent_type != expected_type:
            raise ValueError(f"Agent '{agent_id}' type '{agent.agent_type}' does not match expected '{expected_type}'.")
        return True
