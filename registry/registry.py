import time
from typing import Optional, Literal, List
from common.schemas import AgentRegistration, AgentPolicy
from common.firestore_client import FirestoreClient

class AgentNotFoundError(Exception):
    pass

class AgentSuspendedError(Exception):
    pass

class AgentPausedError(Exception):
    pass

class AgentPolicyViolationError(Exception):
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
        public_key: Optional[str] = None,
        policy: Optional[AgentPolicy] = None
    ) -> AgentRegistration:
        registration = AgentRegistration(
            agent_id=agent_id,
            agent_type=agent_type,
            capabilities=capabilities,
            public_key=public_key,
            registered_at=time.time(),
            status="active",
            policy=policy or AgentPolicy(allowed_capabilities=capabilities)
        )
        self.db.save_agent(registration)
        print(f"[AgentRegistry] Registered agent '{agent_id}' ({agent_type}) with capabilities: {capabilities}")
        return registration

    def get_agent(self, agent_id: str) -> AgentRegistration:
        data = self.db.get_agent(agent_id)
        if not data:
            raise AgentNotFoundError(f"Agent '{agent_id}' is not registered in the Agent Registry.")
        return AgentRegistration(**data)

    def list_all_agents(self) -> List[AgentRegistration]:
        agents_data = self.db.list_agents()
        return [AgentRegistration(**d) for d in agents_data]

    def set_agent_status(self, agent_id: str, status: Literal["active", "paused", "suspended"]) -> AgentRegistration:
        agent = self.get_agent(agent_id)
        agent.status = status
        self.db.save_agent(agent)
        print(f"[AgentRegistry] Updated agent '{agent_id}' status to '{status}'.")
        return agent

    def update_agent_policy(self, agent_id: str, policy: AgentPolicy) -> AgentRegistration:
        agent = self.get_agent(agent_id)
        agent.policy = policy
        self.db.save_agent(agent)
        print(f"[AgentRegistry] Updated policy for agent '{agent_id}'.")
        return agent

    def verify_agent_authorized(self, agent_id: str, expected_type: Optional[str] = None) -> bool:
        agent = self.get_agent(agent_id)
        if agent.status == "suspended":
            raise AgentSuspendedError(f"Agent '{agent_id}' is suspended by security policy.")
        if agent.status == "paused":
            raise AgentPausedError(f"Agent '{agent_id}' is temporarily paused by operator.")
        if expected_type and agent.agent_type != expected_type:
            raise ValueError(f"Agent '{agent_id}' type '{agent.agent_type}' does not match expected '{expected_type}'.")
        return True
