
from aiadapter.agents.base_agent import BaseAgent


class AgentManager:
    """
    Manager for creating and managing multiple agents.
    """

    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}

    def register_agent(self, agent_id: str, agent: BaseAgent) -> None:
        """
        Register an agent with the manager.
        """
        self.agents[agent_id] = agent

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        """
        Get an agent by ID.
        """
        return self.agents.get(agent_id)

    def remove_agent(self, agent_id: str) -> None:
        """
        Remove an agent from the manager.
        """
        if agent_id in self.agents:
            del self.agents[agent_id]

    def list_agents(self) -> dict[str, BaseAgent]:
        """
        List all registered agents.
        """
        return self.agents

    def reset_agent(self, agent_id: str) -> None:
        """
        Reset an agent's state (e.g., clear conversation history).
        """
        agent = self.get_agent(agent_id)
        if agent:
            agent.reset()

    def reset_all_agents(self) -> None:
        """
        Reset all agents' states.
        """
        for agent in self.agents.values():
            agent.reset()
